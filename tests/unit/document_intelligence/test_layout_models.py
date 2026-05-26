import pytest
from pydantic import ValidationError

from exeboard_ai.document_intelligence.chunking.chunker import chunk_document
from exeboard_ai.document_intelligence.core.ids import make_chunk_id, make_page_id, make_span_id
from exeboard_ai.document_intelligence.ir.models import (
    BoundingBox,
    BoundingRegion,
    ContentLayer,
    DocumentIR,
    DocumentLayout,
    DocumentSource,
    Figure,
    LayoutBlock,
    LayoutBlockType,
    Page,
    ParserRun,
    Table,
    TableCell,
    TableCellRole,
    TextSpan,
)

DOCUMENT_ID = "550e8400-e29b-41d4-a716-446655440000"
OTHER_DOCUMENT_ID = "650e8400-e29b-41d4-a716-446655440000"
PARSER_RUN_ID = "test-parser:layout"


def _span_id(page_number: int, span_index: int, document_id: str = DOCUMENT_ID) -> str:
    return make_span_id(document_id, page_number, span_index)


def _region(page_number: int = 1) -> BoundingRegion:
    return BoundingRegion(
        page_number=page_number,
        bbox=BoundingBox(x0=72, y0=72, x1=200, y1=96),
    )


def _document(
    page_texts: list[list[str]] | None = None,
    *,
    layout: DocumentLayout | None = None,
    parser_runs: list[ParserRun] | None = None,
    document_id: str = DOCUMENT_ID,
) -> DocumentIR:
    if page_texts is None:
        page_texts = [["Alpha paragraph", "Beta paragraph"]]

    content_parts: list[str] = []
    pages: list[Page] = []

    for page_index, texts in enumerate(page_texts):
        page_number = page_index + 1
        spans: list[TextSpan] = []
        for span_index, text in enumerate(texts):
            if content_parts:
                content_parts.append("\n")
            char_start = len("".join(content_parts))
            content_parts.append(text)
            spans.append(
                TextSpan(
                    span_id=make_span_id(document_id, page_number, span_index),
                    page_number=page_number,
                    text=text,
                    char_start=char_start,
                    char_end=char_start + len(text),
                    reading_order=span_index,
                    parser_run_id=PARSER_RUN_ID,
                )
            )
        pages.append(
            Page(
                page_id=make_page_id(document_id, page_number),
                page_number=page_number,
                width=612,
                height=792,
                rotation=0,
                spans=spans,
            )
        )

    return DocumentIR(
        document_id=document_id,
        source=DocumentSource(file_name=f"{document_id}.pdf", file_extension="pdf"),
        parser_runs=parser_runs
        if parser_runs is not None
        else [ParserRun(parser_run_id=PARSER_RUN_ID, parser_name="test-parser")],
        content="".join(content_parts),
        pages=pages,
        layout=layout,
    )


def _paragraph_block(
    *,
    block_id: str = "block-1",
    reading_order: int = 0,
    source_span_ids: tuple[str, ...] | None = None,
    page_numbers: tuple[int, ...] = (1,),
    parent_block_id: str | None = None,
) -> LayoutBlock:
    return LayoutBlock(
        block_id=block_id,
        block_type=LayoutBlockType.PARAGRAPH,
        content_layer=ContentLayer.BODY,
        page_numbers=page_numbers,
        reading_order=reading_order,
        source_span_ids=source_span_ids if source_span_ids is not None else (_span_id(1, 0),),
        bounding_regions=(_region(page_numbers[0]),),
        parent_block_id=parent_block_id,
    )


def _layout(
    *,
    blocks: tuple[LayoutBlock, ...] | None = None,
    tables: tuple[Table, ...] = (),
    figures: tuple[Figure, ...] = (),
    parser_run_id: str = PARSER_RUN_ID,
) -> DocumentLayout:
    return DocumentLayout(
        parser_run_id=parser_run_id,
        blocks=blocks if blocks is not None else (_paragraph_block(),),
        tables=tables,
        figures=figures,
    )


def test_document_ir_without_layout_remains_valid() -> None:
    document = _document()

    assert document.layout is None


