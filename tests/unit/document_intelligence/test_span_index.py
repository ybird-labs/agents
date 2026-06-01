import pytest

from exeboard_ai.document_intelligence.core.ids import make_page_id, make_span_id
from exeboard_ai.document_intelligence.ir.models import DocumentIR, DocumentSource, Page, TextSpan
from exeboard_ai.document_intelligence.ir.span_index import SpanIndex

DOCUMENT_ID = "550e8400-e29b-41d4-a716-446655440000"


def _make_span(page_number: int, span_index: int, text: str, char_start: int) -> TextSpan:
    return TextSpan(
        span_id=make_span_id(DOCUMENT_ID, page_number, span_index),
        page_number=page_number,
        text=text,
        char_start=char_start,
        char_end=char_start + len(text),
        reading_order=span_index,
    )


def _make_document() -> DocumentIR:
    content = "Alpha\nBeta\nGamma"
    alpha_start = content.index("Alpha")
    beta_start = content.index("Beta")
    gamma_start = content.index("Gamma")

    return DocumentIR(
        document_id=DOCUMENT_ID,
        source=DocumentSource(file_name=f"{DOCUMENT_ID}.pdf", file_extension="pdf"),
        content=content,
        pages=[
            Page(
                page_id=make_page_id(DOCUMENT_ID, 1),
                page_number=1,
                spans=[
                    _make_span(1, 1, "Beta", beta_start),
                    _make_span(1, 0, "Alpha", alpha_start),
                ],
            ),
            Page(
                page_id=make_page_id(DOCUMENT_ID, 2),
                page_number=2,
                spans=[
                    _make_span(2, 0, "Gamma", gamma_start),
                ],
            ),
        ],
    )


def test_get_span_returns_span_by_id() -> None:
    index = SpanIndex(_make_document())
    span_id = make_span_id(DOCUMENT_ID, 1, 0)

    span = index.get_span(span_id)

    assert span.text == "Alpha"


def test_get_span_raises_key_error_for_unknown_id() -> None:
    index = SpanIndex(_make_document())

    with pytest.raises(KeyError, match="unknown span_id"):
        index.get_span("missing-span")


def test_has_span_checks_existence() -> None:
    index = SpanIndex(_make_document())

    assert index.has_span(make_span_id(DOCUMENT_ID, 1, 0)) is True
    assert index.has_span("missing-span") is False


def test_get_spans_returns_requested_spans() -> None:
    index = SpanIndex(_make_document())

    spans = index.get_spans(
        [
            make_span_id(DOCUMENT_ID, 1, 0),
            make_span_id(DOCUMENT_ID, 2, 0),
        ]
    )

    assert [span.text for span in spans] == ["Alpha", "Gamma"]


def test_get_page_spans_returns_spans_in_reading_order() -> None:
    index = SpanIndex(_make_document())

    spans = index.get_page_spans(1)

    assert [span.text for span in spans] == ["Alpha", "Beta"]


def test_get_page_text_joins_page_spans_in_reading_order() -> None:
    index = SpanIndex(_make_document())

    assert index.get_page_text(1) == "Alpha\nBeta"


def test_get_text_for_spans_returns_document_order_not_input_order() -> None:
    index = SpanIndex(_make_document())

    text = index.get_text_for_spans(
        [
            make_span_id(DOCUMENT_ID, 1, 1),
            make_span_id(DOCUMENT_ID, 1, 0),
        ]
    )

    assert text == "Alpha\nBeta"


def test_get_page_text_for_missing_page_returns_empty_string() -> None:
    index = SpanIndex(_make_document())

    assert index.get_page_text(99) == ""


def test_get_text_for_spans_orders_across_pages() -> None:
    index = SpanIndex(_make_document())

    text = index.get_text_for_spans(
        [
            make_span_id(DOCUMENT_ID, 2, 0),
            make_span_id(DOCUMENT_ID, 1, 0),
        ]
    )

    assert text == "Alpha\nGamma"
