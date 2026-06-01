import pytest
from pydantic import ValidationError

from exeboard_ai.document_intelligence.core.ids import make_page_id, make_span_id
from exeboard_ai.document_intelligence.ir.models import (
    IR_VERSION,
    BoundingBox,
    DocumentIR,
    DocumentSource,
    Page,
    ParserRun,
    TextSpan,
)

DOCUMENT_ID = "550e8400-e29b-41d4-a716-446655440000"
PARSER_RUN_ID = "test-parser:text"


def _make_document_ir() -> DocumentIR:
    content = "This Agreement begins on January 1.\nEither party may terminate with 30 days notice."
    first_text = "This Agreement begins on January 1."
    second_text = "Either party may terminate with 30 days notice."
    second_start = content.index(second_text)

    return DocumentIR(
        document_id=DOCUMENT_ID,
        source=DocumentSource(
            file_name=f"{DOCUMENT_ID}.pdf",
            file_extension="pdf",
            mime_type="application/pdf",
            source_uri="memory://fixture",
            content_sha256=None,
        ),
        parser_runs=[
            ParserRun(
                parser_run_id=PARSER_RUN_ID,
                parser_name="test-parser",
                parser_version="1.0",
            )
        ],
        content=content,
        pages=[
            Page(
                page_id=make_page_id(DOCUMENT_ID, 1),
                page_number=1,
                width=612,
                height=792,
                rotation=0,
                spans=[
                    TextSpan(
                        span_id=make_span_id(DOCUMENT_ID, 1, 0),
                        page_number=1,
                        text=first_text,
                        char_start=0,
                        char_end=len(first_text),
                        reading_order=0,
                        bbox=None,
                        parser_run_id=PARSER_RUN_ID,
                    ),
                    TextSpan(
                        span_id=make_span_id(DOCUMENT_ID, 1, 1),
                        page_number=1,
                        text=second_text,
                        char_start=second_start,
                        char_end=second_start + len(second_text),
                        reading_order=1,
                        bbox=BoundingBox(x0=72, y0=120, x1=500, y1=140),
                        parser_run_id=PARSER_RUN_ID,
                    ),
                ],
            )
        ],
    )


def test_can_create_document_ir_with_pages_and_spans() -> None:
    document = _make_document_ir()

    assert document.ir_version == IR_VERSION
    assert document.document_id == DOCUMENT_ID
    assert document.pages[0].page_number == 1
    assert document.pages[0].spans[0].text == "This Agreement begins on January 1."


def test_document_ir_serializes_to_json_ready_dict() -> None:
    document = _make_document_ir()

    data = document.model_dump()

    assert data["document_id"] == DOCUMENT_ID
    assert data["source"]["file_name"] == f"{DOCUMENT_ID}.pdf"
    assert data["pages"][0]["spans"][1]["bbox"]["coordinate_system"] == "pdf_points_top_left"


