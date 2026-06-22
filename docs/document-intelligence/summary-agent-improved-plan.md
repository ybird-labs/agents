# Improved plan: evidence-backed summary agent (next 90 days)

Date: 2026-06-09
Method: three parallel expert agents — (A) LLM-boundary expert, (B) grounding/validation expert, (C) sequencing critic — each given the codebase, the prior four-lens research synthesis (`research/product-engineering-deep-research-review.md`), and fresh web research. This document is the merged plan. Disagreements between experts are flagged explicitly rather than silently resolved.

Posture adopted from the sequencing critic, updated after the 2026-06-21 deep-research review: **the span-addressed grounding baseline is done enough, but live-model measurement is not honest until proposal/drop telemetry and LLM-boundary guardrails exist.** Do not deepen validators beyond the targeted telemetry/boundary prerequisites before a real model reads real public board packs; do not compare providers from silently dropped claims.

2026-06-21 plan update sources: `deep-research/external-best-practices.md`, `deep-research/local-implementation-gap-analysis.md`, `deep-research/summary-model-plan-review.md`, `deep-research/llm-boundary-plan-review.md`, and `deep-research/validation-grounding-plan-review.md`.

---

## Decisions adopted

### D1. Quote mechanism: quote-as-locator with trusted-code anchoring (expert B)

