# PDF Parsing Strategy for Evidence-Backed Summarization

Last updated: 2026-05-25

Status: architecture decision and implementation plan. This document does not change runtime behavior yet.

## Design checkpoint before code changes

Layer: Parsing + IR layout extension.

Responsibility: Convert a source PDF into citeable text spans plus explicit document layout structures that preserve reading order, body/furniture boundaries, tables, figures, and provenance.

Options:

1. Keep only `PyMuPDFParser` text extraction.
2. Replace `DocumentIR` with a parser/vendor object such as Docling's native document model.
3. Keep `DocumentIR` as the canonical citation substrate and add a layout layer that references existing `SpanId`s.
4. Use cloud layout parsers such as Azure Document Intelligence or Google Document AI as primary adapters.

Recommendation: Use option 3. Keep `DocumentIR.content`, `Page`, and `TextSpan` as the citation source of truth. Add layout models under the document-intelligence IR boundary. Add a Docling-backed parser adapter candidate that populates both citeable spans and layout objects. Keep `PyMuPDFParser` as the fast native-text baseline.

Rejected shortcuts that justify the layout-aware adapter decision: Treating `PyMuPDF` `sort=True` output as semantic reading order, flattening table cells into prose, silently OCRing inside `PyMuPDFParser`, or asking an LLM to infer missing layout from broken extracted text. These are not alternative recommendations; they are the concrete failure modes the Docling/layout-aware adapter is being introduced to avoid.

Memory/test guard: Text-bearing layout objects must reference existing `SpanId`s from the same `DocumentIR`; visual-only objects must use explicit page/bounding-region provenance without fake spans; table cells must preserve row/column indices; reading order must be explicit and deterministic; body/furniture labels must be representable; layout/OCR/span-alignment failure modes must be explicit parser-port failures or warnings, not hidden behavior changes.

## Problem statement

Evidence-backed summarization is only as reliable as the provenance substrate it summarizes over.

The current component has a solid low-level IR:

```text
DocumentIR -> Page -> TextSpan
```

That is enough to cite digital text spans and validate whether a claim references real spans. It is not enough to reliably summarize complex PDFs because many business PDFs are not a simple top-to-bottom stream of lines. They include multi-column layouts, repeated headers/footers, tables, captions, callouts, figures, footnotes, and reading-order discontinuities.

For those documents, a summary pipeline that consumes raw extracted lines can be wrong even when every citation points to a real span. The citation can be syntactically valid while the generated claim is semantically distorted by bad ordering or lost table structure.

Production requirement:

```text
PDF
  -> low-level text/token extraction
  -> layout analysis
  -> reading-order reconstruction
  -> table/figure/header/footer detection
  -> structured document IR with provenance
  -> layout-aware chunking
  -> summarization over structure, not raw lines
```

## Industry research summary

The industry pattern is not “extract text with a coordinate sort and hope.” Production document-intelligence systems return structured layout and provenance.

Sources reviewed:

- PyMuPDF documentation: plain text extraction may not reflect natural reading order, and `sort=True` is a coordinate-order heuristic rather than semantic layout reconstruction. Source: <https://pymupdf.readthedocs.io/>
- Azure Document Intelligence Analyze Result: returns document content with spans plus pages, lines, paragraphs, tables, figures, sections, bounding regions, and semantic roles. Source: <https://learn.microsoft.com/azure/ai-services/document-intelligence/concept/analyze-document-response>
- Google Document AI / Gemini layout parsing: designed for RAG-style document understanding with layout-aware chunks and preservation of headings, tables, figures, and lists. Sources: <https://cloud.google.com/document-ai> and <https://cloud.google.com/document-ai/docs/parse-layout>
- Docling: exposes a unified `DoclingDocument` with text, tables, pictures, key-value items, document hierarchy, body/furniture grouping, layout bounding boxes, and provenance including page/bbox/char-span information. Source: <https://github.com/docling-project/docling>
- Unstructured `partition_pdf`: exposes explicit parsing strategies such as `fast`, `hi_res`, `ocr_only`, and `auto`, reinforcing that native text extraction, layout analysis, and OCR are distinct strategies with different tradeoffs. Source: <https://docs.unstructured.io/open-source/core-functionality/partitioning>
- pdfplumber and Camelot: useful specialized tools for coordinates and tables, but they are better considered targeted extraction/table tools than the primary general layout-aware parser for this component right now. Sources: <https://github.com/jsvine/pdfplumber> and <https://camelot-py.readthedocs.io/>

