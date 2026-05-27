from exeboard_ai.document_intelligence.chunking.models import Chunk
from exeboard_ai.document_intelligence.summarization.models import (
    DEFAULT_ALLOWED_CLAIM_ROLES_BY_DOCUMENT_TYPE,
    DocumentType,
)

CHUNK_SUMMARY_PROMPT_NAME = "chunk_summary"
CHUNK_SUMMARY_PROMPT_VERSION = "0.1"


def build_chunk_summary_prompt(
    *,
    chunk: Chunk,
    document_type: DocumentType,
) -> str:
    allowed_roles = sorted(DEFAULT_ALLOWED_CLAIM_ROLES_BY_DOCUMENT_TYPE[document_type])
    allowed_roles_text = ", ".join(allowed_roles)
    page_numbers_text = ", ".join(str(page_number) for page_number in chunk.page_numbers)
    source_span_ids_text = "\n".join(f"- {span_id}" for span_id in chunk.source_span_ids)

    return f"""Summarize the provided document chunk into evidence-backed claims.

Document ID: {chunk.document_id}
Chunk ID: {chunk.chunk_id}
Document type: {document_type}
Allowed claim roles: {allowed_roles_text}
Chunk page numbers: {page_numbers_text}
Allowed source span IDs:
{source_span_ids_text}

Rules:
- Use only the chunk text below.
- Return an empty claims list if there are no meaningful claims.
- Every claim must use one of the allowed claim roles.
- Every claim importance must be one of: low, medium, high.
- Every evidence quote must be an exact substring from the chunk text.
- Every evidence item must cite only the allowed source span IDs listed above.
- Do not invent page numbers, span IDs, chunk IDs, document IDs, claim IDs, or validation status.

Chunk text:
{chunk.text}
"""
