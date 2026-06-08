# Document summary evaluation

The MVP evaluation gate is evidence-first. A summary pass is not based only on fluent prose.

## Minimum gold data fields

Each eval case should include:

- `document_id`
- source fixture path or checksum
- document type
- gold claims
- gold evidence quote per claim
- expected trusted page number derived from cited spans
- expected source span IDs when stable
- expected allowed span context (`span_id`, page number, exact `TextSpan.text`) for chunk-level fake-generator requests
- expected validation outcome
- notes for unsupported or ambiguous claims

## MVP pass/fail checks

A run passes only if:

1. The parser produces stable `DocumentIR` spans for the fixture.
2. Every generated final-summary sentence cites an existing valid claim ID.
3. Chunk summary generation receives a typed span-addressed context built from `SpanIndex`; missing chunk spans fail before the fake generator is invoked.
4. Every final-summary claim has valid citation validation.
5. Every final-summary claim has exact quote validation inside the cited `TextSpan.text`, not merely somewhere on the same page or chunk.
6. Unvalidated, invalid, same-page/chunk wrong-span, normalized-only, fuzzy-only, and missing-quote claims are excluded from final summaries.
7. Replay keys are deterministic for equivalent allowed-span ordering and change when prompt/schema/chunk/span text/page context changes.
8. No provider SDK, remote inference, or silent OCR is required for the deterministic fake-LLM eval.

Future evals may add LLM/NLI support validation, coverage scoring, and human review, but deterministic citation and quote gates remain mandatory.
