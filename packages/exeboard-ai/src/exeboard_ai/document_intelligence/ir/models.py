from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from exeboard_ai.document_intelligence.core.ids import (
    DocumentId,
    PageId,
    SpanId,
    validate_document_id,
)

IR_VERSION = "0.1"

CoordinateSystem = Literal["pdf_points_top_left"]


class DocumentSource(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    file_name: str
    file_extension: str
    mime_type: str | None = None
    source_uri: str | None = None
    content_sha256: str | None = None

    @field_validator("file_name", "file_extension")
    @classmethod
    def _must_not_be_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("must not be empty")
        return value

    @field_validator("file_extension")
    @classmethod
    def _normalize_file_extension(cls, value: str) -> str:
        extension = value.lower().lstrip(".")
        if not extension:
            raise ValueError("file_extension must not be empty")
        return extension


class BoundingBox(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    x0: float
    y0: float
    x1: float
    y1: float
    coordinate_system: CoordinateSystem = "pdf_points_top_left"

    @model_validator(mode="after")
    def _validate_bounds(self) -> "BoundingBox":
        if self.x1 < self.x0:
            raise ValueError("x1 must be greater than or equal to x0")
        if self.y1 < self.y0:
            raise ValueError("y1 must be greater than or equal to y0")
        return self


class ParserRun(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    parser_run_id: str
    parser_name: str
    parser_version: str | None = None
    ir_version: str = IR_VERSION
    warnings: list[str] = Field(default_factory=list)

    @field_validator("parser_run_id", "parser_name", "ir_version")
    @classmethod
    def _must_not_be_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("must not be empty")
        return value


class TextSpan(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    span_id: SpanId
    page_number: int = Field(ge=1)
    text: str
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    reading_order: int = Field(ge=0)
    bbox: BoundingBox | None = None
    parser_run_id: str | None = None

    @model_validator(mode="after")
    def _validate_char_range(self) -> "TextSpan":
        if self.char_end < self.char_start:
            raise ValueError("char_end must be greater than or equal to char_start")
        return self


class Page(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    page_id: PageId
    page_number: int = Field(ge=1)
    width: float | None = Field(default=None, ge=0)
    height: float | None = Field(default=None, ge=0)
    rotation: int | None = None
    spans: list[TextSpan] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_span_pages(self) -> "Page":
        for span in self.spans:
            if span.page_number != self.page_number:
                raise ValueError("span page_number must match containing page")
        return self


class DocumentIR(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    ir_version: str = IR_VERSION
    document_id: DocumentId
    source: DocumentSource
    parser_runs: list[ParserRun] = Field(default_factory=list)
    content: str
    pages: list[Page] = Field(default_factory=list)

    @field_validator("document_id")
    @classmethod
    def _validate_document_id(cls, value: str) -> DocumentId:
        return validate_document_id(value)

    @field_validator("ir_version")
    @classmethod
    def _validate_ir_version(cls, value: str) -> str:
        if not value:
            raise ValueError("ir_version must not be empty")
        return value

    @model_validator(mode="after")
    def _validate_span_offsets(self) -> "DocumentIR":
        content_length = len(self.content)
        for page in self.pages:
            for span in page.spans:
                if span.char_end > content_length:
                    raise ValueError("span char_end exceeds document content length")
                if self.content[span.char_start : span.char_end] != span.text:
                    raise ValueError("span text must match document content at char range")
        return self
