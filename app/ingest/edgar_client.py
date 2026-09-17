"""SEC EDGAR HTTP client: fixed company config, submissions lookup, filing selection."""

import json
import os
import time
import urllib.error
import urllib.request

from dotenv import load_dotenv

load_dotenv()

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
REQUEST_TIMEOUT_SECONDS = 15
MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2

COMPANIES = [
    {"ticker": "AAPL", "cik": 320193, "name": "Apple Inc."},
    {"ticker": "MSFT", "cik": 789019, "name": "Microsoft Corporation"},
    {"ticker": "TSLA", "cik": 1318605, "name": "Tesla, Inc."},
]

FILING_TYPES_WANTED = {"10-K": 1, "10-Q": 2}


def _user_agent() -> str:
    user_agent = os.environ.get("SEC_EDGAR_USER_AGENT")
    if not user_agent:
        raise RuntimeError(
            "SEC_EDGAR_USER_AGENT is not set. SEC EDGAR requires a descriptive "
            "User-Agent header identifying the requester (name and email). "
            "Set it in .env (see .env.example)."
        )
    return user_agent


def _get(url: str) -> bytes:
    """GET a URL with the required SEC User-Agent, retrying transient network errors."""
    request = urllib.request.Request(url, headers={"User-Agent": _user_agent()})
    last_error: urllib.error.URLError | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                return response.read()
        except urllib.error.URLError as error:
            last_error = error
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS)
    raise last_error


def fetch_submissions(cik: int) -> dict:
    """Fetch the raw submissions JSON for a company's CIK."""
    url = SUBMISSIONS_URL.format(cik=cik)
    return json.loads(_get(url))


def select_filings(submissions: dict) -> list[dict]:
    """Select the most recent filings per FILING_TYPES_WANTED from a submissions payload."""
    recent = submissions["filings"]["recent"]
    entries = [
        {
            "form": recent["form"][i],
            "filingDate": recent["filingDate"][i],
            "accessionNumber": recent["accessionNumber"][i],
            "primaryDocument": recent["primaryDocument"][i],
        }
        for i in range(len(recent["form"]))
        if recent["form"][i] in FILING_TYPES_WANTED
    ]
    entries.sort(key=lambda entry: entry["filingDate"], reverse=True)

    selected = []
    counts = {form: 0 for form in FILING_TYPES_WANTED}
    for entry in entries:
        form = entry["form"]
        if counts[form] < FILING_TYPES_WANTED[form]:
            selected.append(entry)
            counts[form] += 1

    missing = [form for form, wanted in FILING_TYPES_WANTED.items() if counts[form] < wanted]
    if missing:
        raise RuntimeError(f"Not enough filings found for forms: {missing}")

    return selected


def filing_document_url(cik: int, entry: dict) -> str:
    """Build the Archives URL for a filing's primary document."""
    accession_no_dashes = entry["accessionNumber"].replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}/{entry['primaryDocument']}"


def fetch_filing_document(cik: int, entry: dict) -> str:
    """Download a filing's primary document as decoded HTML text."""
    url = filing_document_url(cik, entry)
    return _get(url).decode("utf-8", errors="replace")
