from hashlib import sha256
import json
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from exeboard_ai.document_intelligence.chunking.models import Chunk
from exeboard_ai.document_intelligence.core.ids import SpanId, make_claim_id
from exeboard_ai.document_intelligence.ir.span_index import SpanIndex
from exeboard_ai.document_intelligence.summarization.models import (
    ClaimEvidence,
    ClaimRole,
    ChunkSummary,
    DocumentType,
    DroppedClaimRecord,
    EvidenceFailureDetail,
    GroundingRunReport,
    Importance,
    SummaryClaim,
)
from exeboard_ai.document_intelligence.summarization.ports import (
    StructuredGenerationRequest,
    StructuredResponseGenerator,
)
from exeboard_ai.document_intelligence.summarization.prompts import (
    CHUNK_SUMMARY_PROMPT_NAME,
    CHUNK_SUMMARY_PROMPT_VERSION,
    build_chunk_summary_prompt,
)
from exeboard_ai.document_intelligence.summarization.span_context import (
    AllowedEvidenceSpan,
    SpanAddressedChunkContext,
    build_span_addressed_chunk_context,
)

CHUNK_SUMMARY_OPERATION_NAME = "document_intelligence.chunk_summary"
CHUNK_SUMMARY_OUTPUT_SCHEMA_NAME = "chunk_summary_proposal"
CHUNK_SUMMARY_OUTPUT_SCHEMA_VERSION = "0.2"


