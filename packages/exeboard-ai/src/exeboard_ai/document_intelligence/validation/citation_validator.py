from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from exeboard_ai.document_intelligence.core.ids import (
    ClaimId,
    DocumentId,
    SpanId,
    parse_claim_id,
    validate_document_id,
)
from exeboard_ai.document_intelligence.ir.span_index import SpanIndex
from exeboard_ai.document_intelligence.summarization.models import SummaryClaim

CitationValidationErrorCode = Literal[
    "invalid_span_id",
    "page_mismatch",
    "document_mismatch",
]


class CitationValidationError(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    code: CitationValidationErrorCode
    message: str
    claim_id: ClaimId
    evidence_index: int | None = Field(default=None, ge=0)
    source_span_id: SpanId | None = None
    expected_document_id: DocumentId | None = None
    actual_document_id: DocumentId | None = None
    expected_page_number: int | None = Field(default=None, ge=1)
    actual_page_number: int | None = Field(default=None, ge=1)

    @field_validator("message")
    @classmethod
    def _message_must_not_be_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("must not be empty")
        return value

    @field_validator("claim_id")
    @classmethod
    def _validate_claim_id(cls, value: str) -> ClaimId:
        parse_claim_id(value)
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


class CitationValidationResult(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    claim_id: ClaimId
    document_id: DocumentId
    valid: bool
    errors: tuple[CitationValidationError, ...] = ()

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
    def _valid_must_match_errors(self) -> CitationValidationResult:
        if self.valid != (not self.errors):
            raise ValueError("valid must be True iff errors is empty")
        return self


def validate_claim_citations(
    *,
    claim: SummaryClaim,
    span_index: SpanIndex,
) -> CitationValidationResult:
    errors: list[CitationValidationError] = []

    if span_index.document.document_id != claim.document_id:
        errors.append(
            CitationValidationError(
                code="document_mismatch",
                message="claim document_id must match SpanIndex document_id",
                claim_id=claim.claim_id,
                expected_document_id=claim.document_id,
                actual_document_id=span_index.document.document_id,
            )
        )
        return CitationValidationResult(
            claim_id=claim.claim_id,
            document_id=claim.document_id,
            valid=False,
            errors=tuple(errors),
        )

    for evidence_index, evidence in enumerate(claim.evidence):
        for source_span_id in evidence.source_span_ids:
            if not span_index.has_span(source_span_id):
                errors.append(
                    CitationValidationError(
                        code="invalid_span_id",
                        message="citation source_span_id does not exist in SpanIndex",
                        claim_id=claim.claim_id,
                        evidence_index=evidence_index,
                        source_span_id=source_span_id,
                    )
                )
                continue

            span = span_index.get_span(source_span_id)
            if span.page_number != evidence.page_number:
                errors.append(
                    CitationValidationError(
                        code="page_mismatch",
                        message="citation page_number must match cited span page_number",
                        claim_id=claim.claim_id,
                        evidence_index=evidence_index,
                        source_span_id=source_span_id,
                        expected_page_number=evidence.page_number,
                        actual_page_number=span.page_number,
                    )
                )

    return CitationValidationResult(
        claim_id=claim.claim_id,
        document_id=claim.document_id,
        valid=not errors,
        errors=tuple(errors),
    )
