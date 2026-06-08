from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import ClassVar, Literal
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from exeboard_ai.document_intelligence.core.ids import (
    ClaimId,
    DocumentId,
    SpanId,
    validate_document_id,
    parse_claim_id,
)
from exeboard_ai.document_intelligence.ir.span_index import SpanIndex
from exeboard_ai.document_intelligence.summarization.models import SummaryClaim

QuoteValidationErrorCode = Literal[
    "quote_not_found",
    "quote_outside_cited_spans",
    "normalized_match_only",
    "fuzzy_match",
    "invalid_span_id",
    "document_mismatch",
]
QuoteMatchType = Literal["exact", "normalized", "fuzzy"]
QuoteMatchScope = Literal["cited_spans", "page"]


class QuoteValidationMatch(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    claim_id: ClaimId
    evidence_index: int = Field(ge=0)
    quote: str
    page_number: int = Field(ge=1)
    match_type: QuoteMatchType
    scope: QuoteMatchScope

    @field_validator("claim_id")
    @classmethod
    def _validate_claim_id(cls, value: str) -> ClaimId:
        parse_claim_id(value)
        return value

    @field_validator("quote")
    @classmethod
    def _quote_must_not_be_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("quote must not be empty")
        return value


class QuoteValidationError(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    code: QuoteValidationErrorCode
    message: str
    claim_id: ClaimId
    evidence_index: int | None = Field(default=None, ge=0)
    quote: str | None = None
    expected_document_id: DocumentId | None = None
    actual_document_id: DocumentId | None = None
    source_span_id: SpanId | None = None

    @field_validator("message")
    @classmethod
    def _message_must_not_be_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("message must not be empty")
        return value

    @field_validator("claim_id")
    @classmethod
    def _validate_claim_id(cls, value: str) -> ClaimId:
        parse_claim_id(value)
        return value

    @field_validator("quote")
    @classmethod
    def _quote_must_not_be_empty(cls, value: str | None) -> str | None:
        if value is not None and (not value or not value.strip()):
            raise ValueError("quote must not be empty")
        return value

    @field_validator("source_span_id")
    @classmethod
    def _source_span_id_must_not_be_empty(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("source_span_id must not be empty")
        return value

    @field_validator("expected_document_id", "actual_document_id")
    @classmethod
    def _validate_document_id(cls, value: str | None) -> DocumentId | None:
        if value is None:
            return None
        return validate_document_id(value)


class QuoteValidationResult(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    claim_id: ClaimId
    document_id: DocumentId
    valid: bool
    matches: tuple[QuoteValidationMatch, ...] = ()
    errors: tuple[QuoteValidationError, ...] = ()

    @field_validator("claim_id")
    @classmethod
    def _validate_claim_id(cls, value: str) -> ClaimId:
        parse_claim_id(value)
        return value

    @field_validator("document_id")
    @classmethod
    def _validate_document_id(cls, value: str) -> DocumentId:
        return validate_document_id(value)

    @model_validator(mode="after")
    def _valid_must_match_errors(self) -> QuoteValidationResult:
        if self.valid != (not self.errors):
            raise ValueError("valid must be True iff errors is empty")
        for match in self.matches:
            if match.claim_id != self.claim_id:
                raise ValueError("match claim_id must match result claim_id")
        for error in self.errors:
            if error.claim_id != self.claim_id:
                raise ValueError("error claim_id must match result claim_id")
        return self


def validate_claim_quotes(*, claim: SummaryClaim, span_index: SpanIndex) -> QuoteValidationResult:
    errors: list[QuoteValidationError] = []
    matches: list[QuoteValidationMatch] = []

    if span_index.document.document_id != claim.document_id:
        errors.append(
            QuoteValidationError(
                code="document_mismatch",
                message="claim document_id must match SpanIndex document_id",
                claim_id=claim.claim_id,
                expected_document_id=claim.document_id,
                actual_document_id=span_index.document.document_id,
            )
        )
        return QuoteValidationResult(
            claim_id=claim.claim_id,
            document_id=claim.document_id,
            valid=False,
            errors=tuple(errors),
        )

    for evidence_index, evidence in enumerate(claim.evidence):
        missing_span_ids = tuple(
            span_id for span_id in evidence.source_span_ids if not span_index.has_span(span_id)
        )
        for missing_span_id in missing_span_ids:
            errors.append(
                QuoteValidationError(
                    code="invalid_span_id",
                    message="quote citation source_span_id does not exist in SpanIndex",
                    claim_id=claim.claim_id,
                    evidence_index=evidence_index,
                    quote=evidence.quote,
                    source_span_id=missing_span_id,
                )
            )

        evidence_match = _classify_evidence_quote(
            claim_id=claim.claim_id,
            evidence_index=evidence_index,
            quote=evidence.quote,
            page_number=evidence.page_number,
            cited_span_texts=tuple(
                span_index.get_span(span_id).text
                for span_id in evidence.source_span_ids
                if span_index.has_span(span_id)
            ),
            page_text=span_index.get_page_text(evidence.page_number),
        )
        if isinstance(evidence_match, QuoteValidationError):
            errors.append(evidence_match)
        else:
            matches.append(evidence_match)
            if evidence_match.scope != "cited_spans":
                errors.append(
                    QuoteValidationError(
                        code="quote_outside_cited_spans",
                        message="quote matched on the cited page but not inside cited spans",
                        claim_id=claim.claim_id,
                        evidence_index=evidence_index,
                        quote=evidence.quote,
                    )
                )
            elif evidence_match.match_type == "normalized":
                errors.append(
                    QuoteValidationError(
                        code="normalized_match_only",
                        message="quote only matched after normalization",
                        claim_id=claim.claim_id,
                        evidence_index=evidence_index,
                        quote=evidence.quote,
                    )
                )
            elif evidence_match.match_type == "fuzzy":
                errors.append(
                    QuoteValidationError(
                        code="fuzzy_match",
                        message="quote only matched fuzzily",
                        claim_id=claim.claim_id,
                        evidence_index=evidence_index,
                        quote=evidence.quote,
                    )
                )

    return QuoteValidationResult(
        claim_id=claim.claim_id,
        document_id=claim.document_id,
        valid=not errors,
        matches=tuple(matches),
        errors=tuple(errors),
    )


def _classify_evidence_quote(
    *,
    claim_id: ClaimId,
    evidence_index: int,
    quote: str,
    page_number: int,
    cited_span_texts: tuple[str, ...],
    page_text: str,
) -> QuoteValidationMatch | QuoteValidationError:
    if any(quote in cited_span_text for cited_span_text in cited_span_texts):
        return QuoteValidationMatch(
            claim_id=claim_id,
            evidence_index=evidence_index,
            quote=quote,
            page_number=page_number,
            match_type="exact",
            scope="cited_spans",
        )
    if quote in page_text:
        return QuoteValidationMatch(
            claim_id=claim_id,
            evidence_index=evidence_index,
            quote=quote,
            page_number=page_number,
            match_type="exact",
            scope="page",
        )

    normalized_quote = normalize_quote_text(quote)
    normalized_span_texts = tuple(normalize_quote_text(cited_span_text) for cited_span_text in cited_span_texts)
    normalized_page_text = normalize_quote_text(page_text)
    if normalized_quote and any(normalized_quote in span_text for span_text in normalized_span_texts):
        return QuoteValidationMatch(
            claim_id=claim_id,
            evidence_index=evidence_index,
            quote=quote,
            page_number=page_number,
            match_type="normalized",
            scope="cited_spans",
        )
    if normalized_quote and normalized_quote in normalized_page_text:
        return QuoteValidationMatch(
            claim_id=claim_id,
            evidence_index=evidence_index,
            quote=quote,
            page_number=page_number,
            match_type="normalized",
            scope="page",
        )

    if any(_has_fuzzy_match(normalized_quote, span_text) for span_text in normalized_span_texts):
        return QuoteValidationMatch(
            claim_id=claim_id,
            evidence_index=evidence_index,
            quote=quote,
            page_number=page_number,
            match_type="fuzzy",
            scope="cited_spans",
        )
    if _has_fuzzy_match(normalized_quote, normalized_page_text):
        return QuoteValidationMatch(
            claim_id=claim_id,
            evidence_index=evidence_index,
            quote=quote,
            page_number=page_number,
            match_type="fuzzy",
            scope="page",
        )

    return QuoteValidationError(
        code="quote_not_found",
        message="quote was not found in cited spans or cited page",
        claim_id=claim_id,
        evidence_index=evidence_index,
        quote=quote,
    )


def normalize_quote_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).replace("\u00ad", "")
    normalized = re.sub(r"(?<=\w)-\s+(?=\w)", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _has_fuzzy_match(quote: str, text: str) -> bool:
    if not quote or not text:
        return False
    if len(quote) < 8:
        return False
    if SequenceMatcher(None, quote, text).ratio() >= 0.85:
        return True
    if len(text) <= len(quote):
        return False

    window_size = len(quote)
    step = max(1, window_size // 4)
    for start in range(0, len(text) - window_size + 1, step):
        window = text[start : start + window_size]
        if SequenceMatcher(None, quote, window).ratio() >= 0.85:
            return True
    return False
