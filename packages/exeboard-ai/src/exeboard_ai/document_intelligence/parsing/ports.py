from pathlib import Path
from typing import Protocol

from exeboard_ai.document_intelligence.ir.models import DocumentIR


class DocumentParseError(Exception):
    """Base exception for parser-port failures."""


class EncryptedDocumentError(DocumentParseError):
    """Raised when a parser cannot parse an encrypted document."""


class UnreadableDocumentError(DocumentParseError):
    """Raised when a parser cannot open or read a document."""


class NoExtractableTextError(DocumentParseError):
    """Raised when a parser succeeds but finds no extractable text."""


class LayoutExtractionError(DocumentParseError):
    """Raised when a selected layout-aware parser cannot produce required layout."""


class SpanAlignmentError(DocumentParseError):
    """Raised when parser-native text/layout cannot be aligned to DocumentIR spans."""


class DocumentParser(Protocol):
    def parse(self, path: Path) -> DocumentIR: ...
