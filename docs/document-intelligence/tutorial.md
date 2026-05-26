# Tutorial: Build the Evidence-Backed Summary Component Yourself

This tutorial is a step-by-step guide for implementing the summary-first Document Intelligence component.

The goal is learning. Do each step manually and stop after each checkpoint.

## How to use this tutorial interactively

This tutorial is designed for a mentor-style workflow with the assistant.

You write the code. The assistant helps you reason, review, debug, and decide the next step.

### Ground rules

- Do **not** ask the assistant to implement the component for you.
- Do ask the assistant to explain concepts, review snippets, design tests, and debug errors.
- Move one part at a time.
- Stop at each checkpoint before continuing.
- If a design choice feels unclear, ask before coding further.

### Recommended interaction loop

For each part:

1. Read the part.
2. Ask any conceptual questions.
3. Write the code yourself.
4. Run the checkpoint command.
5. Paste errors, test failures, or confusing output.
6. Ask whether your implementation still respects the architecture.
7. Move to the next part only when the checkpoint passes.

### Good questions to ask

Use questions like:

```text
I am on Part 2. Why do we format page numbers with four digits?
```

```text
I wrote this Span model. Does it preserve enough provenance for citation validation?
```

```text
This test is failing. Explain what the failure means, but don't rewrite the code for me.
```

```text
Before I continue, does this design violate the package boundaries?
```

```text
Give me a hint, not the full answer.
```

### When you paste code

Paste only the smallest relevant snippet and include:

- which part you are on
- file path
- what you expected
- what happened
- exact error message, if any

Example:

```text
Part 4, span_index.py.
I expected get_span("doc:p0001:s0001") to return a Span.
Instead I get KeyError.
Here is the test and the function.
```

### Assistant behavior you should request

If you want to stay in learning mode, say:

```text
Review this Socratically. Ask me questions before giving the answer.
```

or:

```text
Give me a small hint only.
```

or:

```text
Explain the tradeoff, then let me choose.
```

### Stop signs

Pause and ask questions if any of these happen:

- you are about to add an API, database, worker, or UI code
- a module wants to import from `apps/`
- parser-specific objects leak into chunking or summarization
- a summary claim has no source span IDs
- the final summary sees unvalidated claims
- a test needs a real LLM provider to pass

## What you are building

A reusable Python component in:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/
```

It will take a PDF path and produce an evidence-backed summary.

Pipeline:

```text
PDF path
  -> parse into DocumentIR
  -> chunk spans
  -> summarize chunks into cited claims
  -> validate citations and quotes
  -> synthesize final summary from valid claims
