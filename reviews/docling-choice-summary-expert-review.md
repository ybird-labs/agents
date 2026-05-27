# Expert review: Docling as next layout-aware PDF parser adapter

Date: 2026-05-26

## 1. Research performed

Fresh research was performed before review. Sources relied on:

- Docling `DoclingDocument` concept docs — unified document representation with text, tables, pictures, hierarchy, body/furniture grouping, layout bboxes, and provenance: <https://docling-project-docling.mintlify.app/concepts/docling-document>
- Docling core model source — `ProvenanceItem` / document data structures including page, bbox, charspan-style provenance and table cell fields: <https://github.com/docling-project/docling-core/blob/main/docling_core/types/doc/document.py>
- Docling Technical Report — describes PDF pipeline using programmatic text tokens with coordinates, layout analysis, table structure recognition, reading order, figures: <https://arxiv.org/pdf/2408.09869>
- Docling paper, “Docling: An Efficient Open-Source Toolkit for AI-driven Document Conversion” — local, MIT-licensed, structured document conversion with layout/table models: <https://arxiv.org/html/2501.17887>
- Docling pipeline/options docs — `PipelineOptions(enable_remote_services=False, allow_external_plugins=False)` and `PdfPipelineOptions(do_ocr=...)`: <https://docling-project-docling.mintlify.app/api/options/pipeline-options>
- Docling CLI options reference — OCR can be enabled/disabled; remote services default false, but OCR CLI default is documented as true: <https://docling-project-docling.mintlify.app/api/cli/options>
- “Correctness is not Faithfulness in Retrieval Augmented Generation Attributions” — distinguishes answer correctness from faithful citation/attribution: <https://dl.acm.org/doi/10.1145/3731120.3744592>
- PyMuPDF project/docs — strong low-level local PDF extraction/manipulation library, but not a full Exeboard-owned semantic layout adapter by itself: <https://github.com/pymupdf/PyMuPDF>

## 2. Verdict

**APPROVE the architectural choice of Docling as the next layout-aware local PDF parser adapter, with implementation gated by the plan’s Slice 0 discovery and the blockers below.**

Docling is the best next parser candidate for Exeboard’s evidence-backed summarization pipeline because it is local, open-source, layout-aware, table/figure-aware, and exposes structured provenance that can plausibly be translated into Exeboard-owned `DocumentIR` / `DocumentLayout` rather than replacing them. This fits the current IR direction: `DocumentIR.content` + `TextSpan` remain the citation source of truth; layout objects organize spans and visual regions.

Confidence: **high for the adapter choice**, **medium until real Docling API/config/provenance discovery is completed**.

## 3. Severity-ranked concerns

### Blockers before implementation

1. **Prove no silent OCR and no remote inference in real Docling configuration.**  
   Research confirms Docling has pipeline knobs such as `enable_remote_services=False` and PDF OCR options, but Docling CLI docs also show OCR defaulting to true. The adapter must explicitly construct PDF options with OCR disabled by default, and remote services/external plugins disabled. Do not rely on defaults.

2. **Complete Slice 0 API/provenance discovery before writing mapper logic.**  
   The plan correctly says not to map guessed object shapes. Implementation should stop unless real Docling output exposes stable public fields for pages, item reading order, labels, provenance page/bbox/charspan, tables/cells, figures/captions, coordinate semantics, and model/artifact behavior.

3. **Add `ParserDependencyError` before the adapter.**  
   `docling-adapter-plan.md` requires it, but current `parsing/ports.py` does not include it. Missing optional Docling must not leak `ImportError`.

4. **Fix the ID-width scale bug before Docling-generated span-heavy documents.**  
   `make_page_id()` / `make_span_id()` produce `:04d` minimum width, but `parse_page_id()` / `parse_span_id()` require exactly four digits. Page/span index `10000` will fail round-trip. Prefer `\d{4,}`.

5. **Span alignment must fail loudly.**  
   The approved path is to build `DocumentIR.content` from exact generated `TextSpan.text` while traversing Docling reading order, then attach layout objects to those span IDs. Do not consume only Docling Markdown or fuzzy-align without a hard `SpanAlignmentError` path.

### High concerns

6. **Validate parser-run lineage more tightly.**  
   `DocumentLayout.parser_run_id` references an existing run, but `TextSpan.parser_run_id` is not currently validated against `parser_runs`. For a Docling adapter, spans cited by layout should either have the same parser run or a documented lineage rule. Otherwise later audit cannot prove layout and cited text came from the same conversion.

7. **Model/artifact downloads are operationally important.**  
   Docling is local, but layout/table models may require first-use artifacts. The adapter plan should record whether artifacts download, how to pin/cache/offline them, and should keep real integration tests opt-in.

8. **Coordinate normalization is a correctness boundary.**  
   Current IR uses only `pdf_points_top_left`. The adapter must document Docling bbox units/origin/page-number base/rotation behavior and normalize before model construction. Do not pass through raw Docling coordinates under Exeboard’s coordinate label.

### Medium concerns