def test_valid_paragraph_layout_references_existing_spans() -> None:
    layout = _layout()

    document = _document(layout=layout)

    assert document.layout is layout
    assert document.layout.blocks[0].source_span_ids == (_span_id(1, 0),)
    assert document.layout.blocks[0].bounding_regions[0].bbox.coordinate_system == "pdf_points_top_left"


def test_document_layout_parser_run_id_must_reference_existing_parser_run() -> None:
    layout = _layout(parser_run_id="missing-parser")

    with pytest.raises(ValidationError, match="parser_run_id must reference"):
        _document(layout=layout)


def test_document_layout_blocks_must_not_be_empty() -> None:
    with pytest.raises(ValidationError, match="blocks must not be empty"):
        DocumentLayout(parser_run_id=PARSER_RUN_ID, blocks=())


def test_duplicate_parser_run_ids_are_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate parser_run_id"):
        _document(
            parser_runs=[
                ParserRun(parser_run_id=PARSER_RUN_ID, parser_name="first"),
                ParserRun(parser_run_id=PARSER_RUN_ID, parser_name="second"),
            ]
        )


def test_missing_span_id_in_layout_is_rejected() -> None:
    layout = _layout(blocks=(_paragraph_block(source_span_ids=(_span_id(1, 99),)),))

    with pytest.raises(ValidationError, match="unknown layout block block-1 span_id"):
        _document(layout=layout)


def test_cross_document_span_id_in_layout_is_rejected() -> None:
    layout = _layout(
        blocks=(_paragraph_block(source_span_ids=(_span_id(1, 0, OTHER_DOCUMENT_ID),)),)
    )

    with pytest.raises(ValidationError, match="span_id must belong to document_id"):
        _document(layout=layout)


def test_layout_span_id_tuples_must_not_contain_duplicates_or_empty_values() -> None:
    with pytest.raises(ValidationError, match="source_span_ids must be unique"):
        _paragraph_block(source_span_ids=(_span_id(1, 0), _span_id(1, 0)))

    with pytest.raises(ValidationError, match="source_span_ids must not contain empty values"):
        TableCell(row_index=0, column_index=0, source_span_ids=("",))

    with pytest.raises(ValidationError, match="span ID fields must be unique"):
        Figure(
            figure_id="figure-1",
            layout_block_id="figure-block",
            source_span_ids=(_span_id(1, 0), _span_id(1, 0)),
            bounding_regions=(_region(1),),
        )

    with pytest.raises(ValidationError, match="span ID fields must not contain empty values"):
        Figure(
            figure_id="figure-1",
            layout_block_id="figure-block",
            caption_span_ids=("",),
            bounding_regions=(_region(1),),
        )


def test_referenced_span_page_must_match_layout_page_provenance() -> None:
    layout = _layout(blocks=(_paragraph_block(source_span_ids=(_span_id(2, 0),)),))

    with pytest.raises(ValidationError, match="span page_number must be included"):
        _document(page_texts=[["Page one"], ["Page two"]], layout=layout)


def test_bounding_region_rejects_zero_area_boxes() -> None:
    with pytest.raises(ValidationError, match="positive width"):
        BoundingRegion(
            page_number=1,
            bbox=BoundingBox(x0=10, y0=10, x1=10, y1=20),
        )

    with pytest.raises(ValidationError, match="positive height"):
        BoundingRegion(
            page_number=1,
            bbox=BoundingBox(x0=10, y0=10, x1=20, y1=10),
        )


def test_bounding_box_rejects_negative_non_finite_and_extra_coordinates() -> None:
    with pytest.raises(ValidationError):
        BoundingBox(x0=-1, y0=0, x1=1, y1=1)

    with pytest.raises(ValidationError):
        BoundingBox(x0=0, y0=0, x1=float("inf"), y1=1)

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        BoundingBox(x0=0, y0=0, x1=1, y1=1, polygon=[0, 0, 1, 1])


