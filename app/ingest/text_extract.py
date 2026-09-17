"""HTML-to-clean-text extraction for downloaded filing documents and transcript pages.

SEC filings are Inline XBRL documents: alongside the human-readable body they
embed a large `display:none` block of XBRL tagging metadata (contexts, units,
hidden facts) that must not leak into the extracted text. Motley Fool
transcript pages embed the transcript inside a full site layout (nav, ads,
related articles); only a `container_id`-matched element's own content should
be collected there.
"""

import re
from datetime import date, datetime
from html.parser import HTMLParser

_SKIP_TAGS = {"script", "style"}
_VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}
_BLOCK_TAGS = {
    "p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "ul", "ol",
    "tr", "table", "section", "article", "header", "footer", "blockquote",
}

_MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
    "Jan", "Feb", "Mar", "Apr", "Jun", "Jul", "Aug", "Sep", "Sept", "Oct", "Nov", "Dec",
)
_MONTH_DAY_YEAR_RE = re.compile(
    r"\b(" + "|".join(_MONTH_NAMES) + r")\.?\s+(\d{1,2}),\s+(\d{4})"
)


class _TextCollector(HTMLParser):
    def __init__(self, container_id: str | None = None) -> None:
        super().__init__(convert_charrefs=True)
        self._container_id = container_id
        self._in_container = container_id is None
        self._container_depth = 0
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
            if tag == "br" and self._in_container and not self._is_skipped():
                self._chunks.append("\n")
            return

        if not self._in_container:
            if dict(attrs).get("id") == self._container_id:
                self._in_container = True
                self._container_depth = 1
            return

        if self._container_id is not None:
            self._container_depth += 1

        if tag in _BLOCK_TAGS and not self._is_skipped():
            self._chunks.append("\n")

        parent_hidden = self._is_skipped()
        self._skip_stack.append(parent_hidden or self._is_hidden(tag, attrs))

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID_ELEMENTS or not self._in_container:
            return

        if self._skip_stack:
            self._skip_stack.pop()

        if self._container_id is not None:
            self._container_depth -= 1
            if self._container_depth == 0:
                self._in_container = False

    def handle_data(self, data: str) -> None:
        if self._in_container and not self._is_skipped():
            self._chunks.append(data)

    def get_text(self) -> str:
        return "".join(self._chunks)


def _collect(html: str, container_id: str | None = None) -> str:
    collector = _TextCollector(container_id=container_id)
    collector.feed(html)
    collector.close()
    text = collector.get_text()
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def clean_text(html: str) -> str:
    """Strip tags, scripts, styles, and hidden XBRL metadata, returning collapsed plain text."""
    return _collect(html)


def extract_article_text(html: str, container_id: str = "article-body-transcript") -> str:
    """Extract only the text inside the element with this id, skipping surrounding site chrome."""
    return _collect(html, container_id=container_id)


def parse_call_date(article_text: str) -> date:
    """Parse the real earnings-call date out of a transcript's own DATE heading text.

    Handles both observed formats: a full month name with an optional weekday
    ("Thursday, July 30, 2026 at 5:00 p.m. ET") and an abbreviated month with a
    period ("Oct. 23, 2024, 5:30 p.m. ET").
    """
    match = _MONTH_DAY_YEAR_RE.search(article_text)
    if not match:
        raise ValueError(f"Could not find a month/day/year date in: {article_text[:200]!r}")

    month_name, day, year = match.groups()
    for fmt in ("%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(f"{month_name} {day} {year}", fmt).date()
        except ValueError:
            continue

    raise ValueError(f"Could not parse date from: {match.group(0)!r}")
