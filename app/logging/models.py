"""Data model for one structured log entry per answered question."""

from datetime import datetime

from pydantic import BaseModel

from app.retrieval.models import Citation


class QueryLog(BaseModel):
    timestamp: datetime
    question: str
    retrieved_sources: list[Citation]
    model: str
    latency_ms: int
    tokens: int
    cost: float
