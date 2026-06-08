from exeboard_ai.document_intelligence.summarization.models import (
    DEFAULT_ALLOWED_CLAIM_ROLES_BY_DOCUMENT_TYPE,
    DocumentType,
)
from exeboard_ai.document_intelligence.summarization.span_context import SpanAddressedChunkContext

CHUNK_SUMMARY_PROMPT_NAME = "chunk_summary"
CHUNK_SUMMARY_PROMPT_VERSION = "0.2"


def build_chunk_summary_prompt(
    *,
    chunk_context: SpanAddressedChunkContext,
    document_type: DocumentType,
) -> str:
    allowed_roles = sorted(DEFAULT_ALLOWED_CLAIM_ROLES_BY_DOCUMENT_TYPE[document_type])
    allowed_roles_text = ", ".join(allowed_roles)
    page_numbers_text = ", ".join(
        str(page_number) for page_number in sorted({span.page_number for span in chunk_context.allowed_spans})
    )
    allowed_spans_text = "\n".join(
        f"- span_id: {span.span_id}\n  page_number: {span.page_number}\n  text: {span.text}"
        for span in chunk_context.allowed_spans
    )

    return f"""Summarize the provided document chunk into evidence-backed claims.

Document ID: {chunk_context.document_id}
Chunk ID: {chunk_context.chunk_id}
Document type: {document_type}
Allowed claim roles: {allowed_roles_text}
Chunk page numbers: {page_numbers_text}
Allowed evidence spans:
{allowed_spans_text}

Rules:
- Use only the chunk text and allowed evidence spans below.
- Return an empty claims list if there are no meaningful claims.
- Every claim must use one of the allowed claim roles.
- Every claim importance must be one of: low, medium, high.
- Every evidence quote must be an exact substring of at least one cited allowed TextSpan text.
- Every evidence item must cite only the allowed source span IDs listed above.
- Return only claim text, role, importance, quote, and source span IDs; trusted code derives page numbers.
- Do not invent page numbers, span IDs, chunk IDs, document IDs, claim IDs, source chunk IDs, lineage, or validation status.

Chunk text:
{chunk_context.chunk_text}
"""
