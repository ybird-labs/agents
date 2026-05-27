# Docling choice / Python DI architecture review

Date: 2026-05-26

## 1. Research performed and sources used

Fresh web research was performed before review.

Sources consulted:

- [Docling project README](https://github.com/docling-project/docling?tab=readme-ov-file) — Docling advertises multi-format parsing, advanced PDF understanding, layout, tables, pictures, formulas, and gen-AI integrations.
- [DoclingDocument - Docling](https://docling-project-docling.mintlify.app/concepts/docling-document) — DoclingDocument is a Pydantic representation with rich content types, hierarchy, content classification, layout information, and provenance.
- [Docling Document API reference](https://docling-project.github.io/docling/reference/docling_document/) — public API includes provenance-oriented document structures and export methods.
- [Chunking - Docling](https://docling-project-docling.mintlify.app/concepts/chunking) — native Docling chunking preserves document structure and metadata better than export-then-chunk paths.
- [docling v2.95.0 on PyPI](https://pypi.org/project/docling/) — current package state indicates Docling is actively moving; pin choice must be deliberate.
- [RAG: Citations · llmbestpractices](https://llmbestpractices.com/ai-agents/rag-citations) — citations should be treated as checkable source links; uncited or unverifiable factual claims are failures.
- [How to Build an Answer Grounding Pipeline](https://geodocs.dev/technical/how-to-build-answer-grounding-pipeline) — grounded pipelines need observable evidence extraction, attribution, and post-generation guardrails.
- [Pydantic v2 Unions docs](https://pydantic.dev/docs/validation/2.10/concepts/unions/) and [Fields docs](https://pydantic.dev/docs/validation/2.10/concepts/fields) — favor explicit validation behavior and type shapes that are statically testable.

## 2. Verdict

**CHANGE**

Docling is a reasonable next parser candidate, but it should not be accepted as the next full adapter solely from documentation. The plan is directionally strong and mostly agent-friendly, but the next executable step must be narrowed to a **real Docling discovery + tiny bakeoff gate** before any full mapper implementation.

The architecture choice is correct: Docling must remain an adapter feeding Exeboard-owned `DocumentIR`/`DocumentLayout`, with `DocumentIR.content` and `TextSpan` as citation truth. The plan is also right to forbid guessed fake Docling objects, silent OCR, remote inference, and Docling-native leakage.

However, current repository state still has concrete gaps before implementation:

- `ParserDependencyError` is planned but absent from `parsing/ports.py`.
- `pyproject.toml` has no `docling` optional dependency group yet.
- ID parsing still uses exactly four digits (`\d{4}`), while ID makers produce five+ digits for large page/span counts; the plan correctly identifies this but it is still unresolved.
- The Docling version pin in the plan (`2.78.0`) needs bakeoff confirmation because current public package discovery shows newer Docling releases.

## 3. Blockers before implementation

### Blocker A — run Slice 0 as a bakeoff/discovery gate, not as part of mapper implementation

Before implementing `DoclingMapper`, create the discovery artifact and a tiny bakeoff report. The bakeoff should compare:

1. current `PyMuPDFParser` baseline, and
2. Docling with OCR and remote services explicitly disabled.

Use 3-5 deterministic local fixtures only:

- one simple digital text PDF,
- one two-column or layout-order PDF,
- one simple table PDF,
- one captioned figure or visual block PDF,
- one image-only/scanned PDF to prove no silent OCR.

Acceptance must be provenance-focused, not accuracy-marketing-focused:

- Can Docling expose stable page numbers, text items, reading order, labels/roles, bboxes, and table/figure provenance through public APIs?
- Can those be mapped into existing `TextSpan`, `LayoutBlock`, `TableCell`, `Figure`, and `BoundingRegion` without Markdown-only flattening?
- Can OCR and remote services be proven disabled by explicit config or documented defaults?
- Does first use require model downloads/artifacts?

If these are not proven, stop. Do not build fake-shaped unit tests first.

### Blocker B — optional dependency and missing exception boundary

Before adapter skeleton work:

- Add `ParserDependencyError(DocumentParseError)`.
- Add `[project.optional-dependencies] docling = [...]`.
- Add an import-time test proving base `exeboard_ai` import does not require Docling.
- Lazy-import Docling only when constructing the real default converter.

### Blocker C — fake-vs-real Docling shape discipline

The plan says fakes must mirror discovered real API shape. Make this enforceable:

- Commit `docs/document-intelligence/docling-api-notes.md` first.
- Include a tiny sanitized dump/schema sketch of consumed fields.
- Name every consumed Docling attribute/method.
- Unit fakes should implement only that subset. If mapper tests need fields not in the notes, the notes must be updated first.

### Blocker D — provenance cannot be inferred from semantic similarity

The mapper must not align layout blocks to spans using fuzzy or semantic matching as the normal path. Provenance must come from construction order, parser references, native charspans, or exact normalized text checks. A bad citation must fail rather than pass due to loose similarity.

### Blocker E — CI/runtime risk must be explicit

Docling is likely heavier and more operationally variable than PyMuPDF. Keep real Docling tests out of normal unit CI unless the dependency/artifact story is proven stable. Integration tests must be both dependency-gated and environment-gated.

## 4. Recommended API/model shape

The proposed public shape is mostly right:

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

Recommended refinements:

- Keep `DoclingParser` thin: filesystem/source hashing, lazy dependency construction, exception translation, and call into a pure mapper.
- Add a private `DoclingMapper` with no IO, no imports that require Docling, no network/model side effects.
- Consider a narrow internal `Protocol` for the discovered converter/result subset after Slice 0. This improves fake tests and Pyright without exposing Docling types publicly.
- Do not expose `require_layout=False`. This parser is selected because it is layout-aware; no-layout success should be a parser-port failure.
- Use current `DocumentLayout` models as the Exeboard boundary. They are largely appropriate: frozen Pydantic models, table/figure wrapper links, span-reference validation in `DocumentIR`, page/bbox validation, and no authoritative duplicate layout text.

Model caveat: the adapter should determine “text-bearing” from actual Docling item text, not only from `LayoutBlockType`. `SECTION`, `LIST`, or `UNKNOWN` may be text-bearing in a real parser result; if text exists and cannot be connected to spans, raise `SpanAlignmentError`.

## 5. Matching policy recommendation

For adapter mapping:

1. **Preferred:** build `DocumentIR.content` directly from the exact text used to create `TextSpan.text`; offsets are generated during assembly.
2. Use Docling native provenance/refs to connect layout items to generated spans.
3. If Docling gives charspans, use them as cross-checks, not as a separate independent content source unless proven canonical.
4. Normalize only deterministic PDF extraction artifacts when comparing text:
   - line break and whitespace collapse,
   - soft hyphen removal,
   - end-of-line hyphenation repair where unambiguous,
   - Unicode normalization/smart quote folding if explicitly documented.
5. Do **not** use semantic similarity or low-threshold fuzzy matching to make layout/span alignment pass.
6. Any text-bearing Docling item that cannot be exactly or explicitly-normalized aligned to generated spans should fail with `SpanAlignmentError`.

This preserves source-span semantics required for later quote/citation validation.

## 6. Required tests

Minimum tests before accepting the adapter beyond Slice 0:

- Base import succeeds without Docling installed.
- Missing optional Docling dependency raises `ParserDependencyError`, not `ImportError`.
- Injected fake converter path does not import Docling.
- Fake objects mirror documented real Docling API subset.
- Simple one-page PDF maps title/paragraph to spans, content offsets, pages, and layout blocks.
- Multi-page mapping validates page IDs, span IDs, page-local reading orders, and layout page provenance.
- Table mapping preserves row/column indices, spans, roles, wrapper block linkage, and row-major content assembly.
- Figure mapping supports caption-backed and visual-only figures without fake spans.
- Header/footer/page-number map to `ContentLayer.FURNITURE`.
- Unknown labels map conservatively and deterministically.
- Invalid bbox/page/coordinate values map to `LayoutExtractionError` where provenance is required.
- Text-bearing item with no span mapping raises `SpanAlignmentError`.
- Successful conversion with no text raises `NoExtractableTextError`.
- Mapper-created Pydantic `ValidationError` is translated to the correct parser-port error.
- Serialized `DocumentIR` contains no Docling-native objects.
- Parser run metadata records Docling version/strategy and `ocr_enabled=false`, `remote_services_enabled=false`.
- Opt-in integration tests are skipped unless both Docling is installed and `EXEBOARD_RUN_DOCLING_INTEGRATION=1`.
- Image-only PDF with default config proves no silent OCR.
- ID round-trip test for page/span index `10000` after changing regex to `\d{4,}`.

## 7. Deferred/future concerns

Do not pull these into the next step:

- layout-aware chunking,
- summarization changes,
- quote validator implementation,
- OCR strategy,
- cloud parser integration,
- table extraction quality tuning beyond minimal provenance tests,
- UI/highlighting,
- databases/workers/APIs.

Future concerns after adapter viability is proven:

- Whether Docling table/figure extraction is stable enough across generated and real PDFs.
- How to represent parser confidence and partial extraction warnings in a structured way instead of overloading `ParserRun.warnings`.
- Whether rotated pages need a stricter coordinate normalization policy.
- Whether Docling artifacts/model downloads require an explicit local cache configuration in production.

## 8. Naming/layout refinements

Suggested file layout:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/parsing/adapters/docling.py
packages/exeboard-ai/src/exeboard_ai/document_intelligence/parsing/adapters/_docling_mapper.py
packages/exeboard-ai/src/exeboard_ai/document_intelligence/parsing/adapters/_docling_types.py  # optional internal Protocols after discovery
```

Suggested docs/test artifacts:

```text
docs/document-intelligence/docling-api-notes.md
docs/document-intelligence/docling-bakeoff.md
tests/unit/document_intelligence/parsing/test_docling_parser.py
tests/unit/document_intelligence/parsing/test_docling_mapper.py
tests/integration/document_intelligence/test_docling_parser_integration.py
```

Concrete next step:

**Do only Slice 0 plus the tiny bakeoff.** Produce `docling-api-notes.md` and `docling-bakeoff.md`, proving real API shape, provenance, coordinate semantics, OCR/remote behavior, artifact/download behavior, and baseline comparison against PyMuPDF. Do not implement the full adapter until that gate passes.
