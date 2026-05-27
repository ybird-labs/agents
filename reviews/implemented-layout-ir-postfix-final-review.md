# Implemented Layout IR Postfix Final Review

Date: 2026-05-26
Scope: layout IR models, parser-port exceptions, and PyMuPDF native-text baseline before Docling. No source files modified.

## Research performed

Fresh web research was performed before review, per instruction. Queries covered document-intelligence provenance, citation faithfulness/local attribution, and structured-output/schema validation. Sources relied on:

- [Systems for Grounding AI Extraction in the Source Document | Ironclad](https://ironcladapp.com/resources/articles/grounding-systems) — reinforces that extraction outputs need source-document grounding such as bounding boxes/highlights for fast audit.
- [RaV-IDP: A Reconstruction-as-Validation Framework for Faithful Intelligent Document Processing](https://arxiv.org/pdf/2604.23644) — models document regions with page/layout regions and treats stored page crops/regions as downstream validation anchors.
- [Correctness is not Faithfulness in Retrieval Augmented Generation Attributions](https://dl.acm.org/doi/10.1145/3731120.3744592) — supports reviewing citation/provenance faithfulness separately from answer correctness.
- [Attribute First, then Generate: Locally-attributable Grounded Text Generation](https://arxiv.org/html/2403.17104) and [LAQuer: Localized Attribution Queries in Content-grounded Generation](https://arxiv.org/html/2506.01187) — support precise local source-span attribution rather than coarse document-level citations.
- [LLM Structured Output Validation in Python That Holds Up](https://www.glukhov.org/llm-performance/benchmarks/llm-structured-output-validation-python/) and [Structured LLM Outputs with Pydantic v2](https://dev.to/peytongreen_dev/structured-llm-outputs-with-pydantic-v2-stop-parsing-freeform-json-and-start-typing-your-ai-5201) — reinforce schema-boundary validation instead of trusting loosely shaped structured outputs.

## Verdict

**APPROVED WITH NITS.**

The latest fixes resolve the prior blocking issues for this step. The implemented model contract is now sufficient to proceed to the Docling adapter spike, with the caveat that the nits below should be addressed soon or when the first layout-aware adapter begins producing real bounding regions.

## Severity-ranked findings

### NIT — Layout `BoundingRegion` still permits zero-area boxes

**Files/lines:**

- `packages/exeboard-ai/src/exeboard_ai/document_intelligence/ir/models.py:95-114` (`BoundingBox` allows `x1 == x0` / `y1 == y0`)
- `packages/exeboard-ai/src/exeboard_ai/document_intelligence/ir/models.py:117-121` (`BoundingRegion` adds no positive-area check)

**Why it matters:**

The previous coordinate hardening is otherwise done: extra fields are forbidden, negative coordinates are rejected, non-finite floats are rejected, coordinate ordering is checked, and layout regions are checked against page dimensions when the parent `DocumentIR` is validated. For visual/layout evidence, however, a zero-width or zero-height region is not highlightable/auditable in a useful way.

**Minimal fix:**

Keep `BoundingBox` permissive if legacy `TextSpan.bbox` might need degenerate boxes, but add a `BoundingRegion` `model_validator` requiring `bbox.x1 > bbox.x0` and `bbox.y1 > bbox.y0`.

**Test:**

Add `BoundingRegion(page_number=1, bbox=BoundingBox(x0=1, y0=1, x1=1, y1=2))` and zero-height equivalent rejection tests.

### NIT — JSON serialization round-trip is manually valid but not asserted in tests

**Files/lines:**

- `tests/unit/document_intelligence/test_layout_models.py:786-833`

**Why it matters:**

The existing test validates `model_dump()` / `model_validate()` round-trip. I manually smoke-tested `model_dump_json()` / `model_validate_json()` and it round-trips, but JSON is the more realistic boundary for persisted/inter-service IR.

**Minimal fix:**

Extend the existing test with:

```python
json_dumped = document.model_dump_json()
assert DocumentIR.model_validate_json(json_dumped) == document
```

### NIT — PyMuPDF adapter should defensively drop invalid extracted bboxes instead of letting strict model validation escape

**Files/lines:**

- `packages/exeboard-ai/src/exeboard_ai/document_intelligence/parsing/adapters/pymupdf.py:158-167`

**Why it matters:**

Strict `BoundingBox` validation is correct. But `_make_bounding_box()` only pre-filters inverted boxes. If PyMuPDF ever returns a negative or non-finite coordinate, `BoundingBox(...)` can raise a Pydantic validation error outside the parser-port exception taxonomy. This is not a blocker for the current generated-PDF tests, but real PDFs can contain off-page/cropped content.

**Minimal fix:**

Before constructing `BoundingBox`, reject non-finite or negative coordinates and return `None`; or catch `ValidationError` in `_make_bounding_box()` and return `None` with a parser warning if warning plumbing is added later.

## Verified current status of requested items

- **Strict `BoundingBox` / `BoundingRegion` coordinate validation:** substantially fixed. `BoundingBox` uses `extra="forbid"`, `allow_inf_nan=False`, and `Field(ge=0)` for all coordinates (`models.py:95-106`), plus ordering validation (`models.py:108-114`). Parent-document validation rejects `BoundingRegion` pages that do not exist and bboxes extending beyond known page width/height (`models.py:682-696`). Covered by tests for negative/non-finite/extra coordinates and page-dimension bounds (`test_layout_models.py:215-274`). Only remaining nit: zero-area layout regions.
- **Missing/unreadable PDF parser-port exception mapping:** fixed for the reviewed missing-file path. `parse()` wraps `_make_document_source()` `OSError` as `UnreadableDocumentError` (`pymupdf.py:31-37`), and `_open_pdf()` maps PyMuPDF open/data errors to `UnreadableDocumentError` (`pymupdf.py:104-108`). Covered by missing/empty/invalid PDF tests (`test_pymupdf_parser.py:170-188`).
- **Table-cell provenance:** fixed. Cells require either `source_span_ids` or `bounding_regions` (`models.py:193-230`), and document validation checks cell span references against table/wrapper/cell page provenance (`models.py:535-545`). Covered by `test_table_cell_must_have_text_or_visual_provenance` and table tests (`test_layout_models.py:559-650`).
- **Table/figure detail linkage:** fixed. Table/figure wrapper blocks require detail IDs (`models.py:178-186`), table/figure detail models link through `layout_block_id` (`models.py:233-242`, `287-297`), and `DocumentIR` enforces bidirectional existence/type/ID matching (`models.py:530-533`, `622-680`). Covered by tests around missing IDs, mismatches, and duplicates (`test_layout_models.py:301-390`, `575-616`, `665-730`).
- **Duplicate/blank span refs:** fixed per span tuple. Shared validation rejects blank and duplicate span IDs (`models.py:124-129`) and is wired into blocks/cells/figures (`models.py:173-176`, `214-217`, `306-309`). Covered by `test_layout_span_id_tuples_must_not_contain_duplicates_or_empty_values` (`test_layout_models.py:184-205`).
- **Serialization round-trip:** functionally OK. Python dump/validate round-trip is covered (`test_layout_models.py:786-833`), and manual JSON smoke test passed. Add the JSON assertion as a small test nit.

## Tests attempted

I attempted to run the targeted suite:

```bash
uv run pytest tests/unit/document_intelligence/test_layout_models.py tests/unit/document_intelligence/test_parser_ports.py tests/integration/document_intelligence/test_pymupdf_parser.py
.venv/bin/python -m pytest tests/unit/document_intelligence/test_layout_models.py tests/unit/document_intelligence/test_parser_ports.py tests/integration/document_intelligence/test_pymupdf_parser.py
```

This environment does not currently have `pytest` installed/available (`No module named pytest` / `Failed to spawn: pytest`), so I could not execute the suite here. Manual smoke check confirmed `DocumentIR.model_dump_json()` / `DocumentIR.model_validate_json()` round-trips for a layout-bearing document.

## Required model fields/invariants now satisfied

- `DocumentIR.layout` remains optional for text-only flows.
- `DocumentLayout.blocks` is required and non-empty.
- Layout parser run IDs must reference existing `ParserRun`s, and duplicate parser run IDs are rejected.
- Blocks have deterministic unique `reading_order`; duplicate block/table/figure IDs are rejected.
- Parent block references exist; self-parenting and cycles are rejected.
- Text-bearing blocks cite source spans; table cells and figures have text or visual provenance.
- Referenced layout spans must exist, belong to the document ID, and fall within layout page provenance.
- Table cell row/column bounds, spans, roles, non-empty cells, and overlap are validated.
- Tables and figures attach to wrapper blocks and do not create a separate reading-order namespace.
- Layout models reject extra duplicate text/vendor-object fields.
- PyMuPDF remains a native-text baseline: no OCR, no layout/table IR, warning for partially textless PDFs, explicit `NoExtractableTextError` for fully textless PDFs.

## Deferred/future concerns

- Mutable lists remain inside frozen models (`ParserRun.warnings`, `Page.spans`, `DocumentIR.parser_runs`, `DocumentIR.pages`; `models.py:360`, `397`, `424`, `426`). This is existing IR shape and not a blocker for this step, but tuple conversion is safer before crossing trust/persistence boundaries.
- Consider rejecting the same span appearing in both `Figure.source_span_ids` and `Figure.caption_span_ids` if downstream treats those as semantically disjoint evidence sets.
- The PyMuPDF parser still uses `sort=True` coordinate ordering only; this matches the documented baseline limitation and should not be represented as semantic layout reconstruction.
