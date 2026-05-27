# Docling Adapter Implementation Plan

Last updated: 2026-05-26

Status: reviewed and revised implementation handoff plan. This plan incorporates the reviewer feedback in `reviews/docling-adapter-plan-review.md`.

## Scope

Implement a Docling-backed parser adapter that translates Docling output into Exeboard-owned `DocumentIR` and `DocumentLayout` models.

In scope:

- Add a Docling layout-aware adapter under `packages/exeboard-ai/src/exeboard_ai/document_intelligence/parsing/adapters/`.
- Preserve `DocumentParser.parse(path: Path) -> DocumentIR`.
- Populate `DocumentIR.content`, `Page`, `TextSpan`, and `DocumentLayout` from Docling output.
- Map Docling layout concepts into Exeboard `LayoutBlock`, `Table`, `TableCell`, `Figure`, `BoundingRegion`, and source-span references.
- Add a parser-port dependency error for missing optional parser dependencies.
- Add tests with fake Docling-like objects that mirror the discovered real Docling API shape.
- Add opt-in real Docling integration tests gated by dependency availability and an explicit environment variable.

Out of scope for this step:

- No layout-aware chunker changes.
- No summarization changes.
- No silent OCR fallback.
- No silent remote inference.
- No PyMuPDF table/OCR upgrades.
- No Docling-native objects exposed outside the adapter.
- No imports from `apps/`.

## Architectural goal

Docling should be an adapter, not a new internal data model. The adapter must translate vendor/parser-specific structure into the Exeboard IR boundary:

```text
PDF
  -> Docling converter/result/document
  -> DoclingAdapter translation layer
  -> DocumentIR(content, pages, spans, layout)
```

`DocumentIR.content` and `TextSpan` remain the citation source of truth. Layout objects organize, classify, and add geometry around those spans; they must not become an independent authoritative duplicate text layer.

## Non-negotiable invariants

1. **Docling API discovery first**
   - Do not implement the mapper from guessed Docling object shapes.
   - First executable slice must inspect real Docling output and document the exact public attributes/methods consumed.
   - Fake test objects must mirror that discovered API subset.

2. **No silent OCR or remote inference**
   - Default adapter construction must explicitly disable OCR and remote services using real Docling configuration fields.
   - If the exact fields cannot be identified, stop and request architecture review.
   - If Docling first-use model downloads are required, document that and keep real integration tests opt-in.
   - Future OCR support must be a named parser strategy/configuration, not fallback behavior.

3. **No Docling object leakage**
   - `DocumentIR`, layout models, parser exceptions, and downstream tests must not require callers to import Docling.
   - Store Docling element identifiers only as strings in `parser_element_ref`.

4. **Fail with parser-port errors**
   - Missing dependency must raise `ParserDependencyError`, not leak `ImportError`.
   - Unreadable/invalid/encrypted documents must map to parser-port errors.
   - No text after conversion must raise `NoExtractableTextError`.
   - Missing/invalid layout must raise `LayoutExtractionError`.
   - Text/layout cannot be aligned to Exeboard spans must raise `SpanAlignmentError`.
   - Mapper-created Pydantic `ValidationError`s must be caught and translated to the appropriate parser-port error.

5. **Provenance is mandatory**
   - Text-bearing layout blocks must cite existing `SpanId`s.
   - Table cells must have text spans or visual bounding regions.
   - Figures must have source spans, caption spans, or visual bounding regions.
   - Visual-only objects must use valid `BoundingRegion`s; do not invent fake text spans.

6. **Deterministic output**
   - Reading order must be stable for identical input.
   - Generated block/table/figure IDs must be deterministic from traversal order or stable Docling references.
   - Tests must not depend on network, model downloads, time, or nondeterministic hardware settings.

## Dependency plan

1. Keep the base `exeboard-ai` install lightweight.
2. Add Docling as an optional dependency group:

```toml
[project.optional-dependencies]
docling = ["docling==2.95.0"]
```

3. Add `ParserDependencyError(DocumentParseError)` in `parsing/ports.py`.
4. Import Docling lazily inside the adapter/factory so importing `exeboard_ai.document_intelligence` does not require Docling.
5. Do not install OCR/VLM extras in the default optional dependency.
6. Keep remote services disabled by default.
7. Lock the resolved `docling-core` version in `uv.lock` and record it in Slice 0 notes. In `2.95.0`, `docling` is a small meta-package depending on `docling-slim[standard]==2.95.0`, while `docling-core` is constrained as `>=2.73.0,<3.0.0`; schema stability depends on the resolved core version.

