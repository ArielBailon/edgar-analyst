"""Motley Fool (fool.com) sitemap-based earnings-call transcript discovery."""

import re
from datetime import date

from app.ingest.edgar_client import COMPANIES
from app.ingest.http_client import get_with_retry

USER_AGENT = "edgar-analyst-portfolio-project/1.0 (+https://github.com/ArielBailon/edgar-analyst)"
SITEMAP_URL = "https://www.fool.com/sitemap/{year}/{month:02d}"
TRANSCRIPT_URL_RE = re.compile(
    r"https://www\.fool\.com/earnings/call-transcripts/(\d{4})/(\d{2})/(\d{2})/([a-z0-9-]+)/"
)

TICKERS = [company["ticker"] for company in COMPANIES]
TRANSCRIPTS_PER_COMPANY = 2
SCAN_MONTHS_BACK = 9


def fetch_sitemap(year: int, month: int) -> str:
    """Fetch one month's sitemap XML as text."""
    url = SITEMAP_URL.format(year=year, month=month)
    return get_with_retry(url, headers={"User-Agent": USER_AGENT}).decode("utf-8", errors="replace")


def _months_back(count: int) -> list[tuple[int, int]]:
    """The current month plus the `count - 1` months before it, as (year, month) pairs."""
    today = date.today()
    months = []
    year, month = today.year, today.month
    for _ in range(count):
        months.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return months


def extract_transcript_urls(sitemap_xml: str, ticker: str) -> list[str]:
    """Extract transcript URLs from a sitemap whose slug contains this ticker as a token."""
    token = f"-{ticker.lower()}-q"
    return [
        match.group(0)
        for match in TRANSCRIPT_URL_RE.finditer(sitemap_xml)
        if token in match.group(4)
    ]


def discover_transcript_urls() -> dict[str, list[str]]:
    """Scan the recent monthly sitemaps once and collect candidate transcript URLs per ticker.

    A sitemap's listing month is only a discovery filter, not a reliable recency
    signal: Motley Fool sometimes relists an old transcript in a later month's
    sitemap (observed live: a 2024 TSLA transcript relisted in an April 2026
    sitemap). Every candidate URL here must still be fetched and have its real
    call date parsed (text_extract.parse_call_date) before picking the most
    recent ones - never sort by the date embedded in the URL/sitemap alone.
    """
    matches: dict[str, list[str]] = {ticker: [] for ticker in TICKERS}
    for year, month in _months_back(SCAN_MONTHS_BACK):
        sitemap_xml = fetch_sitemap(year, month)
        for ticker in TICKERS:
            matches[ticker].extend(extract_transcript_urls(sitemap_xml, ticker))
    return {ticker: sorted(set(urls)) for ticker, urls in matches.items()}


def fetch_transcript_page(url: str) -> str:
    """Download a transcript page as decoded HTML text."""
    return get_with_retry(url, headers={"User-Agent": USER_AGENT}).decode("utf-8", errors="replace")
