"""Data model for retrieval-sized chunks derived from ingested filings and transcripts."""

from datetime import date
from typing import Literal

from pydantic import BaseModel


class Chunk(BaseModel):
    id: str
    company: str
    document_type: Literal["10-K", "10-Q", "transcript"]
    section: str
    date: date
    text: str
