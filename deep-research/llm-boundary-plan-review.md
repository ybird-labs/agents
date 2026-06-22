# LLM boundary plan review

Date: 2026-06-21
Reviewer role: senior agentic systems / Python architecture reviewer
Scope reviewed: `docs/document-intelligence/summary-agent-improved-plan.md`, `implementation-plan.md`, `evaluation.md`, `summarization/ports.py`, `chunk_summarizer.py`, `pipeline.py`, and `packages/exeboard-integrations`.

## 1. Research performed

Fresh web research was performed before reviewing the design.

Queries used:

1. `2026 best practices structured outputs JSON schema validation Pydantic LLM applications provider boundaries`
2. `provider agnostic LLM interface Python protocols ports adapters testing fake clients agents`
3. `OpenAI structured outputs Anthropic tool use Gemini structured output JSON schema comparison best practices 2025 2026`
4. `Python typing Protocol ports adapters clean architecture LLM clients fake implementations tests`
5. Follow-up official-doc searches for OpenAI/Gemini/PydanticAI structured output behavior.

Sources used:

- [OpenAI — Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs): strict JSON-schema structured outputs are distinct from plain JSON mode and should be treated as a contract.
- [Google AI for Developers — Gemini structured outputs](https://ai.google.dev/gemini-api/docs/structured-output): Gemini can generate to provided JSON Schema / Pydantic-compatible schemas, but provider semantics differ.
- [Anthropic Claude API Docs — Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs): Claude supports structured JSON outputs and strict tool use, reinforcing that adapters must hide provider-specific channels.
- [PydanticAI Docs — Output](https://pydantic.dev/docs/ai/core-concepts/output/): PydanticAI uses Pydantic schemas for structured outputs and supports output validation retries.
- [Service layer for AI agents: decoupling the loop](https://www.learnwithparam.com/blog/service-layer-ai-agents-decoupling-logic): application logic should take LLM dependencies explicitly and tests should call services with fakes, not provider globals.
- [Hexagonal Architecture — EngineersOfAI](https://engineersofai.com/docs/python/python-advanced/architecture-and-systems-design/hexagonal-architecture): ports/adapters improve testability by making external systems swappable behind protocols.

## 2. Verdict

**CHANGE** — the direction is sound and mostly aligned with provider-agnostic, schema-first design, but several implementation-plan guardrails should be tightened before building the live adapter/replay/eval slices.

The strongest parts are:

- `exeboard_ai` currently has a clean `StructuredResponseGenerator` protocol with no provider SDK imports.
- `chunk_summarizer.py` generates a deterministic, schema-fingerprinted replay key from prompt/schema/context.
- `packages/exeboard-integrations` exists as the intended SDK-bearing package and is currently dependency-free.
- Current tests exercise fake LLM generation and exact quote/citation filtering.

The highest risks are:

- The current port lacks the planned error taxonomy, so adapter exceptions can leak or become ad hoc.
- Replay-cache and live-test split are only documented, not yet enforced by executable guard tests.
- `_assemble_evidence()` silently drops claims on quote mismatch before validation/reporting, which conflicts with the improved plan’s telemetry goals.
- Model/provider selection is described as eval-driven, but there is no explicit config contract that prevents implicit env/default model selection.
- No-silent-remote-inference relies on future discipline unless structural tests are added now.

## 3. Prioritized plan-improvement opportunities

### P0. Freeze the provider-agnostic port contract before any PydanticAI adapter

**Problem:** `ports.py` currently exposes only `StructuredGenerationRequest` and `StructuredResponseGenerator.generate()`. The improved plan says the port will use `StructuredGenerationError -> InvalidOutput | Unavailable | RequestRejected`, but that taxonomy is not in the current code. If the adapter is built first, provider/PydanticAI exception semantics may leak through tests and callers.

**Guardrails:**

- Add domain-owned exception classes in `exeboard_ai.document_intelligence.summarization.ports` only.
- Do **not** include provider name, model ID, usage, latency, trace IDs, token counts, retry metadata, or raw provider exceptions in the public domain return shape.
- Adapter may log/record provider details internally or in cassette metadata, but domain code should only catch the port taxonomy.
- Keep the port sync and non-streaming for this MVP. PydanticAI may be async-capable, but the current pipeline is sync and chunk-level; async would widen scope.
- Keep `output_model: type[T]` generic despite Pyright friction; it is useful here because the same port will serve chunk summary and eval-stage judge outputs.

**Acceptance tests:**

- Fake generator can raise each domain exception type and `summarize_document()`/eval caller handles it fail-closed without provider imports.
- A contract test asserts PydanticAI/provider exceptions are mapped to `InvalidOutput`, `Unavailable`, or `RequestRejected`.
- `pyright` accepts a structural fake implementing `generate(..., output_model: type[T]) -> T`.

### P0. Make no-silent-remote-inference structural, not policy-only

**Problem:** The plan correctly says judge/runtime should not invoke live inference implicitly, but enforcement is not yet executable. The most dangerous future bug is a replay miss or missing env var causing a live model call from a deterministic test/eval path.

**Guardrails:**

- No live adapter constructor should read model/provider/API key from ambient env by default. Require explicit config object or CLI flag.
- `summarize_document()` should continue accepting only a passed `StructuredResponseGenerator`; no factory, model string, env lookup, or provider import in pipeline/domain code.
- Eval judge should remain structurally absent from runtime pipeline. The eval CLI must require `--judge-model` plus an explicit live/record mode.
- Replay `REPLAY` mode must fail closed on cache miss. No fallback-to-live path.
- OCR remains explicit parser strategy/config only; PyMuPDF parser must never silently OCR or call remote parsing/inference.

**Acceptance tests:**

- With env vars for OpenAI/Anthropic/Gemini present, deterministic fake tests do not import SDKs or make network calls.
- Replay `REPLAY` miss raises `ReplayCacheMiss` and does not call the inner generator.
- Eval judge invocation without `--judge-model` fails before constructing a live generator.
- `summarize_document()` has no parameter path that accepts provider/model names.
- Parser tests assert image-only/no-text PDF raises `NoExtractableTextError` or warning path, not OCR/remote fallback.

### P0. Turn invisible claim drops into typed run-report telemetry before relying on model comparisons

**Problem:** `chunk_summarizer._assemble_evidence()` returns `None` when a quote is not an exact substring of a cited allowed span. That means malformed/normalization-only/fuzzy/wrong-span claims can disappear before `quote_validator` and before the improved plan’s drop taxonomy. The improved plan identifies this, but Slice 1 still proposes measuring drop counts before implementing reporting.

**Guardrails:**

- Do not use silent `None` drops as the primary metric for provider/model selection.
- Introduce a minimal `ChunkSummarizationReport` or pipeline-level `GroundingRunReport` earlier than currently scheduled, even if full canonical anchoring waits until Slice 3.
- Report proposed/generated claim count, assembled count, validation-valid count, and dropped stage/reason.
- Maintain conservation invariant: `claims_proposed == claims_valid + len(drops)` once reporting exists.

**Acceptance tests:**

- Generated claim with bad quote produces a `DroppedClaimRecord(stage="assembly_anchor" or equivalent)` rather than disappearing silently.
- A fake generator returning N claims yields a report where proposed/valid/drop counts add up.
- Model-comparison CLI refuses to print provider ranking if report conservation fails.

### P1. Specify replay cassette format and schema-drift behavior before live eval baselines

**Problem:** The plan says strict VCR-style cassettes with Pydantic revalidation on load, but it needs one accepted disk contract before the adapter lands. Otherwise, cassettes will become provider-specific or unstable.

**Guardrails:**

- Store domain request envelope fields, prompt/schema fingerprints, `output_model` schema name/version/fingerprint, sample index, adapter `generator_info`, and raw structured output.
- Store no secrets and no API keys. Redact request headers/provider auth if adapter metadata is ever recorded.
- `REPLAY` validates the cached output with the current `output_model.model_validate()`; schema drift raises a specific cache/schema error.
- `RECORD` requires non-null `replay_key`; `REPLAY` requires non-null `replay_key`.
- Path derivation must be content-addressed and safe for filesystems; do not trust raw replay key as a path.

**Acceptance tests:**

- Replay returns byte-identical validated model from cassette and does not call inner generator.
- Replay miss raises `ReplayCacheMiss`.
- Cached output with extra/missing fields fails validation and does not regenerate.
- Same request with different prompt version/schema fingerprint maps to different cassette path.
- `sample_index` changes path and cassette identity even before multi-sample API exists.

### P1. Make model selection an eval artifact, not an adapter default

**Problem:** The plan says default model is eval-driven, but adapter design could accidentally create provider defaults through constructor defaults, env fallback, or PydanticAI model strings sprinkled in scripts.

**Guardrails:**

- Define a small `LiveModelConfig` in `exeboard-integrations` or CLI composition only: model string, timeout, output retries, and provider-specific auth source if needed.
- Domain request metadata may include operation/prompt/schema fingerprints, but not canonical model IDs.
- No default production model in reusable code. A CLI may have a required `--model`; an eval report may recommend a model.
- Baseline reports must record model/provider externally, not on `SummaryClaim` or `DocumentSummary`.

**Acceptance tests:**

- Constructing the live adapter without a model string raises a config error.
- `SummaryClaim`, `ChunkSummary`, and `DocumentSummary` do not expose model/provider fields.
- Eval baseline output includes model/config outside domain summary JSON.
- Provider comparison over at least two configured models records separate replay namespaces.

### P1. Enforce package import boundaries with CI tests now

**Problem:** `packages/exeboard-integrations` is the intended SDK-bearing package, but currently only docs enforce that `exeboard_ai` cannot import `pydantic_ai` or provider SDKs. The root workspace still contains many scaffold packages, so accidental imports are easy.

**Guardrails:**

- Add an architecture test or script rule: `packages/exeboard-ai/src` must not import `pydantic_ai`, `openai`, `anthropic`, `google.genai`, `google.generativeai`, `litellm`, `httpx` for model calls, or `requests` for model calls.
- `exeboard-integrations` may import `exeboard_ai` ports/models, but `exeboard_ai` must not import `exeboard_integrations`.
- Provider adapter code lives under `packages/exeboard-integrations/src/exeboard_integrations/llm/` or similarly explicit namespace.

**Acceptance tests:**

- Static import-boundary test fails if `exeboard_ai` imports `pydantic_ai` or provider SDKs.
- Static import-boundary test fails if `exeboard_ai` imports `exeboard_integrations`.
- `packages/exeboard-ai/pyproject.toml` has no provider SDK/PydanticAI dependency.

### P1. Clarify fake/live test split and markers

**Problem:** Current tests use good deterministic fakes, but there is no documented live-test marker/skip policy in code yet. Once adapters land, accidental CI live calls are likely unless split is explicit.

**Guardrails:**

- Unit and integration tests under the normal suite use fake generators or replay only.
- Live tests are `@pytest.mark.live` and require explicit env/CLI opt-in, never default CI.
- Adapter contract tests should run against fake/PydanticAI test model/replay without real network.
- Live smoke tests prove only wiring; they should not become correctness gates.

**Acceptance tests:**

- Running the default documented test command with provider API keys set still skips live tests.
- `pytest -m live` fails with a clear skip/error if required explicit model/API key config is absent.
- Contract tests are parametrized over fake generator, cache replay, and PydanticAI test model where feasible.

### P2. Keep structured-output schemas operation-local and versioned

**Problem:** `_GeneratedChunkSummary` is intentionally private and operation-specific, which is good. The plan should state that provider adapters receive JSON Schema from Pydantic but never substitute provider-owned schemas.

**Guardrails:**

- The Pydantic model passed to the port is the source of truth for validation.
- Adapter may translate to provider-native structured-output mechanisms, but must validate the final result with `output_model.model_validate()` before returning.
- Bump `CHUNK_SUMMARY_OUTPUT_SCHEMA_VERSION` when `_GeneratedChunkSummary` semantics change, not only when public domain models change.

**Acceptance tests:**

- Fake/live adapter returns are revalidated against `output_model` even if provider claims schema compliance.
- Extra fields in model output are rejected because schemas use `extra="forbid"`.
- Changing generated schema fingerprint changes replay key.

### P2. Document sync-vs-async decision explicitly

**Problem:** The current sync port is appropriate, but PydanticAI and live providers often expose async APIs. Without an ADR sentence, future code may introduce async into the port prematurely.

**Guardrails:**

- Keep sync `generate()` for the MVP because parser/chunker/pipeline are sync and test determinism is more important than throughput.
- If async is needed later, add a separate `AsyncStructuredResponseGenerator` port rather than making the current port ambiguous.

**Acceptance tests:**

- None required beyond type checks now; add only if async port is introduced.

## 4. Recommended protocol shape

Current shape is close. Recommended narrow shape before adapter implementation:

```python
T = TypeVar("T", bound=BaseModel)

class StructuredGenerationError(Exception): ...
class InvalidOutput(StructuredGenerationError): ...
class Unavailable(StructuredGenerationError): ...
class RequestRejected(StructuredGenerationError): ...

class StructuredGenerationRequest(BaseModel):
    operation_name: str
    prompt_name: str
    prompt_version: str
    output_schema_name: str
    output_schema_version: str
    prompt: str
    context: BaseModel | None = None
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

Important exclusions from the port:

- No provider SDK/PydanticAI types.
- No model ID as domain data.
- No usage/cost/confidence/trace IDs until their lifecycle is defined.
- No retries/streaming/async knobs in the domain request for this MVP.

## 5. Tests required before implementation can be considered ready

Minimum acceptance-test set for the next slices:

1. **Boundary/import tests**: `exeboard_ai` imports no `pydantic_ai`, provider SDK, or `exeboard_integrations`.
2. **Port exception tests**: adapter maps invalid output / provider unavailable / request rejected into domain exceptions.
3. **Fake generator tests**: existing fake tests remain the default for `summarize_chunk()` and `summarize_document()`.
4. **Replay cache tests**: strict replay miss, schema drift, no inner call, sample index path separation, replay key required.
5. **No-silent-live tests**: default pytest suite cannot perform network/model calls even with API keys present.
6. **Model config tests**: live adapter requires explicit model; no default env-derived model.
7. **Run-report tests**: generated/proposed/valid/drop conservation around assembly and validation.
8. **OCR/parser guard tests**: no silent OCR or remote inference for textless PDFs.

## 6. Deferred/future concerns

Do not pull these into the MVP protocol or next immediate adapter unless a measured need appears:

- Streaming.
- Async pipeline execution.
- Token/cost tracking as domain fields.
- Trace IDs or observability objects in domain models.
- Multi-provider routing/capability registry.
- Retry policy as a domain request field.
- Final constrained rewrite pass.
- Entailment judge in runtime pipeline.
- OCR strategy beyond explicit parser configuration.

## 7. Naming/layout refinements

- Put provider code under `packages/exeboard-integrations/src/exeboard_integrations/llm/pydantic_ai_structured.py` or similar. Avoid names that privilege one vendor.
- Keep replay cache in `exeboard_ai.document_intelligence.summarization.replay` only if it remains stdlib-only and deterministic; otherwise move SDK-coupled recording to integrations.
- Rename future cache wrapper as `ReplayCachingStructuredResponseGenerator` rather than generic `Caching...` to make strict replay semantics obvious.
- Prefer `RunReport` / `GroundingRunReport` over log-only telemetry.
- Keep generated-schema classes private per operation (`_GeneratedChunkSummary`) but version them explicitly.

## 8. Evidence from local review

Files inspected included:

- `docs/document-intelligence/summary-agent-improved-plan.md`
- `docs/document-intelligence/implementation-plan.md`
- `docs/document-intelligence/evaluation.md`
- `packages/exeboard-ai/src/exeboard_ai/document_intelligence/summarization/ports.py`
- `packages/exeboard-ai/src/exeboard_ai/document_intelligence/summarization/chunk_summarizer.py`
- `packages/exeboard-ai/src/exeboard_ai/document_intelligence/summarization/pipeline.py`
- `packages/exeboard-ai/src/exeboard_ai/document_intelligence/validation/*`
- `packages/exeboard-integrations/*`
- relevant document-intelligence tests.

Validation command run:

```bash
uv run --package exeboard-ai --with pytest pytest \
  tests/unit/document_intelligence/test_summarization_ports.py \
  tests/unit/document_intelligence/test_chunk_summarizer.py \
  tests/unit/document_intelligence/test_quote_validator.py \
  tests/integration/document_intelligence/test_summary_pipeline.py
```

Result: `48 passed in 0.09s`.

Import grep found no provider SDK/PydanticAI imports under `packages/exeboard-ai` or `packages/exeboard-integrations`; only docs mention the planned boundary.

## 9. Acceptance report

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "Scope was limited to research, review, validation commands, and writing deep-research/llm-boundary-plan-review.md; no source implementation files were edited."
    },
    {
      "id": "criterion-2",
      "status": "satisfied",
      "evidence": "Review cites fresh web research, lists inspected files, records local validation command output, and provides prioritized guardrails plus acceptance tests."
    }
  ],
  "changedFiles": [
    "deep-research/llm-boundary-plan-review.md"
  ],
  "testsAddedOrUpdated": [],
  "commandsRun": [
    {
      "command": "web_search with 4 LLM-boundary/structured-output/testing queries plus 3 official-doc follow-up queries",
      "result": "passed",
      "summary": "Collected current sources for structured outputs, PydanticAI validation retries, provider-agnostic ports, and fake-client testing."
    },
    {
      "command": "read requested docs/source files and inspect packages/exeboard-integrations",
      "result": "passed",
      "summary": "Reviewed plans, current port, chunk summarizer, pipeline, validation helpers, integrations package, and related tests."
    },
    {
      "command": "grep -RIn \"pydantic_ai\\|openai\\|anthropic\\|google.generative\\|genai\\|gemini\\|litellm\\|openrouter\\|requests\\|httpx\" packages/exeboard-ai packages/exeboard-integrations docs/document-intelligence tests",
      "result": "passed",
      "summary": "No provider SDK/PydanticAI imports found in packages; matches were documentation/test text only."
    },
    {
      "command": "uv run --package exeboard-ai --with pytest pytest tests/unit/document_intelligence/test_summarization_ports.py tests/unit/document_intelligence/test_chunk_summarizer.py tests/unit/document_intelligence/test_quote_validator.py tests/integration/document_intelligence/test_summary_pipeline.py",
      "result": "passed",
      "summary": "48 passed in 0.09s."
    },
    {
      "command": "git status --short",
      "result": "passed",
      "summary": "Repository has many pre-existing unstaged/untracked added files; this task only created deep-research/llm-boundary-plan-review.md and staged no files."
    }
  ],
  "validationOutput": [
    "48 focused document-intelligence tests passed.",
    "Provider import grep found no SDK/PydanticAI imports in packages/exeboard-ai or packages/exeboard-integrations.",
    "packages/exeboard-integrations is currently a placeholder with no dependencies."
  ],
  "residualRisks": [
    "Port error taxonomy, replay cache, live-test marker policy, and run-report telemetry are planned but not implemented yet.",
    "Repository contains many pre-existing unstaged/untracked files unrelated to this review; no staged files were detected by git diff --cached --name-only."
  ],
  "noStagedFiles": true,
  "notes": "Verdict: CHANGE. Do not implement live adapter/replay/model-selection slices until P0 guardrails are accepted."
}
```