The model keeps echoing a quote, but the echo is only a **locator**: trusted code anchors it to a character range inside the cited spans (tier 1 exact, tier 2 canonical) and the stored `ClaimEvidence.quote` is always re-sliced verbatim from `DocumentIR.content` at the resolved range. Model-emitted character offsets are **rejected permanently** (LLMs can't count characters; Anthropic Citations proves the division of labor — model indicates *what*, trusted code computes *where*). This supersedes the prior synthesis's "model cites span ID + offsets" preference.

- New `validation/anchoring.py`: `anchor_quote(quote, cited_spans, content) -> QuoteAnchor | AnchorFailure`; successful `QuoteAnchor` carries `span_id, char_start, char_end, tier`. Never searches outside cited spans.
- Ambiguity fails closed for the MVP: duplicate matches in distinct source ranges return `AnchorFailure(code="ambiguous_anchor")`, counted in telemetry, and never enter the final summary.
- MVP evidence anchors inside exactly one cited `TextSpan`. Multi-span contextual citations may be listed, but the quote range must be contained by one cited span; future cross-span evidence requires segmented anchors.
- `ClaimEvidence` gains `char_start, char_end, anchor_tier`; invariant: `quote == content[char_start:char_end]` and range ⊆ a cited span's range.
- `quote_validator.py` becomes offset-integrity re-verification (defense in depth). Taxonomy: keep `quote_not_found` (tamper check), `invalid_span_id`, `document_mismatch`; rename `quote_outside_cited_spans` → `range_outside_cited_spans`; **delete** `normalized_match_only`, `fuzzy_match`, `QuoteMatchType`, `QuoteMatchScope`, page-scope search. Fuzzy (SequenceMatcher) is removed from validity entirely and demoted to drop-diagnosis telemetry.
- Generated schema unchanged; prompt rule line softens to "copy the quote as exactly as you can from one cited span" → `CHUNK_SUMMARY_PROMPT_VERSION = "0.3"`.
- No compat shims: migrate affected tests in the same slice (quote_validator, aggregate_validator, chunk_summarizer, summary_models, pipeline tests, seed dataset).

Key codebase finding driving this: `_assemble_evidence` in `chunk_summarizer.py` silently returns `None` on a failed exact-substring check **before the quote validator runs** — the normalized/fuzzy paths are effectively dead code in the pipeline path, and the drop rate is currently invisible and unclassified.

### D2. Canonicalization: matcher-side only, versioned, offset-mapped (expert B)

`DocumentIR.content` is never modified. New `text/canonical.py` with `CANONICALIZATION_VERSION = "1"` and a lossless offset map (`CanonicalText.to_source_offsets`): every canonical hit converts to a raw content range — canonical matching is **not** fuzzy matching. Pipeline order: (1) NFKC, (2) soft-hyphen removal, (3) line-break dehyphenation only at newlines (`(?<=\w)-[ \t]*\n[ \t]*(?=\w)` — the current `normalize_quote_text` regex wrongly joins intra-line "well- known"), (4) explicit versioned fold table for curly quotes/dashes/NBSP (NFKC does not fold these), (5) whitespace collapse. Version joins the replay key and eval report header. Tests: round-trip property, per-transform offset-map correctness, idempotence, pinned golden file.

### D3. Recall telemetry: typed run report, no logging side effects (expert B)

`summarize_document` returns `SummarizationRunResult { summary, report: GroundingRunReport }`. Report carries `claims_proposed, evidence_proposed, claims_assembled_or_anchored, anchored_exact, anchored_canonical, claims_valid, drops: tuple[DroppedClaimRecord, ...], counts_by_error_code, ambiguous_anchor_count` plus derived `exact_anchor_rate / canonical_recovery_rate / drop_rate`. Every drop becomes a `DroppedClaimRecord` with `stage` (`assembly_anchor | citation_validation | quote_validation`) and a diagnostic `near_miss_tier` (the deleted SequenceMatcher gets one legitimate home here: classifying *why* a drop happened, zero effect on validity). Conservation invariant tested: `claims_proposed == claims_valid + len(drops)`. Multi-evidence generated claims drop once, with nested evidence failure detail. Eval harness serializes reports to `evals/reports/`.

A minimal pre-anchoring version of this report lands before the first live-model comparison: it records proposed/generated claim count, assembly drops, validation drops, valid claims, parser counters, and conservation, without yet accepting canonical matches.

### D4. Provider adapter: one PydanticAI-backed adapter; provider/model choice is configuration, decided by evals (resolved — see Disagreement 1)

No provider is privileged in the architecture — the default model is selected from measured grounding performance and cost in slice-1/slice-5 eval runs, not from vendor preference. Honest framing of the choice: provider portability alone does not mandate PydanticAI — a single hand-rolled adapter against an OpenAI-compatible gateway (OpenRouter, self-hosted LiteLLM) also reaches many providers' models through one API. The margins that decided it for PydanticAI: it handles the heterogeneity of structured-output support across models/channels (strict JSON schema vs tool-based vs prompted fallbacks) per provider, and maintains the validation-retry harness — both things a gateway adapter would re-implement by hand. The cost is one framework layer, confined to the adapter. The decision is small and reversible behind the port. Channel note (verified 2026-06-10 against OpenRouter docs): OpenRouter does not retain prompts itself (prompt logging is opt-in) and offers enforceable Zero Data Retention routing — account-level toggles per model group, per-key guardrails, and per-request `"zdr": true` that restricts routing to ZDR-compliant endpoints. So it is not technically disqualified for production confidential traffic; the remaining considerations are contractual (data still transits a third party in flight; some enterprise buyers require traffic confined to their own contracted tenant regardless of retention) and unverified compliance posture (BAA/DPA/certifications not confirmed in their public docs). Treat production-channel choice as a per-customer procurement question; OpenRouter is well suited to slice-1/eval model comparisons either way.

- `PydanticAIStructuredResponseGenerator(model, timeout_seconds, output_retries=2)`: `model` is a required explicit configuration string for any PydanticAI-supported provider; no reusable adapter constructor may silently pick a model from ambient environment. It uses PydanticAI's validated structured output and retry-on-validation; maps PydanticAI/provider exceptions to the port taxonomy.
- Port (`ports.py`) gains the error contract only: `StructuredGenerationError` → `InvalidOutput | Unavailable | RequestRejected`. Port stays sync, non-streaming; generation params (model, max_tokens, timeout, retries) are adapter config recorded in run/eval/cassette metadata, never domain fields. PydanticAI types, provider exception types, usage objects, and model IDs must not leak through the port; PydanticAI's `Agent` abstraction never appears in domain code.
- Architecture guard test: `exeboard_ai` imports no provider SDK and no `pydantic_ai` (all of it lives in `exeboard-integrations`).
- Shared contract test suite parametrized over fake / PydanticAI(`TestModel`) / caching decorator. One `@pytest.mark.live` smoke test per configured provider, excluded from CI.

### D5. Strict replay, not production prompt caching: file-based VCR-style cassettes (expert A)

`ReplayCachingStructuredResponseGenerator(inner, cache, mode, sample_index=0)` with `RECORD` and strict `REPLAY` (miss raises `ReplayCacheMiss` — silent fallthrough to live calls would be quiet remote inference). One JSON file per `(replay_key, sample_index)` under a content-addressed path; stored output re-validated with `model_validate` on load (schema drift raises, never silently regenerates). `sample_index` baked into the disk format now; no N>1 API yet. `replay_key=None` rejected in both modes. Golden cassettes committed under `evals/golden_traces/`. This is deterministic eval replay, not a production prompt/KV cache; production caching is a later latency/cost optimization with a separate design.

### D6. Entailment judge: eval-stage only, structurally absent from runtime (experts A+B)

Judge runs behind the same `StructuredResponseGenerator` port, invoked only by the eval CLI with an explicit `--judge-model` (no default, no env fallback). `summarize_document` has no judge parameter — "no silent remote inference" enforced structurally. Judge sees claim text + **derived verbatim quotes + full resolved cited-span texts only** (no chunk text, no neighbors) — measuring citation support, not answer correctness (the AIS distinction). Verdicts record/replay through D5's cache. Calibration before any gating: ≥0.90 catch on entailment negatives, ≥0.90 supported on positives, 10–20 human spot-checks per release appended as golden cases. A judge error is "no verdict", never "supported".

> Verdict scale is Disagreement 2 below.

### D7. Constrained-rewrite final summary: spec now, build on demand (experts A+C)

Full spec retained from expert A (sentence/claim-ID closure, high-importance coverage check, verbatim numeric-token guard, fallback to deterministic assembly on any failure or generator error, `DocumentSummary.composition` field). **Not built** until Slice 6 admin/demo feedback actually calls the deterministic output choppy — don't pre-solve a complaint nobody has made.

### D8. Eval dataset v1: ~130–145 cases over 3 real public PDFs (expert B)

- Fixtures (sha256-pinned): clean DEF 14A proxy statement; artifact-bearing public board agenda packet (verify ≥1 ligature + ≥1 hyphen-break before committing); table-heavy annual-report excerpt. Each fixture has parser/layout stress labels where applicable: reading-order risk, table-value loss, furniture-as-body, caption orphaning, scanned/no-text page, and page/coordinate mismatch.
- ~40 hand-annotated **paraphrase** positives (shared-token overlap with quote < 60%, lint-enforced), ≥10 of them canonical-tier positives (deliberate curly-quote/ligature/hyphen-break locators with `expected_anchor_tier: "canonical"` — the regression test for the whole D1 migration, since old `normalized_match_only` negatives flip polarity to positives).
- ~65–75 deterministic seeded perturbation negatives (FactCC-style generators in `evals/generators/`): `nonexistent_span`, `wrong_span_same_page`, `wrong_page_span`, `fabricated_quote`, `truncated_quote` — each tagged `expected_error_code`.
- ~30 entailment negatives (`negated_claim`, `entity_swap`, `number_swap`): deterministic gate MUST pass them (CI polarity self-check), judge must catch them.
- Append-only versioning; old `summary_mvp_seed.json` retired.

Thresholds table (into `evaluation.md`): structural/quote negative rejection 100% hard-fail CI; positive acceptance ≥0.95; exact-tier anchor share report-only in v1; entailment negatives passing deterministic gate 100%; judge catch ≥0.90 / judge support on positives ≥0.90 (pre-release); real-LLM citation validity ≥0.90; coverage of gold claims ≥0.70. Reports also track sentence/claim citation coverage, cited-token/output-token ratio, cited-span count, partial-support rate, structured-output retry/failure rates, parser warnings, textless pages, and claims/chunk distribution.

---

## Disagreements — RESOLVED (human decision, 2026-06-10)

1. **PydanticAI vs hand-rolled adapter → RESOLVED: PydanticAI (product-owner decision, 2026-06-10).** Expert A's hand-rolled recommendation rested on an unstated and unjustified premise: committing to a single provider (Anthropic). Note the corrected reasoning: portability alone does not decide this — a hand-rolled adapter against an OpenAI-compatible gateway (OpenRouter, self-hosted LiteLLM) would also reach many models through one API. PydanticAI wins on the residual margins (per-provider structured-output fallbacks, maintained validation-retry harness) at the cost of one framework layer confined to the adapter; the choice is low-stakes and reversible behind the untouched domain port (`StructuredResponseGenerator`). Default model is an eval output (slice 1/5), not a vendor default; OpenRouter is the natural eval channel, and with its enforceable ZDR routing it is not technically disqualified for production either — production channel is a per-customer procurement decision (see channel note in D4).
2. **Judge verdict scale → RESOLVED: 3-level with collapse-at-scoring (expert B).** Record `supported | partially_supported | unsupported` raw; the release gate collapses `partially_supported → unsupported` (strict) in one line of scoring code. Gates identically to binary while preserving the signal where judges and humans actually disagree (a high partial rate means claims are too coarse or the prompt invites overreach); the collapse policy can be revisited without re-running the judge.
3. **Package layout for SDK-bearing code → RESOLVED: exactly one extra package, `exeboard-integrations`.** Anything importing provider SDKs (the Anthropic adapter, live judge wiring) lives there; `exeboard-ai`'s pyproject never lists `anthropic`, making the "domain never imports SDKs" rule mechanically unviolable (import won't resolve; CI fails automatically) rather than a policed convention. The replay cache is stdlib-only and deterministic, so it stays in `exeboard-ai`. Delete `exeboard-application/-domain/-platform/-temporal/-tools`; fold `exeboard-evals` until slice 5 proves a boundary.

