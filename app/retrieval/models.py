"""Data models for retrieval results and the citations that identify their sources."""

from datetime import date
from typing import Literal

from pydantic import BaseModel


class Citation(BaseModel):
    company: str
    document_type: Literal["10-K", "10-Q", "transcript"]
    section: str
    date: date
    chunk_id: str


class RetrievalResult(BaseModel):
    chunk_id: str
    text: str
    citation: Citation
    distance: float
