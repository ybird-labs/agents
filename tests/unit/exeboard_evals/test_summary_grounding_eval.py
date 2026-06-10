from pathlib import Path
from typing import TypeVar

import pytest

from exeboard_ai.document_intelligence.core.ids import make_page_id, make_span_id
from exeboard_ai.document_intelligence.ir.models import (
    DocumentIR,
    DocumentSource,
    Page,
    TextSpan,
)
from exeboard_ai.document_intelligence.parsing.adapters.pymupdf import PyMuPDFParser
from exeboard_ai.document_intelligence.parsing.ports import (
    DocumentParser,
    UnreadableDocumentError,
)
from exeboard_evals.document_intelligence.summary_grounding import (
    ReplaySummaryGroundingGenerator,
    SummaryGroundingCase,
    load_summary_grounding_cases,
    run_summary_grounding_case,
    write_summary_grounding_report,
)
from pydantic import BaseModel

DOCUMENT_ID = "550e8400-e29b-41d4-a716-446655440000"
T = TypeVar("T", bound=BaseModel)


class FakeParser(DocumentParser):
    def parse(self, path: Path) -> DocumentIR:
        revenue_text = "Revenue increased by 10%"
        costs_text = "Costs declined by 3%"
        content = f"{revenue_text}\n{costs_text}"
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
                            text=revenue_text,
                            char_start=0,
                            char_end=len(revenue_text),
                            reading_order=0,
                        ),
                        TextSpan(
                            span_id=make_span_id(DOCUMENT_ID, 1, 1),
                            page_number=1,
                            text=costs_text,
                            char_start=len(revenue_text) + 1,
                            char_end=len(content),
                            reading_order=1,
                        ),
                    ],
                ),
            ],
        )


class FailingParser(DocumentParser):
    def parse(self, path: Path) -> DocumentIR:
        raise UnreadableDocumentError("boom")


def _case(*, costs_source_span_id: str | None = None) -> SummaryGroundingCase:
    revenue_span_id = make_span_id(DOCUMENT_ID, 1, 0)
    costs_span_id = make_span_id(DOCUMENT_ID, 1, 1)
    return SummaryGroundingCase.model_validate(
        {
            "case_id": "business-review-grounding",
            "fixture_path": "ignored.pdf",
            "document_id": DOCUMENT_ID,
            "document_type": "business_review",
            "target_chars": 200,
            "max_chars": 250,
            "generated_claims": [
                {
                    "trigger_span_id": revenue_span_id,
                    "claim": "Revenue increased by 10%.",
                    "claim_role": "finding",
                    "importance": "high",
                    "quote": "Revenue increased by 10%",
                    "source_span_ids": [revenue_span_id],
                },
                {
                    "trigger_span_id": costs_span_id,
                    "claim": "Costs declined by 3%.",
                    "claim_role": "finding",
                    "importance": "medium",
                    "quote": "Costs declined by 3%",
                    "source_span_ids": [costs_source_span_id or revenue_span_id],
                },
            ],
            "expected_claims": [
                {
                    "claim": "Revenue increased by 10%.",
                    "quote": "Revenue increased by 10%",
                    "page_number": 1,
                    "source_span_ids": [revenue_span_id],
                }
            ],
            "forbidden_claims": ["Costs declined by 3%."],
        }
    )


def test_summary_grounding_eval_passes_when_only_expected_exact_span_claims_survive() -> (
    None
):
    case = _case()

    result = run_summary_grounding_case(
        case,
        parser=FakeParser(),
        response_generator=ReplaySummaryGroundingGenerator(case.generated_claims),
    )

    assert result.passed is True
    assert result.failures == ()
    assert result.observed_claims == ("Revenue increased by 10%.",)
    assert result.observed_summary_sentences == ("Revenue increased by 10%.",)


def test_summary_grounding_eval_fails_when_forbidden_claim_survives() -> None:
    costs_span_id = make_span_id(DOCUMENT_ID, 1, 1)
    case = _case(costs_source_span_id=costs_span_id)

    result = run_summary_grounding_case(
        case,
        parser=FakeParser(),
        response_generator=ReplaySummaryGroundingGenerator(case.generated_claims),
    )

    assert result.passed is False
    assert "forbidden claim survived: Costs declined by 3%." in result.failures


def test_summary_grounding_eval_converts_parser_exception_to_failing_result() -> None:
    case = _case()

    result = run_summary_grounding_case(
        case,
        parser=FailingParser(),
        response_generator=ReplaySummaryGroundingGenerator(case.generated_claims),
    )

    assert result.passed is False
    assert result.failures == ("pipeline failed (UnreadableDocumentError): boom",)
    assert result.observed_claims == ()
    assert result.observed_summary_sentences == ()


def test_expected_claim_spec_rejects_blank_source_span_ids() -> None:
    revenue_span_id = make_span_id(DOCUMENT_ID, 1, 0)

    payload = _case().model_dump(mode="json")
    payload["expected_claims"][0]["source_span_ids"] = [revenue_span_id, "  "]

    with pytest.raises(ValueError, match="source_span_ids must not contain empty span ids"):
        SummaryGroundingCase.model_validate(payload)


def test_load_summary_grounding_cases_reads_jsonl(tmp_path: Path) -> None:
    case = _case()
    dataset_path = tmp_path / "cases.jsonl"
    dataset_path.write_text(case.model_dump_json() + "\n", encoding="utf-8")

    loaded_cases = load_summary_grounding_cases(dataset_path)

    assert loaded_cases == (case,)


def test_write_summary_grounding_report_emits_json_summary(tmp_path: Path) -> None:
    case = _case()
    result = run_summary_grounding_case(
        case,
        parser=FakeParser(),
        response_generator=ReplaySummaryGroundingGenerator(case.generated_claims),
    )
    report_path = tmp_path / "reports" / "summary_grounding.json"

    write_summary_grounding_report((result,), report_path)

    assert report_path.read_text(encoding="utf-8") == (
        "{\n"
        '  "total": 1,\n'
        '  "passed": 1,\n'
        '  "failed": 0,\n'
        '  "results": [\n'
        "    {\n"
        '      "case_id": "business-review-grounding",\n'
        '      "passed": true,\n'
        '      "failures": [],\n'
        '      "observed_claims": [\n'
        '        "Revenue increased by 10%."\n'
        "      ],\n"
        '      "observed_summary_sentences": [\n'
        '        "Revenue increased by 10%."\n'
        "      ]\n"
        "    }\n"
        "  ]\n"
        "}\n"
    )


def test_committed_summary_grounding_dataset_passes_with_pymupdf_fixture() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    cases = load_summary_grounding_cases(
        repo_root / "evals/datasets/document_intelligence/summary_grounding_v1.jsonl"
    )

    results = tuple(
        run_summary_grounding_case(
            case,
            parser=PyMuPDFParser(),
            response_generator=ReplaySummaryGroundingGenerator(case.generated_claims),
        )
        for case in cases
    )

    assert results, "Expected at least one summary grounding case in committed dataset."
    assert all(result.failures == () for result in results)