---

## Slice plan (updated 2026-06-21)

### Completed baseline — Span-addressed summary context
The current repo baseline is no longer the pre-span-addressed pipeline. The span-addressed context slice is complete: generator-visible evidence spans come from trusted `SpanIndex`/`TextSpan` data, generated page numbers are not trusted, same-page wrong-span quotes remain invalid, and fake-generator unit/integration coverage passes. Future measurement uses this baseline.

### Slice 0 — Grounding observability + LLM-boundary guardrails (S)
Implement only the prerequisites needed to make live-model measurement honest and safe:

- Add `SummarizationRunResult { summary, report }` and a minimal `GroundingRunReport` without changing validity semantics yet.
- Track generated/proposed claim count, evidence count, assembly drops, citation-validation drops, quote-validation drops, valid claims, parser counters, and conservation: `claims_proposed == claims_valid + len(drops)`.
- Represent zero-valid-claim outcomes explicitly (`summary: None` or a typed refusal/result status) instead of raising or fabricating a non-empty `DocumentSummary`.
- Add the `StructuredGenerationError` taxonomy (`InvalidOutput | Unavailable | RequestRejected`) to the domain port.
- Add import-boundary tests: `exeboard_ai` imports no provider SDKs, no `pydantic_ai`, and no `exeboard_integrations`.

