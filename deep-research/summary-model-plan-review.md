# Document-intelligence summary model/plan review

Date: 2026-06-21
Reviewer role: evidence-backed summary schema / grounded-claim / provenance reviewer
Verdict: **CHANGE**

## 1. Research performed

Fresh web research was performed before review, using these queries:

1. `2025 evidence-backed summarization fine-grained attribution exact source spans citations quote provenance best practices`
2. `LLM summarization citation faithfulness attribution correctness evidence selection verification recent research`
3. `Pydantic v2 structured outputs schema validation LLM required fields validators best practices`
4. `document intelligence provenance schema page bounding box charspan Docling DocuDevs PullCite source grounding`

External sources relied on:

- [Attribution, Citation, and Quotation: A Survey of Evidence-based Text Generation with Large Language Models](https://arxiv.org/html/2508.15396v1) — frames evidence-backed generation around traceable attribution/citation/quotation.
- [Unstructured Evidence Attribution for Long Context Query Focused Summarization](https://arxiv.org/html/2502.14409v2) — supports extracting localized evidence spans for long-context summaries.
- [Correctness is not Faithfulness in Retrieval Augmented Generation Attributions](https://dl.acm.org/doi/10.1145/3731120.3744592) — important distinction: answers can be correct while citations are unfaithful.
- [VeriCite: Towards Reliable Citations in Retrieval-Augmented Generation via Rigorous Verification](https://arxiv.org/html/2510.11394) — supports separating generation/evidence selection/verification rather than trusting citations at generation time.
- [DoclingDocument - Docling](https://docling-project-docling.mintlify.app/concepts/docling-document) and [Docling core `ProvenanceItem`](https://github.com/docling-project/docling-core/blob/main/docling_core/types/doc/document.py) — provenance examples include page number, bounding box, and character span.
- [DocuDevs Source Locations](https://docs.docudevs.ai/docs/core/source-locations) and [PullCite](https://pypi.org/project/pullcite/) — production document extraction examples expose quote + page + bounding-box/source-location artifacts.
- [Pydantic: How to Use Pydantic for LLMs](https://pydantic.dev/articles/llm-intro) — structured AI output should be validated at the schema boundary with explicit runtime validation.

## 2. Verdict

**CHANGE.** The direction is strong and mostly correct: span-addressed context, required evidence, `DocumentIR.content`/`TextSpan` as source of truth, final summaries from valid claims only, provider-agnostic ports, and Pydantic v2 frozen models are the right base.

However, the plans are currently inconsistent with each other and with the implementation in ways that matter for evidence-backed board-pack summaries:

- `summary-agent-improved-plan.md` correctly identifies the need for trusted anchoring, char ranges, canonical offset maps, and run telemetry, but schedules a real-model/user-facing sequence before the current pipeline can truthfully report proposed vs dropped claims.
- `implementation-plan.md`, `summary_pipeline.md`, and `evaluation.md` still describe the pre-anchoring quote model and quote-validator taxonomy.
- Current code still stores `ClaimEvidence` without source character ranges and silently drops generated claims in `_assemble_evidence` before validation/reporting.
- Evaluation documentation treats citation/quote validity as the MVP gate but does not yet make citation faithfulness / claim support a required release gate.
- Board-pack usefulness needs a small model-level adjustment before the schema freezes: the current document types/roles do not represent board packs or decisions-needed well enough.

## 3. Blockers / must-change recommendations

### M1. Align all plans on quote anchoring as the evidence contract

**Problem:** `summary-agent-improved-plan.md` D1 is correct: model quote is a locator; trusted code anchors it to exact `DocumentIR.content` ranges and stores a re-sliced verbatim quote. But `implementation-plan.md` Step 5 still defines `ClaimEvidence` as only `quote`, `page_number`, `source_span_ids`, and `source_chunk_ids`; `summary_pipeline.md` still says quote validation requires exact substring in cited `TextSpan.text`; current `ClaimEvidence` in code has no `char_start`, `char_end`, or `anchor_tier` (`summarization/models.py:56-65`).

**Why this blocks:** Fine-grained provenance requires machine-readable evidence pointers. Page + span IDs are necessary but not sufficient for exact highlighting, ambiguity detection, replay, or validating that the stored quote is the exact source slice.

**Concrete plan text change:** Replace the Step 5 `ClaimEvidence` snippet in `docs/document-intelligence/implementation-plan.md` with:

```python
AnchorTier = Literal["exact", "canonical"]

class ClaimEvidence(BaseModel):
    quote: str  # trusted-code re-slice from DocumentIR.content, not raw model output
    page_number: int
    source_span_ids: tuple[SpanId, ...]
    source_chunk_ids: tuple[ChunkId, ...]
    char_start: int
    char_end: int
    anchor_tier: AnchorTier
    ambiguous_anchor: bool = False
```

Add invariants beneath it:

```text
ClaimEvidence invariants:
- char_start/char_end are offsets into DocumentIR.content.
- quote == DocumentIR.content[char_start:char_end].
- char range is contained by exactly one cited TextSpan range unless ambiguous_anchor=True, in which case the claim is dropped before final summary.
- page_number matches the cited TextSpan page.
- anchor_tier="canonical" is valid only when canonical matching maps losslessly back to raw content offsets; fuzzy matching never validates evidence.
```

Update `docs/document-intelligence/summary_pipeline.md` rule 25 to say quote validation re-verifies the stored source range rather than searching page text.

### M2. Add telemetry before any real-model comparison or user-facing demo

**Problem:** The improved plan says the current grounding pipeline is "done enough" (`summary-agent-improved-plan.md:6`) and Slice 1 will log proposed/citation-fail/quote-fail/valid counts (`summary-agent-improved-plan.md:77-81`). Current code cannot do that truthfully: `_assemble_evidence` returns `None` on quote mismatch (`chunk_summarizer.py:252-253`), causing the entire generated claim to disappear before citation/quote validation and before any run report exists. `summarize_document` returns only `DocumentSummary` (`pipeline.py:15-23`), so drops are not externally auditable.

**Why this blocks:** A measurement slice that cannot count all proposed claims will underreport model failures and overstate grounding quality.

**Concrete plan text change:** Insert a Slice 0 before current Slice 1:

```text
### Slice 0 — Grounding observability before real-model measurement (S)
Implement SummarizationRunResult and GroundingRunReport without changing validity rules. Every generated claim proposal receives a proposal_index. Every assembly/anchoring/citation/quote failure becomes a DroppedClaimRecord with stage, chunk_id, source_span_ids when available, error_code, and near_miss_tier. Conservation invariant: claims_proposed == claims_valid + len(drops). Slice 1 real-model tables must be produced from this report, not ad hoc logs.
```

Then change current Slice 1 "Out of scope" to allow this minimal report and remove any implied user-facing use until D1/D3 are complete.

### M3. Remove page-scope/fuzzy quote semantics from the implementation plan and validator roadmap

**Problem:** D1 says page-scope search, fuzzy validity, `QuoteMatchType`, and `QuoteMatchScope` should be deleted (`summary-agent-improved-plan.md:16-20`). But `implementation-plan.md` still says quote validation may check the cited page and classify normalized/fuzzy matches (`implementation-plan.md:538-561`), and current validator code searches page text and uses fuzzy matching (`quote_validator.py:257-340`).

**Why this blocks:** Citation faithfulness means the claim must be grounded in the cited evidence, not merely somewhere on the page. Page-level fallback makes wrong-span citations look less severe and can hide attribution failures.

**Concrete plan text change:** Replace `implementation-plan.md` Step 8 quote section with:

```text
Quote anchoring/validation checks source-range integrity only:
- model-emitted quote is used only as a locator inside cited spans;
- trusted anchoring resolves to DocumentIR.content char_start/char_end;
- stored quote is re-sliced from DocumentIR.content;
- validation rechecks quote == content[char_start:char_end];
- char range must be contained in a cited span and page/document must match;
- normalized/canonical matches are accepted only through lossless offset-mapped canonical anchoring;
- fuzzy matches and page-scope matches are diagnostics for dropped claims, never valid evidence.
```

### M4. Make citation faithfulness / claim support a release gate, not a vague future idea

**Problem:** `evaluation.md` currently says future evals *may* add LLM/NLI support validation and coverage scoring (`evaluation.md:33`). The improved plan has a stronger D6/D8 eval-stage judge and entailment negatives (`summary-agent-improved-plan.md:45-63`), but that has not been propagated.

**Why this blocks:** Research on citation faithfulness shows a claim can be correct but cited to the wrong evidence. Exact quote existence is necessary but not sufficient for board-pack trust.

**Concrete plan text change:** Replace the final sentence of `docs/document-intelligence/evaluation.md` with:

```text
Release gates after the deterministic MVP:
- Citation/quote structural negatives: 100% rejection in CI.
- Positive anchored evidence cases: >= 0.95 acceptance.
- Entailment negatives (negation, entity swap, number swap, wrong evidence for a true claim): deterministic gates must not mark them as citation-faithful; eval-stage judge must catch >= 0.90 before broad reuse.
- Judge support on positives: >= 0.90 after calibration and 10-20 human spot checks per release.
- Real-LLM citation validity on public board-pack fixtures: >= 0.90.
- Gold claim coverage on board-pack fixtures: >= 0.70.
```

Also add `expected_support_verdict` and `support_evidence_rationale` to eval case fields.

### M5. Define board-pack summary usefulness in the model contract before admin demo

**Problem:** Current `DocumentType` lacks `board_pack`, and `generic`/`business_review` do not allow `decision` even though board packets often center on approvals, decisions needed, risks, financial highlights, and open questions (`summarization/models.py:18-54`). The current final summarizer simply emits one sentence per valid claim (`final_summarizer.py:29-36`), which is safe but not a board-useful executive summary.

**Why this blocks:** The component can be grounded and still fail the target user if it cannot distinguish "decision needed" from background findings.

**Concrete plan text change:** Add a narrow board-pack document type and final-summary sections without adding UI/workers:

```python
DocumentType = Literal[..., "board_pack"]
ClaimRole = Literal[..., "decision_needed", "approval_request"]
BoardSummarySection = Literal[
    "decisions_needed",
    "key_risks",
    "financial_highlights",
    "recommended_actions",
    "open_questions",
    "context",
]
```

Rules:

```text
board_pack allowed roles: finding, forecast, risk, recommendation, action_item, decision_needed, approval_request, open_question.
Each SummarySentence has section: BoardSummarySection | None. Section assignment is metadata over valid claims; it must not introduce unsupported prose.
```

## 4. Should-change recommendations

### S1. Preserve validation detail, not only flattened error strings

Current `SummaryClaim.validation_errors` stores only strings (`models.py:118-119`), and `apply_claim_grounding_validation` flattens error codes (`aggregate_validator.py`). Keep the simple status for filtering, but add a typed validation artifact in the run report:

```python
ClaimValidationRecord(
    claim_id: ClaimId,
    citation_result: CitationValidationResult,
    quote_result: QuoteValidationResult,
    validation_status: ValidationStatus,
)
```

Do not stuff provider/model confidence into claims.

### S2. Add proposal lineage for dropped claims

When a generated claim fails assembly/anchoring, no `SummaryClaim` exists. The run report should still preserve `chunk_id`, `proposal_index`, generated claim text, proposed span IDs, proposed quote, error code, and prompt/schema versions. This is necessary to debug model failures and compare providers.

### S3. Make replay keys include canonicalization/anchoring versions

D2 says canonicalization version joins the replay key, but current replay key includes prompt/schema/chunk/span text only (`chunk_summarizer.py:170-183`). Add `CANONICALIZATION_VERSION` and `ANCHORING_VERSION` once D1/D2 land.

### S4. Add bounded final-summary rewrite contract, but keep deterministic fallback

D7 is sensible to defer a generated rewrite. If/when implemented, require:

- every sentence cites existing valid claim IDs;
- numeric tokens in the sentence must appear in supporting claim text or evidence quote;
- no generated section heading/summary sentence without support;
- generator error or failed validation falls back to deterministic claim-as-sentence assembly.

### S5. Clarify span vs bounding-box provenance expectations

`TextSpan` already has `char_start`, `char_end`, and optional `bbox` (`ir/models.py:380-390`), and `DocumentIR` validates span text against content (`ir/models.py:472-481`). The summary docs should state that MVP quote highlighting uses content offsets; span-level bbox is used as a coarse page highlight when available; exact quote bounding boxes are future unless word-level geometry exists.

### S6. Avoid destructive scaffold recommendations in the summary plan

The scaffold deletion list in `summary-agent-improved-plan.md:105-116` is outside this review's schema/model scope. Keep it as a separate architecture ADR if desired; do not let summary schema implementation depend on deleting packages/apps.

## 5. Defer / do not do now

- Do not add OCR, Docling, table extraction, vector stores, Q&A, Temporal workers, auth, databases, or MCP to fix the summary model contract.
- Do not add runtime LLM/NLI judges to `summarize_document`; keep judges eval-stage only as the improved plan says.
- Do not add confidence scores unless their lifecycle and calibration are defined; validation status + evidence support metrics are enough for MVP.
- Do not require exact quote bounding boxes until the parser has word-level or glyph-level geometry; keep char offsets first.
- Do not build a polished generated executive rewrite before grounded deterministic output has been shown to board admins.

## 6. Required model fields and invariants

Minimum corrected model shape:

```python
AnchorTier = Literal["exact", "canonical"]
ValidationStatus = Literal["unvalidated", "valid", "invalid"]

class ClaimEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    quote: str
    page_number: int = Field(ge=1)
    source_span_ids: tuple[SpanId, ...]
    source_chunk_ids: tuple[ChunkId, ...]
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)
    anchor_tier: AnchorTier

class SummaryClaim(BaseModel):
    claim_id: ClaimId
    document_id: DocumentId
    document_type: DocumentType
    claim: str
    claim_role: ClaimRole
    importance: Literal["low", "medium", "high"]
    evidence: tuple[ClaimEvidence, ...]
    derived_from_claim_ids: tuple[ClaimId, ...] = ()
    validation_status: ValidationStatus = "unvalidated"
    validation_errors: tuple[str, ...] = ()

class SummarySentence(BaseModel):
    text: str
    supporting_claim_ids: tuple[ClaimId, ...]
    section: BoardSummarySection | None = None
```

Cross-field invariants:

- `document_id` is a valid UUID; claim/chunk/span IDs parse and belong to `document_id`.
- evidence tuple is non-empty; source spans/chunks are non-empty and unique.
- `char_start < char_end`; resolved quote equals `DocumentIR.content[char_start:char_end]` in anchoring/validation code.
- evidence char range is contained in cited span range(s); page number matches span page.
- `validation_status == "invalid"` iff `validation_errors` is non-empty; `valid` and `unvalidated` have no errors.
- `DocumentSummary.claims` contains only valid claims.
- every `SummarySentence.supporting_claim_ids` is non-empty, unique, belongs to the document, and references an included valid claim.
- run report conservation: `claims_proposed == claims_valid + len(drops)`.

## 7. Tests required

Must add/update tests for the next implementation slice:

1. `ClaimEvidence` rejects missing/blank quote, invalid page, duplicate span/chunk IDs, invalid char range, and cross-document span/chunk IDs.
2. Anchoring exact match re-slices quote from `DocumentIR.content` and stores `char_start`, `char_end`, `anchor_tier="exact"`.
3. Canonical match maps back to raw offsets and stores a verbatim raw quote; no intra-line `well- known` dehyphenation.
4. Ambiguous anchor is dropped or marked invalid and never reaches `DocumentSummary`.
5. Page-scope match and wrong-span same-page match are invalid, even when quote exists elsewhere on the page.
6. Fuzzy match is diagnostic only and cannot make `QuoteValidationResult.valid=True`.
7. Dropped generated claims are represented in `GroundingRunReport` with proposal index and stage.
8. Report conservation invariant holds across assembly/anchoring/citation/quote failures.
9. `evaluation.md` thresholds are represented in a deterministic eval fixture with positives, structural negatives, wrong-evidence true-claim negatives, and entailment negatives.
10. Board-pack role validation permits `decision_needed` / `approval_request` for `board_pack` and rejects them for inappropriate document types.
11. Replay key changes when prompt/schema/canonicalization/anchoring version or allowed span text/page changes.
12. Architecture guard: no provider SDK or `pydantic_ai` import in `exeboard_ai`.

## 8. Quality gates

Keep current gates:

```bash
uv run python scripts/check_workspace.py
uv run --package exeboard-ai --with pytest pytest tests/unit/document_intelligence tests/integration/document_intelligence
uv run --with pyright --with pytest pyright
```

Add release/eval gates when D1-D3/D8 land:

```bash
# proposed command shape; exact module name can vary
uv run --package exeboard-ai pytest tests/unit/document_intelligence/test_anchoring.py tests/unit/document_intelligence/test_summary_run_report.py
uv run --package exeboard-ai python -m exeboard_ai.document_intelligence.evals.run_grounding_eval --dataset evals/datasets/document_intelligence/summary_v1.json --mode deterministic
```

Required thresholds:

- deterministic structural/quote negatives: 100% rejected;
- anchored positive cases: >= 0.95 accepted;
- report conservation: 100%;
- final summary invalid-claim exclusion: 100%;
- real-LLM citation validity on public board-pack fixtures: >= 0.90 before user-facing reuse;
- eval-stage support judge, once introduced: >= 0.90 catch on entailment negatives and >= 0.90 support on positives after human spot-check calibration.

## 9. Validation run during this review

Commands run:

```bash
uv run --package exeboard-ai --with pytest pytest tests/unit/document_intelligence tests/integration/document_intelligence
# 283 passed in 0.71s

uv run python scripts/check_workspace.py
# workspace scaffold valid

uv run --with pyright pyright
# failed: pytest imports unresolved in tests

uv run --with pyright --with pytest pyright
# 0 errors, 0 warnings, 0 informations
```

## 10. Bottom line

Approve the core architecture direction, but update the plans before building more surface area. The highest-leverage change is not a new provider or UI: it is making the evidence object a real provenance pointer (`quote + page + span IDs + DocumentIR char range + anchor tier`) and making every generated proposal auditable, including drops. Once that is in place, board-pack usefulness can be improved safely through roles/sections without weakening grounding.
