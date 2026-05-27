# Docling Adapter Plan Review

Reviewed: `docs/document-intelligence/docling-adapter-plan.md` against the strategy doc, current IR/ID/parser-port code, PyMuPDF adapter patterns, pyproject, and relevant tests.

## Review

### Correct

- The plan preserves the core Exeboard boundary: Docling remains an adapter, while `DocumentIR.content`/`TextSpan` stay the citation source of truth (`docs/document-intelligence/docling-adapter-plan.md:29-40`). This matches the strategy decision to keep Exeboard-owned IR instead of exposing Docling-native objects (`docs/document-intelligence/pdf-parsing-strategy.md:425-442`).
- The plan correctly makes layout provenance non-negotiable: text-bearing blocks must cite `SpanId`s, table cells need spans or regions, and visual-only objects must not get fake spans (`docs/document-intelligence/docling-adapter-plan.md:61-65`). These align with current model validators: text-bearing `LayoutBlock`s require `source_span_ids` (`packages/exeboard-ai/src/exeboard_ai/document_intelligence/ir/models.py:188-200`), `TableCell` requires spans or bounding regions (`models.py:236-240`), and `Figure` requires source spans, caption spans, or regions (`models.py:328-335`).
- The adapter boundary and dependency direction are right: optional dependency, lazy imports, no `apps/` imports, converter injection for tests, and no Docling object leakage (`docs/document-intelligence/docling-adapter-plan.md:20-27`, `72-86`, `105-110`). Current `pyproject.toml` has no optional dependencies yet, so the planned optional group is the appropriate place to add Docling without burdening base installs (`packages/exeboard-ai/pyproject.toml:1-16`).
- The plan correctly identifies the current ID-width edge: makers use `:04d` but parsers currently accept exactly four digits (`docs/document-intelligence/docling-adapter-plan.md:251-260`; `packages/exeboard-ai/src/exeboard_ai/document_intelligence/core/ids.py:10-13`, `40-54`).
- The implementation slices are broadly agent-friendly: skeleton, text/spans, blocks, tables, figures, then real Docling smoke coverage (`docs/document-intelligence/docling-adapter-plan.md:249-296`).

### Severity-ranked findings and concrete plan changes

#### High — Make the Docling API/default-behavior discovery an explicit Slice 0 gate

Evidence: The plan says OCR/remote inference must not be silent (`docs/document-intelligence/docling-adapter-plan.md:44-48`) and notes that implementation must verify the actual Docling OCR knob (`docling-adapter-plan.md:109`), but it does not require a concrete pre-implementation discovery artifact that names the actual `DocumentConverter`/pipeline options, OCR flag, remote-services flag, model/artifact behavior, page/geometry fields, table/cell fields, and caption/provenance fields. The fake-unit-test strategy also says to use “Docling-like objects” (`docling-adapter-plan.md:213-229`), which can accidentally test an invented shape rather than Docling’s real public API.

Concrete change to plan:
- Add a mandatory first slice before the current dependency/skeleton slice: instantiate/configure real Docling locally, document the exact converter construction and options used to disable OCR and remote services, and record the exact public attributes/methods the mapper will consume for pages, text items, labels, provenance, bboxes, tables/cells, figures, captions, and refs.
- Require at least one tiny real-Docling schema fixture or dump, committed as sanitized test data if practical, or documented in the plan, before building the fake objects.
- State that fake objects must mirror this discovered interface, not an aspirational adapter-owned shape.
- Keep the existing stop condition, but move it from only “Explicit stop conditions” (`docling-adapter-plan.md:313-320`) into the first executable gate.

#### High — Strengthen OCR/remote/model-download tests from “guarded if needed” to mandatory safe gates

Evidence: The plan allows either `pytest.importorskip("docling")` or an environment variable for integration tests (`docs/document-intelligence/docling-adapter-plan.md:231-240`). If Docling happens to be installed in CI/dev, import-skipping alone can still run conversion and potentially trigger model downloads or OCR-like behavior. The strategy requires explicit parser provenance for OCR/cloud/VLM/model/fallback behavior (`docs/document-intelligence/pdf-parsing-strategy.md:355-356`).

