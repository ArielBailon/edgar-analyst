"""Ingest pipeline: fetch, clean, and persist the fixed SEC EDGAR filing set."""

import json
from pathlib import Path

from app.ingest.edgar_client import (
    COMPANIES,
    fetch_filing_document,
    fetch_submissions,
    filing_document_url,
    select_filings,
)
from app.ingest.models import Filing
from app.ingest.text_extract import clean_text

DATA_DIR = Path("data/filings")


def _write_filing(filing: Filing) -> Path:
    company_dir = DATA_DIR / filing.company
    company_dir.mkdir(parents=True, exist_ok=True)
    path = company_dir / f"{filing.filing_type}_{filing.date.isoformat()}.json"
    path.write_text(filing.model_dump_json(indent=2), encoding="utf-8")
    return path


def ingest_all() -> list[Filing]:
    """Fetch, clean, and persist the fixed 1x10-K + 2x10-Q filing set for every configured company."""
    filings: list[Filing] = []
    for company in COMPANIES:
        cik = company["cik"]
        submissions = fetch_submissions(cik)
        entries = select_filings(submissions)
        for entry in entries:
            html = fetch_filing_document(cik, entry)
            filing = Filing(
                company=company["ticker"],
                filing_type=entry["form"],
                date=entry["filingDate"],
                raw_text=clean_text(html),
                source_url=filing_document_url(cik, entry),
            )
            _write_filing(filing)
            filings.append(filing)
    return filings


if __name__ == "__main__":
    result = ingest_all()
    print(f"Ingested {len(result)} filings into {DATA_DIR}/")
