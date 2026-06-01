import re
from uuid import UUID

DocumentId = str
PageId = str
SpanId = str
ChunkId = str
ClaimId = str

_CANONICAL_ID_NUMBER_PATTERN = r"(?:\d{4}|[1-9]\d{4,})"
_PAGE_ID_PATTERN = re.compile(
    rf"^(?P<document_id>[^:]+):p(?P<page_number>{_CANONICAL_ID_NUMBER_PATTERN})$"
)
_SPAN_ID_PATTERN = re.compile(
    rf"^(?P<document_id>[^:]+):p(?P<page_number>{_CANONICAL_ID_NUMBER_PATTERN})"
    rf":s(?P<span_index>{_CANONICAL_ID_NUMBER_PATTERN})$"
)
_CHUNK_ID_PATTERN = re.compile(
    rf"^(?P<document_id>[^:]+):c(?P<chunk_index>{_CANONICAL_ID_NUMBER_PATTERN})$"
)
_CLAIM_ID_PATTERN = re.compile(
    rf"^(?P<document_id>[^:]+):claim(?P<claim_index>{_CANONICAL_ID_NUMBER_PATTERN})$"
)


def validate_document_id(document_id: str) -> DocumentId:
    try:
        return str(UUID(document_id))
    except ValueError as exc:
        raise ValueError("document_id must be a valid UUID") from exc


def make_document_id_from_file_name(file_name: str) -> DocumentId:
    stem, separator, extension = file_name.rpartition(".")
    if not separator or not stem or not extension:
        raise ValueError("file_name must use the '<uuid>.<extension>' format")
    return validate_document_id(stem)


def _validate_positive_page_number(page_number: int) -> None:
    if page_number < 1:
        raise ValueError("page_number must be 1 or greater")


def _validate_non_negative_index(name: str, value: int) -> None:
    if value < 0:
        raise ValueError(f"{name} must be 0 or greater")


def make_page_id(document_id: DocumentId, page_number: int) -> PageId:
    document_id = validate_document_id(document_id)
    _validate_positive_page_number(page_number)
    return f"{document_id}:p{page_number:04d}"


def make_span_id(
    document_id: DocumentId,
    page_number: int,
    span_index: int,
) -> SpanId:
    document_id = validate_document_id(document_id)
    _validate_positive_page_number(page_number)
    _validate_non_negative_index("span_index", span_index)
    return f"{document_id}:p{page_number:04d}:s{span_index:04d}"


def parse_page_id(page_id: PageId) -> tuple[DocumentId, int]:
    match = _PAGE_ID_PATTERN.fullmatch(page_id)
    if match is None:
        raise ValueError(
            "page_id must use the '<document_id>:p0001' format with canonical page digits"
        )

    document_id = validate_document_id(match.group("document_id"))
    page_number = int(match.group("page_number"))
    _validate_positive_page_number(page_number)
    return document_id, page_number


def parse_span_id(span_id: SpanId) -> tuple[DocumentId, int, int]:
    match = _SPAN_ID_PATTERN.fullmatch(span_id)
    if match is None:
        raise ValueError(
            "span_id must use the '<document_id>:p0001:s0000' format with canonical page/span digits"
        )

    document_id = validate_document_id(match.group("document_id"))
    page_number = int(match.group("page_number"))
    span_index = int(match.group("span_index"))
    _validate_positive_page_number(page_number)
    _validate_non_negative_index("span_index", span_index)
    return document_id, page_number, span_index


def parse_chunk_id(chunk_id: ChunkId) -> tuple[DocumentId, int]:
    match = _CHUNK_ID_PATTERN.fullmatch(chunk_id)
    if match is None:
        raise ValueError("chunk_id must use '<document_id>:c0000' format")

    document_id = validate_document_id(match.group("document_id"))
    chunk_index = int(match.group("chunk_index"))
    _validate_non_negative_index("chunk_index", chunk_index)
    return document_id, chunk_index


def parse_claim_id(claim_id: ClaimId) -> tuple[DocumentId, int]:
    match = _CLAIM_ID_PATTERN.fullmatch(claim_id)
    if match is None:
        raise ValueError("claim_id must use '<document_id>:claim0000' format")

    document_id = validate_document_id(match.group("document_id"))
    claim_index = int(match.group("claim_index"))
    _validate_non_negative_index("claim_index", claim_index)
    return document_id, claim_index


def make_chunk_id(document_id: DocumentId, chunk_index: int) -> ChunkId:
    document_id = validate_document_id(document_id)
    _validate_non_negative_index("chunk_index", chunk_index)
    return f"{document_id}:c{chunk_index:04d}"


def make_claim_id(document_id: DocumentId, claim_index: int) -> ClaimId:
    document_id = validate_document_id(document_id)
    _validate_non_negative_index("claim_index", claim_index)
    return f"{document_id}:claim{claim_index:04d}"