def test_bounding_region_page_number_must_exist_in_document_pages() -> None:
    block = LayoutBlock(
        block_id="block-1",
        block_type=LayoutBlockType.PARAGRAPH,
        content_layer=ContentLayer.BODY,
        page_numbers=(1,),
        reading_order=0,
        source_span_ids=(_span_id(1, 0),),
        bounding_regions=(_region(2),),
    )

    with pytest.raises(ValidationError, match="BoundingRegion page_number must exist"):
        _document(layout=_layout(blocks=(block,)))


def test_layout_bounding_regions_must_fit_within_page_dimensions_when_known() -> None:
    block_too_wide = LayoutBlock(
        block_id="block-1",
        block_type=LayoutBlockType.PARAGRAPH,
        content_layer=ContentLayer.BODY,
        page_numbers=(1,),
        reading_order=0,
        source_span_ids=(_span_id(1, 0),),
        bounding_regions=(
            BoundingRegion(
                page_number=1,
                bbox=BoundingBox(x0=0, y0=0, x1=700, y1=100),
            ),
        ),
    )
    with pytest.raises(ValidationError, match="fit within page width"):
        _document(layout=_layout(blocks=(block_too_wide,)))

    block_too_tall = LayoutBlock(
        block_id="block-1",
        block_type=LayoutBlockType.PARAGRAPH,
        content_layer=ContentLayer.BODY,
        page_numbers=(1,),
        reading_order=0,
        source_span_ids=(_span_id(1, 0),),
        bounding_regions=(
            BoundingRegion(
                page_number=1,
                bbox=BoundingBox(x0=0, y0=0, x1=100, y1=900),
            ),
        ),
    )
    with pytest.raises(ValidationError, match="fit within page height"):
        _document(layout=_layout(blocks=(block_too_tall,)))


def test_duplicate_block_ids_are_rejected() -> None:
    layout = _layout(
        blocks=(
            _paragraph_block(block_id="duplicate", reading_order=0),
            _paragraph_block(block_id="duplicate", reading_order=1, source_span_ids=(_span_id(1, 1),)),
        )
    )

    with pytest.raises(ValidationError, match="duplicate layout block_id"):
        _document(layout=layout)


def test_duplicate_block_reading_order_is_rejected() -> None:
    layout = _layout(
        blocks=(
            _paragraph_block(block_id="block-1", reading_order=0),
            _paragraph_block(block_id="block-2", reading_order=0, source_span_ids=(_span_id(1, 1),)),
        )
    )

    with pytest.raises(ValidationError, match="duplicate layout block reading_order"):
        _document(layout=layout)


def test_duplicate_table_ids_are_rejected() -> None:
    first_block = LayoutBlock(
        block_id="table-block-1",
        block_type=LayoutBlockType.TABLE,
        content_layer=ContentLayer.BODY,
        page_numbers=(1,),
        reading_order=0,
        table_id="duplicate-table",
    )
    second_block = LayoutBlock(
        block_id="table-block-2",
        block_type=LayoutBlockType.TABLE,
        content_layer=ContentLayer.BODY,
        page_numbers=(1,),
        reading_order=1,
        table_id="duplicate-table",
    )
    tables = (
        Table(
            table_id="duplicate-table",
            layout_block_id="table-block-1",
            row_count=1,
            column_count=1,
            cells=(TableCell(row_index=0, column_index=0, bounding_regions=(_region(1),)),),
        ),
        Table(
            table_id="duplicate-table",
            layout_block_id="table-block-2",
            row_count=1,
            column_count=1,
            cells=(TableCell(row_index=0, column_index=0, bounding_regions=(_region(1),)),),
        ),
    )

    with pytest.raises(ValidationError, match="duplicate table_id"):
        _document(layout=_layout(blocks=(first_block, second_block), tables=tables))


