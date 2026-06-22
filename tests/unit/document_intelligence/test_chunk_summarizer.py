from typing import TypeVar

import pytest
from pydantic import BaseModel, ValidationError

from exeboard_ai.document_intelligence.chunking.models import Chunk
from exeboard_ai.document_intelligence.core.ids import make_chunk_id, make_claim_id, make_page_id, make_span_id
from exeboard_ai.document_intelligence.ir.models import DocumentIR, DocumentSource, Page, TextSpan
from exeboard_ai.document_intelligence.ir.span_index import SpanIndex
from exeboard_ai.document_intelligence.summarization.chunk_summarizer import (
    CHUNK_SUMMARY_OPERATION_NAME,
    CHUNK_SUMMARY_OUTPUT_SCHEMA_NAME,
    CHUNK_SUMMARY_OUTPUT_SCHEMA_VERSION,
    summarize_chunk,
    summarize_chunk_run,
)
from exeboard_ai.document_intelligence.summarization.models import ChunkSummary
from exeboard_ai.document_intelligence.summarization.ports import StructuredGenerationRequest
from exeboard_ai.document_intelligence.summarization.prompts import (
    CHUNK_SUMMARY_PROMPT_NAME,
    CHUNK_SUMMARY_PROMPT_VERSION,
)
from exeboard_ai.document_intelligence.summarization.span_context import SpanAddressedChunkContext

DOCUMENT_ID = "550e8400-e29b-41d4-a716-446655440000"
T = TypeVar("T", bound=BaseModel)


class FakeStructuredResponseGenerator:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.seen_request: StructuredGenerationRequest | None = None
        self.seen_output_model: type[BaseModel] | None = None
        self.generate_count = 0

    def generate(
        self,
        *,
        request: StructuredGenerationRequest,
        output_model: type[T],
    ) -> T:
        self.generate_count += 1
        self.seen_request = request
        self.seen_output_model = output_model
        return output_model.model_validate(self.payload)


def _span_index(
    *,
    first_text: str = "Revenue increased by 10%.",
    second_text: str = "Costs declined.",
    first_page_number: int = 1,
) -> SpanIndex:
    content = f"{first_text}\n{second_text}"
    first_span = TextSpan(
        span_id=make_span_id(DOCUMENT_ID, first_page_number, 0),
        page_number=first_page_number,
        text=first_text,
        char_start=0,
        char_end=len(first_text),
        reading_order=0,
    )
    second_span = TextSpan(
        span_id=make_span_id(DOCUMENT_ID, 1, 1),
        page_number=1,
        text=second_text,
        char_start=len(first_text) + 1,
        char_end=len(content),
        reading_order=1,
    )
    pages = [
        Page(
            page_id=make_page_id(DOCUMENT_ID, first_page_number),
            page_number=first_page_number,
            spans=[first_span],
        )
    ]
    if first_page_number == 1:
        pages[0].spans.append(second_span)
    else:
        pages.append(
            Page(
                page_id=make_page_id(DOCUMENT_ID, 1),
                page_number=1,
                spans=[second_span],
            )
        )

    return SpanIndex(
        DocumentIR(
            document_id=DOCUMENT_ID,
            source=DocumentSource(file_name=f"{DOCUMENT_ID}.pdf", file_extension="pdf"),
            content=content,
            pages=pages,
        )
    )


def _chunk(*, source_span_ids: tuple[str, ...] | None = None, page_numbers: tuple[int, ...] = (1,)) -> Chunk:
    return Chunk(
        chunk_id=make_chunk_id(DOCUMENT_ID, 0),
        document_id=DOCUMENT_ID,
        text="Revenue increased by 10%.\nCosts declined.",
        page_numbers=page_numbers,
        source_span_ids=source_span_ids
        if source_span_ids is not None
        else (
            make_span_id(DOCUMENT_ID, 1, 0),
            make_span_id(DOCUMENT_ID, 1, 1),
        ),
    )


def _generated_payload(
    *,
    quote: str = "Revenue increased by 10%.",
    source_span_ids: tuple[str, ...] | None = None,
    extra_evidence_fields: dict[str, object] | None = None,
) -> dict[str, object]:
    evidence: dict[str, object] = {
        "quote": quote,
        "source_span_ids": source_span_ids
        if source_span_ids is not None
        else (make_span_id(DOCUMENT_ID, 1, 0),),
    }
    if extra_evidence_fields is not None:
        evidence.update(extra_evidence_fields)
    return {
        "claims": [
            {
                "claim": "Revenue increased by 10%.",
                "claim_role": "finding",
                "importance": "high",
                "evidence": [evidence],
            }
        ]
    }


