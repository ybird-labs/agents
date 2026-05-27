# Layout IR Agentic Engineering Review

## 1. Research performed

Fresh research was performed on 2026-05-26 before review.

Queries used:

- `2026 best practices structured LLM outputs JSON schema Pydantic validation LLM applications`
- `provider agnostic LLM interface Python architecture ports adapters Protocol fake client testing agents`
- `Python Protocol typing ports adapters architecture Pyright testing fake clients LLM apps`
- `evidence grounded summarization citations provenance document AI layout-aware chunking best practices`

External sources used:

- [Structured Output · llmbestpractices](https://llmbestpractices.com/ai-agents/structured-output)
- [LLM Structured Outputs in Production: Stop Parsing JSON with Regex — Effloow](https://effloow.com/articles/llm-structured-outputs-json-schema-production-guide-2026)
- [Protocols and structural subtyping — typing documentation](https://typing.python.org/en/latest/reference/protocols.html)
- [Dioxide Testing Guide: Fakes Over Mocks](https://dioxide.readthedocs.io/en/stable/TESTING_GUIDE.html)
- [Hexagonal Architecture with dioxide](https://dioxide.readthedocs.io/en/latest/user_guide/hexagonal_architecture.html)
- [RAG: Chunking · llmbestpractices](https://llmbestpractices.com/ai-agents/rag-chunking)
- [Attribute First, then Generate: Locally-attributable Grounded Text Generation](https://arxiv.org/html/2403.17104)
- [SPIRE: Structure-Preserving Interpretable Retrieval of Evidence](https://arxiv.org/pdf/2604.20849)
- [Evidence Units: Ontology-Grounded Document Organization for Parser-Independent Retrieval](https://arxiv.org/pdf/2604.00500)

Research takeaways applied: schema-first structured contracts should be validated before application logic consumes model output; ports/adapters plus Protocols keep provider boundaries testable; deterministic fakes are preferable at boundaries; evidence-backed generation needs precise source attribution and structure-preserving retrieval/chunking rather than flattened text.

## 2. Verdict

**CHANGE**.

I approve implementing **layout IR models + tests next before any Docling adapter**. That sequence is the right production move.

I do **not** approve implementing the current sketch literally without tightening the boundary. The next step must lock down layout as an Exeboard-owned, provider-agnostic organization layer over `DocumentIR` spans and page regions, with validation in or adjacent to `DocumentIR`. If layout is added as a loose optional object that downstream code may or may not validate, it will undermine provenance truth and later evidence-backed summarization.

Short answer to the explicit question: **approve layout IR next, reject Docling-first, reject parser-native layout leakage, reject unvalidated optional layout.**

## 3. Blockers before implementation

1. **No Docling types, parser-native IDs, or provider metadata in IR models.**
   - `ir` must define Exeboard-owned models only.
   - Docling translation belongs later in `parsing/adapters/docling.py`.
   - What breaks if skipped: chunking, validation, and summarization become coupled to one parser's object model and cloud/OCR adapters become migration projects instead of adapters.

2. **Layout references must be validated against the parent `DocumentIR`.**
   - A standalone `DocumentLayout` cannot know whether `source_span_ids` exist, belong to the same document, or match claimed pages.
   - Either:
     - add `DocumentIR.layout: DocumentLayout | None` and validate all references in `DocumentIR._validate_document_structure`, or
     - keep layout external but require an `attach_layout(document, layout) -> DocumentIR` helper that performs the same validation.
   - What breaks if skipped: a summary can cite real-looking span IDs that are absent, from another document, or not on the claimed page.

3. **Avoid a circular import trap.**
   - If layout models live in `ir/layout.py` and use `BoundingBox` from `ir/models.py`, then adding `DocumentIR.layout` in `models.py` can create a cycle.
   - Acceptable options:
     - place layout models in `ir/models.py` for this narrow step, or
     - move shared geometry types such as `BoundingBox` / `CoordinateSystem` into a small `ir/geometry.py` first.
   - Do not solve this with fragile runtime imports or string annotations that make Pydantic rebuild behavior obscure.

4. **Define authoritative text policy now.**
   - `TextSpan` + `DocumentIR.content` remain the citation source of truth.
   - Layout objects may reference spans and bounding regions; they must not become a second authoritative text store.
   - Prefer no `text` field on `LayoutBlock`/`TableCell` in the first implementation. If convenience text is included, `DocumentIR` validation must prove it equals reconstruction from referenced spans, or it must be explicitly named/typed as non-authoritative derived annotation.
   - What breaks if skipped: quote validation can pass against one text copy while a layout/table value used by summarization came from a divergent copy.

5. **Reading order must have one unambiguous scope.**
   - Do not have independent `reading_order` fields on blocks, tables, and figures unless duplicate-order validation is global across all of them.
   - Safer first boundary: `DocumentLayout.blocks` is the ordered skeleton; table/figure details attach to a table/figure block by ID. Then only blocks carry document-level reading order.
   - What breaks if skipped: layout-aware chunking can produce nondeterministic or duplicate ordering when a table is both a block and a table object.

6. **Coordinates must be normalized at the adapter boundary.**
   - Current `BoundingBox.coordinate_system` supports `pdf_points_top_left` only. Keep that as the canonical IR policy unless intentionally expanded.
   - Layout `BoundingRegion` should use canonical `BoundingBox`; parser-specific coordinate systems must be normalized before IR construction.
   - What breaks if skipped: highlighting, audit UI, and visual provenance point at the wrong region, especially for rotated pages or parsers with different origins.

## 4. Recommended protocol/model boundary

### Parser boundary

Keep the parser port unchanged for this step:

```python
class DocumentParser(Protocol):
    def parse(self, path: Path) -> DocumentIR: ...
```

This remains the correct sync, deterministic component boundary for the current MVP. Do not introduce async, retries, streaming, LLM harnesses, or provider SDK dependencies for layout IR. Parser adapters can populate `DocumentIR.layout` when they have layout; `PyMuPDFParser` can continue returning `layout=None`.

If a later use case requires layout, make that use case fail fast with a domain error such as `LayoutRequiredError` or a simple precondition, not by changing the parser port now.

### Exact IR shape I recommend

Use Exeboard-owned Pydantic models roughly like this. Names can vary, but the invariants should not.

```python
LayoutBlockType = Literal[
    "section",
    "heading",
    "paragraph",
    "list",
    "list_item",
    "table",
    "figure",
    "caption",
    "header",
    "footer",
    "page_number",
    "footnote",
    "unknown",
]

ContentLayer = Literal["body", "furniture", "unknown"]

class BoundingRegion(BaseModel):
    page_number: int = Field(ge=1)
    bbox: BoundingBox

class DocumentLayout(BaseModel):
    layout_version: str = "0.1"
    parser_run_id: str
    blocks: tuple[LayoutBlock, ...]
    tables: tuple[Table, ...] = ()
    figures: tuple[Figure, ...] = ()

class LayoutBlock(BaseModel):
    block_id: str
    block_type: LayoutBlockType
    content_layer: ContentLayer
    page_numbers: tuple[int, ...]
    reading_order: int = Field(ge=0)
    source_span_ids: tuple[SpanId, ...] = ()
    bounding_regions: tuple[BoundingRegion, ...] = ()
    parent_block_id: str | None = None
    table_id: str | None = None
    figure_id: str | None = None

class Table(BaseModel):
    table_id: str
    layout_block_id: str
    cells: tuple[TableCell, ...]
    bounding_regions: tuple[BoundingRegion, ...] = ()

class TableCell(BaseModel):
    row_index: int = Field(ge=0)
    column_index: int = Field(ge=0)
    row_span: int = Field(default=1, ge=1)
    column_span: int = Field(default=1, ge=1)
    is_header: bool = False
    source_span_ids: tuple[SpanId, ...] = ()
    bounding_regions: tuple[BoundingRegion, ...] = ()

class Figure(BaseModel):
    figure_id: str
    layout_block_id: str
    bounding_regions: tuple[BoundingRegion, ...]
    caption_span_ids: tuple[SpanId, ...] = ()
    source_span_ids: tuple[SpanId, ...] = ()
```

Key boundary choices:

- `DocumentIR.content` and `TextSpan` stay authoritative.
- `DocumentLayout` is organization/provenance over spans and regions.
- `LayoutBlock` owns reading order; `Table`/`Figure` attach rich structure to blocks instead of creating another competing order.
- `TableCell` preserves row/column semantics and span provenance but does not need a first-pass `text` field.
- Visual-only figures are valid with bounding regions and no fake spans.
- `parser_run_id` on `DocumentLayout` must match an existing `ParserRun` in the document.
- Pydantic models should be frozen and should use `extra="forbid"` for the new layout layer.

### Embedded vs helper attachment

Preferred implementation:

```python
class DocumentIR(BaseModel):
    ...
    layout: DocumentLayout | None = None
```

But only if `DocumentIR` validates layout references during model validation.

If adding that validator becomes too large or creates import problems, implement an `attach_layout(document, layout)` helper first and keep direct construction disciplined by tests. However, long-term, the invariant belongs with `DocumentIR` because tutorial-state already says invalid IR should not exist.

## 5. Risks in optional `DocumentIR.layout`

Optional layout is the right compatibility mechanism, but it has real risks:

1. **False sense of production support.**
   - `layout=None` is fine for native-text MVP, but complex PDF summarization must not silently fall back to span-order chunking.
   - Require layout-aware use cases to check `document.layout is not None`.

2. **Late validation failure.**
   - If layout references are not checked when the document is built, failures move into chunking/summarization after expensive parsing or LLM calls.

3. **Ambiguous parser capability.**
   - `layout=None` can mean parser does not support layout, layout extraction failed, or caller used the wrong adapter.
   - For now this is acceptable if `ParserRun.warnings` record explicit no-layout/failure reasons where applicable. Do not invent fake confidence or trace fields.

4. **Two divergent document truths.**
   - If layout carries its own text, downstream summarization may trust layout text while validators trust spans.
   - Avoid or strictly validate duplicated text.

5. **Chunker misuse.**
   - Current `chunk_document` remains valid for text-only flows, but must not be branded layout-aware.
   - A later `chunk_layout_document` should require `DocumentLayout` and preserve table/figure/block IDs alongside span IDs.

## 6. Tests required before Docling

Minimum unit tests before any Docling adapter spike:

1. **Valid layout attaches to a document.**
   - Blocks reference existing spans.
   - `parser_run_id` exists in `DocumentIR.parser_runs`.

2. **Missing span ID is rejected.**
   - Any block/cell/figure/caption source span not in `SpanIndex(document)` fails at `DocumentIR` construction or `attach_layout`.

3. **Cross-document span ID is rejected.**
   - A well-formed span ID from another UUID must not attach.

4. **Page mismatch is rejected.**
   - Referenced span page numbers must be included in the object's `page_numbers` or bounding regions, depending on model shape.

5. **Duplicate block IDs are rejected.**

6. **Duplicate reading order is rejected within the document layout skeleton.**

7. **Parent block references are valid.**
   - Missing parent rejected.
   - Self-parent rejected.
   - If hierarchy is implemented, cycles rejected.

8. **Table linkage is valid.**
   - Each `Table.layout_block_id` references a `LayoutBlock` of type `table`.
   - Duplicate table IDs rejected.
   - Cell row/column indices and spans are preserved.
   - Invalid `row_span`/`column_span` rejected.

9. **Figure linkage is valid.**
   - Each `Figure.layout_block_id` references a `LayoutBlock` of type `figure`.
   - Visual-only figure with bounding region and no spans is accepted.
   - Figure without spans and without bounding region is rejected.

10. **Furniture is representable and separate from body.**
    - Header/footer/page number blocks can be `content_layer="furniture"`.

11. **Multi-page/non-contiguous structure is representable.**
    - A section or table can include multiple page numbers and multiple bounding regions.

12. **Coordinate policy is enforced.**
    - Invalid/inverted bboxes rejected.
    - Accepted layout regions use the canonical coordinate system.

13. **No authoritative duplicate text.**
    - If any layout text field is added despite the recommendation, tests must reject text that does not reconstruct from referenced spans unless the field is explicitly non-authoritative.

14. **Legacy parser/chunker behavior remains unchanged.**
    - `PyMuPDFParser.parse(...)` still returns a valid `DocumentIR` without OCR and without pretending to provide layout.
    - `chunk_document(document)` still works for `layout=None` documents and remains span-based.

15. **Serialization round trip.**
    - `DocumentIR.model_dump()` / `model_validate()` preserves layout, table cells, figures, regions, and tuple immutability semantics.

## 7. Deferred/future concerns

Defer these until after layout IR tests exist:

- Docling adapter implementation.
- OCR strategy selection.
- Cloud parser adapters.
- LLM-generated figure/table descriptions.
- Layout-aware chunker implementation.
- Final summarizer changes.
- Retries, tracing, token/cost tracking, streaming, async parsing.

When LLM-bound summarization later consumes layout, follow schema-first structured outputs with Pydantic validation at the LLM boundary. LLM proposals must cite `SpanId`s and cannot create layout provenance. Derived descriptions from figures/tables should be separate non-authoritative annotations unless backed by OCR/text spans.

## 8. Naming/layout refinements

- Prefer `ir/layout.py` only if shared geometry is moved to avoid circular imports. Otherwise keep layout models in `ir/models.py` for the first step.
- Use `BoundingRegion`, not just `bbox`, for layout objects because page number is part of visual provenance.
- Use `content_layer`, not `is_header_footer`, because body/furniture/unknown generalizes without overfitting.
- Keep `PyMuPDFParser` as a native-text baseline; do not add hidden table/OCR/layout behavior to it.
- Consider typed aliases later (`LayoutBlockId`, `TableId`, `FigureId`), but do not block MVP on elaborate ID helpers. Non-empty unique strings are enough if document-level validators enforce uniqueness and references.

## 9. Production shortcut warnings

These shortcuts would break evidence-backed summarization:

- **Flattening tables into prose only:** validators can find numbers but cannot prove row/column context; financial claims become audit-weak.
- **Letting layout text diverge from spans:** quote validation and summarization rely on different truths.
- **Silent OCR fallback:** cost, latency, privacy, and error profile change invisibly; tests become non-reproducible.
- **LLM-inferred layout:** plausible structure is not provenance; validators cannot distinguish inferred relationships from actual document evidence.
- **Using PyMuPDF `sort=True` as semantic reading order:** coordinate sorting is not enough for columns, captions, page furniture, and table semantics.
- **Exposing Docling-native objects:** breaks provider isolation and makes future adapters contaminate core chunking/summarization.

Final position: implement layout IR next, but make it a validated Exeboard-owned layer over `DocumentIR`, not an optional bag of parser output.
