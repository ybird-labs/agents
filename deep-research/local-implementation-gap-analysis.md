# Code Context

## Files Retrieved
1. `docs/document-intelligence/summary-agent-improved-plan.md` (lines 12-63, 77-120) - current 90-day decisions and slice sequencing.
2. `docs/document-intelligence/implementation-plan.md` (lines 26-48, 132-150, 210-637 via targeted grep/read) - original MVP component plan and non-goals.
3. `docs/document-intelligence/docling-adapter-plan.md` (lines 1-220) - reviewed Docling adapter handoff and Slice 0 gate.
4. `docs/document-intelligence/docling-api-notes.md` (lines 1-150) - incomplete Docling Slice 0 discovery checklist.
5. `.a5c/processes/summary-agent-span-addressed-context.process.md` (lines 1-93) - span-addressed prompt/context process and acceptance criteria.
6. `packages/exeboard-ai/src/exeboard_ai/document_intelligence/summarization/chunk_summarizer.py` (lines 33-278) - structured schema, span-addressed context request, replay key, and evidence assembly/drop behavior.
7. `packages/exeboard-ai/src/exeboard_ai/document_intelligence/summarization/pipeline.py` (lines 15-48) - current public pipeline return type and validation flow.
8. `packages/exeboard-ai/src/exeboard_ai/document_intelligence/summarization/models.py` (lines 56-245) - current `ClaimEvidence`, `SummaryClaim`, and `DocumentSummary` invariants.
9. `packages/exeboard-ai/src/exeboard_ai/document_intelligence/validation/quote_validator.py` (lines 20-340) - current normalized/fuzzy/page-scope quote validator.
10. `packages/exeboard-ai/src/exeboard_ai/document_intelligence/parsing/ports.py` (lines 7-36) - parser exception taxonomy includes Docling-ready errors.
11. `packages/exeboard-ai/src/exeboard_ai/document_intelligence/parsing/adapters/pymupdf.py` (lines 1-206) - only implemented parser adapter; text-only PyMuPDF path.
12. `packages/exeboard-ai/src/exeboard_ai/document_intelligence/summarization/ports.py` (lines 1-47) - current provider-agnostic generator protocol without planned error contract.
13. `tests/unit/document_intelligence/*` and `tests/integration/document_intelligence/*` (targeted grep) - coverage confirms span-addressed slice landed; no anchoring/canonical/reporting/provider/cache/judge tests found.
14. `evals/datasets/document_intelligence/summary_mvp_seed.json` and `packages/exeboard-integrations/src/exeboard_integrations/__init__.py` - eval/integration scaffolds exist but are not the planned v1/provider implementation.

## Key Code

- Span-addressed context is implemented: `summarize_chunk` builds `SpanAddressedChunkContext`, passes it in `StructuredGenerationRequest.context`, and includes canonical allowed spans in the replay key (`chunk_summarizer.py` lines 112-139, 162-194).
- Evidence assembly still uses exact substring matching and silently drops the whole claim before aggregate validation if any quote is not an exact substring of an allowed cited span (`chunk_summarizer.py` lines 210-253). This matches the plan's known risk (`summary-agent-improved-plan.md` line 22).
- The pipeline returns only `DocumentSummary`, not the planned `SummarizationRunResult { summary, report }` (`pipeline.py` lines 15-48 vs. plan lines 28-30).
- `ClaimEvidence` lacks planned trusted offsets and anchor tier (`models.py` lines 56-100 vs. plan lines 16-18).
- `quote_validator.py` still exposes normalized/fuzzy/page-scope concepts and uses `SequenceMatcher` (`quote_validator.py` lines 20-29, 183-228, 267-340), while the improved plan says these should be deleted from validity and moved to drop diagnostics (`summary-agent-improved-plan.md` lines 18, 28-30).
- Parser ports already have `ParserDependencyError`, `LayoutExtractionError`, and `SpanAlignmentError` (`parsing/ports.py` lines 11-32). There is no `DoclingParser`; only `PyMuPDFParser` exists and produces text spans/pages but no layout (`pymupdf.py` lines 25-77).
- `StructuredResponseGenerator` has no error taxonomy (`ports.py` lines 1-47), while the plan requires `StructuredGenerationError -> InvalidOutput | Unavailable | RequestRejected` (`summary-agent-improved-plan.md` lines 36-39).
- `packages/exeboard-integrations` exists but contains only an empty package; grep found no `pydantic_ai`, `anthropic`, or `openai` imports under inspected package source.
- Docling Slice 0 is explicitly incomplete: `docling-api-notes.md` says runtime discovery has not been completed and has unchecked TODOs (`docling-api-notes.md` lines 5-7, 17-24, 53-62, 72-143).

