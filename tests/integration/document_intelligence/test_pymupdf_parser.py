from pathlib import Path
from typing import cast

import pymupdf
import pytest

from exeboard_ai.document_intelligence.core.ids import make_page_id, make_span_id
from exeboard_ai.document_intelligence.ir.span_index import SpanIndex
from exeboard_ai.document_intelligence.parsing.adapters.pymupdf import (
    PYMUPDF_TEXT_PARSER_RUN_ID,
    PyMuPDFParser,
    _make_bounding_box,
)
from exeboard_ai.document_intelligence.parsing.ports import (
    EncryptedDocumentError,
    NoExtractableTextError,
    UnreadableDocumentError,
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


def _write_top_edge_pdf(path: Path) -> None:
    document = pymupdf.open()
    try:
        page = document.new_page()
        page.insert_text((72, 1), "Top edge text")
        document.save(path)
    finally:
        document.close()


def _write_rotated_pdf(path: Path) -> None:
    document = pymupdf.open()
    try:
        page = document.new_page(width=200, height=400)
        page.insert_text((50, 100), "Rotated page text")
        page.set_rotation(90)
        document.save(path)
    finally:
        document.close()


def _write_encrypted_pdf(path: Path) -> None:
    document = pymupdf.open()
    try:
        page = document.new_page()
        page.insert_text((72, 72), "Encrypted text")
        document.save(
            path,
            encryption=cast(int, getattr(pymupdf, "PDF_ENCRYPT_AES_256")),
            owner_pw="owner-password",
            user_pw="user-password",
        )
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

    assert document.layout is None
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
    assert parser_run.parser_version is not None
    assert "PyMuPDF" in parser_run.parser_version
    assert "MuPDF" in parser_run.parser_version
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
    assert [
        (span.char_start, span.char_end) for span in first_page_spans
    ] == [(0, 17), (18, 42)]
    assert document.pages[1].spans[0].char_start == 43
    assert document.pages[1].spans[0].char_end == 62
    assert all(span.parser_run_id == PYMUPDF_TEXT_PARSER_RUN_ID for span in first_page_spans)
    assert first_page_spans[0].bbox is not None
    assert first_page_spans[0].bbox.x1 >= first_page_spans[0].bbox.x0
    assert first_page_spans[0].bbox.y1 >= first_page_spans[0].bbox.y0

    assert document.content == "Executive summary\nRevenue increased by 10%\nSecond page finding"
    for page in document.pages:
        for span in page.spans:
            assert document.content[span.char_start : span.char_end] == span.text

    index = SpanIndex(document)
    assert index.get_page_text(1) == "Executive summary\nRevenue increased by 10%"
    assert index.get_page_text(2) == "Second page finding"


def test_pymupdf_parser_reports_partially_blank_pdf_without_ocr(tmp_path: Path) -> None:
    pdf_path = tmp_path / f"{DOCUMENT_ID}.pdf"
    _write_pdf(pdf_path, [["Text page"], []])

    document = PyMuPDFParser().parse(pdf_path)

    assert document.content == "Text page"
    assert len(document.pages) == 2
    assert len(document.pages[0].spans) == 1
    assert document.pages[1].spans == []
    assert "no text extracted on pages: 2; OCR was not attempted" in document.parser_runs[0].warnings


def test_pymupdf_parser_raises_no_extractable_text_for_blank_pdf_without_ocr(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / f"{DOCUMENT_ID}.pdf"
    _write_pdf(pdf_path, [[]])

    with pytest.raises(NoExtractableTextError, match="no extractable text found"):
        PyMuPDFParser().parse(pdf_path)


def test_pymupdf_parser_drops_invalid_optional_text_bboxes_without_failing(
    tmp_path: Path,
) -> None:
    assert _make_bounding_box({"bbox": (72, -6.825, 150, 8)}) is None
    assert _make_bounding_box({"bbox": (72, float("nan"), 150, 8)}) is None

    pdf_path = tmp_path / f"{DOCUMENT_ID}.pdf"
    _write_top_edge_pdf(pdf_path)

    document = PyMuPDFParser().parse(pdf_path)

    assert document.content == "Top edge text"
    assert document.pages[0].spans[0].text == "Top edge text"


def test_pymupdf_parser_uses_unrotated_page_dimensions_for_text_coordinates(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / f"{DOCUMENT_ID}.pdf"
    _write_rotated_pdf(pdf_path)

    document = PyMuPDFParser().parse(pdf_path)

    page = document.pages[0]
    assert page.rotation == 90
    assert page.width == 200
    assert page.height == 400
    assert len(page.spans) == 1

    span = page.spans[0]
    assert span.text == "Rotated page text"
    assert document.content[span.char_start : span.char_end] == span.text
    assert span.bbox is not None
    assert 0 <= span.bbox.x0 <= span.bbox.x1 <= page.width
    assert 0 <= span.bbox.y0 <= span.bbox.y1 <= page.height


def test_pymupdf_parser_rejects_missing_pdf_with_parser_port_error(tmp_path: Path) -> None:
    missing_pdf_path = tmp_path / f"{DOCUMENT_ID}.pdf"

    with pytest.raises(UnreadableDocumentError, match="failed to read PDF"):
        PyMuPDFParser().parse(missing_pdf_path)


def test_pymupdf_parser_rejects_empty_or_invalid_pdf(tmp_path: Path) -> None:
    empty_pdf_path = tmp_path / f"{DOCUMENT_ID}.pdf"
    empty_pdf_path.write_bytes(b"")

    with pytest.raises(UnreadableDocumentError, match="failed to open PDF"):
        PyMuPDFParser().parse(empty_pdf_path)

    invalid_pdf_path = tmp_path / f"{DOCUMENT_ID}.pdf"
    invalid_pdf_path.write_bytes(b"not a pdf")

    with pytest.raises(UnreadableDocumentError, match="failed to open PDF"):
        PyMuPDFParser().parse(invalid_pdf_path)


def test_pymupdf_parser_rejects_encrypted_pdf_without_fake_authentication(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / f"{DOCUMENT_ID}.pdf"
    _write_encrypted_pdf(pdf_path)

    with pytest.raises(EncryptedDocumentError, match="encrypted PDFs require a password"):
        PyMuPDFParser().parse(pdf_path)


def test_pymupdf_parser_rejects_non_uuid_file_name(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    _write_pdf(pdf_path, [["text"]])

    with pytest.raises(ValueError, match="document_id must be a valid UUID"):
        PyMuPDFParser().parse(pdf_path)
