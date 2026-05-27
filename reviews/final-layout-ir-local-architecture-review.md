## Review

**Final decision: APPROVED for the next implementation step only — adding Exeboard-owned layout IR models + tests.**  
**Rejected for this step:** any Docling adapter code, layout-aware chunking, OCR fallback, or PyMuPDF table/layout upgrades.

Note: I did not write `/Users/jeancarlobarrios/Developing/exeboard/ai/reviews/final-layout-ir-local-architecture-review.md` because the task also says “Do not modify files.” No files were changed.

- Correct:
  - The plan preserves the parser boundary: `DocumentParser.parse(path: Path) -> DocumentIR` is the stable port in `parsing/ports.py:23-24`, matching the tutorial state at `docs/document-intelligence/tutorial-state.md:26-27`.
  - The proposed `DocumentIR.layout: DocumentLayout | None` is compatible with current text-only flows because existing `DocumentIR` fields are unchanged and layout can default to `None` (`ir/models.py:125-133`).
  - The architecture keeps `TextSpan` as the citation source of truth, consistent with current IR validation of canonical content offsets at `ir/models.py:163-169` and the strategy at `pdf-parsing-strategy.md:269-275`.
  - Current PyMuPDF behavior is explicitly text-only: it creates spans and parser provenance but no layout (`pymupdf.py:75-88`), uses coordinate-sorted text extraction (`pymupdf.py:116`), warns on partially textless PDFs without OCR (`pymupdf.py:69-73`), and raises parser-port errors for encrypted/unreadable/no-text cases (`pymupdf.py:40-42`, `101-105`).
  - Current chunking and validation are span-based and should remain so for this step: `chunk_document` sorts spans by `(page_number, reading_order)` (`chunker.py:46-48`), and citation validation only checks `SpanIndex` references (`citation_validator.py:93-144`).
  - Baseline tests currently pass: `147 passed` for `uv run --package exeboard-ai --with pytest pytest tests/unit/document_intelligence tests/integration/document_intelligence`.

- Fixed:
  - None. Review-only; no modifications applied.

- Blocker:
  - **No blocker for the IR-only step if the constraints below are followed.**
  - **Blocker before any Docling adapter:** add and test layout-specific parser-port errors:
    - `LayoutExtractionError(DocumentParseError)`
    - `SpanAlignmentError(DocumentParseError)`
    This is required by `pdf-parsing-strategy.md:414-423`. Using `UnreadableDocumentError` or `NoExtractableTextError` for layout/alignment failures would collapse distinct retry/audit decisions and break parser-strategy selection.

- Note: exact implementation constraints:
  1. Add layout under the IR boundary only. Do not import Docling, PyMuPDF, parser adapters, chunking, summarization, validation, or `SpanIndex` into layout models.
  2. Avoid circular imports:
     - Preferred safe shape: put shared geometry such as `BoundingBox` / `CoordinateSystem` in a neutral IR module and re-export as needed; or keep first-pass layout models in `ir/models.py`.
     - Do **not** create `ir/layout.py` that imports `DocumentIR` while `DocumentIR` imports `DocumentLayout`.
  3. `DocumentIR.layout` must be optional and default to `None`; existing PyMuPDF/parser/chunker tests must not need layout.
  4. `DocumentIR` must validate layout cross-references when layout is present:
     - layout `parser_run_id` exists in `parser_runs`;
     - duplicate `parser_run_id`s are rejected before layout lookup;
     - referenced `SpanId`s exist in the same `DocumentIR`;
     - referenced span pages are included in the relevant block/table/figure page provenance.
  5. Keep one reading-order namespace:
     - only `LayoutBlock.reading_order`;
     - reject duplicate block reading orders;
     - do not add independent `reading_order` fields to `Table`, `TableCell`, or `Figure`.
  6. Table/figure linkage must be bidirectional and validated:
     - `Table.layout_block_id` points to a block with `block_type="table"`;
     - the wrapper block’s `table_id` matches the table;
     - same rule for `Figure` / `figure_id`;
     - non-table blocks cannot carry `table_id`; non-figure blocks cannot carry `figure_id`.
  7. Table cells must enforce production semantics:
     - `row_count` / `column_count` positive;
     - row/column indices non-negative;
     - row/column spans positive;
     - cells cannot exceed table bounds;
     - overlapping cell coverage should be rejected unless a future explicit covered-cell model is added.
  8. Visual-only figures are valid only with explicit bounding-region provenance. Do not fabricate spans.
  9. Do not add authoritative duplicate `text` fields to `LayoutBlock` or `TableCell`.
  10. Coordinate policy must use the existing normalized `BoundingBox` policy or explicit coordinate metadata. Do not store parser-native coordinate blobs as production IR.

- Note: must-have tests:
  - `DocumentIR` without layout remains valid.
  - PyMuPDF-parsed documents have `layout is None` and existing PyMuPDF integration tests still pass.
  - Duplicate `parser_run_id`s are rejected.
  - `DocumentLayout.parser_run_id` must reference an existing `ParserRun`.
  - Missing/cross-document/nonexistent span IDs in blocks, cells, figures, or captions are rejected.
  - Referenced span pages must match block/table/figure provenance.
  - Duplicate block IDs and duplicate block reading orders are rejected.
  - Parent references: missing parent, self-parent, and cycles are rejected.
  - Content layers include `body`, `furniture`, `background`, `invisible`, `notes`, `unknown`.
  - Header/footer/page-number furniture can be represented without marking it as body.
  - Table linkage, table bounds, duplicate/overlapping cells, cell roles, and merged-cell spans are tested.
  - Figure linkage, caption spans, visual-only figures, and figure-without-spans-or-regions rejection are tested.
  - Cross-page/non-contiguous blocks/tables/figures are representable.
  - `chunk_document` remains span-based and unaffected by optional layout.
  - Parser-port tests are extended for `LayoutExtractionError` and `SpanAlignmentError` before any adapter work.

Architectural defers:
- Do **not** implement layout-aware chunking now. The current chunker is explicitly span-based (`chunker.py:7-34`); retrofitting it would blur legacy text-only behavior. Add a separate layout-aware chunker later, as the strategy requires at `pdf-parsing-strategy.md:444-455`.
- Do **not** add Docling now. Without validated layout IR and layout/alignment parser errors, the adapter would either leak Docling-native objects or flatten structure, both rejected by the strategy at `pdf-parsing-strategy.md:326-330`.
- Do **not** change PyMuPDF into a layout/OCR parser. That would violate its current role as the fast native-text baseline and risk regressions to the existing parser tests.