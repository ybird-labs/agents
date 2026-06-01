from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from exeboard_ai.document_intelligence.core.ids import (
    ChunkId,
    DocumentId,
    SpanId,
    parse_chunk_id,
    parse_span_id,
    validate_document_id,
)

ChunkType = Literal["text"]


class Chunk(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    chunk_id: ChunkId
    document_id: DocumentId
    text: str
    page_numbers: tuple[int, ...]
    source_span_ids: tuple[SpanId, ...]
    chunk_type: ChunkType = "text"

    @field_validator("chunk_id", "text")
    @classmethod
    def _must_not_be_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("must not be empty")
        return value

    @field_validator("document_id")
    @classmethod
    def _validate_document_id(cls, value: str) -> DocumentId:
        return validate_document_id(value)

    @model_validator(mode="after")
    def _validate_structure(self) -> "Chunk":
        try:
            chunk_document_id, _chunk_index = parse_chunk_id(self.chunk_id)
        except ValueError as exc:
            raise ValueError("chunk_id must be in format '<document_id>:c<digits>'") from exc
        if chunk_document_id != self.document_id:
            raise ValueError("chunk_id must belong to document_id")

        if not self.page_numbers:
            raise ValueError("page_numbers must not be empty")
        if len(set(self.page_numbers)) != len(self.page_numbers):
            raise ValueError("page_numbers must be unique")
        if any(page_number < 1 for page_number in self.page_numbers):
            raise ValueError("page_numbers must be positive")

        if not self.source_span_ids:
            raise ValueError("source_span_ids must not be empty")
        if len(set(self.source_span_ids)) != len(self.source_span_ids):
            raise ValueError("source_span_ids must be unique")
        if any(not span_id for span_id in self.source_span_ids):
            raise ValueError("source_span_ids must not contain empty values")
        source_page_numbers: set[int] = set()
        for span_id in self.source_span_ids:
            try:
                span_document_id, span_page_number, _span_index = parse_span_id(span_id)
            except ValueError as exc:
                raise ValueError("source_span_ids must contain valid span ids") from exc
            if span_document_id != self.document_id:
                raise ValueError("source_span_ids must belong to document_id")
            source_page_numbers.add(span_page_number)
        if source_page_numbers != set(self.page_numbers):
            raise ValueError("page_numbers must match source_span_ids")

        return self
