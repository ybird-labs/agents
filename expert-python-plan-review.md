# Expert Python Plan Review: Document Intelligence Agent

## 1. Verdict

**Proceed only after narrowing MVP and making several architecture decisions.** The plan is directionally strong: it has the right high-level pipeline, emphasizes canonical IR and evidence-backed outputs, and includes evaluation from the start. However, it is currently too broad for a first implementation and leaves important production decisions unresolved: IR contract/versioning, parser/OCR failure modes, retrieval quality controls, citation validation semantics, async job orchestration, storage layout, security, and deployment constraints.

A feasible MVP is: **single-document, PDF-only, mostly digital PDFs, expert Q&A with answer citations and quote validation**. Complex table extraction, OCR-heavy documents, multi-document reasoning, broad schemas, full human review UI, and high recall fact extraction should be deferred.

## 2. Strongest Parts

- **Correct pipeline shape:** upload → classify → parse/OCR → canonical IR → index/retrieve → task layer → validation → cited output → human review is the right separation of concerns.
- **Canonical IR is the right core abstraction:** requiring all downstream answers to cite IR spans reduces parser/vendor lock-in and makes validation/evaluation possible.
- **Hybrid retrieval is appropriate:** combining lexical search with vector retrieval is the right default for legal/financial/technical PDFs where exact terms matter.
- **Evidence-backed output is treated as a first-class requirement:** answer, evidence quotes, confidence, limitations, and human-review flags are good product primitives.
- **Evaluation is included early:** the proposed gold set and metrics are directionally useful and better than relying on qualitative demos.
- **MVP exclusions are mostly correct:** deferring complex tables, many document types, human review UI, fine-tuning, and multi-document reasoning reduces delivery risk.

## 3. Blockers / Missing Decisions

### A. Canonical IR is underspecified
Before implementation, decide:

- Stable ID format for `document_id`, `page_id`, `block_id`, `span_id`, `table_id`, `cell_id`, `chunk_id`.
- Coordinate system: page units, origin, rotation handling, normalized vs PDF coordinates.
- Text normalization policy: whitespace, hyphenation, ligatures, headers/footers, OCR artifacts.
- Span-to-page and span-to-bbox mapping guarantees.
- IR versioning and migration strategy.
- Parser provenance fields: parser name/version, confidence, warnings, fallback path.

Without this, citations, quote validation, regression testing, and parser fallback comparison will become fragile.

### B. Parser/OCR strategy needs operational validation
Docling + PyMuPDF + pdfplumber + OCRmyPDF is plausible, but the plan does not yet address:

- Native dependencies: Tesseract, Ghostscript, Poppler-like tooling, system packages, Docker image size.
- Runtime and memory costs for large PDFs.
- Bad PDF handling: encrypted files, corrupted files, rotated pages, mixed scanned/digital pages, embedded images, forms, annotations.
- Parser disagreement policy: which parser wins when text/page order/table output differs?
- OCR confidence and language support.

Run a parser bakeoff on the 20-doc seed set before locking the IR and MVP timeline.

### C. Retrieval quality controls are incomplete
The plan names keyword + vector retrieval but does not define:

- Embedding model choice and dimensionality.
- Chunk sizes/overlap by content type.
- Whether retrieval uses sections, pages, layout blocks, tables, or all of them.
- Reranking strategy.
- Maximum evidence budget passed to the LLM.
- Query rewriting policy.
- How retrieval recall is measured independently from answer quality.

For evidence-backed Q&A, retrieval recall is usually the dominant failure mode.

### D. Citation/evidence validation is underdefined
“Evidence quote found >95%” is a good metric, but the system must define:

- Whether exact quote match is required or fuzzy match is allowed.
- How quote offsets map back to IR spans and bboxes.
- Whether the cited evidence actually entails the claim, not merely contains overlapping words.
- How to handle synthesized answers requiring multiple evidence spans.
- What happens when evidence is missing: refuse, answer with limitations, or route to human review.

Quote existence is necessary but not sufficient for factual grounding.

### E. Human-review workflow is deferred too late
A full UI can wait, but **review states and audit trail should be designed early**:

