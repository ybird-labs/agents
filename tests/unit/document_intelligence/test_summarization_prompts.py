from exeboard_ai.document_intelligence.chunking.models import Chunk
from exeboard_ai.document_intelligence.core.ids import make_chunk_id, make_page_id, make_span_id
from exeboard_ai.document_intelligence.ir.models import DocumentIR, DocumentSource, Page, TextSpan
from exeboard_ai.document_intelligence.ir.span_index import SpanIndex
from exeboard_ai.document_intelligence.summarization.prompts import build_chunk_summary_prompt
from exeboard_ai.document_intelligence.summarization.span_context import (
    SpanAddressedChunkContext,
    build_span_addressed_chunk_context,
)

DOCUMENT_ID = "550e8400-e29b-41d4-a716-446655440000"


def _span_index() -> SpanIndex:
    first_text = "Revenue increased by 10%."
    second_text = "Costs declined."
    content = f"{first_text}\n{second_text}"
    return SpanIndex(
        DocumentIR(
            document_id=DOCUMENT_ID,
            source=DocumentSource(file_name=f"{DOCUMENT_ID}.pdf", file_extension="pdf"),
            content=content,
            pages=[
                Page(
                    page_id=make_page_id(DOCUMENT_ID, 1),
                    page_number=1,
                    spans=[
                        TextSpan(
                            span_id=make_span_id(DOCUMENT_ID, 1, 0),
                            page_number=1,
                            text=first_text,
                            char_start=0,
                            char_end=len(first_text),
                            reading_order=0,
                        ),
                        TextSpan(
                            span_id=make_span_id(DOCUMENT_ID, 1, 1),
                            page_number=1,
                            text=second_text,
                            char_start=len(first_text) + 1,
                            char_end=len(content),
                            reading_order=1,
                        ),
                    ],
                )
            ],
        )
    )


def _chunk() -> Chunk:
    return Chunk(
        chunk_id=make_chunk_id(DOCUMENT_ID, 0),
        document_id=DOCUMENT_ID,
        text="Revenue increased by 10%.",
        page_numbers=(1,),
        source_span_ids=(make_span_id(DOCUMENT_ID, 1, 0),),
    )


def _chunk_context() -> SpanAddressedChunkContext:
    return build_span_addressed_chunk_context(chunk=_chunk(), span_index=_span_index())


def test_chunk_summary_prompt_includes_chunk_context_and_span_addressed_source_constraints() -> None:
    chunk_context = build_span_addressed_chunk_context(chunk=_chunk(), span_index=_span_index())

    prompt = build_chunk_summary_prompt(chunk_context=chunk_context, document_type="business_review")

    assert f"Document ID: {DOCUMENT_ID}" in prompt
    assert f"Chunk ID: {make_chunk_id(DOCUMENT_ID, 0)}" in prompt
    assert "Document type: business_review" in prompt
    assert "Chunk page numbers: 1" in prompt
    assert "Allowed evidence spans:" in prompt
    assert f"span_id: {make_span_id(DOCUMENT_ID, 1, 0)}" in prompt
    assert "page_number: 1" in prompt
    assert "text: Revenue increased by 10%." in prompt
    assert "Costs declined." not in prompt
    assert "Revenue increased by 10%." in prompt
    assert "cite only the allowed source span IDs" in prompt
    assert "exact substring of at least one cited allowed TextSpan text" in prompt
    assert "trusted code derives page numbers" in prompt
    assert "low, medium, high" in prompt
    assert "Return an empty claims list if there are no meaningful claims" in prompt


def test_chunk_summary_prompt_preserves_exact_span_text_whitespace() -> None:
    span_text = "  Revenue increased by 10%.  "
    document = DocumentIR(
        document_id=DOCUMENT_ID,
        source=DocumentSource(file_name=f"{DOCUMENT_ID}.pdf", file_extension="pdf"),
        content=span_text,
        pages=[
            Page(
                page_id=make_page_id(DOCUMENT_ID, 1),
                page_number=1,
                spans=[
                    TextSpan(
                        span_id=make_span_id(DOCUMENT_ID, 1, 0),
                        page_number=1,
                        text=span_text,
                        char_start=0,
                        char_end=len(span_text),
                        reading_order=0,
                    )
                ],
            )
        ],
    )
    chunk = Chunk(
        chunk_id=make_chunk_id(DOCUMENT_ID, 0),
        document_id=DOCUMENT_ID,
        text=span_text,
        page_numbers=(1,),
        source_span_ids=(make_span_id(DOCUMENT_ID, 1, 0),),
    )

    prompt = build_chunk_summary_prompt(
        chunk_context=build_span_addressed_chunk_context(chunk=chunk, span_index=SpanIndex(document)),
        document_type="business_review",
    )

    assert f"text: {span_text}" in prompt
    assert f"Chunk text:\n{span_text}" in prompt


def test_chunk_summary_prompt_includes_document_type_allowed_roles() -> None:
    prompt = build_chunk_summary_prompt(chunk_context=_chunk_context(), document_type="contract")

    assert "Allowed claim roles:" in prompt
    assert "obligation" in prompt
    assert "entitlement" in prompt
    assert "prohibition" in prompt
