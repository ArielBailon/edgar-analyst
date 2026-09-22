"""Eval runner: score answer_question against the hand-labeled eval set."""

import json
from pathlib import Path

from sentence_transformers import SentenceTransformer, util

from app.embedding.pipeline import EMBEDDING_MODEL
from app.eval.models import EvalPair
from app.generation.generator import answer_question
from app.generation.models import AnswerResult
from app.retrieval.models import Citation

EVAL_SET_PATH = Path(__file__).parent / "eval_set.json"

_model: SentenceTransformer | None = None


def _embedding_model() -> SentenceTransformer:
    """Load the index-time embedding model once per process; relevance scoring runs in a loop."""
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def citation_matches(result: AnswerResult, expected_citation: Citation) -> bool:
    """True iff one of result's citations references the same chunk as expected_citation."""
    return any(citation.chunk_id == expected_citation.chunk_id for citation in result.citations)


def answer_relevance(actual_answer: str, expected_answer: str) -> float:
    """Cosine similarity between the two answers' embeddings, using the index-time model."""
    embeddings = _embedding_model().encode([actual_answer, expected_answer])
    return float(util.cos_sim(embeddings[0], embeddings[1]).item())


def _load_eval_set() -> list[EvalPair]:
    """Read and parse the hand-labeled eval set."""
    records = json.loads(EVAL_SET_PATH.read_text(encoding="utf-8"))
    return [EvalPair.model_validate(record) for record in records]


def run_eval() -> None:
    """Run every eval pair through answer_question and print citation and relevance scores."""
    pairs = _load_eval_set()
    citation_hits = 0
    relevance_scores = []

    for pair in pairs:
        result = answer_question(pair.question)
        matched = citation_matches(result, pair.expected_citation)
        relevance = answer_relevance(result.answer, pair.expected_answer)

        citation_hits += matched
        relevance_scores.append(relevance)

        status = "HIT" if matched else "MISS"
        print(f"[{status}] relevance={relevance:.3f} {pair.question}")

    print()
    print(f"Citation accuracy: {citation_hits}/{len(pairs)} ({citation_hits / len(pairs):.0%})")
    print(f"Average relevance: {sum(relevance_scores) / len(relevance_scores):.3f}")


if __name__ == "__main__":
    run_eval()