- `needs_review`, `review_reason`, `review_status`, `reviewer_decision`, timestamps.
- Versioned model output and evidence snapshots.
- Ability to mark an answer/fact as accepted, corrected, or rejected.

If this is added only in Phase 7, earlier schemas and APIs may need rework.

### F. Evaluation set may be too broad for MVP
The 20-doc gold set spans contracts, invoices, financial/table-heavy PDFs, and scientific PDFs. That is valuable for roadmap evaluation, but too broad for a first MVP if the MVP is expert Q&A. Split into:

- MVP acceptance set: 10–20 representative digital PDFs for Q&A.
- Stress/regression set: scanned PDFs, table-heavy PDFs, scientific layouts, invoices.
- Future extraction set: schema-specific labels.

### G. Production readiness requirements are missing
Add decisions for:

- File security: malware scanning, MIME sniffing, file size/page limits, encrypted PDFs.
- Tenant isolation and authorization.
- PII/secrets handling and data retention.
- Object storage layout and checksum/dedup behavior.
- Async job retry/idempotency.
- Observability: parse/index/LLM traces, cost, latency, failure reason taxonomy.
- Rate limits and backpressure.

## 4. Python Implementation Recommendations

### Core stack
- **API:** FastAPI + Pydantic v2.
- **Database:** PostgreSQL for metadata, IR references, jobs, evaluations; `pgvector` if using Postgres-native vector search.
- **Object storage:** S3-compatible storage or local MinIO for originals, parser artifacts, IR JSON, extracted page images.
- **Workers:** Prefer **Temporal** if workflows need durable retries, long OCR jobs, and resumability. Use Celery/RQ only if operational simplicity is more important than workflow durability.
- **Parsing:** Start with Docling and PyMuPDF. Use pdfplumber only for targeted table/text comparison, not as a third equal parser path in MVP.
- **OCR:** OCRmyPDF is fine for initial searchable-PDF conversion, but validate bbox/text quality early. Do not promise robust OCR extraction until tested.
- **LLM structured output:** Use provider-native structured outputs where possible. Instructor/Pydantic is useful, but still validate and persist raw model responses.

### Data model recommendations
Implement these as explicit versioned models:

- `DocumentRecord`: id, checksum, MIME, size, page count, status, storage URI, timestamps.
- `ParseRun`: parser, parser version, started/finished, status, warnings, artifact URIs.
- `DocumentIR`: schema version, pages, blocks, spans, tables, figures, parser metadata.
- `Chunk`: id, document id, text, chunk type, source span IDs, page numbers, bbox refs.
- `RetrievalResult`: query, chunk IDs, scores, retriever type, reranker score.
- `Answer`: answer text, citations, evidence quotes, confidence, limitations, review flag.

### Retrieval recommendations
- Start with PostgreSQL full-text search + pgvector if operational simplicity matters.
- Add a cross-encoder/reranker only after measuring recall/precision on the gold set.
- Build retrieval eval before agent eval: top-k contains answer evidence, MRR, and recall by question type.
- Keep page-level chunks as fallback, but prefer paragraph/section chunks for answer generation.

### Validation recommendations
- Separate validators:
  - schema validator: output shape and types;
  - quote validator: cited quote appears in source span/page text;
  - citation validator: citation IDs exist and point to valid IR objects;
  - support validator: optional LLM/NLI judge to test whether evidence supports the answer;
  - business validator: domain-specific rules.
- Always store validation failures as structured reasons, not only booleans.

### Testing recommendations
- Unit tests for IR normalization, chunk-source mapping, quote matching, citation validation.
- Golden tests for parser output stability on a small fixture set.
- Retrieval eval independent from LLM generation.
- End-to-end tests with fixed documents and deterministic expected evidence IDs where possible.
- Use regression snapshots carefully; parser upgrades may change span IDs unless IR ID strategy is stable.

## 5. Revised Phase Plan

### Phase 0 — Architecture spike and acceptance criteria
- Run parser bakeoff on the 20 seed docs.
- Define IR v0.1 and citation semantics.
- Choose storage layout, job runner, embedding model, and vector store.
- Define MVP metrics and failure states.

### Phase 1 — Intake, storage, and async processing
- Upload PDF with checksum, MIME sniffing, size/page limits.
- Store original file and metadata.
- Create parse/index job state machine with idempotent retries.

