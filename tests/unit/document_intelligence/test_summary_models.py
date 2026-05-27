import pytest
from pydantic import ValidationError

from exeboard_ai.document_intelligence.core.ids import (
    make_chunk_id,
    make_claim_id,
    make_span_id,
)
from exeboard_ai.document_intelligence.summarization.models import (
    ClaimEvidence,
    ChunkSummary,
    DocumentSummary,
    SummaryClaim,
    SummarySentence,
)

DOCUMENT_ID = "550e8400-e29b-41d4-a716-446655440000"
OTHER_DOCUMENT_ID = "650e8400-e29b-41d4-a716-446655440000"


def _evidence(
    *,
    document_id: str = DOCUMENT_ID,
    page_number: int = 1,
    span_index: int = 0,
    chunk_index: int = 0,
    quote: str = "Revenue increased.",
    source_span_ids: tuple[str, ...] | None = None,
    source_chunk_ids: tuple[str, ...] | None = None,
) -> ClaimEvidence:
    return ClaimEvidence(
        quote=quote,
        page_number=page_number,
        source_span_ids=source_span_ids
        if source_span_ids is not None
        else (make_span_id(document_id, page_number, span_index),),
        source_chunk_ids=source_chunk_ids
        if source_chunk_ids is not None
        else (make_chunk_id(document_id, chunk_index),),
    )


def _claim(
    *,
    document_id: str = DOCUMENT_ID,
    document_type: str = "business_review",
    claim_index: int = 0,
    claim_role: str = "finding",
    evidence: tuple[ClaimEvidence, ...] | None = None,
    derived_from_claim_ids: tuple[str, ...] = (),
    validation_status: str = "unvalidated",
    validation_errors: tuple[str, ...] = (),
) -> SummaryClaim:
    return SummaryClaim(
        claim_id=make_claim_id(document_id, claim_index),
        document_id=document_id,
        document_type=document_type,  # type: ignore[arg-type]
        claim="Revenue increased year over year.",
        claim_role=claim_role,  # type: ignore[arg-type]
        importance="high",
        evidence=evidence if evidence is not None else (_evidence(document_id=document_id),),
        derived_from_claim_ids=derived_from_claim_ids,
        validation_status=validation_status,  # type: ignore[arg-type]
        validation_errors=validation_errors,
    )


def _document_summary(
    *,
    document_id: str = DOCUMENT_ID,
    document_type: str = "business_review",
    claims: tuple[SummaryClaim, ...] | None = None,
    summary_sentences: tuple[SummarySentence, ...] | None = None,
) -> DocumentSummary:
    actual_claims = claims if claims is not None else (_claim(document_id=document_id),)
    actual_summary_sentences = (
        summary_sentences
        if summary_sentences is not None
        else (
            SummarySentence(
                text="Revenue increased year over year.",
                supporting_claim_ids=(
                    actual_claims[0].claim_id if actual_claims else make_claim_id(document_id, 0),
                ),
            ),
        )
    )
    return DocumentSummary(
        document_id=document_id,
        document_type=document_type,  # type: ignore[arg-type]
        summary_sentences=actual_summary_sentences,
        claims=actual_claims,
    )


def test_document_summary_serializes_and_round_trips_with_tuple_provenance() -> None:
    summary = _document_summary()

    data = summary.model_dump()
    restored = DocumentSummary.model_validate(data)

    assert restored == summary
    assert isinstance(restored.summary_sentences, tuple)
    assert isinstance(restored.claims, tuple)
    assert isinstance(restored.claims[0].evidence, tuple)
    assert isinstance(restored.claims[0].evidence[0].source_span_ids, tuple)
    assert restored.claims[0].evidence[0].source_chunk_ids == (make_chunk_id(DOCUMENT_ID, 0),)


def test_summary_models_reject_invalid_document_id() -> None:
    with pytest.raises(ValidationError, match="document_id must be a valid UUID"):
        SummaryClaim(
            claim_id="not-a-uuid:claim0000",
            document_id="not-a-uuid",
            document_type="generic",
            claim="Something happened.",
            claim_role="finding",
            importance="medium",
            evidence=(_evidence(),),
        )


