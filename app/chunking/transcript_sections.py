"""Transcript section detection: discards Motley Fool's editorial front matter, splits by speaker turn."""

import re

_TRANSCRIPT_MARKER = "Full Conference Call Transcript"
_SPEAKER_RE = re.compile(r"\n([A-Z][A-Za-z.\-' ]{1,40}):\s")
_FALLBACK_SECTION = "Full Transcript"


def _looks_like_name(candidate: str) -> bool:
    """A real speaker name is Title Case throughout; a mid-sentence match has lowercase words."""
    return all(word[0].isupper() for word in candidate.split() if word)


def split_transcript_sections(text: str) -> list[tuple[str, str]]:
    """Split verbatim call text (after the editorial front matter) into (speaker, turn_text) pairs."""
    marker_index = text.find(_TRANSCRIPT_MARKER)
    body = text[marker_index + len(_TRANSCRIPT_MARKER):] if marker_index != -1 else text
    padded = "\n" + body.strip()

    matches = [m for m in _SPEAKER_RE.finditer(padded) if _looks_like_name(m.group(1).strip())]
    if not matches:
        return [(_FALLBACK_SECTION, body.strip())]

    turns = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(padded)
        turn_text = padded[match.start():end].strip()
        if turn_text:
            turns.append((match.group(1).strip(), turn_text))

    return turns