Current version note: use latest PyPI `docling==2.95.0` for Slice 0. Context Hub currently only has Docling docs for `2.78.0`, so treat Chub as background guidance only; verify all API/configuration details directly against the installed `2.95.0` package and upstream tagged docs/source. The deep research artifact for `2.95.0` is `reviews/docling-2.95-api-deep-research.md`.

## Public API shape

Add a new adapter class, tentatively:

```python
class DoclingParser:
    def __init__(
        self,
        *,
        converter: object | None = None,
        enable_ocr: bool = False,
    ) -> None: ...

    def parse(self, path: Path) -> DocumentIR: ...
```

Design notes:

- `converter` injection enables fake-converter tests and avoids requiring Docling in most unit tests.
- This adapter is layout-aware by definition. Default parse must return `DocumentIR.layout is not None` with non-empty blocks or fail with `LayoutExtractionError`.
- Do **not** expose `require_layout=False` as public API for production use. If a temporary no-layout escape hatch is needed for tests, keep it private/internal and do not document it as supported behavior.
- `enable_ocr=False` documents the default no-OCR contract. Implementation must verify and assert the real Docling configuration knob in Slice 0 before wiring this option.
- If the team wants a Docling text-only parser later, create a separate explicit strategy rather than weakening this adapter.

## Mandatory Slice 0: Docling API and behavior discovery gate

Before implementing the mapper, perform a small real-Docling discovery spike and write the findings to `docs/document-intelligence/docling-api-notes.md` or a review artifact.

The discovery artifact must answer:

1. **Converter construction**
   - Exact imports and constructor calls for `DocumentConverter`, `InputFormat`, `PdfFormatOption`, and `PdfPipelineOptions`.
   - Use the `2.95.0` explicit construction baseline below unless Slice 0 proves it wrong:

```python
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

pdf_options = PdfPipelineOptions(
    do_ocr=False,
    do_table_structure=True,
    enable_remote_services=False,
    allow_external_plugins=False,
    artifacts_path=None,
)

converter = DocumentConverter(
    allowed_formats=[InputFormat.PDF],
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
    },
)
```

   - Verify `do_ocr=False` because `PdfPipelineOptions.do_ocr` defaults to `True` in `2.95.0`.
   - Verify `do_table_structure=True` remains enabled because table cells are core to this adapter.
   - Verify `enable_remote_services=False` and `allow_external_plugins=False` are set or defaulted as expected.
   - Whether default construction may download model artifacts.
   - How to configure an offline artifacts path via `artifacts_path` or `DOCLING_ARTIFACTS_PATH` if needed.

2. **Result/document shape**
   - Conversion should use `convert(..., raises_on_error=False)` during discovery so `ConversionResult.status`, `errors`, `document`, and `version` are inspectable even for partial failures.
   - Record `ConversionStatus` values encountered; accept only `success` / explicitly handled `partial_success` in the final adapter.
   - Record `ConversionResult.version` fields: `docling_version`, `docling_slim_version`, `docling_core_version`, `docling_parse_version`, and related model/runtime versions when available.
   - How to access `DoclingDocument.pages`: `dict[int, PageItem]` with one-based `page_no` and `size.width` / `size.height`.
   - How to iterate items in reading order: in `2.95.0`, `doc.iterate_items(...)` yields `(item, level)` tuples, not bare items.
   - Text item access: use `TextItem.text` / `orig` after confirming installed API; do not rely on stale examples using `get_text()`.
   - Stable element references/IDs: use `item.self_ref` JSON-pointer-like strings such as `#/texts/0`, `#/tables/0`, stored only as `parser_element_ref`.
   - Provenance access: `DocItem.prov` list; each provenance item has `page_no`, `bbox`, and `charspan`.
   - Table access: `TableItem.data.table_cells`, `num_rows`, `num_cols`, row/column offset indices, spans, header booleans, cell text, and cell bbox.
   - Figure/picture access: `PictureItem`, `captions` refs, `caption_text(doc)`, picture provenance, and optional image fields if image generation is explicitly enabled later.

