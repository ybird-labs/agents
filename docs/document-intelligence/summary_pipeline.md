# Evidence-backed summary pipeline

MVP flow:

```text
PDF path
  -> DocumentParser
  -> DocumentIR / SpanIndex
  -> span-preserving chunks
  -> trusted span-addressed chunk context
  -> chunk-level generated claims
  -> citation validation
  -> quote validation
  -> aggregate grounding validation
  -> final summary from valid claims only
```

Rules:

- Trusted code builds a `SpanAddressedChunkContext` before invoking the generator. Each allowed `source_span_id` is adjacent to its exact `TextSpan.text` and page number resolved from `SpanIndex` / `DocumentIR`.
- A chunk that references a missing span fails closed before generator invocation.
- The LLM proposes claim text, role, importance, quote, and source span IDs only. Generated page numbers, claim IDs, chunk IDs, source chunk IDs, lineage, validation status, and other extras are rejected by the schema boundary.
- Trusted code assigns claim IDs, source chunk IDs, page numbers, validation status, and final-summary lineage.
- Citation validation checks that cited span IDs exist and pages/documents match.
- Quote validation requires exact quote support inside cited `TextSpan.text`. Same-page/chunk wrong-span matches, normalized-only matches, fuzzy-only matches, and missing quotes are invalid and excluded from final summaries.
- Aggregate validation marks a claim valid only when citation and quote validation both pass.
- Replay keys include prompt and schema versions/fingerprints, chunk ID/text, and a canonical ordered representation of allowed spans (`span_id`, trusted `page_number`, exact `text`) so prompt/schema/span text/page changes are cache-sensitive while equivalent span ordering is stable.
- `DocumentSummary` is a final-summary model: it rejects unvalidated or invalid claims.
- Provider SDKs, apps, workers, databases, UI, and OCR are outside this MVP component.
