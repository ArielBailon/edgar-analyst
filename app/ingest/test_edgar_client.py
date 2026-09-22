"""Unit tests for SEC EDGAR filing selection, URL building, and the required User-Agent."""

import pytest

from app.ingest.edgar_client import _user_agent, filing_document_url, select_filings

USER_AGENT_VAR = "SEC_EDGAR_USER_AGENT"


def _submissions(entries: list[tuple[str, str]]) -> dict:
    """Build a submissions payload from (form, filingDate) pairs, in EDGAR's column layout."""
    return {
        "filings": {
            "recent": {
                "form": [form for form, _ in entries],
                "filingDate": [filed for _, filed in entries],
                "accessionNumber": [f"0000320193-26-{i:06d}" for i, _ in enumerate(entries)],
                "primaryDocument": [f"doc{i}.htm" for i, _ in enumerate(entries)],
            }
        }
    }


def test_select_filings_takes_the_most_recent_of_each_wanted_form():
    submissions = _submissions(
        [
            ("10-K", "2024-10-31"),
            ("10-K", "2025-10-31"),
            ("10-Q", "2026-02-01"),
            ("10-Q", "2026-05-01"),
            ("10-Q", "2026-07-31"),
        ]
    )

    selected = select_filings(submissions)

    assert [entry["form"] for entry in selected].count("10-K") == 1
    assert [entry["form"] for entry in selected].count("10-Q") == 2

    by_form = {}
    for entry in selected:
        by_form.setdefault(entry["form"], []).append(entry["filingDate"])
    assert by_form["10-K"] == ["2025-10-31"]
    assert sorted(by_form["10-Q"], reverse=True) == ["2026-07-31", "2026-05-01"]


def test_select_filings_ignores_forms_that_are_not_wanted():
    submissions = _submissions(
        [
            ("8-K", "2026-08-01"),
            ("S-1", "2026-08-01"),
            ("10-K", "2025-10-31"),
            ("10-Q", "2026-05-01"),
            ("10-Q", "2026-07-31"),
        ]
    )

    selected = select_filings(submissions)

    assert {entry["form"] for entry in selected} == {"10-K", "10-Q"}
    assert len(selected) == 3


def test_select_filings_raises_when_a_wanted_form_is_short():
    submissions = _submissions([("10-K", "2025-10-31"), ("10-Q", "2026-05-01")])

    with pytest.raises(RuntimeError, match="10-Q"):
        select_filings(submissions)


def test_select_filings_raises_when_a_wanted_form_is_absent():
    submissions = _submissions([("10-Q", "2026-05-01"), ("10-Q", "2026-07-31")])

    with pytest.raises(RuntimeError, match="10-K"):
        select_filings(submissions)


def test_filing_document_url_strips_dashes_from_the_accession_number():
    entry = {"accessionNumber": "0000320193-26-000071", "primaryDocument": "aapl-20260627.htm"}

    url = filing_document_url(320193, entry)

    assert url == (
        "https://www.sec.gov/Archives/edgar/data/320193/000032019326000071/aapl-20260627.htm"
    )


def test_user_agent_returns_the_configured_value(monkeypatch):
    monkeypatch.setenv(USER_AGENT_VAR, "Test Name test@example.com")

    assert _user_agent() == "Test Name test@example.com"


def test_user_agent_raises_when_unset(monkeypatch):
    monkeypatch.delenv(USER_AGENT_VAR, raising=False)

    with pytest.raises(RuntimeError, match="SEC_EDGAR_USER_AGENT"):
        _user_agent()


def test_user_agent_raises_when_blank(monkeypatch):
    monkeypatch.setenv(USER_AGENT_VAR, "")

    with pytest.raises(RuntimeError):
        _user_agent()
