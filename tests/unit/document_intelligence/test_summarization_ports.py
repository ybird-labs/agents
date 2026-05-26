from typing import TypeVar

from pydantic import BaseModel

from exeboard_ai.document_intelligence.summarization.ports import StructuredResponseGenerator

T = TypeVar("T", bound=BaseModel)


class ExampleStructuredResponse(BaseModel):
    answer: str
    confidence: float


class FakeStructuredResponseGenerator:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.seen_prompt: str | None = None
        self.seen_output_model: type[BaseModel] | None = None

    def generate(
        self,
        *,
        prompt: str,
        output_model: type[T],
    ) -> T:
        self.seen_prompt = prompt
        self.seen_output_model = output_model
        return output_model.model_validate(self.payload)


def _generate_with(
    generator: StructuredResponseGenerator,
    *,
    prompt: str,
    output_model: type[T],
) -> T:
    return generator.generate(prompt=prompt, output_model=output_model)


def test_structured_response_generator_protocol_accepts_structural_generator() -> None:
    generator = FakeStructuredResponseGenerator(
        {"answer": "Revenue increased.", "confidence": 0.9}
    )

    response = _generate_with(
        generator,
        prompt="Summarize this chunk.",
        output_model=ExampleStructuredResponse,
    )

    assert response == ExampleStructuredResponse(answer="Revenue increased.", confidence=0.9)
    assert generator.seen_prompt == "Summarize this chunk."
    assert generator.seen_output_model is ExampleStructuredResponse
