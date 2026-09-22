"""Unit tests for transcript URL discovery from a Motley Fool sitemap."""

from datetime import date

from app.ingest.fool_client import _months_back, extract_transcript_urls

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset>
  <url><loc>https://www.fool.com/earnings/call-transcripts/2026/07/31/apple-aapl-q3-2026-earnings-call-transcript/</loc></url>
  <url><loc>https://www.fool.com/earnings/call-transcripts/2026/07/30/alphabet-googl-q2-2026-earnings-call-transcript/</loc></url>
  <url><loc>https://www.fool.com/earnings/call-transcripts/2026/05/01/apple-aapl-q2-2026-earnings-call-transcript/</loc></url>
  <url><loc>https://www.fool.com/investing/2026/07/31/some-unrelated-article/</loc></url>
</urlset>
"""


def test_extract_transcript_urls_returns_only_the_requested_ticker():
    urls = extract_transcript_urls(SITEMAP, "AAPL")

    assert len(urls) == 2
    assert all("-aapl-q" in url for url in urls)
    assert all("googl" not in url for url in urls)


def test_extract_transcript_urls_returns_full_urls():
    urls = extract_transcript_urls(SITEMAP, "AAPL")

    assert (
        "https://www.fool.com/earnings/call-transcripts/2026/07/31/"
        "apple-aapl-q3-2026-earnings-call-transcript/" in urls
    )


def test_extract_transcript_urls_ignores_non_transcript_urls():
    urls = extract_transcript_urls(SITEMAP, "AAPL")

    assert all("/earnings/call-transcripts/" in url for url in urls)


def test_extract_transcript_urls_is_case_insensitive_on_the_ticker():
    assert extract_transcript_urls(SITEMAP, "aapl") == extract_transcript_urls(SITEMAP, "AAPL")


def test_extract_transcript_urls_returns_empty_for_an_absent_ticker():
    assert extract_transcript_urls(SITEMAP, "MSFT") == []


def test_extract_transcript_urls_returns_empty_for_an_empty_sitemap():
    assert extract_transcript_urls("", "AAPL") == []


def test_months_back_returns_the_requested_count_starting_at_the_current_month():
    months = _months_back(3)

    today = date.today()
    assert len(months) == 3
    assert months[0] == (today.year, today.month)


def test_months_back_walks_backwards_rolling_the_year_over():
    months = _months_back(14)

    assert len(months) == 14
    assert all(1 <= month <= 12 for _, month in months)

    for (year, month), (prev_year, prev_month) in zip(months[1:], months[:-1]):
        expected_year = prev_year if prev_month > 1 else prev_year - 1
        expected_month = prev_month - 1 if prev_month > 1 else 12
        assert (year, month) == (expected_year, expected_month)


def test_months_back_spans_more_than_one_year_when_asked_for_more_than_twelve():
    years = {year for year, _ in _months_back(14)}

    assert len(years) >= 2
