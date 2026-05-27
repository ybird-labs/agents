## Review

**Verdict:** SpanIndex is architecturally aligned and functionally correct for the stated tutorial step and the requested validator/chunker lookup API. No blocker found. Proceed to chunking is reasonable, with a few non-blocking hardening/test recommendations below.

- **Correct:** `SpanIndex` stays inside the document-intelligence IR layer and depends only on `core.ids` and IR models (`span_index.py:1-4`), matching the tutorial placement and purpose (`docs/document-intelligence/tutorial.md:405-424`).
- **Correct:** Required lookup API is present: `has_span`, `get_span`, `get_spans`, `get_page_spans`, `get_page_text`, and `get_text_for_spans` (`span_index.py:22-47`).
- **Correct:** Missing `get_span` raises `KeyError` with a clear message (`span_index.py:29-33`), and the unit test covers it (`test_span_index.py:60-64`).
- **Correct:** Page spans are sorted by `reading_order` during indexing (`span_index.py:13-15`), `get_page_spans` returns a defensive list copy (`span_index.py:38-39`), and tests verify page text/page span ordering (`test_span_index.py:87-98`).
- **Correct:** `get_text_for_spans` sorts selected spans by document-order fields rather than preserving input order (`span_index.py:44-47`), and the test covers reversed same-page input (`test_span_index.py:101-111`).
- **Correct:** Duplicate span IDs are rejected (`span_index.py:17-20`) and tested (`test_span_index.py:120-154`), which supports the research/tutorial emphasis on durable source-span provenance (`research/file-structure-domain-slices.md:19-21`, `docs/document-intelligence/tutorial.md:611-614`).
- **Correct:** `DocumentIR` validates span offsets against canonical content (`models.py:136-145`) and page/span page-number consistency (`models.py:106-111`), so SpanIndex can rely on validated span text and page membership.

- **Fixed:** None. Review was read-only for source files.

- **Blocker:** None.

- **Note:** The documented checkpoint command `uv run pytest ...` did not work directly in this environment because `pytest` is not installed as a dependency (`Failed to spawn: pytest`). I verified the tests with a transient pytest dependency instead: `uv run --with pytest pytest tests/unit/document_intelligence/test_span_index.py tests/unit/document_intelligence/test_ir_models.py` — 17 passed.
- **Note:** `SpanIndex` currently overwrites `_spans_by_page[page.page_number]` if `DocumentIR.pages` contains duplicate page numbers (`span_index.py:13-15`), while `DocumentIR` does not enforce unique page numbers (`models.py:136-145` only validates span offsets). Recommended hardening: reject duplicate page numbers in `DocumentIR` or in `SpanIndex`, and add a unit test.
- **Note:** `get_text_for_spans` sorts by `(page_number, reading_order)` (`span_index.py:44-47`). That matches the current requirement, but canonical `char_start`/`char_end` are the strongest document-order signal in this IR (`models.py:80-85`). Recommended hardening: add a cross-page reversed-input test and consider `char_start` as a tie-breaker or primary sort key if future parsers can emit duplicate/ambiguous reading orders.

**Recommended changes before/while implementing chunking:**
1. Add a test for `get_text_for_spans` with input from page 2 before page 1 to lock cross-page document ordering.
2. Decide whether duplicate `Page.page_number` and duplicate per-page `reading_order` should be invalid IR; if yes, validate them at the model layer or reject them in `SpanIndex`.
3. Add `pytest` to the repo/workspace dev test dependencies if the tutorial checkpoint should run as written.

**Proceed to chunking:** Yes. The current SpanIndex is sufficient for the initial chunker requirement that chunks are in document order and every chunk source span ID exists in `SpanIndex` (`docs/document-intelligence/tutorial.md:593-614`).
