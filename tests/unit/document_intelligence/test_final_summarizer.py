import pytest
from pydantic import ValidationError

from exeboard_ai.document_intelligence.core.ids import make_chunk_id, make_claim_id, make_span_id
from exeboard_ai.document_intelligence.summarization.final_summarizer import build_final_summary
from exeboard_ai.document_intelligence.summarization.models import (
    ClaimEvidence,
    DocumentSummary,
    SummaryClaim,
    SummarySentence,
)

DOCUMENT_ID = "550e8400-e29b-41d4-a716-446655440000"


def _claim(*, claim_index: int = 0, status: str = "valid") -> SummaryClaim:
    return SummaryClaim(
        claim_id=make_claim_id(DOCUMENT_ID, claim_index),
        document_id=DOCUMENT_ID,
        document_type="business_review",
        claim=f"Claim {claim_index} is supported.",
        claim_role="finding",
        importance="high",
        evidence=(
            ClaimEvidence(
                quote=f"Claim {claim_index} is supported.",
                page_number=1,
                source_span_ids=(make_span_id(DOCUMENT_ID, 1, claim_index),),
                source_chunk_ids=(make_chunk_id(DOCUMENT_ID, claim_index),),
            ),
        ),
        validation_status=status,  # type: ignore[arg-type]
        validation_errors=() if status != "invalid" else ("quote_not_found",),
    )


def test_document_summary_rejects_unvalidated_claims() -> None:
    claim = _claim(status="unvalidated")

    with pytest.raises(ValidationError, match="claims must be valid before final summary"):
        DocumentSummary(
            document_id=DOCUMENT_ID,
            document_type="business_review",
            summary_sentences=(SummarySentence(text=claim.claim, supporting_claim_ids=(claim.claim_id,)),),
            claims=(claim,),
        )


def test_document_summary_rejects_invalid_claims() -> None:
    claim = _claim(status="invalid")

    with pytest.raises(ValidationError, match="claims must be valid before final summary"):
        DocumentSummary(
            document_id=DOCUMENT_ID,
            document_type="business_review",
            summary_sentences=(SummarySentence(text=claim.claim, supporting_claim_ids=(claim.claim_id,)),),
            claims=(claim,),
        )


def test_build_final_summary_excludes_invalid_and_unvalidated_claims() -> None:
    valid_claim = _claim(claim_index=0, status="valid")
    invalid_claim = _claim(claim_index=1, status="invalid")
    unvalidated_claim = _claim(claim_index=2, status="unvalidated")

    summary = build_final_summary(
        document_id=DOCUMENT_ID,
        document_type="business_review",
        claims=(valid_claim, invalid_claim, unvalidated_claim),
    )

    assert summary.claims == (valid_claim,)
    assert summary.summary_sentences == (
        SummarySentence(text=valid_claim.claim, supporting_claim_ids=(valid_claim.claim_id,)),
    )


def test_build_final_summary_rejects_no_valid_claims() -> None:
    with pytest.raises(ValueError, match="at least one valid claim"):
        build_final_summary(
            document_id=DOCUMENT_ID,
            document_type="business_review",
            claims=(_claim(status="unvalidated"),),
        )
