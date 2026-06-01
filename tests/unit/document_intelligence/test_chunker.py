import pytest
from pydantic import ValidationError

from exeboard_ai.document_intelligence.chunking.chunker import chunk_document
from exeboard_ai.document_intelligence.chunking.models import Chunk
from exeboard_ai.document_intelligence.core.ids import make_chunk_id, make_page_id, make_span_id
from exeboard_ai.document_intelligence.ir.models import DocumentIR, DocumentSource, Page, TextSpan
from exeboard_ai.document_intelligence.ir.span_index import SpanIndex

DOCUMENT_ID = "550e8400-e29b-41d4-a716-446655440000"
OTHER_DOCUMENT_ID = "650e8400-e29b-41d4-a716-446655440000"


def _span(page_number: int, span_index: int, text: str, char_start: int) -> TextSpan:
    return TextSpan(
        span_id=make_span_id(DOCUMENT_ID, page_number, span_index),
        page_number=page_number,
        text=text,
        char_start=char_start,
        char_end=char_start + len(text),
        reading_order=span_index,
    )


def _document_with_texts(page_texts: list[list[str]]) -> DocumentIR:
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
            spans.append(_span(page_number, span_index, text, char_start))

        pages.append(
            Page(
                page_id=make_page_id(DOCUMENT_ID, page_number),
                page_number=page_number,
                spans=spans,
            )
        )

    return DocumentIR(
        document_id=DOCUMENT_ID,
        source=DocumentSource(file_name=f"{DOCUMENT_ID}.pdf", file_extension="pdf"),
        content="".join(content_parts),
        pages=pages,
    )


def test_chunk_model_serializes_with_provenance() -> None:
    chunk = Chunk(
        chunk_id=make_chunk_id(DOCUMENT_ID, 0),
        document_id=DOCUMENT_ID,
        text="Alpha",
        page_numbers=(1,),
        source_span_ids=(make_span_id(DOCUMENT_ID, 1, 0),)
    )

    data = chunk.model_dump()

    assert data["chunk_id"] == make_chunk_id(DOCUMENT_ID, 0)
    assert data["document_id"] == DOCUMENT_ID
    assert data["chunk_type"] == "text"
    assert data["source_span_ids"] == (make_span_id(DOCUMENT_ID, 1, 0),)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("text", "", "must not be empty"),
        ("page_numbers", [], "page_numbers must not be empty"),
        ("page_numbers", [1, 1], "page_numbers must be unique"),
        ("page_numbers", [0], "page_numbers must be positive"),
        ("source_span_ids", [], "source_span_ids must not be empty"),
        (
            "source_span_ids",
            [make_span_id(DOCUMENT_ID, 1, 0), make_span_id(DOCUMENT_ID, 1, 0)],
            "source_span_ids must be unique",
        ),
        ("source_span_ids", [""], "source_span_ids must not contain empty values"),
    ],
)
def test_chunk_model_rejects_invalid_provenance_fields(
    field: str,
    value: object,
    message: str,
) -> None:
    kwargs = {
        "chunk_id": make_chunk_id(DOCUMENT_ID, 0),
        "document_id": DOCUMENT_ID,
        "text": "Alpha",
        "page_numbers": [1],
        "source_span_ids": [make_span_id(DOCUMENT_ID, 1, 0)],
    }
    kwargs[field] = value

    with pytest.raises(ValidationError, match=message):
        Chunk(**kwargs)


def test_chunk_model_rejects_invalid_document_id() -> None:
    with pytest.raises(ValidationError, match="document_id must be a valid UUID"):
        Chunk(
            chunk_id="not-a-uuid:c0000",
            document_id="not-a-uuid",
            text="Alpha",
            page_numbers=(1,),
            source_span_ids=("span-1",)
        )


def test_chunk_model_rejects_chunk_id_from_another_document() -> None:
    with pytest.raises(ValidationError, match="chunk_id must belong to document_id"):
        Chunk(
            chunk_id=make_chunk_id(OTHER_DOCUMENT_ID, 0),
            document_id=DOCUMENT_ID,
            text="Alpha",
            page_numbers=(1,),
            source_span_ids=(make_span_id(DOCUMENT_ID, 1, 0),)
        )


@pytest.mark.parametrize("chunk_id", [f"{DOCUMENT_ID}:cBAD", f"{DOCUMENT_ID}:c1", f"{DOCUMENT_ID}:c00001"])
def test_chunk_model_rejects_malformed_chunk_id_suffix(chunk_id: str) -> None:
    with pytest.raises(ValidationError, match="chunk_id must be in format"):
        Chunk(
            chunk_id=chunk_id,
            document_id=DOCUMENT_ID,
            text="Alpha",
            page_numbers=(1,),
            source_span_ids=(make_span_id(DOCUMENT_ID, 1, 0),)
        )


def test_chunk_model_accepts_large_generated_chunk_id() -> None:
    chunk = Chunk(
        chunk_id=make_chunk_id(DOCUMENT_ID, 10000),
        document_id=DOCUMENT_ID,
        text="Alpha",
        page_numbers=(1,),
        source_span_ids=(make_span_id(DOCUMENT_ID, 1, 0),)
    )

    assert chunk.chunk_id == f"{DOCUMENT_ID}:c10000"


