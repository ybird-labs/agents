# Document Intelligence ID Semantics

## Purpose

IDs provide stable provenance for evidence-backed summaries.

A final summary claim must be traceable back to:

```text
document -> page -> span
```

## Document file naming convention

Input documents are named:

```text
<uuid>.<file_extension>
```

Example:

```text
550e8400-e29b-41d4-a716-446655440000.pdf
```

The document ID is the UUID stem:

```text
550e8400-e29b-41d4-a716-446655440000
```

The file extension is source/file metadata. It is not part of the document ID.

## DocumentId

`DocumentId` is a canonical UUID string.

Rules:

- must parse as a UUID
- is canonicalized with `str(UUID(document_id))`
- must not be derived by sanitizing arbitrary display names
- must not depend on a local filesystem path

Examples:

```text
550e8400-e29b-41d4-a716-446655440000
```

Non-examples:

```text
contract
board_minutes_2024
/tmp/upload/contract.pdf
```

## File-name to DocumentId helper

The helper:

```python
make_document_id_from_file_name(file_name: str) -> DocumentId
```

expects:

```text
<uuid>.<extension>
```

and returns the canonical UUID stem.

Example:

```python
make_document_id_from_file_name(
    "550e8400-e29b-41d4-a716-446655440000.pdf"
)
```

returns:

```text
550e8400-e29b-41d4-a716-446655440000
```

Invalid examples:

```text
contract.pdf
550e8400-e29b-41d4-a716-446655440000
.pdf
```

## Composite provenance IDs

Page, span, chunk, and claim IDs are derived from `DocumentId` plus local indexes.

Formats:

```text
PageId:  <document_uuid>:p<page_number_4_digits>
SpanId:  <document_uuid>:p<page_number_4_digits>:s<span_index_4_digits>
ChunkId: <document_uuid>:c<chunk_index_4_digits>
ClaimId: <document_uuid>:claim<claim_index_4_digits>
```

Examples:

```text
550e8400-e29b-41d4-a716-446655440000:p0001
550e8400-e29b-41d4-a716-446655440000:p0001:s0000
550e8400-e29b-41d4-a716-446655440000:c0000
550e8400-e29b-41d4-a716-446655440000:claim0000
```

## Indexing rules

- `page_number` is 1-based.
- `span_index` is 0-based within a page.
- `chunk_index` is 0-based within a document.
- `claim_index` is 0-based within a document or summarization run.

## Why this design

- UUID document names avoid display-name/path collisions.
- Composite IDs make provenance readable.
- Fixed-width numeric fields sort naturally in logs and JSON.
- The parser can derive `DocumentId` from the file name but should still store source metadata separately in the IR.
