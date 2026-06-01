import pytest
from pydantic import ValidationError

from exeboard_ai.document_intelligence.core.ids import (
    make_chunk_id,
    make_claim_id,
    make_page_id,
    make_span_id,
)
from exeboard_ai.document_intelligence.ir.models import DocumentIR, DocumentSource, Page, TextSpan
from exeboard_ai.document_intelligence.ir.span_index import SpanIndex
from exeboard_ai.document_intelligence.summarization.models import ClaimEvidence, SummaryClaim
from exeboard_ai.document_intelligence.validation.citation_validator import (
    CitationValidationError,
    CitationValidationResult,
    validate_claim_citations,
)

DOCUMENT_ID = "550e8400-e29b-41d4-a716-446655440000"
OTHER_DOCUMENT_ID = "650e8400-e29b-41d4-a716-446655440000"


def _span_index(
    *,
    document_id: str = DOCUMENT_ID,
    span_document_id: str = DOCUMENT_ID,
    span_id_page_number: int = 1,
    actual_span_page_number: int = 1,
    span_index: int = 0,
    text: str = "Revenue increased.",
) -> SpanIndex:
    span = TextSpan(
        span_id=make_span_id(span_document_id, span_id_page_number, span_index),
        page_number=actual_span_page_number,
        text=text,
        char_start=0,
        char_end=len(text),
        reading_order=0,
    )
    document = DocumentIR(
        document_id=document_id,
        source=DocumentSource(file_name=f"{document_id}.pdf", file_extension="pdf"),
        content=text,
        pages=[
            Page(
                page_id=make_page_id(document_id, actual_span_page_number),
                page_number=actual_span_page_number,
                spans=[span],
            )
        ],
    )
    return SpanIndex(document)


def _claim(
    *,
    document_id: str = DOCUMENT_ID,
    claim_index: int = 0,
    evidence_page_number: int = 1,
    source_span_ids: tuple[str, ...] | None = None,
    validation_status: str = "unvalidated",
) -> SummaryClaim:
    return SummaryClaim(
        claim_id=make_claim_id(document_id, claim_index),
        document_id=document_id,
        document_type="business_review",
        claim="Revenue increased.",
        claim_role="finding",
        importance="high",
        evidence=(
            ClaimEvidence(
                quote="Revenue increased.",
                page_number=evidence_page_number,
                source_span_ids=source_span_ids
                if source_span_ids is not None
                else (make_span_id(document_id, evidence_page_number, 0),),
                source_chunk_ids=(make_chunk_id(document_id, 0),),
            ),
        ),
        validation_status=validation_status,  # type: ignore[arg-type]
    )


def test_validate_claim_citations_returns_result_not_updated_claim() -> None:
    claim = _claim()

    result = validate_claim_citations(claim=claim, span_index=_span_index())

    assert isinstance(result, CitationValidationResult)
    assert not isinstance(result, SummaryClaim)
    assert result.claim_id == claim.claim_id
    assert result.document_id == claim.document_id


def test_valid_citations_produce_valid_result_with_no_errors() -> None:
    result = validate_claim_citations(claim=_claim(), span_index=_span_index())

    assert result.valid is True
    assert result.errors == ()


def test_fake_span_ids_produce_invalid_span_id() -> None:
    missing_span_id = make_span_id(DOCUMENT_ID, 1, 99)

    result = validate_claim_citations(
        claim=_claim(source_span_ids=(missing_span_id,)),
        span_index=_span_index(),
    )

    assert result.valid is False
    assert len(result.errors) == 1
    error = result.errors[0]
    assert error.code == "invalid_span_id"
    assert error.claim_id == make_claim_id(DOCUMENT_ID, 0)
    assert error.evidence_index == 0
    assert error.source_span_id == missing_span_id


