from exeboard_ai.document_intelligence.core.ids import make_chunk_id, make_claim_id, make_page_id, make_span_id
from exeboard_ai.document_intelligence.ir.models import DocumentIR, DocumentSource, Page, TextSpan
from exeboard_ai.document_intelligence.ir.span_index import SpanIndex
from exeboard_ai.document_intelligence.summarization.models import ClaimEvidence, SummaryClaim
from exeboard_ai.document_intelligence.validation.aggregate_validator import (
    apply_claim_grounding_validation,
    validate_claim_grounding,
)

DOCUMENT_ID = "550e8400-e29b-41d4-a716-446655440000"


def _span_index(
    text: str = "Revenue increased.",
    second_text: str | None = None,
) -> SpanIndex:
    content = text if second_text is None else f"{text}\n{second_text}"
    spans = [
        TextSpan(
            span_id=make_span_id(DOCUMENT_ID, 1, 0),
            page_number=1,
            text=text,
            char_start=0,
            char_end=len(text),
            reading_order=0,
        )
    ]
    if second_text is not None:
        spans.append(
            TextSpan(
                span_id=make_span_id(DOCUMENT_ID, 1, 1),
                page_number=1,
                text=second_text,
                char_start=len(text) + 1,
                char_end=len(content),
                reading_order=1,
            )
        )
    return SpanIndex(
        DocumentIR(
            document_id=DOCUMENT_ID,
            source=DocumentSource(file_name=f"{DOCUMENT_ID}.pdf", file_extension="pdf"),
            content=content,
            pages=[
                Page(
                    page_id=make_page_id(DOCUMENT_ID, 1),
                    page_number=1,
                    spans=spans,
                )
            ],
        )
    )


def _claim(*, quote: str = "Revenue increased.", source_span_id: str | None = None) -> SummaryClaim:
    return SummaryClaim(
        claim_id=make_claim_id(DOCUMENT_ID, 0),
        document_id=DOCUMENT_ID,
        document_type="business_review",
        claim="Revenue increased.",
        claim_role="finding",
        importance="high",
        evidence=(
            ClaimEvidence(
                quote=quote,
                page_number=1,
                source_span_ids=(source_span_id or make_span_id(DOCUMENT_ID, 1, 0),),
                source_chunk_ids=(make_chunk_id(DOCUMENT_ID, 0),),
            ),
        ),
    )


def test_aggregate_validation_marks_claim_valid_only_when_citations_and_quotes_are_valid() -> None:
    claim = _claim()

    validated = apply_claim_grounding_validation(claim=claim, span_index=_span_index())

    assert validated.validation_status == "valid"
    assert validated.validation_errors == ()
    assert claim.validation_status == "unvalidated"


def test_aggregate_validation_keeps_claim_invalid_when_quote_validation_fails() -> None:
    validated = apply_claim_grounding_validation(
        claim=_claim(quote="Invented quote."),
        span_index=_span_index(),
    )

    assert validated.validation_status == "invalid"
    assert "quote_not_found" in validated.validation_errors


def test_aggregate_validation_keeps_claim_invalid_when_citation_validation_fails() -> None:
    validated = apply_claim_grounding_validation(
        claim=_claim(source_span_id=make_span_id(DOCUMENT_ID, 1, 99)),
        span_index=_span_index(),
    )

    assert validated.validation_status == "invalid"
    assert "invalid_span_id" in validated.validation_errors


def test_aggregate_validation_rejects_same_page_quote_outside_cited_span() -> None:
    validated = apply_claim_grounding_validation(
        claim=_claim(quote="Costs declined.", source_span_id=make_span_id(DOCUMENT_ID, 1, 0)),
        span_index=_span_index(text="Revenue increased.", second_text="Costs declined."),
    )

    assert validated.validation_status == "invalid"
    assert "quote_outside_cited_spans" in validated.validation_errors


def test_aggregate_result_exposes_separate_citation_and_quote_results() -> None:
    result = validate_claim_grounding(claim=_claim(), span_index=_span_index())

    assert result.valid is True
    assert result.citation_result.valid is True
    assert result.quote_result.valid is True
    assert result.errors == ()
