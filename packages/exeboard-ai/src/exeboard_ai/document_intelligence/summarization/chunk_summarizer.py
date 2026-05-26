from hashlib import sha256
import json
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from exeboard_ai.document_intelligence.chunking.models import Chunk
from exeboard_ai.document_intelligence.core.ids import SpanId, make_claim_id
from exeboard_ai.document_intelligence.summarization.models import (
    ClaimEvidence,
    ClaimRole,
    ChunkSummary,
    DocumentType,
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

CHUNK_SUMMARY_OPERATION_NAME = "document_intelligence.chunk_summary"


class _GeneratedClaimEvidence(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    quote: str
    page_number: int = Field(ge=1)
    source_span_ids: tuple[SpanId, ...]

    @field_validator("quote")
    @classmethod
    def _quote_must_not_be_empty(cls, value: str) -> str:
        if not value:
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


def summarize_chunk(
    *,
    chunk: Chunk,
    document_type: DocumentType,
    generator: StructuredResponseGenerator,
    first_claim_index: int = 0,
) -> ChunkSummary:
    if first_claim_index < 0:
        raise ValueError("first_claim_index must be 0 or greater")

    prompt = build_chunk_summary_prompt(chunk=chunk, document_type=document_type)
    prompt_fingerprint = _sha256_text(prompt)
    output_schema_fingerprint = _schema_fingerprint(_GeneratedChunkSummary)
    request = StructuredGenerationRequest(
        operation_name=CHUNK_SUMMARY_OPERATION_NAME,
        prompt_name=CHUNK_SUMMARY_PROMPT_NAME,
        prompt_version=CHUNK_SUMMARY_PROMPT_VERSION,
        prompt=prompt,
        replay_key=_make_chunk_summary_replay_key(
            chunk=chunk,
            document_type=document_type,
            prompt=prompt,
            output_schema_fingerprint=output_schema_fingerprint,
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

    claims = tuple(
        _assemble_claim(
            chunk=chunk,
            document_type=document_type,
            generated_claim=generated_claim,
            claim_index=first_claim_index + index,
        )
        for index, generated_claim in enumerate(generated_summary.claims)
    )

    return ChunkSummary(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        document_type=document_type,
        claims=claims,
    )


def _make_chunk_summary_replay_key(
    *,
    chunk: Chunk,
    document_type: DocumentType,
    prompt: str,
    output_schema_fingerprint: str,
) -> str:
    replay_payload = {
        "operation_name": CHUNK_SUMMARY_OPERATION_NAME,
        "prompt_name": CHUNK_SUMMARY_PROMPT_NAME,
        "prompt_version": CHUNK_SUMMARY_PROMPT_VERSION,
        "document_id": chunk.document_id,
        "chunk_id": chunk.chunk_id,
        "document_type": document_type,
        "page_numbers": chunk.page_numbers,
        "source_span_ids": chunk.source_span_ids,
        "chunk_text": chunk.text,
        "prompt_sha256": _sha256_text(prompt),
        "output_schema_sha256": output_schema_fingerprint,
    }
    digest = _sha256_json(replay_payload)
    return f"{CHUNK_SUMMARY_OPERATION_NAME}:{CHUNK_SUMMARY_PROMPT_NAME}:{CHUNK_SUMMARY_PROMPT_VERSION}:{digest}"


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
    generated_claim: _GeneratedSummaryClaim,
    claim_index: int,
) -> SummaryClaim:
    evidence = tuple(
        _assemble_evidence(chunk=chunk, generated_evidence=generated_evidence)
        for generated_evidence in generated_claim.evidence
    )

    return SummaryClaim(
        claim_id=make_claim_id(chunk.document_id, claim_index),
        document_id=chunk.document_id,
        document_type=document_type,
        claim=generated_claim.claim,
        claim_role=generated_claim.claim_role,
        importance=generated_claim.importance,
        evidence=evidence,
        validation_status="unvalidated",
        validation_errors=(),
    )


def _assemble_evidence(
    *,
    chunk: Chunk,
    generated_evidence: _GeneratedClaimEvidence,
) -> ClaimEvidence:
    if generated_evidence.page_number not in chunk.page_numbers:
        raise ValueError("evidence page_number must belong to chunk page_numbers")
    if generated_evidence.quote not in chunk.text:
        raise ValueError("evidence quote must appear in chunk text")

    unknown_span_ids = tuple(
        span_id
        for span_id in generated_evidence.source_span_ids
        if span_id not in chunk.source_span_ids
    )
    if unknown_span_ids:
        raise ValueError("evidence source_span_ids must belong to chunk source_span_ids")

    return ClaimEvidence(
        quote=generated_evidence.quote,
        page_number=generated_evidence.page_number,
        source_span_ids=generated_evidence.source_span_ids,
        source_chunk_ids=(chunk.chunk_id,),
    )
