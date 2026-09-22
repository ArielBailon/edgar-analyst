"""Data model for a generated, grounded answer and the citations it draws from."""

from pydantic import BaseModel

from app.retrieval.models import Citation


class AnswerResult(BaseModel):
    answer: str
    citations: list[Citation]