## Parser roles

### `PyMuPDFParser`

Role: fast native digital-text baseline adapter.

Keep it because it is valuable for simple digital PDFs and deterministic tests:

- Low dependency footprint.
- Fast local parsing.
- Good source text and bbox extraction for simple layouts.
- Clear parser-port errors for encrypted, unreadable, and textless PDFs.

Limit this Exeboard adapter explicitly:

- The current `PyMuPDFParser` configuration does not reconstruct semantic reading order.
- The current `PyMuPDFParser` does not expose table IR, even though the PyMuPDF library has table-related APIs such as table detection.
- The current `PyMuPDFParser` does not classify body text versus repeated page furniture.
- The current `PyMuPDFParser` does not invoke PyMuPDF/Tesseract OCR, even though the PyMuPDF library can be used with OCR workflows.
- It should not silently upgrade itself into a layout/table/OCR parser because that hides cost, latency, privacy, and accuracy changes behind a parser that callers selected for native text.

This distinction matters: we are not claiming PyMuPDF-the-library cannot do tables or OCR. We are defining this adapter as a fast native-text baseline. If we later want PyMuPDF table detection or OCR, that should be a separate explicit adapter/strategy with its own provenance, tests, and failure modes.

### `DoclingParser`

Role: recommended layout-aware adapter candidate.

Docling is the best next local adapter candidate because it is built around a document representation rather than only text extraction. It can provide hierarchy, layout, tables, pictures, provenance, and OCR-capable workflows behind an explicit adapter.

The component should not expose Docling-native objects to chunking, validation, or summarization. The adapter should translate Docling output into Exeboard-owned IR models.

### Future OCR adapter or strategy

Role: explicit OCR/layout-heavy parsing path.

OCR must be explicit. It may be implemented as a dedicated adapter or as an explicit parser strategy selected by composition code, for example:

```text
NativeTextPyMuPDFParser
DoclingLayoutParser
OcrLayoutParser
CloudDocumentIntelligenceParser
```

The key rule is that callers must know when OCR is in play. OCR changes latency, cost, data-handling constraints, confidence profile, and failure modes. Silent fallback would make the same parser call behave differently for different files in ways downstream tests and audit logs cannot reliably explain.

## IR implications

Current `DocumentIR` is intentionally minimal:

```text
DocumentIR
  source
  parser_runs
  content
  pages[]
    spans[]
```

This is enough for:

- stable document IDs
- page IDs
- citeable span IDs
- canonical text offsets
- page-level span lookup
- citation validation
- quote validation against cited text

It is not enough for:

- sections and heading hierarchy
- body text versus furniture such as headers, footers, page numbers, watermarks, and repeated boilerplate
- tables, table cells, merged cells, row/column relationships, and header rows
- figures, captions, and figure references
- deterministic layout-level reading order across pages and blocks
- layout-aware chunking that keeps tables intact and avoids chunking headers/footers as business content

## Recommended design

Add a layout layer that references existing `SpanId`s for text-bearing content and explicit page/bounding-region provenance for visual content instead of replacing `DocumentIR`.

Preferred direction:

```text
DocumentIR
  content
  pages[]
    spans[]               # citation source of truth
  layout: DocumentLayout? # optional structured organization over spans
```

Possible model sketch:

