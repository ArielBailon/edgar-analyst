"""Unit tests for query logging.

Every test points LOG_PATH at a tmp_path, so the real data/logs/queries.jsonl is
never touched.
"""

import json
from datetime import date

import pytest

from app.logging import query_logger
from app.logging.models import QueryLog
from app.retrieval.models import Citation


@pytest.fixture(autouse=True)
def _reset_logger_cache():
    """`query_logger` caches its logger in a module global; close its file between tests."""
    _close_cached_logger()
    yield
    _close_cached_logger()


def _close_cached_logger() -> None:
    if query_logger._logger_handle is not None:
        for handler in query_logger._logger_handle.handlers:
            handler.close()
        query_logger._logger_handle.handlers.clear()
    query_logger._logger_handle = None


def _citation() -> Citation:
    return Citation(
        company="AAPL",
        document_type="10-Q",
        section="Item 1A. Risk Factors",
        date="2026-05-01",
        chunk_id="AAPL-10-Q-2026-05-01-item-1a-risk-factors-0",
    )


def test_compute_cost_uses_the_haiku_per_million_token_rates():
    # 2,000 input tokens at $1.00/1M is $0.002; 300 output tokens at $5.00/1M is $0.0015.
    assert query_logger.compute_cost(2_000, 300) == pytest.approx(0.0035)


def test_compute_cost_is_zero_without_tokens():
    assert query_logger.compute_cost(0, 0) == 0.0


def test_log_query_appends_one_json_line_per_call(monkeypatch, tmp_path):
    log_path = tmp_path / "queries.jsonl"
    monkeypatch.setattr(query_logger, "LOG_PATH", log_path)

    query_logger.log_query(
        question="What risk factors does Apple disclose?",
        retrieved_sources=[_citation()],
        model="claude-haiku-4-5-20251001",
        latency_ms=1234,
        input_tokens=2_000,
        output_tokens=300,
    )
    query_logger.log_query(
        question="What is the capital of France?",
        retrieved_sources=[],
        model="",
        latency_ms=56,
        input_tokens=0,
        output_tokens=0,
    )

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2

    first = QueryLog.model_validate(json.loads(lines[0]))
    assert first.question == "What risk factors does Apple disclose?"
    assert first.retrieved_sources == [_citation()]
    assert first.retrieved_sources[0].date == date(2026, 5, 1)
    assert first.model == "claude-haiku-4-5-20251001"
    assert first.latency_ms == 1234
    assert first.tokens == 2_300
    assert first.cost == pytest.approx(0.0035)

    second = QueryLog.model_validate(json.loads(lines[1]))
    assert second.question == "What is the capital of France?"
    assert second.retrieved_sources == []
    assert second.model == ""
    assert second.tokens == 0
    assert second.cost == 0.0


def test_log_query_creates_the_log_directory(monkeypatch, tmp_path):
    log_path = tmp_path / "nested" / "logs" / "queries.jsonl"
    monkeypatch.setattr(query_logger, "LOG_PATH", log_path)

    query_logger.log_query("a question", [], "", 1, 0, 0)

    assert log_path.is_file()