Concrete change to plan:
- Require real Docling integration tests to be gated by both dependency availability and an explicit opt-in env var, unless the team proves the selected converter configuration is fully offline and artifact-stable in CI.
- Add a required test with an image-only/scanned generated PDF that proves `enable_ocr=False` does not silently OCR: expected result should be `NoExtractableTextError` or a documented layout/no-text parser-port error, not extracted OCR text.
- Add a required test or assertion that default converter construction sets/records remote services disabled and OCR disabled using Docling’s real configuration fields.
- Require docs to state where model artifacts come from and whether first use downloads anything; if first use downloads, integration tests must remain opt-in and normal parser construction must not surprise users with network access.

#### High — Require mapper-side translation of validation failures into parser-port errors

Evidence: The plan says parser failures should be parser-port errors (`docs/document-intelligence/docling-adapter-plan.md:54-59`, `194-207`), but current IR construction raises Pydantic `ValidationError` for many layout/provenance problems: missing text spans on text-bearing blocks (`models.py:188-200`), invalid/missing table-cell provenance (`models.py:236-240`), missing layout parser run (`models.py:516-517`), bad span references (`models.py:538-577`, `714-734`), missing table/figure wrapper links (`models.py:638-696`), and invalid regions (`models.py:698-712`). If the adapter simply constructs `DocumentIR` and lets these leak, it violates the parser-port error contract.

Concrete change to plan:
- Add a mapper acceptance criterion: all `DocumentIR`/layout model validation failures caused by Docling mapping must be caught and re-raised as `SpanAlignmentError` when the issue is missing/misaligned text spans, or `LayoutExtractionError` when the issue is layout structure/visual provenance/geometry/wrapper linkage.
- Add unit tests that intentionally trigger Pydantic validation failures through the mapper and assert parser-port exceptions, not raw `ValidationError`.
- Keep low-level IR validators as the last line of defense, but require mapper prechecks where needed so exception taxonomy remains precise.

#### Medium — Make `ParserDependencyError` non-optional

Evidence: The non-negotiable invariant says missing dependency must be a parser-port dependency error rather than leaking `ImportError` (`docs/document-intelligence/docling-adapter-plan.md:54-56`), but the error plan says “If adding a new `ParserDependencyError`” (`docling-adapter-plan.md:207`). Current parser-port errors do not include dependency failure (`packages/exeboard-ai/src/exeboard_ai/document_intelligence/parsing/ports.py:7-28`).

Concrete change to plan:
- Replace “if adding” with “add `ParserDependencyError(DocumentParseError)` in Slice 1.”
- Add tests in `test_parser_ports.py` and Docling adapter tests that missing Docling raises `ParserDependencyError`, including the path where no injected converter is supplied.

#### Medium — Clarify `require_layout=False` or remove it from the public API

Evidence: The proposed public API exposes `require_layout: bool = True` (`docs/document-intelligence/docling-adapter-plan.md:92-100`) while the design notes say this adapter’s purpose is layout-aware parsing and a text-only Docling parser should be a separate strategy (`docling-adapter-plan.md:107-110`). Exposing `require_layout=False` invites a public text-only mode that weakens the boundary and can make downstream code believe it selected a layout parser when `DocumentIR.layout` is absent.

Concrete change to plan:
- Prefer removing `require_layout` from the public `DoclingParser` constructor and treating layout as required for this adapter.
- If retained, document it as an internal/testing escape hatch only, and state that any production composition must not select `DoclingParser` as layout-aware unless `DocumentIR.layout is not None`.
- Add an acceptance criterion that normal/default parses return a non-`None` `DocumentIR.layout` with non-empty blocks, consistent with current `DocumentLayout.blocks` validation (`models.py:339-360`).

#### Medium — Define canonical content assembly for tables/cells and per-page span ordering

Evidence: The span strategy says to create one span per meaningful Docling text item or table-cell text item and preserve table-cell text as span text (`docs/document-intelligence/docling-adapter-plan.md:149-153`), but it does not define how table-cell spans are inserted into `DocumentIR.content`, what separators are used, how row/column order maps to content order, or how `TextSpan.reading_order` remains unique per page. Current `Page` validation rejects duplicate per-page reading orders (`packages/exeboard-ai/src/exeboard_ai/document_intelligence/ir/models.py:409-425`), and `DocumentIR` validates exact `content[char_start:char_end] == span.text` (`models.py:472-481`).

