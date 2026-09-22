"""Unit tests for the EvalPair model."""

from datetime import date

from app.eval.models import EvalPair
from app.retrieval.models import Citation


def test_eval_pair_round_trips_question_answer_and_citation():
    citation = Citation(
        company="AAPL",
        document_type="10-Q",
        section="Item 1A.\xa0\xa0\xa0\xa0Risk Factors",
        date="2026-05-01",
        chunk_id="AAPL-10-Q-2026-05-01-item-1a-risk-factors-0",
    )

    pair = EvalPair(
        question="What risk factors does Apple disclose about supply chain concentration?",
        expected_answer="Supply chain concentration is a risk.",
        expected_citation=citation,
    )

    assert pair.question == "What risk factors does Apple disclose about supply chain concentration?"
    assert pair.expected_answer == "Supply chain concentration is a risk."
    assert pair.expected_citation == citation
    assert pair.expected_citation.date == date(2026, 5, 1)