3. **Coordinate semantics**
   - Bbox units.
   - Origin and axis direction. In `2.95.0`, Docling-core `BoundingBox` stores `l`, `t`, `r`, `b`, and `coord_origin`; use `to_top_left_origin(page_height=...)` when needed.
   - Page-number base. Research indicates `DoclingDocument.pages` and provenance `page_no` are one-based, but fixtures must confirm.
   - Rotation behavior.
   - Required conversion to Exeboard `pdf_points_top_left`.
   - Capture raw bbox, origin, page size, and normalized top-left bbox in the discovery fixture dump.

4. **Safety behavior**
   - Generated image-only/scanned PDF with `enable_ocr=False` must not return OCR text.
   - Remote services must be proven disabled by configuration or by documented Docling default.
   - If model downloads occur, document them and keep real integration tests env-gated.

Stop conditions at Slice 0:

- Cannot disable OCR explicitly or cannot prove it is disabled.
- Cannot disable remote services explicitly or cannot prove they are disabled.
- Cannot find stable public provenance fields for text, tables, or figures.
- Only stable output path is lossy Markdown flattening.

Fake tests in later slices must mirror the discovered interface, not an invented adapter-owned shape.

## Internal decomposition

Keep the adapter thin and testable by splitting conversion from mapping:

1. `DoclingParser.parse(path)`
   - Validate/derive `document_id` using existing filename rules.
   - Build `DocumentSource` with SHA-256, mapping read failures to `UnreadableDocumentError`.
   - Convert via injected or lazily constructed Docling converter.
   - Map conversion failures to parser-port errors.
   - Call pure mapping helpers to build `DocumentIR`.
   - Catch mapper/IR validation failures and translate to `SpanAlignmentError` or `LayoutExtractionError`.

2. `DoclingMapper`
   - Accepts the discovered Docling result/document plus `document_id`, source, parser metadata.
   - Produces only Exeboard IR models.
   - Contains no filesystem, network, model-download, or dependency-import side effects.

3. Pure helpers
   - `_extract_pages(...) -> list[Page]`
   - `_build_spans_and_content(...) -> content, pages, element_ref_to_span_ids`
   - `_map_blocks(...) -> tuple[LayoutBlock, ...]`
   - `_map_tables(...) -> tuple[Table, ...]`
   - `_map_figures(...) -> tuple[Figure, ...]`
   - `_to_bounding_region(...) -> BoundingRegion | None`
   - `_docling_ref(...) -> str | None`
   - `_docling_text(item) -> str` for `TextItem.text` / table-cell text after Slice 0 confirms exact APIs
   - `_docling_provenance(item) -> tuple[raw_prov, ...]` for `DocItem.prov` records

## Text/span alignment and content assembly strategy

Preferred first implementation:

1. Traverse Docling structural items in Docling reading order.
2. Build `DocumentIR.content` from the exact text inserted into `TextSpan.text`.
3. Create deterministic `TextSpan`s while building content; do not build content independently and fuzzy-align afterward unless Docling provides a stable canonical charspan model.
4. Maintain a mapping from Docling element reference to generated `SpanId`s.
5. Layout blocks and table/figure captions cite those generated span IDs.
6. If Docling gives native charspans, use them to cross-check, not as a separate source of truth.
7. If a text-bearing layout item has text but no span can be generated or associated, raise `SpanAlignmentError`.

Initial span granularity:

- One span per meaningful Docling text item or table-cell text item.
- Preserve table-cell text as span text so table cells can cite real spans.
- Avoid converting tables only to Markdown because row/column provenance would be lost.

Deterministic content assembly policy:

- Traverse Docling reading order via `doc.iterate_items(...)`; in `2.95.0`, unpack `(item, level)`.
- Insert `"\n"` between block-level text spans.
- For tables, emit table-cell spans in row-major order inside the table wrapper's reading-order position.
- Insert `"\t"` between cells in the same row and `"\n"` between rows. Separators are not part of any span unless deliberately modeled as text by Docling.
- For multi-page tables, keep table-cell spans on their source page and assign page-local reading order from the global traversal sequence filtered by page.
- Captions follow the figure/table position Docling reports; do not move captions heuristically unless Docling exposes a relation.
- `TextSpan.reading_order` must be unique per page and deterministic across paragraphs, table cells, captions, headers, and footers.
- `char_start` / `char_end` must satisfy the existing `DocumentIR` invariant: `content[char_start:char_end] == span.text`.

