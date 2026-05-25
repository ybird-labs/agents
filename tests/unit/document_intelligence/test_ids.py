import pytest

from exeboard_ai.document_intelligence.core.ids import (
    make_chunk_id,
    make_claim_id,
    make_document_id_from_file_name,
    make_page_id,
    make_span_id,
    validate_document_id,
)

DOCUMENT_ID = "550e8400-e29b-41d4-a716-446655440000"


def test_validate_document_id_accepts_and_canonicalizes_uuid() -> None:
    assert validate_document_id("550E8400-E29B-41D4-A716-446655440000") == DOCUMENT_ID


def test_validate_document_id_rejects_invalid_uuid() -> None:
    with pytest.raises(ValueError, match="document_id must be a valid UUID"):
        validate_document_id("not-a-uuid")


def test_make_document_id_from_file_name_extracts_uuid_stem() -> None:
    assert make_document_id_from_file_name(f"{DOCUMENT_ID}.pdf") == DOCUMENT_ID


def test_make_document_id_from_file_name_rejects_missing_extension() -> None:
    with pytest.raises(ValueError, match="<uuid>.<extension>"):
        make_document_id_from_file_name(DOCUMENT_ID)


def test_make_document_id_from_file_name_rejects_non_uuid_stem() -> None:
    with pytest.raises(ValueError, match="document_id must be a valid UUID"):
        make_document_id_from_file_name("contract.pdf")


def test_make_page_id_is_deterministic() -> None:
    expected = f"{DOCUMENT_ID}:p0001"

    assert make_page_id(DOCUMENT_ID, 1) == expected
    assert make_page_id(DOCUMENT_ID, 1) == expected


def test_make_span_id_includes_document_page_and_span_index() -> None:
    assert make_span_id(DOCUMENT_ID, 1, 0) == f"{DOCUMENT_ID}:p0001:s0000"


def test_make_chunk_id_is_deterministic() -> None:
    expected = f"{DOCUMENT_ID}:c0000"

    assert make_chunk_id(DOCUMENT_ID, 0) == expected
    assert make_chunk_id(DOCUMENT_ID, 0) == expected


def test_make_claim_id_is_deterministic() -> None:
    expected = f"{DOCUMENT_ID}:claim0000"

    assert make_claim_id(DOCUMENT_ID, 0) == expected
    assert make_claim_id(DOCUMENT_ID, 0) == expected


@pytest.mark.parametrize("page_number", [0, -1])
def test_page_number_must_be_positive(page_number: int) -> None:
    with pytest.raises(ValueError, match="page_number must be 1 or greater"):
        make_page_id(DOCUMENT_ID, page_number)

    with pytest.raises(ValueError, match="page_number must be 1 or greater"):
        make_span_id(DOCUMENT_ID, page_number, 0)


@pytest.mark.parametrize(
    ("factory", "expected_message"),
    [
        (lambda: make_span_id(DOCUMENT_ID, 1, -1), "span_index must be 0 or greater"),
        (lambda: make_chunk_id(DOCUMENT_ID, -1), "chunk_index must be 0 or greater"),
        (lambda: make_claim_id(DOCUMENT_ID, -1), "claim_index must be 0 or greater"),
    ],
)
def test_indexes_must_be_non_negative(factory, expected_message: str) -> None:
    with pytest.raises(ValueError, match=expected_message):
        factory()
