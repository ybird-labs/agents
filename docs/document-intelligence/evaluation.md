# Document summary evaluation

The MVP evaluation gate is evidence-first. A summary pass is not based only on fluent prose.

## Minimum gold data fields

Each eval case should include:

- `document_id`
- source fixture path or checksum
- document type
- gold claims
- gold evidence quote per claim
- expected page number
- expected source span IDs when stable
- expected validation outcome
- notes for unsupported or ambiguous claims

## MVP pass/fail checks

A run passes only if:

1. The parser produces stable `DocumentIR` spans for the fixture.
2. Every generated final-summary sentence cites an existing valid claim ID.
3. Every final-summary claim has valid citation validation.
4. Every final-summary claim has exact quote validation.
5. Unvalidated, invalid, normalized-only, fuzzy-only, and missing-quote claims are excluded from final summaries.
6. No provider SDK, remote inference, or silent OCR is required for the deterministic fake-LLM eval.

Future evals may add LLM/NLI support validation, coverage scoring, and human review, but deterministic citation and quote gates remain mandatory.
