from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from exeboard_ai.document_intelligence.core.ids import (
    ChunkId,
    ClaimId,
    DocumentId,
    SpanId,
    parse_chunk_id as parse_core_chunk_id,
    parse_claim_id as parse_core_claim_id,
    parse_span_id as parse_core_span_id,
    validate_document_id,
)

DocumentType = Literal[
    "generic",
    "financial_report",
    "business_review",
    "contract",
    "meeting_notes",
]
ClaimRole = Literal[
    "finding",
    "forecast",
    "risk",
    "recommendation",
    "action_item",
    "decision",
    "open_question",
    "obligation",
    "entitlement",
    "prohibition",
]
Importance = Literal["low", "medium", "high"]
ValidationStatus = Literal["unvalidated", "valid", "invalid"]

DEFAULT_ALLOWED_CLAIM_ROLES_BY_DOCUMENT_TYPE: dict[DocumentType, frozenset[ClaimRole]] = {
    "generic": frozenset(
        ["finding", "risk", "recommendation", "action_item", "open_question"]
    ),
    "financial_report": frozenset(["finding", "forecast", "risk", "open_question"]),
    "business_review": frozenset(
        ["finding", "forecast", "risk", "recommendation", "action_item", "open_question"]
    ),
    "contract": frozenset(
        ["finding", "risk", "obligation", "entitlement", "prohibition", "open_question"]
    ),
    "meeting_notes": frozenset(
        ["finding", "decision", "action_item", "risk", "open_question"]
    ),
}

