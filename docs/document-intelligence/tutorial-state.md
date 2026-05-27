# Document Intelligence Tutorial State

Last updated: 2026-05-25

## Current goal

Build a reusable Document Intelligence component for evidence-backed PDF summarization.

Component root:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/
```

This is a component/library, not an app.

## Stable architecture decisions

- Component belongs under `packages/exeboard-ai/src/exeboard_ai/document_intelligence/`.
- Do not put component code under `apps/`.
- Use Pydantic v2 for IR models.
- `DocumentId` is a canonical UUID string.
- Source documents are named `<uuid>.<file_extension>`.
- File extension is source metadata, not part of `DocumentId`.
- Invalid IR should not exist; enforce invariants in models, not downstream helpers.
- Parser interface is a port, named `parsing/ports.py`.
- Parser port shape is `parse(path: Path) -> DocumentIR`.

## Completed

### 1. ID helpers

Files:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/core/__init__.py
packages/exeboard-ai/src/exeboard_ai/document_intelligence/core/ids.py
tests/unit/document_intelligence/test_ids.py
```

Implemented:

- `DocumentId = str`
- `PageId = str`
- `SpanId = str`
- `ChunkId = str`
- `ClaimId = str`
- `validate_document_id(document_id)`
- `make_document_id_from_file_name(file_name)`
- `make_page_id(document_id, page_number)`
- `make_span_id(document_id, page_number, span_index)`
- `make_chunk_id(document_id, chunk_index)`
- `make_claim_id(document_id, claim_index)`

Rules:

- `DocumentId` must be a UUID.
- `<uuid>.<extension>` file names produce the UUID stem.
- page numbers are 1-based.
- span/chunk/claim indexes are 0-based.

### 2. IR models

Files:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/ir/__init__.py
packages/exeboard-ai/src/exeboard_ai/document_intelligence/ir/models.py
tests/unit/document_intelligence/test_ir_models.py
```

Implemented:

- `IR_VERSION = "0.1"`
- `DocumentSource`
- `BoundingBox`
- `ParserRun`
- `TextSpan`
- `Page`
- `DocumentIR`

Key IR representation:

- `DocumentIR.content` stores canonical full document text.
- `TextSpan.char_start` / `char_end` point into `DocumentIR.content`.
- `DocumentIR` validates that `content[char_start:char_end] == span.text`.
- `TextSpan` is the smallest citeable unit.
- `BoundingBox` is optional visual provenance for highlighting/audit.
- `ParserRun` records parser provenance.

IR invariants now enforced:

- duplicate `page_number` rejected
- duplicate `page_id` rejected
- duplicate `span_id` rejected across the document
- duplicate `span_id` rejected within a page
- duplicate `reading_order` rejected within a page
- span page number must match containing page
- span offsets must match canonical content
- bounding box coordinates must not be inverted

Dependency added:

```text
pydantic>=2
```

in:

```text
packages/exeboard-ai/pyproject.toml
```

### 3. Span index

Files:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/ir/span_index.py
tests/unit/document_intelligence/test_span_index.py
```

Implemented `SpanIndex` with:

- `document` property
- `has_span(span_id)`
- `get_span(span_id)`
- `get_spans(span_ids)`
- `get_page_spans(page_number)`
- `get_page_text(page_number)`
- `get_text_for_spans(span_ids)`

Behavior:

- missing `get_span` raises `KeyError`
- page spans are returned in `reading_order`
- span text for multiple spans is returned in document order, not input order
- missing page text returns empty string

Validated by reviewer agent. Review artifact:

```text
span-index-review.md
```

### 4. Parser port/interface

Files:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/parsing/__init__.py
packages/exeboard-ai/src/exeboard_ai/document_intelligence/parsing/ports.py
tests/unit/document_intelligence/test_parser_ports.py
```

Implemented:

```python
class DocumentParser(Protocol):
    def parse(self, path: Path) -> DocumentIR: ...
```

Decision validated by parallel agents:

- use `ports.py`, not `base.py`
- `DocumentParser` is a port/boundary contract
- concrete parsers are adapters

Correct future import:

```python
from exeboard_ai.document_intelligence.parsing.ports import DocumentParser
```

### 5. PyMuPDF parser adapter

Files:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/parsing/adapters/__init__.py
packages/exeboard-ai/src/exeboard_ai/document_intelligence/parsing/adapters/pymupdf.py
tests/integration/document_intelligence/test_pymupdf_parser.py
```

Dependency added:

```text
pymupdf>=1.27.2.3,<1.28
```

The lockfile resolves the exact PyMuPDF build used by this repo.

Implemented:

- `PyMuPDFParser.parse(path: Path) -> DocumentIR`
- modern `import pymupdf`
- UUID document ID derived from `<uuid>.pdf` file name
- `DocumentSource` with file name, extension, MIME type, source URI, SHA-256
- deterministic parser run ID: `pymupdf:text`
- page extraction with unrotated page dimensions and explicit rotation
- line-level `TextSpan`s
- optional bounding boxes in the same unrotated PyMuPDF text-coordinate policy as page dimensions
- canonical `DocumentIR.content` with valid offsets
- warnings for partially textless documents; OCR is not faked
- total no-text extraction raises `NoExtractableTextError` so an OCR adapter can be selected explicitly later
- encrypted PDF rejection via `EncryptedDocumentError` without fake authentication
- clear invalid/empty PDF open failures via `UnreadableDocumentError`
- parser version provenance records PyMuPDF and MuPDF versions when available

