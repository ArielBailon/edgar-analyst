"""Unit tests for transcript front-matter removal and speaker-turn splitting."""

from app.chunking.transcript_sections import split_transcript_sections

TRANSCRIPT = """Editorial preamble written by the publisher.
Some more marketing copy here.
Full Conference Call Transcript
Tim Cook: Thank you and good afternoon everyone.
Luca Maestri: Revenue for the quarter was a record.
Operator: Our first question comes from the line of an analyst.
"""


def test_split_transcript_sections_returns_one_entry_per_speaker_turn():
    sections = split_transcript_sections(TRANSCRIPT)

    assert [speaker for speaker, _ in sections] == ["Tim Cook", "Luca Maestri", "Operator"]


def test_split_transcript_sections_discards_editorial_front_matter():
    sections = split_transcript_sections(TRANSCRIPT)

    joined = "\n".join(text for _, text in sections)
    assert "Editorial preamble" not in joined
    assert "marketing copy" not in joined


def test_split_transcript_sections_keeps_each_turn_with_its_speaker():
    sections = dict(split_transcript_sections(TRANSCRIPT))

    assert "Thank you and good afternoon" in sections["Tim Cook"]
    assert "record" in sections["Luca Maestri"]
    assert "record" not in sections["Tim Cook"]


def test_split_transcript_sections_ignores_a_mid_sentence_colon_match():
    """A real speaker label is Title Case; 'One note:' is prose, not a speaker."""
    text = (
        "Full Conference Call Transcript\n"
        "Tim Cook: Opening remarks.\n"
        "One important note: this is prose, not a speaker label.\n"
    )

    sections = split_transcript_sections(text)

    assert [speaker for speaker, _ in sections] == ["Tim Cook"]
    assert "One important note" in sections[0][1]


def test_split_transcript_sections_falls_back_when_no_speakers_are_found():
    text = "Full Conference Call Transcript\nA block of prose with no speaker labels at all."

    sections = split_transcript_sections(text)

    assert len(sections) == 1
    assert sections[0][0] == "Full Transcript"
    assert "block of prose" in sections[0][1]


def test_split_transcript_sections_handles_a_missing_marker():
    text = "Tim Cook: Remarks without any publisher preamble marker.\n"

    sections = split_transcript_sections(text)

    assert [speaker for speaker, _ in sections] == ["Tim Cook"]


def test_split_transcript_sections_on_empty_text_falls_back():
    sections = split_transcript_sections("")

    assert sections == [("Full Transcript", "")]
