"""Filing section detection: strips repeated page-header noise, then splits by Item heading.

SEC filing HTML rendering varies by filer: some duplicate every Item heading in
a table of contents, some leave repeated page-header/footer artifacts (a
running "PART I / Item 1" style header, repeated table column headers, page
numbers) scattered through the whole document body. Both are handled here
without filer-specific rules - see the feature spec's Investigation section
for the real examples (AAPL, MSFT, TSLA) this was validated against.
"""

import re
from collections import Counter

_ITEM_RE = re.compile(r"\bItem\s+(\d+[A-Za-z]?)\.", re.IGNORECASE)
_FALLBACK_SECTION = "Full Document"
_MAX_HEADING_LEN = 150


def strip_repeated_lines(text: str, min_repeats: int = 5, max_line_len: int = 40) -> str:
    """Remove short lines that repeat many times verbatim (running headers/footers/page numbers)."""
    lines = text.split("\n")
    candidates = [line.strip() for line in lines if line.strip() and len(line.strip()) <= max_line_len]
    counts = Counter(candidates)
    noise = {line for line, count in counts.items() if count >= min_repeats}

    cleaned_lines = ["" if line.strip() in noise else line for line in lines]
    cleaned = "\n".join(cleaned_lines)
    return re.sub(r"\n{3,}", "\n\n", cleaned)


def _looks_like_heading(text: str, start: int) -> bool:
    """A real heading is its own short line; an inline cross-reference runs on as long prose."""
    line_end = text.find("\n", start)
    line_end = len(text) if line_end == -1 else line_end
    return (line_end - start) <= _MAX_HEADING_LEN


def _real_heading_positions(text: str) -> list[tuple[str, int]]:
    """For each Item label, pick the occurrence that starts the largest span of real content."""
    by_label: dict[str, list[int]] = {}
    for match in _ITEM_RE.finditer(text):
        if not _looks_like_heading(text, match.start()):
            continue
        label = match.group(1).upper()
        by_label.setdefault(label, []).append(match.start())

    all_starts = sorted(start for starts in by_label.values() for start in starts)

    def content_span(start: int) -> int:
        later = [s for s in all_starts if s > start]
        return (min(later) if later else len(text)) - start

    resolved = []
    for label, starts in by_label.items():
        best_start = max(starts, key=content_span)
        resolved.append((label, best_start))

    return sorted(resolved, key=lambda pair: pair[1])


def split_filing_sections(text: str) -> list[tuple[str, str]]:
    """Split filing text into (section_name, section_text) pairs by real Item heading."""
    cleaned = strip_repeated_lines(text)
    headings = _real_heading_positions(cleaned)

    if len(headings) < 2:
        return [(_FALLBACK_SECTION, cleaned)]

    sections = []
    for i, (label, start) in enumerate(headings):
        end = headings[i + 1][1] if i + 1 < len(headings) else len(cleaned)
        section_text = cleaned[start:end].strip()
        if not section_text:
            continue
        heading_line = section_text.split("\n", 1)[0].strip()
        section_name = heading_line if heading_line else f"Item {label}"
        sections.append((section_name, section_text))

    return sections if sections else [(_FALLBACK_SECTION, cleaned)]
