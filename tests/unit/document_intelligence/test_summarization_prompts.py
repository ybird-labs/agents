from exeboard_ai.document_intelligence.chunking.models import Chunk
from exeboard_ai.document_intelligence.core.ids import make_chunk_id, make_span_id
from exeboard_ai.document_intelligence.summarization.prompts import build_chunk_summary_prompt

DOCUMENT_ID = "550e8400-e29b-41d4-a716-446655440000"


def _chunk() -> Chunk:
    return Chunk(
        chunk_id=make_chunk_id(DOCUMENT_ID, 0),
        document_id=DOCUMENT_ID,
        text="Revenue increased by 10%.",
        page_numbers=(1,),
        source_span_ids=(make_span_id(DOCUMENT_ID, 1, 0),),
    )


def test_chunk_summary_prompt_includes_chunk_context_and_source_constraints() -> None:
    chunk = _chunk()

    prompt = build_chunk_summary_prompt(chunk=chunk, document_type="business_review")

    assert f"Document ID: {DOCUMENT_ID}" in prompt
    assert f"Chunk ID: {make_chunk_id(DOCUMENT_ID, 0)}" in prompt
    assert "Document type: business_review" in prompt
    assert "Chunk page numbers: 1" in prompt
    assert make_span_id(DOCUMENT_ID, 1, 0) in prompt
    assert "Revenue increased by 10%." in prompt
    assert "cite only the allowed source span IDs" in prompt
    assert "exact substring from the chunk text" in prompt
    assert "low, medium, high" in prompt
    assert "Return an empty claims list if there are no meaningful claims" in prompt


def test_chunk_summary_prompt_includes_document_type_allowed_roles() -> None:
    prompt = build_chunk_summary_prompt(chunk=_chunk(), document_type="contract")

    assert "Allowed claim roles:" in prompt
    assert "obligation" in prompt
    assert "entitlement" in prompt
    assert "prohibition" in prompt
