from collections.abc import Iterable

from exeboard_ai.document_intelligence.core.ids import SpanId
from exeboard_ai.document_intelligence.ir.models import DocumentIR, TextSpan


class SpanIndex:
    def __init__(self, document: DocumentIR) -> None:
        self._document = document
        self._spans_by_id: dict[SpanId, TextSpan] = {}
        self._spans_by_page: dict[int, list[TextSpan]] = {}

        for page in document.pages:
            page_spans = sorted(page.spans, key=lambda span: span.reading_order)
            self._spans_by_page[page.page_number] = page_spans

            for span in page_spans:
                if span.span_id in self._spans_by_id:
                    raise ValueError(f"duplicate span_id: {span.span_id}")
                self._spans_by_id[span.span_id] = span

    @property
    def document(self) -> DocumentIR:
        return self._document

    def has_span(self, span_id: SpanId) -> bool:
        return span_id in self._spans_by_id

    def get_span(self, span_id: SpanId) -> TextSpan:
        try:
            return self._spans_by_id[span_id]
        except KeyError as exc:
            raise KeyError(f"unknown span_id: {span_id}") from exc

    def get_spans(self, span_ids: Iterable[SpanId]) -> list[TextSpan]:
        return [self.get_span(span_id) for span_id in span_ids]

    def get_page_spans(self, page_number: int) -> list[TextSpan]:
        return list(self._spans_by_page.get(page_number, []))

    def get_page_text(self, page_number: int) -> str:
        return self._join_span_text(self.get_page_spans(page_number))

    def get_text_for_spans(self, span_ids: Iterable[SpanId]) -> str:
        spans = self.get_spans(span_ids)
        ordered_spans = sorted(spans, key=lambda span: (span.page_number, span.reading_order))
        return self._join_span_text(ordered_spans)

    @staticmethod
    def _join_span_text(spans: Iterable[TextSpan]) -> str:
        return "\n".join(span.text for span in spans)