def _summarize(
    *,
    chunk: Chunk | None = None,
    span_index: SpanIndex | None = None,
    generator: FakeStructuredResponseGenerator | None = None,
) -> ChunkSummary:
    return summarize_chunk(
        chunk=chunk or _chunk(),
        document_type="business_review",
        generator=generator or FakeStructuredResponseGenerator(_generated_payload()),
        span_index=span_index or _span_index(),
    )


def test_summarize_chunk_run_reports_generated_valid_and_assembly_dropped_claims() -> None:
    generator = FakeStructuredResponseGenerator(
        {
            "claims": [
                {
                    "claim": "Revenue increased by 10%.",
                    "claim_role": "finding",
                    "importance": "high",
                    "evidence": [
                        {
                            "quote": "Revenue increased by 10%.",
                            "source_span_ids": (make_span_id(DOCUMENT_ID, 1, 0),),
                        }
                    ],
                },
                {
                    "claim": "Invented quote claim.",
                    "claim_role": "finding",
                    "importance": "medium",
                    "evidence": [
                        {
                            "quote": "Invented quote.",
                            "source_span_ids": (make_span_id(DOCUMENT_ID, 1, 0),),
                        }
                    ],
                },
            ]
        }
    )

    result = summarize_chunk_run(
        chunk=_chunk(),
        document_type="business_review",
        generator=generator,
        span_index=_span_index(),
    )

    assert [claim.claim for claim in result.summary.claims] == ["Revenue increased by 10%."]
    assert result.report.claims_proposed == 2
    assert result.report.evidence_proposed == 2
    assert result.report.claims_assembled == 1
    assert result.report.claims_valid == 1
    assert len(result.report.drops) == 1
    drop = result.report.drops[0]
    assert drop.stage == "assembly_anchor"
    assert drop.error_codes == ("quote_not_found",)
    assert drop.proposal_index == 1
    assert drop.generated_claim == "Invented quote claim."
    assert drop.evidence_failures[0].quote == "Invented quote."
    assert result.report.counts_by_error_code == {"quote_not_found": 1}


def test_summarize_chunk_run_drops_multi_evidence_claim_once_with_failure_details() -> None:
    generator = FakeStructuredResponseGenerator(
        {
            "claims": [
                {
                    "claim": "Revenue increased by 10% and invented quote.",
                    "claim_role": "finding",
                    "importance": "high",
                    "evidence": [
                        {
                            "quote": "Revenue increased by 10%.",
                            "source_span_ids": (make_span_id(DOCUMENT_ID, 1, 0),),
                        },
                        {
                            "quote": "Invented quote.",
                            "source_span_ids": (make_span_id(DOCUMENT_ID, 1, 0),),
                        },
                    ],
                }
            ]
        }
    )

    result = summarize_chunk_run(
        chunk=_chunk(),
        document_type="business_review",
        generator=generator,
        span_index=_span_index(),
    )

    assert result.summary.claims == ()
    assert result.report.claims_proposed == 1
    assert result.report.evidence_proposed == 2
    assert result.report.claims_valid == 0
    assert len(result.report.drops) == 1
    assert result.report.drops[0].error_codes == ("quote_not_found",)
    assert result.report.drops[0].evidence_failures[0].evidence_index == 1
    assert result.report.drops[0].evidence_failures[0].quote == "Invented quote."


