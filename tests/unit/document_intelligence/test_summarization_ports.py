from typing import TypeVar

import pytest
from pydantic import BaseModel, ValidationError

from exeboard_ai.document_intelligence.summarization.ports import (
    StructuredGenerationRequest,
    StructuredResponseGenerator,
)

T = TypeVar("T", bound=BaseModel)


class ExampleStructuredResponse(BaseModel):
    answer: str
    confidence: float


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


def _request(**overrides: object) -> StructuredGenerationRequest:
    data: dict[str, object] = {
        "operation_name": "document_intelligence.chunk_summary",
        "prompt_name": "chunk_summary",
        "prompt_version": "0.1",
        "output_schema_name": "chunk_summary_proposal",
        "output_schema_version": "0.1",
        "prompt": "Summarize this chunk.",
    }
    data.update(overrides)
    return StructuredGenerationRequest.model_validate(data)


def _generate_with(
    generator: StructuredResponseGenerator,
    *,
    request: StructuredGenerationRequest,
    output_model: type[T],
) -> T:
    return generator.generate(request=request, output_model=output_model)


def test_structured_response_generator_protocol_accepts_structural_generator() -> None:
    generator = FakeStructuredResponseGenerator(
        {"answer": "Revenue increased.", "confidence": 0.9}
    )
    request = _request(
        replay_key="doc:chunk:chunk_summary:0.1",
        metadata={"chunk_id": "chunk-1"},
    )

    response = _generate_with(
        generator,
        request=request,
        output_model=ExampleStructuredResponse,
    )

    assert response == ExampleStructuredResponse(answer="Revenue increased.", confidence=0.9)
    assert generator.seen_request == request
    assert generator.seen_output_model is ExampleStructuredResponse


@pytest.mark.parametrize(
    "field",
    [
        "operation_name",
        "prompt_name",
        "prompt_version",
        "output_schema_name",
        "output_schema_version",
        "prompt",
    ],
)
def test_structured_generation_request_rejects_blank_required_fields(field: str) -> None:
    with pytest.raises(ValidationError, match="must not be empty"):
        _request(**{field: "   "})


def test_structured_generation_request_rejects_blank_replay_key() -> None:
    with pytest.raises(ValidationError, match="replay_key must not be empty"):
        _request(replay_key="   ")


def test_structured_generation_request_rejects_blank_metadata_keys_and_values() -> None:
    with pytest.raises(ValidationError, match="metadata keys must not be empty"):
        _request(metadata={"   ": "value"})

    with pytest.raises(ValidationError, match="metadata values must not be empty"):
        _request(metadata={"key": "   "})


def test_structured_generation_request_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        StructuredGenerationRequest.model_validate(
            {
                "operation_name": "document_intelligence.chunk_summary",
                "prompt_name": "chunk_summary",
                "prompt_version": "0.1",
                "output_schema_name": "chunk_summary_proposal",
                "output_schema_version": "0.1",
                "prompt": "Summarize this chunk.",
                "model_name": "provider-owned-metadata",
            }
        )
