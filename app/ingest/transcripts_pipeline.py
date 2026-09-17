"""Transcript ingest pipeline: discover, fetch, extract, and persist the fixed Motley Fool set."""

from datetime import date
from pathlib import Path

from app.ingest.fool_client import (
    TICKERS,
    TRANSCRIPTS_PER_COMPANY,
    discover_transcript_urls,
    fetch_transcript_page,
)
from app.ingest.models import Transcript
from app.ingest.text_extract import extract_article_text, parse_call_date

DATA_DIR = Path("data/transcripts")
MAX_TRANSCRIPT_AGE_DAYS = 400


def _write_transcript(transcript: Transcript) -> Path:
    company_dir = DATA_DIR / transcript.company
    company_dir.mkdir(parents=True, exist_ok=True)
    path = company_dir / f"{transcript.date.isoformat()}.json"
    path.write_text(transcript.model_dump_json(indent=2), encoding="utf-8")
    return path


def _fetch_dated_candidates(ticker: str, urls: list[str]) -> list[Transcript]:
    """Fetch every candidate URL and build a Transcript for each, dated by its real DATE heading."""
    candidates = []
    for url in urls:
        html = fetch_transcript_page(url)
        text = extract_article_text(html)
        call_date = parse_call_date(text)
        candidates.append(
            Transcript(company=ticker, date=call_date, raw_text=text, source_url=url)
        )
    return candidates


def ingest_all_transcripts() -> list[Transcript]:
    """Discover, fetch, and persist the fixed 2-most-recent transcript set for every company."""
    urls_by_ticker = discover_transcript_urls()

    transcripts: list[Transcript] = []
    for ticker in TICKERS:
        candidates = _fetch_dated_candidates(ticker, urls_by_ticker[ticker])
        candidates.sort(key=lambda transcript: transcript.date, reverse=True)
        selected = candidates[:TRANSCRIPTS_PER_COMPANY]

        if len(selected) < TRANSCRIPTS_PER_COMPANY:
            raise RuntimeError(
                f"Not enough dated transcripts for {ticker}: "
                f"wanted {TRANSCRIPTS_PER_COMPANY}, got {len(selected)}"
            )

        stale = [t for t in selected if (date.today() - t.date).days > MAX_TRANSCRIPT_AGE_DAYS]
        if stale:
            raise RuntimeError(
                f"Selected a stale transcript for {ticker}: {stale[0].date.isoformat()} is "
                f"more than {MAX_TRANSCRIPT_AGE_DAYS} days old, which means fool.com likely "
                f"doesn't have a fresher one discoverable in the current scan window (it may "
                f"be missing coverage for a recent quarter, or use a slug this feature's "
                f"ticker-token matching doesn't catch). Widen SCAN_MONTHS_BACK, or accept "
                f"fewer than {TRANSCRIPTS_PER_COMPANY} transcripts for this company, rather "
                f"than silently shipping a stale one."
            )

        for transcript in selected:
            _write_transcript(transcript)
            transcripts.append(transcript)

    return transcripts


if __name__ == "__main__":
    result = ingest_all_transcripts()
    print(f"Ingested {len(result)} transcripts into {DATA_DIR}/")
