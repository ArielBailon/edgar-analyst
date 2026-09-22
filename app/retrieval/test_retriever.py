"""Unit tests for retrieval.

Nothing here touches ChromaDB, the sentence-transformers model, or the network: the
collection and the embedding model are both faked. Loading the real model costs
seconds and an 87 MB download on a cold cache, which would make the suite neither
fast nor deterministic.
"""

import pytest
from chromadb.errors import NotFoundError

from app.retrieval import retriever
from app.retrieval.models import RetrievalResult

SECTION = "Item 1A.\xa0\xa0\xa0\xa0Risk Factors"


@pytest.fixture(autouse=True)
def _reset_module_caches():
    """`retriever` caches the model and collection in module globals.

    Without this reset a handle cached by an earlier test is returned by a later one,
    which makes a missing-collection test pass for the wrong reason.
    """
    retriever._model = None
    retriever._collection_handle = None
    yield
    retriever._model = None
    retriever._collection_handle = None


class _FakeVectors:
    def __init__(self, rows: list[list[float]]) -> None:
        self._rows = rows

    def tolist(self) -> list[list[float]]:
        return self._rows


class _FakeModel:
    def __init__(self) -> None:
        self.encoded: list[list[str]] = []

    def encode(self, texts: list[str]) -> _FakeVectors:
        self.encoded.append(texts)
        return _FakeVectors([[0.1] * 384 for _ in texts])


class _FakeCollection:
    def __init__(self, response: dict | None = None, count: int = 3) -> None:
        self._response = response or _response()
        self._count = count
        self.queries: list[dict] = []

    def count(self) -> int:
        return self._count

    def query(self, **kwargs) -> dict:
        self.queries.append(kwargs)
        return self._response


def _response(n: int = 3) -> dict:
    rows = [
        ("AAPL", "10-Q", "2026-05-01", 0.727),
        ("AAPL", "10-K", "2025-10-31", 0.794),
        ("TSLA", "10-K", "2026-01-29", 0.851),
    ][:n]
    return {
        "ids": [[f"{c}-{t}-{d}-item-1a-risk-factors-{i}" for i, (c, t, d, _) in enumerate(rows)]],
        "documents": [[f"Body text {i}." for i, _ in enumerate(rows)]],
        "metadatas": [
            [
                {"company": c, "document_type": t, "section": SECTION, "date": d}
                for c, t, d, _ in rows
            ]
        ],
        "distances": [[dist for *_, dist in rows]],
    }


def _install(monkeypatch, collection=None, missing: bool = False):
    """Point the retriever at a fake collection and a fake embedding model."""
    collection = collection if collection is not None else _FakeCollection()
    created = []

    class _FakeClient:
        def get_collection(self, name):
            if missing:
                raise NotFoundError(f"Collection [{name}] does not exist")
            return collection

    def fake_persistent_client(path):
        created.append(path)
        return _FakeClient()

    monkeypatch.setattr(retriever.chromadb, "PersistentClient", fake_persistent_client)
    monkeypatch.setattr(retriever, "_embedding_model", _FakeModel)
    return collection, created


def test_module_caches_start_empty():
    """Proves the autouse reset fixture is doing its job, not decoration."""
    assert retriever._model is None
    assert retriever._collection_handle is None


@pytest.mark.parametrize("question", ["", "   ", "\n\t "])
def test_blank_question_raises(monkeypatch, question):
    _install(monkeypatch)

    with pytest.raises(ValueError, match="blank"):
        retriever.retrieve(question)


@pytest.mark.parametrize("top_k", [0, -1, -10])
def test_non_positive_top_k_raises(monkeypatch, top_k):
    _install(monkeypatch)

    with pytest.raises(ValueError, match="at least 1"):
        retriever.retrieve("a real question", top_k=top_k)


def test_returns_one_result_per_hit_in_order(monkeypatch):
    _install(monkeypatch)

    results = retriever.retrieve("supply chain concentration", top_k=3)

    assert len(results) == 3
    assert all(isinstance(result, RetrievalResult) for result in results)
    distances = [result.distance for result in results]
    assert distances == sorted(distances)


def test_maps_chroma_metadata_onto_the_citation(monkeypatch):
    _install(monkeypatch)

    first = retriever.retrieve("supply chain concentration")[0]

    assert first.citation.company == "AAPL"
    assert first.citation.document_type == "10-Q"
    assert first.citation.section == SECTION
    assert first.citation.date.isoformat() == "2026-05-01"
    assert first.citation.chunk_id == first.chunk_id
    assert first.text == "Body text 0."


def test_passes_top_k_through_as_n_results(monkeypatch):
    collection, _ = _install(monkeypatch)

    retriever.retrieve("a question", top_k=2)

    assert collection.queries[0]["n_results"] == 2


def test_requests_the_fields_the_citation_needs(monkeypatch):
    collection, _ = _install(monkeypatch)

    retriever.retrieve("a question")

    included = collection.queries[0]["include"]
    assert {"documents", "metadatas", "distances"} <= set(included)


def test_missing_collection_raises_with_the_reindex_command(monkeypatch):
    _install(monkeypatch, missing=True)

    with pytest.raises(RuntimeError, match=r"python -m app\.embedding\.pipeline"):
        retriever.retrieve("a question")


def test_empty_collection_raises_with_the_reindex_command(monkeypatch):
    _install(monkeypatch, collection=_FakeCollection(count=0))

    with pytest.raises(RuntimeError, match=r"python -m app\.embedding\.pipeline"):
        retriever.retrieve("a question")


def test_a_mismatched_response_raises_instead_of_truncating(monkeypatch):
    """Silently returning a short result set would misrepresent what actually matched."""
    broken = _response()
    broken["distances"] = [broken["distances"][0][:2]]
    _install(monkeypatch, collection=_FakeCollection(response=broken))

    with pytest.raises(ValueError):
        retriever.retrieve("a question")


def test_the_collection_is_resolved_once_per_process(monkeypatch):
    _, created = _install(monkeypatch)

    retriever.retrieve("first question")
    retriever.retrieve("second question")

    assert len(created) == 1


def test_a_cached_collection_does_not_hide_a_later_missing_one(monkeypatch):
    """The cache is why the reset fixture exists; this pins the behavior it protects."""
    _install(monkeypatch)
    retriever.retrieve("warms the cache")
    assert retriever._collection_handle is not None

    retriever._collection_handle = None
    _install(monkeypatch, missing=True)

    with pytest.raises(RuntimeError):
        retriever.retrieve("a question")
