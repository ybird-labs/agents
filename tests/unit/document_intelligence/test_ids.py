import pytest

from exeboard_ai.document_intelligence.core.ids import (
    make_chunk_id,
    make_claim_id,
    make_document_id_from_file_name,
    make_page_id,
    make_span_id,
    parse_chunk_id,
    parse_claim_id,
    parse_page_id,
    parse_span_id,
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


def test_parse_page_id_extracts_document_and_page() -> None:
    assert parse_page_id(f"{DOCUMENT_ID}:p0001") == (DOCUMENT_ID, 1)


def test_parse_page_id_round_trips_generated_ids_with_large_page_numbers() -> None:
    page_id = make_page_id(DOCUMENT_ID, 10000)

    assert page_id == f"{DOCUMENT_ID}:p10000"
    assert parse_page_id(page_id) == (DOCUMENT_ID, 10000)


def test_parse_span_id_extracts_document_page_and_span_index() -> None:
    assert parse_span_id(f"{DOCUMENT_ID}:p0001:s0002") == (DOCUMENT_ID, 1, 2)


def test_parse_span_id_round_trips_generated_ids_with_large_page_and_span_numbers() -> None:
    span_id = make_span_id(DOCUMENT_ID, 10000, 10000)

    assert span_id == f"{DOCUMENT_ID}:p10000:s10000"
    assert parse_span_id(span_id) == (DOCUMENT_ID, 10000, 10000)


@pytest.mark.parametrize(
    "page_id",
    [
        "not-a-page-id",
        f"{DOCUMENT_ID}:page0001",
        f"{DOCUMENT_ID}:p001",
        f"{DOCUMENT_ID}:p00001",
        f"{DOCUMENT_ID}:p0000",
    ],
)
def test_parse_page_id_rejects_malformed_values(page_id: str) -> None:
    with pytest.raises(ValueError):
        parse_page_id(page_id)


@pytest.mark.parametrize(
    "span_id",
    [
        "not-a-span-id",
        f"{DOCUMENT_ID}:p0001:span0000",
        f"{DOCUMENT_ID}:p001:s0000",
        f"{DOCUMENT_ID}:p00001:s0000",
        f"{DOCUMENT_ID}:p0001:s001",
        f"{DOCUMENT_ID}:p0001:s00000",
        f"{DOCUMENT_ID}:p0000:s0000",
    ],
)
def test_parse_span_id_rejects_malformed_values(span_id: str) -> None:
    with pytest.raises(ValueError):
        parse_span_id(span_id)


def test_make_chunk_id_is_deterministic() -> None:
    expected = f"{DOCUMENT_ID}:c0000"

    assert make_chunk_id(DOCUMENT_ID, 0) == expected
    assert make_chunk_id(DOCUMENT_ID, 0) == expected


def test_parse_chunk_id_round_trips_generated_ids_with_large_chunk_indexes() -> None:
    chunk_id = make_chunk_id(DOCUMENT_ID, 10000)

    assert chunk_id == f"{DOCUMENT_ID}:c10000"
    assert parse_chunk_id(chunk_id) == (DOCUMENT_ID, 10000)


@pytest.mark.parametrize("chunk_id", [f"{DOCUMENT_ID}:c1", f"{DOCUMENT_ID}:c00001"])
def test_parse_chunk_id_rejects_non_canonical_ids(chunk_id: str) -> None:
    with pytest.raises(ValueError):
        parse_chunk_id(chunk_id)


def test_make_claim_id_is_deterministic() -> None:
    expected = f"{DOCUMENT_ID}:claim0000"

    assert make_claim_id(DOCUMENT_ID, 0) == expected
    assert make_claim_id(DOCUMENT_ID, 0) == expected


def test_parse_claim_id_round_trips_generated_ids_with_large_claim_indexes() -> None:
    claim_id = make_claim_id(DOCUMENT_ID, 10000)

    assert claim_id == f"{DOCUMENT_ID}:claim10000"
    assert parse_claim_id(claim_id) == (DOCUMENT_ID, 10000)


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