```python
LayoutBlockType = Literal[
    "section",
    "title",
    "heading",
    "paragraph",
    "list",
    "list_item",
    "table",
    "figure",
    "caption",
    "footnote",
    "footer",
    "header",
    "page_number",
    "unknown",
]

ContentLayer = Literal[
    "body",
    "furniture",
    "background",
    "invisible",
    "notes",
    "unknown",
]

TableCellRole = Literal[
    "content",
    "row_header",
    "column_header",
    "stub_head",
    "description",
    "row_section",
    "unknown",
]

class BoundingRegion(BaseModel):
    page_number: int
    bbox: BoundingBox

class DocumentLayout(BaseModel):
    layout_version: str
    parser_run_id: str
    blocks: tuple[LayoutBlock, ...]
    tables: tuple[Table, ...] = ()
    figures: tuple[Figure, ...] = ()

class LayoutBlock(BaseModel):
    block_id: str
    block_type: LayoutBlockType
    content_layer: ContentLayer
    page_numbers: tuple[int, ...]
    reading_order: int
    source_span_ids: tuple[SpanId, ...] = ()
    bounding_regions: tuple[BoundingRegion, ...] = ()
    parent_block_id: str | None = None
    heading_level: int | None = None
    table_id: str | None = None
    figure_id: str | None = None
    parser_element_ref: str | None = None

class Table(BaseModel):
    table_id: str
    layout_block_id: str
    row_count: int
    column_count: int
    cells: tuple[TableCell, ...]
    bounding_regions: tuple[BoundingRegion, ...] = ()
    parser_element_ref: str | None = None

class TableCell(BaseModel):
    row_index: int
    column_index: int
    row_span: int = 1
    column_span: int = 1
    roles: tuple[TableCellRole, ...] = ("content",)
    source_span_ids: tuple[SpanId, ...] = ()
    bounding_regions: tuple[BoundingRegion, ...] = ()
    parser_element_ref: str | None = None

class Figure(BaseModel):
    figure_id: str
    layout_block_id: str
    source_span_ids: tuple[SpanId, ...] = ()
    caption_span_ids: tuple[SpanId, ...] = ()
    bounding_regions: tuple[BoundingRegion, ...]
    derived_description: str | None = None
    derived_description_is_authoritative: bool = False
    parser_element_ref: str | None = None
```

The exact classes should be finalized with tests before implementation, but the architectural invariant is fixed: layout objects organize spans and page regions; they do not become the citation source of truth.

Important refinements from architecture review:

- Use `page_numbers` plus `bounding_regions`, not only one `page_number` and one `bbox`. Production PDFs have cross-page tables, continued sections, separated captions, and non-contiguous regions.
- Use one deterministic reading-order namespace. `LayoutBlock` is the ordered document skeleton; `Table` and `Figure` attach to a block by ID instead of carrying an independent competing `reading_order`.
- Tables and figures may be represented by wrapper blocks with `block_type="table"` or `block_type="figure"`; the detailed `Table`/`Figure` model must link back to that block via `layout_block_id`.
- Text-bearing blocks and table cells must cite existing `SpanId`s. Visual-only figures may have no text spans and must not force fake spans; they need page/bbox visual provenance and optional caption spans.
- Avoid duplicated authoritative text in layout models. Do not add `text` to `LayoutBlock` or `TableCell` in the first implementation. If convenience text is added later, it must either exactly reconstruct from referenced spans or be explicitly non-authoritative.
- Table cells need production semantics: table row/column counts, non-negative row/column indices, positive row/column spans, cell roles such as row/column header, and validation that cells stay within table bounds.
- `ContentLayer` should map the parser ecosystem without immediate loss: `body`, `furniture`, `background`, `invisible`, `notes`, and `unknown`.
- `parser_element_ref` may store a stable parser-native reference string for debugging/alignment, but parser-native objects must never leak into IR, chunking, validation, or summarization.
- Generated descriptions of figures, images, or table interpretations are derived annotations. They are useful for later summarization only if clearly marked non-authoritative unless backed by citeable OCR/text spans.
- Coordinate-system policy must be explicit. Parsers differ in unit, origin, page rotation handling, and bbox/polygon shape. Exeboard layout models should either normalize coordinates into the existing `BoundingBox` policy or record source coordinate metadata clearly enough for audit/highlighting.

