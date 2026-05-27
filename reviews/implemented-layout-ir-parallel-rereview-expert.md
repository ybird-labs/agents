# Implemented Layout IR Parallel Re-review — Expert

Date: 2026-05-26  
Scope: layout IR models, parser-port exceptions, and PyMuPDF native-text baseline before Docling. No source files modified except writing this review artifact.

## 1. Research performed

Fresh web research was performed before review. Queries covered evidence-backed summarization, citation faithfulness/attribution, structured output validation, and document-intelligence provenance. Sources relied on:

- [GenProve: Learning to Generate Text with Fine-Grained Provenance](https://arxiv.org/html/2601.04932v2) — reinforces sentence/claim-level provenance and explicit supporting source spans.
- [Correctness is not Faithfulness in Retrieval Augmented Generation Attributions](https://dl.acm.org/doi/10.1145/3731120.3744592) — supports treating attribution faithfulness as separate from factual correctness.
- [sui-1: Grounded and Verifiable Long-Form Summarization](https://arxiv.org/pdf/2601.08472) — supports cited, source-sentence-grounded long-form summaries.
- [Pydantic v2 Models documentation](https://docs.pydantic.dev/latest/concepts/models/) and [Pydantic v2 JSON Schema documentation](https://docs.pydantic.dev/latest/concepts/json_schema/) — supports schema-boundary validation and JSON serialization contracts.
- [DoclingDocument - Docling](https://docling-project.github.io/docling/concepts/docling_document/) and [`docling_core` document models](https://github.com/docling-project/docling-core/blob/main/docling_core/types/doc/document.py) — support page/bounding-box/char-span provenance as a document-intelligence norm.

## 2. Verdict

**APPROVED WITH NITS.**

No blocker remains for proceeding to the Docling adapter. The latest implementation fixes the prior high-severity PyMuPDF/strict-bbox regression, adds positive-area `BoundingRegion` validation, adds JSON round-trip coverage, and keeps the PyMuPDF adapter as a native-text baseline rather than a hidden layout/OCR parser.

## 3. Severity-ranked findings

### LOW — ID maker/parser round-trip fails after 4 digits

**Files/lines:**

- `packages/exeboard-ai/src/exeboard_ai/document_intelligence/core/ids.py:10-13`
- `packages/exeboard-ai/src/exeboard_ai/document_intelligence/core/ids.py:40-54`
- `packages/exeboard-ai/src/exeboard_ai/document_intelligence/core/ids.py:57-78`

**Finding:**

`make_page_id()` and `make_span_id()` use `:04d`, which means “minimum width 4”, not “exactly width 4”. For page/span indexes `>= 10000`, the maker emits `p10000` / `s10000`, but the parser regexes require exactly `\d{4}`. Therefore canonical IDs produced by the project’s own makers become unparsable by `parse_page_id()` / `parse_span_id()` and would be rejected by `DocumentIR` validation.

**Minimal fix:**

Either explicitly cap page numbers/span indexes at `9999`, or preferably make the parser match the maker’s actual canonical format:

```python
_PAGE_ID_PATTERN = re.compile(r"^(?P<document_id>[^:]+):p(?P<page_number>\d{4,})$")
_SPAN_ID_PATTERN = re.compile(
    r"^(?P<document_id>[^:]+):p(?P<page_number>\d{4,}):s(?P<span_index>\d{4,})$"
)
```

Keep rejecting unpadded `p1` / `s1`; accept `p0001` and `p10000`.

**Required tests:**

- `parse_page_id(make_page_id(DOCUMENT_ID, 10000)) == (DOCUMENT_ID, 10000)`
- `parse_span_id(make_span_id(DOCUMENT_ID, 1, 10000)) == (DOCUMENT_ID, 1, 10000)`
- Optional: verify unpadded manually supplied IDs still fail.

### NIT — Add a few direct guard tests for already-implemented validation paths

**Files/lines:**

- `packages/exeboard-ai/src/exeboard_ai/document_intelligence/ir/models.py:657-667`, `690-694`, `698-712`
- `tests/unit/document_intelligence/test_layout_models.py:229-237`, `255-288`

**Finding:**

The implementation validates all layout bounding-region pages and dimensions through the shared path, including table/cell/figure regions. Existing tests directly exercise block regions and indirectly rely on the shared code. For regression clarity before Docling starts producing real table/figure provenance, add direct tests for table, table-cell, and figure regions outside page bounds. Also add an explicit `NaN` unit test for `BoundingBox`; PyMuPDF tests cover `NaN` optional bboxes, while the unit test only checks `inf`.

**Minimal fix:**

Add targeted tests only; no model change required.

## 4. Requested-item verification

- **Canonical page/span IDs:** Mostly sound at the `DocumentIR` boundary. `DocumentIR` validates document UUID canonicalization and parses page/span IDs against document/page consistency (`models.py:439-481`). Duplicate page IDs, page numbers, and span IDs are rejected (`models.py:460-484`). Remaining low issue: maker/parser mismatch for IDs above four digits in `ids.py:10-13`, `40-54`, `57-78`.
- **Strict `BoundingBox` / `BoundingRegion` coordinate validation:** Good. `BoundingBox` is frozen, forbids extras, disallows non-finite coordinates, requires non-negative coordinates, and rejects inverted boxes (`models.py:97-116`). `BoundingRegion` forbids extras, requires positive page numbers, and now rejects zero-width/zero-height boxes (`models.py:119-131`). Parent `DocumentIR` enforces region page existence and page-dimension fit (`models.py:698-712`).
- **Zero-area region tradeoff:** Resolved correctly. `BoundingBox` still permits degenerate boxes for optional low-level text bboxes, while `BoundingRegion` requires positive area for visual/layout audit regions (`models.py:125-131`).
- **PyMuPDF invalid optional bbox handling:** Resolved. `_coerce_bbox()` rejects malformed/non-finite values (`pymupdf.py:195-206`), `_make_bounding_box()` drops inverted or negative optional bboxes instead of raising IR validation errors (`pymupdf.py:159-174`), and the integration test covers negative and `NaN` bboxes plus a top-edge generated PDF (`test_pymupdf_parser.py:159-172`).
- **Parser-port exception mapping:** Sufficient for this stage. Missing files are mapped to `UnreadableDocumentError` (`pymupdf.py:35-38`), open/data failures are mapped to `UnreadableDocumentError` (`pymupdf.py:105-109`), encrypted PDFs raise `EncryptedDocumentError` (`pymupdf.py:44-46`), and textless PDFs raise `NoExtractableTextError` (`pymupdf.py:73-77`). Parser-port layout/alignment errors exist for the upcoming Docling adapter (`ports.py:23-28`).
- **Table/cell/figure provenance and linkage:** Good. Table cells require text or visual provenance (`models.py:236-240`); table and figure wrappers require detail IDs (`models.py:188-197`); details link back through `layout_block_id` (`models.py:243-252`, `297-307`); `DocumentIR` enforces bidirectional table/figure wrapper matching and unique IDs (`models.py:638-696`); source spans are validated against document existence and page provenance (`models.py:538-577`, `714-734`).
- **Serialization JSON round-trip:** Covered. The layout-bearing round-trip test now asserts both `model_dump()`/`model_validate()` and `model_dump_json()`/`model_validate_json()` (`test_layout_models.py:800-850`).
- **Proceeding to Docling adapter:** Approved. The remaining ID-width edge and extra direct tests should be addressed soon, but they do not block starting the Docling adapter behind this IR contract.

## 5. Tests run

```bash
uv run --with pytest --package exeboard-ai pytest \
  tests/unit/document_intelligence/test_ir_models.py \
  tests/unit/document_intelligence/test_layout_models.py \
  tests/unit/document_intelligence/test_parser_ports.py \
  tests/integration/document_intelligence/test_pymupdf_parser.py
```

Result: **84 passed, 5 warnings**.

## 6. Required model fields/invariants now satisfied

- `DocumentIR.layout` remains optional for text-only flows.
- `DocumentLayout.parser_run_id` must reference an existing `ParserRun`; duplicate parser run IDs are rejected.
- `DocumentLayout.blocks` is required and non-empty.
- `LayoutBlock.reading_order` is a single deterministic namespace; duplicate block reading orders are rejected.
- Text-bearing blocks must cite source spans.
- Layout span references must exist, belong to the same document, and be page-consistent with layout provenance.
- Visual-only figures can be represented with bounding regions without fake spans.
- Table cells preserve row/column indices, positive spans, roles, source spans, and/or bounding regions.
- Tables and figures attach to wrapper blocks and enforce bidirectional ID/type consistency.
- Layout models reject extra duplicate text/vendor-object fields.
- PyMuPDF remains a native-text parser: no OCR, no table/layout IR, explicit warnings/errors for textless pages/documents.

## 7. Deferred/future concerns

- Consider wrapping `load_page()` / `get_text()` failures in `UnreadableDocumentError` if real-world corrupt PDFs expose raw PyMuPDF exceptions after open succeeds.
- Consider tuple-izing mutable lists in frozen models (`ParserRun.warnings`, `Page.spans`, `DocumentIR.parser_runs`, `DocumentIR.pages`) before using these objects across trust/persistence boundaries.
- Consider restricting `heading_level` to heading-like block types if downstream semantics assume that.
- Consider rejecting overlap between `Figure.source_span_ids` and `Figure.caption_span_ids` only if downstream treats those as disjoint evidence roles.
