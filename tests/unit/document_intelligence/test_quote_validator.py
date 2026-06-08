import pytest
from pydantic import ValidationError

from exeboard_ai.document_intelligence.core.ids import make_chunk_id, make_claim_id, make_page_id, make_span_id
from exeboard_ai.document_intelligence.ir.models import DocumentIR, DocumentSource, Page, TextSpan
from exeboard_ai.document_intelligence.ir.span_index import SpanIndex
from exeboard_ai.document_intelligence.summarization.models import ClaimEvidence, SummaryClaim
from exeboard_ai.document_intelligence.validation.quote_validator import (
    QuoteValidationError,
    QuoteValidationResult,
    validate_claim_quotes,
)

DOCUMENT_ID = "550e8400-e29b-41d4-a716-446655440000"
OTHER_DOCUMENT_ID = "650e8400-e29b-41d4-a716-446655440000"


def _span_index(*, document_id: str = DOCUMENT_ID, first_text: str = "Revenue increased by 10%.", second_text: str = "Costs declined.") -> SpanIndex:
    content = f"{first_text}\n{second_text}"
    first_span = TextSpan(
        span_id=make_span_id(document_id, 1, 0),
        page_number=1,
        text=first_text,
        char_start=0,
        char_end=len(first_text),
        reading_order=0,
    )
    second_span = TextSpan(
        span_id=make_span_id(document_id, 1, 1),
        page_number=1,
        text=second_text,
        char_start=len(first_text) + 1,
        char_end=len(content),
        reading_order=1,
    )
    return SpanIndex(
        DocumentIR(
            document_id=document_id,
            source=DocumentSource(file_name=f"{document_id}.pdf", file_extension="pdf"),
            content=content,
            pages=[
                Page(
                    page_id=make_page_id(document_id, 1),
                    page_number=1,
                    spans=[first_span, second_span],
                )
            ],
        )
    )


def _claim(*, quote: str = "Revenue increased by 10%.", span_index: int = 0, document_id: str = DOCUMENT_ID) -> SummaryClaim:
    return SummaryClaim(
        claim_id=make_claim_id(document_id, 0),
        document_id=document_id,
        document_type="business_review",
        claim="Revenue increased by 10%.",
        claim_role="finding",
        importance="high",
        evidence=(
            ClaimEvidence(
                quote=quote,
                page_number=1,
                source_span_ids=(make_span_id(document_id, 1, span_index),),
                source_chunk_ids=(make_chunk_id(document_id, 0),),
            ),
        ),
    )


def test_exact_quote_in_cited_span_is_valid() -> None:
    result = validate_claim_quotes(claim=_claim(), span_index=_span_index())

    assert result.valid is True
    assert result.claim_id == make_claim_id(DOCUMENT_ID, 0)
    assert result.document_id == DOCUMENT_ID
    assert result.errors == ()
    assert result.matches[0].match_type == "exact"
    assert result.matches[0].scope == "cited_spans"


def test_exact_quote_match_preserves_source_whitespace() -> None:
    quote = " Revenue increased by 10%. "
    result = validate_claim_quotes(
        claim=_claim(quote=quote),
        span_index=_span_index(first_text=quote),
    )

    assert result.valid is True
    assert result.matches[0].quote == quote


def test_exact_quote_on_cited_page_is_invalid_when_outside_cited_span() -> None:
    result = validate_claim_quotes(
        claim=_claim(quote="Costs declined.", span_index=0),
        span_index=_span_index(),
    )

    assert result.valid is False
    assert result.errors[0].code == "quote_outside_cited_spans"
    assert result.matches[0].match_type == "exact"
    assert result.matches[0].scope == "page"


def test_quote_validator_is_invalid_when_any_cited_span_is_missing() -> None:
    claim = SummaryClaim(
        claim_id=make_claim_id(DOCUMENT_ID, 0),
        document_id=DOCUMENT_ID,
        document_type="business_review",
        claim="Revenue increased by 10%.",
        claim_role="finding",
        importance="high",
        evidence=(
            ClaimEvidence(
                quote="Revenue increased by 10%.",
                page_number=1,
                source_span_ids=(
                    make_span_id(DOCUMENT_ID, 1, 0),
                    make_span_id(DOCUMENT_ID, 1, 99),
                ),
                source_chunk_ids=(make_chunk_id(DOCUMENT_ID, 0),),
            ),
        ),
    )

    result = validate_claim_quotes(claim=claim, span_index=_span_index())

    assert result.valid is False
    assert result.errors[0].code == "invalid_span_id"
    assert result.errors[0].source_span_id == make_span_id(DOCUMENT_ID, 1, 99)


