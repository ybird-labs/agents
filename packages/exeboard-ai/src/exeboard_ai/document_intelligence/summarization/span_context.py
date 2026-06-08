from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from exeboard_ai.document_intelligence.chunking.models import Chunk
from exeboard_ai.document_intelligence.core.ids import ChunkId, DocumentId, SpanId, validate_document_id
from exeboard_ai.document_intelligence.ir.span_index import SpanIndex


class AllowedEvidenceSpan(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    span_id: SpanId
    page_number: int = Field(ge=1)
    text: str

    @field_validator("span_id", "text")
    @classmethod
    def _must_not_be_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must not be empty")
        return value


class SpanAddressedChunkContext(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    document_id: DocumentId
    chunk_id: ChunkId
    chunk_text: str
    allowed_spans: tuple[AllowedEvidenceSpan, ...]

    @field_validator("document_id")
    @classmethod
    def _validate_document_id(cls, value: str) -> DocumentId:
        return validate_document_id(value)

    @field_validator("chunk_id", "chunk_text")
    @classmethod
    def _must_not_be_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must not be empty")
        return value

    @model_validator(mode="after")
    def _validate_allowed_spans(self) -> "SpanAddressedChunkContext":
        if not self.allowed_spans:
            raise ValueError("allowed_spans must not be empty")
        span_ids = tuple(span.span_id for span in self.allowed_spans)
        if len(set(span_ids)) != len(span_ids):
            raise ValueError("allowed_spans span_id values must be unique")
        return self

    @property
    def allowed_span_ids(self) -> frozenset[SpanId]:
        return frozenset(span.span_id for span in self.allowed_spans)

    def get_allowed_span(self, span_id: SpanId) -> AllowedEvidenceSpan:
        for span in self.allowed_spans:
            if span.span_id == span_id:
                return span
        raise KeyError(f"span_id is not allowed for chunk context: {span_id}")

    def canonical_allowed_spans(self) -> tuple[dict[str, object], ...]:
        return tuple(
            {
                "span_id": span.span_id,
                "page_number": span.page_number,
                "text": span.text,
            }
            for span in sorted(
                self.allowed_spans,
                key=lambda allowed_span: (allowed_span.page_number, allowed_span.span_id),
            )
        )


def build_span_addressed_chunk_context(
    *,
    chunk: Chunk,
    span_index: SpanIndex,
) -> SpanAddressedChunkContext:
    if span_index.document.document_id != chunk.document_id:
        raise ValueError("chunk document_id must match SpanIndex document_id")

    allowed_spans: list[AllowedEvidenceSpan] = []
    for source_span_id in chunk.source_span_ids:
        if not span_index.has_span(source_span_id):
            raise ValueError("chunk source_span_ids must exist in SpanIndex")
        span = span_index.get_span(source_span_id)
        if span.page_number not in chunk.page_numbers:
            raise ValueError("chunk source_span_ids page_number must belong to chunk page_numbers")
        allowed_spans.append(
            AllowedEvidenceSpan(
                span_id=span.span_id,
                page_number=span.page_number,
                text=span.text,
            )
        )

    canonical_spans = tuple(
        sorted(
            allowed_spans,
            key=lambda allowed_span: (allowed_span.page_number, allowed_span.span_id),
        )
    )
    return SpanAddressedChunkContext(
        document_id=chunk.document_id,
        chunk_id=chunk.chunk_id,
        chunk_text=chunk.text,
        allowed_spans=canonical_spans,
    )
