from pathlib import Path

from exeboard_ai.document_intelligence.ir.models import DocumentIR, DocumentSource
from exeboard_ai.document_intelligence.parsing.ports import (
    DocumentParseError,
    DocumentParser,
    EncryptedDocumentError,
    LayoutExtractionError,
    NoExtractableTextError,
    SpanAlignmentError,
    UnreadableDocumentError,
)

DOCUMENT_ID = "550e8400-e29b-41d4-a716-446655440000"


class FakeParser:
    def parse(self, path: Path) -> DocumentIR:
        return DocumentIR(
            document_id=DOCUMENT_ID,
            source=DocumentSource(file_name=path.name, file_extension="pdf"),
            content="",
            pages=[],
        )


def _parse_with(parser: DocumentParser, path: Path) -> DocumentIR:
    return parser.parse(path)


def test_document_parser_protocol_accepts_structural_parser() -> None:
    document = _parse_with(FakeParser(), Path(f"{DOCUMENT_ID}.pdf"))

    assert document.document_id == DOCUMENT_ID
    assert document.source.file_name == f"{DOCUMENT_ID}.pdf"


def test_parser_specific_errors_are_parser_port_errors() -> None:
    assert issubclass(EncryptedDocumentError, DocumentParseError)
    assert issubclass(UnreadableDocumentError, DocumentParseError)
    assert issubclass(NoExtractableTextError, DocumentParseError)
    assert issubclass(LayoutExtractionError, DocumentParseError)
    assert issubclass(SpanAlignmentError, DocumentParseError)
