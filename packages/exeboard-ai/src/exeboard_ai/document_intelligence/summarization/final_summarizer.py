from __future__ import annotations

from exeboard_ai.document_intelligence.core.ids import DocumentId, validate_document_id
from exeboard_ai.document_intelligence.summarization.models import (
    DocumentSummary,
    DocumentType,
    SummaryClaim,
    SummarySentence,
)


def build_final_summary(
    *,
    document_id: DocumentId,
    document_type: DocumentType,
    claims: tuple[SummaryClaim, ...],
) -> DocumentSummary:
    document_id = validate_document_id(document_id)
    valid_claims = tuple(
        claim
        for claim in claims
        if claim.document_id == document_id
        and claim.document_type == document_type
        and claim.validation_status == "valid"
    )
    if not valid_claims:
        raise ValueError("final summary requires at least one valid claim")

    return DocumentSummary(
        document_id=document_id,
        document_type=document_type,
        claims=valid_claims,
        summary_sentences=tuple(
            SummarySentence(text=claim.claim, supporting_claim_ids=(claim.claim_id,))
            for claim in valid_claims
        ),
    )