def test_duplicate_figure_ids_are_rejected() -> None:
    first_block = LayoutBlock(
        block_id="figure-block-1",
        block_type=LayoutBlockType.FIGURE,
        content_layer=ContentLayer.BODY,
        page_numbers=(1,),
        reading_order=0,
        figure_id="duplicate-figure",
    )
    second_block = LayoutBlock(
        block_id="figure-block-2",
        block_type=LayoutBlockType.FIGURE,
        content_layer=ContentLayer.BODY,
        page_numbers=(1,),
        reading_order=1,
        figure_id="duplicate-figure",
    )
    figures = (
        Figure(
            figure_id="duplicate-figure",
            layout_block_id="figure-block-1",
            bounding_regions=(_region(1),),
        ),
        Figure(
            figure_id="duplicate-figure",
            layout_block_id="figure-block-2",
            bounding_regions=(_region(1),),
        ),
    )

    with pytest.raises(ValidationError, match="duplicate figure_id"):
        _document(layout=_layout(blocks=(first_block, second_block), figures=figures))


def test_table_and_figure_blocks_must_carry_detail_ids() -> None:
    with pytest.raises(ValidationError, match="table blocks must reference table_id"):
        LayoutBlock(
            block_id="table-block",
            block_type=LayoutBlockType.TABLE,
            content_layer=ContentLayer.BODY,
            page_numbers=(1,),
            reading_order=0,
        )

    with pytest.raises(ValidationError, match="figure blocks must reference figure_id"):
        LayoutBlock(
            block_id="figure-block",
            block_type=LayoutBlockType.FIGURE,
            content_layer=ContentLayer.BODY,
            page_numbers=(1,),
            reading_order=0,
        )


def test_non_table_and_non_figure_blocks_cannot_carry_detail_ids() -> None:
    with pytest.raises(ValidationError, match="table_id is only allowed on table blocks"):
        LayoutBlock(
            block_id="paragraph",
            block_type=LayoutBlockType.PARAGRAPH,
            content_layer=ContentLayer.BODY,
            page_numbers=(1,),
            reading_order=0,
            source_span_ids=(_span_id(1, 0),),
            table_id="table-1",
        )

    with pytest.raises(ValidationError, match="figure_id is only allowed on figure blocks"):
        LayoutBlock(
            block_id="paragraph",
            block_type=LayoutBlockType.PARAGRAPH,
            content_layer=ContentLayer.BODY,
            page_numbers=(1,),
            reading_order=0,
            source_span_ids=(_span_id(1, 0),),
            figure_id="figure-1",
        )


def test_missing_parent_block_is_rejected() -> None:
    layout = _layout(blocks=(_paragraph_block(parent_block_id="missing-parent"),))

    with pytest.raises(ValidationError, match="parent_block_id must reference"):
        _document(layout=layout)


def test_self_parent_block_is_rejected() -> None:
    layout = _layout(blocks=(_paragraph_block(block_id="self", parent_block_id="self"),))

    with pytest.raises(ValidationError, match="cannot be its own parent"):
        _document(layout=layout)


def test_parent_block_cycles_are_rejected() -> None:
    section_a = LayoutBlock(
        block_id="section-a",
        block_type=LayoutBlockType.SECTION,
        content_layer=ContentLayer.BODY,
        page_numbers=(1,),
        reading_order=0,
        parent_block_id="section-b",
    )
    section_b = LayoutBlock(
        block_id="section-b",
        block_type=LayoutBlockType.SECTION,
        content_layer=ContentLayer.BODY,
        page_numbers=(1,),
        reading_order=1,
        parent_block_id="section-a",
    )

    with pytest.raises(ValidationError, match="parent block graph contains a cycle"):
        _document(layout=_layout(blocks=(section_a, section_b)))


@pytest.mark.parametrize(
    "layer",
    [
        "body",
        "furniture",
        "background",
        "invisible",
        "notes",
        "unknown",
    ],
)
def test_content_layer_accepts_required_values(layer: str) -> None:
    block = LayoutBlock(
        block_id=f"section-{layer}",
        block_type=LayoutBlockType.SECTION,
        content_layer=layer,
        page_numbers=(1,),
        reading_order=0,
    )

    assert block.content_layer == layer


