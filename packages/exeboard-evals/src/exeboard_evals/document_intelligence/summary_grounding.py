from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar, TypeVar

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from exeboard_ai.document_intelligence.core.ids import DocumentId, SpanId, validate_document_id
from exeboard_ai.document_intelligence.parsing.ports import DocumentParser
from exeboard_ai.document_intelligence.summarization.models import (
    ClaimRole,
    DocumentType,
    Importance,
    SummaryClaim,
)
from exeboard_ai.document_intelligence.summarization.pipeline import summarize_document
from exeboard_ai.document_intelligence.summarization.ports import (
    StructuredGenerationRequest,
    StructuredResponseGenerator,
)
from exeboard_ai.document_intelligence.summarization.span_context import SpanAddressedChunkContext

T = TypeVar("T", bound=BaseModel)


class GeneratedClaimSpec(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    trigger_span_id: SpanId
    claim: str
    claim_role: ClaimRole
    importance: Importance
    quote: str
    source_span_ids: tuple[SpanId, ...]

    @field_validator("trigger_span_id", "claim", "quote")
    @classmethod
    def _must_not_be_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must not be empty")
        return value

    @model_validator(mode="after")
    def _validate_spec(self) -> GeneratedClaimSpec:
        if not self.source_span_ids:
            raise ValueError("source_span_ids must not be empty")
        if len(set(self.source_span_ids)) != len(self.source_span_ids):
            raise ValueError("source_span_ids must be unique")
        if any(not span_id or not span_id.strip() for span_id in self.source_span_ids):
            raise ValueError("source_span_ids must not contain empty values")
        return self


class ExpectedClaimSpec(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    claim: str
    quote: str
    page_number: int
    source_span_ids: tuple[SpanId, ...]

    @field_validator("claim", "quote")
    @classmethod
    def _must_not_be_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must not be empty")
        return value

    @model_validator(mode="after")
    def _validate_spec(self) -> ExpectedClaimSpec:
        if self.page_number < 1:
            raise ValueError("page_number must be 1 or greater")
        if not self.source_span_ids:
            raise ValueError("source_span_ids must not be empty")
        if len(set(self.source_span_ids)) != len(self.source_span_ids):
            raise ValueError("source_span_ids must be unique")
        return self


class SummaryGroundingCase(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    fixture_path: str
    document_id: DocumentId
    document_type: DocumentType
    target_chars: int = 2000
    max_chars: int = 2500
    generated_claims: tuple[GeneratedClaimSpec, ...]
    expected_claims: tuple[ExpectedClaimSpec, ...]
    forbidden_claims: tuple[str, ...] = ()

    @field_validator("case_id", "fixture_path")
    @classmethod
    def _must_not_be_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must not be empty")
        return value

    @field_validator("document_id")
    @classmethod
    def _validate_document_id(cls, value: str) -> DocumentId:
        return validate_document_id(value)

    @field_validator("forbidden_claims")
    @classmethod
    def _forbidden_claims_must_not_contain_empty_values(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        if any(not claim or not claim.strip() for claim in value):
            raise ValueError("forbidden_claims must not contain empty values")
        return value

    @model_validator(mode="after")
    def _validate_case(self) -> SummaryGroundingCase:
        if self.target_chars < 1:
            raise ValueError("target_chars must be 1 or greater")
        if self.max_chars < self.target_chars:
            raise ValueError("max_chars must be greater than or equal to target_chars")
        if not self.generated_claims:
            raise ValueError("generated_claims must not be empty")
        if not self.expected_claims:
            raise ValueError("expected_claims must not be empty")
        return self


class SummaryGroundingResult(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    passed: bool
    failures: tuple[str, ...]
    observed_claims: tuple[str, ...]
    observed_summary_sentences: tuple[str, ...]

    @model_validator(mode="after")
    def _validate_result(self) -> SummaryGroundingResult:
        if self.passed and self.failures:
            raise ValueError("passing result must not contain failures")
        if not self.passed and not self.failures:
            raise ValueError("failing result requires failures")
        return self


class ReplaySummaryGroundingGenerator(StructuredResponseGenerator):
    def __init__(self, generated_claims: tuple[GeneratedClaimSpec, ...]) -> None:
        self._generated_claims = generated_claims
        self.requests: list[StructuredGenerationRequest] = []

    def generate(
        self,
        *,
        request: StructuredGenerationRequest,
        output_model: type[T],
    ) -> T:
        self.requests.append(request)
        if not isinstance(request.context, SpanAddressedChunkContext):
            raise ValueError("summary grounding replay requires span-addressed context")

        allowed_span_ids = request.context.allowed_span_ids
        claims = [
            {
                "claim": claim.claim,
                "claim_role": claim.claim_role,
                "importance": claim.importance,
                "evidence": [
                    {
                        "quote": claim.quote,
                        "source_span_ids": claim.source_span_ids,
                    }
                ],
            }
            for claim in self._generated_claims
            if claim.trigger_span_id in allowed_span_ids
        ]
        return output_model.model_validate({"claims": claims})


def load_summary_grounding_cases(path: Path) -> tuple[SummaryGroundingCase, ...]:
    cases: list[SummaryGroundingCase] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at line {line_number}") from exc
        cases.append(SummaryGroundingCase.model_validate(payload))
    return tuple(cases)


def write_summary_grounding_report(
    results: tuple[SummaryGroundingResult, ...],
    path: Path,
) -> None:
    payload = {
        "total": len(results),
        "passed": sum(1 for result in results if result.passed),
        "failed": sum(1 for result in results if not result.passed),
        "results": [result.model_dump(mode="json") for result in results],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run_summary_grounding_case(
    case: SummaryGroundingCase,
    *,
    parser: DocumentParser,
    response_generator: StructuredResponseGenerator,
) -> SummaryGroundingResult:
    failures: list[str] = []
    try:
        summary = summarize_document(
            Path(case.fixture_path),
            parser=parser,
            response_generator=response_generator,
            document_type=case.document_type,
            target_chars=case.target_chars,
            max_chars=case.max_chars,
        )
    except Exception as exc:
        return SummaryGroundingResult(
            case_id=case.case_id,
            passed=False,
            failures=(f"pipeline failed: {exc}",),
            observed_claims=(),
            observed_summary_sentences=(),
        )

    if summary.document_id != case.document_id:
        failures.append(
            f"document_id mismatch: expected {case.document_id}, observed {summary.document_id}"
        )

    for expected_claim in case.expected_claims:
        if not _has_expected_claim(summary.claims, expected_claim):
            failures.append(f"expected claim missing: {expected_claim.claim}")

    observed_claims = tuple(claim.claim for claim in summary.claims)
    for forbidden_claim in case.forbidden_claims:
        if forbidden_claim in observed_claims:
            failures.append(f"forbidden claim survived: {forbidden_claim}")

    observed_summary_sentences = tuple(sentence.text for sentence in summary.summary_sentences)
    return SummaryGroundingResult(
        case_id=case.case_id,
        passed=not failures,
        failures=tuple(failures),
        observed_claims=observed_claims,
        observed_summary_sentences=observed_summary_sentences,
    )


def _has_expected_claim(
    claims: tuple[SummaryClaim, ...],
    expected_claim: ExpectedClaimSpec,
) -> bool:
    for claim in claims:
        if claim.claim != expected_claim.claim:
            continue
        if any(
            evidence.quote == expected_claim.quote
            and evidence.page_number == expected_claim.page_number
            and evidence.source_span_ids == expected_claim.source_span_ids
            for evidence in claim.evidence
        ):
            return True
    return False
