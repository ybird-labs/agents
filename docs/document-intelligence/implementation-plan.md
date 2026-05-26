# Evidence-Backed Document Summary Component — Implementation Plan

## Status

Validated plan for building a reusable summary-first Document Intelligence component inside the existing Exeboard monorepo.

This is a **component/library**, not a full app.

## Correct repository location

Component code belongs in:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/
```

Reason:

- `apps/` is for deployable processes.
- `packages/` is for reusable packages.
- `packages/exeboard-ai` owns AI orchestration, LLM-facing abstractions, prompt loading, and AI runtime composition.
- This component is reusable AI/runtime logic, not a deployable API or worker.

Apps, workers, or agents may call this component later, but this component must not import from `apps/`.

## MVP goal

Build evidence-backed PDF summarization.

Given a single mostly digital PDF path, the component should:

```text
PDF path
  -> PyMuPDF parser
  -> canonical DocumentIR
  -> chunk spans
  -> chunk-level cited summary claims
  -> validate citations and quotes
  -> final summary from validated claims only
```

## MVP non-goals

Do not build these in the first MVP:

- Q&A
- structured fact extraction
- complex table IR
- OCR guarantees
- Docling integration
- FastAPI endpoints
- workers
- database persistence
- human review UI
- multi-document reasoning
- provider-specific LLM SDK adapters

## Component layout

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/
  __init__.py

  core/
    __init__.py
    ids.py

  ir/
    __init__.py
    models.py
    span_index.py

  parsing/
    __init__.py
    ports.py
    adapters/
      __init__.py
      pymupdf.py

  chunking/
    __init__.py
    models.py
    chunker.py

  summarization/
    __init__.py
    models.py
    ports.py
    prompts.py
    chunk_summarizer.py
    final_summarizer.py
    pipeline.py

  validation/
    __init__.py
    citation_validator.py
    quote_validator.py
```

## Tests and fixtures

```text
tests/unit/document_intelligence/
tests/integration/document_intelligence/
tests/fixtures/document_intelligence/
```

## Documentation

```text
docs/document-intelligence/
  implementation-plan.md
  tutorial.md
  mvp_scope.md
  id_semantics.md
  ir_v0_1.md
  citation_semantics.md
  summary_pipeline.md
  evaluation.md
```

## Evaluation assets

Static eval assets belong under top-level `evals/`:

```text
evals/datasets/document_intelligence/
evals/prompts/document_intelligence/
evals/reports/document_intelligence/
```

Executable evaluation code should be deferred until after the MVP pipeline exists. When added, it belongs in:

```text
packages/exeboard-evals/src/exeboard_evals/document_intelligence/
```

## Dependency rules

The component should accept plain Python inputs and protocol implementations.

Allowed core inputs:

- `pathlib.Path`
- Pydantic/dataclass models
- parser protocol implementations
- LLM protocol implementations

The MVP component must not depend on:

- FastAPI
- database sessions
- Temporal
- Redis
- web request objects
- UI code
- `apps/*`

Correct dependency direction:

```text
apps/api or apps/workers later
  -> imports exeboard_ai.document_intelligence
```

Incorrect dependency direction:

```text
exeboard_ai.document_intelligence
  -> imports apps/*
```

## Key reasoning

### Why IR first?

The product is an evidence-backed summary. Evidence-backed summary claims need citations. Citations need:

- stable span IDs
- page numbers
- source text
- optional bounding boxes

Therefore the minimal canonical IR must exist before summarization.

### Why parser adapters?

Parser outputs vary. PyMuPDF, Docling, pdfplumber, OCR systems, and future cloud parsers all expose different shapes.

Downstream summarization and validation should depend only on `DocumentIR`, not parser-specific objects.

### Why chunk-level claims before final summary?

Long PDFs cannot reliably be summarized in one prompt. Chunk-level claim extraction gives you smaller, inspectable, evidence-backed units.

### Why validate before final summary?

The final summary should not be able to include unsupported claims. The safe flow is:

```text
chunk claims -> citation/quote validation -> valid claims only -> final summary
```

### Why no real LLM SDK at first?

A protocol plus fake LLM lets you build and test the pipeline deterministically. Real provider adapters can be wired later by app/worker composition.

## Implementation order

### Step 0 — Write supporting docs

Create or fill in:

```text
docs/document-intelligence/mvp_scope.md
docs/document-intelligence/ir_v0_1.md
docs/document-intelligence/citation_semantics.md
docs/document-intelligence/summary_pipeline.md
docs/document-intelligence/evaluation.md
```

### Step 1 — IDs and IR models

Files:

```text
core/ids.py
ir/models.py
```

ID semantics:

