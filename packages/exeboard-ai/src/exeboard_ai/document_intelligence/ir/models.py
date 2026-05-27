from enum import StrEnum
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from exeboard_ai.document_intelligence.core.ids import (
    DocumentId,
    PageId,
    SpanId,
    parse_page_id,
    parse_span_id,
    validate_document_id,
)

IR_VERSION = "0.1"
LAYOUT_VERSION = "0.1"

CoordinateSystem = Literal["pdf_points_top_left"]


class LayoutBlockType(StrEnum):
    SECTION = "section"
    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    LIST_ITEM = "list_item"
    TABLE = "table"
    FIGURE = "figure"
    CAPTION = "caption"
    FOOTNOTE = "footnote"
    FOOTER = "footer"
    HEADER = "header"
    PAGE_NUMBER = "page_number"
    UNKNOWN = "unknown"


class ContentLayer(StrEnum):
    BODY = "body"
    FURNITURE = "furniture"
    BACKGROUND = "background"
    INVISIBLE = "invisible"
    NOTES = "notes"
    UNKNOWN = "unknown"


class TableCellRole(StrEnum):
    CONTENT = "content"
    ROW_HEADER = "row_header"
    COLUMN_HEADER = "column_header"
    STUB_HEAD = "stub_head"
    DESCRIPTION = "description"
    ROW_SECTION = "row_section"
    UNKNOWN = "unknown"


_TEXT_BEARING_BLOCK_TYPES = frozenset(
    {
        LayoutBlockType.TITLE,
        LayoutBlockType.HEADING,
        LayoutBlockType.PARAGRAPH,
        LayoutBlockType.LIST_ITEM,
        LayoutBlockType.CAPTION,
        LayoutBlockType.FOOTNOTE,
        LayoutBlockType.FOOTER,
        LayoutBlockType.HEADER,
        LayoutBlockType.PAGE_NUMBER,
    }
)


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
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        allow_inf_nan=False,
    )

    x0: float = Field(ge=0)
    y0: float = Field(ge=0)
    x1: float = Field(ge=0)
    y1: float = Field(ge=0)
    coordinate_system: CoordinateSystem = "pdf_points_top_left"

    @model_validator(mode="after")
    def _validate_bounds(self) -> "BoundingBox":
        if self.x1 < self.x0:
            raise ValueError("x1 must be greater than or equal to x0")
        if self.y1 < self.y0:
            raise ValueError("y1 must be greater than or equal to y0")
        return self