def test_summary_models_forbid_extra_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ClaimEvidence.model_validate(
            {
                "quote": "Revenue increased.",
                "page_number": 1,
                "source_span_ids": (make_span_id(DOCUMENT_ID, 1, 0),),
                "source_chunk_ids": (make_chunk_id(DOCUMENT_ID, 0),),
                "unexpected": "field",
            }
        )


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: _evidence(quote="   "), "quote must not be empty"),
        (
            lambda: SummaryClaim(
                claim_id=make_claim_id(DOCUMENT_ID, 0),
                document_id=DOCUMENT_ID,
                document_type="generic",
                claim="   ",
                claim_role="finding",
                importance="medium",
                evidence=(_evidence(),),
            ),
            "claim must not be empty",
        ),
        (
            lambda: SummarySentence(
                text="   ",
                supporting_claim_ids=(make_claim_id(DOCUMENT_ID, 0),),
            ),
            "text must not be empty",
        ),
    ],
)
def test_summary_models_reject_blank_text_fields(factory: object, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        factory()  # type: ignore[operator]


def test_summary_claim_rejects_empty_evidence() -> None:
    with pytest.raises(ValidationError, match="evidence must not be empty"):
        _claim(evidence=())


def test_claim_evidence_rejects_empty_source_span_ids() -> None:
    with pytest.raises(ValidationError, match="source_span_ids must not be empty"):
        _evidence(source_span_ids=())


def test_claim_evidence_rejects_empty_source_chunk_ids() -> None:
    with pytest.raises(ValidationError, match="source_chunk_ids must not be empty"):
        _evidence(source_chunk_ids=())


def test_claim_evidence_rejects_duplicate_source_span_ids() -> None:
    span_id = make_span_id(DOCUMENT_ID, 1, 0)

    with pytest.raises(ValidationError, match="source_span_ids must be unique"):
        _evidence(source_span_ids=(span_id, span_id))


def test_claim_evidence_rejects_duplicate_source_chunk_ids() -> None:
    chunk_id = make_chunk_id(DOCUMENT_ID, 0)

    with pytest.raises(ValidationError, match="source_chunk_ids must be unique"):
        _evidence(source_chunk_ids=(chunk_id, chunk_id))


def test_summary_sentence_rejects_duplicate_supporting_claim_ids() -> None:
    claim_id = make_claim_id(DOCUMENT_ID, 0)

    with pytest.raises(ValidationError, match="supporting_claim_ids must be unique"):
        SummarySentence(text="Revenue increased.", supporting_claim_ids=(claim_id, claim_id))


def test_summary_sentence_rejects_empty_supporting_claim_ids() -> None:
    with pytest.raises(ValidationError, match="supporting_claim_ids must not be empty"):
        SummarySentence(text="Revenue increased.", supporting_claim_ids=())


def test_summary_claim_rejects_duplicate_derived_claim_ids() -> None:
    derived_claim_id = make_claim_id(DOCUMENT_ID, 1)

    with pytest.raises(ValidationError, match="derived_from_claim_ids must be unique"):
        _claim(derived_from_claim_ids=(derived_claim_id, derived_claim_id))


def test_summary_claim_rejects_self_derived_claim_id() -> None:
    with pytest.raises(ValidationError, match="derived_from_claim_ids must not contain claim_id"):
        _claim(derived_from_claim_ids=(make_claim_id(DOCUMENT_ID, 0),))


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (
            lambda: ClaimEvidence(
                quote="Revenue increased.",
                page_number=1,
                source_span_ids=("bad-span-id",),
                source_chunk_ids=(make_chunk_id(DOCUMENT_ID, 0),),
            ),
            "span_id must use '<document_id>:p0001:s0000' format",
        ),
        (
            lambda: ClaimEvidence(
                quote="Revenue increased.",
                page_number=1,
                source_span_ids=(make_span_id(DOCUMENT_ID, 1, 0),),
                source_chunk_ids=("bad-chunk-id",),
            ),
            "chunk_id must use '<document_id>:c0000' format",
        ),
        (
            lambda: SummaryClaim(
                claim_id="bad-claim-id",
                document_id=DOCUMENT_ID,
                document_type="generic",
                claim="Something happened.",
                claim_role="finding",
                importance="medium",
                evidence=(_evidence(),),
            ),
            "claim_id must use '<document_id>:claim0000' format",
        ),
    ],
)
def test_summary_models_reject_malformed_ids(factory: object, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        factory()  # type: ignore[operator]


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (
            lambda: SummaryClaim(
                claim_id=make_claim_id(OTHER_DOCUMENT_ID, 0),
                document_id=DOCUMENT_ID,
                document_type="generic",
                claim="Something happened.",
                claim_role="finding",
                importance="medium",
                evidence=(_evidence(),),
            ),
            "claim_id must belong to document_id",
        ),
        (
            lambda: _claim(evidence=(_evidence(document_id=OTHER_DOCUMENT_ID),)),
            "evidence source IDs must belong to document_id",
        ),
        (
            lambda: _claim(derived_from_claim_ids=(make_claim_id(OTHER_DOCUMENT_ID, 1),)),
            "derived_from_claim_ids must belong to document_id",
        ),
        (
            lambda: ChunkSummary(
                chunk_id=make_chunk_id(OTHER_DOCUMENT_ID, 0),
                document_id=DOCUMENT_ID,
                document_type="business_review",
            ),
            "chunk_id must belong to document_id",
        ),
    ],
)
def test_summary_models_reject_ids_from_another_document(factory: object, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        factory()  # type: ignore[operator]


def test_claim_evidence_rejects_page_mismatch() -> None:
    with pytest.raises(ValidationError, match="source_span_ids page must match page_number"):
        _evidence(page_number=2, source_span_ids=(make_span_id(DOCUMENT_ID, 1, 0),))


def test_claim_evidence_rejects_single_evidence_object_spanning_multiple_pages() -> None:
    with pytest.raises(ValidationError, match="source_span_ids page must match page_number"):
        _evidence(
            page_number=1,
            source_span_ids=(
                make_span_id(DOCUMENT_ID, 1, 0),
                make_span_id(DOCUMENT_ID, 2, 0),
            ),
        )


def test_claim_evidence_rejects_mixed_document_sources() -> None:
    with pytest.raises(ValidationError, match="evidence source IDs must belong to the same document"):
        _evidence(
            source_span_ids=(make_span_id(DOCUMENT_ID, 1, 0),),
            source_chunk_ids=(make_chunk_id(OTHER_DOCUMENT_ID, 0),),
        )


def test_generic_document_type_rejects_obligation() -> None:
    with pytest.raises(ValidationError, match="claim_role is not allowed for document_type"):
        _claim(document_type="generic", claim_role="obligation")


@pytest.mark.parametrize(
    ("document_type", "claim_role"),
    [
        ("financial_report", "forecast"),
        ("business_review", "recommendation"),
        ("business_review", "action_item"),
        ("contract", "obligation"),
        ("contract", "entitlement"),
        ("contract", "prohibition"),
        ("meeting_notes", "decision"),
    ],
)
def test_document_type_specific_roles_are_allowed(document_type: str, claim_role: str) -> None:
    claim = _claim(document_type=document_type, claim_role=claim_role)

    assert claim.document_type == document_type
    assert claim.claim_role == claim_role


def test_chunk_summary_rejects_claim_that_does_not_cite_chunk() -> None:
    claim = _claim(evidence=(_evidence(chunk_index=1),))

    with pytest.raises(ValidationError, match="claim evidence must cite chunk_id"):
        ChunkSummary(
            chunk_id=make_chunk_id(DOCUMENT_ID, 0),
            document_id=DOCUMENT_ID,
            document_type="business_review",
            claims=(claim,),
        )


def test_chunk_summary_rejects_claim_with_mismatched_document_id() -> None:
    claim = _claim(document_id=OTHER_DOCUMENT_ID)

    with pytest.raises(ValidationError, match="claim document_id must match ChunkSummary document_id"):
        ChunkSummary(
            chunk_id=make_chunk_id(DOCUMENT_ID, 0),
            document_id=DOCUMENT_ID,
            document_type="business_review",
            claims=(claim,),
        )


def test_chunk_summary_rejects_claim_with_mismatched_document_type() -> None:
    claim = _claim(document_type="generic")

    with pytest.raises(ValidationError, match="claim document_type must match ChunkSummary document_type"):
        ChunkSummary(
            chunk_id=make_chunk_id(DOCUMENT_ID, 0),
            document_id=DOCUMENT_ID,
            document_type="business_review",
            claims=(claim,),
        )


def test_chunk_summary_rejects_duplicate_claim_ids() -> None:
    claim = _claim()

    with pytest.raises(ValidationError, match="claim_ids must be unique"):
        ChunkSummary(
            chunk_id=make_chunk_id(DOCUMENT_ID, 0),
            document_id=DOCUMENT_ID,
            document_type="business_review",
            claims=(claim, claim),
        )


def test_document_summary_rejects_empty_claims() -> None:
    with pytest.raises(ValidationError, match="claims must not be empty"):
        _document_summary(claims=())


def test_document_summary_rejects_empty_summary_sentences() -> None:
    with pytest.raises(ValidationError, match="summary_sentences must not be empty"):
        _document_summary(summary_sentences=())


def test_document_summary_rejects_summary_sentence_with_missing_claim_id() -> None:
    claim = _claim()

    with pytest.raises(ValidationError, match="supporting_claim_ids must reference existing claims"):
        _document_summary(
            claims=(claim,),
            summary_sentences=(
                SummarySentence(
                    text="Revenue increased.",
                    supporting_claim_ids=(make_claim_id(DOCUMENT_ID, 99),),
                ),
            ),
        )


def test_document_summary_rejects_duplicate_claim_ids() -> None:
    claim = _claim()

    with pytest.raises(ValidationError, match="claim_ids must be unique"):
        _document_summary(claims=(claim, claim))


def test_document_summary_rejects_claim_with_mismatched_document_id() -> None:
    claim = _claim(document_id=OTHER_DOCUMENT_ID)

    with pytest.raises(ValidationError, match="claim document_id must match DocumentSummary document_id"):
        _document_summary(
            claims=(claim,),
            summary_sentences=(
                SummarySentence(text="Revenue increased.", supporting_claim_ids=(claim.claim_id,)),
            ),
        )


def test_document_summary_rejects_claim_with_mismatched_document_type() -> None:
    claim = _claim(document_type="generic")

    with pytest.raises(ValidationError, match="claim document_type must match DocumentSummary document_type"):
        _document_summary(
            claims=(claim,),
            summary_sentences=(
                SummarySentence(text="Revenue increased.", supporting_claim_ids=(claim.claim_id,)),
            ),
        )


def test_document_summary_rejects_supporting_claim_id_from_another_document() -> None:
    claim = _claim()

    with pytest.raises(ValidationError, match="supporting_claim_ids must belong to document_id"):
        _document_summary(
            claims=(claim,),
            summary_sentences=(
                SummarySentence(
                    text="Revenue increased.",
                    supporting_claim_ids=(make_claim_id(OTHER_DOCUMENT_ID, 0),),
                ),
            ),
        )


@pytest.mark.parametrize(
    ("validation_status", "validation_errors", "message"),
    [
        (
            "unvalidated",
            ("source span missing",),
            "validation_errors must be empty unless validation_status is invalid",
        ),
        (
            "valid",
            ("source span missing",),
            "validation_errors must be empty unless validation_status is invalid",
        ),
        (
            "invalid",
            (),
            "invalid validation_status requires validation_errors",
        ),
        (
            "invalid",
            ("   ",),
            "validation_errors must not contain empty values",
        ),
    ],
)
def test_validation_status_must_match_validation_errors(
    validation_status: str,
    validation_errors: tuple[str, ...],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        _claim(validation_status=validation_status, validation_errors=validation_errors)