Required table/content tests:

- Paragraph before table and table before paragraph preserve offsets and reading order.
- Table cells use row-major content order.
- Multi-page table cells keep correct page numbers and page-local reading orders.
- Separators do not corrupt span text or char offsets.

## Layout mapping strategy

### Label and role mapping

After Slice 0 discovery, add a concrete mapping table to either this plan or implementation docs:

```text
Docling label/role -> Exeboard enum
```

Rules:

- Known text labels map to `LayoutBlockType` values.
- Header/footer/page-number labels map to `ContentLayer.FURNITURE`.
- Unknown labels map to `LayoutBlockType.UNKNOWN` and `ContentLayer.UNKNOWN` or conservative `BODY` only when the item is clearly body text.
- Every mapped label/role gets a unit test.
- At least one unknown label/role gets a unit test.

### Blocks

- Create one `LayoutBlock` per Docling structural item that should participate in reading order.
- Use a single monotonic `reading_order` namespace across all blocks.
- For text-bearing block types, attach generated `source_span_ids`.
- For tables and figures, create wrapper blocks with `table_id` / `figure_id` and attach details through `layout_block_id`.
- Use Docling references as `parser_element_ref` when available.

### Tables

- Create a table wrapper block in reading order.
- Create a `Table` with deterministic `table_id` and matching `layout_block_id`.
- Preserve `row_index`, `column_index`, `row_span`, `column_span`.
- In `2.95.0`, map Docling table-cell offset fields into Exeboard indices:
  - `row_index = start_row_offset_idx`
  - `column_index = start_col_offset_idx`
  - `row_span = row_span` or `end_row_offset_idx - start_row_offset_idx` after validation
  - `column_span = col_span` or `end_col_offset_idx - start_col_offset_idx` after validation
- Map Docling header booleans into `TableCellRole`:
  - `column_header` -> `COLUMN_HEADER`
  - `row_header` -> `ROW_HEADER`
  - `row_section` -> `ROW_SECTION`
  - otherwise `CONTENT`.
- Each `TableCell` must have `source_span_ids` from cell text or a valid visual `BoundingRegion`.
- Do not flatten tables into prose as the only representation.

### Figures

- Create a figure wrapper block in reading order.
- Create a `Figure` with deterministic `figure_id` and matching `layout_block_id`.
- Attach caption spans by resolving Docling `captions` refs / `caption_text(doc)` after Slice 0 confirms the exact behavior.
- Attach figure bounding regions when available.
- Pass `bounding_regions=()` explicitly for span-only/caption-only figures because the current model field is required syntactically.
- Do not generate authoritative derived descriptions in this adapter.
- Visual-only figures are valid if they have bounding regions.

### Bounding regions

- Convert Docling page/bbox provenance into `BoundingRegion(page_number, BoundingBox)`.
- In `2.95.0`, Docling bboxes expose `l`, `t`, `r`, `b`, and `coord_origin`; normalize to Exeboard `pdf_points_top_left` before model construction using Docling's origin conversion helper when available.
- Convert zero-based page indexes to one-based page numbers if Docling uses zero-based indexes.
- Reject invalid/negative/non-finite/zero-area visual regions.
- Reject boxes exceeding known page dimensions.
- Drop optional text bboxes only when the text span remains citeable by text.
- Do not silently drop invalid visual-only object regions if they are the only provenance; raise `LayoutExtractionError` instead.

Required coordinate tests:

- Docling bbox in discovered coordinate system converts to top-left PDF-point `BoundingRegion`.
- Page-number base conversion is correct.
- Invalid negative/non-finite/zero-area/out-of-page bboxes map to `LayoutExtractionError` when required for layout provenance.
- Rotated-page behavior is tested if Docling exposes enough rotation metadata; otherwise document rotation as a known limitation in Slice 6.

## Parser-run provenance policy

Use existing `ParserRun` fields for this slice:

- `parser_run_id`: stable value such as `docling:layout`.
- `parser_name`: `docling`.
- `parser_version`: include Docling package version, Docling slim version, Docling core version, Docling parse version, and selected converter/pipeline/backend strategy when available.
- `warnings`: include concise, explicit operational facts until a structured parser-provenance model exists:
  - `ocr_enabled=false` for default parser.
  - `remote_services_enabled=false` for default parser.
  - model/artifact path or download behavior when known.
  - partial-layout/fallback warnings when Docling reports them.

