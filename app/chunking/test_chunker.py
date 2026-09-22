"""Unit tests for paragraph-aware chunking."""

from app.chunking.chunker import DEFAULT_CHUNK_SIZE, chunk_text


def test_blank_text_produces_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_short_text_stays_one_chunk():
    text = "First paragraph.\n\nSecond paragraph."
    assert chunk_text(text) == [text]


def test_long_text_splits_without_exceeding_chunk_size():
    paragraph = ("word " * 100).strip()
    text = "\n\n".join([paragraph] * 6)

    chunks = chunk_text(text, chunk_size=600, overlap=50)

    assert len(chunks) > 1
    assert all(len(chunk) <= 600 for chunk in chunks)


def test_consecutive_chunks_share_the_overlap_tail():
    paragraph = "x" * 400
    text = "\n\n".join([paragraph] * 3)

    chunks = chunk_text(text, chunk_size=1000, overlap=100)

    assert len(chunks) == 2
    assert chunks[1].startswith(chunks[0][-100:])


def test_a_single_oversized_paragraph_is_sliced():
    chunks = chunk_text("a" * 1000, chunk_size=300, overlap=50)

    assert len(chunks) > 1
    assert all(len(chunk) <= 300 for chunk in chunks)
    assert "".join(chunk[:250] for chunk in chunks).startswith("a" * 250)


def test_zero_overlap_produces_no_shared_tail():
    paragraph = "y" * 400
    text = "\n\n".join([paragraph] * 3)

    chunks = chunk_text(text, chunk_size=1000, overlap=0)

    assert len(chunks) == 2
    assert chunks[1] == paragraph


def test_paragraph_breaks_are_preferred_over_slicing():
    text = "\n\n".join(["short one", "short two", "short three"])

    assert chunk_text(text, chunk_size=DEFAULT_CHUNK_SIZE) == [text]


def test_blank_paragraphs_are_dropped():
    text = "First.\n\n\n\nSecond."

    chunks = chunk_text(text)

    assert chunks == ["First.\n\nSecond."]
