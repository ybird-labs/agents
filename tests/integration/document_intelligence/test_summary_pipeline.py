from pathlib import Path
from typing import TypeVar

import pytest
from pydantic import BaseModel

from exeboard_ai.document_intelligence.core.ids import make_page_id, make_span_id
from exeboard_ai.document_intelligence.ir.models import DocumentIR, DocumentSource, Page, TextSpan
from exeboard_ai.document_intelligence.parsing.ports import DocumentParser
from exeboard_ai.document_intelligence.summarization.pipeline import summarize_document, summarize_document_run
from exeboard_ai.document_intelligence.summarization.ports import StructuredGenerationRequest
from exeboard_ai.document_intelligence.summarization.span_context import SpanAddressedChunkContext

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
    def __init__(
        self,
        *,
        cite_wrong_span_for_revenue: bool = False,
        cite_wrong_span_for_costs: bool = False,
        cite_out_of_context_span_for_revenue: bool = False,
        cite_out_of_context_span_for_costs: bool = False,
        revenue_quote: str = "Revenue increased.",
        costs_quote: str = "Costs declined.",
    ) -> None:
        self.requests: list[StructuredGenerationRequest] = []
        self.cite_wrong_span_for_revenue = cite_wrong_span_for_revenue
        self.cite_wrong_span_for_costs = cite_wrong_span_for_costs
        self.cite_out_of_context_span_for_revenue = cite_out_of_context_span_for_revenue
        self.cite_out_of_context_span_for_costs = cite_out_of_context_span_for_costs
        self.revenue_quote = revenue_quote
        self.costs_quote = costs_quote

    def generate(self, *, request: StructuredGenerationRequest, output_model: type[T]) -> T:
        self.requests.append(request)
        assert isinstance(request.context, SpanAddressedChunkContext)
        allowed_span_ids = request.context.allowed_span_ids
        claims: list[dict[str, object]] = []
        revenue_span_id = make_span_id(DOCUMENT_ID, 1, 0)
        costs_span_id = make_span_id(DOCUMENT_ID, 1, 1)
        if revenue_span_id in allowed_span_ids:
            if self.cite_out_of_context_span_for_revenue:
                revenue_source_span_id = make_span_id(DOCUMENT_ID, 1, 99)
            else:
                revenue_source_span_id = costs_span_id if self.cite_wrong_span_for_revenue else revenue_span_id
            claims.append(
                {
                    "claim": "Revenue increased.",
                    "claim_role": "finding",
                    "importance": "high",
                    "evidence": [
                        {
                            "quote": self.revenue_quote,
                            "source_span_ids": (revenue_source_span_id,),
                        }
                    ],
                }
            )
        if costs_span_id in allowed_span_ids:
            if self.cite_out_of_context_span_for_costs:
                costs_source_span_id = make_span_id(DOCUMENT_ID, 1, 99)
            else:
                costs_source_span_id = revenue_span_id if self.cite_wrong_span_for_costs else costs_span_id
            claims.append(
                {
                    "claim": "Costs declined.",
                    "claim_role": "finding",
                    "importance": "medium",
                    "evidence": [
                        {
                            "quote": self.costs_quote,
                            "source_span_ids": (costs_source_span_id,),
                        }
                    ],
                }
            )
        return output_model.model_validate({"claims": claims})


def test_summarize_document_run_reports_valid_claims_and_parser_counters() -> None:
    generator = FakeStructuredResponseGenerator()

    result = summarize_document_run(
        Path("ignored.pdf"),
        parser=FakeParser(),
        response_generator=generator,
        document_type="business_review",
        target_chars=18,
        max_chars=30,
    )

    assert result.status == "completed"
    assert result.summary is not None
    assert [claim.validation_status for claim in result.summary.claims] == ["valid", "valid"]
    assert result.report.claims_proposed == 2
    assert result.report.evidence_proposed == 2
    assert result.report.claims_assembled == 2
    assert result.report.claims_valid == 2
    assert result.report.drops == ()
    assert result.report.parser_counters == {
        "page_count": 1,
        "span_count": 2,
        "textless_page_count": 0,
        "parser_warning_count": 0,
    }


