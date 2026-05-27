# PDF Parsing Plan Architecture Review

## Verdict

Approve the plan with important corrections to apply before coding the layout models. I found no blocker to the architecture decision itself.

The plan correctly ties the rejected shortcuts to the need for a layout-aware adapter, keeps the citation substrate parser-neutral, and correctly sequences layout IR before Docling adapter work.

## Blockers

- None for plan approval.

## Important corrections before implementation

1. **Do not freeze a one-page-only layout/table model.** The sketch gives `LayoutBlock`, `Table`, and `Figure` a single `page_number` and optional single `bbox` (`docs/document-intelligence/pdf-parsing-strategy.md:187`, `:195`, `:213`, `:217`). That is acceptable as a sketch, but the first real model should support per-page bounding regions or an explicit continuation model before the Docling adapter is built. Multi-page tables, repeated table headers, captions separated from figures, and section blocks crossing page boundaries are common in business PDFs. If the IR hardcodes one page per table/figure, the adapter will have to fragment a single semantic object into unrelated objects, and layout-aware chunking will lose row/column/header continuity.

2. **Clarify the span requirement for non-text layout objects.** The guard says every layout object must reference existing `SpanId`s (`docs/document-intelligence/pdf-parsing-strategy.md:24`), and the figure sketch has `source_span_ids` plus `caption_span_ids` (`docs/document-intelligence/pdf-parsing-strategy.md:215-216`). For purely visual figures or non-text decorations, there may be no citeable text span. Do not force fake spans just to satisfy the model; that would corrupt the citation source of truth. The safer invariant is: text-bearing blocks/cells must cite existing spans; non-text figures may carry page/bbox provenance with empty text spans, and any claim based on visual/OCR content must first materialize citeable OCR/vision text spans.

3. **Decide text-span granularity for table cells before adapter code.** Current PyMuPDF extraction creates line-level spans from `get_text("dict", sort=True)` (`packages/exeboard-ai/src/exeboard_ai/document_intelligence/parsing/adapters/pymupdf.py:116`, `:132-144`). The plan requires table cells to cite `source_span_ids` (`docs/document-intelligence/pdf-parsing-strategy.md:197`, `:207`). A Docling adapter should not map an entire row or table line span into every cell just to satisfy the field: that makes citations syntactically valid but too coarse to prove cell-level row/column context. The layout IR/tests should require cell text to reconstruct from its cited spans, or explicitly mark derived/non-authoritative text.

4. **Put layout reference validation at the `DocumentIR`/constructor-helper boundary.** `DocumentIR` currently owns `content`, `pages`, and the span/content consistency checks (`packages/exeboard-ai/src/exeboard_ai/document_intelligence/ir/models.py:125-133`, `:164-169`). A standalone `DocumentLayout` cannot prove that a `SpanId` exists in the same document unless it receives the parent document/span index. If `layout: DocumentLayout | None` is added as recommended (`docs/document-intelligence/pdf-parsing-strategy.md:346`), the same model-level validator or a required construction helper should verify referenced span existence, page/bounding-region compatibility, and `parser_run_id` membership in `parser_runs`.

## Correct

- **Rejected shortcuts are connected to the adapter decision.** The document explicitly recommends option 3: keep `DocumentIR.content`, `Page`, and `TextSpan` as the citation source while adding layout models and a Docling-backed adapter (`docs/document-intelligence/pdf-parsing-strategy.md:17`, `:20`). It then names the shortcuts the adapter is meant to avoid (`docs/document-intelligence/pdf-parsing-strategy.md:22`, `:253-285`). This is not hand-wavy: the current parser really uses PyMuPDF coordinate sorting (`pymupdf.py:116`), and the current chunker consumes spans sorted only by `(page_number, reading_order)` (`packages/exeboard-ai/src/exeboard_ai/document_intelligence/chunking/chunker.py:46-48`).

- **The layout layer over `SpanId`s is sound.** Existing citation and validation are span-centric: `TextSpan` carries text, canonical char offsets, page number, reading order, and optional bbox (`packages/exeboard-ai/src/exeboard_ai/document_intelligence/ir/models.py:77-86`), and `DocumentIR` validates that span text matches the document content slice (`models.py:168-169`). The citation validator checks cited span existence and page agreement through `SpanIndex` (`packages/exeboard-ai/src/exeboard_ai/document_intelligence/validation/citation_validator.py:113-134`). Replacing this with Docling-native objects would couple chunking/validation/summarization to one parser shape; the plan correctly rejects that (`docs/document-intelligence/pdf-parsing-strategy.md:281-285`).

- **Layout IR should be implemented before the Docling adapter.** The parser port currently returns `DocumentIR` (`packages/exeboard-ai/src/exeboard_ai/document_intelligence/parsing/ports.py:23-24`), and `DocumentIR` has no layout field today (`ir/models.py:125-133`). Building Docling adapter code first would force one of three bad shortcuts: discard Docling structure, leak Docling-native objects past the parser boundary, or create throwaway private models that downstream code cannot depend on. The plan correctly says to add owned layout IR/tests first, then translate Docling output into it (`docs/document-intelligence/pdf-parsing-strategy.md:318-346`, `:348-364`).

- **Keeping PyMuPDF as a baseline and OCR as explicit is correct.** The current adapter already reports no-text pages with an OCR-not-attempted warning and raises on fully textless PDFs (`packages/exeboard-ai/src/exeboard_ai/document_intelligence/parsing/adapters/pymupdf.py:69-73`). The plan preserves that behavior instead of hiding OCR/layout costs and failure modes behind a parser selected for fast native text (`docs/document-intelligence/pdf-parsing-strategy.md:73-85`, `:95-108`).

## Approval / rejection

Approved with the corrections above. The next implementation step should be **layout IR models and tests**, not Docling adapter code. Do not build the Docling adapter first: without stable owned layout models, the adapter either loses the value of Docling's structure or creates parser-native coupling that the plan is explicitly trying to avoid.
