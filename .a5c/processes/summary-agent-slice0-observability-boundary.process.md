# Babysitter plan: summary-agent Slice 0 observability + LLM-boundary guardrails

Process id: `project/summary-agent-slice0-observability-boundary`

Purpose: execute the first slice from the updated evidence-backed summary-agent plan: make live-model measurement honest by adding grounding/drop telemetry and core LLM-boundary guardrails before implementing live providers, replay, judges, UI, Docling, or OCR.

## Scope

In scope:

- Add a typed `SummarizationRunResult` and minimal `GroundingRunReport`.
- Track proposed/generated claims, evidence counts where practical, assembly drops, citation-validation drops, quote-validation drops, valid claims, parser counters, and error-code counts.
- Enforce conservation: `claims_proposed == claims_valid + len(drops)`.
- Represent zero-valid-claim outcomes explicitly, preferably as `summary: None` in `SummarizationRunResult`, rather than fabricating a non-empty `DocumentSummary`.
- Add domain-owned `StructuredGenerationError` taxonomy: `InvalidOutput`, `Unavailable`, `RequestRejected`.
- Add static import-boundary tests: `exeboard_ai` must not import provider SDKs, `pydantic_ai`, or `exeboard_integrations`.
- Run focused quality gates and specialist reviews.

Out of scope:

- Canonical quote anchoring / `ClaimEvidence` offsets.
- Live PydanticAI/provider adapter.
- Replay cache.
- Eval-stage judge.
- App/API/UI/demo surface.
- Docling adapter or Docling Slice 0 runtime discovery.
- OCR or remote inference.
- DB, Temporal, workers, auth, deployment.
- Broad validator rewrites or fuzzy/page-scope validity changes.

## Proposed run flow

1. **Preflight inventory**
   - Inspect the updated plan, deep-research reports, summarization/pipeline/port code, validation code, and tests.
   - Produce a focused TDD implementation plan, expected files/tests, risks, and acceptance criteria.

2. **Human breakpoint: approve implementation**
   - Ask the owner to approve implementing only Slice 0 with the preflight plan and boundaries.

3. **TDD implementation**
   - Add/adjust tests first for result/report models, drop accounting, conservation, zero-valid behavior, port exception taxonomy, and import boundaries.
   - Implement minimal code to pass.
   - Preserve current exact-validity semantics; no canonical/fuzzy/page-scope validity expansion.

4. **Quality gates**
   - `uv run python scripts/check_workspace.py`
   - `uv run --package exeboard-ai --with pytest pytest tests/unit/document_intelligence tests/integration/document_intelligence`
   - `uv run --with pyright --with pytest pyright`

5. **Parallel specialist review**
   - `exeboard.document-summary-model-expert`
   - `exeboard.agentic-llm-boundary-expert`
   - `exeboard.agentic-python-di-validation-expert`

6. **Refinement loop**
   - If any reviewer returns non-`APPROVE`, blockers, or required changes, run a focused worker task to fix only those blockers.
   - Re-run gates and reviews.
   - Cap at two refinement passes.

7. **Final report**
   - Summarize changed files, tests run, review verdicts, acceptance criteria, and remaining risks.

## Acceptance criteria

- `summarize_document` or its new result-returning path exposes `SummarizationRunResult { summary, report }`.
- Generated/proposed claims and dropped claims are visible in a typed report; bad generated claims do not disappear silently from measurement.
- Conservation invariant is tested.
- Zero-valid-claim behavior is explicit and does not fabricate a final summary.
- Port exception taxonomy is domain-owned and provider-agnostic.
- `exeboard_ai` has no provider SDK, `pydantic_ai`, or `exeboard_integrations` imports.
- No live provider, replay, judge, app/API/UI, Docling, OCR, DB, or Temporal work is added.
- Workspace, focused pytest, and pyright gates pass.
- Specialist reviewers approve with no blockers or required changes.
