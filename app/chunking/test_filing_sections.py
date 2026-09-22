"""Unit tests for filing noise stripping and Item-heading section splitting."""

from app.chunking.filing_sections import split_filing_sections, strip_repeated_lines


def test_strip_repeated_lines_removes_a_frequently_repeated_short_line():
    lines = []
    for i in range(6):
        lines.append("Apple Inc. | Form 10-Q")
        lines.append(f"unique body line {i}")
    text = "\n".join(lines)

    cleaned = strip_repeated_lines(text)

    assert "Apple Inc. | Form 10-Q" not in cleaned
    assert all(f"unique body line {i}" in cleaned for i in range(6))


def test_strip_repeated_lines_keeps_a_line_below_the_repeat_threshold():
    text = "\n".join(["Occasional header", "body"] * 4)

    cleaned = strip_repeated_lines(text, min_repeats=5)

    assert "Occasional header" in cleaned


def test_strip_repeated_lines_keeps_long_lines_even_when_repeated():
    long_line = "This sentence is well past the short running header length limit."
    text = "\n".join([long_line] * 10)

    cleaned = strip_repeated_lines(text, max_line_len=40)

    assert long_line in cleaned


def test_strip_repeated_lines_collapses_the_gaps_it_creates():
    text = "\n".join(["noise", "noise", "noise", "noise", "noise", "kept"])

    cleaned = strip_repeated_lines(text)

    assert "\n\n\n" not in cleaned
    assert "kept" in cleaned


def _filing_with_table_of_contents() -> str:
    toc = "Item 1. Business\nItem 1A. Risk Factors\n"
    business = "Item 1. Business\n" + ("The company designs devices. " * 40)
    risks = "Item 1A. Risk Factors\n" + ("Supply chain concentration is a risk. " * 40)
    return f"{toc}\n{business}\n\n{risks}"


def test_split_filing_sections_splits_on_item_headings():
    sections = split_filing_sections(_filing_with_table_of_contents())

    assert len(sections) == 2
    assert [name for name, _ in sections] == ["Item 1. Business", "Item 1A. Risk Factors"]


def test_split_filing_sections_prefers_the_body_over_the_table_of_contents():
    sections = split_filing_sections(_filing_with_table_of_contents())

    business_text = dict(sections)["Item 1. Business"]
    risks_text = dict(sections)["Item 1A. Risk Factors"]

    assert "The company designs devices." in business_text
    assert "Supply chain concentration is a risk." in risks_text
    assert "Supply chain concentration" not in business_text


def test_split_filing_sections_falls_back_when_there_are_too_few_headings():
    text = "Item 1. Business\n" + ("Only one heading here. " * 20)

    sections = split_filing_sections(text)

    assert len(sections) == 1
    assert sections[0][0] == "Full Document"


def test_split_filing_sections_falls_back_when_there_are_no_headings():
    text = "This filing body has no item headings at all."

    sections = split_filing_sections(text)

    assert sections == [("Full Document", text)]


def test_split_filing_sections_ignores_inline_cross_references():
    """An Item reference buried in long prose is not its own heading line."""
    inline = (
        "Item 1. Business\n"
        + "Refer to Item 1A. Risk Factors for a discussion of relevant factors. "
        + ("This clause keeps the same line running far past a heading length. " * 5)
        + "\n"
        + ("Body content continues. " * 40)
    )

    sections = split_filing_sections(inline)

    assert len(sections) == 1
    assert sections[0][0] == "Full Document"


def test_split_filing_sections_returns_non_empty_text_for_every_section():
    sections = split_filing_sections(_filing_with_table_of_contents())

    assert all(text.strip() for _, text in sections)
