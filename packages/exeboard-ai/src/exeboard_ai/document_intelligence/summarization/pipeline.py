from __future__ import annotations

from pathlib import Path

from exeboard_ai.document_intelligence.chunking.chunker import chunk_document
from exeboard_ai.document_intelligence.parsing.ports import DocumentParser
from exeboard_ai.document_intelligence.ir.span_index import SpanIndex
from exeboard_ai.document_intelligence.ir.models import DocumentIR
from exeboard_ai.document_intelligence.summarization.chunk_summarizer import summarize_chunk_run
from exeboard_ai.document_intelligence.summarization.final_summarizer import build_final_summary
from exeboard_ai.document_intelligence.summarization.models import (
    DocumentSummary,
    DocumentType,
    DroppedClaimRecord,
    GroundingRunReport,
    SummarizationRunResult,
    SummaryClaim,
)
from exeboard_ai.document_intelligence.summarization.ports import StructuredResponseGenerator
from exeboard_ai.document_intelligence.validation.aggregate_validator import validate_claim_grounding


def summarize_document(
    pdf_path: Path,
    *,
    parser: DocumentParser,
    response_generator: StructuredResponseGenerator,
    document_type: DocumentType = "generic",
    target_chars: int = 2000,
    max_chars: int = 2500,
) -> DocumentSummary:
    result = summarize_document_run(
        pdf_path,
        parser=parser,
        response_generator=response_generator,
        document_type=document_type,
        target_chars=target_chars,
        max_chars=max_chars,
    )
    if result.summary is None:
        raise ValueError("final summary requires at least one valid claim")
    return result.summary


def summarize_document_run(
    pdf_path: Path,
    *,
    parser: DocumentParser,
    response_generator: StructuredResponseGenerator,
    document_type: DocumentType = "generic",
    target_chars: int = 2000,
    max_chars: int = 2500,
) -> SummarizationRunResult:
    document = parser.parse(pdf_path)
    span_index = SpanIndex(document)
    chunks = chunk_document(document, target_chars=target_chars, max_chars=max_chars)

    validated_claims: list[SummaryClaim] = []
    drops: list[DroppedClaimRecord] = []
    claims_proposed = 0
    evidence_proposed = 0
    claims_assembled = 0
    next_claim_index = 0
    for chunk in chunks:
        chunk_run = summarize_chunk_run(
            chunk=chunk,
            document_type=document_type,
            generator=response_generator,
            span_index=span_index,
            first_claim_index=next_claim_index,
        )
        chunk_summary = chunk_run.summary
        claims_proposed += chunk_run.report.claims_proposed
        evidence_proposed += chunk_run.report.evidence_proposed
        claims_assembled += len(chunk_summary.claims)
        drops.extend(chunk_run.report.drops)
        next_claim_index += len(chunk_summary.claims)

        for claim in chunk_summary.claims:
            validation_result = validate_claim_grounding(claim=claim, span_index=span_index)
            if validation_result.valid:
                validated_claims.append(
                    claim.model_copy(update={"validation_status": "valid", "validation_errors": ()})
                )
                continue

            error_codes = validation_result.errors
            stage = "citation_validation" if not validation_result.citation_result.valid else "quote_validation"
            drops.append(
                DroppedClaimRecord(
                    stage=stage,
                    error_codes=error_codes,
                    chunk_id=chunk.chunk_id,
                    claim_id=claim.claim_id,
                )
            )

    report = GroundingRunReport(
        claims_proposed=claims_proposed,
        evidence_proposed=evidence_proposed,
        claims_assembled=claims_assembled,
        claims_valid=len(validated_claims),
        drops=tuple(drops),
        parser_counters=_parser_counters(document),
    )
    if not validated_claims:
        return SummarizationRunResult(summary=None, report=report, status="zero_valid_claims")

    summary = build_final_summary(
        document_id=document.document_id,
        document_type=document_type,
        claims=tuple(validated_claims),
    )
    return SummarizationRunResult(summary=summary, report=report, status="completed")


def _parser_counters(document: DocumentIR) -> dict[str, int]:
    return {
        "page_count": len(document.pages),
        "span_count": sum(len(page.spans) for page in document.pages),
        "textless_page_count": sum(1 for page in document.pages if not page.spans),
        "parser_warning_count": sum(len(parser_run.warnings) for parser_run in document.parser_runs),
    }
