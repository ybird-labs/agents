# Evidence-backed summary pipeline

MVP flow:

```text
PDF path
  -> DocumentParser
  -> DocumentIR / SpanIndex
  -> span-preserving chunks
  -> chunk-level generated claims
  -> citation validation
  -> quote validation
  -> aggregate grounding validation
  -> final summary from valid claims only
```

Rules:

- The LLM proposes claim text, role, importance, quote, page number, and source span IDs only.
- Trusted code assigns claim IDs, chunk IDs, validation status, and final-summary lineage.
- Citation validation checks that cited span IDs exist and pages/documents match.
- Quote validation checks exact quote support separately. Normalized-only and fuzzy matches are explicit warnings/errors and are not fully valid in the MVP.
- Aggregate validation marks a claim valid only when citation and quote validation both pass.
- `DocumentSummary` is a final-summary model: it rejects unvalidated or invalid claims.
- Provider SDKs, apps, workers, databases, UI, and OCR are outside this MVP component.
