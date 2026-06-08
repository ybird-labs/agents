import pytest
from pydantic import ValidationError

from exeboard_ai.document_intelligence.core.ids import make_chunk_id, make_span_id
from exeboard_ai.document_intelligence.summarization.span_context import (
    AllowedEvidenceSpan,
    SpanAddressedChunkContext,
)

DOCUMENT_ID = "550e8400-e29b-41d4-a716-446655440000"


def _allowed_span(**overrides: object) -> AllowedEvidenceSpan:
    values = {
        "span_id": make_span_id(DOCUMENT_ID, 1, 0),
        "page_number": 1,
        "text": "Revenue increased by 10%.",
    }
    values.update(overrides)
    return AllowedEvidenceSpan.model_validate(values)


def _chunk_context(**overrides: object) -> SpanAddressedChunkContext:
    values = {
        "document_id": DOCUMENT_ID,
        "chunk_id": make_chunk_id(DOCUMENT_ID, 0),
        "chunk_text": "Revenue increased by 10%.",
        "allowed_spans": (_allowed_span(),),
    }
    values.update(overrides)
    return SpanAddressedChunkContext.model_validate(values)


@pytest.mark.parametrize("field_name", ["span_id", "text"])
def test_allowed_evidence_span_rejects_whitespace_only_required_strings(field_name: str) -> None:
    with pytest.raises(ValidationError, match="must not be empty"):
        _allowed_span(**{field_name: " \t\n "})


def test_allowed_evidence_span_preserves_nonblank_whitespace() -> None:
    span = _allowed_span(span_id=" span-1 ", text=" Revenue increased by 10%. ")

    assert span.span_id == " span-1 "
    assert span.text == " Revenue increased by 10%. "


@pytest.mark.parametrize("field_name", ["chunk_id", "chunk_text"])
def test_span_addressed_chunk_context_rejects_whitespace_only_required_strings(field_name: str) -> None:
    with pytest.raises(ValidationError, match="must not be empty"):
        _chunk_context(**{field_name: " \t\n "})


def test_span_addressed_chunk_context_preserves_nonblank_whitespace() -> None:
    context = _chunk_context(chunk_id=" chunk-1 ", chunk_text=" Revenue increased by 10%. ")

    assert context.chunk_id == " chunk-1 "
    assert context.chunk_text == " Revenue increased by 10%. "