### Why this design

#### Raw spans remain the citation source of truth

`TextSpan` already has stable IDs, page numbers, canonical character offsets, text, and optional bboxes. Validators, summary claims, and review UI can continue to cite spans. This avoids rebuilding citation semantics around every parser's native object model.

#### Layout objects organize spans and visual regions without duplicating provenance truth

A text-bearing `LayoutBlock` or `TableCell` should point to spans. A visual-only `Figure` may point to bounding regions and optional caption spans. Layout objects may carry convenience text, but that text is derived and must not become a second authoritative copy. If derived text disagrees with cited spans, the spans win and tests should fail. If a derived visual description is not backed by citeable OCR/text spans, it must be marked non-authoritative and cannot pass quote validation as source text.

#### Tables preserve row/column semantics

Flattening a table to plain text loses the relationships that often carry the meaning:

- which value belongs to which row label
- which column header qualifies a value
- whether a cell is part of a merged header
- whether a number is a total, subtotal, period value, forecast, or variance

Evidence-backed financial and operational summaries cannot safely infer those relationships from flattened prose after the fact.

#### Chunking can consume structure later

The current chunker groups spans by page and span reading order. A layout-aware chunker should instead consume blocks/tables/figures:

- keep sections coherent
- keep table cells with their table context
- avoid repeated furniture as claim material
- split by semantic boundaries before token limits
- include table headers with value cells when needed for interpretation

## Rejected shortcuts

This section is the rationale for the layout-aware adapter decision. These are not things we should still consider doing; they are the shortcuts that the Docling/layout-aware direction exists to avoid.

### Treating `PyMuPDF sort=True` as semantic reading order

`sort=True` is useful but not sufficient. It sorts by coordinates. It does not know that a two-column page should be read down the left column before the right column, that a caption belongs to a figure, or that repeated headers should not be mixed into the body narrative.

Shortcut consequence: the summarizer can combine unrelated neighboring lines, miss section boundaries, or cite real spans for a claim whose premise was created by wrong ordering.

### Flattening tables into plain text only

Flattened text may preserve some visible tokens but loses table structure.

Shortcut consequence: claims about numerical values become hard to audit. A quote validator may find the number, but it cannot prove the row/column context that makes the number meaningful.

### Silent OCR fallback

OCR is not just another extraction method. It changes cost, latency, privacy posture, confidence, and error profile.

Shortcut consequence: the same parser call can silently shift from deterministic native text to probabilistic OCR, making failures hard to reproduce and making compliance/audit behavior unclear.

### Making an LLM infer layout from broken text

An LLM can sometimes guess intended structure, but that guess is not provenance. It is not deterministic, not easily testable, and not anchored to bboxes or table cells.

Shortcut consequence: the model may produce plausible claims that validators cannot distinguish from correct claims if the cited text exists somewhere but the structure was inferred incorrectly.

### Replacing Exeboard IR with Docling-native objects

Docling is a strong adapter candidate, not the component's domain model.

Shortcut consequence: chunking, validation, summarization, and future parser adapters become coupled to one vendor/library shape. That breaks the parser boundary and makes cloud parsers, OCR engines, and future local parsers harder to add.

## Test guards

When layout IR is implemented, add tests that enforce these rules:

