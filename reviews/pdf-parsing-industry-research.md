# PDF Parsing Strategy — Industry Research Review

Date: 2026-05-25

Reviewed local docs:

- `docs/document-intelligence/pdf-parsing-strategy.md`
- `docs/document-intelligence/implementation-plan.md`
- `docs/document-intelligence/tutorial-state.md`

## Summary verdict

**Verdict: approve the architecture direction, with production-hardening corrections before implementing Docling/layout parsing.** The plan’s core choice—keep Exeboard-owned `DocumentIR`/`TextSpan` as the citation substrate and add a layout layer over spans—is aligned with current document-intelligence APIs: Azure returns a global reading-order `content` string plus element spans, bounding regions, pages, paragraphs, tables, figures, sections, and paragraph roles; Docling uses a structured document model with body/furniture, tables, pictures, hierarchy, bounding boxes, and provenance; Google Document AI/Gemini layout parser is explicitly layout/RAG oriented; Unstructured exposes distinct fast/layout/OCR strategies. [Azure](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept/analyze-document-response?view=doc-intel-4.0.0), [Docling](https://docling-project-docling.mintlify.app/concepts/docling-document), [Google](https://cloud.google.com/document-ai/docs/layout-parse-chunk), [Unstructured](https://docs.unstructured.io/open-source/core-functionality/partitioning)

The current MVP implementation remains correctly scoped as **native-text PDF summarization only**. It should not be described as production-grade for complex, scanned, table-heavy, multi-column, or figure-heavy PDFs until layout IR, a layout-aware parser adapter, and layout-aware chunking are implemented.

## Evidence findings

1. **PyMuPDF native text extraction is fast but not semantic layout reconstruction.** PyMuPDF states that `Page.get_text("text")` extracts text in “original order” as specified by the PDF creator, which “may not equal” natural reading order; `sort=True` only reorders by a “top-left to bottom-right” scheme. This supports the plan’s rejection of treating `sort=True` as semantic reading order. [PyMuPDF text extraction details](https://pymupdf.readthedocs.io/en/latest/app1.html)

2. **PyMuPDF has useful table and OCR capabilities, but they must be explicit product choices.** PyMuPDF documents that visible PDF tables are usually just positioned text and extracting them requires detecting the table area and borders; `Page.find_tables()` exists for table detection. PyMuPDF also has integrated Tesseract-based OCR, but OCR is “about one thousand times slower” than standard text extraction and loses original font/style detail. Therefore, the plan should say the **Exeboard `PyMuPDFParser`** does not OCR or expose table IR, not that the PyMuPDF library cannot. [PyMuPDF table extraction](https://pymupdf.readthedocs.io/en/latest/recipes-text.html), [PyMuPDF OCR](https://pymupdf.readthedocs.io/en/latest/recipes-ocr.html)

3. **Docling is a strong local layout-adapter candidate.** Docling’s `DoclingDocument` supports text, tables, pictures, key-value items, hierarchy, main body vs. furniture, bounding boxes, and provenance with page number, bbox, and character spans. Its API also exposes document-order iteration and structured tables. This matches the plan’s “Docling adapter translated into Exeboard-owned IR” approach. [Docling concepts](https://docling-project-docling.mintlify.app/concepts/docling-document), [Docling API](https://docling-project-docling.mintlify.app/api/docling-document)

4. **Azure Document Intelligence validates the proposed IR shape.** Azure’s Analyze response groups content into pages and returns a top-level `content` string in reading order; elements point into it via spans. It also returns paragraphs, tables, figures, sections, bounding regions, roles such as page header/footer/page number/title/section heading/footnote, and table cells with row/column indices and spans. This strongly supports a canonical content string plus structured layout objects with provenance. [Azure Analyze response](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept/analyze-document-response?view=doc-intel-4.0.0)

5. **Azure also exposes edge cases the proposed model should handle.** Azure notes that reading order across page boundaries is not currently supported, ambiguous order may fall back to left-to-right/top-to-bottom, element content can be non-contiguous, and bounding regions can be arrays for non-contiguous or cross-page elements. This argues against a layout model that only allows one `page_number` and one bbox per block/table/figure. [Azure Analyze response](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept/analyze-document-response?view=doc-intel-4.0.0)

6. **Google Document AI/Gemini layout parser aligns with the plan’s layout-aware RAG premise.** Google says standard OCR flattens documents and destroys context; its layout parser identifies tables, figures, lists, headers, and heading relationships, produces a `DocumentLayout` tree, and creates context-aware chunks with ancestor headings/table headers. It also combines OCR with Gemini and has table/image annotations. This supports the plan’s stance that summarization should consume structure, not raw lines. [Google layout parser](https://cloud.google.com/document-ai/docs/layout-parse-chunk), [Google ProcessOptions/LayoutConfig](https://docs.cloud.google.com/document-ai/docs/reference/rest/v1/ProcessOptions)

7. **Cloud layout parsers introduce production constraints and non-authoritative generated text.** Google layout parser has online/batch file and page limits, preview model versions, optional image/table annotations, and higher-latency model variants. Generated table/image descriptions should be treated as derived annotations, not quote-valid source text unless tied back to OCR/text spans or visual-region provenance. [Google layout parser](https://cloud.google.com/document-ai/docs/layout-parse-chunk)

8. **Unstructured confirms that native extraction, layout inference, OCR, and VLM parsing are distinct strategies with tradeoffs.** `partition_pdf` supports `auto`, `fast`, `hi_res`, and `ocr_only`; `fast` uses pdfminer/raw text, `hi_res` identifies layout, `ocr_only` runs Tesseract then text partitioning, and `auto` chooses/falls back based on document characteristics. Its current docs also emphasize speed/cost/quality tradeoffs and that Fast can be ~100x faster than image-to-text models. This supports the plan’s “no silent OCR fallback” rule, but also means any `auto` adapter must record actual chosen strategies per page/file. [Unstructured partitioning](https://docs.unstructured.io/open-source/core-functionality/partitioning), [Unstructured strategies](https://docs.unstructured.io/open-source/concepts/partitioning-strategies)

## Comparison to the plan

### What is well aligned

- **Layered IR is the right production boundary.** Keeping `DocumentIR.content`, pages, and `TextSpan`s as Exeboard’s citation truth while adding layout objects over spans matches Azure’s top-level content + spans design and avoids coupling downstream summarization to Docling/Azure/Google-native object shapes.
- **PyMuPDF as fast native-text baseline is correct.** It is appropriate for simple digital PDFs and deterministic MVP tests, but not as a semantic layout engine.
- **Explicit parser strategies are correct.** OCR/layout/cloud parsing changes latency, cost, privacy, confidence profile, dependencies, and failure modes. The plan is right to avoid silent fallback inside `PyMuPDFParser`.
- **Table structure must be preserved.** Azure and Docling both model table cells/row-column structure, and Google/Unstructured emphasize complex tables as a RAG failure mode.
- **Docling as local layout adapter candidate is reasonable.** It is not a vendor-domain model replacement; translating it into Exeboard IR is the correct dependency direction.

### Recommended corrections before implementation

1. **Clarify PyMuPDF claims.** Replace broad wording like “PyMuPDF does not understand tables” / “does not OCR” with: “The Exeboard `PyMuPDFParser` is configured as a native-text adapter and will not expose table IR or invoke PyMuPDF/Tesseract OCR.” PyMuPDF itself has `find_tables()` and OCR APIs, but using them should be an explicit parser strategy.

2. **Make layout elements multi-region and optionally multi-page.** Current sketch uses singular `page_number`/`bbox` on `LayoutBlock`, `Table`, and `Figure`. Production layout should support `bounding_regions: tuple[BoundingRegion, ...]`, `page_numbers: tuple[int, ...]`, and explicit continuation semantics for cross-page tables/sections/figures. Azure’s model explicitly uses arrays of bounding regions and notes non-contiguous/cross-page cases.

3. **Do not require text spans for non-text visual evidence.** A figure may have no text span except a caption; forcing `source_span_ids` risks fake spans or losing visual provenance. Add `VisualRegionId`/`FigureRegion` or allow `source_span_ids=()` with required `bounding_regions` and optional `caption_span_ids`. Generated image/table descriptions must be marked `derived_non_authoritative` unless quote-supported by OCR/text spans.

4. **Add coordinate-system normalization to the IR contract.** Store or normalize bbox unit, origin, page rotation policy, and source coordinate system. PyMuPDF uses page coordinates; Azure uses page units such as inches for PDFs and bounding polygons; Docling bboxes have their own origin metadata. Highlighting and citation audit will break if these are mixed silently.

5. **Add span-alignment failure modes for Docling/cloud adapters.** Mapping Docling/Azure/Google text spans into Exeboard `TextSpanId`s is non-trivial because each parser may normalize whitespace, order text differently, emit non-contiguous spans, or use different character-index units. The adapter must either construct `DocumentIR.content` directly from the parser’s canonical content or run a deterministic alignment step that can fail loudly.

6. **Record actual parser strategy, OCR use, model/version, confidence, and fallbacks per parser run/page.** This is especially important for Docling pipelines, Unstructured `auto`, Azure model versions, and Google Gemini layout parser preview/stable versions. `ParserRun` should distinguish native text, OCR, layout inference, VLM/generative annotation, and cloud processing.

7. **Keep layout-aware chunking separate from vendor chunking.** Google can return layout-aware chunks, but Exeboard should still translate layout/chunk provenance into Exeboard-owned chunk models. Vendor chunks may be useful adapter input, not the canonical chunking contract.

8. **Add quality/evaluation gates for tables and reading order.** Production acceptance should include multi-column pages, repeated headers/footers, table header/value alignment, merged cells, scanned pages, rotated pages, and cross-page tables—not only parser success and citation validity.

## Explicit shortcut / architecture risks

- **Risk: calling the current MVP “production PDF summarization.”** The implemented PyMuPDF + span chunker pipeline is a useful digital-text vertical slice, but industry sources show that complex PDFs require layout, table, OCR, and provenance-aware parsing.
- **Risk: `sort=True` or line order becomes de facto reading order.** PyMuPDF’s own docs say original order may not be natural and sorted order is only top-left to bottom-right.
- **Risk: layout text becomes a second citation truth.** Keep `TextSpan`s authoritative. Derived markdown/table text can be useful, but quote validation must resolve back to source spans or explicitly mark derived/generated annotations.
- **Risk: hidden OCR/auto fallback changes compliance and reproducibility.** Unstructured and PyMuPDF demonstrate why OCR/layout modes differ materially in speed, dependencies, and quality. If an adapter uses `auto`, log the actual strategy and warnings.
- **Risk: no provenance model for visual-only evidence.** Figures/charts/images cannot always cite text spans. Add visual-region provenance instead of fabricating spans.
- **Risk: single-page layout objects under-model production PDFs.** Tables, sections, and figures can be non-contiguous or cross page boundaries; singular `page_number`/`bbox` is too narrow.

## Sources

### Kept

- PyMuPDF Appendix 1: Details on Text Extraction — official evidence for original-order extraction and `sort=True` limits: https://pymupdf.readthedocs.io/en/latest/app1.html
- PyMuPDF Text Recipes — official table extraction discussion and `find_tables()` context: https://pymupdf.readthedocs.io/en/latest/recipes-text.html
- PyMuPDF OCR Recipes — official OCR capability and speed/style tradeoffs: https://pymupdf.readthedocs.io/en/latest/recipes-ocr.html
- DoclingDocument Concepts — official Docling document model, body/furniture, provenance, layout: https://docling-project-docling.mintlify.app/concepts/docling-document
- DoclingDocument API — official item/table/picture/hierarchy API overview: https://docling-project-docling.mintlify.app/api/docling-document
- Azure Document Intelligence Analyze response — official spans, reading order, pages, paragraphs, tables, figures, sections, roles, bounding regions: https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept/analyze-document-response?view=doc-intel-4.0.0
- Google Document AI/Gemini layout parser — official layout/RAG, OCR+Gemini, chunks, tables, figures, limits: https://cloud.google.com/document-ai/docs/layout-parse-chunk
- Google Document AI ProcessOptions/LayoutConfig — official chunking config, bounding boxes, image/table annotation flags: https://docs.cloud.google.com/document-ai/docs/reference/rest/v1/ProcessOptions
- Unstructured open-source partitioning — official `partition_pdf` strategies and fallback behavior: https://docs.unstructured.io/open-source/core-functionality/partitioning
- Unstructured partitioning strategies — official speed/quality tradeoff framing: https://docs.unstructured.io/open-source/concepts/partitioning-strategies

### Dropped / lower weight

- Blog/commentary pages comparing parsers — excluded in favor of official docs and API references.
- GitHub discussions/issues except source-code-level Docling inspection — useful for nuance but not primary architecture evidence.
- Older ReadTheDocs mirror for Unstructured 0.12.6 — superseded by current docs.unstructured.io pages except where it confirmed the same strategy names.

## Gaps / next research steps

- Run an implementation spike on representative PDFs to verify Docling-to-`DocumentIR` span alignment, especially whitespace normalization, char-span semantics, tables, and furniture labels.
- Build a small evaluation set: two-column report, financial table with merged headers, scanned page, repeated header/footer, rotated page, figure with caption, and cross-page table.
- Decide whether visual-only provenance belongs in `DocumentLayout` now or a separate evidence model later. For production summarization of charts/images, it should be designed before enabling generated figure/table descriptions.
