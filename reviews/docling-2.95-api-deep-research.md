# Docling 2.95.0 API deep research for Exeboard layout-aware PDF adapter

## Summary

Docling 2.95.0 is usable for a layout-aware PDF adapter through `DocumentConverter` + `PdfFormatOption` + `PdfPipelineOptions`/`StandardPdfPipeline`, with conversion output in a Pydantic `DoclingDocument` that preserves reading-order hierarchy, stable JSON-pointer refs, pages, item provenance (`page_no`, `bbox`, `charspan`), table cell structure, and picture/caption links. The most important adapter cautions are: `iterate_items()` yields `(item, level)` tuples; item text is generally `.text` rather than the stale-docs-style `get_text()`; bounding boxes are in page coordinate space with explicit `CoordOrigin`; and default PDF conversion still has `do_ocr=True` and `do_table_structure=True`, so Slice 0 should make these explicit for predictable speed/quality.

## Version and source baseline

- **Docling release:** v2.95.0, uploaded 2026-05-21, Python `>=3.10,<4.0`, production/stable. PyPI exposes extras: `asr`, `easyocr`, `htmlrender`, `ocrmac`, `onnxruntime`, `rapidocr`, `remote-serving`, `tesserocr`, `vlm`, `xbrl`; the `docling` wheel is now a small meta-package depending on `docling-slim[standard]==2.95.0`. [PyPI JSON](https://pypi.org/pypi/docling/2.95.0/json), [docling package pyproject](https://github.com/docling-project/docling/blob/v2.95.0/packages/docling/pyproject.toml)
- **Core implementation checked:** v2.95.0 source for converter, pipeline options, pipeline, result models, settings, exceptions. [document_converter.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/document_converter.py), [pipeline_options.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/datamodel/pipeline_options.py), [standard_pdf_pipeline.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/pipeline/standard_pdf_pipeline.py), [datamodel/document.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/datamodel/document.py)
- **DoclingDocument source:** lives in `docling-core`; `docling-slim` depends on `docling-core>=2.73.0,<3.0.0`, so exact schema can float unless locked. Current PyPI latest observed is `docling-core 2.77.1`; source shows `DoclingDocument.version` schema `1.10.0`. [docling-slim pyproject](https://github.com/docling-project/docling/blob/v2.95.0/pyproject.toml), [docling-core PyPI](https://pypi.org/project/docling-core/), [docling-core document.py](https://github.com/docling-project/docling-core/blob/main/docling_core/types/doc/document.py)

## Converter construction and PDF pipeline configuration

### Constructor shape

`DocumentConverter` is still the top-level Python API:

```python
DocumentConverter(
    allowed_formats: Optional[list[InputFormat]] = None,
    format_options: Optional[dict[InputFormat, FormatOption]] = None,
)
```

- If `allowed_formats` is omitted, Docling allows every `InputFormat` enum value.
- If a format has no custom option, `_get_default_option()` supplies one.
- Default PDF option is `PdfFormatOption(pipeline_cls=StandardPdfPipeline, backend=DoclingParseDocumentBackend, backend_options=None)`.
- `FormatOption` auto-fills `pipeline_options` from `pipeline_cls.get_default_options()` when omitted.
- Pipelines are cached per converter by `(pipeline class, md5(pipeline_options.model_dump()))`, so one converter can safely reuse an initialized pipeline for multiple PDFs with identical options. [document_converter.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/document_converter.py), [official DocumentConverter docs](https://docling-project-docling.mintlify.app/api/document-converter)

### Recommended Exeboard Slice 0 construction

Make all defaults explicit, disable network-like behavior, and constrain to PDFs:

```python
from pathlib import Path
from docling.datamodel.base_models import InputFormat, ConversionStatus
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

pdf_opts = PdfPipelineOptions(
    do_ocr=False,                 # Slice 0: faster; turn on later for scanned PDFs
    do_table_structure=True,      # keep layout-aware table cells
    enable_remote_services=False, # default, but make explicit
    allow_external_plugins=False, # default, but make explicit
    artifacts_path=None,          # or Path("/models/docling") for offline deployments
)

converter = DocumentConverter(
    allowed_formats=[InputFormat.PDF],
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_opts),
    },
)

result = converter.convert(Path("sample.pdf"), raises_on_error=False)
if result.status not in {ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS}:
    raise RuntimeError([e.error_message for e in result.errors])
doc = result.document
```

`convert()` accepts a `Path`, URL string, or `DocumentStream`; `convert_all()` yields `ConversionResult`; `page_range=(start,end)` is validated as 1-based inclusive. [document_converter.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/document_converter.py), [settings.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/datamodel/settings.py)

### `StandardPdfPipeline`

`StandardPdfPipeline` is the default PDF/image/METS-GBS pipeline. It is a threaded, stage-based pipeline: preprocess → OCR → layout → table structure → assemble → reading order/enrichment. It initializes heavy models once per pipeline instance and uses per-run queues/threads for isolation. `get_default_options()` returns `ThreadedPdfPipelineOptions()`, which inherits all `PdfPipelineOptions` fields. [standard_pdf_pipeline.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/pipeline/standard_pdf_pipeline.py), [official StandardPdfPipeline docs](https://docling-project-docling.mintlify.app/api/pipelines/standard-pdf)

## `PdfPipelineOptions` fields that matter

Key defaults in v2.95.0:

| Field | Default | Adapter implication |
|---|---:|---|
| `do_table_structure` | `True` | Keep for layout-aware tables. |
| `do_ocr` | `True` | Consider `False` for Slice 0 programmatic PDFs; `True` increases latency. |
| `ocr_options` | `OcrAutoOptions(lang=[])` | Auto-selects OCR engine; specify engine/language later for deterministic OCR. |
| `table_structure_options` | `TableStructureOptions(mode=ACCURATE, do_cell_matching=True)` | TableFormer v1 default; v2 exists as `TableStructureV2Options`. |
| `layout_options` | `LayoutOptions(model_spec=DOCLING_LAYOUT_HERON, create_orphan_clusters=True)` | Heron is the default layout model. |
| `enable_remote_services` | `False` | Required for API/remote model calls; does **not** by itself prevent model artifact downloads. |
| `allow_external_plugins` | `False` | Keep false for deterministic/security-conscious adapter. |
| `artifacts_path` | `None` | If set, must be an existing directory; otherwise models may be fetched/cached on first use. |
| `generate_page_images` | `False` | Set true only if we need crops/images via `get_image()`. |
| `generate_picture_images` | `False` | Set true if adapter must emit embedded/cropped figure images. |
| `generate_table_images` | `False`, deprecated | Prefer page images + `TableItem.get_image()`. |
| `generate_parsed_pages` | `False` | Intermediate parsed pages cleared unless enabled. |
| threaded queue/batch fields | `ocr/layout/table_batch_size=4`, `queue_max_size=100`, poll `0.5s` | Mostly leave default in Slice 0. |

These fields are defined in source and reflected in the API docs. [pipeline_options.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/datamodel/pipeline_options.py), [PipelineOptions docs](https://docling-project-docling.mintlify.app/api/options/pipeline-options)

### Artifact and settings precedence

`BasePipeline` resolves artifacts as:

1. `pipeline_options.artifacts_path`, if set;
2. else global `docling.datamodel.settings.settings.artifacts_path` / `DOCLING_ARTIFACTS_PATH`;
3. else `None`, allowing normal model fetch/cache behavior.

If an artifacts path is set but is not a directory, pipeline initialization raises `RuntimeError`. `settings.cache_dir` defaults to `~/.cache/docling`; v2.95 also added a scoped settings context manager for temporary `perf/debug/inference` overrides. [base_pipeline.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/pipeline/base_pipeline.py), [settings.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/datamodel/settings.py), [v2.95.0 changelog](https://github.com/docling-project/docling/blob/v2.95.0/CHANGELOG.md)

## Conversion result and document object shape

`ConversionResult` extends `ConversionAssets` and contains:

- `input: InputDocument`
- `status: ConversionStatus`
- `errors: list[ErrorItem]`
- `pages: list[Page]` internal pipeline page objects
- `timings`, `confidence`
- `document: DoclingDocument`
- `assembled: AssembledUnit`
- `version: DoclingVersion` with `docling_version`, `docling_slim_version`, `docling_core_version`, `docling_ibm_models_version`, `docling_parse_version`, platform and Python versions. [datamodel/document.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/datamodel/document.py)

`ConversionStatus` values are: `pending`, `started`, `failure`, `success`, `partial_success`, `skipped`. `ErrorItem` has `component_type`, `module_name`, `error_message`. [base_models.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/datamodel/base_models.py)

```python
res = converter.convert("x.pdf", raises_on_error=False)
print(res.status, res.version.docling_version, res.version.docling_core_version)
for err in res.errors:
    print(err.component_type, err.module_name, err.error_message)
```

Exception types are minimal: `ConversionError`, `OperationNotAllowed`, `SecurityError`, all derived from `BaseError(RuntimeError)`. With `raises_on_error=True`, `DocumentConverter.convert_all()` raises `ConversionError` when status is not success/partial success; pipeline internals may raise a wrapped `RuntimeError("Pipeline ... failed")` from the original exception. [exceptions.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/exceptions.py), [document_converter.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/document_converter.py), [base_pipeline.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/pipeline/base_pipeline.py)

## `DoclingDocument` hierarchy and iteration

Core shape:

- `name`, `origin`, `version`
- root groups: `body`, deprecated `furniture`
- item arrays: `groups`, `texts`, `pictures`, `tables`, `key_value_items`, `form_items`, `field_regions`, `field_items`
- `pages: dict[int, PageItem]`

Every `NodeItem` has:

- `self_ref`: JSON pointer such as `#/texts/0` or `#/tables/2`
- `parent: RefItem | None`
- `children: list[RefItem]`
- `content_layer`: `body`, `furniture`, `background`, `invisible`, `notes`

`iterate_items()` source signature returns `Iterable[tuple[NodeItem, int]]`, i.e. `(item, level)`, not just item. It can include groups, traverse inside pictures, filter by page, and filter content layers. [docling-core document.py](https://github.com/docling-project/docling-core/blob/main/docling_core/types/doc/document.py), [DoclingDocument docs](https://docling-project-docling.mintlify.app/api/docling-document)

```python
from docling_core.types.doc import TextItem, TableItem, PictureItem, GroupItem, ContentLayer

for item, level in doc.iterate_items(
    with_groups=True,
    traverse_pictures=True,
    included_content_layers={ContentLayer.BODY},
):
    ref = item.self_ref
    label = getattr(item, "label", None)
    text = item.text if isinstance(item, TextItem) else None
    print(level, ref, label, text)
```

**Adapter rule:** use `isinstance(item, TextItem)` and `.text`/`.orig`; do not rely on stale examples that use `item.get_text()`. Table cells have a private `_get_text(doc=doc)` helper and `TableItem.export_to_dataframe(doc=doc)` for richer cells.

## Provenance, pages, and coordinates

### Page model

`DoclingDocument.pages` maps 1-based page numbers to `PageItem(page_no, size: Size, image: ImageRef | None)`. `Size` has `width`, `height`. The PDF pipeline also adds failed/skipped pages to `document.pages` to preserve page numbering/page breaks. [docling-core document.py](https://github.com/docling-project/docling-core/blob/main/docling_core/types/doc/document.py), [standard_pdf_pipeline.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/pipeline/standard_pdf_pipeline.py)

### Provenance fields

`ProvenanceItem` is:

```python
class ProvenanceItem(BaseModel):
    page_no: int
    bbox: BoundingBox
    charspan: tuple[int, int]  # 0-indexed
```

`DocItem.prov` is a list, so multi-page/multi-region items are possible. [docling-core document.py](https://github.com/docling-project/docling-core/blob/main/docling_core/types/doc/document.py)

### Bounding boxes

`BoundingBox(l, t, r, b, coord_origin=CoordOrigin.TOPLEFT)` supports `TOPLEFT` and `BOTTOMLEFT`, conversion with `to_top_left_origin(page_height)` / `to_bottom_left_origin(page_height)`, `normalized(page_size)`, scaling, IoU, union, and overlap methods. Coordinates are in the same page coordinate space as `doc.pages[page_no].size`; for PDF crops Docling scales by `images_scale` and uses 72 DPI when generating page images. Do **not** assume all bboxes are pixels or top-left—read `bbox.coord_origin` and normalize at the adapter boundary. [docling-core base.py](https://github.com/docling-project/docling-core/blob/main/docling_core/types/doc/base.py), [docling-core document.py](https://github.com/docling-project/docling-core/blob/main/docling_core/types/doc/document.py), [standard_pdf_pipeline.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/pipeline/standard_pdf_pipeline.py)

```python
from docling_core.types.doc import DocItem

for item, level in doc.iterate_items():
    if isinstance(item, DocItem):
        for prov in item.prov:
            page = doc.pages[prov.page_no]
            bbox_tl = prov.bbox.to_top_left_origin(page_height=page.size.height)
            bbox_norm = bbox_tl.normalized(page.size)
            # Store both raw and normalized for discovery.
```

## Tables and cells

`TableItem` is a `FloatingItem` with `data: TableData`, `label` default `TABLE`, captions/references/footnotes, optional image, and deprecated `annotations` migrated toward `meta`. [docling-core document.py](https://github.com/docling-project/docling-core/blob/main/docling_core/types/doc/document.py)

`TableData`:

- `table_cells: list[TableCell | RichTableCell]`
- `num_rows`, `num_cols`
- computed `grid: list[list[TableCell]]`
- helpers: row/column insertion/removal, `get_row_bounding_boxes()`, `get_column_bounding_boxes()`

`TableCell`:

- `bbox: BoundingBox | None`
- `row_span`, `col_span`
- `start_row_offset_idx`, `end_row_offset_idx`
- `start_col_offset_idx`, `end_col_offset_idx`
- `text`
- `column_header`, `row_header`, `row_section`, `fillable`

The start/end offset indices are effectively half-open grid intervals; spans should match `end-start`, but adapter should trust both and validate. Header semantics are boolean fields, not a single role enum. [docling-core document.py](https://github.com/docling-project/docling-core/blob/main/docling_core/types/doc/document.py)

```python
from docling_core.types.doc import TableItem, RichTableCell

for item, level in doc.iterate_items():
    if isinstance(item, TableItem):
        table_prov = item.prov[0] if item.prov else None
        caption = item.caption_text(doc) if item.captions else ""
        for cell in item.data.table_cells:
            cell_text = cell._get_text(doc=doc)  # works for normal and rich cells
            role = (
                "column_header" if cell.column_header else
                "row_header" if cell.row_header else
                "row_section" if cell.row_section else
                "body"
            )
            print(cell.start_row_offset_idx, cell.end_row_offset_idx,
                  cell.start_col_offset_idx, cell.end_col_offset_idx,
                  cell.row_span, cell.col_span, role, cell_text, cell.bbox)
```

## Pictures, figures, charts, and captions

`PictureItem` is a `FloatingItem` with:

- `label`: `PICTURE` or `CHART`
- `captions: list[RefItem]` inherited from `FloatingItem`
- `references`, `footnotes`
- `image: ImageRef | None`
- `meta: PictureMeta | None`, with `description`, `classification`, `molecule`, `tabular_chart`, `code`
- deprecated `annotations`, migrated into `meta` when possible

`caption_text(doc)` resolves caption refs and concatenates caption text. `get_image(doc)` returns `self.image` if present, otherwise crops from page image if available. `generate_picture_images=True` creates cropped images during PDF assembly; otherwise images may be absent even when picture bboxes exist. [docling-core document.py](https://github.com/docling-project/docling-core/blob/main/docling_core/types/doc/document.py), [standard_pdf_pipeline.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/pipeline/standard_pdf_pipeline.py)

```python
from docling_core.types.doc import PictureItem

for item, level in doc.iterate_items():
    if isinstance(item, PictureItem):
        caption = item.caption_text(doc) if item.captions else ""
        desc = item.meta.description.text if item.meta and item.meta.description else None
        cls = None
        if item.meta and item.meta.classification:
            cls = item.meta.classification.get_main_prediction().class_name
        print(item.self_ref, caption, desc, cls, item.prov)
```

## Stable refs and IDs

`self_ref` values are the stable in-document identifiers and are JSON-pointer-like (`#/texts/0`, `#/tables/0`, etc.). `RefItem.resolve(doc)` resolves a ref into the corresponding array item. These refs are stable for a serialized, immutable conversion result, but Docling mutation helpers (`delete_items`, insert/replace, normalize) can rewrite refs and child links. Exeboard should store `self_ref` as the Docling-native ID plus its own immutable adapter ID/hash for downstream persistence. [docling-core document.py](https://github.com/docling-project/docling-core/blob/main/docling_core/types/doc/document.py)

## Remote services, VLM, OCR, and defaults

- **Remote service calls:** `PipelineOptions.enable_remote_services=False` by default. API-based picture description explicitly requires `enable_remote_services=True`; factories for layout/table/picture-description receive this flag. Keep false for Slice 0. [pipeline_options.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/datamodel/pipeline_options.py), [base_pipeline.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/pipeline/base_pipeline.py), [standard_pdf_pipeline.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/pipeline/standard_pdf_pipeline.py)
- **External plugins:** `allow_external_plugins=False` by default and passed to OCR/layout/table/picture-description factories. Keep false unless we intentionally support third-party engines. [pipeline_options.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/datamodel/pipeline_options.py)
- **Model downloads:** `artifacts_path=None` means models are fetched from remote sources on first use; use `docling-tools models download` and point `artifacts_path`/`DOCLING_ARTIFACTS_PATH` at the directory for offline or reproducible environments. [pipeline_options.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/datamodel/pipeline_options.py), [base_pipeline.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/pipeline/base_pipeline.py)
- **OCR:** PDF default is `do_ocr=True` with `OcrAutoOptions(lang=[])`. Explicit OCR options include RapidOCR, EasyOCR, Tesseract CLI/Python, macOS Vision, and KServe v2 OCR. [pipeline_options.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/datamodel/pipeline_options.py)
- **VLM:** Standard PDF pipeline does not use `VlmPipelineOptions`; VLM conversion is separate. Defaults include `VlmConvertOptions.from_preset("granite_docling")`, while picture-description default options use `smolvlm` but `do_picture_description=False`. [pipeline_options.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/datamodel/pipeline_options.py)

## Obvious differences from v2.78.0 / Chub baseline

- **Packaging changed significantly:** v2.78.0 was a monolithic `docling` package with many dependencies in the main wheel; v2.95.0 makes `docling` a meta-package that depends on `docling-slim[standard]==2.95.0`, with fine-grained extras on `docling-slim`. This matters for Exeboard dependency locking and Docker image size. [v2.78 pyproject](https://github.com/docling-project/docling/blob/v2.78.0/pyproject.toml), [v2.95 docling pyproject](https://github.com/docling-project/docling/blob/v2.95.0/packages/docling/pyproject.toml), [v2.95 slim pyproject](https://github.com/docling-project/docling/blob/v2.95.0/pyproject.toml)
- **Docling-core lower bound moved:** v2.78.0 required `docling-core[chunking]>=2.66.0`; v2.95.0 `docling-slim` requires `docling-core>=2.73.0,<3.0.0` and uses separate `feat-chunking` extra. Lock `docling-core` in Exeboard if schema stability matters. [v2.78 pyproject](https://github.com/docling-project/docling/blob/v2.78.0/pyproject.toml), [v2.95 slim pyproject](https://github.com/docling-project/docling/blob/v2.95.0/pyproject.toml)
- **TableFormer v2 was already present in v2.78.0**, so no adapter-breaking difference there. Default remains `TableStructureOptions()` / TableFormer v1 accurate mode unless changed explicitly. [v2.78 pipeline_options.py](https://github.com/docling-project/docling/blob/v2.78.0/docling/datamodel/pipeline_options.py), [v2.95 pipeline_options.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/datamodel/pipeline_options.py)
- **Chart/VLM/OCR options expanded:** v2.95.0 adds richer chart extraction options, more VLM presets, KServe v2 OCR options, extraction prompt style, and `padding_side` on legacy picture VLM options. These are mostly irrelevant for Slice 0 unless we turn on chart/VLM enrichment. [v2.95 pipeline_options.py](https://github.com/docling-project/docling/blob/v2.95.0/docling/datamodel/pipeline_options.py), [v2.95 changelog](https://github.com/docling-project/docling/blob/v2.95.0/CHANGELOG.md)
- **v2.95.0 release itself is not PDF-adapter-breaking:** changelog entries are scoped settings, more callback metadata, HTML image headers, docx/CLI fixes. [v2.95.0 changelog](https://github.com/docling-project/docling/blob/v2.95.0/CHANGELOG.md)

## Concrete implications for Exeboard Slice 0 discovery and adapter plan

1. **Pin exact versions.** Use `docling==2.95.0` and also lock the resolved `docling-core` version in `uv.lock`/`requirements.lock`, because `docling-core` floats under `<3.0.0`.
2. **Use PDF-only converter.** Build one converter per option set with `allowed_formats=[InputFormat.PDF]` and explicit `PdfFormatOption`.
3. **Start with `do_ocr=False`, `do_table_structure=True`.** For born-digital PDFs this gives layout + tables with less latency. Add an OCR mode later for scanned PDFs; record `result.confidence.ocr_score` and empty-text heuristics during discovery.
4. **Capture raw Docling JSON in Slice 0.** Store `doc.export_to_dict(coord_precision=None)` or full `ConversionResult.save()` output for fixture PDFs so we can diff schema and provenance behavior.
5. **Normalize geometry at adapter boundary.** Emit both raw bbox `{l,t,r,b,origin,page_width,page_height}` and normalized top-left bbox. Do not assume pixels.
6. **Use hierarchy traversal, not flat arrays only.** `doc.texts`, `doc.tables`, etc. are storage arrays; reading order and nesting live in `body.children` and `iterate_items()`.
7. **Treat `self_ref` as source ID, not global ID.** Store it, but create Exeboard IDs stable across reprocessing via document hash + self_ref + provenance hash.
8. **Tables need two levels of geometry.** Capture table item provenance bbox plus each `TableCell.bbox`, spans, offset indices, and header booleans. Use `cell._get_text(doc=doc)` for rich cells.
9. **Pictures/captions are refs.** Resolve captions via `caption_text(doc)` or `captions` refs; do not assume caption is adjacent text. Enable `generate_picture_images` only if downstream needs image bytes.
10. **Error handling:** call `convert(..., raises_on_error=False)` in discovery so partial results are inspectable; accept `PARTIAL_SUCCESS` with errors attached.
11. **No remote/plugin execution in Slice 0.** Keep `enable_remote_services=False`, `allow_external_plugins=False`, and set `artifacts_path` in CI/offline environments.

## Minimal adapter extraction sketch

```python
from docling_core.types.doc import DocItem, TextItem, TableItem, PictureItem, ContentLayer


def iter_exeboard_blocks(doc):
    for item, level in doc.iterate_items(
        with_groups=True,
        traverse_pictures=True,
        included_content_layers={ContentLayer.BODY},
    ):
        provs = []
        if isinstance(item, DocItem):
            for p in item.prov:
                page = doc.pages.get(p.page_no)
                if not page:
                    continue
                bbox_tl = p.bbox.to_top_left_origin(page.size.height)
                provs.append({
                    "page_no": p.page_no,
                    "bbox": p.bbox.model_dump(mode="json"),
                    "bbox_top_left": bbox_tl.model_dump(mode="json"),
                    "bbox_norm_top_left": bbox_tl.normalized(page.size).model_dump(mode="json"),
                    "charspan": p.charspan,
                    "page_size": page.size.model_dump(mode="json"),
                })

        if isinstance(item, TextItem):
            yield {"kind": "text", "ref": item.self_ref, "level": level,
                   "label": item.label.value, "text": item.text, "orig": item.orig,
                   "provenance": provs}
        elif isinstance(item, TableItem):
            yield {"kind": "table", "ref": item.self_ref, "level": level,
                   "label": item.label.value, "caption": item.caption_text(doc),
                   "rows": item.data.num_rows, "cols": item.data.num_cols,
                   "cells": [
                       {"text": c._get_text(doc=doc),
                        "row0": c.start_row_offset_idx, "row1": c.end_row_offset_idx,
                        "col0": c.start_col_offset_idx, "col1": c.end_col_offset_idx,
                        "row_span": c.row_span, "col_span": c.col_span,
                        "column_header": c.column_header, "row_header": c.row_header,
                        "row_section": c.row_section,
                        "bbox": c.bbox.model_dump(mode="json") if c.bbox else None}
                       for c in item.data.table_cells
                   ], "provenance": provs}
        elif isinstance(item, PictureItem):
            yield {"kind": "picture", "ref": item.self_ref, "level": level,
                   "caption": item.caption_text(doc), "provenance": provs}
```

## Sources kept

- [Docling PyPI 2.95.0 JSON](https://pypi.org/pypi/docling/2.95.0/json) — release metadata, Python support, extras, meta-package dependencies.
- [Docling v2.95.0 changelog](https://github.com/docling-project/docling/blob/v2.95.0/CHANGELOG.md) — exact release notes and v2.78 comparison anchor.
- [v2.95.0 `document_converter.py`](https://github.com/docling-project/docling/blob/v2.95.0/docling/document_converter.py) — authoritative constructor, defaults, conversion status handling, pipeline cache.
- [v2.95.0 `pipeline_options.py`](https://github.com/docling-project/docling/blob/v2.95.0/docling/datamodel/pipeline_options.py) — authoritative PDF/OCR/table/VLM defaults.
- [v2.95.0 `standard_pdf_pipeline.py`](https://github.com/docling-project/docling/blob/v2.95.0/docling/pipeline/standard_pdf_pipeline.py) — actual threaded PDF stages, image generation, failed-page handling.
- [v2.95.0 `datamodel/document.py`](https://github.com/docling-project/docling/blob/v2.95.0/docling/datamodel/document.py) — `ConversionResult`, `DoclingVersion`, input/result shape.
- [docling-core `document.py`](https://github.com/docling-project/docling-core/blob/main/docling_core/types/doc/document.py) and [base.py](https://github.com/docling-project/docling-core/blob/main/docling_core/types/doc/base.py) — `DoclingDocument`, items, provenance, tables, pictures, refs, coordinates.
- [Official API docs: DocumentConverter](https://docling-project-docling.mintlify.app/api/document-converter), [PipelineOptions](https://docling-project-docling.mintlify.app/api/options/pipeline-options), [StandardPdfPipeline](https://docling-project-docling.mintlify.app/api/pipelines/standard-pdf), [DoclingDocument](https://docling-project-docling.mintlify.app/api/docling-document) — public docs cross-check.
- [v2.78.0 pyproject](https://github.com/docling-project/docling/blob/v2.78.0/pyproject.toml) and [v2.78.0 pipeline_options.py](https://github.com/docling-project/docling/blob/v2.78.0/docling/datamodel/pipeline_options.py) — comparison baseline.

## Gaps / things to verify with fixtures

- Official docs do not precisely state PDF coordinate units; source indicates page coordinate space with explicit origin and image scaling, but Slice 0 should empirically confirm whether our target PDFs expose page sizes in PDF points and how rotations are represented.
- Exact OCR engine chosen by `OcrAutoOptions` depends on installed extras/runtime; log it in discovery or avoid auto by disabling OCR initially.
- `docling-core` is not pinned by `docling==2.95.0`; fixture schema may change if dependency resolution changes. Lock it.