1. Text-bearing layout objects reference existing `SpanId`s.
2. Referenced spans belong to the same `DocumentIR.document_id`.
3. Referenced spans' page numbers are included in the layout object's `page_numbers` or `bounding_regions`.
4. Visual-only figures can be represented with page/bbox provenance and optional caption spans without fabricating text spans.
5. `LayoutBlock.reading_order` is explicit and deterministic; tables and figures attach to ordered blocks instead of defining a second ordering namespace.
6. Duplicate layout reading-order values are rejected across `DocumentLayout.blocks`.
7. Duplicate block, table, and figure IDs are rejected.
8. Parent block references exist; self-parenting and cycles are rejected.
9. `DocumentLayout.parser_run_id` references an existing `ParserRun`, and duplicate parser run IDs are rejected before layout depends on them.
10. `ContentLayer` can represent `body`, `furniture`, `background`, `invisible`, `notes`, and `unknown`.
11. Header/footer/page-number furniture can be represented without pretending it is body content.
12. Tables preserve row count, column count, row index, column index, row span, column span, cell roles, source spans, and bounding regions.
13. `Table.layout_block_id` references an existing `LayoutBlock` with `block_type="table"`; table IDs are unique and linked from the wrapper block.
14. Table cells cannot cite spans from another document and cannot extend beyond table bounds.
15. Figures preserve figure/caption provenance separately from body paragraphs.
16. `Figure.layout_block_id` references an existing `LayoutBlock` with `block_type="figure"`; visual-only figures with bounding regions and no spans are valid, but figures without spans and without regions are rejected.
17. Cross-page or non-contiguous tables/sections/figures can be represented without splitting one semantic object into unrelated objects.
18. Derived layout text, if stored, must equal reconstruction from referenced spans or be clearly marked non-authoritative.
19. Coordinate systems, units, origin, and rotation policy are normalized or explicitly recorded.
20. A layout-aware parser's no-layout, OCR-required, encrypted, unreadable, unsupported-document, and span-alignment failures are explicit.
21. Parser provenance records actual strategy and version information: native text, layout analysis, OCR use, cloud/VLM use, selected model/version, confidence/fallbacks when available.
22. `PyMuPDFParser` continues not to OCR and continues to report partially textless PDFs with warnings.
23. The legacy span-based chunker remains valid for text-only flows but is not presented as layout-aware.
24. Quality/evaluation fixtures include multi-column pages, repeated headers/footers, table header/value alignment, merged cells, scanned pages, rotated pages, figures with captions, and cross-page tables before claiming production support for complex PDFs.

## Proposed implementation sequence

### 1. Create this strategy document

Done by adding:

```text
docs/document-intelligence/pdf-parsing-strategy.md
```

This records the production architecture decision before changing code.

### 2. Add layout IR models and tests

Add Exeboard-owned layout models under the IR boundary, likely one of:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/ir/layout.py
```

or, if the file grows, a package:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/ir/layout/
```

Recommended first test file:

```text
tests/unit/document_intelligence/test_layout_models.py
```

Acceptance:

- `DocumentIR` without layout remains valid, so existing PyMuPDF and span-chunker flows are unchanged.
- `DocumentIR` gains `layout: DocumentLayout | None` and validates layout references when layout is present.
- text-bearing layout blocks can reference spans from a `DocumentIR`.
- invalid/missing/cross-document span references are rejected by `DocumentIR` validation or a required attachment helper.
- `DocumentLayout.parser_run_id` references an existing parser run; duplicate `parser_run_id`s are rejected.
- layout blocks provide the single deterministic reading-order namespace; duplicate block reading orders are rejected.
- table and figure details attach to wrapper blocks via `layout_block_id`, avoiding competing table/figure reading orders.
- parent block references are validated; missing parents, self-parents, and cycles are rejected.
- table cells preserve row/column semantics, including row/column counts, row/column indices, row/column spans, roles, and span/region provenance.
- multi-page/non-contiguous layout objects are representable through `page_numbers` and `bounding_regions`.
- visual-only figures can be represented without fake spans.
- coordinate-system normalization or metadata is enforced.
- expanded content-layer labels are representable: `body`, `furniture`, `background`, `invisible`, `notes`, and `unknown`.
- no authoritative duplicate layout text is introduced in the first implementation.

Architectural choice: add `DocumentIR.layout: DocumentLayout | None` now. This preserves the existing `DocumentParser.parse(path) -> DocumentIR` port while allowing richer parsers to populate layout. The tradeoff is that `DocumentIR` validation becomes broader, but that is the correct place for the invariant because project state already says invalid IR should not exist.