**Becomes real:** measurable drop accounting before any provider ranking.
**Out of scope:** canonical anchoring, replay, judge, live provider adapter, UI, Docling, OCR, DB.
**Artifact:** deterministic fake-generator report showing proposed/valid/drop conservation across happy path and drop cases.

### Slice 1 — First Real Run on the span-addressed baseline (S–M)
Build the smallest D4 adapter/CLI surface needed for measurement, not the hardened production adapter:

- Minimal `PydanticAIStructuredResponseGenerator` in `packages/exeboard-integrations` with explicit required `--model` / config, no ambient default model, sync non-streaming port use, and provider exceptions mapped to the Slice 0 taxonomy.
- Dev CLI/script with explicit `--model`, `--pdf`, and output path flags.
- Run 3–5 public board-pack-like PDFs against at least two configured models/providers.
- Print and persist per-document/per-model metrics from `GroundingRunReport`: proposed, assembly drops, citation failures, quote failures, valid claims, parser warnings, textless pages, structured-output retries/failures, latency/cost metadata outside domain summaries.
- Optionally benchmark vendor-native citation features as an eval baseline only; do not make them the runtime architecture.

**Becomes real:** first real LLM calls, first real public PDFs, first provider-comparison data, and first parser-vs-model failure split.
**Out of scope:** strict replay, repair loop, judge, canonicalization, app/API/UI.
**Artifact:** terminal/report table such as `41 proposed, 9 dropped (7 assembly_quote_mismatch, 2 bad citation), 32 valid`, with parser/provider metadata.