class ClaimEvidence(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    quote: str
    page_number: int
    source_span_ids: tuple[SpanId, ...]
    source_chunk_ids: tuple[ChunkId, ...]

    @field_validator("quote")
    @classmethod
    def _quote_must_not_be_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("quote must not be empty")
        return value

    @model_validator(mode="after")
    def _validate_evidence(self) -> ClaimEvidence:
        if self.page_number < 1:
            raise ValueError("page_number must be 1 or greater")

        _validate_non_empty_unique_tuple(
            "source_span_ids",
            self.source_span_ids,
        )
        _validate_non_empty_unique_tuple(
            "source_chunk_ids",
            self.source_chunk_ids,
        )

        span_document_ids: set[DocumentId] = set()
        for span_id in self.source_span_ids:
            span_document_id, span_page_number = _parse_span_id(span_id)
            span_document_ids.add(span_document_id)
            if span_page_number != self.page_number:
                raise ValueError("source_span_ids page must match page_number")

        chunk_document_ids = {_parse_chunk_id(chunk_id) for chunk_id in self.source_chunk_ids}
        document_ids = span_document_ids | chunk_document_ids
        if len(document_ids) != 1:
            raise ValueError("evidence source IDs must belong to the same document")

        return self


class SummaryClaim(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    claim_id: ClaimId
    document_id: DocumentId
    document_type: DocumentType
    claim: str
    claim_role: ClaimRole
    importance: Importance
    evidence: tuple[ClaimEvidence, ...]
    derived_from_claim_ids: tuple[ClaimId, ...] = ()
    validation_status: ValidationStatus = "unvalidated"
    validation_errors: tuple[str, ...] = ()

    @field_validator("document_id")
    @classmethod
    def _validate_document_id(cls, value: str) -> DocumentId:
        return validate_document_id(value)

    @field_validator("claim")
    @classmethod
    def _claim_must_not_be_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("claim must not be empty")
        return value

    @model_validator(mode="after")
    def _validate_claim(self) -> SummaryClaim:
        claim_document_id = _parse_claim_id(self.claim_id)
        if claim_document_id != self.document_id:
            raise ValueError("claim_id must belong to document_id")

        allowed_roles = DEFAULT_ALLOWED_CLAIM_ROLES_BY_DOCUMENT_TYPE[self.document_type]
        if self.claim_role not in allowed_roles:
            raise ValueError("claim_role is not allowed for document_type")

        if not self.evidence:
            raise ValueError("evidence must not be empty")

        for evidence in self.evidence:
            evidence_document_id = _document_id_from_evidence(evidence)
            if evidence_document_id != self.document_id:
                raise ValueError("evidence source IDs must belong to document_id")

        _validate_unique_tuple("derived_from_claim_ids", self.derived_from_claim_ids)
        for derived_claim_id in self.derived_from_claim_ids:
            if _parse_claim_id(derived_claim_id) != self.document_id:
                raise ValueError("derived_from_claim_ids must belong to document_id")
            if derived_claim_id == self.claim_id:
                raise ValueError("derived_from_claim_ids must not contain claim_id")

        _validate_validation_status(self.validation_status, self.validation_errors)

        return self


class ChunkSummary(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    chunk_id: ChunkId
    document_id: DocumentId
    document_type: DocumentType
    claims: tuple[SummaryClaim, ...] = ()

    @field_validator("document_id")
    @classmethod
    def _validate_document_id(cls, value: str) -> DocumentId:
        return validate_document_id(value)

    @model_validator(mode="after")
    def _validate_chunk_summary(self) -> ChunkSummary:
        if _parse_chunk_id(self.chunk_id) != self.document_id:
            raise ValueError("chunk_id must belong to document_id")

        _validate_unique_tuple("claim_ids", tuple(claim.claim_id for claim in self.claims))

        for claim in self.claims:
            if claim.document_id != self.document_id:
                raise ValueError("claim document_id must match ChunkSummary document_id")
            if claim.document_type != self.document_type:
                raise ValueError("claim document_type must match ChunkSummary document_type")
            if any(evidence.source_chunk_ids != (self.chunk_id,) for evidence in claim.evidence):
                raise ValueError("claim evidence must cite only chunk_id")

        return self


class SummarySentence(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    text: str
    supporting_claim_ids: tuple[ClaimId, ...]

    @field_validator("text")
    @classmethod
    def _text_must_not_be_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("text must not be empty")
        return value

    @model_validator(mode="after")
    def _validate_summary_sentence(self) -> SummarySentence:
        _validate_non_empty_unique_tuple("supporting_claim_ids", self.supporting_claim_ids)
        for claim_id in self.supporting_claim_ids:
            _parse_claim_id(claim_id)
        return self


class DocumentSummary(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    document_id: DocumentId
    document_type: DocumentType
    summary_sentences: tuple[SummarySentence, ...]
    claims: tuple[SummaryClaim, ...]

    @field_validator("document_id")
    @classmethod
    def _validate_document_id(cls, value: str) -> DocumentId:
        return validate_document_id(value)

    @model_validator(mode="after")
    def _validate_document_summary(self) -> DocumentSummary:
        if not self.summary_sentences:
            raise ValueError("summary_sentences must not be empty")
        if not self.claims:
            raise ValueError("claims must not be empty")

        claim_ids = tuple(claim.claim_id for claim in self.claims)
        _validate_unique_tuple("claim_ids", claim_ids)
        claim_id_set = set(claim_ids)

        for claim in self.claims:
            if claim.document_id != self.document_id:
                raise ValueError("claim document_id must match DocumentSummary document_id")
            if claim.document_type != self.document_type:
                raise ValueError("claim document_type must match DocumentSummary document_type")
            if claim.validation_status != "valid":
                raise ValueError("claims must be valid before final summary")

        for sentence in self.summary_sentences:
            for claim_id in sentence.supporting_claim_ids:
                if _parse_claim_id(claim_id) != self.document_id:
                    raise ValueError("supporting_claim_ids must belong to document_id")
                if claim_id not in claim_id_set:
                    raise ValueError("supporting_claim_ids must reference existing claims")

        return self


def _parse_claim_id(claim_id: ClaimId) -> DocumentId:
    try:
        document_id, _claim_index = parse_core_claim_id(claim_id)
    except ValueError as exc:
        raise ValueError("claim_id must use '<document_id>:claim0000' format") from exc
    return document_id


def _parse_chunk_id(chunk_id: ChunkId) -> DocumentId:
    try:
        document_id, _chunk_index = parse_core_chunk_id(chunk_id)
    except ValueError as exc:
        raise ValueError("chunk_id must use '<document_id>:c0000' format") from exc
    return document_id


def _parse_span_id(span_id: SpanId) -> tuple[DocumentId, int]:
    try:
        document_id, page_number, _span_index = parse_core_span_id(span_id)
    except ValueError as exc:
        raise ValueError("span_id must use '<document_id>:p0001:s0000' format") from exc
    return document_id, page_number


def _document_id_from_evidence(evidence: ClaimEvidence) -> DocumentId:
    document_id, _ = _parse_span_id(evidence.source_span_ids[0])
    return document_id


def _validate_non_empty_unique_tuple(name: str, values: tuple[str, ...]) -> None:
    if not values:
        raise ValueError(f"{name} must not be empty")
    _validate_unique_tuple(name, values)
    if any(not value for value in values):
        raise ValueError(f"{name} must not contain empty values")


def _validate_unique_tuple(name: str, values: tuple[str, ...]) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique")


def _validate_validation_status(
    validation_status: ValidationStatus,
    validation_errors: tuple[str, ...],
) -> None:
    if any(not error for error in validation_errors):
        raise ValueError("validation_errors must not contain empty values")

    if validation_status in {"unvalidated", "valid"} and validation_errors:
        raise ValueError("validation_errors must be empty unless validation_status is invalid")

    if validation_status == "invalid" and not validation_errors:
        raise ValueError("invalid validation_status requires validation_errors")
