from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from exeboard_ai.document_intelligence.core.ids import ClaimId, DocumentId, parse_claim_id, validate_document_id
from exeboard_ai.document_intelligence.ir.span_index import SpanIndex
from exeboard_ai.document_intelligence.summarization.models import SummaryClaim
from exeboard_ai.document_intelligence.validation.citation_validator import (
    CitationValidationResult,
    validate_claim_citations,
)
from exeboard_ai.document_intelligence.validation.quote_validator import (
    QuoteValidationResult,
    validate_claim_quotes,
)


class ClaimGroundingValidationResult(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    claim_id: ClaimId
    document_id: DocumentId
    valid: bool
    citation_result: CitationValidationResult
    quote_result: QuoteValidationResult
    errors: tuple[str, ...] = ()

    @field_validator("claim_id")
    @classmethod
    def _validate_claim_id(cls, value: str) -> ClaimId:
        parse_claim_id(value)
        return value

    @field_validator("document_id")
    @classmethod
    def _validate_document_id(cls, value: str) -> DocumentId:
        return validate_document_id(value)

    @field_validator("errors")
    @classmethod
    def _errors_must_not_contain_empty_values(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not error for error in value):
            raise ValueError("errors must not contain empty values")
        return value

    @model_validator(mode="after")
    def _validate_result(self) -> ClaimGroundingValidationResult:
        if self.citation_result.claim_id != self.claim_id:
            raise ValueError("citation_result claim_id must match claim_id")
        if self.quote_result.claim_id != self.claim_id:
            raise ValueError("quote_result claim_id must match claim_id")
        if self.citation_result.document_id != self.document_id:
            raise ValueError("citation_result document_id must match document_id")
        if self.quote_result.document_id != self.document_id:
            raise ValueError("quote_result document_id must match document_id")
        expected_valid = self.citation_result.valid and self.quote_result.valid
        if self.valid != expected_valid:
            raise ValueError("valid must reflect citation and quote validation")
        if self.valid and self.errors:
            raise ValueError("valid aggregate validation must not have errors")
        if not self.valid and not self.errors:
            raise ValueError("invalid aggregate validation requires errors")
        return self


def validate_claim_grounding(*, claim: SummaryClaim, span_index: SpanIndex) -> ClaimGroundingValidationResult:
    citation_result = validate_claim_citations(claim=claim, span_index=span_index)
    quote_result = validate_claim_quotes(claim=claim, span_index=span_index)
    errors = tuple(
        error.code
        for error in (*citation_result.errors, *quote_result.errors)
    )

    return ClaimGroundingValidationResult(
        claim_id=claim.claim_id,
        document_id=claim.document_id,
        valid=citation_result.valid and quote_result.valid,
        citation_result=citation_result,
        quote_result=quote_result,
        errors=errors,
    )


def apply_claim_grounding_validation(*, claim: SummaryClaim, span_index: SpanIndex) -> SummaryClaim:
    result = validate_claim_grounding(claim=claim, span_index=span_index)
    if result.valid:
        return claim.model_copy(update={"validation_status": "valid", "validation_errors": ()})
    return claim.model_copy(update={"validation_status": "invalid", "validation_errors": result.errors})
