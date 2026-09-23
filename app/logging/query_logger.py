"""Append one QueryLog entry per answered question to a local JSON Lines file."""

import logging
from datetime import datetime, timezone
from pathlib import Path

from app.logging.models import QueryLog
from app.retrieval.models import Citation

LOG_PATH = Path("data/logs/queries.jsonl")

# Claude Haiku 4.5 published Anthropic API pricing, in dollars per token.
INPUT_COST_PER_TOKEN = 1.00 / 1_000_000
OUTPUT_COST_PER_TOKEN = 5.00 / 1_000_000

_logger_handle: logging.Logger | None = None


def _query_logger() -> logging.Logger:
    """Open the log file handler once per process; callers may answer questions in a loop."""
    global _logger_handle
    if _logger_handle is None:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger = logging.getLogger("edgar_analyst.queries")
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        _logger_handle = logger
    return _logger_handle


def compute_cost(input_tokens: int, output_tokens: int) -> float:
    """Dollar cost of one Claude call at Claude Haiku 4.5's published per-token rates."""
    return input_tokens * INPUT_COST_PER_TOKEN + output_tokens * OUTPUT_COST_PER_TOKEN


def log_query(
    question: str,
    retrieved_sources: list[Citation],
    model: str,
    latency_ms: int,
    input_tokens: int,
    output_tokens: int,
) -> None:
    """Append one QueryLog entry for an answered question as a single JSON line."""
    entry = QueryLog(
        timestamp=datetime.now(timezone.utc),
        question=question,
        retrieved_sources=retrieved_sources,
        model=model,
        latency_ms=latency_ms,
        tokens=input_tokens + output_tokens,
        cost=compute_cost(input_tokens, output_tokens),
    )
    _query_logger().info(entry.model_dump_json())
