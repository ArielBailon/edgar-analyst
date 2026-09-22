"""Unit tests for answer generation.

Nothing here calls the real Anthropic API: the client is faked. Hitting the real
API would make the suite neither fast, deterministic, nor free.
"""

from datetime import date

import pytest

from app.generation import generator
from app.generation.models import AnswerResult
from app.retrieval.models import Citation, RetrievalResult

API_KEY_VAR = "ANTHROPIC_API_KEY"


@pytest.fixture(autouse=True)
def _reset_client_cache():
    """`generator` caches the client in a module global, same as retriever caches its handles."""
    generator._client_handle = None
    yield
    generator._client_handle = None


def _result(**overrides) -> RetrievalResult:
    citation_fields = {
        "company": "AAPL",
        "document_type": "10-Q",
        "section": "Item 1A.\xa0\xa0\xa0\xa0Risk Factors",
        "date": "2026-05-01",
        "chunk_id": "AAPL-10-Q-2026-05-01-item-1a-risk-factors-0",
    }
    fields = {
        "chunk_id": citation_fields["chunk_id"],
        "text": "Supply chain concentration is a risk.",
        "citation": Citation(**citation_fields),
        "distance": 0.727,
    }
    return RetrievalResult(**{**fields, **overrides})


class _FakeContentBlock:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeMessage:
    def __init__(self, text: str) -> None:
        self.content = [_FakeContentBlock(text)]


class _FakeMessages:
    def __init__(self, response_text: str) -> None:
        self._response_text = response_text
        self.calls: list[dict] = []

    def create(self, **kwargs) -> _FakeMessage:
        self.calls.append(kwargs)
        return _FakeMessage(self._response_text)


class _FakeAnthropic:
    def __init__(self, response_text: str = "Answer. [1]") -> None:
        self.messages = _FakeMessages(response_text)


def _install(monkeypatch, response_text: str = "Answer. [1]") -> _FakeAnthropic:
    monkeypatch.setenv(API_KEY_VAR, "sk-ant-test-key")
    fake = _FakeAnthropic(response_text)
    monkeypatch.setattr(generator.anthropic, "Anthropic", lambda api_key: fake)
    return fake


def test_blank_question_raises(monkeypatch):
    _install(monkeypatch)

    with pytest.raises(ValueError, match="blank"):
        generator.generate_answer("   ", [_result()])


def test_empty_results_raises(monkeypatch):
    _install(monkeypatch)

    with pytest.raises(ValueError, match="empty"):
        generator.generate_answer("a real question", [])


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv(API_KEY_VAR, raising=False)

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        generator.generate_answer("a real question", [_result()])


def test_build_context_numbers_each_result_with_its_citation():
    first = _result()
    second = _result(
        chunk_id="MSFT-10-K-2025-10-31-item-1a-risk-factors-0",
        text="Currency exposure is a risk.",
        citation=Citation(
            company="MSFT",
            document_type="10-K",
            section="Item 1A.\xa0\xa0\xa0\xa0Risk Factors",
            date="2025-10-31",
            chunk_id="MSFT-10-K-2025-10-31-item-1a-risk-factors-0",
        ),
        distance=0.8,
    )

    context = generator._build_context([first, second])

    assert "[1] AAPL 10-Q 2026-05-01" in context
    assert "Supply chain concentration is a risk." in context
    assert "[2] MSFT 10-K 2025-10-31" in context
    assert "Currency exposure is a risk." in context


def test_generate_answer_returns_the_response_text_and_input_citations(monkeypatch):
    fake = _install(monkeypatch, response_text="Apple discloses supply chain risk. [1]")
    results = [_result()]

    answer = generator.generate_answer("What risk factors does Apple disclose?", results)

    assert isinstance(answer, AnswerResult)
    assert answer.answer == "Apple discloses supply chain risk. [1]"
    assert answer.citations == [results[0].citation]
    assert answer.citations[0].date == date(2026, 5, 1)

    call = fake.messages.calls[0]
    assert call["model"] == generator.MODEL
    assert call["system"] == generator.SYSTEM_PROMPT
    assert "What risk factors does Apple disclose?" in call["messages"][0]["content"]


def test_generate_answer_preserves_citation_order_across_multiple_results(monkeypatch):
    _install(monkeypatch)
    first = _result()
    second = _result(
        chunk_id="TSLA-10-K-2026-01-29-item-1a-risk-factors-0",
        citation=Citation(
            company="TSLA",
            document_type="10-K",
            section="Item 1A.\xa0\xa0\xa0\xa0Risk Factors",
            date="2026-01-29",
            chunk_id="TSLA-10-K-2026-01-29-item-1a-risk-factors-0",
        ),
        distance=0.9,
    )

    answer = generator.generate_answer("a question", [first, second])

    assert answer.citations == [first.citation, second.citation]


def test_answer_question_generates_when_the_nearest_result_is_close_enough(monkeypatch):
    fake = _install(monkeypatch, response_text="Apple discloses supply chain risk. [1]")
    results = [_result(distance=generator.DISTANCE_THRESHOLD - 0.001)]
    monkeypatch.setattr(generator, "retrieve", lambda question, top_k: results)

    answer = generator.answer_question("What risk factors does Apple disclose?")

    assert answer.answer == "Apple discloses supply chain risk. [1]"
    assert answer.citations == [results[0].citation]
    assert len(fake.messages.calls) == 1


def test_answer_question_refuses_when_the_nearest_result_is_too_far(monkeypatch):
    fake = _install(monkeypatch)
    results = [_result(distance=generator.DISTANCE_THRESHOLD)]
    monkeypatch.setattr(generator, "retrieve", lambda question, top_k: results)

    answer = generator.answer_question("What is the capital of France?")

    assert answer == AnswerResult(answer=generator.REFUSAL_MESSAGE, citations=[])
    assert fake.messages.calls == []


def test_answer_question_refuses_when_nothing_is_retrieved(monkeypatch):
    fake = _install(monkeypatch)
    monkeypatch.setattr(generator, "retrieve", lambda question, top_k: [])

    answer = generator.answer_question("a question with no matching chunks")

    assert answer == AnswerResult(answer=generator.REFUSAL_MESSAGE, citations=[])
    assert fake.messages.calls == []


def test_answer_question_passes_top_k_through_to_retrieve(monkeypatch):
    _install(monkeypatch)
    seen = {}

    def fake_retrieve(question, top_k):
        seen["top_k"] = top_k
        return [_result(distance=0.1)]

    monkeypatch.setattr(generator, "retrieve", fake_retrieve)

    generator.answer_question("a question", top_k=3)

    assert seen["top_k"] == 3


def test_answer_question_raises_on_a_blank_question(monkeypatch):
    _install(monkeypatch)

    with pytest.raises(ValueError, match="blank"):
        generator.answer_question("   ")


def test_the_client_is_resolved_once_per_process(monkeypatch):
    monkeypatch.setenv(API_KEY_VAR, "sk-ant-test-key")
    created = []

    def fake_anthropic(api_key):
        created.append(api_key)
        return _FakeAnthropic()

    monkeypatch.setattr(generator.anthropic, "Anthropic", fake_anthropic)

    generator.generate_answer("first question", [_result()])
    generator.generate_answer("second question", [_result()])

    assert len(created) == 1