Validated against generated test PDFs and local real PDFs.

### 6. Chunking

Files:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/chunking/__init__.py
packages/exeboard-ai/src/exeboard_ai/document_intelligence/chunking/models.py
packages/exeboard-ai/src/exeboard_ai/document_intelligence/chunking/chunker.py
tests/unit/document_intelligence/test_chunker.py
```

Implemented `Chunk` with:

- `chunk_id`
- `document_id`
- `text`
- `page_numbers`
- `source_span_ids`
- `chunk_type = "text"`

Chunk invariants:

- `document_id` must be a UUID
- `chunk_id` must be non-empty and belong to `document_id`
- `text` must not be empty
- `page_numbers` must be non-empty, positive, and unique
- `source_span_ids` must be non-empty, unique, and non-empty strings

Implemented:

```python
def chunk_document(
    document: DocumentIR,
    *,
    target_chars: int = 2000,
    max_chars: int = 2500,
) -> list[Chunk]: ...
```

Chunker behavior:

- validates `target_chars > 0`, `max_chars > 0`, and `target_chars <= max_chars`
- sorts spans by `(page_number, reading_order)`
- skips empty text spans
- groups spans until adding the next span would exceed `target_chars`
- treats `max_chars` as a hard cap except for a single overlong span
- creates deterministic chunk IDs via `make_chunk_id`
- preserves source span IDs
- makes `chunk.text == SpanIndex(document).get_text_for_spans(chunk.source_span_ids)`

### 7. Summary models

Files:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/summarization/models.py
tests/unit/document_intelligence/test_summary_models.py
```

Implemented:

- `DocumentType`
- `ClaimRole`
- `Importance`
- `ValidationStatus`
- `ClaimEvidence`
- `SummaryClaim`
- `ChunkSummary`
- `SummarySentence`
- `DocumentSummary`

Key decisions:

- use structured `ClaimEvidence`, not flat citation fields
- require evidence quote, page number, source span IDs, and source chunk IDs
- preserve claim/chunk/span lineage with tuple provenance collections
- validate document-type-specific claim roles
- reject duplicate IDs, malformed IDs, mixed-document evidence, uncited summary sentences, and inconsistent validation status/errors

### 8. Structured generation port and chunk summarizer

Files:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/summarization/ports.py
packages/exeboard-ai/src/exeboard_ai/document_intelligence/summarization/prompts.py
packages/exeboard-ai/src/exeboard_ai/document_intelligence/summarization/chunk_summarizer.py
tests/unit/document_intelligence/test_summarization_ports.py
tests/unit/document_intelligence/test_summarization_prompts.py
tests/unit/document_intelligence/test_chunk_summarizer.py
```

Implemented:

- `StructuredGenerationRequest`
- `StructuredResponseGenerator.generate(request=..., output_model=...)`
- chunk summary prompt contract
- `summarize_chunk(...) -> ChunkSummary`

Architecture decisions:

- chunk summarizer is an LLM-bound use case, not deterministic core and not an agent harness
- use case initiates the domain-specific generation request
- injected harness/generator executes the LLM call
- use case owns prompt contract, private proposal schema, and domain assembly
- harness/runtime owns provider, tracing, replay, retry, cache, eval capture, and model config
- LLM proposal owns only claim text, claim role, importance, evidence quote, evidence page number, and source span IDs
- code owns deterministic app fields: claim ID, document ID/type, source chunk IDs, validation status/errors

### 9. Citation validator

Files:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/validation/__init__.py
packages/exeboard-ai/src/exeboard_ai/document_intelligence/validation/citation_validator.py
tests/unit/document_intelligence/test_citation_validator.py
```

Implemented:

- `CitationValidationErrorCode`
- `CitationValidationError`
- `CitationValidationResult`
- `validate_claim_citations(claim: SummaryClaim, span_index: SpanIndex) -> CitationValidationResult`

Citation validator responsibility:

- validate citation references only
- report `invalid_span_id`, `page_mismatch`, and `document_mismatch`
- return separate validator-specific result models
- never mutate or mark `SummaryClaim.validation_status`

Decision:

Citation validity is not aggregate claim validity. A claim can be citation-valid but quote-invalid, so citation validation must not set `SummaryClaim.validation_status="valid"`.

## Current test status

Last passing command:

```bash
uv run --package exeboard-ai --with pytest pytest tests/unit/document_intelligence tests/integration/document_intelligence
```

Result:

```text
147 passed
```

## Remaining tutorial work

### Next step: Quote validator

Next file:

```text
packages/exeboard-ai/src/exeboard_ai/document_intelligence/validation/quote_validator.py
```

Quote validator should remain separate from citation validation and check quote support only:

- exact quote appears in cited span text
- quote appears on cited page as a weaker result if not in cited spans
- normalized/fuzzy matches are classified explicitly and not silently treated as fully valid

Later steps:

- Final summarizer
- End-to-end summarization pipeline

## Known cleanup/documentation notes

- `docs/document-intelligence/tutorial.md` and `implementation-plan.md` were updated to use `parsing/ports.py` and `DocumentParser`.
- `pyrightconfig.json` was added so editor/type checker recognizes Python 3.12 and package `src` paths.
- Generated `__pycache__` files should be removed after tests.

## Important interaction preference

Before making code changes, explain:

1. what will be changed
2. why it is needed
3. which files are affected
4. what tests will be run

Then execute only after confirmation or explicit instruction.
