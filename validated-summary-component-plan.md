# Validated Summary Component Plan Review

## Verdict

**Go, with minor revisions before implementation.** The proposed component placement and package boundaries match the repo architecture. The main gaps are dependency declaration timing, a missing shared LLM protocol location, future eval package dependency wiring, and a few traceability/validation details that should be made explicit before coding.

## Evidence checked

- Root workspace includes `packages/exeboard-ai` and `packages/exeboard-evals`: `pyproject.toml:12-28`.
- `docs/file-structure.md` defines `apps/` as deployable processes and `packages/` as reusable packages: `docs/file-structure.md:7-15`.
- `packages/exeboard-ai` is for agent orchestration, LLM-facing abstractions, prompt loading, and AI runtime composition: `docs/file-structure.md:43-52`.
- Static eval assets belong under top-level `evals/`, while executable eval code belongs in `packages/exeboard-evals`: `docs/file-structure.md:72-81`.
- Packages must not import from `apps/`: `docs/file-structure.md:83-92`.
- `packages/exeboard-ai/pyproject.toml` currently has no dependencies: `packages/exeboard-ai/pyproject.toml:1-13`.
- `packages/exeboard-evals/pyproject.toml` currently has no dependencies: `packages/exeboard-evals/pyproject.toml:1-13`.

## Repo-placement corrections

- **Component root is correct:** `packages/exeboard-ai/src/exeboard_ai/document_intelligence/` is the right location for reusable AI/runtime logic. It is not a deployable process, so it should not live under `apps/`.
- **Static eval assets are correctly placed:** `evals/datasets/document_intelligence/`, `evals/prompts/document_intelligence/`, and `evals/reports/document_intelligence/` align with the documented top-level eval asset layout.
- **Executable eval code is correctly deferred to `packages/exeboard-evals`:** once added, it should import `exeboard_ai` through a declared workspace dependency, not by path hacks.
- **Tests are mostly fine:** `tests/integration/document_intelligence/` and `tests/fixtures/document_intelligence/` match the existing test layout. `tests/unit/` does not currently exist, but adding it is reasonable; consider adding a small `tests/unit/README.md` or updating docs if the repo wants the test taxonomy documented.

## Missing files/dependencies

1. **Add an explicit LLM protocol module.**
   - The plan says to use an `LLMClient Protocol`, but the layout has no obvious shared home for it.
   - Suggested file: `packages/exeboard-ai/src/exeboard_ai/document_intelligence/summarization/llm.py` or `.../core/protocols.py`.
   - This avoids duplicating protocol definitions across `chunk_summarizer.py` and `final_summarizer.py`.

2. **Declare PyMuPDF when implementing `pymupdf_parser.py`.**
   - `packages/exeboard-ai` currently has `dependencies = []`.
   - Step 3 should include adding the package dependency, likely `pymupdf`, to `packages/exeboard-ai/pyproject.toml` when the adapter is introduced.

3. **If Pydantic models are used, declare Pydantic.**
   - The plan says dataclasses/Pydantic. If implementation chooses Pydantic, add it to `packages/exeboard-ai/pyproject.toml`; otherwise keep the MVP on stdlib dataclasses to preserve the no-dependency baseline.

4. **When executable evals are added, wire dependencies.**
   - `packages/exeboard-evals` currently has `dependencies = []`.
   - If `packages/exeboard-evals/src/exeboard_evals/document_intelligence/` imports `exeboard_ai`, add a workspace dependency on `exeboard-ai` there.

## Import-boundary concerns

- The plan correctly bans FastAPI, DB sessions, apps imports, Temporal, Redis, web requests, and UI assumptions from the MVP component.
- Keep provider SDK adapters out of `exeboard_ai` for the MVP. If a real LLM adapter is later placed in `exeboard-integrations`, avoid making `exeboard_ai` import it. Apps or worker composition should wire the integration adapter into the `LLMClient` protocol to avoid package cycles.
- Do not let top-level `evals/` become an importable Python module. Static assets only; executable code belongs in `packages/exeboard-evals`.

## Plan flaws / risks to fix before coding

- **Traceability needs one more model detail:** add stable IDs for claims/chunk summaries, or at least a clear lineage field from final summary items back to validated `SummaryClaim`s. `source_span_ids` are useful, but claim-level IDs make validation and eval reporting much easier.
- **Citation/quote semantics should define text normalization.** Exact quote matching against PDF extraction can fail because of whitespace, ligatures, hyphenation, and line breaks. The MVP can still require exact matches for `valid`, but docs and validators should define normalized comparison and classify fuzzy matches as non-valid or warning-only.
- **Bounding box semantics need documentation if included.** Specify page coordinate system, units, origin, and optionality in `ir_v0_1.md`.
- **Stable span ID semantics should be explicit.** Decide whether IDs are stable only within a parser run or stable across repeated parses of the same PDF. Unit tests for stable IDs should reflect that decision.
- **Final summary should preserve citations.** The final summarizer should not merely receive validated claims; its output model should retain source claim IDs/source spans/pages so downstream UI/evals can audit every summary point.

## Revised task list

0. Write docs first: MVP scope, IR v0.1, citation semantics including normalization, summary pipeline, and evaluation.
1. Add `core/ids.py`, `ir/models.py`; define DocumentIR/Page/Span/BoundingBox/ParserRun and explicit span ID stability rules. Test serialization and deterministic IDs.
2. Add `ir/span_index.py`; test valid/invalid span lookup, page text lookup, and multi-span text extraction.
3. Add `parsing/base.py`; then add `parsing/pymupdf_parser.py` plus `pymupdf` dependency in `packages/exeboard-ai/pyproject.toml`. Integration-test against a local fixture PDF.
4. Add `chunking/models.py` and `chunking/chunker.py`; test chunk coverage, ordering, page numbers, and that every chunk span ID exists.
5. Add `summarization/models.py` with claim IDs, validation status/errors, source span IDs, evidence quote, page number, claim type, and final-summary lineage.
6. Add shared `LLMClient` protocol module and fake test client.
7. Add `summarization/prompts.py` and `chunk_summarizer.py`; test deterministic structured output parsing with the fake client.
8. Add `validation/citation_validator.py` and `quote_validator.py`; test fake span IDs, wrong pages, missing quotes, exact quote matches, and normalized-but-not-valid/fuzzy cases.
9. Add `summarization/final_summarizer.py`; test that invalid claims are excluded and final outputs retain citation lineage.
10. Add `summarization/pipeline.py`; integration-test parse -> index -> chunk -> summarize -> validate -> final summary with fake LLM.
11. Add static eval assets under top-level `evals/` after pipeline shape is stable.
12. Add executable eval runner under `packages/exeboard-evals` only after the MVP pipeline exists, and declare its dependency on `exeboard-ai`.

## Final go/no-go

**Go** after incorporating the small revisions above. No repo-boundary violation or major architecture/location mistake was found.