from hashlib import sha256
from pathlib import Path
from typing import Any

import pymupdf

from exeboard_ai.document_intelligence.core.ids import (
    DocumentId,
    make_document_id_from_file_name,
    make_page_id,
    make_span_id,
)
from exeboard_ai.document_intelligence.ir.models import (
    BoundingBox,
    DocumentIR,
    DocumentSource,
    Page,
    ParserRun,
    TextSpan,
)

PYMUPDF_TEXT_PARSER_RUN_ID = "pymupdf:text"
PARSER_NAME = "pymupdf"


class PyMuPDFParser:
    def parse(self, path: Path) -> DocumentIR:
        document_id = make_document_id_from_file_name(path.name)
        source = _make_document_source(path)
        pages: list[Page] = []
        content_parts: list[str] = []
        warnings: list[str] = []
        empty_page_numbers: list[int] = []

        with pymupdf.open(path) as pdf:
            if pdf.needs_pass:
                raise ValueError("encrypted PDFs require a password")

            parser_version = _get_pymupdf_version()

            for page_index in range(pdf.page_count):
                pdf_page = pdf.load_page(page_index)
                page_number = page_index + 1
                page_spans = _extract_page_spans(
                    pdf_page=pdf_page,
                    document_id=document_id,
                    page_number=page_number,
                    content_parts=content_parts,
                )
                if not page_spans:
                    empty_page_numbers.append(page_number)

                pages.append(
                    Page(
                        page_id=make_page_id(document_id, page_number),
                        page_number=page_number,
                        width=float(pdf_page.rect.width),
                        height=float(pdf_page.rect.height),
                        rotation=int(pdf_page.rotation),
                        spans=page_spans,
                    )
                )

        if empty_page_numbers:
            pages_text = ", ".join(str(page_number) for page_number in empty_page_numbers)
            warnings.append(f"no text extracted on pages: {pages_text}; OCR was not attempted")
        if not content_parts:
            warnings.append("no text extracted; OCR was not attempted")

        return DocumentIR(
            document_id=document_id,
            source=source,
            parser_runs=[
                ParserRun(
                    parser_run_id=PYMUPDF_TEXT_PARSER_RUN_ID,
                    parser_name=PARSER_NAME,
                    parser_version=parser_version,
                    warnings=warnings,
                )
            ],
            content="".join(content_parts),
            pages=pages,
        )


def _make_document_source(path: Path) -> DocumentSource:
    return DocumentSource(
        file_name=path.name,
        file_extension=path.suffix,
        mime_type="application/pdf",
        source_uri=str(path),
        content_sha256=sha256(path.read_bytes()).hexdigest(),
    )


def _extract_page_spans(
    *,
    pdf_page: Any,
    document_id: DocumentId,
    page_number: int,
    content_parts: list[str],
) -> list[TextSpan]:
    page_spans: list[TextSpan] = []
    text_dict = pdf_page.get_text("dict", sort=True, flags=_text_dict_flags())

    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue

        for line in block.get("lines", []):
            line_text = "".join(span.get("text", "") for span in line.get("spans", []))
            if not line_text.strip():
                continue

            if content_parts:
                content_parts.append("\n")

            char_start = len("".join(content_parts))
            content_parts.append(line_text)
            char_end = char_start + len(line_text)
            span_index = len(page_spans)

            page_spans.append(
                TextSpan(
                    span_id=make_span_id(document_id, page_number, span_index),
                    page_number=page_number,
                    text=line_text,
                    char_start=char_start,
                    char_end=char_end,
                    reading_order=span_index,
                    bbox=_make_bounding_box(line),
                    parser_run_id=PYMUPDF_TEXT_PARSER_RUN_ID,
                )
            )

    return page_spans


def _text_dict_flags() -> int:
    return pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES


def _make_bounding_box(line: dict[str, Any]) -> BoundingBox | None:
    bbox = line.get("bbox") or _union_span_bboxes(line.get("spans", []))
    if bbox is None or len(bbox) != 4:
        return None

    x0, y0, x1, y1 = (float(value) for value in bbox)
    if x1 < x0 or y1 < y0:
        return None

    return BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1)


def _union_span_bboxes(spans: list[dict[str, Any]]) -> tuple[float, float, float, float] | None:
    bboxes: list[tuple[float, float, float, float]] = []
    for span in spans:
        bbox = _coerce_bbox(span.get("bbox"))
        if bbox is not None:
            bboxes.append(bbox)

    if not bboxes:
        return None

    return (
        min(bbox[0] for bbox in bboxes),
        min(bbox[1] for bbox in bboxes),
        max(bbox[2] for bbox in bboxes),
        max(bbox[3] for bbox in bboxes),
    )


def _coerce_bbox(value: object) -> tuple[float, float, float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None

    return (float(value[0]), float(value[1]), float(value[2]), float(value[3]))


def _get_pymupdf_version() -> str:
    version = getattr(pymupdf, "version", None)
    if isinstance(version, tuple) and version:
        return str(version[0])
    if isinstance(version, str):
        return version
    return "unknown"
