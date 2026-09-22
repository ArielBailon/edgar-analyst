"""Unit tests for HTML-to-clean-text extraction and transcript date parsing."""

from datetime import date

import pytest

from app.ingest.text_extract import clean_text, extract_article_text, parse_call_date

FILING_HTML = """
<html><body>
<p>Visible paragraph one.</p>
<script>var hidden_script = 1;</script>
<style>.noise { color: red; }</style>
<div style="display:none">XBRL context metadata</div>
<div style="DISPLAY: NONE">Uppercase hidden metadata</div>
<p>Visible paragraph two.</p>
</body></html>
"""


def test_clean_text_keeps_visible_text():
    text = clean_text(FILING_HTML)

    assert "Visible paragraph one." in text
    assert "Visible paragraph two." in text


def test_clean_text_drops_scripts_styles_and_hidden_metadata():
    text = clean_text(FILING_HTML)

    assert "hidden_script" not in text
    assert ".noise" not in text
    assert "XBRL context metadata" not in text
    assert "Uppercase hidden metadata" not in text


def test_clean_text_drops_nested_content_of_a_hidden_block():
    html = '<div style="display:none"><p>Nested hidden fact</p></div><p>Kept</p>'

    text = clean_text(html)

    assert "Nested hidden fact" not in text
    assert "Kept" in text


def test_clean_text_collapses_whitespace():
    html = "<p>Spaced     out\ttext</p>\n\n\n<p>Next</p>"

    text = clean_text(html)

    assert "Spaced out text" in text
    assert "\n\n\n" not in text
    assert text == text.strip()


def test_clean_text_on_empty_html_returns_empty_string():
    assert clean_text("") == ""


ARTICLE_HTML = """
<html><body>
<nav>Site navigation links</nav>
<div id="article-body-transcript">
  <p>Prepared remarks begin here.</p>
  <p>Operator instructions.</p>
</div>
<footer>Related articles you may like</footer>
</body></html>
"""


def test_extract_article_text_returns_only_container_content():
    text = extract_article_text(ARTICLE_HTML)

    assert "Prepared remarks begin here." in text
    assert "Operator instructions." in text


def test_extract_article_text_excludes_surrounding_site_chrome():
    text = extract_article_text(ARTICLE_HTML)

    assert "Site navigation links" not in text
    assert "Related articles you may like" not in text


def test_extract_article_text_honors_a_custom_container_id():
    html = '<div id="other">Wanted</div><div id="article-body-transcript">Default</div>'

    assert extract_article_text(html, container_id="other") == "Wanted"


def test_extract_article_text_returns_empty_when_container_is_absent():
    assert extract_article_text("<p>No container here</p>") == ""


@pytest.mark.parametrize(
    ("article_text", "expected"),
    [
        ("Thursday, July 30, 2026 at 5:00 p.m. ET", date(2026, 7, 30)),
        ("Oct. 23, 2024, 5:30 p.m. ET", date(2024, 10, 23)),
        ("DATE\nMay 1, 2025", date(2025, 5, 1)),
    ],
)
def test_parse_call_date_handles_observed_formats(article_text, expected):
    assert parse_call_date(article_text) == expected


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Known defect: _MONTH_NAMES lists 'Sept', so the regex matches 'Sept. 9, 2025', "
        "but strptime accepts only 'Sep' (%b) or 'September' (%B), so parse_call_date "
        "raises instead of returning a date. 'Sept' is the only such token. Not "
        "currently reachable (no ingested transcript uses it) but a September call "
        "formatted this way would crash transcripts_pipeline. Remove this marker when "
        "the defect is fixed; strict=True makes the suite fail if it starts passing."
    ),
)
def test_parse_call_date_handles_sept_abbreviation():
    assert parse_call_date("Sept. 9, 2025, 4:00 p.m. ET") == date(2025, 9, 9)


def test_parse_call_date_takes_the_first_date_in_the_text():
    text = "Published Jan. 2, 2025. Call held Feb. 3, 2025."

    assert parse_call_date(text) == date(2025, 1, 2)


def test_parse_call_date_raises_when_no_date_is_present():
    with pytest.raises(ValueError):
        parse_call_date("This transcript has no month day year anywhere.")
