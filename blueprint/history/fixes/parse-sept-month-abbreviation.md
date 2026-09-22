# Fix: Parse the Sept month abbreviation

**Type:** Fix
**Status:** verified
**Branch:** `fix/parse-sept-month-abbreviation`

## The problem

`parse_call_date` in `app/ingest/text_extract.py` raises `ValueError` on a date its
own month list accepts. `_MONTH_NAMES` (line 25) includes `Sept`, so
`_MONTH_DAY_YEAR_RE` happily matches `Sept. 9, 2025`. The parse loop then tries only
`%B` (full name, wants `September`) and `%b` (three letters, wants `Sep`). Neither
accepts `Sept`, so the loop falls through to the final
`raise ValueError(f"Could not parse date from: ...")` at line 136.

Verified during feature 9: `Sept` is the **only** token in `_MONTH_NAMES` where the
regex matches but `strptime` refuses. Every other entry parses.

Nothing is broken today: no ingested transcript currently uses this spelling, checked
across all six in `data/transcripts/`. But `transcripts_pipeline` calls
`parse_call_date` on every candidate page, and per the project error-handling standard
it fails loudly rather than skipping, so one September call published as `Sept.` would
abort the whole transcript ingest. Q3 earnings calls land in exactly that window.

Feature 9 recorded this as a `pytest.mark.xfail(strict=True)` in
`app/ingest/test_text_extract.py` rather than fixing it, because that spec forbade
editing code under test. `strict=True` means the suite **fails** once the defect is
repaired unless the marker is removed, so removing it is part of this fix, not
optional cleanup.

## The fix

Normalize the matched month token before handing it to `strptime`, mapping the
abbreviations the regex accepts but `strptime` does not onto ones it does.

Add a module-level alias map beside `_MONTH_NAMES`:

```python
_MONTH_ALIASES = {"sept": "Sep"}
```

and apply it to `month_name` after unpacking the match groups, keyed on the lowercased
token.

**Correction made during implementation:** this section originally claimed `Sept`,
`sept`, and `SEPT` would all normalize. That was wrong. `_MONTH_DAY_YEAR_RE` is
compiled without `re.IGNORECASE`, so a lowercase or uppercase month never matches the
regex and never reaches the alias lookup at all. Case sensitivity is deliberate:
`May`, `March`, and `August` are ordinary English words, and an `IGNORECASE` regex
would match them in running prose and parse a false date. Only the `Sept`
capitalization the regex already accepts is in scope; the `.lower()` on the lookup key
is defensive, not a case-insensitivity feature. A test now pins the case-sensitive
behavior so it is not mistaken for a bug later.

Deliberately **not** doing the other obvious thing: removing `Sept` from
`_MONTH_NAMES`. That would stop the regex matching `Sept. 9, 2025` at all, turning a
parse failure into a "no date found" failure. The transcript would still fail to
ingest, so it trades one error message for another instead of fixing anything.

Must not break: the two formats already covered by tests (`Thursday, July 30, 2026 at
5:00 p.m. ET` and `Oct. 23, 2024, 5:30 p.m. ET`), the full-name and three-letter
abbreviation forms, and the `ValueError` raised when no date is present at all. The
first-match-wins behavior stays as it is.

Out of scope: any other change to `text_extract.py`, adding a date-parsing dependency,
and re-running the ingest pipelines. Existing ingested data is unaffected because no
stored transcript uses this spelling.

## Build steps

- [x] 1. Add `_MONTH_ALIASES` to `app/ingest/text_extract.py` and normalize
  `month_name` through it inside `parse_call_date`. Then remove the
  `@pytest.mark.xfail(strict=True)` marker from
  `test_parse_call_date_handles_sept_abbreviation` in
  `app/ingest/test_text_extract.py` so it becomes an ordinary passing test, and fold
  the case back into the `test_parse_call_date_handles_observed_formats` parametrize
  list alongside the other formats. Add a case for the plain `Sep` spelling so both
  abbreviations are pinned.
  **Done when:** `pytest` reports all tests passed with **zero xfailed** (the count
  proves the marker is gone rather than silently still expected to fail), and
  `parse_call_date("Sept. 9, 2025, 4:00 p.m. ET")` returns `date(2025, 9, 9)`.

## Verify

1. `pytest` is green and the summary line shows no `xfailed` entry at all.
2. `pytest app/ingest/test_text_extract.py -q` passes, covering `Sept`, `Sep`,
   `September`, the full-name and abbreviated observed formats, and the no-date
   `ValueError`.
3. `python -c "from app.ingest.text_extract import parse_call_date; print(parse_call_date('Sept. 9, 2025, 4:00 p.m. ET'))"`
   prints `2025-09-09`.
4. `python -m compileall -q app` stays clean.


<!-- blueprint:completion {"schemaVersion":1,"specBytes":4615,"specSha256":"d5b2d228c705f1693af5fdd27da1ccb585d745377a71e64e74d1dfbd63744972","branch":"refs/heads/fix/parse-sept-month-abbreviation","head":"020d4fc433a96f3700e49bbe47aea0b4fd4c2794","baseRef":"refs/heads/master","baseCommit":"020d4fc433a96f3700e49bbe47aea0b4fd4c2794","sourceTree":"9b6b5e3ddea11b7f90dae57ce39a4326e144ec45","absentOptional":[]} -->
