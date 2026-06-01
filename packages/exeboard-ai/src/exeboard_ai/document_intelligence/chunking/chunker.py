from exeboard_ai.document_intelligence.core.ids import make_chunk_id
from exeboard_ai.document_intelligence.chunking.models import Chunk
from exeboard_ai.document_intelligence.ir.models import DocumentIR, TextSpan
from exeboard_ai.document_intelligence.ir.span_index import SpanIndex


def chunk_document(
    document: DocumentIR,
    *,
    target_chars: int = 2000,
    max_chars: int = 2500,
) -> list[Chunk]:
    _validate_chunk_limits(target_chars=target_chars, max_chars=max_chars)

    index = SpanIndex(document)
    spans = _get_non_empty_spans_in_document_order(document)
    chunks: list[Chunk] = []
    current_spans: list[TextSpan] = []

    for span in spans:
        if len(span.text) > max_chars:
            raise ValueError(
                f"span {span.span_id!r} exceeds max_chars ({len(span.text)} > {max_chars})"
            )

        if current_spans and _projected_text_length(current_spans, span) > target_chars:
            chunks.append(_make_chunk(document, index, len(chunks), current_spans))
            current_spans = []

        current_spans.append(span)

        if _joined_text_length(current_spans) >= max_chars:
            chunks.append(_make_chunk(document, index, len(chunks), current_spans))
            current_spans = []

    if current_spans:
        chunks.append(_make_chunk(document, index, len(chunks), current_spans))

    return chunks


def _validate_chunk_limits(*, target_chars: int, max_chars: int) -> None:
    if target_chars <= 0:
        raise ValueError("target_chars must be greater than 0")
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than 0")
    if target_chars > max_chars:
        raise ValueError("target_chars must be less than or equal to max_chars")


def _get_non_empty_spans_in_document_order(document: DocumentIR) -> list[TextSpan]:
    spans = [span for page in document.pages for span in page.spans if span.text]
    return sorted(spans, key=lambda span: (span.page_number, span.reading_order))


def _projected_text_length(current_spans: list[TextSpan], next_span: TextSpan) -> int:
    return _joined_text_length(current_spans) + 1 + len(next_span.text)


def _joined_text_length(spans: list[TextSpan]) -> int:
    if not spans:
        return 0
    return sum(len(span.text) for span in spans) + len(spans) - 1


def _make_chunk(
    document: DocumentIR,
    index: SpanIndex,
    chunk_index: int,
    spans: list[TextSpan],
) -> Chunk:
    source_span_ids = tuple(span.span_id for span in spans)
    page_numbers = tuple(sorted({span.page_number for span in spans}))

    return Chunk(
        chunk_id=make_chunk_id(document.document_id, chunk_index),
        document_id=document.document_id,
        text=index.get_text_for_spans(source_span_ids),
        page_numbers=page_numbers,
        source_span_ids=source_span_ids,
    )
