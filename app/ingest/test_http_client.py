"""Unit tests for the shared HTTP GET retry helper. No real network I/O happens here."""

import urllib.error

import pytest

from app.ingest.http_client import MAX_ATTEMPTS, get_with_retry


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc_info) -> bool:
        return False

    def read(self) -> bytes:
        return self._payload


@pytest.fixture(autouse=True)
def _no_real_sleeping(monkeypatch):
    """The helper sleeps between attempts; tests must not pay that cost."""
    monkeypatch.setattr("time.sleep", lambda _seconds: None)


def _install_urlopen(monkeypatch, outcomes: list):
    """Serve one outcome per call: an exception is raised, anything else is returned."""
    calls = []

    def fake_urlopen(request, timeout=None):
        calls.append({"request": request, "timeout": timeout})
        outcome = outcomes[len(calls) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return calls


def test_returns_the_body_on_the_first_success(monkeypatch):
    calls = _install_urlopen(monkeypatch, [_FakeResponse(b"payload")])

    assert get_with_retry("https://example.test/doc", headers={}) == b"payload"
    assert len(calls) == 1


def test_passes_the_given_headers_through(monkeypatch):
    calls = _install_urlopen(monkeypatch, [_FakeResponse(b"ok")])

    get_with_retry("https://example.test/doc", headers={"User-Agent": "Test Agent"})

    assert calls[0]["request"].get_header("User-agent") == "Test Agent"
    assert calls[0]["request"].full_url == "https://example.test/doc"


def test_applies_a_request_timeout(monkeypatch):
    calls = _install_urlopen(monkeypatch, [_FakeResponse(b"ok")])

    get_with_retry("https://example.test/doc", headers={})

    assert calls[0]["timeout"] is not None


def test_retries_a_transient_error_then_succeeds(monkeypatch):
    calls = _install_urlopen(
        monkeypatch,
        [urllib.error.URLError("temporary failure"), _FakeResponse(b"recovered")],
    )

    assert get_with_retry("https://example.test/doc", headers={}) == b"recovered"
    assert len(calls) == 2


def test_reraises_after_exhausting_every_attempt(monkeypatch):
    calls = _install_urlopen(
        monkeypatch,
        [urllib.error.URLError(f"failure {i}") for i in range(MAX_ATTEMPTS)],
    )

    with pytest.raises(urllib.error.URLError):
        get_with_retry("https://example.test/doc", headers={})

    assert len(calls) == MAX_ATTEMPTS


def test_does_not_swallow_the_failure_into_an_empty_result(monkeypatch):
    """Citation accuracy depends on a failed fetch raising, never returning empty bytes."""
    _install_urlopen(
        monkeypatch,
        [urllib.error.URLError("down") for _ in range(MAX_ATTEMPTS)],
    )

    with pytest.raises(urllib.error.URLError):
        get_with_retry("https://example.test/doc", headers={})