class _GeneratedClaimEvidence(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    quote: str
    source_span_ids: tuple[SpanId, ...]

    @field_validator("quote")
    @classmethod
    def _quote_must_not_be_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("quote must not be empty")
        return value

    @model_validator(mode="after")
    def _validate_evidence(self) -> "_GeneratedClaimEvidence":
        if not self.source_span_ids:
            raise ValueError("source_span_ids must not be empty")
        if len(set(self.source_span_ids)) != len(self.source_span_ids):
            raise ValueError("source_span_ids must be unique")
        if any(not span_id for span_id in self.source_span_ids):
            raise ValueError("source_span_ids must not contain empty values")
        return self


class _GeneratedSummaryClaim(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    claim: str
    claim_role: ClaimRole
    importance: Importance
    evidence: tuple[_GeneratedClaimEvidence, ...]

    @field_validator("claim")
    @classmethod
    def _claim_must_not_be_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("claim must not be empty")
        return value

    @model_validator(mode="after")
    def _validate_claim(self) -> "_GeneratedSummaryClaim":
        if not self.evidence:
            raise ValueError("evidence must not be empty")
        return self


class _GeneratedChunkSummary(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    claims: tuple[_GeneratedSummaryClaim, ...]


class ChunkSummarizationRunResult(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    summary: ChunkSummary
    report: GroundingRunReport


def summarize_chunk(
    *,
    chunk: Chunk,
    document_type: DocumentType,
    generator: StructuredResponseGenerator,
    span_index: SpanIndex,
    first_claim_index: int = 0,
) -> ChunkSummary:
    return summarize_chunk_run(
        chunk=chunk,
        document_type=document_type,
        generator=generator,
        span_index=span_index,
        first_claim_index=first_claim_index,
    ).summary


def summarize_chunk_run(
    *,
    chunk: Chunk,
    document_type: DocumentType,
    generator: StructuredResponseGenerator,
    span_index: SpanIndex,
    first_claim_index: int = 0,
) -> ChunkSummarizationRunResult:
    if first_claim_index < 0:
        raise ValueError("first_claim_index must be 0 or greater")

    chunk_context = build_span_addressed_chunk_context(chunk=chunk, span_index=span_index)
    prompt = build_chunk_summary_prompt(chunk_context=chunk_context, document_type=document_type)
    prompt_fingerprint = _sha256_text(prompt)
    output_schema_fingerprint = _schema_fingerprint(_GeneratedChunkSummary)
    request = StructuredGenerationRequest(
        operation_name=CHUNK_SUMMARY_OPERATION_NAME,
        prompt_name=CHUNK_SUMMARY_PROMPT_NAME,
        prompt_version=CHUNK_SUMMARY_PROMPT_VERSION,
        output_schema_name=CHUNK_SUMMARY_OUTPUT_SCHEMA_NAME,
        output_schema_version=CHUNK_SUMMARY_OUTPUT_SCHEMA_VERSION,
        prompt=prompt,
        context=chunk_context,
        replay_key=_make_chunk_summary_replay_key(
            chunk=chunk,
            document_type=document_type,
            prompt=prompt,
            output_schema_fingerprint=output_schema_fingerprint,
            chunk_context=chunk_context,
        ),
        metadata={
            "document_id": chunk.document_id,
            "chunk_id": chunk.chunk_id,
            "document_type": document_type,
            "prompt_sha256": prompt_fingerprint,
            "output_schema_sha256": output_schema_fingerprint,
        },
    )
    generated_summary = generator.generate(request=request, output_model=_GeneratedChunkSummary)

    assembled_claims: list[SummaryClaim] = []
    drops: list[DroppedClaimRecord] = []
    for proposal_index, generated_claim in enumerate(generated_summary.claims):
        assembled_claim, evidence_failures = _assemble_claim(
            chunk=chunk,
            document_type=document_type,
            chunk_context=chunk_context,
            generated_claim=generated_claim,
            claim_index=first_claim_index + len(assembled_claims),
        )
        if assembled_claim is not None:
            assembled_claims.append(assembled_claim)
            continue
        error_codes = tuple(dict.fromkeys(failure.error_code for failure in evidence_failures))
        drops.append(
            DroppedClaimRecord(
                stage="assembly_anchor",
                error_codes=error_codes or ("assembly_failed",),
                chunk_id=chunk.chunk_id,
                proposal_index=proposal_index,
                generated_claim=generated_claim.claim,
                evidence_failures=evidence_failures,
            )
        )
    claims = tuple(assembled_claims)
    summary = ChunkSummary(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        document_type=document_type,
        claims=claims,
    )
    report = GroundingRunReport(
        claims_proposed=len(generated_summary.claims),
        evidence_proposed=sum(len(generated_claim.evidence) for generated_claim in generated_summary.claims),
        claims_assembled=len(claims),
        claims_valid=len(claims),
        drops=tuple(drops),
    )

    return ChunkSummarizationRunResult(summary=summary, report=report)


def _make_chunk_summary_replay_key(
    *,
    chunk: Chunk,
    document_type: DocumentType,
    prompt: str,
    output_schema_fingerprint: str,
    chunk_context: SpanAddressedChunkContext,
) -> str:
    replay_payload = {
        "operation_name": CHUNK_SUMMARY_OPERATION_NAME,
        "prompt_name": CHUNK_SUMMARY_PROMPT_NAME,
        "prompt_version": CHUNK_SUMMARY_PROMPT_VERSION,
        "document_id": chunk.document_id,
        "chunk_id": chunk.chunk_id,
        "document_type": document_type,
        "output_schema_name": CHUNK_SUMMARY_OUTPUT_SCHEMA_NAME,
        "output_schema_version": CHUNK_SUMMARY_OUTPUT_SCHEMA_VERSION,
        "chunk_text": chunk.text,
        "allowed_spans": chunk_context.canonical_allowed_spans(),
        "prompt_sha256": _sha256_text(prompt),
        "output_schema_sha256": output_schema_fingerprint,
    }
    digest = _sha256_json(replay_payload)
    return ":".join(
        [
            CHUNK_SUMMARY_OPERATION_NAME,
            CHUNK_SUMMARY_PROMPT_NAME,
            CHUNK_SUMMARY_PROMPT_VERSION,
            CHUNK_SUMMARY_OUTPUT_SCHEMA_NAME,
            CHUNK_SUMMARY_OUTPUT_SCHEMA_VERSION,
            digest,
        ]
    )


def _sha256_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _schema_fingerprint(model: type[BaseModel]) -> str:
    return _sha256_json(model.model_json_schema())


def _sha256_json(value: object) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()


def _assemble_claim(
    *,
    chunk: Chunk,
    document_type: DocumentType,
    chunk_context: SpanAddressedChunkContext,
    generated_claim: _GeneratedSummaryClaim,
    claim_index: int,
) -> tuple[SummaryClaim | None, tuple[EvidenceFailureDetail, ...]]:
    evidence: list[ClaimEvidence] = []
    failures: list[EvidenceFailureDetail] = []
    for evidence_index, generated_evidence in enumerate(generated_claim.evidence):
        assembled_evidence, failure = _assemble_evidence(
            chunk=chunk,
            chunk_context=chunk_context,
            generated_evidence=generated_evidence,
            evidence_index=evidence_index,
        )
        if failure is not None:
            failures.append(failure)
            continue
        if assembled_evidence is not None:
            evidence.append(assembled_evidence)

    if failures:
        return None, tuple(failures)

    return SummaryClaim(
        claim_id=make_claim_id(chunk.document_id, claim_index),
        document_id=chunk.document_id,
        document_type=document_type,
        claim=generated_claim.claim,
        claim_role=generated_claim.claim_role,
        importance=generated_claim.importance,
        evidence=tuple(evidence),
        validation_status="unvalidated",
        validation_errors=(),
    ), ()


def _assemble_evidence(
    *,
    chunk: Chunk,
    chunk_context: SpanAddressedChunkContext,
    generated_evidence: _GeneratedClaimEvidence,
    evidence_index: int,
) -> tuple[ClaimEvidence | None, EvidenceFailureDetail | None]:
    unknown_span_ids = tuple(
        span_id
        for span_id in generated_evidence.source_span_ids
        if span_id not in chunk_context.allowed_span_ids
    )
    if unknown_span_ids:
        return None, EvidenceFailureDetail(
            evidence_index=evidence_index,
            error_code="source_span_not_in_chunk_context",
            quote=generated_evidence.quote,
            source_span_ids=generated_evidence.source_span_ids,
        )

    cited_spans = _get_cited_allowed_spans(
        chunk_context=chunk_context,
        source_span_ids=generated_evidence.source_span_ids,
    )
    page_numbers = {span.page_number for span in cited_spans}
    if len(page_numbers) != 1:
        return None, EvidenceFailureDetail(
            evidence_index=evidence_index,
            error_code="evidence_spans_cross_pages",
            quote=generated_evidence.quote,
            source_span_ids=generated_evidence.source_span_ids,
        )
    page_number = page_numbers.pop()

    if not any(generated_evidence.quote in span.text for span in cited_spans):
        return None, EvidenceFailureDetail(
            evidence_index=evidence_index,
            error_code="quote_not_found",
            quote=generated_evidence.quote,
            source_span_ids=generated_evidence.source_span_ids,
        )

    return ClaimEvidence(
        quote=generated_evidence.quote,
        page_number=page_number,
        source_span_ids=generated_evidence.source_span_ids,
        source_chunk_ids=(chunk.chunk_id,),
    ), None


def _get_cited_allowed_spans(
    *,
    chunk_context: SpanAddressedChunkContext,
    source_span_ids: tuple[SpanId, ...],
) -> tuple[AllowedEvidenceSpan, ...]:
    return tuple(chunk_context.get_allowed_span(span_id) for span_id in source_span_ids)