```

## What you are not building yet

Do not build these yet:

- API endpoints
- database storage
- workers
- Q&A
- structured fact extraction
- tables
- OCR guarantees
- real LLM provider adapters

## Before you code

Read:

```text
docs/file-structure.md
docs/document-intelligence/implementation-plan.md
```

The important repo rule is:

```text
packages/exeboard-ai = reusable AI component code
apps/* = deployable app composition later
```

Your component must not import from `apps/`.

---

# Part 1 — Create the component skeleton

Create folders under:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/
```

Target skeleton:

```text
document_intelligence/
  __init__.py
  core/__init__.py
  ir/__init__.py
  parsing/__init__.py
  chunking/__init__.py
  summarization/__init__.py
  validation/__init__.py
```

Also create test folders:

```text
tests/unit/document_intelligence/
tests/integration/document_intelligence/
tests/fixtures/document_intelligence/
```

Checkpoint:

```bash
find packages/exeboard-ai/src/exeboard_ai/document_intelligence -maxdepth 3 -type f | sort
```

You should see only empty `__init__.py` files at this point.

---

# Part 2 — Implement stable IDs

Read first:

```text
docs/document-intelligence/id_semantics.md
```

File:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/core/ids.py
```

Document files are named:

```text
<uuid>.<file_extension>
```

Example:

```text
550e8400-e29b-41d4-a716-446655440000.pdf
```

The `DocumentId` is the UUID stem:

```text
550e8400-e29b-41d4-a716-446655440000
```

The extension is source/file metadata. It is not part of the document ID.

Implement helpers conceptually like:

```python
DocumentId = str
PageId = str
SpanId = str
ChunkId = str
ClaimId = str


def validate_document_id(document_id: str) -> DocumentId:
    ...


def make_document_id_from_file_name(file_name: str) -> DocumentId:
    ...


def make_page_id(document_id: DocumentId, page_number: int) -> PageId:
    ...


def make_span_id(
    document_id: DocumentId,
    page_number: int,
    span_index: int,
) -> SpanId:
    ...


def make_chunk_id(document_id: DocumentId, chunk_index: int) -> ChunkId:
    ...


def make_claim_id(document_id: DocumentId, claim_index: int) -> ClaimId:
    ...
```

Expected ID formats:

```text
PageId:  <uuid>:p0001
SpanId:  <uuid>:p0001:s0000
ChunkId: <uuid>:c0000
ClaimId: <uuid>:claim0000
```

Reason:

A summary claim cannot be audited unless it points to stable source spans. The document UUID anchors the provenance chain; page/span/chunk/claim IDs are deterministic IDs inside that document namespace.

Test file:

```text
tests/unit/document_intelligence/test_ids.py
```

Test:

- valid UUID document ID is accepted and canonicalized
- invalid document ID is rejected
- `<uuid>.pdf` file name returns the UUID stem
- page ID is deterministic
- span ID includes document ID and page number
- chunk ID is deterministic
- claim ID is deterministic
- page numbers must be 1 or greater
- span/chunk/claim indexes must be 0 or greater

Checkpoint:

```bash
uv run pytest tests/unit/document_intelligence/test_ids.py
```

---

# Part 3 — Define minimal IR models

File:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/ir/models.py
```

Use Pydantic or dataclasses. If you use Pydantic, add it to:

```text
packages/exeboard-ai/pyproject.toml
```

Minimal models:

```text
BoundingBox
ParserRun
Span
Page
DocumentIR
```

Suggested fields:

```python
class BoundingBox:
    x0: float
    y0: float
    x1: float
    y1: float
    coordinate_system: str
```

```python
class Span:
    span_id: str
    page_number: int
    text: str
    bbox: BoundingBox | None = None
```

```python
class Page:
    page_id: str
    page_number: int
    width: float | None = None
    height: float | None = None
    rotation: int | None = None
    spans: list[Span]
```

```python
class DocumentIR:
    ir_version: str
    document_id: str
    parser_runs: list[ParserRun]
    pages: list[Page]
```

Reason:

You only model what evidence-backed summaries need:

- document
- page
- span
- text
- page number
- optional bbox

Do not add tables or sections yet.

Test file:

```text
tests/unit/document_intelligence/test_ir_models.py
```

Test:

- fake `DocumentIR` can be created
- fake `DocumentIR` can serialize to dict/JSON
- page contains spans

Checkpoint:

```bash
uv run pytest tests/unit/document_intelligence/test_ir_models.py
```

---

# Part 4 — Build the span index

File:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/ir/span_index.py
```

Implement a helper class that takes `DocumentIR` and supports:

```python
get_span(span_id)
get_spans(span_ids)
get_page_text(page_number)
get_text_for_spans(span_ids)
```

Reason:

Validators need a fast, central way to check whether citations are real.

Test file:

```text
tests/unit/document_intelligence/test_span_index.py
```

Test:

- valid span ID returns span
- invalid span ID raises/returns clear failure
- page text reconstruction works
- multi-span text extraction works

Checkpoint:

```bash
uv run pytest tests/unit/document_intelligence/test_span_index.py
```

---

# Part 5 — Define the parser interface

File:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/parsing/ports.py
```

Define a protocol:

```python
from pathlib import Path
from typing import Protocol

from exeboard_ai.document_intelligence.ir.models import DocumentIR


class DocumentParser(Protocol):
    def parse(self, path: Path) -> DocumentIR:
        ...
```

Reason:

Later you can add Docling, OCR, or cloud parsers without changing summarization code.

Checkpoint:

No runtime behavior yet. This is a boundary contract.

---

# Part 6 — Implement the PyMuPDF parser

File:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/parsing/adapters/pymupdf.py
```

First add dependency:

```text
packages/exeboard-ai/pyproject.toml
```

Add:

```text
pymupdf>=1.27.2.3,<1.28
```

Then implement:

```text
PDF -> pages -> spans -> DocumentIR
```

Use PyMuPDF to:

- open PDF
- iterate pages
- get page dimensions
- extract text blocks/spans
- assign deterministic span IDs
- create `DocumentIR`
- record parser metadata in `ParserRun`

Do not worry about perfect tables or OCR. The native PyMuPDF adapter should not silently run OCR. If a document has no extractable digital text, raise a parser-port failure such as `NoExtractableTextError` so a separate OCR adapter can be selected explicitly later. If only some pages lack text, return `DocumentIR` with parser warnings.

Fixture:

Put a small digital PDF in:

```text
tests/fixtures/document_intelligence/sample.pdf
```

Integration test:

```text
tests/integration/document_intelligence/test_pymupdf_parser.py
```

Test:

- parser returns `DocumentIR`
- document has pages
- pages have spans
- spans have text
- spans have page numbers
- fully textless PDF raises `NoExtractableTextError`
- partially textless PDF returns `DocumentIR` with warnings
- invalid/empty PDF raises `UnreadableDocumentError`
- encrypted PDF raises `EncryptedDocumentError`

Checkpoint:

```bash
uv run pytest tests/integration/document_intelligence/test_pymupdf_parser.py
```

---

# Part 7 — Define chunks

File:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/chunking/models.py
```

Define `Chunk`:

```python
class Chunk:
    chunk_id: str
    document_id: str
    text: str
    page_numbers: list[int]
    source_span_ids: list[str]
    chunk_type: str
```

Reason:

The LLM summarizes chunks, not the whole PDF. But every chunk must preserve source spans.

Test:

- chunk serializes
- chunk has source span IDs

---

# Part 8 — Implement the chunker

File:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/chunking/chunker.py
```

Implement:

```python
def chunk_document(document_ir: DocumentIR, target_chars: int = 2000) -> list[Chunk]:
    ...
```

Initial rule:

```text
Group consecutive spans until roughly 1500–2500 characters.
```

For each chunk, preserve:

- text
- page numbers
- source span IDs

Test file:

```text
tests/unit/document_intelligence/test_chunker.py
```

Test:

- chunks are produced in document order
- every chunk span ID exists in `SpanIndex`
- no chunk is empty

Checkpoint:

```bash
uv run pytest tests/unit/document_intelligence/test_chunker.py
```

---

# Part 9 — Define summary models

File:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/summarization/models.py
```

Define:

```text
DocumentType
ClaimRole
ClaimEvidence
SummaryClaim
ChunkSummary
SummarySentence
DocumentSummary
```

Use document-type-aware roles with a generic fallback:

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

Use structured evidence instead of loose citation fields:

```python
class ClaimEvidence(BaseModel):
    quote: str
    page_number: int
    source_span_ids: tuple[SpanId, ...]
    source_chunk_ids: tuple[ChunkId, ...]
```

Then claims cite one or more evidence objects:

```python
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

Represent final prose as cited sentences:

```python
class SummarySentence(BaseModel):
    text: str
    supporting_claim_ids: tuple[ClaimId, ...]
```

Reason:

The LLM must return structured, auditable claims and every final summary sentence must be traceable to cited claims. Do not allow uncited freeform summary prose.

Test:

- claim serializes
- claim requires evidence quote and source spans/chunks
- claim role is valid for document type
- final summary sentences require supporting claim IDs
- duplicate IDs and inconsistent validation status are rejected

Checkpoint:

```bash
uv run pytest tests/unit/document_intelligence/test_summary_models.py
```

---

# Part 10 — Define the structured generation port and fake generator

File:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/summarization/ports.py
```

Define a structured generation port. This is a boundary contract, not an LLM implementation.

Example concept:

```python
T = TypeVar("T", bound=BaseModel)

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

For tests, make a fake `StructuredResponseGenerator` inside the test file or test helpers.

Reason:

You can test the pipeline without paying for or depending on a real model provider. The domain use case owns the prompt contract; the injected generator owns execution details such as provider/runtime/replay later.

Do not add OpenAI/Anthropic SDKs yet.

---

# Part 11 — Write prompts

File:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/summarization/prompts.py
```

Create two prompt builders:

```text
build_chunk_summary_prompt(chunk)
build_final_summary_prompt(validated_claims)
```

Chunk prompt rules:

```text
Only use the provided chunk.
Every claim must include an exact quote from the chunk.
Every claim must cite source span IDs from the provided evidence.
Do not invent page numbers or span IDs.
If no meaningful claim exists, return empty claims.
```

Final summary prompt rules:

```text
Only use the provided validated claims.
Do not introduce new claims.
Preserve citation lineage.
```

Reason:

The chunk summarizer extracts grounded atoms. The final summarizer organizes them.

---

# Part 12 — Implement chunk summarizer

File:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/summarization/chunk_summarizer.py
```

Implement a class/function that:

```text
Chunk + StructuredResponseGenerator -> ChunkSummary
```

In tests, fake the LLM response.

Test:

- fake LLM returns one claim
- chunk summarizer parses it into `ChunkSummary`
- claim includes source span IDs and quote

Checkpoint:

```bash
uv run pytest tests/unit/document_intelligence/test_chunk_summarizer.py
```

---

# Part 13 — Implement citation validator

File:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/validation/citation_validator.py
```

Checks citation references only:

- all `source_span_ids` exist in the `SpanIndex`
- cited page number matches the actual cited spans
- validator `SpanIndex` document matches the claim document

Return a separate `CitationValidationResult`. Do not update `SummaryClaim.validation_status` here. Citation validity is not aggregate claim validity because a claim can be citation-valid but quote-invalid.

Citation error codes:

```text
invalid_span_id
page_mismatch
document_mismatch
```

Test:

- valid citations return `CitationValidationResult(valid=True, errors=())`
- fake span ID returns `invalid_span_id`
- wrong cited page returns `page_mismatch`
- claim/index document mismatch returns `document_mismatch`
- citation validator does not mark `SummaryClaim` aggregate-valid

Checkpoint:

```bash
uv run pytest tests/unit/document_intelligence/test_citation_validator.py
```

---

# Part 14 — Implement quote validator

File:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/validation/quote_validator.py
```

Checks:

- exact quote appears in cited span text
- if not, quote appears on cited page
- normalized/fuzzy match is marked explicitly

Recommended quote-validation statuses/codes:

```text
quote_not_found
normalized_match_only
fuzzy_match
```

Do not duplicate citation-reference statuses here; `invalid_span_id`, `page_mismatch`, and `document_mismatch` belong to citation validation.

Important rule:

Only exact source-supported claims should be treated as fully valid by default.

Test:

- exact quote passes
- missing quote fails
- quote on wrong page fails
- normalized whitespace case is classified explicitly

Checkpoint:

```bash
uv run pytest tests/unit/document_intelligence/test_quote_validator.py
```

---

# Part 15 — Implement final summarizer

File:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/summarization/final_summarizer.py
```

Input:

```text
validated claims only
```

Output:

```text
DocumentSummary
```

Rules:

- invalid claims are excluded before this step
- final summary does not introduce new claims
- final summary preserves claim IDs/source spans/pages

Test:

- invalid claim is not included
- valid claim appears in final summary
- citation lineage is preserved

Checkpoint:

```bash
uv run pytest tests/unit/document_intelligence/test_final_summarizer.py
```

---

# Part 16 — Implement pipeline

File:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/summarization/pipeline.py
```

Pipeline flow:

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

Suggested function:

```python
def summarize_document(
    pdf_path: Path,
    parser: DocumentParser,
    response_generator: StructuredResponseGenerator,
) -> DocumentSummary:
    ...
```

Integration test:

```text
tests/integration/document_intelligence/test_summary_pipeline.py
```

Use:

- fixture PDF
- PyMuPDF parser
- fake LLM

Checkpoint:

```bash
uv run pytest tests/integration/document_intelligence/test_summary_pipeline.py
```

---

# Part 17 — Only after MVP works: eval assets

Create static eval assets under:

```text
evals/datasets/document_intelligence/
evals/prompts/document_intelligence/
evals/reports/document_intelligence/
```

Start with one small JSONL file of expected quotes/claims.

Do not create executable eval code yet unless the pipeline is stable.

---

# Debugging checklist

If the summary has unsupported claims, inspect in this order:

1. Did the parser extract the source text correctly?
2. Did the span IDs survive chunking?
3. Did the chunk prompt show source span IDs clearly?
4. Did the fake/real LLM invent a span ID?
5. Did citation validation catch it?
6. Did quote validation catch missing quotes?
7. Did final summarization receive only valid claims?

---

# First complete vertical slice

Your first useful end-to-end result is:

```text
tests/fixtures/document_intelligence/sample.pdf
  -> PyMuPDFParser
  -> DocumentIR
  -> chunk_document
  -> ChunkSummarizer with fake LLM
  -> CitationValidator
  -> QuoteValidator
  -> FinalSummarizer with fake LLM
  -> DocumentSummary
```

Once this works with fake LLMs, then wire a real provider externally.

---

# What success looks like

The MVP is done when:

- fixture PDF parses into IR
- spans have deterministic IDs
- chunks preserve source spans
- chunk summarizer returns structured cited claims
- validators reject fake citations and missing quotes
- final summary includes only valid claims
- pipeline test passes with fake LLM
- no component code imports from `apps/`
- no API/database/worker dependency exists
