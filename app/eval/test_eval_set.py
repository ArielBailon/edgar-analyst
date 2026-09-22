"""Structural checks for the hand-labeled eval set.

Only checks the file's own internal shape: it never touches ChromaDB, the
embedding model, or `data/chunks/` (gitignored, absent on a fresh clone), so
`pytest` keeps needing no ingested data to pass.
"""

import json
from pathlib import Path

from app.eval.models import EvalPair

EVAL_SET_PATH = Path(__file__).parent / "eval_set.json"


def _load_records() -> list[dict]:
    return json.loads(EVAL_SET_PATH.read_text(encoding="utf-8"))


def test_eval_set_has_between_20_and_50_records():
    records = _load_records()
    assert 20 <= len(records) <= 50


def test_every_record_parses_as_an_eval_pair():
    records = _load_records()
    for record in records:
        EvalPair.model_validate(record)


def test_no_two_records_repeat_the_same_question():
    records = _load_records()
    questions = [record["question"] for record in records]
    assert len(questions) == len(set(questions))