### Slice 2 — Quote pathway lands (S–M) — consumes D1, D2, D3
Implement the real evidence contract after the Slice 1 corpus shows actual failure modes:

- `text/canonical.py` with versioned, offset-mapped canonicalization.
- `validation/anchoring.py` with exact-first, canonical-second anchoring inside cited spans only.
- `ClaimEvidence.char_start`, `char_end`, and `anchor_tier`; trusted code re-slices `quote` from `DocumentIR.content`.
- Replace quote validation with offset-integrity re-verification; remove page-scope/fuzzy validity APIs.
- Upgrade `GroundingRunReport` to include exact/canonical anchor rates, ambiguous-anchor count, near-miss diagnostics, and nested evidence failure details.
- Re-run the Slice 1 corpus and record before/after drop rates to `evals/reports/`.

**Becomes real:** first measured recall improvement with zero loosening of fail-closed grounding.
**Out of scope:** Docling, OCR, runtime judge, user-facing app.

### Slice 3 — Board-pack usefulness model pass (S)
Before any admin-facing demo, make the grounded model minimally board-useful without adding product surface area:

- Add `DocumentType="board_pack"`.
- Add board-specific claim roles such as `decision_needed` and `approval_request`.
- Add optional final-summary section metadata (`decisions_needed`, `key_risks`, `financial_highlights`, `recommended_actions`, `open_questions`, `context`) over already-valid claims only.
- Keep deterministic final assembly as fallback; no unsupported executive rewrite.

**Becomes real:** summaries can separate board decisions/approvals from generic findings while preserving citations.
**Out of scope:** polished rewrite, UI, admin workflow, DB.

### Slice 4 — Adapter hardening + strict replay + eval-stage judge (M) — consumes D4, D5, D6
Harden the Slice 1 adapter into the D4 production adapter and make evals reproducible:

- Contract tests over fake / PydanticAI test model / replay wrapper.
- Strict replay cassettes with schema-drift failure, replay-key-required behavior, sample-index path separation, and no fallback to live calls.
- Eval-stage judge behind the same port, requiring explicit `--judge-model`; runtime `summarize_document` remains judge-free.
- Calibration script and confusion matrices by seeded error type, with 10–20 human spot checks before any gate relies on judge results.

**Becomes real:** first byte-identical $0 re-run and first measured claim↔span support rate.

### Slice 5 — Eval dataset v1 + recorded baseline (M–L) — consumes D8
Author the versioned dataset, generators, manifests, and thresholds:

- Append-only dataset manifest with source URL/license/hash, parser version, annotation version, prompt/schema version, split, perturbation generator version, and reviewer.
- Parser/layout stress labels and partial-support cases.
- Deterministic CI hook for structural/quote tiers.
- One full recorded baseline run using strict replay.

**Becomes real:** first versioned, threshold-bearing, CI-gated baseline on real board-pack-like PDFs. This is the release gate before broad reuse (MCP, second agent, productionization).

### Slice 6 — Refusal/demo surface and admin wedge validation (M)
Only after Slice 0 telemetry and Slice 2 trusted offsets exist, make a minimal demo surface:

- Minimal FastAPI/page path: upload PDF → grounded summary → per-claim verified/could-not-verify badge → click-to-highlight cited source range → visible dropped-claim count.
- Highlights render from `DocumentIR.content` offsets and span/page provenance, never by string-searching model quotes.
- Show to 2–3 board admins; record wedge decision as an ADR.

**Out of scope:** auth, DB, multi-doc, Q&A, MCP, deployment.

### Parser escalation trigger — Docling remains parked
Do not start the Docling adapter until Slice 1/2 parser telemetry shows PyMuPDF failure is material. Reopen Docling Slice 0 if parser warnings, reading-order/table/caption failures, or textless-page rates block summary quality. `docs/document-intelligence/docling-api-notes.md` must be completed against installed `docling==2.95.0` before any fake-based mapper work.

---

## Scaffold freeze list (requires human-approval checkpoint before any destructive scaffold change)

| Artifact | Action |
|---|---|
| `apps/agents/board_minutes` | Delete — crowded wedge; biases the decision admins should make |
| `apps/workers/{agent,ingestion,workflow}` | Delete — no Temporal for 90 days |
| `apps/web` | Freeze — any Slice 6 demo page lives in `apps/api` unless a later ADR changes the surface |
| `apps/mcp-server` | Freeze — credible surface #2, after slice 5 + authz story |
| `packages/exeboard-{application,domain,platform,temporal,tools}` | Delete (per architecture.md §18's own advice) |
| `packages/exeboard-integrations` | Keep — the one SDK-bearing package (resolved disagreement 3) |
| `packages/exeboard-evals` | Fold into `exeboard-ai` + `evals/` tree until slice 5 proves a boundary |
| `docs/architecture.md` | Reframe as north-star ADR; this document is the "next 90 days" doc |

## What not to do (next 90 days)

Temporal wiring · Docling adapter before parser telemetry and completed Slice 0 discovery · minutes-from-transcript agent · LangGraph/multi-agent orchestration · registries & capability manifests · MCP productionization (gated on slice 5) · **fuzzy-match thresholds (refused permanently)** · OCR strategies · DB/auth/multitenancy · constrained-rewrite pass before admin/user evidence of need · broad fake-only validator deepening that does not improve Slice 0/Slice 1 measurement.

## Riskiest assumptions (one per expert)

- **A (boundary):** that structured-output generation + PydanticAI's 2-attempt validation retry preserves acceptable claim recall on real packs across providers — i.e., semantic-validator failures (out-of-set span IDs, blank quotes) are rare residuals rather than a dominant, provider-dependent failure mode. Measured per-model in slice 1.
- **B (grounding):** that drop-causing artifacts on real board packs are *normalization-shaped* (ligatures, hyphenation, quote styling). If they're structural (garbage glyphs, wrong reading order, image-only pages), no canonicalization tier recovers them and the right next move is parser/OCR strategy work, not matcher work. Slice-1/Slice-2 telemetry (`near_miss_tier="none"`, parser warnings, textless pages, table/layout labels) measures this.
- **C (sequencing):** that 2–3 board admins can be reached after the grounded report/offset pathway exists; if not, the wedge decision stalls and slice 5 proceeds on the pack-summary assumption unvalidated.