@pytest.mark.parametrize(
    "block_type",
    [
        "section",
        "title",
        "heading",
        "paragraph",
        "list",
        "list_item",
        "table",
        "figure",
        "caption",
        "footnote",
        "footer",
        "header",
        "page_number",
        "unknown",
    ],
)
def test_layout_block_type_accepts_required_values(block_type: str) -> None:
    text_bearing_types = {
        "title",
        "heading",
        "paragraph",
        "list_item",
        "caption",
        "footnote",
        "footer",
        "header",
        "page_number",
    }
    block = LayoutBlock(
        block_id=f"block-{block_type}",
        block_type=block_type,
        content_layer=ContentLayer.BODY,
        page_numbers=(1,),
        reading_order=0,
        source_span_ids=(_span_id(1, 0),) if block_type in text_bearing_types else (),
        table_id="table-1" if block_type == "table" else None,
        figure_id="figure-1" if block_type == "figure" else None,
    )

    assert block.block_type == block_type


def test_header_footer_and_page_number_can_be_furniture() -> None:
    header = LayoutBlock(
        block_id="header",
        block_type=LayoutBlockType.HEADER,
        content_layer=ContentLayer.FURNITURE,
        page_numbers=(1,),
        reading_order=0,
        source_span_ids=(_span_id(1, 0),),
    )
    footer = LayoutBlock(
        block_id="footer",
        block_type=LayoutBlockType.FOOTER,
        content_layer=ContentLayer.FURNITURE,
        page_numbers=(1,),
        reading_order=1,
        source_span_ids=(_span_id(1, 1),),
    )
    page_number = LayoutBlock(
        block_id="page-number",
        block_type=LayoutBlockType.PAGE_NUMBER,
        content_layer=ContentLayer.FURNITURE,
        page_numbers=(1,),
        reading_order=2,
        source_span_ids=(_span_id(1, 2),),
    )

    document = _document(
        page_texts=[["Confidential", "Footer", "1"]],
        layout=_layout(blocks=(header, footer, page_number)),
    )

    assert [block.content_layer for block in document.layout.blocks] == [
        ContentLayer.FURNITURE,
        ContentLayer.FURNITURE,
        ContentLayer.FURNITURE,
    ]


def test_table_cell_must_have_text_or_visual_provenance() -> None:
    with pytest.raises(ValidationError, match="table cells must have source_span_ids or bounding_regions"):
        TableCell(row_index=0, column_index=0)


def test_table_cells_must_not_be_empty() -> None:
    with pytest.raises(ValidationError, match="cells must not be empty"):
        Table(
            table_id="table-1",
            layout_block_id="table-block",
            row_count=1,
            column_count=1,
            cells=(),
        )


def test_valid_table_wrapper_block_table_and_cell_pass() -> None:
    block = LayoutBlock(
        block_id="table-block",
        block_type=LayoutBlockType.TABLE,
        content_layer=ContentLayer.BODY,
        page_numbers=(1,),
        reading_order=0,
        table_id="table-1",
    )
    table = Table(
        table_id="table-1",
        layout_block_id="table-block",
        row_count=1,
        column_count=1,
        cells=(TableCell(row_index=0, column_index=0, source_span_ids=(_span_id(1, 0),)),),
        bounding_regions=(_region(1),),
    )

    document = _document(layout=_layout(blocks=(block,), tables=(table,)))

    assert document.layout.tables[0].cells[0].roles == (TableCellRole.CONTENT,)


def test_table_block_table_id_mismatch_is_rejected() -> None:
    block = LayoutBlock(
        block_id="table-block",
        block_type=LayoutBlockType.TABLE,
        content_layer=ContentLayer.BODY,
        page_numbers=(1,),
        reading_order=0,
        table_id="wrong-table-id",
    )
    table = Table(
        table_id="table-1",
        layout_block_id="table-block",
        row_count=1,
        column_count=1,
        cells=(TableCell(row_index=0, column_index=0, bounding_regions=(_region(1),)),),
    )

    with pytest.raises(ValidationError, match="table_id must match"):
        _document(layout=_layout(blocks=(block,), tables=(table,)))


