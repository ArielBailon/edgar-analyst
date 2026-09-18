"""Retrieval: embed a question and return the most relevant indexed chunks with their citations."""

import sys

import chromadb
from chromadb.errors import NotFoundError
from sentence_transformers import SentenceTransformer

from app.embedding.pipeline import CHROMA_DIR, COLLECTION_NAME, EMBEDDING_MODEL
from app.retrieval.models import Citation, RetrievalResult

DEFAULT_TOP_K = 5

REINDEX_HINT = "Run `python -m app.embedding.pipeline` to build the index."

_model: SentenceTransformer | None = None
_collection_handle: chromadb.Collection | None = None


def _embedding_model() -> SentenceTransformer:
    """Load the index-time embedding model once per process; loading it costs seconds."""
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def _collection() -> chromadb.Collection:
    """Resolve the indexed collection once per process; callers query it in a loop."""
    global _collection_handle
    if _collection_handle is not None:
        return _collection_handle

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        collection = client.get_collection(COLLECTION_NAME)
    except NotFoundError as error:
        raise RuntimeError(
            f"Collection '{COLLECTION_NAME}' does not exist at {CHROMA_DIR}/. {REINDEX_HINT}"
        ) from error
    if collection.count() == 0:
        raise RuntimeError(
            f"Collection '{COLLECTION_NAME}' at {CHROMA_DIR}/ is empty. {REINDEX_HINT}"
        )

    _collection_handle = collection
    return _collection_handle


def retrieve(question: str, top_k: int = DEFAULT_TOP_K) -> list[RetrievalResult]:
    """Return the top_k indexed chunks nearest to the question, nearest first."""
    if not question.strip():
        raise ValueError("question must not be blank")
    if top_k < 1:
        raise ValueError(f"top_k must be at least 1, got {top_k}")

    collection = _collection()
    query_embedding = _embedding_model().encode([question]).tolist()
    response = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    return [
        RetrievalResult(
            chunk_id=chunk_id,
            text=text,
            citation=Citation(**metadata, chunk_id=chunk_id),
            distance=distance,
        )
        for chunk_id, text, metadata, distance in zip(
            response["ids"][0],
            response["documents"][0],
            response["metadatas"][0],
            response["distances"][0],
            strict=True,
        )
    ]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python -m app.retrieval.retriever "<question>"')

    for result in retrieve(sys.argv[1]):
        citation = result.citation
        print(f"[{result.distance:.4f}] {citation.company} {citation.document_type} {citation.date}")
        print(f"  section: {citation.section}")
        print(f"  chunk:   {result.chunk_id}")
        print(f"  text:    {result.text[:160].strip()}")
        print()