9. **Current IR is mostly strong, but `frozen=True` with mutable lists is not fully immutable.**  
   `ParserRun.warnings`, `Page.spans`, `DocumentIR.parser_runs`, and `DocumentIR.pages` are lists. This is acceptable for the MVP if callers do not mutate after validation, but tuples would better preserve validated IR invariants.

10. **Table cell provenance permits text-only cells without visual regions.**  
    This is acceptable because `TextSpan` remains citeable, but if UI highlighting for cells matters, require either cell `bounding_regions` or span bboxes in adapter tests.

11. **Do not overclaim production quality from Docling alone.**  
    Docling is the right adapter to spike, not a guarantee. Production support still depends on fixtures for multi-column pages, repeated furniture, merged/cross-page tables, rotations, scanned PDFs with OCR disabled, figures/captions, and no-network/offline runs.

## 4. Alternatives compared

- **Keep only current PyMuPDF adapter:** reject as the next complex-PDF path. It remains valuable as a fast native-text baseline, but the current adapter does not provide semantic reading order, body/furniture classification, table/figure structure, or layout-level provenance. Extending it directly risks hiding layout/OCR complexity behind the wrong parser contract.

- **PyMuPDF + custom heuristics:** possible future targeted adapter, but weaker than Docling as the next step. Exeboard would need to build and maintain reading-order, table, figure, furniture, and hierarchy logic itself.

- **pdfplumber / Camelot:** useful specialized tools for coordinates and table extraction. They are not as strong as a primary general layout-aware document parser because they do not naturally cover the whole hierarchy/table/figure/body-furniture contract.

- **Unstructured:** viable future adapter, especially because it exposes explicit strategies. However, it is less attractive as the next citation substrate unless its output can provide stable span/page/bbox/table provenance without lossy flattening and without implicit OCR/remote behavior.

- **Azure Document Intelligence / Google Document AI:** strong layout/provenance APIs, but remote/cloud processing conflicts with the requested “no silent OCR/remote” local-first next adapter. Keep as explicit future cloud adapters, not the next default path.

- **Docling:** best fit now. It is local, structured, layout/table/figure-aware, has provenance concepts, and can be isolated behind Exeboard’s parser port without exposing native objects.

## 5. Required model fields/invariants to preserve

The current IR contract is directionally correct and should remain non-negotiable:

- `DocumentIR.content` and `TextSpan` are the citation source of truth.
- Every `TextSpan` must match `content[char_start:char_end]` exactly.
- Text-bearing layout blocks cite existing same-document `SpanId`s.
- Tables attach through table wrapper `LayoutBlock`s; no independent table reading-order namespace.
- Figures attach through figure wrapper `LayoutBlock`s; visual-only figures use `BoundingRegion`, not fake spans.
- `BoundingRegion` page numbers exist and bboxes fit page dimensions when dimensions are known.
- `DocumentLayout.parser_run_id` references an existing `ParserRun`.
- Duplicate parser runs, pages, spans, layout blocks, table IDs, figure IDs, and layout reading orders are rejected.
- Parent block references exist and parent cycles are rejected.
- Table cell row/column spans stay inside table bounds and do not overlap.
- Docling references, if stored, are strings only in `parser_element_ref`.

Recommended additional invariant before adapter completion:

- If `TextSpan.parser_run_id` is set, it must reference an existing parser run; Docling layout-cited spans should have parser lineage consistent with `DocumentLayout.parser_run_id` or a documented cross-run alignment rule.

## 6. Tests required

Minimum tests before approving a Docling adapter implementation:

1. Missing Docling dependency raises `ParserDependencyError`.
2. Default construction explicitly sets OCR disabled and remote services/external plugins disabled.
3. Generated scanned/image-only PDF with default `enable_ocr=False` does not produce OCR text.
4. Simple digital PDF yields `DocumentIR.layout` with non-empty blocks and exact span/content offsets.
5. Header/footer/page-number map to furniture, not body.
6. Table wrapper block links to `Table`; cells preserve row/column/spans/roles and cite spans or regions.
7. Figure wrapper block links to `Figure`; caption and visual-only provenance are represented without fake spans.
8. Invalid/missing bboxes for visual-only objects raise `LayoutExtractionError`.
9. Text-bearing item that cannot be associated to generated spans raises `SpanAlignmentError`.
10. Serialized `DocumentIR` contains no Docling-native objects.
11. Page/span ID round-trip works past index `9999`.
12. Opt-in real Docling integration tests are env-gated and do not require network during normal test runs.

## 7. Deferred/future concerns

- Layout-aware chunking remains future work; do not mix it into the adapter implementation.
- OCR should become a separately named strategy/configuration with explicit provenance, not fallback behavior.
- Cloud parsers can be added later behind the same `DocumentParser` boundary.
- Structured parser-run provenance may eventually deserve fields beyond free-form `warnings`.

## 8. Final recommendation

Proceed with Docling as the next layout-aware parser adapter **after** completing Slice 0 discovery and the small parser-port/ID hardening fixes. Keep PyMuPDF as the fast native-text baseline. Do not replace Exeboard IR with Docling’s model. Translate Docling into Exeboard-owned `DocumentIR`/`DocumentLayout`, keep citations grounded in `TextSpan`, and fail loudly on OCR, remote, layout, coordinate, or span-alignment uncertainty.