def test_table_cell_out_of_row_or_column_bounds_is_rejected() -> None:
    with pytest.raises(ValidationError, match="extends beyond row_count"):
        Table(
            table_id="table-1",
            layout_block_id="table-block",
            row_count=1,
            column_count=2,
            cells=(TableCell(row_index=0, column_index=0, row_span=2, bounding_regions=(_region(1),)),),
        )

    with pytest.raises(ValidationError, match="extends beyond column_count"):
        Table(
            table_id="table-1",
            layout_block_id="table-block",
            row_count=2,
            column_count=1,
            cells=(TableCell(row_index=0, column_index=0, column_span=2, bounding_regions=(_region(1),)),),
        )


def test_overlapping_table_cells_are_rejected() -> None:
    with pytest.raises(ValidationError, match="overlapping table cell coverage"):
        Table(
            table_id="table-1",
            layout_block_id="table-block",
            row_count=2,
            column_count=2,
            cells=(
                TableCell(row_index=0, column_index=0, row_span=2, bounding_regions=(_region(1),)),
                TableCell(row_index=1, column_index=0, bounding_regions=(_region(1),)),
            ),
        )


def test_table_cell_roles_must_be_non_empty_and_unique() -> None:
    with pytest.raises(ValidationError, match="roles must not be empty"):
        TableCell(row_index=0, column_index=0, roles=())

    with pytest.raises(ValidationError, match="roles must be unique"):
        TableCell(
            row_index=0,
            column_index=0,
            roles=(TableCellRole.CONTENT, TableCellRole.CONTENT),
        )


def test_visual_only_figure_with_bounding_region_and_no_spans_passes() -> None:
    block = LayoutBlock(
        block_id="figure-block",
        block_type=LayoutBlockType.FIGURE,
        content_layer=ContentLayer.BODY,
        page_numbers=(1,),
        reading_order=0,
        figure_id="figure-1",
    )
    figure = Figure(
        figure_id="figure-1",
        layout_block_id="figure-block",
        bounding_regions=(_region(1),),
    )

    document = _document(layout=_layout(blocks=(block,), figures=(figure,)))

    assert document.layout.figures[0].source_span_ids == ()


def test_figure_without_spans_or_bounding_region_is_rejected() -> None:
    with pytest.raises(ValidationError, match="figures must have source spans"):
        Figure(
            figure_id="figure-1",
            layout_block_id="figure-block",
            bounding_regions=(),
        )


def test_figure_wrapper_figure_id_mismatch_is_rejected() -> None:
    block = LayoutBlock(
        block_id="figure-block",
        block_type=LayoutBlockType.FIGURE,
        content_layer=ContentLayer.BODY,
        page_numbers=(1,),
        reading_order=0,
        figure_id="wrong-figure-id",
    )
    figure = Figure(
        figure_id="figure-1",
        layout_block_id="figure-block",
        bounding_regions=(_region(1),),
    )

    with pytest.raises(ValidationError, match="figure_id must match"):
        _document(layout=_layout(blocks=(block,), figures=(figure,)))


def test_caption_span_ids_are_validated_separately() -> None:
    block = LayoutBlock(
        block_id="figure-block",
        block_type=LayoutBlockType.FIGURE,
        content_layer=ContentLayer.BODY,
        page_numbers=(1,),
        reading_order=0,
        figure_id="figure-1",
    )
    figure = Figure(
        figure_id="figure-1",
        layout_block_id="figure-block",
        caption_span_ids=(_span_id(1, 99),),
        bounding_regions=(_region(1),),
    )

    with pytest.raises(ValidationError, match="unknown figure figure-1 caption span_id"):
        _document(layout=_layout(blocks=(block,), figures=(figure,)))


