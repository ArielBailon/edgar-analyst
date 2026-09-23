"""Answer generation: turn retrieved chunks into a grounded, cited answer via Claude."""

import os
import sys
import time

import anthropic
from anthropic.types import Usage
from dotenv import load_dotenv

from app.generation.models import AnswerResult
from app.logging.query_logger import log_query
from app.retrieval.models import RetrievalResult
from app.retrieval.retriever import DEFAULT_TOP_K, retrieve

load_dotenv()

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1024
DISTANCE_THRESHOLD = 1.0
REFUSAL_MESSAGE = (
    "The retrieved filings and transcripts do not contain information to "
    "answer this question."
)

SYSTEM_PROMPT = (
    "You are a financial analyst assistant. Answer the user's question using only "
    "the numbered context blocks provided below the question. Each block is one "
    "chunk of a SEC filing or earnings-call transcript.\n\n"
    "Rules:\n"
    "- Use only facts stated in the context blocks. Do not use outside knowledge.\n"
    "- After every claim, cite the block(s) it came from using its marker, "
    "for example [1] or [2][3].\n"
    "- If the context blocks do not contain the answer, say plainly that the "
    "provided filings and transcripts do not support an answer. Do not guess."
)

_client_handle: anthropic.Anthropic | None = None


def _client() -> anthropic.Anthropic:
    """Load the Anthropic client once per process; callers may generate answers in a loop."""
    global _client_handle
    if _client_handle is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Set it in .env (see .env.example)."
            )
        _client_handle = anthropic.Anthropic(api_key=api_key)
    return _client_handle


def _build_context(results: list[RetrievalResult]) -> str:
    """Render each result as a numbered block carrying its citation and text."""
    blocks = []
    for i, result in enumerate(results, start=1):
        citation = result.citation
        blocks.append(
            f"[{i}] {citation.company} {citation.document_type} {citation.date} "
            f"- {citation.section}\n{result.text}"
        )
    return "\n\n".join(blocks)


def _call_claude(question: str, results: list[RetrievalResult]) -> tuple[AnswerResult, Usage]:
    """Ask Claude for a grounded answer and return it with the response's token usage."""
    context = _build_context(results)
    response = _client().messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Question: {question}\n\nContext:\n{context}"}],
    )

    answer = AnswerResult(
        answer=response.content[0].text,
        citations=[result.citation for result in results],
    )
    return answer, response.usage


def generate_answer(question: str, results: list[RetrievalResult]) -> AnswerResult:
    """Generate a grounded answer to question from the given retrieved chunks."""
    if not question.strip():
        raise ValueError("question must not be blank")
    if not results:
        raise ValueError("results must not be empty")

    answer, _ = _call_claude(question, results)
    return answer


def answer_question(question: str, top_k: int = DEFAULT_TOP_K) -> AnswerResult:
    """Answer question from the local index, refusing when nothing retrieved is close enough.

    Every answered or refused call appends one QueryLog entry.
    """
    start = time.perf_counter()
    results = retrieve(question, top_k)
    if not results or results[0].distance >= DISTANCE_THRESHOLD:
        answer = AnswerResult(answer=REFUSAL_MESSAGE, citations=[])
        model, input_tokens, output_tokens = "", 0, 0
    else:
        answer, usage = _call_claude(question, results)
        model, input_tokens, output_tokens = MODEL, usage.input_tokens, usage.output_tokens

    log_query(
        question=question,
        retrieved_sources=[result.citation for result in results],
        model=model,
        latency_ms=round((time.perf_counter() - start) * 1000),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    return answer


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python -m app.generation.generator "<question>"')

    answer = answer_question(sys.argv[1])

    print(answer.answer)
    if answer.citations:
        print()
        print("Sources:")
        for citation in answer.citations:
            print(f"  {citation.company} {citation.document_type} {citation.date} - {citation.section}")