@pytest.mark.parametrize(
    ("model_factory", "kwargs"),
    [
        (
            DocumentSource,
            {"file_name": f"{DOCUMENT_ID}.pdf", "file_extension": "pdf"},
        ),
        (ParserRun, {"parser_run_id": PARSER_RUN_ID, "parser_name": "test-parser"}),
        (
            TextSpan,
            {
                "span_id": make_span_id(DOCUMENT_ID, 1, 0),
                "page_number": 1,
                "text": "Alpha",
                "char_start": 0,
                "char_end": 5,
                "reading_order": 0,
            },
        ),
        (Page, {"page_id": make_page_id(DOCUMENT_ID, 1), "page_number": 1}),
        (
            DocumentIR,
            {
                "document_id": DOCUMENT_ID,
                "source": DocumentSource(file_name=f"{DOCUMENT_ID}.pdf", file_extension="pdf"),
                "content": "",
                "pages": [],
            },
        ),
    ],
)
def test_core_ir_models_reject_unknown_fields(model_factory, kwargs: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        model_factory(**kwargs, unexpected_field="value")


def test_document_id_is_canonicalized() -> None:
    document = _make_document_ir().model_copy(
        update={"document_id": "550E8400-E29B-41D4-A716-446655440000"}
    )

    document = DocumentIR.model_validate(document.model_dump())

    assert document.document_id == DOCUMENT_ID


def test_rejects_invalid_document_id() -> None:
    with pytest.raises(ValidationError):
        DocumentIR(
            document_id="not-a-uuid",
            source=DocumentSource(file_name="not-a-uuid.pdf", file_extension="pdf"),
            content="",
            pages=[],
        )


def test_span_text_must_match_document_content_offsets() -> None:
    with pytest.raises(ValidationError, match="span text must match document content"):
        DocumentIR(
            document_id=DOCUMENT_ID,
            source=DocumentSource(file_name=f"{DOCUMENT_ID}.pdf", file_extension="pdf"),
            content="actual text",
            pages=[
                Page(
                    page_id=make_page_id(DOCUMENT_ID, 1),
                    page_number=1,
                    spans=[
                        TextSpan(
                            span_id=make_span_id(DOCUMENT_ID, 1, 0),
                            page_number=1,
                            text="wrong text",
                            char_start=0,
                            char_end=5,
                            reading_order=0,
                        )
                    ],
                )
            ],
        )


def test_span_page_number_must_match_containing_page() -> None:
    with pytest.raises(ValidationError, match="span page_number must match containing page"):
        Page(
            page_id=make_page_id(DOCUMENT_ID, 1),
            page_number=1,
            spans=[
                TextSpan(
                    span_id=make_span_id(DOCUMENT_ID, 2, 0),
                    page_number=2,
                    text="text",
                    char_start=0,
                    char_end=4,
                    reading_order=0,
                )
            ],
        )


def test_bounding_box_rejects_inverted_coordinates() -> None:
    with pytest.raises(ValidationError, match="x1 must be greater than or equal to x0"):
        BoundingBox(x0=10, y0=0, x1=5, y1=1)


def test_document_rejects_page_id_that_does_not_match_document_and_page() -> None:
    with pytest.raises(ValidationError, match="page_id must match document_id and page_number"):
        DocumentIR(
            document_id=DOCUMENT_ID,
            source=DocumentSource(file_name=f"{DOCUMENT_ID}.pdf", file_extension="pdf"),
            content="Alpha",
            pages=[
                Page(
                    page_id=make_page_id(DOCUMENT_ID, 2),
                    page_number=1,
                    spans=[
                        TextSpan(
                            span_id=make_span_id(DOCUMENT_ID, 1, 0),
                            page_number=1,
                            text="Alpha",
                            char_start=0,
                            char_end=5,
                            reading_order=0,
                        )
                    ],
                )
            ],
        )


def test_document_rejects_span_id_that_does_not_match_document_and_page() -> None:
    with pytest.raises(ValidationError, match="span_id must match document_id and span page_number"):
        DocumentIR(
            document_id=DOCUMENT_ID,
            source=DocumentSource(file_name=f"{DOCUMENT_ID}.pdf", file_extension="pdf"),
            content="Alpha",
            pages=[
                Page(
                    page_id=make_page_id(DOCUMENT_ID, 1),
                    page_number=1,
                    spans=[
                        TextSpan(
                            span_id=make_span_id(DOCUMENT_ID, 2, 0),
                            page_number=1,
                            text="Alpha",
                            char_start=0,
                            char_end=5,
                            reading_order=0,
                        )
                    ],
                )
            ],
        )


def test_file_extension_is_normalized() -> None:
    source = DocumentSource(file_name=f"{DOCUMENT_ID}.PDF", file_extension=".PDF")

    assert source.file_extension == "pdf"


def test_page_rejects_duplicate_reading_order() -> None:
    with pytest.raises(ValidationError, match="duplicate span reading_order on page"):
        Page(
            page_id=make_page_id(DOCUMENT_ID, 1),
            page_number=1,
            spans=[
                TextSpan(
                    span_id=make_span_id(DOCUMENT_ID, 1, 0),
                    page_number=1,
                    text="Alpha",
                    char_start=0,
                    char_end=5,
                    reading_order=0,
                ),
                TextSpan(
                    span_id=make_span_id(DOCUMENT_ID, 1, 1),
                    page_number=1,
                    text="Beta",
                    char_start=6,
                    char_end=10,
                    reading_order=0,
                ),
            ],
        )


def test_page_rejects_duplicate_span_id() -> None:
    duplicate_span_id = make_span_id(DOCUMENT_ID, 1, 0)

    with pytest.raises(ValidationError, match="duplicate span_id on page"):
        Page(
            page_id=make_page_id(DOCUMENT_ID, 1),
            page_number=1,
            spans=[
                TextSpan(
                    span_id=duplicate_span_id,
                    page_number=1,
                    text="Alpha",
                    char_start=0,
                    char_end=5,
                    reading_order=0,
                ),
                TextSpan(
                    span_id=duplicate_span_id,
                    page_number=1,
                    text="Beta",
                    char_start=6,
                    char_end=10,
                    reading_order=1,
                ),
            ],
        )


def test_document_rejects_duplicate_page_number() -> None:
    with pytest.raises(ValidationError, match="duplicate page_number"):
        DocumentIR(
            document_id=DOCUMENT_ID,
            source=DocumentSource(file_name=f"{DOCUMENT_ID}.pdf", file_extension="pdf"),
            content="Alpha\nBeta",
            pages=[
                Page(
                    page_id=make_page_id(DOCUMENT_ID, 1),
                    page_number=1,
                    spans=[
                        TextSpan(
                            span_id=make_span_id(DOCUMENT_ID, 1, 0),
                            page_number=1,
                            text="Alpha",
                            char_start=0,
                            char_end=5,
                            reading_order=0,
                        )
                    ],
                ),
                Page(
                    page_id=make_page_id(DOCUMENT_ID, 2),
                    page_number=1,
                    spans=[
                        TextSpan(
                            span_id=make_span_id(DOCUMENT_ID, 1, 1),
                            page_number=1,
                            text="Beta",
                            char_start=6,
                            char_end=10,
                            reading_order=0,
                        )
                    ],
                ),
            ],
        )


def test_document_rejects_duplicate_page_id() -> None:
    duplicate_page_id = make_page_id(DOCUMENT_ID, 1)

    with pytest.raises(ValidationError, match="duplicate page_id"):
        DocumentIR(
            document_id=DOCUMENT_ID,
            source=DocumentSource(file_name=f"{DOCUMENT_ID}.pdf", file_extension="pdf"),
            content="Alpha\nBeta",
            pages=[
                Page(
                    page_id=duplicate_page_id,
                    page_number=1,
                    spans=[
                        TextSpan(
                            span_id=make_span_id(DOCUMENT_ID, 1, 0),
                            page_number=1,
                            text="Alpha",
                            char_start=0,
                            char_end=5,
                            reading_order=0,
                        )
                    ],
                ),
                Page(
                    page_id=duplicate_page_id,
                    page_number=2,
                    spans=[
                        TextSpan(
                            span_id=make_span_id(DOCUMENT_ID, 2, 0),
                            page_number=2,
                            text="Beta",
                            char_start=6,
                            char_end=10,
                            reading_order=0,
                        )
                    ],
                ),
            ],
        )


def test_document_rejects_duplicate_span_id_across_pages() -> None:
    duplicate_span_id = make_span_id(DOCUMENT_ID, 1, 0)

    with pytest.raises(ValidationError, match="duplicate span_id in document"):
        DocumentIR(
            document_id=DOCUMENT_ID,
            source=DocumentSource(file_name=f"{DOCUMENT_ID}.pdf", file_extension="pdf"),
            content="Alpha\nBeta",
            pages=[
                Page(
                    page_id=make_page_id(DOCUMENT_ID, 1),
                    page_number=1,
                    spans=[
                        TextSpan(
                            span_id=duplicate_span_id,
                            page_number=1,
                            text="Alpha",
                            char_start=0,
                            char_end=5,
                            reading_order=0,
                        )
                    ],
                ),
                Page(
                    page_id=make_page_id(DOCUMENT_ID, 2),
                    page_number=2,
                    spans=[
                        TextSpan(
                            span_id=duplicate_span_id,
                            page_number=2,
                            text="Beta",
                            char_start=6,
                            char_end=10,
                            reading_order=0,
                        )
                    ],
                ),
            ],
        )