def test_quote_crossing_cited_span_boundary_is_invalid() -> None:
    claim = SummaryClaim(
        claim_id=make_claim_id(DOCUMENT_ID, 0),
        document_id=DOCUMENT_ID,
        document_type="business_review",
        claim="Revenue increased and costs declined.",
        claim_role="finding",
        importance="high",
        evidence=(
            ClaimEvidence(
                quote="increased by 10%.\nCosts",
                page_number=1,
                source_span_ids=(
                    make_span_id(DOCUMENT_ID, 1, 0),
                    make_span_id(DOCUMENT_ID, 1, 1),
                ),
                source_chunk_ids=(make_chunk_id(DOCUMENT_ID, 0),),
            ),
        ),
    )

    result = validate_claim_quotes(claim=claim, span_index=_span_index())

    assert result.valid is False
    assert result.errors[0].code == "quote_outside_cited_spans"
    assert result.matches[0].match_type == "exact"
    assert result.matches[0].scope == "page"


def test_missing_quote_is_invalid() -> None:
    result = validate_claim_quotes(claim=_claim(quote="Invented quote."), span_index=_span_index())

    assert result.valid is False
    assert result.errors[0].code == "quote_not_found"
    assert result.errors[0].evidence_index == 0


def test_missing_quote_error_preserves_source_whitespace() -> None:
    quote = " Invented quote. "
    result = validate_claim_quotes(claim=_claim(quote=quote), span_index=_span_index())

    assert result.valid is False
    assert result.errors[0].quote == quote


def test_normalized_whitespace_match_is_classified_but_not_valid() -> None:
    result = validate_claim_quotes(
        claim=_claim(quote="Revenue increased by 10%."),
        span_index=_span_index(first_text="Revenue   increased\nby 10%."),
    )

    assert result.valid is False
    assert result.errors[0].code == "normalized_match_only"
    assert result.matches[0].match_type == "normalized"


def test_fuzzy_match_is_classified_but_not_valid() -> None:
    result = validate_claim_quotes(
        claim=_claim(quote="Revenue increased by 10%."),
        span_index=_span_index(first_text="Revenue increased about 10%."),
    )

    assert result.valid is False
    assert result.errors[0].code == "fuzzy_match"
    assert result.matches[0].match_type == "fuzzy"


def test_quote_validator_does_not_mutate_claim_validation_status() -> None:
    claim = _claim()

    result = validate_claim_quotes(claim=claim, span_index=_span_index())

    assert result.valid is True
    assert claim.validation_status == "unvalidated"
    assert claim.validation_errors == ()


def test_quote_validation_error_rejects_whitespace_only_source_span_id() -> None:
    with pytest.raises(ValidationError, match="source_span_id must not be empty"):
        QuoteValidationError(
            code="invalid_span_id",
            message="Missing span.",
            claim_id=make_claim_id(DOCUMENT_ID, 0),
            evidence_index=0,
            quote="Revenue increased by 10%.",
            source_span_id=" \t\n ",
        )


def test_quote_validation_error_allows_missing_source_span_id() -> None:
    error = QuoteValidationError(
        code="quote_not_found",
        message="Missing quote.",
        claim_id=make_claim_id(DOCUMENT_ID, 0),
        evidence_index=0,
        quote="Missing quote.",
        source_span_id=None,
    )

    assert error.source_span_id is None


def test_quote_validation_result_valid_must_match_errors() -> None:
    error = QuoteValidationError(
        code="quote_not_found",
        message="Missing quote.",
        claim_id=make_claim_id(DOCUMENT_ID, 0),
        evidence_index=0,
        quote="Missing quote.",
    )

    with pytest.raises(ValidationError, match="valid must be True iff errors is empty"):
        QuoteValidationResult(
            claim_id=make_claim_id(DOCUMENT_ID, 0),
            document_id=DOCUMENT_ID,
            valid=True,
            errors=(error,),
        )


def test_quote_validator_reports_document_mismatch() -> None:
    result = validate_claim_quotes(
        claim=_claim(document_id=DOCUMENT_ID),
        span_index=_span_index(document_id=OTHER_DOCUMENT_ID),
    )

    assert result.valid is False
    assert result.errors[0].code == "document_mismatch"