def test_cross_page_non_contiguous_block_table_and_figure_can_be_represented() -> None:
    section = LayoutBlock(
        block_id="section",
        block_type=LayoutBlockType.SECTION,
        content_layer=ContentLayer.BODY,
        page_numbers=(1, 3),
        reading_order=0,
        bounding_regions=(_region(1), _region(3)),
    )
    table_block = LayoutBlock(
        block_id="table-block",
        block_type=LayoutBlockType.TABLE,
        content_layer=ContentLayer.BODY,
        page_numbers=(1, 3),
        reading_order=1,
        table_id="table-1",
        bounding_regions=(_region(1), _region(3)),
    )
    figure_block = LayoutBlock(
        block_id="figure-block",
        block_type=LayoutBlockType.FIGURE,
        content_layer=ContentLayer.BODY,
        page_numbers=(1, 3),
        reading_order=2,
        figure_id="figure-1",
    )
    table = Table(
        table_id="table-1",
        layout_block_id="table-block",
        row_count=2,
        column_count=1,
        cells=(
            TableCell(row_index=0, column_index=0, source_span_ids=(_span_id(1, 0),)),
            TableCell(row_index=1, column_index=0, source_span_ids=(_span_id(3, 0),)),
        ),
        bounding_regions=(_region(1), _region(3)),
    )
    figure = Figure(
        figure_id="figure-1",
        layout_block_id="figure-block",
        bounding_regions=(_region(1), _region(3)),
    )

    document = _document(
        page_texts=[["Page one"], ["Page two"], ["Page three"]],
        layout=_layout(blocks=(section, table_block, figure_block), tables=(table,), figures=(figure,)),
    )

    assert document.layout.blocks[0].page_numbers == (1, 3)
    assert document.layout.tables[0].bounding_regions[1].page_number == 3
    assert document.layout.figures[0].bounding_regions[1].page_number == 3


def test_document_ir_with_layout_serializes_and_round_trips() -> None:
    paragraph = _paragraph_block(block_id="paragraph", reading_order=0)
    table_block = LayoutBlock(
        block_id="table-block",
        block_type=LayoutBlockType.TABLE,
        content_layer=ContentLayer.BODY,
        page_numbers=(1,),
        reading_order=1,
        table_id="table-1",
        bounding_regions=(_region(1),),
    )
    figure_block = LayoutBlock(
        block_id="figure-block",
        block_type=LayoutBlockType.FIGURE,
        content_layer=ContentLayer.BODY,
        page_numbers=(1,),
        reading_order=2,
        figure_id="figure-1",
        bounding_regions=(_region(1),),
    )
    table = Table(
        table_id="table-1",
        layout_block_id="table-block",
        row_count=1,
        column_count=1,
        cells=(TableCell(row_index=0, column_index=0, source_span_ids=(_span_id(1, 1),)),),
        bounding_regions=(_region(1),),
    )
    figure = Figure(
        figure_id="figure-1",
        layout_block_id="figure-block",
        caption_span_ids=(_span_id(1, 2),),
        bounding_regions=(_region(1),),
        derived_description="Non-authoritative chart description.",
    )
    document = _document(
        page_texts=[["Paragraph", "Table cell", "Figure caption"]],
        layout=_layout(
            blocks=(paragraph, table_block, figure_block),
            tables=(table,),
            figures=(figure,),
        ),
    )

    dumped = document.model_dump()
    restored = DocumentIR.model_validate(dumped)
    json_dumped = document.model_dump_json()
    json_restored = DocumentIR.model_validate_json(json_dumped)

    assert restored == document
    assert json_restored == document


def test_extra_text_or_vendor_object_fields_are_rejected_by_layout_models() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        LayoutBlock(
            block_id="block-1",
            block_type=LayoutBlockType.PARAGRAPH,
            content_layer=ContentLayer.BODY,
            page_numbers=(1,),
            reading_order=0,
            source_span_ids=(_span_id(1, 0),),
            text="duplicate authoritative text",
        )

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        TableCell(
            row_index=0,
            column_index=0,
            vendor_object={"raw": "parser payload"},
        )


def test_chunk_document_output_is_unchanged_and_ignores_layout() -> None:
    document = _document(layout=_layout())

    chunks = chunk_document(document, target_chars=100, max_chars=120)

    assert len(chunks) == 1
    assert chunks[0].chunk_id == make_chunk_id(DOCUMENT_ID, 0)
    assert chunks[0].text == "Alpha paragraph\nBeta paragraph"
    assert chunks[0].source_span_ids == [_span_id(1, 0), _span_id(1, 1)]