class BoundingRegion(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    page_number: int = Field(ge=1)
    bbox: BoundingBox

    @model_validator(mode="after")
    def _validate_positive_area(self) -> "BoundingRegion":
        if self.bbox.x1 <= self.bbox.x0:
            raise ValueError("BoundingRegion bbox must have positive width")
        if self.bbox.y1 <= self.bbox.y0:
            raise ValueError("BoundingRegion bbox must have positive height")
        return self


def _validate_span_id_tuple(value: tuple[SpanId, ...], field_name: str) -> tuple[SpanId, ...]:
    if any(not span_id for span_id in value):
        raise ValueError(f"{field_name} must not contain empty values")
    if len(set(value)) != len(value):
        raise ValueError(f"{field_name} must be unique")
    return value


class LayoutBlock(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    block_id: str
    block_type: LayoutBlockType
    content_layer: ContentLayer
    page_numbers: tuple[int, ...]
    reading_order: int = Field(ge=0)
    source_span_ids: tuple[SpanId, ...] = ()
    bounding_regions: tuple[BoundingRegion, ...] = ()
    parent_block_id: str | None = None
    heading_level: int | None = Field(default=None, ge=1)
    table_id: str | None = None
    figure_id: str | None = None
    parser_element_ref: str | None = None

    @field_validator("block_id")
    @classmethod
    def _id_must_not_be_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("block_id must not be empty")
        return value

    @field_validator("parent_block_id", "table_id", "figure_id", "parser_element_ref")
    @classmethod
    def _optional_ids_must_not_be_empty(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("optional string fields must not be empty when provided")
        return value

    @field_validator("page_numbers")
    @classmethod
    def _validate_page_numbers(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if not value:
            raise ValueError("page_numbers must not be empty")
        if any(page_number < 1 for page_number in value):
            raise ValueError("page_numbers must be positive")
        if len(set(value)) != len(value):
            raise ValueError("page_numbers must be unique")
        return value

    @field_validator("source_span_ids")
    @classmethod
    def _validate_source_span_ids(cls, value: tuple[SpanId, ...]) -> tuple[SpanId, ...]:
        return _validate_span_id_tuple(value, "source_span_ids")

    @model_validator(mode="after")
    def _validate_block_semantics(self) -> "LayoutBlock":
        if self.block_type == LayoutBlockType.TABLE and self.table_id is None:
            raise ValueError("table blocks must reference table_id")
        if self.block_type == LayoutBlockType.FIGURE and self.figure_id is None:
            raise ValueError("figure blocks must reference figure_id")
        if self.table_id is not None and self.block_type != LayoutBlockType.TABLE:
            raise ValueError("table_id is only allowed on table blocks")
        if self.figure_id is not None and self.block_type != LayoutBlockType.FIGURE:
            raise ValueError("figure_id is only allowed on figure blocks")
        if self.block_type in _TEXT_BEARING_BLOCK_TYPES and not self.source_span_ids:
            raise ValueError("text-bearing layout blocks must cite source_span_ids")
        return self


class TableCell(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    row_index: int = Field(ge=0)
    column_index: int = Field(ge=0)
    row_span: int = Field(default=1, ge=1)
    column_span: int = Field(default=1, ge=1)
    roles: tuple[TableCellRole, ...] = (TableCellRole.CONTENT,)
    source_span_ids: tuple[SpanId, ...] = ()
    bounding_regions: tuple[BoundingRegion, ...] = ()
    parser_element_ref: str | None = None

    @field_validator("roles")
    @classmethod
    def _validate_roles(cls, value: tuple[TableCellRole, ...]) -> tuple[TableCellRole, ...]:
        if not value:
            raise ValueError("roles must not be empty")
        if len(set(value)) != len(value):
            raise ValueError("roles must be unique")
        return value

    @field_validator("source_span_ids")
    @classmethod
    def _validate_source_span_ids(cls, value: tuple[SpanId, ...]) -> tuple[SpanId, ...]:
        return _validate_span_id_tuple(value, "source_span_ids")

    @field_validator("parser_element_ref")
    @classmethod
    def _optional_ref_must_not_be_empty(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("parser_element_ref must not be empty when provided")
        return value

    @model_validator(mode="after")
    def _validate_cell_provenance(self) -> "TableCell":
        if not self.source_span_ids and not self.bounding_regions:
            raise ValueError("table cells must have source_span_ids or bounding_regions")
        return self


class Table(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    table_id: str
    layout_block_id: str
    row_count: int = Field(ge=1)
    column_count: int = Field(ge=1)
    cells: tuple[TableCell, ...]
    bounding_regions: tuple[BoundingRegion, ...] = ()
    parser_element_ref: str | None = None

    @field_validator("table_id", "layout_block_id")
    @classmethod
    def _ids_must_not_be_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("must not be empty")
        return value

    @field_validator("cells")
    @classmethod
    def _cells_must_not_be_empty(cls, value: tuple[TableCell, ...]) -> tuple[TableCell, ...]:
        if not value:
            raise ValueError("cells must not be empty")
        return value

    @field_validator("parser_element_ref")
    @classmethod
    def _optional_ref_must_not_be_empty(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("parser_element_ref must not be empty when provided")
        return value

    @model_validator(mode="after")
    def _validate_cells(self) -> "Table":
        covered_coordinates: set[tuple[int, int]] = set()

        for cell in self.cells:
            row_end = cell.row_index + cell.row_span
            column_end = cell.column_index + cell.column_span
            if row_end > self.row_count:
                raise ValueError("table cell extends beyond row_count")
            if column_end > self.column_count:
                raise ValueError("table cell extends beyond column_count")

            for row_index in range(cell.row_index, row_end):
                for column_index in range(cell.column_index, column_end):
                    coordinate = (row_index, column_index)
                    if coordinate in covered_coordinates:
                        raise ValueError("overlapping table cell coverage")
                    covered_coordinates.add(coordinate)

        return self


class Figure(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    figure_id: str
    layout_block_id: str
    source_span_ids: tuple[SpanId, ...] = ()
    caption_span_ids: tuple[SpanId, ...] = ()
    bounding_regions: tuple[BoundingRegion, ...]
    derived_description: str | None = None
    derived_description_is_authoritative: bool = False
    parser_element_ref: str | None = None

    @field_validator("figure_id", "layout_block_id")
    @classmethod
    def _ids_must_not_be_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("must not be empty")
        return value

    @field_validator("source_span_ids", "caption_span_ids")
    @classmethod
    def _validate_span_ids(cls, value: tuple[SpanId, ...]) -> tuple[SpanId, ...]:
        return _validate_span_id_tuple(value, "span ID fields")

    @field_validator("parser_element_ref")
    @classmethod
    def _optional_ref_must_not_be_empty(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("parser_element_ref must not be empty when provided")
        return value

    @model_validator(mode="after")
    def _validate_figure_provenance(self) -> "Figure":
        if self.derived_description is not None and not self.derived_description.strip():
            raise ValueError("derived_description must not be blank")
        if self.derived_description_is_authoritative:
            raise ValueError("authoritative derived figure descriptions are not supported")
        if not self.source_span_ids and not self.caption_span_ids and not self.bounding_regions:
            raise ValueError("figures must have source spans, caption spans, or bounding regions")
        return self


class DocumentLayout(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    layout_version: str = LAYOUT_VERSION
    parser_run_id: str
    blocks: tuple[LayoutBlock, ...]
    tables: tuple[Table, ...] = ()
    figures: tuple[Figure, ...] = ()

    @field_validator("layout_version", "parser_run_id")
    @classmethod
    def _must_not_be_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("must not be empty")
        return value

    @field_validator("blocks")
    @classmethod
    def _blocks_must_not_be_empty(cls, value: tuple[LayoutBlock, ...]) -> tuple[LayoutBlock, ...]:
        if not value:
            raise ValueError("blocks must not be empty")
        return value


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
    def _validate_spans(self) -> "Page":
        seen_reading_orders: set[int] = set()
        seen_span_ids: set[SpanId] = set()

        for span in self.spans:
            if span.page_number != self.page_number:
                raise ValueError("span page_number must match containing page")
            if span.reading_order in seen_reading_orders:
                raise ValueError("duplicate span reading_order on page")
            if span.span_id in seen_span_ids:
                raise ValueError("duplicate span_id on page")

            seen_reading_orders.add(span.reading_order)
            seen_span_ids.add(span.span_id)

        return self


class DocumentIR(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    ir_version: str = IR_VERSION
    document_id: DocumentId
    source: DocumentSource
    parser_runs: list[ParserRun] = Field(default_factory=list)
    content: str
    pages: list[Page] = Field(default_factory=list)
    layout: DocumentLayout | None = None

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
    def _validate_document_structure(self) -> "DocumentIR":
        content_length = len(self.content)
        seen_page_numbers: set[int] = set()
        seen_page_ids: set[PageId] = set()
        seen_span_ids: set[SpanId] = set()
        parser_run_ids = self._validate_parser_runs()
        spans_by_id: dict[SpanId, TextSpan] = {}

        for page in self.pages:
            if page.page_number in seen_page_numbers:
                raise ValueError("duplicate page_number")
            if page.page_id in seen_page_ids:
                raise ValueError("duplicate page_id")
            page_document_id, page_number = parse_page_id(page.page_id)
            if page_document_id != self.document_id or page_number != page.page_number:
                raise ValueError("page_id must match document_id and page_number")

            seen_page_numbers.add(page.page_number)
            seen_page_ids.add(page.page_id)

            for span in page.spans:
                if span.span_id in seen_span_ids:
                    raise ValueError("duplicate span_id in document")
                span_document_id, span_page_number, _span_index = parse_span_id(span.span_id)
                if span_document_id != self.document_id or span_page_number != span.page_number:
                    raise ValueError("span_id must match document_id and span page_number")
                if span.char_end > content_length:
                    raise ValueError("span char_end exceeds document content length")
                if self.content[span.char_start : span.char_end] != span.text:
                    raise ValueError("span text must match document content at char range")

                seen_span_ids.add(span.span_id)
                spans_by_id[span.span_id] = span

        if self.layout is not None:
            pages_by_number = {page.page_number: page for page in self.pages}
            self._validate_layout(
                parser_run_ids=parser_run_ids,
                page_numbers=seen_page_numbers,
                pages_by_number=pages_by_number,
                spans_by_id=spans_by_id,
            )

        return self

    def _validate_parser_runs(self) -> set[str]:
        parser_run_ids: set[str] = set()
        for parser_run in self.parser_runs:
            if parser_run.parser_run_id in parser_run_ids:
                raise ValueError("duplicate parser_run_id")
            parser_run_ids.add(parser_run.parser_run_id)
        return parser_run_ids

    def _validate_layout(
        self,
        *,
        parser_run_ids: set[str],
        page_numbers: set[int],
        pages_by_number: dict[int, Page],
        spans_by_id: dict[SpanId, TextSpan],
    ) -> None:
        assert self.layout is not None
        layout = self.layout

        if layout.parser_run_id not in parser_run_ids:
            raise ValueError("DocumentLayout.parser_run_id must reference an existing ParserRun")

        blocks_by_id = self._validate_blocks(
            layout=layout,
            page_numbers=page_numbers,
            pages_by_number=pages_by_number,
        )
        self._validate_parent_block_graph(blocks_by_id)
        tables_by_id = self._validate_tables(
            layout=layout,
            blocks_by_id=blocks_by_id,
            page_numbers=page_numbers,
            pages_by_number=pages_by_number,
        )
        figures_by_id = self._validate_figures(
            layout=layout,
            blocks_by_id=blocks_by_id,
            page_numbers=page_numbers,
            pages_by_number=pages_by_number,
        )

        for block in layout.blocks:
            block_page_numbers = self._block_page_provenance(block)
            self._validate_span_references(
                span_ids=block.source_span_ids,
                spans_by_id=spans_by_id,
                allowed_page_numbers=block_page_numbers,
                context=f"layout block {block.block_id}",
            )
            if block.table_id is not None and block.table_id not in tables_by_id:
                raise ValueError("table block table_id must reference an existing Table")
            if block.figure_id is not None and block.figure_id not in figures_by_id:
                raise ValueError("figure block figure_id must reference an existing Figure")

        for table in layout.tables:
            wrapper_block = blocks_by_id[table.layout_block_id]
            table_page_numbers = self._table_page_provenance(table, wrapper_block)
            for cell in table.cells:
                cell_page_numbers = table_page_numbers | self._region_page_numbers(cell.bounding_regions)
                self._validate_span_references(
                    span_ids=cell.source_span_ids,
                    spans_by_id=spans_by_id,
                    allowed_page_numbers=cell_page_numbers,
                    context=f"table {table.table_id} cell",
                )

        for figure in layout.figures:
            wrapper_block = blocks_by_id[figure.layout_block_id]
            figure_page_numbers = self._figure_page_provenance(figure, wrapper_block)
            self._validate_span_references(
                span_ids=figure.source_span_ids,
                spans_by_id=spans_by_id,
                allowed_page_numbers=figure_page_numbers,
                context=f"figure {figure.figure_id} source",
            )
            self._validate_span_references(
                span_ids=figure.caption_span_ids,
                spans_by_id=spans_by_id,
                allowed_page_numbers=figure_page_numbers,
                context=f"figure {figure.figure_id} caption",
            )

    def _validate_blocks(
        self,
        *,
        layout: DocumentLayout,
        page_numbers: set[int],
        pages_by_number: dict[int, Page],
    ) -> dict[str, LayoutBlock]:
        blocks_by_id: dict[str, LayoutBlock] = {}
        seen_reading_orders: set[int] = set()

        for block in layout.blocks:
            if block.block_id in blocks_by_id:
                raise ValueError("duplicate layout block_id")
            if block.reading_order in seen_reading_orders:
                raise ValueError("duplicate layout block reading_order")
            missing_page_numbers = set(block.page_numbers) - page_numbers
            if missing_page_numbers:
                raise ValueError("layout block page_numbers must exist in document pages")
            self._validate_bounding_region_pages(
                regions=block.bounding_regions,
                page_numbers=page_numbers,
                pages_by_number=pages_by_number,
            )

            blocks_by_id[block.block_id] = block
            seen_reading_orders.add(block.reading_order)

        return blocks_by_id

    @staticmethod
    def _validate_parent_block_graph(blocks_by_id: dict[str, LayoutBlock]) -> None:
        for block in blocks_by_id.values():
            parent_block_id = block.parent_block_id
            if parent_block_id is None:
                continue
            if parent_block_id not in blocks_by_id:
                raise ValueError("parent_block_id must reference an existing LayoutBlock")
            if parent_block_id == block.block_id:
                raise ValueError("layout block cannot be its own parent")

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(block_id: str) -> None:
            if block_id in visited:
                return
            if block_id in visiting:
                raise ValueError("layout parent block graph contains a cycle")

            visiting.add(block_id)
            parent_block_id = blocks_by_id[block_id].parent_block_id
            if parent_block_id is not None:
                visit(parent_block_id)
            visiting.remove(block_id)
            visited.add(block_id)

        for block_id in blocks_by_id:
            visit(block_id)

    def _validate_tables(
        self,
        *,
        layout: DocumentLayout,
        blocks_by_id: dict[str, LayoutBlock],
        page_numbers: set[int],
        pages_by_number: dict[int, Page],
    ) -> dict[str, Table]:
        tables_by_id: dict[str, Table] = {}
        for table in layout.tables:
            if table.table_id in tables_by_id:
                raise ValueError("duplicate table_id")
            wrapper_block = blocks_by_id.get(table.layout_block_id)
            if wrapper_block is None:
                raise ValueError("Table.layout_block_id must reference an existing LayoutBlock")
            if wrapper_block.block_type != LayoutBlockType.TABLE:
                raise ValueError("Table.layout_block_id must reference a table LayoutBlock")
            if wrapper_block.table_id != table.table_id:
                raise ValueError("table wrapper block table_id must match Table.table_id")
            self._validate_bounding_region_pages(
                regions=table.bounding_regions,
                page_numbers=page_numbers,
                pages_by_number=pages_by_number,
            )
            for cell in table.cells:
                self._validate_bounding_region_pages(
                    regions=cell.bounding_regions,
                    page_numbers=page_numbers,
                    pages_by_number=pages_by_number,
                )
            tables_by_id[table.table_id] = table
        return tables_by_id

    def _validate_figures(
        self,
        *,
        layout: DocumentLayout,
        blocks_by_id: dict[str, LayoutBlock],
        page_numbers: set[int],
        pages_by_number: dict[int, Page],
    ) -> dict[str, Figure]:
        figures_by_id: dict[str, Figure] = {}
        for figure in layout.figures:
            if figure.figure_id in figures_by_id:
                raise ValueError("duplicate figure_id")
            wrapper_block = blocks_by_id.get(figure.layout_block_id)
            if wrapper_block is None:
                raise ValueError("Figure.layout_block_id must reference an existing LayoutBlock")
            if wrapper_block.block_type != LayoutBlockType.FIGURE:
                raise ValueError("Figure.layout_block_id must reference a figure LayoutBlock")
            if wrapper_block.figure_id != figure.figure_id:
                raise ValueError("figure wrapper block figure_id must match Figure.figure_id")
            self._validate_bounding_region_pages(
                regions=figure.bounding_regions,
                page_numbers=page_numbers,
                pages_by_number=pages_by_number,
            )
            figures_by_id[figure.figure_id] = figure
        return figures_by_id

    @staticmethod
    def _validate_bounding_region_pages(
        *,
        regions: tuple[BoundingRegion, ...],
        page_numbers: set[int],
        pages_by_number: dict[int, Page],
    ) -> None:
        for region in regions:
            if region.page_number not in page_numbers:
                raise ValueError("BoundingRegion page_number must exist in document pages")
            page = pages_by_number[region.page_number]
            if page.width is not None and region.bbox.x1 > page.width:
                raise ValueError("BoundingRegion bbox must fit within page width")
            if page.height is not None and region.bbox.y1 > page.height:
                raise ValueError("BoundingRegion bbox must fit within page height")

    def _validate_span_references(
        self,
        *,
        span_ids: tuple[SpanId, ...],
        spans_by_id: dict[SpanId, TextSpan],
        allowed_page_numbers: set[int],
        context: str,
    ) -> None:
        for span_id in span_ids:
            if span_id not in spans_by_id:
                if not span_id.startswith(f"{self.document_id}:"):
                    raise ValueError(f"{context} span_id must belong to document_id")
                raise ValueError(f"unknown {context} span_id")

            span = spans_by_id[span_id]
            if not span.span_id.startswith(f"{self.document_id}:"):
                raise ValueError(f"{context} span_id must belong to document_id")
            if span.page_number not in allowed_page_numbers:
                raise ValueError(
                    f"{context} span page_number must be included in layout page provenance"
                )

    @staticmethod
    def _block_page_provenance(block: LayoutBlock) -> set[int]:
        return set(block.page_numbers) | DocumentIR._region_page_numbers(block.bounding_regions)

    @staticmethod
    def _table_page_provenance(table: Table, wrapper_block: LayoutBlock) -> set[int]:
        return (
            set(wrapper_block.page_numbers)
            | DocumentIR._region_page_numbers(wrapper_block.bounding_regions)
            | DocumentIR._region_page_numbers(table.bounding_regions)
        )

    @staticmethod
    def _figure_page_provenance(figure: Figure, wrapper_block: LayoutBlock) -> set[int]:
        return (
            set(wrapper_block.page_numbers)
            | DocumentIR._region_page_numbers(wrapper_block.bounding_regions)
            | DocumentIR._region_page_numbers(figure.bounding_regions)
        )

    @staticmethod
    def _region_page_numbers(regions: tuple[BoundingRegion, ...]) -> set[int]:
        return {region.page_number for region in regions}
