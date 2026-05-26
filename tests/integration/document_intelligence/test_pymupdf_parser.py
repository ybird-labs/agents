from pathlib import Path

import pymupdf
import pytest

from exeboard_ai.document_intelligence.core.ids import make_page_id, make_span_id
from exeboard_ai.document_intelligence.ir.span_index import SpanIndex
from exeboard_ai.document_intelligence.parsing.adapters.pymupdf import (
    PYMUPDF_TEXT_PARSER_RUN_ID,
    PyMuPDFParser,
)

DOCUMENT_ID = "550e8400-e29b-41d4-a716-446655440000"


def _write_pdf(path: Path, pages: list[list[str]]) -> None:
    document = pymupdf.open()
    try:
        for page_lines in pages:
            page = document.new_page()
            y = 72
            for line in page_lines:
                page.insert_text((72, y), line)
                y += 24
        document.save(path)
    finally:
        document.close()


def test_pymupdf_parser_creates_document_ir_from_generated_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / f"{DOCUMENT_ID}.pdf"
    _write_pdf(
        pdf_path,
        [
            ["Executive summary", "Revenue increased by 10%"],
            ["Second page finding"],
        ],
    )

    document = PyMuPDFParser().parse(pdf_path)

    assert document.document_id == DOCUMENT_ID
    assert document.source.file_name == f"{DOCUMENT_ID}.pdf"
    assert document.source.file_extension == "pdf"
    assert document.source.mime_type == "application/pdf"
    assert document.source.source_uri == str(pdf_path)
    assert document.source.content_sha256 is not None
    assert len(document.source.content_sha256) == 64

    assert len(document.parser_runs) == 1
    parser_run = document.parser_runs[0]
    assert parser_run.parser_run_id == PYMUPDF_TEXT_PARSER_RUN_ID
    assert parser_run.parser_name == "pymupdf"
    assert parser_run.parser_version
    assert parser_run.warnings == []

    assert [page.page_id for page in document.pages] == [
        make_page_id(DOCUMENT_ID, 1),
        make_page_id(DOCUMENT_ID, 2),
    ]
    assert document.pages[0].width is not None
    assert document.pages[0].height is not None
    assert document.pages[0].rotation == 0

    first_page_spans = document.pages[0].spans
    assert [span.span_id for span in first_page_spans] == [
        make_span_id(DOCUMENT_ID, 1, 0),
        make_span_id(DOCUMENT_ID, 1, 1),
    ]
    assert [span.text for span in first_page_spans] == [
        "Executive summary",
        "Revenue increased by 10%",
    ]
    assert all(span.parser_run_id == PYMUPDF_TEXT_PARSER_RUN_ID for span in first_page_spans)
    assert first_page_spans[0].bbox is not None
    assert first_page_spans[0].bbox.x1 >= first_page_spans[0].bbox.x0
    assert first_page_spans[0].bbox.y1 >= first_page_spans[0].bbox.y0

    assert "Executive summary" in document.content
    assert "Revenue increased by 10%" in document.content
    assert "Second page finding" in document.content
    for page in document.pages:
        for span in page.spans:
            assert document.content[span.char_start : span.char_end] == span.text

    index = SpanIndex(document)
    assert index.get_page_text(1) == "Executive summary\nRevenue increased by 10%"
    assert index.get_page_text(2) == "Second page finding"


def test_pymupdf_parser_reports_blank_pdf_without_ocr(tmp_path: Path) -> None:
    pdf_path = tmp_path / f"{DOCUMENT_ID}.pdf"
    _write_pdf(pdf_path, [[]])

    document = PyMuPDFParser().parse(pdf_path)

    assert document.content == ""
    assert len(document.pages) == 1
    assert document.pages[0].spans == []
    assert "no text extracted on pages: 1; OCR was not attempted" in document.parser_runs[0].warnings
    assert "no text extracted; OCR was not attempted" in document.parser_runs[0].warnings


def test_pymupdf_parser_rejects_non_uuid_file_name(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    _write_pdf(pdf_path, [["text"]])

    with pytest.raises(ValueError, match="document_id must be a valid UUID"):
        PyMuPDFParser().parse(pdf_path)