def test_summarize_document_run_reports_assembly_drops_without_changing_exact_validity() -> None:
    generator = FakeStructuredResponseGenerator(cite_wrong_span_for_costs=True)

    result = summarize_document_run(
        Path("ignored.pdf"),
        parser=FakeParser(),
        response_generator=generator,
        document_type="business_review",
        target_chars=200,
        max_chars=250,
    )

    assert result.summary is not None
    assert [claim.claim for claim in result.summary.claims] == ["Revenue increased."]
    assert result.report.claims_proposed == 2
    assert result.report.claims_valid == 1
    assert len(result.report.drops) == 1
    assert result.report.drops[0].stage == "assembly_anchor"
    assert result.report.drops[0].error_codes == ("quote_not_found",)
    assert result.report.counts_by_error_code == {"quote_not_found": 1}


def test_summarize_document_run_returns_none_summary_when_no_claims_are_valid() -> None:
    generator = FakeStructuredResponseGenerator(
        cite_wrong_span_for_revenue=True,
        cite_wrong_span_for_costs=True,
    )

    result = summarize_document_run(
        Path("ignored.pdf"),
        parser=FakeParser(),
        response_generator=generator,
        document_type="business_review",
        target_chars=200,
        max_chars=250,
    )

    assert result.status == "zero_valid_claims"
    assert result.summary is None
    assert result.report.claims_proposed == 2
    assert result.report.claims_valid == 0
    assert len(result.report.drops) == 2
    assert result.report.assembly_drop_count == 2


def test_summarize_document_run_returns_zero_valid_report_for_out_of_context_generated_spans() -> None:
    generator = FakeStructuredResponseGenerator(
        cite_out_of_context_span_for_revenue=True,
        cite_out_of_context_span_for_costs=True,
    )

    result = summarize_document_run(
        Path("ignored.pdf"),
        parser=FakeParser(),
        response_generator=generator,
        document_type="business_review",
        target_chars=200,
        max_chars=250,
    )

    assert result.status == "zero_valid_claims"
    assert result.summary is None
    assert result.report.claims_proposed == 2
    assert result.report.claims_assembled == 0
    assert result.report.claims_valid == 0
    assert result.report.assembly_drop_count == 2
    assert result.report.counts_by_error_code == {"source_span_not_in_chunk_context": 2}
    assert [drop.proposal_index for drop in result.report.drops] == [0, 1]
    assert [drop.generated_claim for drop in result.report.drops] == [
        "Revenue increased.",
        "Costs declined.",
    ]
    assert result.report.parser_counters == {
        "page_count": 1,
        "span_count": 2,
        "textless_page_count": 0,
        "parser_warning_count": 0,
    }


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
    assert [claim.evidence[0].page_number for claim in summary.claims] == [1, 1]
    assert [claim.evidence[0].source_chunk_ids for claim in summary.claims] == [
        (f"{DOCUMENT_ID}:c0000",),
        (f"{DOCUMENT_ID}:c0001",),
    ]
    assert [sentence.supporting_claim_ids for sentence in summary.summary_sentences] == [
        (f"{DOCUMENT_ID}:claim0000",),
        (f"{DOCUMENT_ID}:claim0001",),
    ]
    assert len(generator.requests) == 2
    assert all(isinstance(request.context, SpanAddressedChunkContext) for request in generator.requests)


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


@pytest.mark.parametrize("costs_quote", ["Costs   declined.", "Costs decline."])
def test_summarize_document_pipeline_excludes_normalized_or_fuzzy_only_quote(
    costs_quote: str,
) -> None:
    generator = FakeStructuredResponseGenerator(costs_quote=costs_quote)

    summary = summarize_document(
        Path("ignored.pdf"),
        parser=FakeParser(),
        response_generator=generator,
        document_type="business_review",
        target_chars=200,
        max_chars=250,
    )

    assert [claim.claim for claim in summary.claims] == ["Revenue increased."]
    assert [sentence.text for sentence in summary.summary_sentences] == ["Revenue increased."]