def test_summarize_chunk_sends_span_addressed_request_and_private_schema_to_generator() -> None:
    chunk = _chunk()
    generator = FakeStructuredResponseGenerator(_generated_payload())

    summarize_chunk(
        chunk=chunk,
        document_type="business_review",
        generator=generator,
        span_index=_span_index(),
    )

    assert generator.seen_request is not None
    assert generator.seen_request.operation_name == CHUNK_SUMMARY_OPERATION_NAME
    assert generator.seen_request.prompt_name == CHUNK_SUMMARY_PROMPT_NAME
    assert generator.seen_request.prompt_version == CHUNK_SUMMARY_PROMPT_VERSION
    assert generator.seen_request.output_schema_name == CHUNK_SUMMARY_OUTPUT_SCHEMA_NAME
    assert generator.seen_request.output_schema_version == CHUNK_SUMMARY_OUTPUT_SCHEMA_VERSION
    assert generator.seen_request.replay_key is not None
    assert generator.seen_request.replay_key.startswith(
        ":".join(
            [
                CHUNK_SUMMARY_OPERATION_NAME,
                CHUNK_SUMMARY_PROMPT_NAME,
                CHUNK_SUMMARY_PROMPT_VERSION,
                CHUNK_SUMMARY_OUTPUT_SCHEMA_NAME,
                CHUNK_SUMMARY_OUTPUT_SCHEMA_VERSION,
                "",
            ]
        )
    )
    replay_key_digest = generator.seen_request.replay_key.rsplit(":", maxsplit=1)[1]
    assert len(replay_key_digest) == 64
    assert generator.seen_request.metadata["document_id"] == chunk.document_id
    assert generator.seen_request.metadata["chunk_id"] == chunk.chunk_id
    assert generator.seen_request.metadata["document_type"] == "business_review"
    assert len(generator.seen_request.metadata["prompt_sha256"]) == 64
    assert len(generator.seen_request.metadata["output_schema_sha256"]) == 64
    assert isinstance(generator.seen_request.context, SpanAddressedChunkContext)
    assert generator.seen_request.context.allowed_spans[0].span_id == make_span_id(DOCUMENT_ID, 1, 0)
    assert generator.seen_request.context.allowed_spans[0].page_number == 1
    assert generator.seen_request.context.allowed_spans[0].text == "Revenue increased by 10%."
    assert chunk.chunk_id in generator.seen_request.prompt
    assert chunk.document_id in generator.seen_request.prompt
    assert "span_id: " + make_span_id(DOCUMENT_ID, 1, 0) in generator.seen_request.prompt
    assert "page_number: 1" in generator.seen_request.prompt
    assert "text: Revenue increased by 10%." in generator.seen_request.prompt
    assert chunk.text in generator.seen_request.prompt
    assert generator.seen_output_model is not None
    assert generator.seen_output_model is not ChunkSummary
    assert generator.seen_output_model.__name__ == "_GeneratedChunkSummary"


def test_summarize_chunk_fails_before_generation_when_chunk_span_is_missing_from_index() -> None:
    missing_span_chunk = _chunk(
        source_span_ids=(make_span_id(DOCUMENT_ID, 1, 99),),
        page_numbers=(1,),
    )
    generator = FakeStructuredResponseGenerator(_generated_payload())

    with pytest.raises(ValueError, match="chunk source_span_ids must exist in SpanIndex"):
        summarize_chunk(
            chunk=missing_span_chunk,
            document_type="business_review",
            generator=generator,
            span_index=_span_index(),
        )

    assert generator.generate_count == 0


def test_summarize_chunk_assembles_valid_generated_claim_with_trusted_page_and_lineage() -> None:
    chunk = _chunk()
    generator = FakeStructuredResponseGenerator(_generated_payload())

    summary = summarize_chunk(
        chunk=chunk,
        document_type="business_review",
        generator=generator,
        span_index=_span_index(),
        first_claim_index=5,
    )

    assert summary.chunk_id == chunk.chunk_id
    assert summary.document_id == chunk.document_id
    assert summary.document_type == "business_review"
    assert len(summary.claims) == 1

    claim = summary.claims[0]
    assert claim.claim_id == make_claim_id(DOCUMENT_ID, 5)
    assert claim.document_id == chunk.document_id
    assert claim.document_type == "business_review"
    assert claim.claim == "Revenue increased by 10%."
    assert claim.claim_role == "finding"
    assert claim.importance == "high"
    assert claim.validation_status == "unvalidated"
    assert claim.validation_errors == ()
    assert claim.derived_from_claim_ids == ()

    evidence = claim.evidence[0]
    assert evidence.quote == "Revenue increased by 10%."
    assert evidence.page_number == 1
    assert evidence.source_span_ids == (make_span_id(DOCUMENT_ID, 1, 0),)
    assert evidence.source_chunk_ids == (chunk.chunk_id,)


def test_summarize_chunk_accepts_empty_generated_claims() -> None:
    chunk = _chunk()
    generator = FakeStructuredResponseGenerator({"claims": []})

    summary = summarize_chunk(
        chunk=chunk,
        document_type="business_review",
        generator=generator,
        span_index=_span_index(),
    )

    assert summary == ChunkSummary(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        document_type="business_review",
        claims=(),
    )