## Architecture

The implemented component follows the original MVP architecture: `PDF path -> parser -> DocumentIR -> chunker -> chunk summarizer -> validators -> deterministic final summarizer`. Provider SDK-bearing code is intended to live in `packages/exeboard-integrations`, but no adapter is implemented yet.

The 90-day plan says the grounding pipeline is done enough and the next move should be measurement on real PDFs/models before deepening validators (`summary-agent-improved-plan.md` lines 6, 77-81). The code lacks the adapter/CLI/run-report needed to produce that measurement, while also containing the pre-planned validator shape that Slice 3 intends to replace.

## Plan-improvement opportunities

### 1. Make Slice 1 measurable without waiting for Slice 3

**Current state:** Slice 1 asks for real runs with proposed/citation-fail/quote-fail/valid counts (`summary-agent-improved-plan.md` lines 77-81). Current `summarize_document` returns only `DocumentSummary`; assembly drops are silent (`pipeline.py` lines 28-48; `chunk_summarizer.py` lines 141-153, 225-253).

**Missing next slice:** Add a thin Slice 1a diagnostic runner or temporary instrumentation for `generated_claims`, `assembly_drops`, `validation_errors`, and `valid_claims` without committing to full Slice 3 `GroundingRunReport` yet.

**Risk:** Without this, Slice 1 metrics will be incomplete or guessed.

### 2. Split provider adapter prerequisites from production hardening

**Current state:** The domain port has no error contract (`summarization/ports.py` lines 1-47). `exeboard-integrations` is a skeleton. D4/Slice 1 require PydanticAI adapter work, while Slice 4 owns hardening (`summary-agent-improved-plan.md` lines 36-39, 77-81, 93-95).

**Missing next slice:** Define Slice 1 minimum as: domain error taxonomy, `PydanticAIStructuredResponseGenerator` in `exeboard-integrations`, one fake/TestModel contract test, architecture guard against provider imports in `exeboard_ai`, and a dev CLI with explicit `--model`. Defer retries/cache/live smoke matrix to Slice 4.

**Risk:** Too much hardening delays first real run; too little structure risks SDK leakage.

### 3. Treat span-addressed context as done and update sequencing language

**Current state:** The process file's span-addressed scope (`.a5c/...process.md` lines 9-22, 39-93) appears implemented in code/tests (`chunk_summarizer.py` lines 112-139, 162-194; targeted test grep hits).

**Missing next slice:** Update plans to call this the baseline and say Slice 1 runs the current span-addressed pipeline, not a pre-span-addressed “unchanged” pipeline.

**Risk:** Future agents may rework completed context plumbing or compare real-run results against the wrong baseline.

### 4. Make Slice 3 anchor migration depend on measured artifacts

**Current state:** Current tests keep normalized/fuzzy matches invalid; improved plan flips canonical-tier positives into valid anchored claims and removes fuzzy from validity (`summary-agent-improved-plan.md` lines 24-30, 55-63, 89-90).

**Missing next slice:** Add a Slice 3 entry criterion requiring at least one real-run artifact or curated fixture showing hyphenation/ligature/curly-quote/whitespace quote mismatch. Then implement canonical offset map -> `anchor_quote` -> `ClaimEvidence` offsets/tier -> report -> validator slim-down -> test migration.

**Risk:** Synthetic-only canonicalization may miss structural parser failures noted in plan risk B (`summary-agent-improved-plan.md` lines 124-125).

### 5. Resolve empty-summary/refusal behavior before real runs

**Current state:** `DocumentSummary` requires non-empty sentences and claims (`models.py` lines 223-245). If all claims are invalid/dropped, `build_final_summary` cannot represent a refusal summary.

**Missing next slice:** Decide before or during Slice 1 whether `SummarizationRunResult.summary` can be `None` for zero valid claims, or add an explicit refusal/status model outside `DocumentSummary`.