Concrete change to plan:
- Add a deterministic content-assembly policy: e.g., traverse layout blocks in Docling reading order; for tables, emit cell spans in row-major order within the table wrapper, with a fixed separator policy that is not part of any span unless deliberately modeled.
- Specify how page-local `TextSpan.reading_order` is assigned when the same page has paragraphs, table cells, captions, and figure text.
- Add unit tests for char offsets around table cells, multi-page tables, and ordering of paragraph-before-table/table-before-paragraph content.

#### Medium — Add concrete coordinate/page-normalization tests

Evidence: The plan says to ensure coordinate system is PDF points top-left or convert before model construction (`docs/document-intelligence/docling-adapter-plan.md:187-192`), and the strategy requires units/origin/rotation policy to be normalized or recorded (`docs/document-intelligence/pdf-parsing-strategy.md:353-356`). Current `BoundingBox` only admits `pdf_points_top_left` (`packages/exeboard-ai/src/exeboard_ai/document_intelligence/ir/models.py:18`, `97-108`) and `DocumentIR` rejects regions outside known page dimensions (`models.py:698-712`).

Concrete change to plan:
- Add unit tests for converting Docling bboxes into top-left PDF-point `BoundingRegion`s, including page-number base conversion if Docling uses zero-based indexes, invalid/negative/non-finite boxes, and boxes exceeding page dimensions.
- Add at least one rotated-page integration or fake-mapper test, or explicitly document that rotation support is unknown and must be a known limitation in Slice 6 docs.

#### Medium — Specify parser-run provenance fields despite current minimal `ParserRun`

Evidence: The strategy requires parser provenance to record actual strategy/version information, OCR use, cloud/VLM use, selected model/version, confidence/fallbacks when available (`docs/document-intelligence/pdf-parsing-strategy.md:355-356`). Current `ParserRun` only has `parser_run_id`, `parser_name`, `parser_version`, `ir_version`, and `warnings` (`packages/exeboard-ai/src/exeboard_ai/document_intelligence/ir/models.py:363-378`). The plan mentions “parser metadata” in the mapper (`docs/document-intelligence/docling-adapter-plan.md:123-126`) but does not define what will be recorded.

Concrete change to plan:
- Add a specific parser-run policy for this slice, using existing fields if the model is not extended: stable `parser_run_id` such as `docling:layout`, `parser_name="docling"`, `parser_version` containing Docling version and selected converter/pipeline strategy, and warnings containing explicit `ocr_enabled=false`, `remote_services_enabled=false`, model/artifact info when available, and fallback/partial-layout warnings.
- If warnings are considered the wrong place for structured provenance, add a separate follow-up to extend `ParserRun`; do not leave provenance unspecified.

#### Low — Add a Docling label/role mapping table to avoid implementation drift

Evidence: The plan says to map known Docling labels to `LayoutBlockType` and unknown labels to `UNKNOWN` (`docs/document-intelligence/docling-adapter-plan.md:161-167`) and to map table roles when exposed (`docling-adapter-plan.md:171-176`), but it does not list the concrete label/role mapping.

Concrete change to plan:
- After the Docling API discovery gate, add a small mapping table in the plan or implementation docs: Docling label/role → Exeboard enum, with explicit unknown/default behavior.
- Add unit tests for every mapped label/role and at least one unknown label.

#### Low — Note current `Figure` construction requires an explicit `bounding_regions` argument

Evidence: The plan states figures may have source spans, caption spans, or visual bounding regions (`docs/document-intelligence/docling-adapter-plan.md:61-65`, `178-185`), which matches the semantic validator (`models.py:328-335`), but the current model field is required syntactically: `bounding_regions: tuple[BoundingRegion, ...]` has no default (`packages/exeboard-ai/src/exeboard_ai/document_intelligence/ir/models.py:297-307`).

Concrete change to plan:
- Tell implementers to pass `bounding_regions=()` explicitly for span-only/caption-only figures, or adjust the model in a separate IR change if default-empty is desired.

## Final verdict

**Approved with changes.** The architecture direction is sound and consistent with Exeboard boundaries, but the plan should be tightened before handing to an implementation agent: make real Docling API/default discovery a first gate, require safe OCR/remote/model-download tests, make dependency and validation-error taxonomy explicit, and define deterministic table/content/coordinate provenance policies.
