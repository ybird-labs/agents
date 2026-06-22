# Research: External best practices for Exeboard evidence-backed document summaries

## Summary
Exeboard's 90-day plan is broadly aligned with current evidence: keep citations as trusted-code anchored spans, validate before final synthesis, use structured-output adapters behind ports, and gate model/provider choice on measured grounding quality. The strongest improvements are to (1) add an explicit citation-granularity/coverage metric, (2) make parser/layout failures part of the eval corpus earlier, (3) benchmark native citation features as an eval baseline but not a runtime dependency, and (4) separate reproducibility replay from production prompt caching.

## Prioritized improvement opportunities

1. **Add sentence/claim-level attribution coverage and conciseness metrics to `evaluation.md`** — Current plan measures quote/citation validity, judge support, and coverage of gold claims, but not whether every final sentence is fully covered by the smallest sufficient evidence. Recent locally-attributable generation work defines two complementary requirements: every generated fact should be backed by cited snippets, and citations should be as concise as possible; it also found localized citations can cut human verification time by roughly half while keeping generation quality. Change the plan to report per-sentence/claim: `has_citation`, `fully_supported`, `partial_supported`, `unsupported`, cited-token count, cited-span count, and citation-token/output-token ratio. Confidence: **high**. [Attribute First, then Generate](https://arxiv.org/html/2403.17104)

2. **Keep quote-as-locator, but add a vendor-native citation baseline in Slice 1/Slice 4 evals** — Anthropic's Citations API guarantees valid pointers to provided documents and extracts `cited_text`; its docs explicitly contrast this with prompt-based quote emission, claiming better citation reliability and relevance. However, it is incompatible with Anthropic Structured Outputs, PDF citations are page-range based rather than Exeboard char-range based, and image citations are unsupported. Change the plan to benchmark native citations as an external baseline for recall/precision/user-verification effort, not as the core architecture; preserve trusted-code char anchoring from `DocumentIR.content`. Confidence: **high**. [Anthropic Citations docs](https://platform.claude.com/docs/en/build-with-claude/citations)

3. **Add an `attribute-first` optional final-composition experiment before building constrained rewrite** — The current plan defers constrained rewrite until users complain. If they do, do not jump straight to freeform rewrite: test a two-step “selected evidence cluster → one sentence” composer that receives only pre-anchored claims/evidence and must output sentence objects linked to claim IDs. This mirrors the research decomposition: content selection, sentence planning, sentence-by-sentence generation. Change D7 to name this as the first experiment if choppiness appears. Confidence: **medium-high**. [Attribute First, then Generate](https://arxiv.org/html/2403.17104)

4. **Move parser/layout stress cases into eval dataset v1, not only Docling later** — The plan correctly defers Docling until PyMuPDF fails, but board packs often contain tables, furniture, captions, scanned inserts, and multi-column reading-order issues. Docling's own docs emphasize provenance tracking, page/position metadata, structured tables, pictures, document hierarchy, and body-vs-furniture layers. Change D8 to include parser-quality labels and failure classes: reading-order error, table-value lost, furniture included as body, caption orphaned, scanned/no-text page, and page/coordinate mismatch. These can be tested with PyMuPDF now and used later to justify Docling. Confidence: **high**. [DoclingDocument docs](https://docling-project-docling.mintlify.app/concepts/docling-document), [Docling PDF Processing Options](https://docling-project-docling.mintlify.app/guides/pdf-processing)

5. **Treat Docling as a measured parser candidate, but require real API discovery before implementation** — The local Docling plan's Slice 0 is well-supported externally: Docling exposes `DoclingDocument` as a Pydantic representation with text, tables, pictures, hierarchy, provenance, pages, bounding boxes, and `iterate_items()`. Change the summary plan's “Docling adapter later” note to: “trigger Docling spike when eval parser-failure rate exceeds threshold or table/caption failures dominate drops.” Preserve no silent OCR/remote inference. Confidence: **high**. [DoclingDocument docs](https://docling-project-docling.mintlify.app/concepts/docling-document)

6. **Record structured-output capability and retry behavior per provider/model in the eval report** — PydanticAI supports output schemas and validation-driven retries; OpenAI and Gemini both expose native JSON-schema/response-schema mechanisms, while Anthropic citations cannot be combined with Anthropic structured outputs. Change D4/Slice 1 reports to include: provider, model, native structured mode/tool mode/prompt fallback, retry count, validation failure category, schema version, and tokens/cost. Confidence: **high**. [PydanticAI Output docs](https://pydantic.dev/docs/ai/core-concepts/output/), [OpenAI Structured Outputs](https://openai.com/index/introducing-structured-outputs-in-the-api/), [Gemini Structured Outputs](https://ai.google.dev/gemini-api/docs/structured-output), [Anthropic Citations docs](https://platform.claude.com/docs/en/build-with-claude/citations)

7. **Calibrate the LLM judge with human spot checks and keep deterministic validators as the hard gate** — External eval guidance warns that LLM-system evaluation should define task scope, datasets, metrics, and methodology; recent factuality-metric work cautions that automatic factuality evaluators can have surface-similarity and context-window biases. The plan already keeps the judge eval-only; strengthen it by requiring confusion matrices by error type, bootstrap confidence intervals for support rates, and periodic human adjudication of borderline `partial_supported` cases. Confidence: **high**. [Practical Guide for Evaluating LLMs](https://arxiv.org/html/2506.13023v2), [Verify with Caution](https://aclanthology.org/2025.findings-acl.1175.pdf)

8. **Make `partial_supported` a first-class diagnostic, not only a collapsed judge label** — Attribution research and human interfaces distinguish full support, partial support, no support, refutation, and unclear; partial support often reveals claims that are too broad or citations missing adjacent context. Change D6/D8 to add seeded partial-support cases and report partial-support rate separately even when release scoring collapses it to unsupported. Confidence: **medium-high**. [Attribute First, then Generate](https://arxiv.org/html/2403.17104)

9. **Separate strict replay cassettes from production prompt caching in terminology and design** — The plan's strict replay cache is right for deterministic evals. External caching guidance distinguishes request-response replay/caching from provider prompt/KV caching for latency/cost, and AI21 notes agentic pipelines need cache keys that encode call position/sample to reproduce variance. Change D5 to explicitly call it “replay,” include operation/prompt/schema/model/parser/canonicalization versions in keys, and add a later, separate production prompt-cache story. Confidence: **high**. [AI21 caching in agentic pipelines](https://www.ai21.com/blog/caching-in-agentic-llm-pipelines/), [AWS LLM caching guidance](https://aws.amazon.com/blogs/database/optimize-llm-response-costs-and-latency-with-effective-caching/)

10. **Version eval datasets append-only and promote real traces into datasets deliberately** — LangSmith docs reflect a common production pattern: curate datasets from manual cases, historical traces, or synthetic generation, version datasets, and run evaluations to compare versions/regressions. Change D8/Slice 5 to specify dataset manifest fields: source PDF URL/license/hash, parser version, annotation version, prompt/schema version, split, perturbation generator version, and reviewer. Confidence: **high**. [LangSmith dataset management](https://docs.langchain.com/langsmith/manage-datasets), [OpenAI Evals cookbook](https://developers.openai.com/cookbook/examples/evaluation/getting_started_with_openai_evals)

11. **Add a parser-to-grounding error budget in Slice 1 terminal table** — The current Slice 1 table counts proposed/citation-fail/quote-fail/valid. Add parser warnings and parser-derived denominators: pages, spans, textless pages, table spans, furniture spans, chunks, claims per chunk, dropped due to invalid span IDs vs quote anchoring. This will tell whether failures are model-output issues or upstream extraction issues. Confidence: **medium-high**. [DoclingDocument docs](https://docling-project-docling.mintlify.app/concepts/docling-document)

12. **Use model/provider selection as a Pareto decision, not a single accuracy ranking** — Current plan says default model is chosen by evals. Make the decision table explicit: structural schema success, quote-anchor exact/canonical rates, citation validity, judge support, latency, token cost, privacy channel/ZDR availability, context length, retry rate, and parser-PDF support. Anthropic native citations are ZDR-eligible for organizations with ZDR, but incompatible with structured outputs; OpenAI/Gemini have native schema support; PydanticAI can normalize retries/fallbacks. Confidence: **medium-high**. [Anthropic Citations docs](https://platform.claude.com/docs/en/build-with-claude/citations), [OpenAI Structured Outputs](https://openai.com/index/introducing-structured-outputs-in-the-api/), [Gemini Structured Outputs](https://ai.google.dev/gemini-api/docs/structured-output/)

## Concrete plan edits suggested

- **D1/D2:** keep as-is; add metric `citation_conciseness_tokens` and invariant that final summary evidence is evaluated at sentence/claim granularity.
- **D3:** extend `GroundingRunReport` with parser counters, cited-token counts, `partial_supported_count`, and per-provider retry/validation stats.
- **D4:** add provider capability matrix fields and explicitly document Anthropic Citations as eval baseline only because citations and structured outputs are incompatible.
- **D5:** rename user-facing concept from “cache” to “strict replay”; reserve “prompt cache” for provider latency/cost features.
- **D6:** keep judge eval-only; add calibration confusion matrices by seeded error type and human spot-check protocol.
- **D7:** if rewrite is needed, first test selected-evidence/sentence-planning composition, not unconstrained rewrite.
- **D8:** add parser/layout stress labels, partial-support cases, and append-only manifest/version fields.
- **Slice 1:** run at least two providers plus one native-citation baseline where available; log parser counters and structured-output retry stats.
- **Docling plan:** no change to architecture; add threshold trigger from eval parser-failure telemetry before starting the adapter.

## Sources

- Kept: Anthropic Citations docs (https://platform.claude.com/docs/en/build-with-claude/citations) — primary vendor evidence on native citation guarantees, chunking, index formats, ZDR eligibility, and incompatibility with structured outputs.
- Kept: OpenAI Structured Outputs announcement (https://openai.com/index/introducing-structured-outputs-in-the-api/) — primary vendor evidence that JSON mode is weaker than schema-constrained structured outputs.
- Kept: Gemini Structured Outputs docs (https://ai.google.dev/gemini-api/docs/structured-output) — primary vendor evidence for response schemas and Pydantic-compatible schema paths.
- Kept: PydanticAI Output docs (https://pydantic.dev/docs/ai/core-concepts/output/) — primary framework evidence for schema validation and output retries.
- Kept: DoclingDocument docs (https://docling-project-docling.mintlify.app/concepts/docling-document) — primary parser docs for document hierarchy, tables, pictures, provenance, pages, bounding boxes, and iteration shape.
- Kept: Docling PDF Processing Options (https://docling-project-docling.mintlify.app/guides/pdf-processing) — primary parser docs for PDF-specific table/OCR/layout capabilities.
- Kept: Attribute First, then Generate (https://arxiv.org/html/2403.17104) — recent research directly relevant to locally attributable grounded summarization, citation conciseness, sentence-level support, and human verification time.
- Kept: A Practical Guide for Evaluating LLMs (https://arxiv.org/html/2506.13023v2) — recent eval methodology guidance for datasets, metrics, and scope alignment.
- Kept: Verify with Caution (https://aclanthology.org/2025.findings-acl.1175.pdf) — cautionary evidence on factuality evaluator biases.
- Kept: AI21 caching in agentic pipelines (https://www.ai21.com/blog/caching-in-agentic-llm-pipelines/) — practical evidence for replay keys that support reproducibility and variance.
- Kept: AWS LLM caching guidance (https://aws.amazon.com/blogs/database/optimize-llm-response-costs-and-latency-with-effective-caching/) — practical distinction between prompt caching and request-response caching.
- Kept: LangSmith dataset management (https://docs.langchain.com/langsmith/manage-datasets) — practical evidence for dataset versioning and trace-to-dataset workflows.
- Kept: OpenAI Evals cookbook (https://developers.openai.com/cookbook/examples/evaluation/getting_started_with_openai_evals) — practical eval framing for regression testing across code/model changes.
- Dropped: SEO/blog summaries of structured output providers — useful for orientation but weaker than official OpenAI/Gemini/Pydantic docs.
- Dropped: Towards Data Science Docling article — useful practitioner context, but not primary evidence compared with Docling docs.
- Dropped: pdfmux benchmark blog — interesting parser benchmark, but not primary/peer-reviewed enough for plan changes.
- Dropped: Future-dated or speculative model/provider benchmark pages — excluded unless needed for a later provider bakeoff.

## Gaps

- I did not verify current live provider pricing, exact current model IDs, or enterprise data-retention terms beyond cited public docs; do this immediately before model bakeoff/procurement.
- I did not inspect real public board-pack PDFs; parser/layout failure thresholds need empirical data from Slice 1.
- The Docling 2.95 local discovery file remains unfilled; external docs support the approach but do not replace installed-version API verification.
- The best judge model for board-pack claims remains unknown; calibrate with Exeboard's own positive/negative/partial cases.

## Supervisor coordination
No supervisor decision was needed; task was research-only and no project files outside the requested output artifact were edited.

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "Completed focused research and wrote only the requested artifact at deep-research/external-best-practices.md; no code, plan, or test files were changed."
    },
    {
      "id": "criterion-2",
      "status": "satisfied",
      "evidence": "Brief includes prioritized improvement opportunities with external source links, confidence levels, concrete plan-change recommendations, kept/dropped sources, and residual gaps."
    }
  ],
  "changedFiles": [
    "/Users/jeancarlobarrios/Developing/exeboard/ai/deep-research/external-best-practices.md"
  ],
  "testsAddedOrUpdated": [],
  "commandsRun": [
    {
      "command": "read local plan files via functions.read",
      "result": "passed",
      "summary": "Read summary-agent-improved-plan.md, implementation-plan.md, docling-adapter-plan.md, and docling-api-notes.md for context."
    },
    {
      "command": "web_search with four research angles plus targeted follow-ups",
      "result": "passed",
      "summary": "Covered grounded/cited summarization, PDF parsing/Docling, structured-output reliability, eval datasets/judges, replay/caching, and provider selection."
    },
    {
      "command": "fetch_content/get_search_content for primary sources",
      "result": "passed",
      "summary": "Fetched primary docs and research papers including Anthropic Citations, OpenAI Structured Outputs, Gemini structured output, Docling docs, PydanticAI output docs, and eval/caching sources."
    },
    {
      "command": "functions.write deep-research/external-best-practices.md",
      "result": "passed",
      "summary": "Wrote requested research artifact."
    }
  ],
  "validationOutput": [
    "Research artifact written successfully by functions.write.",
    "No automated tests were run because the task was research-only and requested no code edits."
  ],
  "residualRisks": [
    "No shell access was available to run git status; no staging commands were used.",
    "Provider pricing/model IDs and Docling installed-version behavior should be re-verified immediately before implementation."
  ],
  "noStagedFiles": true,
  "notes": "Review gate required by parent/reviewer."
}
```