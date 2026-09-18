"""Embedding + indexing pipeline: embeds persisted chunks and upserts them into ChromaDB."""

import json
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

from app.chunking.models import Chunk

CHUNKS_DIR = Path("data/chunks")
CHROMA_DIR = Path("chroma_db")
COLLECTION_NAME = "edgar_chunks"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def _load_chunks(path: Path) -> list[Chunk]:
    records = json.loads(path.read_text(encoding="utf-8"))
    return [Chunk.model_validate(record) for record in records]


def index_all() -> int:
    """Embed every persisted chunk and upsert it into the ChromaDB collection. Returns the total indexed."""
    model = SentenceTransformer(EMBEDDING_MODEL)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    total = 0
    for path in sorted(CHUNKS_DIR.glob("*/*.json")):
        chunks = _load_chunks(path)
        if not chunks:
            raise RuntimeError(f"No chunks found in {path}")

        texts = [chunk.text for chunk in chunks]
        embeddings = model.encode(texts, show_progress_bar=False).tolist()

        collection.upsert(
            ids=[chunk.id for chunk in chunks],
            embeddings=embeddings,
            documents=texts,
            metadatas=[
                {
                    "company": chunk.company,
                    "document_type": chunk.document_type,
                    "section": chunk.section,
                    "date": chunk.date.isoformat(),
                }
                for chunk in chunks
            ],
        )
        total += len(chunks)

    return total


if __name__ == "__main__":
    result = index_all()
    print(f"Indexed {result} chunks into {COLLECTION_NAME} at {CHROMA_DIR}/")
