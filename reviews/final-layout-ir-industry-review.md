# Final Layout IR Industry Review

## Verdict

**Approval: APPROVED WITH MUST-HAVE GUARDS.** The next step is ready to implement **only as layout IR models + unit tests**, with no Docling adapter code yet. The patched plan is aligned with current industry practice: keep a canonical text string/spans as provenance source of truth, then add layout/table/figure structures that reference those spans and page regions.

## Remaining blockers in the plan

1. **No blocking architecture issue for this step.** The current boundaries are correct: `DocumentParser.parse(path) -> DocumentIR`, PyMuPDF remains a native-text baseline, and the span chunker remains span-only.
2. **Coordinate policy must be explicit in the models/tests.** Azure and Google return polygons and units that differ from PyMuPDF; Exeboard can use the existing `BoundingBox` for v1, but tests must enforce that it is a normalized `pdf_points_top_left` rectangle/envelope, not raw vendor coordinates.
3. **Parser-port layout failures are a blocker for the later adapter step, not this model step.** Do not start Docling until `LayoutExtractionError` / `SpanAlignmentError` exist.

## Must-have model requirements

1. Add `DocumentIR.layout: DocumentLayout | None = None`; `DocumentIR` without layout must remain valid.
2. New layout models should be Exeboard-owned Pydantic v2 models, frozen, and preferably `extra="forbid"` to prevent accidental duplicate text or vendor-object leakage.
3. `DocumentLayout` must carry `layout_version`, `parser_run_id`, `blocks`, optional `tables`, optional `figures`; `parser_run_id` must resolve to an existing `ParserRun`.
4. Reject duplicate `parser_run_id`s in `DocumentIR.parser_runs` before layout depends on them.
5. `LayoutBlock` must provide the single deterministic `reading_order` namespace; duplicate block reading orders are invalid.
6. Block IDs, table IDs, and figure IDs must be non-empty and unique.
7. Text-bearing blocks/cells/figures must reference existing `SpanId`s from the same `DocumentIR`; visual-only figures must use page/bbox provenance without fake spans.
8. Support multi-page/non-contiguous objects via `page_numbers` plus `bounding_regions`.
9. Parent block references must exist; self-parenting and cycles must be rejected.
10. `ContentLayer` must include at least `body`, `furniture`, `background`, `invisible`, `notes`, and `unknown`.
11. `LayoutBlockType` must represent headings, paragraphs, lists/list items, tables, figures, captions, footnotes, headers, footers, page numbers, sections/title, and unknown.
12. Tables must preserve `row_count`, `column_count`, `row_index`, `column_index`, positive row/column spans, roles, span provenance, and bounding-region provenance.
13. `Table.layout_block_id` must reference an existing wrapper block with `block_type="table"`; wrapper block and detailed table must link consistently.
14. Table cells must not extend beyond table bounds; overlapping/duplicate cell positions should be rejected unless deliberately modeled.
15. Figures must preserve figure region, source spans, and caption spans separately; `Figure.layout_block_id` must reference a wrapper block with `block_type="figure"`.
16. No authoritative duplicate `text` fields in `LayoutBlock` or `TableCell` for the first implementation.

## Must-have tests

1. Existing PyMuPDF parser and span chunker flows still pass with `layout=None`.
2. Valid layout can attach to a simple `DocumentIR` and reference existing spans.
3. Missing, invalid, duplicate, or cross-document span references are rejected.
4. Duplicate parser run IDs and layout parser_run references to missing parser runs are rejected.
5. Duplicate block reading orders are rejected.
6. Duplicate block/table/figure IDs are rejected.
7. Missing parent, self-parent, and cyclic parent block graphs are rejected.
8. Header/footer/page-number furniture can be represented without being labeled as body.
9. Visual-only figures with bounding regions and no spans are valid; figures with neither spans nor regions are invalid.
10. Table cells preserve headers/roles and reject out-of-bounds row/column spans.
11. Cross-page table/section/figure regions can be represented.
12. Coordinate-system normalization is asserted for layout bounding regions.
13. Extra `text`/vendor-object fields on layout models are rejected.

## What breaks if these are shortcut

- Bad span validation breaks citations and quote validation because layout could cite text that is absent or from another document.
- Duplicate/competing reading order makes future layout-aware chunking nondeterministic.
- Flattened tables lose row/column/header context, making financial or operational claims hard to audit.
- Missing furniture labels causes repeated headers/footers/page numbers to be summarized as business content.
- Fake spans for figures let derived visual descriptions masquerade as source text.
- Unspecified coordinate systems produce wrong highlights on rotated pages and make cloud/PyMuPDF adapter output incomparable.
- Parent cycles can break traversal/chunking with infinite loops.
- Duplicate authoritative text creates divergence from `DocumentIR.content`, undermining the existing citation substrate.

## Source links

- Azure Document Intelligence Analyze Response: spans, top-level content, reading order, bounding regions, tables, figures, sections. <https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept/analyze-document-response?view=doc-intel-4.0.0>
- Azure Layout model: roles, tables, figures, sections. <https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/prebuilt/layout?view=doc-intel-4.0.0>
- DoclingDocument concept: body/furniture, hierarchy, tables, pictures, bounding boxes, provenance. <https://docling-project.github.io/docling/concepts/docling_document/>
- DoclingDocument reference: `DoclingDocument`, `TableItem`, `PictureItem`, `ProvenanceItem`, content layers. <https://docling-project.github.io/docling/reference/docling_document/>
- Google Document AI / Gemini layout parser: hierarchy, tables/figures, layout-aware chunks for RAG. <https://cloud.google.com/document-ai/docs/layout-parse-chunk>
- Google Document AI response handling: source text as truth, `textAnchor`, bounding polygons, top-left origin. <https://cloud.google.com/document-ai/docs/handle-response>
- Unstructured partitioning strategies: fast vs hi_res vs ocr_only separation. <https://docs.unstructured.io/open-source/concepts/partitioning-strategies>
- PyMuPDF text extraction reading order and `sort=True` behavior. <https://pymupdf.readthedocs.io/en/latest/app1.html>
- PyMuPDF OCR behavior and cost. <https://pymupdf.readthedocs.io/en/latest/recipes-ocr.html>
- PyMuPDF table detection API. <https://pymupdf.readthedocs.io/en/latest/page.html#Page.find_tables>
