# Research: Docling as Exeboard's next PDF/document-intelligence parser adapter

## Summary
Proceed with **Docling as the best next local/layout-aware adapter candidate**, but keep the current Exeboard design guardrails: Docling must translate into Exeboard-owned `DocumentIR`/`DocumentLayout`, not replace them, and Slice 0 must prove exact API shape, no silent OCR/remote calls, coordinate normalization, and span alignment. A broader bakeoff is still useful before claiming production quality, but it should be an acceptance/evaluation gate rather than a blocker to the Docling adapter spike.

## Recommendation
**Proceed with Docling**, with these conditions:

1. Configure Docling explicitly, do not rely on defaults: current Docling CLI/code defaults have OCR and table extraction enabled (`--ocr` default `True`; `PdfPipelineOptions.do_ocr=True`, `do_table_structure=True`), while remote services are disabled by default. For Exeboard's default no-OCR/no-remote contract, set `do_ocr=False`, `enable_remote_services=False`, `allow_external_plugins=False`, and record those settings in parser provenance. [Docling CLI](https://docling-project.github.io/docling/reference/cli/) [Docling pipeline options](https://github.com/docling-project/docling/blob/main/docling/datamodel/pipeline_options.py)
2. Treat model artifacts as an explicit operational dependency: Docling documents that artifacts are fetched from remote sources on first use unless `artifacts_path` points to pre-downloaded models. This is compatible with offline execution, but only if Exeboard prefetches/pins artifacts and tests offline behavior. [Docling PipelineOptions](https://docling-project-docling.mintlify.app/api/options/pipeline-options) [Docling advanced options](https://docling-project-docling.mintlify.app/guides/advanced-options)
3. Run a small **acceptance bakeoff** after the adapter can emit Exeboard IR: PyMuPDF baseline, Docling, Marker, MinerU, and one cloud oracle (Azure or Google) over fixtures for multi-column text, repeated furniture, merged-header tables, figures/captions, scanned/image-only pages, rotated pages, and cross-page tables.

## Findings

1. **Exeboard's existing architecture points to Docling for the right reason: layout over spans, not parser-native replacement.** The local strategy requires `DocumentIR.content`/`TextSpan` as citation source of truth, with layout objects referencing span IDs or visual page/bbox provenance. The Docling adapter plan correctly requires no native Docling leakage, explicit parser-port failures, fake tests based on real API discovery, and no silent OCR/remote inference. [pdf-parsing-strategy.md](../docs/document-intelligence/pdf-parsing-strategy.md) [docling-adapter-plan.md](../docs/document-intelligence/docling-adapter-plan.md)

2. **Docling best matches Exeboard's local layout IR needs among OSS candidates.** Official Docling docs describe a `DoclingDocument` with text, tables, pictures, key-value items, hierarchy, body/furniture separation, bounding boxes, source page/position provenance, and per-item provenance with `page_no`, `bbox`, and `charspan`. It also exposes `iterate_items()` traversal and structured table grids. [DoclingDocument](https://docling-project-docling.mintlify.app/concepts/docling-document)

3. **Docling has real table/layout machinery rather than just coordinate heuristics.** The Docling technical report says its pipeline parses PDF text tokens and page images, applies layout analysis and TableFormer, infers reading order, matches figures with captions, and serializes typed document objects; TableFormer predicts row/column structure, header/body cells, spans, empty cells, hierarchy, and borderless/partial-border tables. [Docling technical report](https://arxiv.org/html/2408.09869v5)

4. **Docling's main risk is operational/runtime complexity, not feature fit.** Docling's model catalog includes layout object-detection models, TableFormer, OCR engines, VLM conversion, picture classification/description, code/formula enrichment, and multiple inference engines. That breadth is useful but increases dependency, model-download, accelerator, and reproducibility risk; Exeboard should pin versions/artifacts and keep integration tests opt-in. [Docling model catalog](https://docling-project.github.io/docling/usage/model_catalog/)

5. **PyMuPDF-only should remain the fast baseline, not the layout-aware adapter.** PyMuPDF exposes fast text, blocks, words, raw char dictionaries, bboxes, and table detection, but its docs state plain text is in original creator order and may not match natural reading order; `sort=True` is a top-left-to-bottom-right reorder heuristic. That does not satisfy Exeboard's semantic reading order, table cell, figure/caption, and furniture requirements by itself. [PyMuPDF text extraction](https://pymupdf.readthedocs.io/en/latest/app1.html)

6. **pdfplumber/Camelot are useful targeted tools but not the best primary layout IR adapter.** pdfplumber provides excellent character/object coordinates and customizable table extraction, but it works best on machine-generated PDFs and explicitly does not provide OCR or strong OCR-table support. Camelot has strong table-specific parsers (stream/lattice/network/hybrid and optional ML), but it is primarily a table extractor; it does not provide a full document hierarchy, figure/caption model, or unified provenance substrate for summarization. [pdfplumber README](https://github.com/jsvine/pdfplumber) [Camelot how it works](https://camelot-py.readthedocs.io/en/latest/user/how-it-works.html)

7. **Unstructured is flexible but weaker for deterministic local evidence-backed layout by default.** `partition_pdf` supports `fast`, `hi_res`, `ocr_only`, and `auto`, with local inference if no URL is set, but it can choose/fall back across strategies, OCR is applied when text is unavailable, and the docs warn `hi_res` has difficulty ordering elements for multi-column image documents. This is a good ingestion option, but its fallback behavior and element abstraction make it less clean than Docling for Exeboard's explicit parser-port failure model. [Unstructured partitioning](https://docs.unstructured.io/open-source/core-functionality/partitioning)

8. **Marker is a serious local contender but has licensing and authority/provenance concerns for Exeboard's first adapter.** Marker converts PDFs/images/Office/HTML/EPUB to Markdown, JSON, chunks, and HTML; handles tables, figures, headers/footers, math, references, images; and has block IDs/polygons plus table-cell row/column/span/header fields in code. However, its README advertises optional LLM hybrid mode using Gemini by default, its code is GPL-3.0 and model license is OpenRAIL-M/commercial-gated, and its output is oriented toward Markdown/HTML/chunks rather than an explicit page/bbox/char-span citation substrate. [Marker README](https://github.com/VikParuchuri/marker) [Marker block schema](https://github.com/VikParuchuri/marker/blob/master/marker/schema/blocks/base.py) [Marker table cell schema](https://github.com/VikParuchuri/marker/blob/master/marker/schema/blocks/tablecell.py)

9. **MinerU is another credible local/open parser to include in bakeoff, not the next adapter default.** MinerU claims reading order, OCR/VLM engines, tables, formulas, multi-column, cross-page table merging, and JSON/Markdown output. Its docs expose layout PDFs with reading-order numbers and structured `middle.json` with page info, blocks, lines, spans, and bboxes. But it has additional license terms beyond Apache 2.0 and less clear char-offset provenance into one canonical text string, so it is better as an evaluation competitor for now. [MinerU README](https://github.com/opendatalab/MinerU) [MinerU output files](https://github.com/opendatalab/MinerU/blob/master/docs/en/reference/output_files.md) [MinerU license](https://github.com/opendatalab/MinerU/blob/master/LICENSE.md)

10. **Azure Document Intelligence is the strongest comparison point for layout IR shape, but it is cloud-first.** Azure returns global `content`, spans with offsets/lengths, pages sorted by reading order, paragraphs with roles including headers/footers/title/section heading/footnote, tables with row/column indices/spans and cell roles, figures with bounding regions/spans/captions, and sections. It is an excellent oracle/reference adapter shape but violates Exeboard's local/offline preference as a primary next adapter. [Azure analyze response](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept/analyze-document-response?view=doc-intel-4.0.0)

11. **Google Document AI/Gemini Layout Parser has excellent RAG-oriented structure but is also remote/cloud and partially generative.** Google Document AI uses a `Document.text` source of truth, `textAnchor` offsets, page/layout bounding polygons, tables, and normalized vertices. The Gemini layout parser adds hierarchy, layout-aware chunks, figures/tables/lists/headers, and generative annotations/verbalizations for visual elements, but it is a cloud processor with page/file limits and some preview model versions. [Google Document AI response](https://cloud.google.com/document-ai/docs/handle-response) [Gemini layout parser](https://cloud.google.com/document-ai/docs/layout-parse-chunk)

12. **The most important Docling implementation risk is span alignment.** Docling exposes provenance including charspans, but Exeboard should still build `DocumentIR.content` from the exact generated `TextSpan.text` traversal or cross-check Docling charspans deterministically. If Docling's public API cannot stably connect text items/table cells/figures to page/bbox/char spans, the adapter should stop at Slice 0 rather than fall back to lossy Markdown.

## Comparison matrix

| Option | Fit for Exeboard layout IR | Local/offline | Tables/cells | Figures/captions | Provenance | Main risk |
|---|---:|---:|---:|---:|---:|---|
| **Docling** | High | High if artifacts prefetched | High | Medium-High | page/bbox/charspan documented | Defaults OCR on; model artifacts/deps; API discovery required |
| PyMuPDF-only | Low-Medium | High | Medium if adding table APIs | Low | strong raw spans/bboxes | no semantic reading order/furniture/figure model |
| pdfplumber/Camelot | Medium for targeted tables | High | Medium-High targeted | Low | strong coords, weak global char-span IR | table tools, not full layout parser |
| Unstructured | Medium | Medium-High with local inference | Medium | Medium | element metadata, not ideal canonical spans | fallback/OCR strategy ambiguity; multi-column limits |
| Marker | Medium-High | High, but LLM mode can be remote | High | Medium-High | block polygons/IDs, weaker canonical charspan story | GPL/model/commercial license; Markdown-first |
| MinerU | Medium-High | High | High claimed | Medium-High | bboxes/spans in JSON, char offsets unclear | license terms; API/version maturity for adapter |
| Azure DI | Very high | No | High | High | excellent global content spans + bounding regions | cloud/privacy/cost/latency |
| Google Document AI | Very high | No | High | High | textAnchor + boundingPoly | cloud/privacy/cost; generative/preview pieces |

## Sources

### Kept
- DoclingDocument (https://docling-project-docling.mintlify.app/concepts/docling-document) — primary evidence for Docling hierarchy, body/furniture, tables, pictures, bbox, page, charspan provenance.
- Docling PipelineOptions / CLI / Advanced Options (https://docling-project-docling.mintlify.app/api/options/pipeline-options, https://docling-project.github.io/docling/reference/cli/, https://docling-project-docling.mintlify.app/guides/advanced-options) — OCR defaults, remote-service defaults, artifact-download/offline behavior.
- Docling technical report (https://arxiv.org/html/2408.09869v5) — architecture, reading order, layout/table models, local execution, performance caveats.
- PyMuPDF docs (https://pymupdf.readthedocs.io/en/latest/app1.html) — exact limits of text order and bbox/char extraction baseline.
- pdfplumber README (https://github.com/jsvine/pdfplumber) — character/object coordinates, table extraction, no OCR caveat.
- Camelot docs (https://camelot-py.readthedocs.io/en/latest/user/how-it-works.html) — table-specific parser mechanisms and scope.
- Unstructured docs (https://docs.unstructured.io/open-source/core-functionality/partitioning) — strategy/fallback/OCR/local inference behavior.
- Marker README/schema (https://github.com/VikParuchuri/marker) — features, license/dependency concerns, block/table-cell schema.
- MinerU README/output/license (https://github.com/opendatalab/MinerU) — local/open competitor features and structured outputs.
- Azure Document Intelligence docs (https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept/analyze-document-response?view=doc-intel-4.0.0) — reference-grade cloud layout/provenance model.
- Google Document AI docs (https://cloud.google.com/document-ai/docs/handle-response, https://cloud.google.com/document-ai/docs/layout-parse-chunk) — reference-grade textAnchor/layout/chunking model.

### Dropped
- pdfmux blog benchmark pages — potentially useful but self-promotional and not needed for the adapter decision.
- DEV Community parser comparison — broad but secondary commentary, weaker than primary docs.
- CodeCut Docling vs Marker vs LlamaParse article — anecdotal comparison, not primary evidence.
- Generic GitHub projects such as MetadataDocumentParser — interesting but less mature/relevant than Docling/Marker/MinerU for this decision.

## Gaps
1. No Exeboard-corpus benchmark has been run yet. The final production claim needs fixture-level accuracy measurements for reading order, table cell alignment, span reconstruction, figures/captions, OCR-disabled scanned PDFs, and rotated/cross-page cases.
2. Docling's exact public API at the pinned target version (`docling==2.78.0` in the plan) still needs Slice 0 discovery. Current docs indicate the right capabilities, but implementation must verify attribute names, coordinate origin/units, charspan semantics, defaults, and artifact behavior in that pinned version.
3. Licensing review should confirm whether Marker GPL/OpenRAIL and MinerU additional terms are acceptable if either becomes more than a bakeoff competitor.

## Supervisor coordination
No supervisor decision needed. Recommendation is to proceed with Docling under the existing Slice 0 stop conditions and add a small acceptance bakeoff before production claims.
