# Code Context

## Files Retrieved
1. `packages/exeboard-ai/pyproject.toml` (lines 1-15) - package-local dependency convention; currently only `pydantic>=2`.
2. `pyproject.toml` (lines 1-28) - root is a `uv` workspace manifest with no root runtime dependencies.
3. `pyrightconfig.json` (lines 1-24) - Python 3.12, standard type checking, includes `apps`, `packages`, and `tests`, with `packages/exeboard-ai/src` in `extraPaths`.
4. `docs/file-structure.md` (lines 23-26, 43-52, 83-92) - dependency declarations stay local to the workspace member; package/app import boundaries.
5. `packages/exeboard-ai/src/exeboard_ai/document_intelligence/parsing/ports.py` (lines 1-8) - current parser port shape.
6. `packages/exeboard-ai/src/exeboard_ai/document_intelligence/core/ids.py` (lines 1-60) - UUID file-name convention and deterministic page/span IDs.
7. `packages/exeboard-ai/src/exeboard_ai/document_intelligence/ir/models.py` (lines 12-173) - current IR models and invariants the adapter must satisfy.
8. `packages/exeboard-ai/src/exeboard_ai/document_intelligence/ir/span_index.py` (lines 1-48) - downstream assumes spans are ordered by `reading_order` and reconstructable as text.
9. `tests/unit/document_intelligence/test_parser_ports.py` (lines 1-27) - naming and structural protocol test convention.
10. `tests/unit/document_intelligence/test_ir_models.py` (lines 15-73) - existing fixture constants and expected `ParserRun`, bbox, and content-offset patterns.
11. `tests/unit/document_intelligence/test_ids.py` (lines 1-82) - tests enforce UUID file-name document IDs and deterministic ID formatting.
12. `tests/unit/document_intelligence/test_span_index.py` (lines 1-104) - tests enforce document-order text reconstruction by page and reading order.
13. `docs/document-intelligence/implementation-plan.md` (lines 98-104, 284-316) - planned test/fixture locations and explicit PyMuPDF dependency note.
14. `docs/document-intelligence/tutorial-state.md` (lines 164-228) - current validated state and next parser-adapter requirements.
15. `docs/document-intelligence/tutorial.md` (lines 479-543) - tutorial PyMuPDF step; contains a fixture naming conflict noted below.
16. `tests/integration/README.md` (lines 1-3) and `tests/fixtures/README.md` (lines 1-3) - placeholder top-level integration/fixture directories.
17. `.gitignore` (lines 1-10, 35-37) - ignores Python caches and top-level `/tmp/`, but not generated PDFs under `tests/fixtures`.

## Key Code

Current parser port is already fixed and minimal:

```python
# packages/exeboard-ai/src/exeboard_ai/document_intelligence/parsing/ports.py:1-8
from pathlib import Path
from typing import Protocol

from exeboard_ai.document_intelligence.ir.models import DocumentIR


class DocumentParser(Protocol):
    def parse(self, path: Path) -> DocumentIR: ...
```

IDs and file names are not arbitrary. The adapter should derive the document ID from `path.name`, and the file must be named `<uuid>.<extension>`:

```python
# packages/exeboard-ai/src/exeboard_ai/document_intelligence/core/ids.py:17-21
def make_document_id_from_file_name(file_name: str) -> DocumentId:
    stem, separator, extension = file_name.rpartition(".")
    if not separator or not stem or not extension:
        raise ValueError("file_name must use the '<uuid>.<extension>' format")
    return validate_document_id(stem)
```

The adapter must produce spans whose text exactly matches `DocumentIR.content` at `char_start:char_end`:

```python
# packages/exeboard-ai/src/exeboard_ai/document_intelligence/ir/models.py:125-173
class DocumentIR(BaseModel):
    ...
    content: str
    pages: list[Page] = Field(default_factory=list)
    ...
    def _validate_document_structure(self) -> "DocumentIR":
        ...
        for page in self.pages:
            ...
            for span in page.spans:
                ...
                if span.char_end > content_length:
                    raise ValueError("span char_end exceeds document content length")
                if self.content[span.char_start : span.char_end] != span.text:
                    raise ValueError("span text must match document content at char range")
```

`TextSpan` fields needed from PyMuPDF extraction:

```python
# packages/exeboard-ai/src/exeboard_ai/document_intelligence/ir/models.py:77-87
class TextSpan(BaseModel):
    span_id: SpanId
    page_number: int = Field(ge=1)
    text: str
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    reading_order: int = Field(ge=0)
    bbox: BoundingBox | None = None
    parser_run_id: str | None = None
```

Repo-local dependency convention:

```toml
# packages/exeboard-ai/pyproject.toml:1-8
[project]
name = "exeboard-ai"
...
dependencies = [
  "pydantic>=2",
]
```

```md
# docs/file-structure.md:23-26
The workspace members are the Python deployable apps and reusable packages listed in the root pyproject.toml. Keep dependency declarations local to the workspace member that needs them.
```

## Architecture

- `packages/exeboard-ai/src/exeboard_ai/document_intelligence/` is the right component root. Docs explicitly classify `packages/exeboard-ai` as reusable AI/runtime composition code, while apps remain deployable composition only (`docs/file-structure.md:43-52`, `83-92`).
- `DocumentParser` is a port in `parsing/ports.py`; concrete parsers are adapters. `tutorial-state.md:164-172` says use `ports.py`, not `base.py`, and import `DocumentParser` from `exeboard_ai.document_intelligence.parsing.ports`.
- The PyMuPDF adapter should live at `packages/exeboard-ai/src/exeboard_ai/document_intelligence/parsing/pymupdf_parser.py` per `implementation-plan.md:284-290` and `tutorial-state.md:197-202`.
- Data flow expected by docs: `PDF path -> PyMuPDF parser -> DocumentIR`; parser derives `DocumentId`, fills `DocumentSource`, `ParserRun`, pages, spans, canonical content, IDs, offsets, and optional bounding boxes (`tutorial-state.md:217-228`).
- Downstream code depends only on `DocumentIR`, not PyMuPDF objects. Do not expose PyMuPDF types in public IR fields.