def test_summarize_chunk_rejects_missing_generated_claims_field() -> None:
    generator = FakeStructuredResponseGenerator({})

    with pytest.raises(ValidationError, match="claims"):
        _summarize(generator=generator)


def test_summarize_chunk_excludes_generated_quote_outside_cited_span_text() -> None:
    generator = FakeStructuredResponseGenerator(_generated_payload(quote="Invented quote."))

    summary = _summarize(generator=generator)

    assert summary.claims == ()


def test_summarize_chunk_excludes_same_page_wrong_span_quote() -> None:
    generator = FakeStructuredResponseGenerator(
        _generated_payload(
            quote="Costs declined.",
            source_span_ids=(make_span_id(DOCUMENT_ID, 1, 0),),
        )
    )

    summary = _summarize(generator=generator)

    assert summary.claims == ()


def test_summarize_chunk_excludes_quote_with_only_stripped_whitespace_match() -> None:
    generator = FakeStructuredResponseGenerator(
        _generated_payload(
            quote=" Revenue increased by 10%. ",
            source_span_ids=(make_span_id(DOCUMENT_ID, 1, 0),),
        )
    )

    summary = _summarize(generator=generator)

    assert summary.claims == ()


def test_summarize_chunk_preserves_exact_quote_whitespace_from_cited_span() -> None:
    quote = " Revenue increased by 10%. "
    generator = FakeStructuredResponseGenerator(
        _generated_payload(
            quote=quote,
            source_span_ids=(make_span_id(DOCUMENT_ID, 1, 0),),
        )
    )

    summary = _summarize(generator=generator, span_index=_span_index(first_text=quote))

    assert summary.claims[0].evidence[0].quote == quote


def test_summarize_chunk_sends_prompt_and_context_without_stripping_span_text() -> None:
    span_text = " Revenue increased by 10%. "
    generator = FakeStructuredResponseGenerator({"claims": []})

    _summarize(generator=generator, span_index=_span_index(first_text=span_text))

    assert generator.seen_request is not None
    assert isinstance(generator.seen_request.context, SpanAddressedChunkContext)
    assert generator.seen_request.context.allowed_spans[0].text == span_text
    assert f"text: {span_text}" in generator.seen_request.prompt
    assert f"Chunk text:\n{_chunk().text}" in generator.seen_request.prompt


def test_summarize_chunk_drops_entire_claim_when_any_evidence_is_unsupported() -> None:
    generator = FakeStructuredResponseGenerator(
        {
            "claims": [
                {
                    "claim": "Revenue increased by 10% and costs declined.",
                    "claim_role": "finding",
                    "importance": "high",
                    "evidence": [
                        {
                            "quote": "Revenue increased by 10%.",
                            "source_span_ids": (make_span_id(DOCUMENT_ID, 1, 0),),
                        },
                        {
                            "quote": "Costs declined.",
                            "source_span_ids": (make_span_id(DOCUMENT_ID, 1, 0),),
                        },
                    ],
                }
            ]
        }
    )

    summary = _summarize(generator=generator)

    assert summary.claims == ()


def test_summarize_chunk_drops_entire_claim_when_any_evidence_is_normalized_only() -> None:
    normalized_span = "Revenue in-\ncreased by 10%."
    generator = FakeStructuredResponseGenerator(
        {
            "claims": [
                {
                    "claim": "Revenue increased by 10% and costs declined.",
                    "claim_role": "finding",
                    "importance": "high",
                    "evidence": [
                        {
                            "quote": normalized_span,
                            "source_span_ids": (make_span_id(DOCUMENT_ID, 1, 0),),
                        },
                        {
                            "quote": "Revenue increased by 10%.",
                            "source_span_ids": (make_span_id(DOCUMENT_ID, 1, 0),),
                        },
                    ],
                }
            ]
        }
    )

    summary = _summarize(generator=generator, span_index=_span_index(first_text=normalized_span))

    assert summary.claims == ()


