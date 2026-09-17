"""HTML-to-clean-text extraction for downloaded SEC filing documents.

SEC filings are Inline XBRL documents: alongside the human-readable body they
embed a large `display:none` block of XBRL tagging metadata (contexts, units,
hidden facts) that must not leak into the extracted text.
"""

import re
from html.parser import HTMLParser

_SKIP_TAGS = {"script", "style"}
_VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}


class _TextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_stack: list[bool] = []
        self._chunks: list[str] = []

    def _is_skipped(self) -> bool:
        return bool(self._skip_stack) and self._skip_stack[-1]

    @staticmethod
    def _is_hidden(tag: str, attrs: list[tuple[str, str | None]]) -> bool:
        if tag in _SKIP_TAGS:
            return True
        attr_dict = dict(attrs)
        style = (attr_dict.get("style") or "").replace(" ", "").lower()
        if "display:none" in style:
            return True
        return attr_dict.get("hidden") is not None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _VOID_ELEMENTS:
            return
        parent_hidden = self._is_skipped()
        self._skip_stack.append(parent_hidden or self._is_hidden(tag, attrs))

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID_ELEMENTS:
            return
        if self._skip_stack:
            self._skip_stack.pop()

    def handle_data(self, data: str) -> None:
        if not self._is_skipped():
            self._chunks.append(data)

    def get_text(self) -> str:
        return "".join(self._chunks)


def clean_text(html: str) -> str:
    """Strip tags, scripts, styles, and hidden XBRL metadata, returning collapsed plain text."""
    collector = _TextCollector()
    collector.feed(html)
    collector.close()
    text = collector.get_text()
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()
