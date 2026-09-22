"""Unit tests for the eval runner's scoring functions.

Nothing here calls the real embedding model, ChromaDB, or the Anthropic API:
the embedding model is faked. run_eval itself calls the real pipeline and is
verified by running it manually, not tested here.
"""

import json

import pytest

from app.eval import runner
from app.eval.models import EvalPair
from app.generation.models import AnswerResult
from app.retrieval.models import Citation

CITATION = Citation(
    company="AAPL",
    document_type="10-Q",
    section="Item 1A.\xa0\xa0\xa0\xa0Risk Factors",
    date="2026-05-01",
    chunk_id="AAPL-10-Q-2026-05-01-item-1a-risk-factors-0",
)


@pytest.fixture(autouse=True)
def _reset_model_cache():
    """`runner` caches the embedding model in a module global, same as retriever.py."""
    runner._model = None
    yield
    runner._model = None


def test_citation_matches_when_expected_chunk_id_is_present():
    result = AnswerResult(answer="Answer. [1]", citations=[CITATION])

    assert runner.citation_matches(result, CITATION) is True


def test_citation_matches_false_when_chunk_id_differs():
    other = CITATION.model_copy(update={"chunk_id": "AAPL-10-Q-2026-05-01-item-1a-risk-factors-1"})
    result = AnswerResult(answer="Answer. [1]", citations=[other])

    assert runner.citation_matches(result, CITATION) is False


def test_citation_matches_false_for_a_refusal_with_no_citations():
    result = AnswerResult(answer="The retrieved filings do not contain information.", citations=[])

    assert runner.citation_matches(result, CITATION) is False


class _FakeVectors:
    def __init__(self, rows: list[list[float]]) -> None:
        self._rows = rows

    def __getitem__(self, index):
        return self._rows[index]


class _FakeModel:
    def __init__(self, rows: list[list[float]]) -> None:
        self._rows = rows

    def encode(self, texts: list[str]) -> _FakeVectors:
        return _FakeVectors(self._rows)


def test_answer_relevance_is_1_for_identical_vectors(monkeypatch):
    monkeypatch.setattr(runner, "_embedding_model", lambda: _FakeModel([[1.0, 0.0], [1.0, 0.0]]))

    assert runner.answer_relevance("a", "b") == pytest.approx(1.0)


def test_answer_relevance_is_0_for_orthogonal_vectors(monkeypatch):
    monkeypatch.setattr(runner, "_embedding_model", lambda: _FakeModel([[1.0, 0.0], [0.0, 1.0]]))

    assert runner.answer_relevance("a", "b") == pytest.approx(0.0)


def test_load_eval_set_returns_an_eval_pair_per_record():
    raw = json.loads(runner.EVAL_SET_PATH.read_text(encoding="utf-8"))

    pairs = runner._load_eval_set()

    assert len(pairs) == len(raw)
    assert all(isinstance(pair, EvalPair) for pair in pairs)
