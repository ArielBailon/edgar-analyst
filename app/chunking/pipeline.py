"""Chunking pipeline: reads ingested filings/transcripts, derives sections, chunks, and persists."""

import json
import re
from pathlib import Path

from app.chunking.chunker import chunk_text
from app.chunking.filing_sections import split_filing_sections
from app.chunking.models import Chunk
from app.chunking.transcript_sections import split_transcript_sections
from app.ingest.models import Filing, Transcript

FILINGS_DIR = Path("data/filings")
TRANSCRIPTS_DIR = Path("data/transcripts")
CHUNKS_DIR = Path("data/chunks")


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"


def _chunks_for_document(company: str, document_type: str, date, sections: list[tuple[str, str]]) -> list[Chunk]:
    chunks = []
    next_index_for_slug: dict[str, int] = {}
    for section_name, section_text in sections:
        section_slug = _slugify(section_name)
        for piece in chunk_text(section_text):
            index = next_index_for_slug.get(section_slug, 0)
            next_index_for_slug[section_slug] = index + 1
            chunks.append(
                Chunk(
                    id=f"{company}-{document_type}-{date}-{section_slug}-{index}",
                    company=company,
                    document_type=document_type,
                    section=section_name,
                    date=date,
                    text=piece,
                )
            )
    return chunks


def _write_chunks(company: str, document_type: str, date, chunks: list[Chunk]) -> Path:
    company_dir = CHUNKS_DIR / company
    company_dir.mkdir(parents=True, exist_ok=True)
    path = company_dir / f"{document_type}_{date}.json"
    path.write_text(
        json.dumps([chunk.model_dump(mode="json") for chunk in chunks], indent=2),
        encoding="utf-8",
    )
    return path


def chunk_all() -> list[Chunk]:
    """Chunk every persisted filing and transcript, writing one chunk file per source document."""
    all_chunks: list[Chunk] = []

    for path in sorted(FILINGS_DIR.glob("*/*.json")):
        filing = Filing.model_validate_json(path.read_text(encoding="utf-8"))
        sections = split_filing_sections(filing.raw_text)
        chunks = _chunks_for_document(filing.company, filing.filing_type, filing.date, sections)
        if not chunks:
            raise RuntimeError(f"No chunks produced for {path}")
        _write_chunks(filing.company, filing.filing_type, filing.date, chunks)
        all_chunks.extend(chunks)

    for path in sorted(TRANSCRIPTS_DIR.glob("*/*.json")):
        transcript = Transcript.model_validate_json(path.read_text(encoding="utf-8"))
        sections = split_transcript_sections(transcript.raw_text)
        chunks = _chunks_for_document(transcript.company, "transcript", transcript.date, sections)
        if not chunks:
            raise RuntimeError(f"No chunks produced for {path}")
        _write_chunks(transcript.company, "transcript", transcript.date, chunks)
        all_chunks.extend(chunks)

    return all_chunks


if __name__ == "__main__":
    result = chunk_all()
    print(f"Produced {len(result)} chunks into {CHUNKS_DIR}/")
