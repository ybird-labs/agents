# Layout IR + PDF Parsing Expert Review

## Verdict

**APPROVE the next implementation step: build Exeboard-owned layout IR models and tests before any Docling adapter code.** The sequencing is correct: current `DocumentIR -> Page -> TextSpan` is a valid citation substrate, but the layout layer must be finalized and validated before mapping Docling structures into it.

**Reject the current model sketch as an exact implementation shape unless the corrections below are applied.** The current strategy is directionally aligned with Azure Document Intelligence, Docling, Google Document AI/Gemini Layout Parser, PyMuPDF, and Unstructured, but the first implementation needs stronger validation around cross-object reading order, parser-run provenance, table cell roles, parent/section hierarchy for tables and figures, coordinate policy, and span alignment.

## Standards comparison relevant to this step

1. **Span-backed canonical content is the right backbone.** Azure Analyze Result exposes top-level `content` in reading order and makes elements point into it via spans; those spans are character offsets/lengths into the top-level content string. This matches Exeboard’s existing `DocumentIR.content` and `TextSpan.char_start/char_end` invariant. [Azure Analyze response](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept/analyze-document-response?view=doc-intel-4.0.0)
2. **Bounding regions must be multi-region and page-aware.** Azure uses arrays of `boundingRegions` for visually non-contiguous or cross-page elements, each with a page number and polygon. The strategy’s `page_numbers + bounding_regions` direction is correct; a single page/bbox per object is not production-safe. [Azure Analyze response](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept/analyze-document-response?view=doc-intel-4.0.0)
3. **Body/furniture separation is not optional.** Docling’s `DoclingDocument` explicitly separates body and furniture and carries `content_layer`; Docling Core supports `body`, `furniture`, `background`, `invisible`, and `notes`. The first Exeboard model should not collapse all non-body content to only `unknown`. [DoclingDocument](https://docling-project-docling.mintlify.app/concepts/docling-document), [Docling Core model](https://github.com/docling-project/docling-core/blob/main/docling_core/types/doc/document.py)
4. **Table semantics require more than `is_header`.** Azure differentiates general content, row header, column header, stub head, description, captions, and footnotes; Docling table cells carry row/column offsets, spans, `column_header`, `row_header`, and `row_section`. Exeboard table cells need explicit roles, row/column indices, row/column spans, and validation against table dimensions. [Azure Analyze response](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept/analyze-document-response?view=doc-intel-4.0.0), [Docling Core model](https://github.com/docling-project/docling-core/blob/main/docling_core/types/doc/document.py)
5. **Generated visual descriptions are derived annotations, not source evidence.** Google’s Gemini layout parser can verbalize figures/tables and use annotations in RAG chunks, but those annotations are generated. Exeboard must mark derived descriptions non-authoritative unless backed by citeable spans. [Google Gemini layout parser](https://cloud.google.com/document-ai/docs/layout-parse-chunk)
6. **PyMuPDF baseline remains correctly scoped.** PyMuPDF says plain extraction follows original creator order and may not equal natural reading order; `sort=True` reorders top-left to bottom-right, not semantic reading order. PyMuPDF also supports OCR via Tesseract and `find_tables()`, but those are distinct capabilities and should not silently change the existing fast native-text adapter. [PyMuPDF text extraction](https://pymupdf.readthedocs.io/en/latest/app1.html), [PyMuPDF OCR](https://pymupdf.readthedocs.io/en/latest/recipes-ocr.html)
7. **Strategy separation is industry-normal.** Unstructured separates `fast`, `hi_res`, and `ocr_only` PDF strategies because native extraction, layout inference, and OCR have different quality/speed/cost profiles. Exeboard should preserve that separation in parser provenance and errors. [Unstructured partitioning strategies](https://docs.unstructured.io/open-source/concepts/partitioning-strategies)

## Model-shape corrections for the first implementation

1. **Add `DocumentIR.layout: DocumentLayout | None` now, not a detached parse result.** The parser port is already `parse(path: Path) -> DocumentIR`, and tutorial state says invalid IR should not exist. A detached `DocumentLayout` cannot validate span references without the parent document. Put attachment validation in `DocumentIR`’s model validator or in a required constructor that returns a validated `DocumentIR`; the cleaner first implementation is `DocumentIR.layout`.

2. **Use immutable collections for layout models.** Current IR uses mutable `list` fields inside frozen Pydantic models. For new layout models, use `tuple[...]` for `blocks`, `tables`, `figures`, `cells`, `bounding_regions`, `source_span_ids`, and caption refs so post-validation mutation cannot invalidate layout invariants.

3. **Make parser-run linkage enforceable.** `DocumentLayout.parser_run_id` must reference an existing `ParserRun.parser_run_id`. Also add a `DocumentIR` validation guard for duplicate `parser_run_id`s before layout depends on them.

4. **Use one deterministic reading-order namespace.** Either add a single ordered `items` collection or enforce uniqueness of `reading_order` across all top-level layout objects: blocks + tables + figures. Do not allow block `reading_order=5` and table `reading_order=5` in the same document layout.

5. **Do not represent tables and figures twice.** Remove `table` and `figure` from `LayoutBlockType` unless a `LayoutBlock` only acts as a wrapper that references a `table_id`/`figure_id`. Preferred first implementation: keep specialized `Table` and `Figure` models and keep `LayoutBlockType` focused on text/structure: `section`, `title`, `heading`, `paragraph`, `list`, `list_item`, `caption`, `footnote`, `header`, `footer`, `page_number`, `unknown`.

6. **Let tables and figures attach to hierarchy.** Add `parent_block_id: str | None` to `Table` and `Figure`, not only to `LayoutBlock`. Azure sections attach paragraphs, tables, and figures; Docling hierarchy has parent/child references. Exeboard must be able to place a table under a section without inventing a fake paragraph block.

7. **Add heading/section level.** Add `level: int | None` or `heading_level: int | None` for heading/section blocks. Google and Docling expose hierarchy; Azure emits section structure and section-heading roles.

8. **Expand `ContentLayer`.** Use at least: `body`, `furniture`, `background`, `invisible`, `notes`, `unknown`. This maps Docling without immediate loss and still supports the strategy’s body/furniture requirement.

9. **Strengthen table cell shape.** Add `row_count` and `column_count` to `Table`; validate every `TableCell` is within bounds. Replace `is_header: bool` with roles, e.g. `cell_roles: tuple["content" | "row_header" | "column_header" | "stub_head" | "description" | "row_section" | "unknown", ...]`. Validate `row_span >= 1`, `column_span >= 1`, non-negative indices, and no duplicate/overlapping simple cell coverage unless explicitly represented by spans.

10. **Make convenience text non-authoritative unless exactly backed by spans.** If `LayoutBlock.text` or `TableCell.text` is stored, `DocumentIR` validation must check that it equals reconstruction from `source_span_ids` for text-backed objects. If the text is generated, normalized, verbalized, or cannot be exactly reconstructed, it needs an explicit non-authoritative annotation field instead of pretending to be source text.

11. **Represent visual-only figures without fake spans.** `Figure.bounding_regions` must be non-empty. `source_span_ids` may be empty. `caption_span_ids` should be separate from figure/body spans. `derived_description` must default to non-authoritative and should carry `created_by`/model provenance if present.

12. **Add optional parser-native element references, not parser-native objects.** Add fields such as `parser_element_ref: str | None` on layout objects for Docling JSON pointers or Azure element IDs. This aids debugging and adapter traceability without leaking Docling objects into downstream APIs.

13. **Coordinate policy must be encoded in `BoundingRegion`.** Existing `BoundingBox.coordinate_system = "pdf_points_top_left"` is acceptable as the normalized target, but `BoundingRegion` should support multi-region provenance and ideally optional polygon points. Azure returns polygons; PyMuPDF rotated text may need quads; Docling can carry different coordinate origins. If polygons are not added in the first patch, tests must assert that the model deliberately stores normalized axis-aligned boxes only and parser provenance records that polygon/quad detail was dropped.

14. **Validate parent references and cycles.** If `parent_block_id` exists, it must refer to an existing block in the same layout. Reject self-parenting and cycles.

15. **Keep legacy span chunking explicitly span-only.** Adding `DocumentIR.layout` must not change `chunk_document`; add a regression test proving the existing chunker output is unchanged for a document that has layout.

## Must-have test cases before Docling adapter code

1. `DocumentIR` without layout remains valid and existing PyMuPDF/chunker tests remain unchanged.
2. Valid layout with a paragraph block referencing existing same-document spans passes.
3. Layout referencing a missing span ID is rejected.
4. Layout referencing a span ID from another document is rejected.
5. Layout object `page_numbers` and `bounding_regions.page_number` must correspond to referenced span pages and existing document pages.
6. `DocumentLayout.parser_run_id` must reference an existing parser run; duplicate parser run IDs are rejected.
7. Duplicate layout object IDs are rejected across blocks/tables/figures.
8. Duplicate top-level `reading_order` values across blocks/tables/figures are rejected.
9. Reading order is deterministic after serialization/round trip.
10. Text-bearing block types (`title`, `heading`, `paragraph`, `list_item`, `caption`, `header`, `footer`, `page_number`, `footnote`) require source spans unless explicitly allowed as structural/unknown.
11. Structural `section` block can be represented without source spans but can parent child blocks/tables/figures.
12. Parent block reference must exist; self-parent and cycles are rejected.
13. `ContentLayer` accepts `body`, `furniture`, `background`, `invisible`, `notes`, and `unknown`; header/footer/page-number blocks can be furniture.
14. A visual-only figure with bounding region and no spans is valid.
15. Figure caption spans are validated separately from visual figure provenance.
16. Figure `derived_description` defaults to non-authoritative; authoritative generated descriptions are rejected unless backed by source spans.
17. Table with `row_count`, `column_count`, cells, row/column indices, row/column spans, and header roles is valid.
18. Table cells with out-of-bounds row/column indices or spans are rejected.
19. Merged table cells preserve row/column span and roles.
20. Table cell text, when present and source-backed, must equal reconstruction from referenced spans; mismatch is rejected.
21. Empty table cells may have empty span refs if they have explicit cell position/region provenance.
22. Cross-page/non-contiguous table is valid via multiple `page_numbers` and multiple `bounding_regions`.
23. Cross-page/non-contiguous section is valid via multiple regions/pages.
24. Bounding region page number must exist in `DocumentIR.pages`.
25. Inverted bboxes remain rejected; if polygon support is added, polygons with invalid point counts/coordinates are rejected.
26. Layout attachment cannot mutate into invalid state after construction; prefer tuple immutability tests.
27. Legacy `chunk_document(document)` ignores layout and still produces text chunks based on span order.

## Parser provenance and span-alignment requirements before Docling

1. **Add parser-port failure types before the Docling adapter.** At minimum: `LayoutExtractionError` and `SpanAlignmentError`. Keep OCR-required behavior explicit via `NoExtractableTextError` or a dedicated `OcrRequiredError`; do not silently OCR.
2. **Extend parser provenance beyond free-form warnings.** `ParserRun` should record actual strategy (`native_text`, `layout`, `ocr`, `vlm`, `cloud`), parser/library versions, model/artifact versions where known, OCR enabled/used pages, coordinate normalization policy, and fallback decisions. Free-form `warnings` are not enough for production audit.
3. **Docling must build citeable spans from the same text basis used for layout mapping.** Best path: build `DocumentIR.content` from the Docling traversal/export that layout items are aligned to. Alternate path: deterministic alignment from Docling item/cell text and `prov.charspan` into Exeboard `TextSpan`s. If exact alignment fails, raise `SpanAlignmentError` or emit explicit per-object warnings and mark affected layout text non-authoritative.
4. **Do not reuse PyMuPDF line-level spans for Docling table cells.** Current PyMuPDF spans are line-level. A table row line can contain multiple cells, so citing the whole line for each cell would overstate provenance. The Docling adapter must create spans granular enough for cell/paragraph/caption evidence or must fail cell-level span alignment.
5. **All text-bearing layout objects must resolve to existing `SpanId`s in the same `DocumentIR`.** No Docling `charspan`, JSON pointer, or table-cell text should bypass Exeboard `TextSpan` validation.
6. **Visual-only objects must use bounding regions, not fake spans.** Figures, images, and empty table cells can be provenance-valid with page/bbox only.
7. **Partial/normalized text must be explicit.** If Docling sanitized text differs from original text, store the sanitized/generated value only as a derived/non-authoritative annotation unless exact source text remains available through spans.
8. **Record unaligned counts.** Parser output/provenance should include counts of layout objects, tables, cells, captions, and figures that had no alignable spans, plus whether the parse was accepted with warnings or failed.

## Production risks for this step

1. **Axis-aligned bbox-only provenance can be insufficient.** Azure returns polygons and PyMuPDF exposes rotated-text quads. If Exeboard stores only rectangles, highlighting may be approximate on rotated/skewed content.
2. **Line-level spans are too coarse for table evidence.** This is the highest immediate Docling risk. The layout IR must permit precise cell-level span references; the adapter must generate them.
3. **ParserRun is currently under-modeled.** Without structured strategy/model/OCR/fallback provenance, layout-aware parse results will not be auditable.
4. **Global reading order can be overclaimed.** Azure explicitly notes limitations around reading order across page boundaries. Exeboard can require deterministic order, but tests should not imply semantic perfection for ambiguous cross-page layouts.
5. **Generated image/table descriptions can pollute evidence.** Google-style verbalized annotations are useful for retrieval, but they are not source text. Treat them as derived and non-authoritative by default.
6. **Docling schema/version drift is real.** Store Docling and docling-core versions and parser-native element refs so adapter bugs can be reproduced.
7. **Coordinate normalization can silently break UI highlighting.** Page rotation, cropbox/mediabox differences, Docling coordinate origins, and PDF point units must be normalized or explicitly recorded before downstream UI relies on bboxes.
8. **Mutable model fields can invalidate invariants after validation.** New layout fields should use tuples even if legacy IR still uses lists.

## Sources kept

- Azure Document Intelligence Analyze Response — spans, bounding regions, paragraphs, tables, figures, sections, roles: https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept/analyze-document-response?view=doc-intel-4.0.0
- DoclingDocument concepts — body/furniture, hierarchy, tables, pictures, provenance: https://docling-project-docling.mintlify.app/concepts/docling-document
- Docling Core document model — `ProvenanceItem`, `ContentLayer`, `TableCell`, `TableData`, `PictureItem`, `TableItem`: https://github.com/docling-project/docling-core/blob/main/docling_core/types/doc/document.py
- Google Document AI/Gemini layout parser — layout-aware hierarchy, chunks, table/figure annotations, limitations: https://cloud.google.com/document-ai/docs/layout-parse-chunk
- PyMuPDF text extraction details — original order vs natural order, `sort=True`, dict structure: https://pymupdf.readthedocs.io/en/latest/app1.html
- PyMuPDF OCR docs — Tesseract OCR support and cost/behavior: https://pymupdf.readthedocs.io/en/latest/recipes-ocr.html
- Unstructured partitioning strategies — explicit `fast`, `hi_res`, `ocr_only` strategy separation: https://docs.unstructured.io/open-source/concepts/partitioning-strategies

## Sources dropped

- Generic blog/SEO parser comparisons — excluded because official vendor/library docs provided direct model and capability evidence.
- Azure SDK class mirrors — redundant with the conceptual Analyze Response documentation for this review.
