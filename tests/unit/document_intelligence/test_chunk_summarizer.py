from typing import TypeVar

import pytest
from pydantic import BaseModel, ValidationError

from exeboard_ai.document_intelligence.chunking.models import Chunk
from exeboard_ai.document_intelligence.core.ids import make_chunk_id, make_claim_id, make_span_id
from exeboard_ai.document_intelligence.summarization.chunk_summarizer import (
    CHUNK_SUMMARY_OPERATION_NAME,
    CHUNK_SUMMARY_OUTPUT_SCHEMA_NAME,
    CHUNK_SUMMARY_OUTPUT_SCHEMA_VERSION,
    summarize_chunk,
)
from exeboard_ai.document_intelligence.summarization.models import ChunkSummary
from exeboard_ai.document_intelligence.summarization.ports import StructuredGenerationRequest
from exeboard_ai.document_intelligence.summarization.prompts import (
    CHUNK_SUMMARY_PROMPT_NAME,
    CHUNK_SUMMARY_PROMPT_VERSION,
)

DOCUMENT_ID = "550e8400-e29b-41d4-a716-446655440000"
T = TypeVar("T", bound=BaseModel)


class FakeStructuredResponseGenerator:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.seen_request: StructuredGenerationRequest | None = None
        self.seen_output_model: type[BaseModel] | None = None

    def generate(
        self,
        *,
        request: StructuredGenerationRequest,
        output_model: type[T],
    ) -> T:
        self.seen_request = request
        self.seen_output_model = output_model
        return output_model.model_validate(self.payload)


def _chunk() -> Chunk:
    return Chunk(
        chunk_id=make_chunk_id(DOCUMENT_ID, 0),
        document_id=DOCUMENT_ID,
        text="Revenue increased by 10%.\nCosts declined.",
        page_numbers=(1,),
        source_span_ids=(
            make_span_id(DOCUMENT_ID, 1, 0),
            make_span_id(DOCUMENT_ID, 1, 1),
        ),
    )


def _generated_payload(
    *,
    quote: str = "Revenue increased by 10%.",
    page_number: int = 1,
    source_span_ids: tuple[str, ...] | None = None,
) -> dict[str, object]:
    return {
        "claims": [
            {
                "claim": "Revenue increased by 10%.",
                "claim_role": "finding",
                "importance": "high",
                "evidence": [
                    {
                        "quote": quote,
                        "page_number": page_number,
                        "source_span_ids": source_span_ids
                        if source_span_ids is not None
                        else (make_span_id(DOCUMENT_ID, 1, 0),),
                    }
                ],
            }
        ]
    }


def test_summarize_chunk_sends_request_and_private_schema_to_generator() -> None:
    chunk = _chunk()
    generator = FakeStructuredResponseGenerator(_generated_payload())

    summarize_chunk(chunk=chunk, document_type="business_review", generator=generator)

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
    assert chunk.chunk_id in generator.seen_request.prompt
    assert chunk.document_id in generator.seen_request.prompt
    assert chunk.source_span_ids[0] in generator.seen_request.prompt
    assert chunk.text in generator.seen_request.prompt
    assert generator.seen_output_model is not None
    assert generator.seen_output_model is not ChunkSummary
    assert generator.seen_output_model.__name__ == "_GeneratedChunkSummary"


def test_summarize_chunk_assembles_valid_generated_claim_into_chunk_summary() -> None:
    chunk = _chunk()
    generator = FakeStructuredResponseGenerator(_generated_payload())

    summary = summarize_chunk(
        chunk=chunk,
        document_type="business_review",
        generator=generator,
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

    summary = summarize_chunk(chunk=chunk, document_type="business_review", generator=generator)

    assert summary == ChunkSummary(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        document_type="business_review",
        claims=(),
    )


def test_summarize_chunk_rejects_missing_generated_claims_field() -> None:
    generator = FakeStructuredResponseGenerator({})

    with pytest.raises(ValidationError, match="claims"):
        summarize_chunk(chunk=_chunk(), document_type="business_review", generator=generator)


def test_summarize_chunk_rejects_generated_quote_outside_chunk_text() -> None:
    generator = FakeStructuredResponseGenerator(_generated_payload(quote="Invented quote."))

    with pytest.raises(ValueError, match="quote must appear in chunk text"):
        summarize_chunk(chunk=_chunk(), document_type="business_review", generator=generator)


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

    summarize_chunk(chunk=first_chunk, document_type="business_review", generator=first_generator)
    summarize_chunk(chunk=second_chunk, document_type="business_review", generator=second_generator)

    assert first_generator.seen_request is not None
    assert second_generator.seen_request is not None
    assert first_generator.seen_request.replay_key != second_generator.seen_request.replay_key


def test_summarize_chunk_rejects_generated_span_outside_chunk() -> None:
    generator = FakeStructuredResponseGenerator(
        _generated_payload(source_span_ids=(make_span_id(DOCUMENT_ID, 1, 99),))
    )

    with pytest.raises(ValueError, match="source_span_ids must belong to chunk source_span_ids"):
        summarize_chunk(chunk=_chunk(), document_type="business_review", generator=generator)


def test_summarize_chunk_rejects_generated_page_outside_chunk() -> None:
    generator = FakeStructuredResponseGenerator(_generated_payload(page_number=2))

    with pytest.raises(ValueError, match="page_number must belong to chunk page_numbers"):
        summarize_chunk(chunk=_chunk(), document_type="business_review", generator=generator)


def test_summarize_chunk_rejects_negative_first_claim_index() -> None:
    generator = FakeStructuredResponseGenerator({"claims": []})

    with pytest.raises(ValueError, match="first_claim_index must be 0 or greater"):
        summarize_chunk(
            chunk=_chunk(),
            document_type="business_review",
            generator=generator,
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
                            "page_number": 1,
                            "source_span_ids": (make_span_id(DOCUMENT_ID, 1, 0),),
                            "source_chunk_ids": (make_chunk_id(DOCUMENT_ID, 0),),
                        }
                    ],
                }
            ]
        }
    )

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        summarize_chunk(chunk=_chunk(), document_type="business_review", generator=generator)
