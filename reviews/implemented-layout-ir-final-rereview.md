# Implemented Layout IR Final Re-review

Date: 2026-05-26
Scope reviewed: layout IR models, parser-port exceptions, PyMuPDF baseline behavior before Docling. No code files modified.

## Research performed

Fresh research was performed before review, per instruction. Sources relied on:

- [CiteVQA: Benchmarking Evidence Attribution for Trustworthy Document Intelligence](https://arxiv.org/html/2605.12882) — reinforces that answer correctness is insufficient without checking evidence attribution to document regions.
- [Correctness is not Faithfulness in Retrieval Augmented Generation Attributions](https://dl.acm.org/doi/10.1145/3731120.3744592) — distinguishes correct answers from faithfully cited answers.
- [LAQuer: Localized Attribution Queries in Content-grounded Generation](https://arxiv.org/html/2506.01187) — supports localized output-span to source-span attribution rather than coarse document-level citations.
- [Pydantic Validators docs](https://pydantic.dev/docs/validation/2.7/concepts/validators/) and [Pydantic Models docs](https://pydantic.dev/docs/validation/2.10/concepts/models/) — schema-boundary validation should reject invalid structured data before use.
- [Docling ProvenanceItem source](https://github.com/docling-project/docling-core/blob/main/docling_core/types/doc/document.py) and [DoclingDocument concept docs](https://docling-project-docling.mintlify.app/concepts/docling-document) — current Docling provenance tracks page number, bbox, and charspan/source location.

## Verdict

**CHANGE REQUIRED** before starting Docling adapter work.

The specific previous concerns are mostly fixed, but two production provenance/port issues remain:

1. Layout/page-region coordinates are not yet hardened enough for evidence-backed highlighting/audit.
2. A missing/unreadable PDF path can still escape the parser port as raw `FileNotFoundError` before `_open_pdf()` exception mapping runs.

## Previous concerns status

- **Empty `DocumentLayout.blocks`**: fixed. `DocumentLayout.blocks` is required and rejected when empty (`models.py:325-346`), covered by `test_document_layout_blocks_must_not_be_empty` (`test_layout_models.py:153-155`).
- **Empty `Table.cells`**: fixed. `Table.cells` is required non-empty (`models.py:229-252`), covered by `test_table_cells_must_not_be_empty` (`test_layout_models.py:517-525`).
- **Duplicate/blank span refs**: fixed for each span tuple. Shared validator rejects empty and duplicate values (`models.py:120-125`), wired for blocks/cells/figures (`models.py:169-172`, `210-213`, `302-305`), covered by `test_layout_span_id_tuples_must_not_contain_duplicates_or_empty_values` (`test_layout_models.py:184-205`).
- **Layout serialization round-trip**: fixed at model-dump/model-validate level (`test_layout_models.py:739-786`). I also smoke-tested `model_dump_json()` / `model_validate_json()` manually; it round-trips.
- **`TableCell` with no provenance**: fixed. Cells require source spans or bounding regions (`models.py:222-226`), covered by `test_table_cell_must_have_text_or_visual_provenance` (`test_layout_models.py:512-515`).
- **Table/figure blocks without detail IDs**: fixed. Wrapper blocks require `table_id`/`figure_id` (`models.py:174-186`) and document validation requires matching detailed objects (`models.py:517-520`, `607-660`), covered by tests at `test_layout_models.py:326-344`, `551-569`, and `647-663`.
- **Parser-port layout exceptions before Docling**: fixed at the port type level. `LayoutExtractionError` and `SpanAlignmentError` exist and subclass `DocumentParseError` (`ports.py:23-28`; tests `test_parser_ports.py:38-43`).

## Severity-ranked findings

### HIGH — `BoundingBox` accepts invalid/audit-hostile coordinates and silently drops extra vendor fields

**Files/lines:**

- `packages/exeboard-ai/src/exeboard_ai/document_intelligence/ir/models.py:95-110`
- Layout regions depend on this via `BoundingRegion.bbox` at `models.py:113-117`.

**Problem:**

`BoundingBox` currently only checks `x1 >= x0` and `y1 >= y0`. It does not forbid extra fields, non-finite floats, or negative coordinates. In current Pydantic defaults this means values such as `x0=-1`, `x0=NaN`, `x1=Infinity`, or a raw vendor field like `polygon=[...]` can be accepted/silently ignored.

For evidence-backed document intelligence, page/bbox provenance is not decorative metadata: it is the audit/highlight anchor. Docling-style provenance carries page + bbox + charspan, and current evidence-attribution research emphasizes localized evidence, so unrenderable or silently lossy boxes are a production correctness risk.

**Minimal fix:**

- Harden `BoundingBox` itself:
  - `model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)`
  - constrain all coordinates to normalized top-left PDF points, e.g. `x0/y0/x1/y1: float = Field(ge=0)` plus finite-value rejection.
  - Prefer positive area for layout `BoundingRegion`s. If zero-area text bboxes must remain valid for legacy spans, add the positive-area check on `BoundingRegion` instead of globally on `BoundingBox`.
- In `DocumentIR` layout validation, also reject `BoundingRegion` bboxes outside page width/height when page dimensions are known. Today `_validate_bounding_region_pages()` only checks that the page exists (`models.py:662-670`).

**Tests required:**

- Reject negative coordinates.
- Reject `NaN`/`Infinity` coordinates.
- Reject extra/vendor coordinate fields on `BoundingBox`.
- Reject layout `BoundingRegion` outside known `Page.width`/`Page.height`.

### MEDIUM — Missing PDF paths bypass parser-port exception mapping

**Files/lines:**

- `packages/exeboard-ai/src/exeboard_ai/document_intelligence/parsing/adapters/pymupdf.py:32-40`
- `packages/exeboard-ai/src/exeboard_ai/document_intelligence/parsing/adapters/pymupdf.py:91-98`
- `packages/exeboard-ai/src/exeboard_ai/document_intelligence/parsing/ports.py:15-20`

**Problem:**

`PyMuPDFParser.parse()` calls `_make_document_source(path)` before `_open_pdf(path)`. `_make_document_source()` computes `content_sha256=sha256(path.read_bytes()).hexdigest()`. For a missing/unreadable file, `path.read_bytes()` raises raw `FileNotFoundError`/`OSError`, not `UnreadableDocumentError`.

I manually reproduced this with a missing UUID-named PDF: it raised `FileNotFoundError` and `isinstance(exc, DocumentParseError) == False`.

**Minimal fix:**

Wrap source hashing/read failures in the adapter port error contract, e.g. catch `OSError` around `_make_document_source(path)` and raise `UnreadableDocumentError(f"failed to read PDF: {path}")` from the original exception. Alternatively move and wrap source creation inside the same protected open/read section.

**Tests required:**

- Add an integration/unit test that `PyMuPDFParser().parse(missing_uuid_pdf_path)` raises `UnreadableDocumentError`, not raw `FileNotFoundError`.
- Optional: add a permission-denied/read-error test if portable on CI.

## Required invariants now satisfied

- Required, non-empty layout blocks.
- Required, non-empty table cells.
- Required table cell provenance: spans or bounding regions.
- Required figure provenance: spans/caption spans or bounding regions.
- Required table/figure wrapper detail IDs and bidirectional consistency.
- Unique block IDs, table IDs, figure IDs, layout reading orders, parser run IDs.
- Parent block missing/self/cycle rejection.
- Layout parser run ID must reference an existing `ParserRun`.
- Layout span refs must exist, belong to the document, and be on pages included in layout provenance.
- Cross-page/non-contiguous table/figure/block representation is supported.
- Extra authoritative `text`/vendor-object fields are rejected on the new layout models checked by tests.

## Test execution note

I attempted to run the targeted test set with `pytest`, `uv run pytest`, and `.venv/bin/python -m pytest`. The environment does not currently have pytest installed/available, so I could not execute the suite here. Manual smoke checks were performed for JSON round-trip and the missing-file parser exception behavior.

## Deferred / future concerns

- `DocumentIR.pages`, `DocumentIR.parser_runs`, `Page.spans`, and `ParserRun.warnings` remain mutable lists inside frozen models (`models.py:393`, `420-422`, `356`). This can bypass post-construction invariants. I would defer unless this IR is now being stored/shared across trust boundaries, but tuple-conversion is the safer long-term shape.
- Consider rejecting duplicate span IDs across `Figure.source_span_ids` and `Figure.caption_span_ids` if downstream treats those as semantically disjoint evidence sets.
- Add an explicit `model_dump_json()` / `model_validate_json()` test in addition to the current Python `model_dump()` round-trip.