def test_page_mismatch_reports_expected_and_actual_page_numbers() -> None:
    source_span_id = make_span_id(DOCUMENT_ID, 1, 0)
    text = "Revenue increased."
    corrupted_span = TextSpan.model_construct(
        span_id=source_span_id,
        page_number=2,
        text=text,
        char_start=0,
        char_end=len(text),
        reading_order=0,
        bbox=None,
        parser_run_id=None,
    )
    corrupted_document = DocumentIR.model_construct(
        ir_version="0.1",
        document_id=DOCUMENT_ID,
        source=DocumentSource(file_name=f"{DOCUMENT_ID}.pdf", file_extension="pdf"),
        parser_runs=[],
        content=text,
        pages=[
            Page.model_construct(
                page_id=make_page_id(DOCUMENT_ID, 2),
                page_number=2,
                width=None,
                height=None,
                rotation=None,
                spans=[corrupted_span],
            )
        ],
        layout=None,
    )

    result = validate_claim_citations(
        claim=_claim(evidence_page_number=1, source_span_ids=(source_span_id,)),
        span_index=SpanIndex(corrupted_document),
    )

    assert result.valid is False
    assert len(result.errors) == 1
    error = result.errors[0]
    assert error.code == "page_mismatch"
    assert error.claim_id == make_claim_id(DOCUMENT_ID, 0)
    assert error.evidence_index == 0
    assert error.source_span_id == source_span_id
    assert error.expected_page_number == 1
    assert error.actual_page_number == 2


def test_document_mismatch_reports_claim_and_span_index_document_ids() -> None:
    result = validate_claim_citations(
        claim=_claim(document_id=DOCUMENT_ID),
        span_index=_span_index(
            document_id=OTHER_DOCUMENT_ID,
            span_document_id=OTHER_DOCUMENT_ID,
        ),
    )

    assert result.valid is False
    assert len(result.errors) == 1
    error = result.errors[0]
    assert error.code == "document_mismatch"
    assert error.claim_id == make_claim_id(DOCUMENT_ID, 0)
    assert error.evidence_index is None
    assert error.source_span_id is None
    assert error.expected_document_id == DOCUMENT_ID
    assert error.actual_document_id == OTHER_DOCUMENT_ID


def test_citation_validator_does_not_mark_summary_claim_aggregate_valid() -> None:
    claim = _claim(validation_status="unvalidated")

    result = validate_claim_citations(claim=claim, span_index=_span_index())

    assert result.valid is True
    assert claim.validation_status == "unvalidated"
    assert claim.validation_errors == ()


def test_citation_validation_result_valid_must_match_errors() -> None:
    error = CitationValidationError(
        code="invalid_span_id",
        message="Missing span.",
        claim_id=make_claim_id(DOCUMENT_ID, 0),
        evidence_index=0,
        source_span_id=make_span_id(DOCUMENT_ID, 1, 99),
    )

    with pytest.raises(ValidationError, match="valid must be True iff errors is empty"):
        CitationValidationResult(
            claim_id=make_claim_id(DOCUMENT_ID, 0),
            document_id=DOCUMENT_ID,
            valid=True,
            errors=(error,),
        )

    with pytest.raises(ValidationError, match="valid must be True iff errors is empty"):
        CitationValidationResult(
            claim_id=make_claim_id(DOCUMENT_ID, 0),
            document_id=DOCUMENT_ID,
            valid=False,
            errors=(),
        )


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (
            lambda: CitationValidationError(
                code="invalid_span_id",
                message="   ",
                claim_id=make_claim_id(DOCUMENT_ID, 0),
            ),
            "must not be empty",
        ),
        (
            lambda: CitationValidationError(
                code="invalid_span_id",
                message="Missing span.",
                claim_id=make_claim_id(DOCUMENT_ID, 0),
                evidence_index=-1,
            ),
            "greater than or equal to 0",
        ),
        (
            lambda: CitationValidationError(
                code="page_mismatch",
                message="Wrong page.",
                claim_id=make_claim_id(DOCUMENT_ID, 0),
                expected_page_number=0,
            ),
            "greater than or equal to 1",
        ),
        (
            lambda: CitationValidationError(
                code="document_mismatch",
                message="Wrong document.",
                claim_id=make_claim_id(DOCUMENT_ID, 0),
                expected_document_id="not-a-uuid",
            ),
            "document_id must be a valid UUID",
        ),
    ],
)
def test_citation_validation_error_guards(factory: object, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        factory()  # type: ignore[operator]


def test_citation_validation_models_forbid_extra_fields_and_validation_status() -> None:
    assert "validation_status" not in CitationValidationResult.model_fields

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CitationValidationResult.model_validate(
            {
                "claim_id": make_claim_id(DOCUMENT_ID, 0),
                "document_id": DOCUMENT_ID,
                "valid": True,
                "validation_status": "valid",
            }
        )

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CitationValidationError.model_validate(
            {
                "code": "invalid_span_id",
                "message": "Missing span.",
                "claim_id": make_claim_id(DOCUMENT_ID, 0),
                "unexpected": "field",
            }
        )
