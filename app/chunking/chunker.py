"""Paragraph-aware text chunking: splits long text into overlapping, size-bounded pieces."""

DEFAULT_CHUNK_SIZE = 1200
DEFAULT_OVERLAP = 150


def chunk_text(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_OVERLAP) -> list[str]:
    """Split text into chunks of roughly chunk_size characters, preferring paragraph breaks.

    Falls back to plain slicing only when a single paragraph exceeds chunk_size.
    """
    text = text.strip()
    if not text:
        return []

    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buffer = ""

    for paragraph in paragraphs:
        candidate = f"{buffer}\n\n{paragraph}" if buffer else paragraph
        if len(candidate) <= chunk_size:
            buffer = candidate
            continue

        if buffer:
            chunks.append(buffer)
            tail = buffer[-overlap:] if overlap > 0 else ""
            buffer = f"{tail}\n\n{paragraph}" if tail else paragraph
        else:
            buffer = paragraph

        while len(buffer) > chunk_size:
            chunks.append(buffer[:chunk_size])
            buffer = buffer[chunk_size - overlap:]

    if buffer:
        chunks.append(buffer)

    return chunks