Repo-specific recommendations:

1. **Add `pymupdf` as a runtime dependency of `packages/exeboard-ai`, not root.** This is appropriate because the adapter is runtime code inside `exeboard-ai`, and docs explicitly say to add `pymupdf` to `packages/exeboard-ai/pyproject.toml` when implementing this step (`implementation-plan.md:307-309`, `tutorial.md:487-497`). The root `pyproject.toml` is package=false workspace metadata with empty dependencies (`pyproject.toml:1-12`). There is no existing optional-dependencies convention, so an optional extra would be a new pattern and would conflict with the current simple package-local dependency approach.
2. **Use existing loose dependency style.** Current dependency style is lower-bound-only (`pydantic>=2` in `packages/exeboard-ai/pyproject.toml:6-8`). If pinning is not otherwise required, use a similar declaration such as `"pymupdf>=1.24"` or `"pymupdf"` rather than adding app/root dependencies.
3. **Put parser integration tests under `tests/integration/document_intelligence/test_pymupdf_parser.py`.** This location is planned in both docs (`implementation-plan.md:98-104`, `tutorial-state.md:197-202`) and matches top-level test taxonomy (`tests/integration/README.md:1-3`). The directory does not exist yet; creating it is consistent with the plan.
4. **Put persistent fixture PDFs under `tests/fixtures/document_intelligence/`, but name them with a UUID stem.** `tutorial-state.md:202` says `<uuid>.pdf`, which matches `make_document_id_from_file_name`. Avoid `sample.pdf` because it will fail if the adapter follows the required document-ID derivation.
5. **Prefer generated test PDFs in pytest `tmp_path` if the goal is to avoid binary fixtures.** This fits the intent of “generated temp PDFs” better than writing under `tests/fixtures`, because `.gitignore` does not ignore generated PDFs under `tests/fixtures` (`.gitignore:1-10`, `35-37`). Name the temporary file `f"{DOCUMENT_ID}.pdf"` so it still satisfies ID semantics. There is no existing `tmp_path` pattern in tests, but nothing conflicts with it.
6. **If a fixture is committed, keep it small and digital-born.** Docs say “fixture PDF parses” and “Do not worry about perfect tables or OCR” (`implementation-plan.md:311-316`, `tutorial.md:515-523`). Do not introduce scanned/OCR expectations in this adapter test.
7. **Naming conventions:** module `pymupdf_parser.py`, test `test_pymupdf_parser.py`, likely class `PyMuPDFParser`. Tests use `DOCUMENT_ID` constants, helper functions prefixed `_make_...`, and plain `test_...` functions with direct assertions.
8. **Parser run metadata should be asserted.** Acceptance criteria include parser run metadata (`implementation-plan.md:311-316`), and existing tests already use a `PARSER_RUN_ID = "pymupdf:1"` convention (`tests/unit/document_intelligence/test_ir_models.py:15-17`). Exact ID/version can be chosen, but every span’s `parser_run_id` should align with a `ParserRun.parser_run_id`.
9. **Build `content` and offsets while appending spans.** Because IR validation is strict, calculate `char_start` before appending each span’s text to the canonical content and `char_end` after. If inserting separators between spans/pages, account for them in offsets and ensure no span includes separator text unless PyMuPDF provided it.
10. **Keep type checker in mind.** `pyrightconfig.json` includes tests and packages in standard mode (`pyrightconfig.json:1-24`), so unresolved imports or newly added modules will be checked once present. Declare the dependency before importing it in package code.

Conflicts / risks with the proposed plan:

- **Fixture naming conflict:** `docs/document-intelligence/tutorial.md:517-523` says `tests/fixtures/document_intelligence/sample.pdf`, but the validated state says `tests/fixtures/document_intelligence/<uuid>.pdf` (`tutorial-state.md:197-203`) and code requires `<uuid>.<extension>` (`ids.py:17-21`). Use UUID-named PDFs; `sample.pdf` is incompatible unless the adapter stops deriving `DocumentId` from file name, which would violate current docs/tests.
- **Generated temp PDF vs fixture directory:** The docs mention fixture PDFs under `tests/fixtures/document_intelligence/`, but generated temp PDFs should not be created there during tests unless cleaned up. `tmp_path` is safer and avoids unignored generated files.
- **No optional dependency convention:** If the proposed plan tries to make PyMuPDF optional, that adds a new packaging convention not used elsewhere. The repo docs and current plan both favor adding it as a normal package-local runtime dependency.
- **Integration test command in docs is slightly less workspace-specific:** `tutorial-state.md:179-185` uses `uv run --package exeboard-ai --with pytest pytest ...` for current tests, while `tutorial.md:541-543` uses `uv run pytest ...`. Prefer the former style for consistency in this workspace.

## Start Here

Open `packages/exeboard-ai/src/exeboard_ai/document_intelligence/core/ids.py` first to internalize the `<uuid>.pdf` input-file constraint, then implement `packages/exeboard-ai/src/exeboard_ai/document_intelligence/parsing/pymupdf_parser.py` against `ir/models.py` invariants.

## Supervisor coordination

No supervisor decision needed. Main actionable conflict is local: use UUID-named generated or fixture PDFs, not `sample.pdf`.
