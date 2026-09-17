"""Data models for ingested SEC filings."""

from datetime import date
from typing import Literal

from pydantic import BaseModel


class Filing(BaseModel):
    company: str
    filing_type: Literal["10-K", "10-Q"]
    date: date
    raw_text: str
    source_url: str


class Transcript(BaseModel):
    company: str
    date: date
    raw_text: str
    source_url: str
