from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from exeboard_ai.document_intelligence.core.ids import make_page_id, make_span_id
from exeboard_ai.document_intelligence.ir.models import DocumentIR, DocumentSource, Page, TextSpan
from exeboard_ai.document_intelligence.parsing.ports import DocumentParser
from exeboard_ai.document_intelligence.summarization.pipeline import summarize_document
from exeboard_ai.document_intelligence.summarization.ports import StructuredGenerationRequest

DOCUMENT_ID = "550e8400-e29b-41d4-a716-446655440000"
T = TypeVar("T", bound=BaseModel)


class FakeParser(DocumentParser):
    def parse(self, path: Path) -> DocumentIR:
        first_text = "Revenue increased."
        second_text = "Costs declined."
        content = f"{first_text}\n{second_text}"
        return DocumentIR(
            document_id=DOCUMENT_ID,
            source=DocumentSource(file_name=f"{DOCUMENT_ID}.pdf", file_extension="pdf"),
            content=content,
            pages=[
                Page(
                    page_id=make_page_id(DOCUMENT_ID, 1),
                    page_number=1,
                    spans=[
                        TextSpan(
                            span_id=make_span_id(DOCUMENT_ID, 1, 0),
                            page_number=1,
                            text=first_text,
                            char_start=0,
                            char_end=len(first_text),
                            reading_order=0,
                        ),
                        TextSpan(
                            span_id=make_span_id(DOCUMENT_ID, 1, 1),
                            page_number=1,
                            text=second_text,
                            char_start=len(first_text) + 1,
                            char_end=len(content),
                            reading_order=1,
                        ),
                    ],
                )
            ],
        )


class FakeStructuredResponseGenerator:
    def __init__(self, *, cite_wrong_span_for_costs: bool = False) -> None:
        self.requests: list[StructuredGenerationRequest] = []
        self.cite_wrong_span_for_costs = cite_wrong_span_for_costs

    def generate(self, *, request: StructuredGenerationRequest, output_model: type[T]) -> T:
        self.requests.append(request)
        revenue_claim = {
            "claim": "Revenue increased.",
            "claim_role": "finding",
            "importance": "high",
            "evidence": [
                {
                    "quote": "Revenue increased.",
                    "page_number": 1,
                    "source_span_ids": (make_span_id(DOCUMENT_ID, 1, 0),),
                }
            ],
        }
        costs_claim = {
            "claim": "Costs declined.",
            "claim_role": "finding",
            "importance": "medium",
            "evidence": [
                {
                    "quote": "Costs declined.",
                    "page_number": 1,
                    "source_span_ids": (
                        make_span_id(
                            DOCUMENT_ID,
                            1,
                            0 if self.cite_wrong_span_for_costs else 1,
                        ),
                    ),
                }
            ],
        }
        if "Revenue increased." in request.prompt and "Costs declined." in request.prompt:
            payload = {"claims": [revenue_claim, costs_claim]}
        elif "Revenue increased." in request.prompt:
            payload = {"claims": [revenue_claim]}
        else:
            payload = {"claims": [costs_claim]}
        return output_model.model_validate(payload)


def test_summarize_document_pipeline_validates_and_preserves_unique_claim_ids() -> None:
    generator = FakeStructuredResponseGenerator()

    summary = summarize_document(
        Path("ignored.pdf"),
        parser=FakeParser(),
        response_generator=generator,
        document_type="business_review",
        target_chars=18,
        max_chars=30,
    )

    assert [claim.validation_status for claim in summary.claims] == ["valid", "valid"]
    assert [claim.claim_id for claim in summary.claims] == [
        f"{DOCUMENT_ID}:claim0000",
        f"{DOCUMENT_ID}:claim0001",
    ]
    assert [sentence.supporting_claim_ids for sentence in summary.summary_sentences] == [
        (f"{DOCUMENT_ID}:claim0000",),
        (f"{DOCUMENT_ID}:claim0001",),
    ]
    assert len(generator.requests) == 2


def test_summarize_document_pipeline_excludes_same_page_wrong_span_quote() -> None:
    generator = FakeStructuredResponseGenerator(cite_wrong_span_for_costs=True)

    summary = summarize_document(
        Path("ignored.pdf"),
        parser=FakeParser(),
        response_generator=generator,
        document_type="business_review",
        target_chars=200,
        max_chars=250,
    )

    assert [claim.claim for claim in summary.claims] == ["Revenue increased."]
    assert [claim.claim_id for claim in summary.claims] == [f"{DOCUMENT_ID}:claim0000"]
    assert [sentence.text for sentence in summary.summary_sentences] == ["Revenue increased."]
    assert len(generator.requests) == 1