**Risk:** Low-validity real runs may raise instead of producing useful drop data.

### 6. Keep Docling parked but add parser-escalation criteria

**Current state:** The Docling adapter plan is detailed, but current 90-day plan says not to do Docling unless real packs fail PyMuPDF (`summary-agent-improved-plan.md` lines 118-120). API notes remain incomplete with stop conditions unresolved (`docling-api-notes.md` lines 5-7, 145-150).

**Missing next slice:** Add parser metrics to Slice 1 reports: PyMuPDF warnings, empty-page counts, reading-order/table-loss observations. Reopen Docling Slice 0 only if these exceed a named threshold or block summary quality.

**Risk:** Premature Docling work widens scope; delayed parser escalation may overfit quote anchoring to parser artifacts.

### 7. Bridge `summary_mvp_seed.json` to eval v1

**Current state:** Plan says retire `summary_mvp_seed.json` and create v1 with 130-145 cases over real PDFs (`summary-agent-improved-plan.md` lines 55-63, 97-99). Current eval tree has only seed data plus placeholders.

**Missing next slice:** During first real runs, save PDF source metadata and hashes in a fixture manifest; decide which documents graduate into v1. Retire seed data through explicit migration in Slice 5.

**Risk:** Eval v1 becomes an unbounded Slice 5 task.

## Start Here

Open `packages/exeboard-ai/src/exeboard_ai/document_intelligence/summarization/chunk_summarizer.py` first. It is where the implemented span-addressed context, replay key, and silent pre-validation quote drop behavior meet the current plan's Slice 1/Slice 3 gaps.

## Recommended sequencing

1. Mark span-addressed context complete and define the baseline as the current span-addressed pipeline.
2. Add minimal Slice 1 diagnostics for proposed/drop/validation counts.
3. Implement minimal PydanticAI adapter/CLI plus domain error taxonomy and architecture guard.
4. Run public PDFs/models and capture parser/eval metadata.
5. Decide from measured failures whether anchoring/canonicalization, parser escalation, or empty-summary handling blocks next.
6. Implement Slice 3 anchoring/report migration.
7. Add Slice 4 replay/judge hardening.
8. Build Slice 5 eval dataset v1 and CI gates.

## Supervisor coordination

No supervisor decision was needed. The task was read-only scouting plus writing this report.

## Acceptance Report

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "Read-only gap analysis was limited to the requested document-intelligence code, tests, and planning docs; no implementation changes were made."
    },
    {
      "id": "criterion-2",
      "status": "satisfied",
      "evidence": "Findings cite exact file paths and line ranges for current code state and plans, and include current state, missing next slices, risks, and recommended sequencing."
    }
  ],
  "changedFiles": [
    "deep-research/local-implementation-gap-analysis.md"
  ],
  "testsAddedOrUpdated": [],
  "commandsRun": [
    {
      "command": "find/read/grep targeted repository inspection via provided tools",
      "result": "passed",
      "summary": "Mapped document_intelligence source, unit/integration tests, requested planning docs, eval and integrations scaffolds."
    },
    {
      "command": "nl -ba ... | sed ... for selected source/docs",
      "result": "passed",
      "summary": "Captured line-numbered evidence for key code and plan references."
    },
    {
      "command": "git status --short && grep -R \"pydantic_ai\\|anthropic\\|openai\" -n packages/exeboard-ai/src packages/exeboard-integrations/src || true && find packages/exeboard-ai/src/exeboard_ai/document_intelligence -maxdepth 3 -type f | sort",
      "result": "passed",
      "summary": "Confirmed many pre-existing staged/untracked repository files, no provider SDK imports in inspected source, and current document_intelligence file list."
    }
  ],
  "validationOutput": [
    "No tests run; task was read-only analysis/report writing.",
    "git status --short showed many pre-existing staged/untracked files before this report was written."
  ],
  "residualRisks": [
    "Repository already has many staged files, so no-staged-files is false and cannot be remediated without modifying user/parent git state.",
    "Line ranges for implementation-plan.md beyond the first 220 lines were inspected primarily via targeted grep/read rather than full-file citation."
  ],
  "noStagedFiles": false,
  "notes": "Only the requested output report was written. Existing staged/untracked files appear unrelated to this scouting task."
}
```
