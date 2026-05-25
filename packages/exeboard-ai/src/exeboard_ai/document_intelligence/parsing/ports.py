from pathlib import Path
from typing import Protocol

from exeboard_ai.document_intelligence.ir.models import DocumentIR


class DocumentParser(Protocol):
    def parse(self, path: Path) -> DocumentIR: ...
