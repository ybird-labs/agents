from __future__ import annotations

from pathlib import Path

from exeboard_ai.document_intelligence.chunking.chunker import chunk_document
from exeboard_ai.document_intelligence.parsing.ports import DocumentParser
from exeboard_ai.document_intelligence.ir.span_index import SpanIndex
from exeboard_ai.document_intelligence.summarization.chunk_summarizer import summarize_chunk
from exeboard_ai.document_intelligence.summarization.final_summarizer import build_final_summary
from exeboard_ai.document_intelligence.summarization.models import DocumentSummary, DocumentType, SummaryClaim
from exeboard_ai.document_intelligence.summarization.ports import StructuredResponseGenerator
from exeboard_ai.document_intelligence.validation.aggregate_validator import apply_claim_grounding_validation


def summarize_document(
    pdf_path: Path,
    *,
    parser: DocumentParser,
    response_generator: StructuredResponseGenerator,
    document_type: DocumentType = "generic",
    target_chars: int = 2000,
    max_chars: int = 2500,
) -> DocumentSummary:
    document = parser.parse(pdf_path)
    span_index = SpanIndex(document)
    chunks = chunk_document(document, target_chars=target_chars, max_chars=max_chars)

    validated_claims: list[SummaryClaim] = []
    next_claim_index = 0
    for chunk in chunks:
        chunk_summary = summarize_chunk(
            chunk=chunk,
            document_type=document_type,
            generator=response_generator,
            span_index=span_index,
            first_claim_index=next_claim_index,
        )
        next_claim_index += len(chunk_summary.claims)
        validated_claims.extend(
            apply_claim_grounding_validation(claim=claim, span_index=span_index)
            for claim in chunk_summary.claims
        )

    return build_final_summary(
        document_id=document.document_id,
        document_type=document_type,
        claims=tuple(validated_claims),
    )