def test_chunk_model_rejects_source_span_id_from_another_document() -> None:
    with pytest.raises(ValidationError, match="source_span_ids must belong to document_id"):
        Chunk(
            chunk_id=make_chunk_id(DOCUMENT_ID, 0),
            document_id=DOCUMENT_ID,
            text="Alpha",
            page_numbers=(1,),
            source_span_ids=(make_span_id(OTHER_DOCUMENT_ID, 1, 0),)
        )


def test_chunk_model_rejects_page_numbers_that_do_not_match_source_spans() -> None:
    with pytest.raises(ValidationError, match="page_numbers must match source_span_ids"):
        Chunk(
            chunk_id=make_chunk_id(DOCUMENT_ID, 0),
            document_id=DOCUMENT_ID,
            text="Alpha",
            page_numbers=(2,),
            source_span_ids=(make_span_id(DOCUMENT_ID, 1, 0),)
        )


def test_chunk_document_groups_spans_in_document_order() -> None:
    document = _document_with_texts([["Alpha", "Beta", "Gamma"]])

    chunks = chunk_document(document, target_chars=10, max_chars=20)

    assert [chunk.chunk_id for chunk in chunks] == [
        make_chunk_id(DOCUMENT_ID, 0),
        make_chunk_id(DOCUMENT_ID, 1),
    ]
    assert [chunk.text for chunk in chunks] == ["Alpha\nBeta", "Gamma"]
    assert [chunk.source_span_ids for chunk in chunks] == [
        (make_span_id(DOCUMENT_ID, 1, 0), make_span_id(DOCUMENT_ID, 1, 1)),
        (make_span_id(DOCUMENT_ID, 1, 2),),
    ]


def test_chunk_document_chunk_text_matches_span_index_reconstruction() -> None:
    document = _document_with_texts([["Alpha", "Beta"], ["Gamma"]])
    index = SpanIndex(document)

    chunks = chunk_document(document, target_chars=100, max_chars=120)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.text == index.get_text_for_spans(chunk.source_span_ids)
    assert chunk.page_numbers == (1, 2)
    assert all(index.has_span(span_id) for span_id in chunk.source_span_ids)


def test_chunk_document_sorts_unsorted_pages_and_spans() -> None:
    content = "Alpha\nBeta\nGamma"
    alpha_start = content.index("Alpha")
    beta_start = content.index("Beta")
    gamma_start = content.index("Gamma")

    document = DocumentIR(
        document_id=DOCUMENT_ID,
        source=DocumentSource(file_name=f"{DOCUMENT_ID}.pdf", file_extension="pdf"),
        content=content,
        pages=[
            Page(
                page_id=make_page_id(DOCUMENT_ID, 2),
                page_number=2,
                spans=[_span(2, 0, "Gamma", gamma_start)],
            ),
            Page(
                page_id=make_page_id(DOCUMENT_ID, 1),
                page_number=1,
                spans=[
                    _span(1, 1, "Beta", beta_start),
                    _span(1, 0, "Alpha", alpha_start),
                ],
            ),
        ],
    )

    chunks = chunk_document(document, target_chars=100, max_chars=120)

    assert chunks[0].text == "Alpha\nBeta\nGamma"
    assert chunks[0].source_span_ids == (
        make_span_id(DOCUMENT_ID, 1, 0),
        make_span_id(DOCUMENT_ID, 1, 1),
        make_span_id(DOCUMENT_ID, 2, 0),
    )


def test_chunk_document_counts_newline_separators_against_target() -> None:
    document = _document_with_texts([["12345", "67890"]])

    same_chunk = chunk_document(document, target_chars=11, max_chars=20)
    split_chunks = chunk_document(document, target_chars=10, max_chars=20)

    assert [chunk.text for chunk in same_chunk] == ["12345\n67890"]
    assert [chunk.text for chunk in split_chunks] == ["12345", "67890"]


def test_chunk_document_rejects_single_span_over_max_chars() -> None:
    document = _document_with_texts([["A" * 30, "Beta"]])

    with pytest.raises(ValueError, match="exceeds max_chars"):
        chunk_document(document, target_chars=10, max_chars=20)


def test_chunk_document_skips_empty_spans() -> None:
    document = DocumentIR(
        document_id=DOCUMENT_ID,
        source=DocumentSource(file_name=f"{DOCUMENT_ID}.pdf", file_extension="pdf"),
        content="Alpha",
        pages=[
            Page(
                page_id=make_page_id(DOCUMENT_ID, 1),
                page_number=1,
                spans=[
                    _span(1, 0, "", 0),
                    _span(1, 1, "Alpha", 0),
                ],
            )
        ],
    )

    chunks = chunk_document(document)

    assert len(chunks) == 1
    assert chunks[0].text == "Alpha"
    assert chunks[0].source_span_ids == (make_span_id(DOCUMENT_ID, 1, 1),)


def test_chunk_document_returns_empty_list_for_empty_document() -> None:
    document = _document_with_texts([])

    assert chunk_document(document) == []


@pytest.mark.parametrize(
    ("target_chars", "max_chars", "message"),
    [
        (0, 10, "target_chars must be greater than 0"),
        (10, 0, "max_chars must be greater than 0"),
        (11, 10, "target_chars must be less than or equal to max_chars"),
    ],
)
def test_chunk_document_rejects_invalid_limits(
    target_chars: int,
    max_chars: int,
    message: str,
) -> None:
    document = _document_with_texts([["Alpha"]])

    with pytest.raises(ValueError, match=message):
        chunk_document(document, target_chars=target_chars, max_chars=max_chars)