### Phase 2 — Parsing and IR v0.1
- Integrate Docling primary and PyMuPDF fallback.
- Normalize pages, blocks, spans, text, bboxes, parser metadata.
- Persist IR artifact and parse warnings.
- Add parser regression fixtures.

### Phase 3 — Chunking and retrieval evaluation
- Generate chunks with source span/page mappings.
- Implement lexical + vector retrieval.
- Add retrieval metrics: top-k evidence recall, MRR, latency.

### Phase 4 — Evidence-backed expert Q&A MVP
- Define Q&A response schema.
- Implement answer generation with retrieved evidence only.
- Add quote/citation validator.
- Add refusal/limitations behavior for insufficient evidence.

### Phase 5 — MVP evaluation and hardening
- Run Q&A gold set.
- Measure unsupported answer rate, citation validity, retrieval recall, cost, latency.
- Add observability, error taxonomy, and basic review flags.

### Phase 6 — Evidence-backed summarization
- Add claim-level summaries with citations.
- Validate claim evidence separately from Q&A.

### Phase 7 — Structured fact extraction
- Start with one narrow schema, not many.
- Add raw/normalized value, evidence quote, page/span, confidence, validation reasons.

### Phase 8 — Tables/OCR/human-review expansion
- Harden table extraction only after measuring table failure modes.
- Add PaddleOCR/Surya/GROBID/Camelot only for proven gaps.
- Build full human review UI/workflow after review data model already exists.

### Phase 9 — Production monitoring and regression
- Add dashboards for parse failures, retrieval recall proxies, unsupported answer rate, cost/page, latency/page.
- Add versioned eval runs and parser/model upgrade gates.

## 6. MVP Cut Line

### Include in MVP
- PDF upload only.
- Single-document processing only.
- Mostly digital PDFs; OCR allowed as best-effort, not guaranteed.
- Docling primary parser and PyMuPDF fallback.
- Canonical IR v0.1 with pages, blocks, spans, bboxes, parser metadata.
- Chunking with source span/page mappings.
- Hybrid retrieval.
- Expert Q&A only.
- Answer schema: answer, citations, quotes, confidence, limitations, review flag.
- Quote/citation validator.
- Basic evaluation set focused on Q&A.
- Basic job status and failure reporting.

### Exclude from MVP
- Complex table extraction guarantees.
- Structured extraction across many schemas.
- Full evidence-backed summarization if it delays Q&A quality.
- Multi-document reasoning.
- Full human review UI.
- Fine-tuning.
- Broad OCR/language guarantees.
- Scientific-layout/table-heavy accuracy promises.

## 7. Risks to Test Early

1. **Parser quality risk:** Docling/PyMuPDF may produce unstable reading order, broken tables, or poor span mappings on real PDFs.
2. **Citation fragility:** answer quotes may not exactly match normalized IR text unless normalization and fuzzy matching are designed carefully.
3. **Retrieval recall risk:** good answers are impossible if the right evidence is not in top-k context.
4. **OCR cost/latency risk:** OCRmyPDF can be slow and operationally heavy for large/scanned PDFs.
5. **Table-heavy document risk:** cell-level facts and financial statements will likely fail without table-specific extraction and validation.
6. **Evaluation ambiguity:** labeling summaries, Q&A, and facts across four document classes may create inconsistent gold data unless annotation guidelines are written.
7. **LLM support risk:** quote existence does not prove the cited evidence supports the answer.
8. **Workflow durability risk:** long parse/OCR/index jobs need retries, resumability, and idempotency from the start.
9. **Security/compliance risk:** document upload systems need malware scanning, access control, retention policy, and PII handling before production.
10. **Scope creep risk:** summarization, Q&A, extraction, validation, tables, and review workflow are each substantial products; MVP should validate one path first.

## Final Recommendation

Approve the plan only after revising it around a narrower MVP and adding explicit decisions for IR v0.1, citation semantics, parser fallback policy, retrieval evaluation, async job orchestration, storage, and security. The first implementation milestone should prove: **given a digital PDF, the system can parse it into stable IR, retrieve the correct evidence, answer expert questions using only that evidence, and validate that cited quotes map back to source spans.**
