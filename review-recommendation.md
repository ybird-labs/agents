## Review

- Correct: The recommendation is technically sound at the architectural level. It aligns with the repo’s broader platform guidance in `project_research.md`: use workflows/orchestration as the control plane, keep tools bounded, require typed contracts, provenance, validation, security, and observability rather than letting agents freely manipulate systems. For spreadsheets, reusing mature parsing/tooling while owning orchestration, semantic modeling, validation, provenance, UX, and security is the right default because spreadsheet correctness depends more on deterministic data handling and auditability than on LLM reasoning alone.

- Correct: “Do not build from scratch” is especially valid for low-level spreadsheet ingestion/parsing. XLSX/CSV/ODS handling has many edge cases: merged cells, hidden rows/sheets, formulas vs cached values, external links, pivot tables, charts, comments, data validation, locale-specific numbers/dates, encodings, malformed files, password protection, macros, and very large workbooks. Existing parsers/tool layers reduce avoidable implementation risk.

- Note: The recommendation should not imply that LlamaSheets/Reducto/spreadsheet-mcp are interchangeable. They occupy different positions on the spectrum: managed extraction/API products can accelerate ingestion and OCR-like document understanding, while MCP/OSS tools mainly standardize local tool invocation. The decision should be based on file types, privacy constraints, deployment model, latency/cost, provenance quality, formula fidelity, scale limits, licensing, and operational maturity.

- Note: Missing options to evaluate before committing:
  - Direct deterministic libraries: Python `openpyxl`, `calamine`/`python-calamine`, `pyxlsb`, `xlrd` for legacy XLS, `odfpy`, Apache POI if JVM is acceptable.
  - Dataframe/query engines: Polars, DuckDB, Pandas, Ibis, SQLite for smaller/local workloads, Arrow/Parquet as an intermediate representation.
  - Spreadsheet execution/formula engines: LibreOffice headless, Gnumeric, Excel/Graph API/Office Scripts where exact Excel semantics matter, or specialized formula evaluators with explicit coverage limits.
  - Enterprise integrations: Microsoft Graph/SharePoint/OneDrive, Google Sheets API, Box/Drive connectors, S3/object storage ingestion.
  - Document AI/OCR paths for scanned tables or PDFs masquerading as spreadsheets.

- Note: Important incorrect or risky assumption: DuckDB/Pandas are not a complete spreadsheet runtime. They are strong for tabular analysis after extraction, but they do not preserve all workbook semantics: formulas, formatting-as-data, merged-cell headers, cross-sheet references, named ranges, pivot caches, charts, solver/scenario features, macros, data validation, comments, and user intent encoded in layout. A semantic layer must explicitly define what is supported, what is ignored, and when to escalate to an Excel-compatible engine or human review.

- Note: Semantic-layer design is the critical product differentiator and should be specified, not hand-waved. It should include sheet/table detection, header inference, unit/currency/date normalization, entity definitions, metric definitions, joins across sheets, lineage from output cells to source cells/ranges, confidence scores, and user-confirmable assumptions. Without this, the LLM will hallucinate structure over messy workbooks.

- Note: Validation loop requirements should be concrete. Recommended checks: schema/type validation, row counts and totals reconciliation, formula/cached-value consistency checks, duplicate/missing key detection, unit/currency consistency, outlier checks, provenance coverage, deterministic re-execution of generated queries, and regression tests on representative messy workbooks. LLM-generated analysis should be converted into executable plans/queries and validated before presentation.

- Note: Security risks are material. Spreadsheet agents must treat files as untrusted input: macro malware, formula injection (`=HYPERLINK`, `WEBSERVICE`, DDE-style payloads), CSV injection on export, external workbook links, embedded objects, zip bombs, oversized files, prompt injection hidden in cells/comments/sheet names, and data exfiltration through tools. Require sandboxing, file-size/resource limits, no macro execution by default, network egress controls, scoped credentials, redacted tracing, and export sanitization.

- Note: UX/provenance must be first-class. Users need to see which sheet/range/cell backed each answer, what transformations were applied, what assumptions were made, and when results are approximate. The system should support “show your work,” downloadable audit artifacts, undo/replay, and clarification prompts when workbook structure is ambiguous.

- Note: Managed API vs OSS/local decision criteria:
  - Choose managed API when speed to market, broad format coverage, OCR/table extraction, vendor-maintained parsing, and operational simplicity matter more than data residency/customization/cost control.
  - Choose OSS/local when files contain sensitive financial/customer data, offline/on-prem deployment is required, deterministic reproducibility is critical, custom semantic modeling is central, per-file costs would be high, or vendor lock-in is unacceptable.
  - Prefer a hybrid when managed extraction is useful for difficult documents but normalized data, lineage, validation, orchestration, and policy enforcement must remain in your platform.

- Note: Evaluation gates should precede implementation choices. Build a benchmark corpus of real and synthetic spreadsheets covering messy headers, multi-sheet models, formulas, hidden/filtered data, large files, corrupted files, locale variants, and adversarial prompt-injection cells. Score candidates on extraction fidelity, formula/value fidelity, provenance granularity, latency, cost, memory use, failure modes, security posture, and integration effort.

- Blocker: `plan.md` referenced by the task was not present at `/Users/jeancarlobarrios/Developing/exeboard/ai/plan.md`; review used `progress.md` and `project_research.md` context instead.
