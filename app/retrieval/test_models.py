"""Unit tests for the citation and retrieval-result models."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.retrieval.models import Citation, RetrievalResult

SECTION_WITH_NBSP = "Item 1A.\xa0\xa0\xa0\xa0Risk Factors"


def _citation(**overrides) -> Citation:
    fields = {
        "company": "AAPL",
        "document_type": "10-Q",
        "section": SECTION_WITH_NBSP,
        "date": "2026-05-01",
        "chunk_id": "AAPL-10-Q-2026-05-01-item-1a-risk-factors-0",
    }
    return Citation(**{**fields, **overrides})


def test_citation_coerces_an_iso_date_string():
    assert _citation().date == date(2026, 5, 1)


def test_citation_preserves_non_breaking_spaces_in_the_section_name():
    """Citations must echo the stored section byte for byte or they stop matching the index."""
    assert _citation().section == SECTION_WITH_NBSP


@pytest.mark.parametrize("document_type", ["10-K", "10-Q", "transcript"])
def test_citation_accepts_every_indexed_document_type(document_type):
    assert _citation(document_type=document_type).document_type == document_type


def test_citation_rejects_an_unknown_document_type():
    with pytest.raises(ValidationError):
        _citation(document_type="8-K")


def test_citation_rejects_a_malformed_date():
    with pytest.raises(ValidationError):
        _citation(date="not-a-date")


def test_citation_requires_every_field():
    with pytest.raises(ValidationError):
        Citation(company="AAPL", document_type="10-Q")


def test_retrieval_result_holds_its_citation_and_distance():
    citation = _citation()

    result = RetrievalResult(
        chunk_id=citation.chunk_id,
        text="Supply chain concentration is a risk.",
        citation=citation,
        distance=0.727,
    )

    assert result.chunk_id == citation.chunk_id
    assert result.citation.company == "AAPL"
    assert isinstance(result.distance, float)


def test_retrieval_result_coerces_an_integer_distance_to_float():
    result = RetrievalResult(chunk_id="x", text="t", citation=_citation(), distance=1)

    assert isinstance(result.distance, float)
