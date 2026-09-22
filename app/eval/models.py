"""Data models for the hand-labeled eval set."""

from pydantic import BaseModel

from app.retrieval.models import Citation


class EvalPair(BaseModel):
    question: str
    expected_answer: str
    expected_citation: Citation
