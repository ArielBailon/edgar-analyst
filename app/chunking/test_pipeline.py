"""Unit tests for the chunk id contract: slug building and per-document chunk ids.

These target `_slugify` and `_chunks_for_document` directly rather than `chunk_all`,
which reads and writes `data/`. Ids are the join between a chunk and its citation, so
their format and uniqueness are the contract worth pinning.
"""

from datetime import date

from app.chunking.pipeline import _chunks_for_document, _slugify

SECTION_WITH_NBSP = "Item 1A.\xa0\xa0\xa0\xa0Risk Factors"


def test_slugify_lowercases_and_hyphenates():
    assert _slugify("Item 1. Business") == "item-1-business"


def test_slugify_collapses_runs_of_punctuation_to_one_hyphen():
    assert _slugify("Item   1A.  --  Risk   Factors") == "item-1a-risk-factors"


def test_slugify_treats_non_breaking_spaces_as_separators():
    """Real EDGAR headings carry \\xa0; the slug must match the normal-space form."""
    assert _slugify(SECTION_WITH_NBSP) == _slugify("Item 1A. Risk Factors")


def test_slugify_trims_edge_hyphens():
    assert _slugify("  ...Business...  ") == "business"


def test_slugify_falls_back_when_nothing_survives():
    assert _slugify("") == "section"
    assert _slugify("!!!___") == "section"


def _sections(*names: str) -> list[tuple[str, str]]:
    return [(name, f"Body text for {name}.") for name in names]


def test_chunk_ids_follow_the_documented_format():
    chunks = _chunks_for_document("AAPL", "10-Q", date(2026, 5, 1), _sections("Item 1. Business"))

    assert len(chunks) == 1
    assert chunks[0].id == "AAPL-10-Q-2026-05-01-item-1-business-0"


def test_chunk_ids_are_unique_when_a_slug_repeats_across_sections():
    sections = _sections("Item 1A. Risk Factors", SECTION_WITH_NBSP, "Item 1A.  Risk  Factors")

    chunks = _chunks_for_document("TSLA", "10-K", date(2026, 1, 29), sections)

    ids = [chunk.id for chunk in chunks]
    assert len(ids) == len(set(ids))
    assert ids == [
        "TSLA-10-K-2026-01-29-item-1a-risk-factors-0",
        "TSLA-10-K-2026-01-29-item-1a-risk-factors-1",
        "TSLA-10-K-2026-01-29-item-1a-risk-factors-2",
    ]


def test_chunk_indexes_are_tracked_per_slug_not_globally():
    sections = _sections("Item 1. Business", "Item 1A. Risk Factors", "Item 1. Business")

    chunks = _chunks_for_document("MSFT", "10-K", date(2026, 6, 30), sections)

    assert [chunk.id.rsplit("-", 1)[-1] for chunk in chunks] == ["0", "0", "1"]


def test_chunks_carry_the_original_section_name_unchanged():
    chunks = _chunks_for_document("AAPL", "10-Q", date(2026, 5, 1), _sections(SECTION_WITH_NBSP))

    assert chunks[0].section == SECTION_WITH_NBSP


def test_chunks_inherit_document_metadata():
    chunks = _chunks_for_document("AAPL", "transcript", date(2026, 7, 30), _sections("Tim Cook"))

    assert chunks[0].company == "AAPL"
    assert chunks[0].document_type == "transcript"
    assert chunks[0].date == date(2026, 7, 30)


def test_no_sections_produces_no_chunks():
    assert _chunks_for_document("AAPL", "10-Q", date(2026, 5, 1), []) == []