def test_summarize_chunk_drops_entire_claim_when_any_evidence_is_fuzzy_only() -> None:
    generator = FakeStructuredResponseGenerator(
        {
            "claims": [
                {
                    "claim": "Revenue increased by 10% and costs declined.",
                    "claim_role": "finding",
                    "importance": "high",
                    "evidence": [
                        {
                            "quote": "Revenue increased by 10%.",
                            "source_span_ids": (make_span_id(DOCUMENT_ID, 1, 0),),
                        },
                        {
                            "quote": "Revenue increased by 11%.",
                            "source_span_ids": (make_span_id(DOCUMENT_ID, 1, 0),),
                        },
                    ],
                }
            ]
        }
    )

    summary = _summarize(generator=generator)

    assert summary.claims == ()


def test_summarize_chunk_assigns_contiguous_claim_ids_after_excluding_invalid_proposals() -> None:
    generator = FakeStructuredResponseGenerator(
        {
            "claims": [
                {
                    "claim": "Wrong-span costs claim.",
                    "claim_role": "finding",
                    "importance": "medium",
                    "evidence": [
                        {
                            "quote": "Costs declined.",
                            "source_span_ids": (make_span_id(DOCUMENT_ID, 1, 0),),
                        }
                    ],
                },
                {
                    "claim": "Revenue increased by 10%.",
                    "claim_role": "finding",
                    "importance": "high",
                    "evidence": [
                        {
                            "quote": "Revenue increased by 10%.",
                            "source_span_ids": (make_span_id(DOCUMENT_ID, 1, 0),),
                        }
                    ],
                },
            ]
        }
    )

    summary = _summarize(generator=generator)

    assert [claim.claim_id for claim in summary.claims] == [make_claim_id(DOCUMENT_ID, 0)]
    assert [claim.claim for claim in summary.claims] == ["Revenue increased by 10%."]


def test_summarize_chunk_replay_key_changes_when_chunk_text_changes() -> None:
    first_chunk = _chunk()
    second_chunk = Chunk(
        chunk_id=first_chunk.chunk_id,
        document_id=first_chunk.document_id,
        text="Different text.",
        page_numbers=first_chunk.page_numbers,
        source_span_ids=first_chunk.source_span_ids,
    )
    first_generator = FakeStructuredResponseGenerator({"claims": []})
    second_generator = FakeStructuredResponseGenerator({"claims": []})

    _summarize(chunk=first_chunk, generator=first_generator)
    _summarize(chunk=second_chunk, generator=second_generator)

    assert first_generator.seen_request is not None
    assert second_generator.seen_request is not None
    assert first_generator.seen_request.replay_key != second_generator.seen_request.replay_key


def test_summarize_chunk_replay_key_is_stable_for_equivalent_span_ordering() -> None:
    first_chunk = _chunk()
    second_chunk = _chunk(
        source_span_ids=(make_span_id(DOCUMENT_ID, 1, 1), make_span_id(DOCUMENT_ID, 1, 0)),
    )
    first_generator = FakeStructuredResponseGenerator({"claims": []})
    second_generator = FakeStructuredResponseGenerator({"claims": []})

    _summarize(chunk=first_chunk, generator=first_generator)
    _summarize(chunk=second_chunk, generator=second_generator)

    assert first_generator.seen_request is not None
    assert second_generator.seen_request is not None
    assert first_generator.seen_request.replay_key == second_generator.seen_request.replay_key


def test_summarize_chunk_replay_key_changes_when_allowed_span_text_changes() -> None:
    first_generator = FakeStructuredResponseGenerator({"claims": []})
    second_generator = FakeStructuredResponseGenerator({"claims": []})

    _summarize(generator=first_generator, span_index=_span_index(first_text="Revenue increased by 10%."))
    _summarize(generator=second_generator, span_index=_span_index(first_text="Revenue grew by 10%."))

    assert first_generator.seen_request is not None
    assert second_generator.seen_request is not None
    assert first_generator.seen_request.replay_key != second_generator.seen_request.replay_key