Validation placement: a standalone `DocumentLayout` cannot prove referenced spans exist unless it receives the parent document/span index. The first implementation should therefore add `layout` to `DocumentIR` and validate references in `DocumentIR`. If import structure makes that unsafe, use a required constructor/helper such as `attach_layout(document, layout)` temporarily, but do not allow callers to pass around unvalidated layout as production IR.

### 3. Add parser-port failure types for layout adapters

Before Docling adapter code, add explicit parser-port failures for layout-specific parsing:

```python
class LayoutExtractionError(DocumentParseError): ...
class SpanAlignmentError(DocumentParseError): ...
```

Use `LayoutExtractionError` when a selected layout-aware parser cannot produce required layout. Use `SpanAlignmentError` when parser-native text/layout cannot be reconciled with Exeboard `DocumentIR.content` and `TextSpan`s. Do not collapse these into generic unreadable/no-text failures because downstream retry, audit, and parser-strategy selection need to distinguish invalid files from layout/alignment failures.

### 4. Spike a Docling adapter behind the parser boundary

Add a Docling-backed adapter only after the layout IR exists and layout-specific parser failures exist, because otherwise the adapter has nowhere stable to put structure or report alignment failures.

Likely file:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/parsing/adapters/docling.py
```

The spike must prove:

- Docling output can be translated into `DocumentIR.content`, `Page`, and `TextSpan`.
- The adapter either builds `DocumentIR.content` directly from Docling's canonical content or uses a deterministic span-alignment step that can fail loudly when whitespace, character offsets, ordering, or non-contiguous spans cannot be reconciled.
- Docling layout/table/figure provenance can be translated into Exeboard layout objects referencing `SpanId`s where text exists and bounding regions where visual-only provenance exists.
- Parser provenance records Docling version, selected strategy, OCR use, model/artifact versions when available, and fallback/warning information.
- Failures are explicit parser-port errors or explicit warnings.
- No Docling-native objects leak into chunking, validation, or summarization models.

### 5. Design layout-aware chunking

Do not retrofit the current span chunker by sprinkling table heuristics into it. Add a layout-aware chunking path that consumes `DocumentLayout`.

Likely direction:

```text
chunk_document(document)              # current span-based chunker
chunk_layout_document(document)       # new layout-aware chunker, requires layout
```

A layout-aware chunk should still cite `source_span_ids` for text-backed evidence, but it may also carry layout provenance such as block IDs, table IDs, cell coordinates, figure IDs, and bounding regions. Vendor-provided chunks from Google, Docling, or another parser may be useful adapter input, but Exeboard-owned chunk models remain the canonical downstream contract.

### 6. Decide quote validator and final summarizer sequencing

There are two honest paths:

- If the immediate goal is to finish the digital-text MVP, implement quote validation and final summarization next, but label the capability as native-text PDF summarization only. This produces a useful vertical slice but must not be marketed as robust for table-heavy or complex-layout PDFs.
- If the immediate goal is production-grade complex PDF summarization, implement layout IR and the Docling adapter before final summarization, because a final summarizer built only on raw line chunks will bake in reading-order/table limitations that later have to be unwound.

Recommendation: implement layout IR next before claiming production support for complex PDFs. Quote validation remains necessary either way, but it validates quote support, not whether layout was reconstructed correctly.

## Decision

Adopt a two-parser strategy:

```text
PyMuPDFParser
  -> fast native-text baseline
  -> this Exeboard adapter does not invoke OCR or expose table IR
  -> no semantic layout guarantee

DoclingParser
  -> recommended layout-aware adapter candidate
  -> explicit dependency and parser strategy
  -> translates to Exeboard-owned IR/layout models

Future OCR/cloud parsers
  -> explicit strategy/adapters
  -> no hidden fallback inside PyMuPDFParser
```

Adopt a layered IR strategy:

```text
TextSpan
  -> citation source of truth

DocumentLayout / LayoutBlock / Table / TableCell / Figure
  -> organization over spans and visual bounding regions
  -> deterministic reading order and structure
  -> supports multi-page/non-contiguous structures
  -> no parser-native object leakage
```

This keeps the existing evidence/citation architecture intact while creating a production path for layout-aware summarization.