If warnings feel too unstructured, create a follow-up issue to extend `ParserRun`; do not leave parser provenance unspecified.

## Error mapping plan

Add tests for each branch.

- Missing optional Docling dependency -> `ParserDependencyError`.
- Source hashing/read failure -> `UnreadableDocumentError`.
- Docling open/parse/data failure -> `UnreadableDocumentError` unless the exception clearly identifies encryption or no text. During discovery, call `convert(..., raises_on_error=False)` and inspect `ConversionResult.status` / `errors`; final adapter may still use this path for precise error mapping.
- Encrypted input -> `EncryptedDocumentError`.
- Successful conversion but no generated text spans -> `NoExtractableTextError`.
- No/non-empty layout when this adapter is selected -> `LayoutExtractionError`.
- Text-bearing layout item cannot be connected to generated spans -> `SpanAlignmentError`.
- Invalid required visual provenance -> `LayoutExtractionError`.
- Pydantic validation failures during final `DocumentIR` construction:
  - span/text/page/reference failures -> `SpanAlignmentError`.
  - layout geometry/table/figure/wrapper/provenance structure failures -> `LayoutExtractionError`.

Keep low-level IR validators as the last line of defense, but mapper prechecks should make exception taxonomy precise.

## Test plan

### Unit tests with fakes

Use small fake Docling-like objects that mirror the Slice 0 discovered API subset. These tests must not import Docling.

Required cases:

1. Missing Docling dependency raises `ParserDependencyError` when no converter is injected.
2. Simple one-page document with title + paragraph.
3. Multi-page document preserving page IDs, span IDs, char offsets, and reading order.
4. Header/footer/page-number mapping to furniture content layer.
5. Unknown label maps to explicit unknown/default behavior.
6. Table with header cell, content cell, row/column indices, and matching table wrapper block.
7. Table cell with visual-only provenance.
8. Table content assembly: row-major cells, stable separators, valid char offsets.
9. Multi-page table preserving page provenance and page-local reading order.
10. Figure with caption spans.
11. Visual-only figure with bounding region.
12. Span-only/caption-only figure passes `bounding_regions=()` explicitly.
13. Invalid or missing required layout raises `LayoutExtractionError`.
14. Text-bearing layout item without generated span raises `SpanAlignmentError`.
15. Mapper-generated Pydantic validation failure is translated to parser-port error.
16. No extractable text raises `NoExtractableTextError`.
17. JSON round-trip of a Docling-produced layout-bearing `DocumentIR`.
18. Serialized IR contains no Docling-native objects.
19. Coordinate conversion and invalid bbox cases.
20. Parser-run metadata records Docling version/strategy, `docling-slim`, `docling-core`, `docling-parse`, and default OCR/remote-disabled facts.
21. `doc.iterate_items()` tuple shape is represented in fakes and tests.
22. Table cell offset-index fields and header booleans map correctly to Exeboard table-cell indices/roles.

### Mandatory opt-in integration tests

Real Docling integration tests must be gated by both dependency availability and an explicit environment variable, for example:

```python
pytest.importorskip("docling")
pytestmark = pytest.mark.skipif(
    os.environ.get("EXEBOARD_RUN_DOCLING_INTEGRATION") != "1",
    reason="Docling integration tests are opt-in because they may require model artifacts",
)
```

Integration cases:

1. Generated simple digital PDF converts to `DocumentIR` with non-`None` layout and non-empty blocks.
2. Generated image-only/scanned PDF with default `enable_ocr=False` does **not** silently OCR; expected result is `NoExtractableTextError` or a documented parser-port layout/no-text error.
3. Confirm default converter construction records or exposes OCR disabled and remote services disabled.
4. Generated simple table PDF maps at least one `Table` and cells only if Docling extraction is stable in the selected configuration; otherwise keep table coverage in fake unit tests and document integration limitation.
5. Rotated-page behavior if stable; otherwise document as known limitation.

Avoid flaky assertions over exact model-inferred labels unless Docling's output is stable for generated fixtures.

## Implementation slices

### Slice 0 — Docling API/default-behavior discovery

