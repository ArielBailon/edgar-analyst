"""Unit tests for the AnswerResult model."""

from datetime import date

from app.generation.models import AnswerResult
from app.retrieval.models import Citation


def test_answer_result_round_trips_answer_and_citations():
    citation = Citation(
        company="AAPL",
        document_type="10-Q",
        section="Item 1A.\xa0\xa0\xa0\xa0Risk Factors",
        date="2026-05-01",
        chunk_id="AAPL-10-Q-2026-05-01-item-1a-risk-factors-0",
    )

    result = AnswerResult(answer="Supply chain concentration is a risk. [1]", citations=[citation])

    assert result.answer == "Supply chain concentration is a risk. [1]"
    assert result.citations == [citation]
    assert result.citations[0].date == date(2026, 5, 1)
