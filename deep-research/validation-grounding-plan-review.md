# Validation and grounding plan review

Date: 2026-06-21
Reviewer role: senior Python/document-intelligence grounding validation reviewer
Scope reviewed: `docs/document-intelligence/summary-agent-improved-plan.md`, `docling-adapter-plan.md`, `docling-api-notes.md`, `pdf-parsing-strategy.md`, validation/IR/parser/summarization code under `packages/exeboard-ai/src/exeboard_ai/document_intelligence`, and unit tests under `tests/unit/document_intelligence`.

## 1. Research performed and sources used

Fresh web research was performed before this review, using four query angles:

1. Grounded RAG / citation attribution validation best practices.
   - [CiteEval: Principle-Driven Citation Evaluation for Source Attribution](https://aclanthology.org/2025.acl-long.1574.pdf) — supports statement-level citation evaluation and the distinction between cited-context support and broader answer correctness.
   - [RAG: Citations · llmbestpractices](https://llmbestpractices.com/ai-agents/rag-citations) — reinforces checkable citations and post-generation guardrails.
   - [How to Build an Answer Grounding Pipeline](https://geodocs.dev/technical/how-to-build-answer-grounding-pipeline) — describes explicit evidence extraction, attribution, and post-generation verification as separate stages.
2. Python quote matching / PDF normalization.
   - [Citation Validation with Instructor - Prevent Hallucinations](https://python.useinstructor.com/examples/exact_citations/) — simple exact-substring quote validation pattern; useful as a baseline, but insufficient for PDF artifacts without offset-mapped canonicalization.
   - [pypdf Extract Text from a PDF](https://pypdf.readthedocs.io/en/stable/user/extract-text.html) — confirms PDF text extraction is representation-sensitive and layout modes affect whitespace/line behavior.
   - [tos-kamiya/pdfhl](https://github.com/tos-kamiya/pdfhl) — relevant examples of tolerant phrase matching for PDF quirks, but MVP validity should remain exact/canonical-offset mapped, not fuzzy.
3. Pydantic v2/test design.
   - [Pydantic Validators documentation](https://pydantic.dev/docs/validation/latest/concepts/validators/) — confirms model validators are the right place for cross-field invariants, with deterministic failures.
   - [Pydantic Custom validators examples](https://pydantic.dev/docs/validation/2.10/examples/custom_validators/) — supports nested/cross-field invariant enforcement patterns used in current IR models.
4. Docling provenance/layout APIs.
   - [DoclingDocument - Docling](https://docling-project-docling.mintlify.app/concepts/docling-document) — DoclingDocument supports hierarchy, furniture/body disambiguation, layout boxes, and provenance.
   - [Chunking - Docling](https://docling-project-docling.mintlify.app/concepts/chunking) — native chunking preserves structure and metadata for RAG/provenance use cases.
   - [docling-core document.py ProvenanceItem](https://github.com/docling-project/docling-core/blob/main/docling_core/types/doc/document.py) — provenance objects include page, bbox, and charspan-like source pointers.

Research confidence: medium-high for design direction. Exact Docling 2.95 runtime API details remain intentionally unverified in the repository (`docling-api-notes.md` is still a TODO scaffold), so Docling implementation confidence is lower until Slice 0 is completed.

## 2. Verdict

**CHANGE** before implementation.

The overall direction is strong: the improved summary plan correctly moves from model-echoed quotes to trusted-code anchoring, rejects model offsets, keeps `DocumentIR.content`/`TextSpan` as the citation source of truth, removes fuzzy matching from validity, and preserves Docling as an adapter rather than an internal model. The current IR/layout model tests are already materially better than typical MVPs.

However, implementation should not start until several narrow plan refinements are made. The main risk is that the plan describes the right target but leaves enough ambiguity that a worker could implement a second string-search validator instead of a source-span/offset anchoring system. Current code also has known traps: `ClaimEvidence` has no offsets, `quote_validator.py` validates by page/cited-span string search, and `_assemble_evidence` silently drops non-exact quotes before validators or reports see them.

## 3. Blockers before implementation

### B1 — Specify anchor ranges against `DocumentIR.content`, not joined span text

Current `SpanIndex.get_text_for_spans()` and `get_page_text()` join span text with synthetic newlines (`ir/span_index.py:41-51`). That is acceptable for chunk display, but it must not be used as the authoritative anchoring substrate. Anchor success must return `char_start`/`char_end` into `DocumentIR.content` and must prove the range is within one cited `TextSpan.char_start..char_end`.

The improved plan says this at a high level (`summary-agent-improved-plan.md:14-18`), but the implementation handoff should explicitly forbid using `SpanIndex.get_text_for_spans()` as the validity search buffer. Otherwise cross-span/newline artifacts can produce ranges that do not exist in `DocumentIR.content`.

### B2 — Resolve multi-span evidence policy before coding

Current `ClaimEvidence` allows multiple `source_span_ids` (`summarization/models.py:62-65`), but the improved plan says `QuoteAnchor` carries a single `span_id` and range contained in a cited span (`summary-agent-improved-plan.md:16-18`). Current tests mark a quote crossing a cited span boundary invalid even when both spans are cited.

Make this invariant explicit:

- MVP should require each evidence quote to anchor within exactly one cited span.
- `source_span_ids` may contain multiple IDs only if they represent contextual citations, but the anchored quote range must be inside one of them.
- If future support for multi-span quotes is needed, it must use ordered segment anchors, not a single `char_start/char_end` spanning separator text.

### B3 — Define ambiguity as fail-closed for MVP

The plan includes `QuoteAnchor.ambiguous` (`summary-agent-improved-plan.md:16`) and `ambiguous_anchor_count` (`summary-agent-improved-plan.md:30`) but does not state whether an ambiguous anchor is valid. For deterministic provenance semantics, ambiguous exact/canonical matches across cited spans must **drop/fail** for MVP unless the ambiguity resolves to the same raw `char_start`/`char_end`.

Recommended rule: `anchor_quote()` returns `AnchorFailure(code="ambiguous_anchor")` when the normalized locator maps to more than one distinct source range. Track it in the run report, but do not mark the claim valid.

### B4 — Current validator/page-scope semantics must be removed, not adapted

Current `quote_validator.py` searches cited spans, then page text, then normalized page text, then fuzzy page text (`validation/quote_validator.py:239-306`). It records `quote_outside_cited_spans`, `normalized_match_only`, and `fuzzy_match` errors (`validation/quote_validator.py:20-29`, `199-228`). This is useful historical test coverage, but it is not the model for the next slice.

Implementation should replace this with offset-integrity verification only:

- cited span IDs exist;
- evidence document matches `SpanIndex.document.document_id`;
- `0 <= char_start < char_end <= len(document.content)`;
- `document.content[char_start:char_end] == evidence.quote`;
- the range is fully contained by the single anchored cited span;
- `anchor_tier` is one of exact/canonical and consistent with assembly output.

No page-scope search. No validity effect from SequenceMatcher. No semantic/fuzzy pass.

### B5 — Canonicalization plan needs exact offset-map invariants

The improved plan correctly calls for matcher-side canonicalization with a lossless offset map and warns that current `normalize_quote_text()` wrongly joins intra-line `well- known` (`summary-agent-improved-plan.md:24-26`; current regex at `quote_validator.py:317-320`). Before implementation, add the exact representation contract:

- `CanonicalText.text` is the canonical string.
- `CanonicalText.source_ranges[i]` maps each canonical character position to a non-empty source range or a separator/fold range that can be converted to a contiguous raw quote range.
- A canonical hit is valid only if its mapped raw range is contiguous and lies inside one cited span.
- Whitespace collapse can map many source characters to one canonical space, but the returned quote is always re-sliced from raw `DocumentIR.content`.
- Canonicalization version must be included in replay/eval metadata; do not mutate `DocumentIR.content`.

### B6 — `ClaimEvidence` offsets need Pydantic invariants, not only validator checks

The plan says `ClaimEvidence` gains `char_start`, `char_end`, and `anchor_tier` (`summary-agent-improved-plan.md:17`) but cannot enforce `quote == content[...]` in the model without the document. Still, it can enforce structural invariants locally:

- `char_start >= 0`, `char_end > char_start`;
- `anchor_tier in {"exact", "canonical"}`;
- `quote` non-blank and preserved verbatim;
- all source span/chunk IDs belong to one document and source span pages equal `page_number` (current behavior retained);
- no validation-status mutation inside the evidence model.

Document-dependent invariants belong in `validate_claim_quotes()` / `validate_claim_grounding()`.

### B7 — Run report conservation must account for claim-level vs evidence-level drops

`_assemble_claim()` currently returns `None` on the first unassembled evidence (`chunk_summarizer.py:217-227`) and `_assemble_evidence()` silently returns `None` when the quote is not an exact substring (`chunk_summarizer.py:242-253`). The improved plan correctly identifies this (`summary-agent-improved-plan.md:22`, `28-30`).

Before coding, define counting semantics:

- `claims_proposed`: generated claim objects received from the structured generator.
- `evidence_proposed`: generated evidence objects received.
- `claims_anchored`: claims for which all evidence anchors pass.
- `claims_valid`: claims that pass citation + quote validators.
- `drops`: one record per dropped claim, with nested evidence failure detail if multiple evidence objects failed.
- Conservation: `claims_proposed == claims_valid + len(drops)`.

Without this, multi-evidence claims can make telemetry misleading.

### B8 — Complete Docling Slice 0 before any fake-based mapper implementation

`docling-api-notes.md` explicitly says runtime discovery has not been completed and all version/API fields remain TODO (`docling-api-notes.md:5-24`, `53-62`, `72-120`). The adapter plan is correct to require discovery first (`docling-adapter-plan.md:46-55`, `122-180`, `416-424`). This is a hard blocker for Docling implementation.

Do not let fake Docling-like objects become the source of truth. The first executable slice must inspect installed `docling==2.95.0`, fill API notes, and only then align fakes to the discovered shape.

## 4. Prioritized improvement opportunities

### P0 — Narrow the next implementation slice to anchoring + evidence model + deterministic tests

Do not combine Docling, live providers, eval judge, API surface, or layout-aware chunking with quote anchoring. The next safe slice is:

1. Add `text/canonical.py` with offset-mapped canonicalization.
2. Add `validation/anchoring.py` with `anchor_quote()`.
3. Add `char_start`, `char_end`, `anchor_tier` to `ClaimEvidence`.
4. Wire `_assemble_evidence()` to anchor inside cited allowed spans and re-slice raw quote.
5. Replace quote validator with offset-integrity re-verification.
6. Add `GroundingRunReport` only where needed to expose drops.
7. Update tests and remove old normalized/fuzzy-validity taxonomy.

### P1 — Keep canonical matching deterministic and explainable

Canonical matching is allowed only if it produces a raw source range. Treat it as a deterministic transform, not fuzzy semantics. The current `SequenceMatcher` code (`quote_validator.py:324-340`) should move, if retained at all, into drop diagnostics with no validity effect.

### P1 — Add an explicit source-span containment helper

Create a small pure helper, for example:

```python
def range_within_span(*, char_start: int, char_end: int, span: TextSpan) -> bool: ...
```

Use it in both anchoring and quote validation. This prevents subtly different containment logic in assembly and re-validation.

### P1 — Add result objects with machine-stable error codes

Avoid returning `None` from `anchor_quote()` or `_assemble_evidence()`. Use typed failures:

- `invalid_span_id`
- `quote_not_found`
- `ambiguous_anchor`
- `canonical_non_contiguous_range`
- `range_outside_cited_spans`
- `document_mismatch`

These codes should be the report/eval taxonomy and the test assertions.

### P2 — Refine Docling parser provenance before mapper work

The Docling plan stores operational facts in `ParserRun.warnings` (`docling-adapter-plan.md:328-341`). That is acceptable for the first adapter, but parser behavior facts such as OCR disabled, remote disabled, artifact path, and Docling component versions are not warnings. Consider a later `ParserRun.metadata: dict[str, str]` only after the current slice; do not block anchoring on this.

### P2 — Add one architecture guard for provider imports when integration work begins

The improved plan already calls for provider SDKs/PydanticAI to stay outside `exeboard-ai` (`summary-agent-improved-plan.md:36-39`). Add a test when that package exists. This is not a blocker for the grounding slice.

## 5. Recommended API/model shape

### Evidence model

```python
AnchorTier = Literal["exact", "canonical"]

class ClaimEvidence(BaseModel):
    quote: str
    page_number: int
    source_span_ids: tuple[SpanId, ...]
    source_chunk_ids: tuple[ChunkId, ...]
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)
    anchor_tier: AnchorTier
```

Model validator additions:

- `char_end > char_start`;
- `source_span_ids` and `source_chunk_ids` non-empty/unique;
- all IDs same document;
- all source span page numbers equal `page_number`.

Document-level validator additions in `validate_claim_quotes()`:

- document ID matches;
- all span IDs exist;
- exactly one cited span contains `char_start..char_end`;
- `document.content[char_start:char_end] == quote`;
- containing span ID is present in `source_span_ids`.

### Anchoring module

```python
AnchorTier = Literal["exact", "canonical"]
AnchorFailureCode = Literal[
    "invalid_span_id",
    "quote_not_found",
    "ambiguous_anchor",
    "canonical_non_contiguous_range",
    "range_outside_cited_spans",
]

class QuoteAnchor(BaseModel):
    span_id: SpanId
    char_start: int
    char_end: int
    tier: AnchorTier

class AnchorFailure(BaseModel):
    code: AnchorFailureCode
    message: str
    candidate_count: int = 0

def anchor_quote(*, quote: str, cited_spans: tuple[TextSpan, ...], content: str) -> QuoteAnchor | AnchorFailure: ...
```

Do not include `ambiguous: bool` on a successful anchor for MVP. Ambiguity should be a failure to avoid false provenance.

### Run report

```python
class DroppedClaimRecord(BaseModel):
    claim_index: int
    stage: Literal["assembly_anchor", "citation_validation", "quote_validation"]
    error_codes: tuple[str, ...]
    generated_claim: str | None = None
    generated_quotes: tuple[str, ...] = ()
    near_miss_tier: Literal["exact_page", "canonical_page", "fuzzy_diagnostic", "none"] | None = None

class GroundingRunReport(BaseModel):
    claims_proposed: int
    claims_anchored: int
    claims_valid: int
    drops: tuple[DroppedClaimRecord, ...]
    counts_by_error_code: dict[str, int]
    ambiguous_anchor_count: int = 0
```

Add a model validator for `claims_proposed == claims_valid + len(drops)`.

## 6. Matching policy recommendation

1. **Generated quote is a locator only.** Never store model-emitted quote as authoritative evidence text.
2. **Search only cited spans.** Do not search page text for validity.
3. **Exact tier first.** Find exact substring inside raw `DocumentIR.content` ranges for cited spans.
4. **Canonical tier second.** Use versioned, offset-mapped canonicalization only when exact fails. A canonical hit must map back to one contiguous raw source range inside one cited span.
5. **Re-slice raw quote.** Store `ClaimEvidence.quote = document.content[char_start:char_end]`.
6. **Ambiguity fails closed.** More than one distinct source range is `ambiguous_anchor`, not valid.
7. **Fuzzy is telemetry only.** SequenceMatcher or semantic similarity cannot make a citation valid.
8. **No cross-span quote for MVP.** If the locator spans two `TextSpan`s, drop it unless future segmented anchors are explicitly designed.
9. **PDF artifacts are explicit transforms.** Handle NFKC, soft hyphen, newline-only dehyphenation, explicit punctuation folding, and whitespace collapse with golden tests.

## 7. Required tests

### Anchoring/canonicalization unit tests

- exact quote anchors within a cited span and returns raw `char_start`/`char_end`.
- exact quote present on same page but outside cited span fails `quote_not_found` or `range_outside_cited_spans` without page-scope acceptance.
- quote crossing two cited spans fails for MVP.
- duplicate occurrence in two cited spans fails `ambiguous_anchor`.
- duplicate occurrence within the same cited span at different offsets fails `ambiguous_anchor`.
- canonical whitespace collapse maps to a contiguous raw range and stores raw re-sliced quote.
- newline-only dehyphenation recovers `multi-\n year` but does **not** join intra-line `well- known`.
- soft-hyphen removal recovers canonical match and maps source offsets correctly.
- curly quotes/dashes/NBSP fold only through explicit versioned table.
- ligature/NFKC case has expected offset mapping.
- canonical hit whose source map is non-contiguous fails `canonical_non_contiguous_range`.
- canonicalization is idempotent and version-pinned with a golden fixture.

### Evidence/Pydantic invariant tests

- `ClaimEvidence` rejects `char_end <= char_start`.
- `ClaimEvidence` rejects unknown `anchor_tier`.
- source IDs remain non-empty/unique and same-document.
- span page must equal `page_number`.
- `SummaryClaim` still rejects evidence from another document.
- old evidence payloads without offsets fail if no compatibility shim is intended.

### Quote validator tests

- valid anchored evidence passes only when `quote == document.content[char_start:char_end]`.
- tampered quote with same offsets fails `quote_not_found` or `quote_text_mismatch`.
- tampered offsets with same quote fail range/quote mismatch.
- range outside cited span fails `range_outside_cited_spans`.
- invalid span ID fails `invalid_span_id`.
- document mismatch fails `document_mismatch`.
- no `normalized_match_only`, `fuzzy_match`, `QuoteMatchType`, `QuoteMatchScope`, or page-scope result remains in public validator API.

### Assembly/reporting tests

- `_assemble_evidence()` re-slices raw quote from `DocumentIR.content` rather than preserving model whitespace.
- generated quote that only canonical-matches is anchored and marked `anchor_tier="canonical"`.
- generated quote that does not anchor creates a `DroppedClaimRecord`, not a silent `None`.
- multi-evidence claim with one failed evidence drops the claim once and records failing evidence details.
- report conservation invariant: `claims_proposed == claims_valid + len(drops)`.
- counts by error code are deterministic.

### Docling/layout tests before adapter acceptance

Retain the current plan's fake/unit tests, but gate them on completed Slice 0 discovery:

- fakes mirror `doc.iterate_items()` tuple shape and discovered `TextItem`, `TableItem`, `PictureItem`, and provenance fields.
- no test imports Docling unless env-gated integration.
- missing dependency maps to `ParserDependencyError`.
- default converter has OCR and remote services disabled or fails implementation.
- text-bearing layout blocks cite existing spans.
- table cells have source spans or visual regions.
- visual-only figures have bounding regions and no fake spans.
- invalid geometry maps to `LayoutExtractionError`.
- span alignment failures map to `SpanAlignmentError`.
- serialized IR contains no Docling-native objects.

## 8. Exact test gates

For the next grounding/validation implementation slice, require all of:

```bash
uv run python scripts/check_workspace.py
uv run --package exeboard-ai --with pytest pytest \
  tests/unit/document_intelligence/test_quote_validator.py \
  tests/unit/document_intelligence/test_aggregate_validator.py \
  tests/unit/document_intelligence/test_chunk_summarizer.py \
  tests/unit/document_intelligence/test_summary_models.py \
  tests/unit/document_intelligence/test_ir_models.py \
  tests/unit/document_intelligence/test_span_index.py
uv run --package exeboard-ai --with pytest pytest tests/unit/document_intelligence
uv run --with pyright --with pytest pyright packages/exeboard-ai/src/exeboard_ai/document_intelligence tests/unit/document_intelligence
```

If Docling adapter work is included later, add:

```bash
uv run --package exeboard-ai --with pytest pytest \
  tests/unit/document_intelligence/test_layout_models.py \
  tests/unit/document_intelligence/test_parser_ports.py \
  tests/unit/document_intelligence/test_docling_parser.py
EXEBOARD_RUN_DOCLING_INTEGRATION=1 uv run --package exeboard-ai --extra docling --with pytest pytest \
  tests/integration/document_intelligence/test_docling_parser.py
```

The Docling integration command must be opt-in and skipped by default in CI unless artifacts/dependencies are explicitly provisioned.

Commands actually run during this review:

```bash
uv run --package exeboard-ai --with pytest pytest tests/unit/document_intelligence/test_quote_validator.py tests/unit/document_intelligence/test_aggregate_validator.py tests/unit/document_intelligence/test_layout_models.py tests/unit/document_intelligence/test_ir_models.py tests/unit/document_intelligence/test_chunk_summarizer.py
# 117 passed in 0.12s

uv run --with pyright pyright packages/exeboard-ai/src/exeboard_ai/document_intelligence tests/unit/document_intelligence
# failed: pytest import not resolved in pyright environment

uv run --with pyright --with pytest pyright packages/exeboard-ai/src/exeboard_ai/document_intelligence tests/unit/document_intelligence
# 0 errors, 0 warnings, 0 informations
```

## 9. Deferred/future concerns

- Entailment/judge validation should remain eval-only, not runtime, as the plan says.
- Layout-aware chunking is useful but should wait until Docling provenance is real and the grounding slice is stable.
- OCR, table interpretation, Q&A, API/UI, database, worker queues, Temporal, and real provider integration are out of scope for this review's recommended next implementation.
- Parser-run structured metadata may be worth adding later, but do not widen the anchoring slice for it.
- Cross-span/segmented evidence could be useful for paragraph wraps and tables, but it must be a separate design with segment-level provenance.

## 10. Naming/layout refinements

- Prefer `validation/anchoring.py` for quote anchoring and `text/canonical.py` for canonicalization.
- Prefer `AnchorTier = Literal["exact", "canonical"]`; do not expose `fuzzy` as a tier.
- Rename `quote_outside_cited_spans` to `range_outside_cited_spans` only once offsets exist.
- Prefer `AnchorFailure(code="ambiguous_anchor")` over successful `QuoteAnchor(ambiguous=True)`.
- Use `GroundingRunReport` and `DroppedClaimRecord` exactly as typed domain/reporting models, not logging side effects.
- Keep Docling adapter under `parsing/adapters/docling.py`; keep mapper helpers pure and import Docling lazily only in adapter construction.

## 11. Acceptance report

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "Reviewed only the requested plans/code/tests and wrote findings to deep-research/validation-grounding-plan-review.md; no code or plan files were modified."
    },
    {
      "id": "criterion-2",
      "status": "satisfied",
      "evidence": "Report includes fresh research sources, verdict, blockers, prioritized improvements, API/model shape, matching policy, required tests, exact gates, commands run, and residual risks."
    }
  ],
  "changedFiles": [
    "deep-research/validation-grounding-plan-review.md"
  ],
  "testsAddedOrUpdated": [],
  "commandsRun": [
    {
      "command": "web_search with 4 queries covering grounded RAG/citation validation, Python quote normalization/PDF artifacts, Pydantic v2 validators/tests, and Docling provenance/layout APIs",
      "result": "passed",
      "summary": "Fresh sources cited in section 1."
    },
    {
      "command": "uv run --package exeboard-ai --with pytest pytest tests/unit/document_intelligence/test_quote_validator.py tests/unit/document_intelligence/test_aggregate_validator.py tests/unit/document_intelligence/test_layout_models.py tests/unit/document_intelligence/test_ir_models.py tests/unit/document_intelligence/test_chunk_summarizer.py",
      "result": "passed",
      "summary": "117 passed in 0.12s."
    },
    {
      "command": "uv run --with pyright pyright packages/exeboard-ai/src/exeboard_ai/document_intelligence tests/unit/document_intelligence",
      "result": "failed",
      "summary": "11 reportMissingImports errors for pytest because pytest was not installed in that pyright uv environment."
    },
    {
      "command": "uv run --with pyright --with pytest pyright packages/exeboard-ai/src/exeboard_ai/document_intelligence tests/unit/document_intelligence",
      "result": "passed",
      "summary": "0 errors, 0 warnings, 0 informations."
    },
    {
      "command": "git diff --cached --quiet; echo cached_exit=$?",
      "result": "passed",
      "summary": "cached_exit=0; no staged files."
    },
    {
      "command": "git status --short deep-research/validation-grounding-plan-review.md",
      "result": "passed",
      "summary": "Report file is untracked and not staged."
    }
  ],
  "validationOutput": [
    "Focused pytest gate: 117 passed in 0.12s.",
    "Pyright with pytest available: 0 errors, 0 warnings, 0 informations."
  ],
  "residualRisks": [
    "Docling 2.95 runtime API discovery remains incomplete in docs/document-intelligence/docling-api-notes.md, so Docling implementation must not start from fakes alone.",
    "This was a review-only task; no tests were added or updated.",
    "Full workspace checks were not run beyond the focused pytest and pyright commands listed.",
    "Repository has many pre-existing unstaged/untracked files outside this task; this task did not stage files, and the review report remains untracked."
  ],
  "noStagedFiles": true,
  "notes": "Verdict: CHANGE before implementation. Primary blockers are offset/source-span anchoring specificity, ambiguity fail-closed semantics, canonical offset-map invariants, and Docling Slice 0 completion. git diff --cached confirmed no staged files; the report file is untracked."
}
```