- Install/use `docling==2.95.0` locally or in an isolated environment.
- Record the resolved `docling`, `docling-slim`, `docling-core`, `docling-parse`, and model package versions.
- Produce `docs/document-intelligence/docling-api-notes.md` with converter configuration, safety defaults, object shape, provenance fields, coordinate semantics, and model/artifact behavior.
- Use the explicit PDF-only converter baseline from this plan unless discovery proves it wrong.
- Create one tiny sanitized schema fixture/dump if practical, preferably from `doc.export_to_dict(coord_precision=None)` or `ConversionResult.save()` if available in the installed version.
- Update fake test fixtures to mirror this discovered interface.
- Stop if OCR/remote/provenance behavior cannot satisfy this plan.

### Slice 1 — small IR/ID hardening follow-up

Before or during adapter work, resolve the current ID-width edge:

- `make_page_id()` / `make_span_id()` use `:04d`, which is minimum width.
- Current parsers should either accept `\d{4,}` or makers should cap at `9999`.
- Prefer `\d{4,}` so `parse_*_id(make_*_id(..., 10000))` works.
- Add round-trip tests for page/span index `10000`.

This is not Docling-specific, but the Docling adapter may create many spans for large documents; fixing this avoids an artificial scale bug.

### Slice 2 — optional dependency boundary and parser skeleton

- Add optional dependency metadata.
- Add `ParserDependencyError`.
- Add `DoclingParser` with converter injection and lazy default converter creation.
- Add tests for missing dependency, injected converter path, and source read failures.

### Slice 3 — text/pages/spans only

- Convert a fake Docling document into `DocumentIR` without exposing public no-layout mode.
- Validate content offsets, page IDs, span IDs, parser run metadata, and no-text error.
- Keep this slice internal; public adapter should still require layout by completion.

### Slice 4 — layout blocks

- Map title/paragraph/heading/list/caption/header/footer/page-number blocks.
- Create `DocumentLayout` with deterministic reading order.
- Ensure text-bearing blocks cite generated spans.
- Add label mapping table/tests and JSON round-trip tests.

### Slice 5 — tables

- Add table wrapper blocks and `Table` details.
- Preserve cell positions/spans/roles.
- Implement table content assembly/separator policy.
- Validate cell provenance and page-local reading order.

### Slice 6 — figures

- Add figure wrapper blocks and `Figure` details.
- Preserve caption spans and visual-only figure provenance.
- Ensure span-only/caption-only figures pass `bounding_regions=()` explicitly.

### Slice 7 — real Docling smoke coverage and docs

- Add opt-in guarded integration tests.
- Update `pdf-parsing-strategy.md` with actual adapter behavior, dependency/remote/OCR defaults, artifact behavior, and known limitations.

## Acceptance criteria

The step is complete when:

- Slice 0 discovery artifact exists and names the exact Docling API/configuration used, including `docling`, `docling-slim`, `docling-core`, and `docling-parse` versions.
- `ParserDependencyError` exists and missing Docling raises it.
- `DoclingParser` implements `DocumentParser.parse(path: Path) -> DocumentIR`.
- Base package import does not require Docling unless the adapter is instantiated without an injected converter.
- Default parser construction has OCR and remote services disabled or explicitly proven disabled.
- Default successful parse returns `DocumentIR.layout is not None` with non-empty blocks.
- Unit tests cover mapping with fakes that mirror discovered Docling API.
- Optional integration tests are env-gated and deterministic.
- Produced `DocumentIR.layout` passes existing IR validators.
- Text-bearing layout objects cite existing spans from the same document.
- Tables and figures attach through wrapper blocks rather than owning independent reading order.
- Table content assembly has deterministic separators, offsets, and page-local reading order.
- Mapper/IR validation failures are translated into parser-port errors.
- Parser run metadata records Docling version/strategy and OCR/remote defaults using current `ParserRun` fields.
- No Docling-native objects leak into serialized IR.
- No OCR or remote inference is enabled silently.
- Full document-intelligence tests pass.

## Explicit stop conditions

Stop and ask for architecture review if:

- Docling's default conversion cannot be configured to avoid OCR/remote/model downloads, or this cannot be proven.
- Docling's public API does not expose enough stable provenance to create span-backed layout blocks.
- Table or figure extraction requires lossy Markdown flattening as the only stable path.
- Coordinate semantics cannot be normalized to `pdf_points_top_left` with confidence.
- The adapter needs changes in chunking or summarization to be meaningful.