def test_summarize_chunk_replay_key_changes_when_allowed_span_page_changes() -> None:
    page_one_chunk = _chunk(
        source_span_ids=(make_span_id(DOCUMENT_ID, 1, 0),),
        page_numbers=(1,),
    )
    page_two_chunk = Chunk(
        chunk_id=make_chunk_id(DOCUMENT_ID, 0),
        document_id=DOCUMENT_ID,
        text="Revenue increased by 10%.\nCosts declined.",
        page_numbers=(2,),
        source_span_ids=(make_span_id(DOCUMENT_ID, 2, 0),),
    )
    first_generator = FakeStructuredResponseGenerator({"claims": []})
    second_generator = FakeStructuredResponseGenerator({"claims": []})

    _summarize(chunk=page_one_chunk, generator=first_generator, span_index=_span_index())
    _summarize(
        chunk=page_two_chunk,
        generator=second_generator,
        span_index=_span_index(first_page_number=2),
    )

    assert first_generator.seen_request is not None
    assert second_generator.seen_request is not None
    assert first_generator.seen_request.replay_key != second_generator.seen_request.replay_key


@pytest.mark.parametrize("source_span_id", ["not-a-span-id", make_span_id(DOCUMENT_ID, 1, 99)])
def test_summarize_chunk_run_drops_generated_span_outside_allowed_context(
    source_span_id: str,
) -> None:
    generator = FakeStructuredResponseGenerator(
        _generated_payload(source_span_ids=(source_span_id,))
    )

    result = summarize_chunk_run(
        chunk=_chunk(),
        document_type="business_review",
        generator=generator,
        span_index=_span_index(),
    )

    assert result.summary.claims == ()
    assert result.report.claims_proposed == 1
    assert result.report.claims_assembled == 0
    assert result.report.claims_valid == 0
    assert len(result.report.drops) == 1
    drop = result.report.drops[0]
    assert drop.stage == "assembly_anchor"
    assert drop.error_codes == ("source_span_not_in_chunk_context",)
    assert drop.proposal_index == 0
    assert drop.generated_claim == "Revenue increased by 10%."
    assert drop.evidence_failures[0].error_code == "source_span_not_in_chunk_context"
    assert drop.evidence_failures[0].quote == "Revenue increased by 10%."
    assert drop.evidence_failures[0].source_span_ids == (source_span_id,)
    assert result.report.counts_by_error_code == {"source_span_not_in_chunk_context": 1}


def test_summarize_chunk_run_drops_generated_evidence_spanning_multiple_pages() -> None:
    generator = FakeStructuredResponseGenerator(
        _generated_payload(
            source_span_ids=(make_span_id(DOCUMENT_ID, 2, 0), make_span_id(DOCUMENT_ID, 1, 1)),
        )
    )
    chunk = _chunk(
        source_span_ids=(make_span_id(DOCUMENT_ID, 2, 0), make_span_id(DOCUMENT_ID, 1, 1)),
        page_numbers=(1, 2),
    )

    result = summarize_chunk_run(
        chunk=chunk,
        document_type="business_review",
        generator=generator,
        span_index=_span_index(first_page_number=2),
    )

    assert result.summary.claims == ()
    assert result.report.claims_proposed == 1
    assert result.report.claims_assembled == 0
    assert result.report.claims_valid == 0
    assert result.report.assembly_drop_count == 1
    assert result.report.drops[0].error_codes == ("evidence_spans_cross_pages",)
    assert result.report.drops[0].evidence_failures[0].error_code == "evidence_spans_cross_pages"
    assert result.report.counts_by_error_code == {"evidence_spans_cross_pages": 1}


def test_summarize_chunk_rejects_generated_page_number_field() -> None:
    generator = FakeStructuredResponseGenerator(_generated_payload(extra_evidence_fields={"page_number": 1}))

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _summarize(generator=generator)


def test_summarize_chunk_rejects_negative_first_claim_index() -> None:
    generator = FakeStructuredResponseGenerator({"claims": []})

    with pytest.raises(ValueError, match="first_claim_index must be 0 or greater"):
        summarize_chunk(
            chunk=_chunk(),
            document_type="business_review",
            generator=generator,
            span_index=_span_index(),
            first_claim_index=-1,
        )


def test_summarize_chunk_rejects_generated_validation_or_identity_fields() -> None:
    generator = FakeStructuredResponseGenerator(
        {
            "claims": [
                {
                    "claim": "Revenue increased by 10%.",
                    "claim_role": "finding",
                    "importance": "high",
                    "validation_status": "valid",
                    "evidence": [
                        {
                            "quote": "Revenue increased by 10%.",
                            "source_span_ids": (make_span_id(DOCUMENT_ID, 1, 0),),
                            "source_chunk_ids": (make_chunk_id(DOCUMENT_ID, 0),),
                        }
                    ],
                }
            ]
        }
    )

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _summarize(generator=generator)
