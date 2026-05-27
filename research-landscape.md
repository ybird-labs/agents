# Research: LLM/AI agents for reading, analyzing, and editing spreadsheets

## Summary
The problem is **not fully solved as an open-source, production-ready stack**. Commercial Excel-native agents are increasingly credible for analyst-in-the-loop workflows, and managed parsers are production-ready for extraction, but reliable API-first spreadsheet editing with formulas, charts, merged cells, citations, audit trails, and enterprise security still requires custom integration and validation.

Best current path: combine a spreadsheet-aware tool layer (spreadsheet-kit/spreadsheet-mcp or ExStruct), a parser for messy workbooks (LlamaSheets/Reducto/Docling/Unstructured depending on needs), and a guarded agent workflow with diff/proof/recalc/human review. Research repos show useful ideas, but most are benchmarks/prototypes rather than production platforms.

## Findings

1. **Landscape splits into three categories, none complete alone.** Open-source projects provide primitives or research agents; commercial add-ins solve Excel-in-the-loop workflows but are closed products; parsing APIs normalize messy spreadsheets but generally do not perform safe workbook edits. This means “chat with/edit a spreadsheet” is solved for narrow human workflows, but not for a dependable embeddable product backend. [spreadsheet-kit](https://github.com/PSU3D0/spreadsheet-mcp), [Claude for Excel](https://claude.com/docs/office-agents/excel), [LlamaSheets](https://developers.llamaindex.ai/llamaparse/sheets/)

2. **Most open-source LLM spreadsheet agents are research-grade.** SheetCopilot is NeurIPS 2023-era, Windows-only, GPL-3.0, 163 stars, and supports a rich action space including charts/pivots/formatting, but its README still lists TODOs around parsing/evaluation and it is not packaged as a maintained production SDK. SheetAgent is a WWW 2025 research implementation with only ~30 stars, no clear license in the fetched repo, Milvus/OpenAI setup, and benchmark datasets. SheetBrain is newer from Microsoft, MIT, ~22 stars, and claims AAAI 2026 oral acceptance, with an understand-execute-validate architecture and Excel toolkit, but it is still a paper implementation requiring OpenAI access. [SheetCopilot](https://github.com/BraveGroup/SheetCopilot), [SheetAgent](https://github.com/cybisolated/SheetAgent), [SheetBrain](https://github.com/microsoft/SheetBrain)

3. **The strongest open-source production-oriented building blocks are MCP/CLI libraries, not full autonomous agents.** spreadsheet-kit/spreadsheet-mcp is Apache-2.0, Rust, ~43 stars, published to crates.io/npm, has releases, tests, CLI/MCP/JS SDK/WASM surfaces, supports `.xlsx/.xlsm` read-write, `.xls/.xlsb` discovery/read, dry-run edits, diffs, recalc, named ranges, formula diagnostics, session history, undo/redo, fork, and structural impact analysis. It is close to a tool layer for agents, but not an opinionated end-user agent. [spreadsheet-mcp](https://github.com/PSU3D0/spreadsheet-mcp), [crates.io](https://crates.io/crates/spreadsheet-mcp)

4. **ExStruct is the most spreadsheet-structure-aware open-source extractor/editor.** ExStruct is BSD-3-Clause, ~133 stars, PyPI-released, and extracts cells, shapes, charts, SmartArt, table candidates, merged-cell ranges, print areas, hyperlinks, and formula maps. It also has JSON-first patch editing, dry runs, validation, and MCP integration. Limitations: rich extraction depends on Windows Excel COM; non-COM Linux/macOS extraction is best-effort via OOXML/LibreOffice, so chart/shape fidelity and editing parity need testing. [ExStruct](https://github.com/harumiWeb/exstruct)

5. **sv-excel-agent is promising but very young.** SylvianAI/sv-excel-agent is MIT, ~178 stars, Python, created in late 2025, and combines an Excel MCP server with an agent runner and SpreadsheetBench evals. It exposes ~30 Excel editing tools and notes Microsoft Excel is used for accurate formula/format evaluation; LibreOffice is less accurate for complex formulas and conditional formatting. Treat it as an active prototype/reference, not mature infra. [sv-excel-agent](https://github.com/SylvianAI/sv-excel-agent)

6. **Simple ingestors and dataframe agents do not solve workbook semantics.** llm-excel-ingestor is MIT but tiny (~2 stars) and notebook-oriented; it preserves cell lineage, formulas, and dependencies into Markdown/JSON but does not edit/recalculate workbooks. PandasAI is mature for conversational dataframe/CSV/SQL analysis (MIT core, ~23.5k stars, charts, Docker sandbox), but it flattens spreadsheets into dataframes and does not preserve Excel workbook semantics such as merged cells, formulas, charts, pivots, named ranges, or formatting. [llm-excel-ingestor](https://github.com/wesslen/llm-excel-ingestor), [PandasAI](https://github.com/sinaptik-ai/pandas-ai), [PandasAI Agent docs](https://docs.pandas-ai.com/v3/agent)

7. **LangChain/LlamaIndex integrations are mostly loaders/parsers, not editors.** LangChain’s Excel support uses `UnstructuredExcelLoader`, returning raw text or HTML table metadata per sheet. LlamaIndex/LlamaParse can parse Excel and now has LlamaSheets beta for spreadsheet regions/tables plus a private-preview “Spreadsheet Agent,” but the public API is extraction-first. [LangChain Excel loader](https://reference.langchain.com/python/langchain-community/document_loaders/excel/UnstructuredExcelLoader), [LlamaSheets](https://developers.llamaindex.ai/llamaparse/sheets/), [LlamaIndex Spreadsheet Agent preview](https://www.llamaindex.ai/blog/introducing-the-spreadsheet-agent-in-private-preview)

8. **Commercial Excel-native agents are the most “solved” option for user-facing finance workflows.** Claude for Excel is in beta for Pro/Max/Team/Enterprise, supports cell-level citations, multi-tab workbooks, assumption changes preserving formula relationships, debugging, template/model generation, sorting/filtering/pivot tables/conditional formatting/data validation, connectors, and M365 deployment. But Anthropic explicitly warns it is beta, not recommended for final client deliverables or audit-critical calculations without verification, and does not support data tables, macros, or VBA. It also documents prompt-injection risk and local/browser chat storage behavior. [Claude for Excel docs](https://claude.com/docs/office-agents/excel)

9. **Commercial competitors emphasize auditability/security, but evidence is mostly marketing.** Endex is Excel-native for finance, claims integrated citations, finance-tuned models, complex chart understanding, AES-256/TLS encryption, and enterprise security; RowsnColumns claims planning/editing/verification, cell-level diff history, formula-first editing, rollback, audit trails, on-prem deployment, and retention controls; o11 claims in-workbook execution, formula/format edits, verification, source-backed cell-level citations, and repeatable prompt runs. These may be production-ready for their customers, but they are closed platforms with limited public API/SDK evidence. [Endex](https://endex.ai/), [Endex Security](https://endex.ai/security), [RowsnColumns](https://rowsncolumns.ai/), [o11](https://o11.ai/solutions/excel)

10. **GPT for Work is production-oriented for bulk tasks, less for complex workbook modeling.** GPT for Excel provides an Excel add-in agent, bulk tools, and cell functions; it can write/fix formulas, format ranges/sheets, standardize data, create charts/pivot tables, process up to large row counts, and use user-controlled API endpoints. It is strong for row-by-row enrichment and everyday spreadsheet automation, but public docs do not show robust workbook-level audit trails, formula dependency proofs, or enterprise-grade cell citations comparable to finance-focused tools. [GPT for Excel docs](https://gptforwork.com/docs/gpt-for-excel)

11. **Excelence/Excelent-style add-ins show market direction but need validation.** Excelence.ai claims native Excel operation, zero uploads, formula/PivotTable/named range/link/chart preservation, and web/PDF/doc extraction into clean tables; Microsoft AppSource listings confirm it can read/write workbook data and send data over the internet. Public technical detail is thin, so validate via trial/security review before relying on it. [Excelence.ai](https://app.excelence.ai/), [Microsoft AppSource listing](https://marketplace.microsoft.com/en-us/product/office/WA200009379)

12. **Managed parsing APIs are useful but solve extraction, not editing.** LlamaSheets beta identifies spreadsheet regions/tables, returns Parquet table data and cell metadata including coordinates, formatting, merged-cell flags, and raw/processed values; limits include 1 job/sec and 100 columns or 10,000 rows per sheet. Reducto’s spreadsheet config supports LLM/table clustering, large-table splitting, cell colors, formulas as `data-formula`, hidden-content exclusion, and image/chart skipping. These are good ingestion layers for RAG/agents, but neither replaces an Excel-aware mutation/recalc engine. [LlamaSheets](https://developers.llamaindex.ai/llamaparse/sheets/), [LlamaSheets API](https://developers.llamaindex.ai/reference/python/resources/beta/subresources/sheets), [Reducto spreadsheet processing](https://docs.reducto.ai/configs/parse/spreadsheet)

13. **Docling and Unstructured are broad document parsers with partial Excel support.** Docling is MIT, very mature by stars (~57k), supports XLSX and has active work around Excel table bounds and merged-cell flattening, but open issues/discussions show gaps around calculated values vs formulas, merged cells, and charts. Unstructured/LangChain support `.xlsx/.xls` as raw text or HTML table elements and have improved subtable detection, but public docs do not position it as preserving full workbook semantics. [Docling](https://github.com/docling-project/docling), [Docling formula issue](https://github.com/docling-project/docling/issues/1235), [Docling merged-cell issue](https://github.com/docling-project/docling/issues/1939), [UnstructuredExcelLoader](https://reference.langchain.com/python/langchain-community/document_loaders/excel/UnstructuredExcelLoader)

14. **Hard unsolved areas remain.** Formula recalculation fidelity, chart/pivot/table preservation, merged-cell interpretation, hidden-sheet security, prompt injection in external workbooks, cell-level citation/provenance, deterministic diffs, and reviewable rollback are not consistently handled across tools. The most robust public tool layers explicitly include dry-run/diff/recalc/verification because naïve agents easily corrupt workbooks. [spreadsheet-kit](https://github.com/PSU3D0/spreadsheet-mcp), [Claude prompt-injection warning](https://claude.com/docs/office-agents/excel)

## Maturity matrix

| Tool | Type | Maturity / maintenance | License / access | Evidence & strengths | Key limitations |
|---|---|---:|---|---|---|
| SheetBrain | Research OSS agent | New; ~22 stars; last push 2026-01 | MIT | Understand-execute-validate; charts/toolkit; SheetBench | Paper implementation; OpenAI dependency; not packaged prod |
| SheetAgent | Research OSS agent | ~30 stars; last push 2025-04 | No clear license found | WWW 2025; manipulation/reasoning; SheetRM dataset | Milvus/OpenAI setup; research code; unclear commercial use |
| SheetCopilot | Research OSS agent | ~163 stars; older but maintained into 2024 | GPL-3.0 | Rich action space: formatting, charts, pivots, merge, validation | Windows-only; pywin32/UI automation; TODOs; copyleft |
| spreadsheet-kit / spreadsheet-mcp | OSS tool layer | Active; ~43 stars; releases, crates/npm | Apache-2.0 | CLI/MCP/JS SDK/WASM; read/write/recalc/diff/proof/session/security | Not a full autonomous agent; needs orchestration/UX |
| ExStruct | OSS extractor/editor | Active; ~133 stars; PyPI releases | BSD-3-Clause | Cells/shapes/charts/merged/formulas; patch CLI; MCP | Richest mode needs Excel COM; non-Windows best-effort |
| sv-excel-agent | OSS MCP + agent runner | Young; ~178 stars | MIT | ~30 tools; SpreadsheetBench evals; demo app/slack | New; Excel required for best eval; LibreOffice caveats |
| llm-excel-ingestor | OSS ingestor | Tiny; ~2 stars; one-off notebook | MIT | Preserves formulas/dependencies in MD/JSON | No editing/recalc/security; not a library platform |
| PandasAI | OSS/enterprise dataframe agent | Mature; ~23.5k stars | MIT core + EE | Natural language dataframe analysis, charts, sandbox | Loses workbook semantics; not Excel editing |
| LangChain Excel loader | OSS integration | Mature ecosystem | MIT packages | Quick XLS/XLSX ingestion via Unstructured | Raw text/HTML table loading only |
| Claude for Excel | Commercial add-in | Beta but serious | SaaS/add-in | Cell citations, formula-preserving edits, pivots/formatting, connectors | Beta; no macros/VBA/data tables; human verification required |
| Endex | Commercial finance add-in | Enterprise pilots/customers claimed | Closed | Citations, finance sources, complex charts, security claims | Closed; limited public technical docs/API |
| RowsnColumns AI | Commercial workflow | Production claims | Closed | Audit trail, reversible cell edits, formula checks, on-prem | Closed; claims need pilot validation |
| o11 for Excel | Commercial agent | Production claims | Closed | Direct workbook edits, citations, verification, cross-app flows | Closed; limited API details |
| GPT for Work | Commercial add-in | Mature user-facing product | Closed | Bulk row processing, formulas, charts/pivots, BYO API | Less evidence for deep workbook provenance/audit |
| LlamaSheets/LlamaParse | Managed parsing API | Beta for sheets; prod parser brand | API | Region/table detection, Parquet, metadata, merged flags | Extraction only; size/rate limits |
| Reducto | Managed parsing API | Production API | API | Table clustering, formulas/colors, hidden-content controls | Extraction only; not workbook editor |
| Docling | OSS parser | Very mature; ~57k stars | MIT | Broad formats incl. XLSX; active Excel work | Formula values/merged cells/charts still imperfect |
| Unstructured | OSS/API parser | Mature parser ecosystem | OSS/API | XLS/XLSX partitioning, subtables, HTML tables | Limited workbook semantics/citations/editing |

## Production-readiness verdict

- **Production-ready today for human-in-the-loop Excel users:** Claude for Excel, Endex, RowsnColumns, o11, GPT for Work, possibly Excelence after vendor validation.
- **Production-ready as infrastructure building blocks:** spreadsheet-kit/spreadsheet-mcp, ExStruct for extraction/patching with caveats, PandasAI for dataframe-only analysis, Docling/Unstructured/Reducto/LlamaParse for ingestion.
- **Research/prototype only:** SheetBrain, SheetAgent, SheetCopilot, sv-excel-agent, llm-excel-ingestor.
- **Requires custom build:** any product needing API-first spreadsheet agents with deterministic editing, formulas/charts/pivots/merged-cell fidelity, cell citations, secure hidden-content handling, prompt-injection defenses, audit logs, and rollback.

## Recommended architecture if building

1. **Parser/orientation:** LlamaSheets or Reducto for messy workbook table/region detection; ExStruct when charts/shapes/merged cells matter; fallback to openpyxl/calamine for raw values.
2. **Workbook tool layer:** spreadsheet-kit/spreadsheet-mcp for safe read/write/recalc/diff/proof/session; ExStruct patch CLI for JSON-first editing.
3. **Agent policy:** require plan → dry run → diff/proof → recalc → human approval for risky writes; never let the LLM freely rewrite files.
4. **Security:** isolate execution, scan hidden sheets/rows/columns, block macro/VBA execution, preserve original files, log prompts/tool calls/cell edits, and defend against prompt injections in workbook text.
5. **Citations/provenance:** store cell/range references and parser coordinates; for source-document extraction, require source bounding boxes or file offsets from Reducto/LlamaParse-style APIs.

## Sources

- Kept: SheetBrain GitHub (https://github.com/microsoft/SheetBrain) — Microsoft research implementation; architecture/features/license/stars.
- Kept: SheetAgent GitHub (https://github.com/cybisolated/SheetAgent) — WWW 2025 research agent and dataset.
- Kept: SheetCopilot GitHub (https://github.com/BraveGroup/SheetCopilot) — NeurIPS 2023 benchmark/action-space evidence.
- Kept: spreadsheet-mcp/spreadsheet-kit (https://github.com/PSU3D0/spreadsheet-mcp) — strongest OSS tool layer evidence.
- Kept: ExStruct GitHub (https://github.com/harumiWeb/exstruct) — structured extraction/editing/MCP details.
- Kept: sv-excel-agent GitHub (https://github.com/SylvianAI/sv-excel-agent) — young OSS MCP+agent implementation.
- Kept: llm-excel-ingestor GitHub (https://github.com/wesslen/llm-excel-ingestor) — formula/dependency ingest example.
- Kept: PandasAI GitHub/docs (https://github.com/sinaptik-ai/pandas-ai, https://docs.pandas-ai.com/v3/agent) — mature dataframe agent baseline.
- Kept: Claude for Excel docs (https://claude.com/docs/office-agents/excel) — best public commercial details including limitations/security.
- Kept: Endex and security page (https://endex.ai/, https://endex.ai/security) — commercial finance agent claims/security.
- Kept: RowsnColumns (https://rowsncolumns.ai/) — audit/diff/rollback claims.
- Kept: o11 Excel (https://o11.ai/solutions/excel) — in-workbook execution/citation claims.
- Kept: GPT for Excel docs (https://gptforwork.com/docs/gpt-for-excel) — bulk/add-in/function capabilities.
- Kept: LlamaSheets docs/API (https://developers.llamaindex.ai/llamaparse/sheets/) — managed spreadsheet extraction API details.
- Kept: Reducto spreadsheet docs (https://docs.reducto.ai/configs/parse/spreadsheet) — formulas/colors/hidden content/table clustering.
- Kept: Docling GitHub/issues (https://github.com/docling-project/docling) — mature parser plus Excel gaps.
- Kept: LangChain UnstructuredExcelLoader (https://reference.langchain.com/python/langchain-community/document_loaders/excel/UnstructuredExcelLoader) — integration scope.
- Dropped: SEO review/listicle pages for Endex/Ajelix/ExcelMaster — weaker than vendor docs or marketplaces.
- Dropped: unrelated identifai.net pages — different product from Identifai/Endex-like Excel finance agent result.
- Dropped: generic “Excel + LangChain” tutorials — lacked primary technical evidence beyond known loaders.

## Gaps

- Public evidence for Identifai, Excelence, Endex, RowsnColumns, and o11 is mostly marketing; true API/SDK support, SOC2 scope, data retention, formula/chart fidelity, and failure rates require vendor demos/security packs.
- Stars/maintenance are snapshots from search results and may change.
- Few tools publish rigorous evals on real-world financial models with formulas, charts, pivots, merged cells, hidden sheets, and adversarial prompt injection.
- Next step: run a benchmark suite on representative workbooks comparing spreadsheet-kit, ExStruct, LlamaSheets, Reducto, Docling, and Claude/GPT/Endex-style products on extraction fidelity, edit correctness, recalculation, auditability, and security behavior.