- document files are named `<uuid>.<file_extension>`
- `DocumentId` is the canonical UUID stem
- file extension is source/file metadata, not part of `DocumentId`
- page/span/chunk/claim IDs are deterministic composite provenance IDs under the document UUID namespace

Define ID helpers:

- `validate_document_id(document_id)`
- `make_document_id_from_file_name(file_name)`
- `make_page_id(document_id, page_number)`
- `make_span_id(document_id, page_number, span_index)`
- `make_chunk_id(document_id, chunk_index)`
- `make_claim_id(document_id, claim_index)`

Define IR models:

- `DocumentIR`
- `ParserRun`
- `Page`
- `Span`
- `BoundingBox`

Acceptance:

- valid UUID document IDs are accepted and canonicalized
- invalid document IDs are rejected
- `<uuid>.<extension>` file names produce the UUID stem
- deterministic page/span/chunk/claim IDs are generated
- invalid page numbers and negative indexes are rejected
- fake `DocumentIR` serializes
- unit tests cover ID helpers

### Step 2 — Span index

File:

```text
ir/span_index.py
```

Responsibilities:

- look up span by ID
- get multiple spans
- reconstruct page text
- get text for cited spans

Acceptance:

- valid span lookup works
- invalid span lookup fails clearly
- page text reconstruction works

### Step 3 — Parser interface and PyMuPDF parser

Files:

```text
parsing/ports.py
parsing/adapters/pymupdf.py
```

Define a `DocumentParser` port:

```python
class DocumentParser(Protocol):
    def parse(self, path: Path) -> DocumentIR:
        ...
```

Implement PyMuPDF adapter:

```text
PDF -> pages -> spans -> DocumentIR
```

Dependency note:

Add `pymupdf` to `packages/exeboard-ai/pyproject.toml` when this step is implemented. Current production policy uses `pymupdf>=1.27.2.3,<1.28` with `uv.lock` resolving the exact build used by this repo.

Acceptance:

- fixture PDF parses
- pages have spans
- spans have IDs/page numbers/text
- parser run metadata is recorded
- invalid/empty PDFs raise `UnreadableDocumentError`
- encrypted PDFs raise `EncryptedDocumentError`
- PDFs with no extractable digital text raise `NoExtractableTextError`
- partially textless PDFs return `DocumentIR` with warnings
- OCR is not silently attempted by the native PyMuPDF adapter

### Step 4 — Chunking

Files:

```text
chunking/models.py
chunking/chunker.py
```

Chunk model should include:

- `chunk_id`
- `document_id`
- `text`
- `page_numbers`
- `source_span_ids`
- `chunk_type`

Initial chunking rule:

```text
Group consecutive spans into approximately 1500–2500 character chunks.
```

Acceptance:

- chunks preserve span IDs
- every chunk span ID exists in the IR
- chunk order follows document order

### Step 5 — Summary models

File:

```text
summarization/models.py
```

Define:

- `DocumentType`
- `ClaimRole`
- `ClaimEvidence`
- `SummaryClaim`
- `ChunkSummary`
- `SummarySentence`
- `DocumentSummary`

Use a generic fallback document type plus document-type-specific role validation:

```python
DocumentType = Literal[
    "generic",
    "financial_report",
    "business_review",
    "contract",
    "meeting_notes",
]

ClaimRole = Literal[
    "finding",
    "forecast",
    "risk",
    "recommendation",
    "action_item",
    "decision",
    "open_question",
    "obligation",
    "entitlement",
    "prohibition",
]
```

Allowed roles:

```text
generic:            finding, risk, recommendation, action_item, open_question
financial_report:   finding, forecast, risk, open_question
business_review:    finding, forecast, risk, recommendation, action_item, open_question
contract:           finding, risk, obligation, entitlement, prohibition, open_question
meeting_notes:      finding, decision, action_item, risk, open_question
```

`SummaryClaim` should use structured evidence, not flat citation fields:

```python
class ClaimEvidence(BaseModel):
    quote: str
    page_number: int
    source_span_ids: tuple[SpanId, ...]
    source_chunk_ids: tuple[ChunkId, ...]

class SummaryClaim(BaseModel):
    claim_id: ClaimId
    document_id: DocumentId
    document_type: DocumentType
    claim: str
    claim_role: ClaimRole
    importance: Literal["low", "medium", "high"]
    evidence: tuple[ClaimEvidence, ...]
    derived_from_claim_ids: tuple[ClaimId, ...] = ()
    validation_status: Literal["unvalidated", "valid", "invalid"] = "unvalidated"
    validation_errors: tuple[str, ...] = ()
```

Final summaries should avoid uncited freeform prose. Use cited summary sentences:

```python
class SummarySentence(BaseModel):
    text: str
    supporting_claim_ids: tuple[ClaimId, ...]
```

`DocumentSummary` should contain non-empty `summary_sentences` and non-empty `claims`; every sentence must cite existing claim IDs.

Acceptance:

- models serialize cleanly
- missing evidence fields are rejected
- uncited summary sentences are rejected
- claim roles are validated against document type
- IDs are validated against the current deterministic ID grammar
- evidence page numbers match encoded source span pages
- duplicate claim/span/chunk/supporting IDs are rejected
- validation status and validation errors are structurally consistent

### Step 6 — Structured generation port

File:

```text
summarization/ports.py
```

Define a provider-agnostic port for structured generation. This is a boundary contract, not an LLM implementation.

Current port shape:

```python
class StructuredGenerationRequest(BaseModel):
    operation_name: str
    prompt_name: str
    prompt_version: str
    output_schema_name: str
    output_schema_version: str
    prompt: str
    replay_key: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

class StructuredResponseGenerator(Protocol):
    def generate(
        self,
        *,
        request: StructuredGenerationRequest,
        output_model: type[T],
    ) -> T: ...
```

Do not bind the component to OpenAI, Anthropic, Gemini, etc. Tests should use a fake `StructuredResponseGenerator`.

Acceptance:

- chunk summarizer can run against a fake structured response generator
- no provider SDK dependency required

### Step 7 — Chunk summarizer

Files:

```text
summarization/prompts.py
summarization/chunk_summarizer.py
```

Prompt rules:

- only use the provided chunk
- every claim must include an exact quote
- every claim must cite source span IDs from the provided evidence
- do not invent page numbers or span IDs
- if no meaningful claim exists, return empty claims

Acceptance:

- one chunk produces `ChunkSummary`
- deterministic fake LLM test passes
- output parsing is tested

### Step 8 — Citation and quote validation

Files:

```text
validation/citation_validator.py
validation/quote_validator.py
```

Citation validator checks citation references only:

- span IDs exist in the `SpanIndex`
- cited page number matches the actual cited spans
- validator `SpanIndex` document matches the claim document

Citation validation returns a separate `CitationValidationResult`; it must not mutate `SummaryClaim.validation_status`. Citation validity is not aggregate claim validity because a claim can be citation-valid but quote-invalid.

Citation error codes:

```text
invalid_span_id
page_mismatch
document_mismatch
```

Quote validator checks quote support separately:

- quote appears in cited span text
- or quote appears on cited page
- normalized/fuzzy matches are marked separately and are not silently treated as fully valid

Quote validation statuses/codes:

```text
quote_not_found
normalized_match_only
fuzzy_match
```

Acceptance tests:

- valid citations return `CitationValidationResult(valid=True, errors=())`
- fake span ID returns `invalid_span_id`
- wrong cited page returns `page_mismatch`
- claim/index document mismatch returns `document_mismatch`
- citation validation does not mark `SummaryClaim.validation_status="valid"`
- missing quote fails in quote validation
- exact quote passes in quote validation
- normalized whitespace match is classified explicitly in quote validation

### Step 9 — Final summarizer

File:

```text
summarization/final_summarizer.py
```

Rules:

- receives validated claims only
- does not introduce new claims
- preserves citation lineage

Acceptance:

- invalid claims are excluded
- final summary preserves source claim IDs/spans/pages

### Step 10 — Pipeline

File:

```text
summarization/pipeline.py
```

Main flow:

```text
parse PDF
build span index
chunk document
summarize each chunk
validate citations -> CitationValidationResult
validate quotes -> QuoteValidationResult
aggregate validation results outside individual validators
filter invalid claims
synthesize final summary
return DocumentSummary
```

Main callable:

```python
summarize_document(
    pdf_path: Path,
    parser: DocumentParser,
    response_generator: StructuredResponseGenerator,
) -> DocumentSummary
```

Acceptance:

- integration test runs end-to-end with fake LLM
- no API/database/worker dependency exists

## MVP acceptance criteria

The MVP is complete when:

1. A fixture PDF parses into `DocumentIR`.
2. Spans have deterministic IDs.
3. Chunks preserve source span IDs.
4. Chunk summarizer returns structured cited claims.
5. Citation validator rejects invented span IDs.
6. Quote validator rejects missing quotes.
7. Final summary uses only valid claims.
8. Pipeline runs end-to-end with a fake LLM.
9. No code imports from `apps/`.
10. No API/database/worker dependency exists in the component.

## Later extensions

Only after the MVP works:

1. Real LLM provider adapter wired by an app/worker composition layer.
2. Evaluation runner in `packages/exeboard-evals`.
3. Docling parser adapter.
4. OCR fallback.
5. Table IR and table-aware summaries.
6. Q&A over validated IR/chunks.
7. Structured fact extraction.
8. Human review workflow.
