# Feature: Deterministic Tests

**From build-plan:** feature 9
**Build attempt:** 1
**Status:** verified
**Branch:** `feature/deterministic-tests`

## Goal

Cover the pure logic of ingest, chunking, and retrieval with pytest, so the five
shipped features stop depending on manual runs against a local index for their
correctness claims. Every test must pass on a fresh clone with no ingested data and
no network.

## In scope

- Focused unit tests for the parsing, selection, splitting, id-building, and
  validation logic across `app/ingest/`, `app/chunking/`, and `app/retrieval/`.
- Expanding the three placeholder tests in `app/chunking/test_chunker.py` that
  `/tests` added to prove the runner, into real coverage of `chunk_text`.
- Fakes and `monkeypatch` for the three things a unit test must never touch: the
  network, the ChromaDB collection, and the sentence-transformers model.
- The pytest setup currently uncommitted on `master` (`pytest.ini`, the first
  `test_chunker.py`, the pytest pins in `requirements.txt`, and the `AGENTS.md` and
  `coding-standards.md` updates). It was produced by `/tests` for this feature and
  belongs in this feature's commit.

## Out of scope

- Testing functions whose only job is a network round trip: `fetch_submissions`,
  `fetch_filing_document`, `fetch_sitemap`, `fetch_transcript_page`, and
  `discover_transcript_urls`. The project standard excludes integration-level
  surfaces that drive an external service.
- End-to-end pipeline tests that write `data/` or `chroma_db/`. Those directories
  are gitignored and absent on a fresh clone, so a test depending on them is not
  deterministic.
- Coverage measurement, coverage thresholds, CI, and browser testing. `/ci` owns
  verification and CI; `/tests browser` owns a browser harness.
- The eval set and eval runner (items 10 and 11). Those score answer quality and are
  a different kind of check from these deterministic unit tests.
- Any change to the code under test. If a test exposes a real defect, stop and raise
  it rather than editing product code inside this feature.

## Build loop

`workflow.stepReview` is `feature`, so implement all build steps in order and present
one review packet after the last step. `workflow.checkpointCommits` is `disabled`, so
no per-step commits; `/complete` creates the single feature commit.

`AGENTS.md` now declares `Test: pytest`, so the suite is the gate: it must be green
before each step is checked and before `/complete`. No `Verify` command exists yet,
so `pytest` plus `python -m compileall app` are the final checks.

## Build steps

- [x] 1. Add `app/ingest/test_text_extract.py` covering `clean_text`,
  `extract_article_text`, and `parse_call_date`. Include the behavior these exist for:
  `clean_text` drops `script`, `style`, `display:none`, and `hidden` content (the
  Inline XBRL metadata case) while keeping visible text; `extract_article_text`
  returns only the matching container's content and excludes surrounding site chrome;
  `parse_call_date` parses both observed formats (`Thursday, July 30, 2026 at 5:00
  p.m. ET` and `Oct. 23, 2024, 5:30 p.m. ET`) and raises `ValueError` when no date is
  present.
  **Done when:** `pytest` is green and the new file's tests cover all three functions
  including the `ValueError` path.

- [x] 2. Add `app/ingest/test_edgar_client.py`, `app/ingest/test_fool_client.py`, and
  `app/ingest/test_http_client.py`. Cover `select_filings` (picks the most recent
  1x10-K and 2x10-Q from a hand-built submissions dict, ignores other forms, and
  raises `RuntimeError` when a wanted form is short), `filing_document_url` (strips
  dashes from the accession number), `_user_agent` (raises `RuntimeError` when the env
  var is unset, using `monkeypatch.delenv`), `extract_transcript_urls` (matches only
  slugs containing the ticker token, so `AAPL` does not match a `GOOGL` URL),
  `_months_back` (returns the requested count and rolls the year backwards correctly),
  and `get_with_retry` (returns on first success, retries a transient `URLError` then
  succeeds, and re-raises after `MAX_ATTEMPTS`).
  **Done when:** `pytest` is green, no test performs real network I/O, and the retry
  test runs fast because `time.sleep` is monkeypatched.

- [x] 3. Expand `app/chunking/test_chunker.py` and add
  `app/chunking/test_filing_sections.py`, `app/chunking/test_transcript_sections.py`,
  and `app/chunking/test_pipeline.py`. Cover `chunk_text` overlap and the
  single-oversized-paragraph fallback; `strip_repeated_lines` (removes a short line
  repeated at or above the threshold, keeps a long line and an infrequent one);
  `split_filing_sections` (splits on real Item headings, picks the occurrence starting
  the largest content span so a table of contents does not win, and falls back to
  `Full Document` with fewer than two headings); `split_transcript_sections` (discards
  front matter before the marker, splits on speaker turns, rejects a mid-sentence
  match that is not Title Case, and falls back to `Full Transcript`); `_slugify`; and
  `_chunks_for_document` (ids follow
  `{company}-{document_type}-{date}-{section_slug}-{index}` and are unique across
  repeated section names).
  **Done when:** `pytest` is green and chunk ids are asserted unique within a document
  whose sections repeat a slug.

- [x] 4. Add `app/retrieval/test_models.py` and `app/retrieval/test_retriever.py`.
  Cover `Citation` (ISO date string coerces to `date`, a `document_type` outside the
  three allowed values raises `ValidationError`, and a non-breaking-space section name
  survives unchanged). For `retrieve`, monkeypatch both `_embedding_model` and the
  collection so no model loads and no ChromaDB is touched: assert argument validation
  (blank question and `top_k < 1` raise `ValueError`), the mapping from a fake
  ChromaDB response to ordered `RetrievalResult` objects with populated citations, the
  `RuntimeError` naming the re-index command for a missing collection and for an empty
  one, and that a mismatched fake response raises rather than silently truncating.
  Add an autouse fixture in this module resetting `_model` and `_collection_handle`.
  **Done when:** `pytest` is green, the full suite runs in under about five seconds
  because no model or database is loaded, and deleting the autouse reset fixture makes
  at least one test fail (confirming the fixture is load-bearing, not decorative).

  **Measured outcome:** the "no model or database is loaded" half is proven: every
  test duration is under 0.005 s, so `--durations` reports none. The five second wall
  clock is not met and is not reachable from a test file. Collection alone, running
  zero tests, costs about 22 s because `app/retrieval/retriever.py` imports
  `sentence_transformers` (and therefore torch) at module scope; the whole 100 test
  suite then finishes in about 18 s. Moving that import inside `_embedding_model()`
  would fix it, but that edits code under test, which this spec forbids. Raised as a
  follow-up `/fix` instead.

## Files / areas

New test files, each beside the source it covers:

- `app/ingest/test_text_extract.py`
- `app/ingest/test_edgar_client.py`
- `app/ingest/test_fool_client.py`
- `app/ingest/test_http_client.py`
- `app/chunking/test_filing_sections.py`
- `app/chunking/test_transcript_sections.py`
- `app/chunking/test_pipeline.py`
- `app/retrieval/test_models.py`
- `app/retrieval/test_retriever.py`

Modified:

- `app/chunking/test_chunker.py` - expand the three runner-proving tests.

Carried in from the `/tests` setup, already on disk and uncommitted:

- `pytest.ini`, `requirements.txt`, `AGENTS.md`, `blueprint/context/coding-standards.md`

Read only, never modified by this feature: every module under `app/`.

## Data / contracts

- Test discovery is `pytest.ini`: `pythonpath = .`, `testpaths = app`. Files are
  `test_<module>.py` beside their source.
- Fixture data is built inline in each test as small literals. Do not add fixture
  files, factories, or a shared fixtures package; the inputs here are a few lines of
  HTML, text, or dict each.
- The ChromaDB query response shape a retrieval fake must reproduce, as established by
  `app/embedding/pipeline.py` and consumed by `retrieve`: `ids`, `documents`,
  `metadatas`, and `distances`, each a list containing one list per query. Metadata
  keys are exactly `company`, `document_type`, `section`, and `date` (ISO string).
- `_slugify` and `_chunks_for_document` are private but are the chunk id contract, and
  the project standard names id and slug builders as in-scope logic. Test them
  directly rather than reaching them through `chunk_all`, which does disk I/O.

## Testing

This feature is the tests. `AGENTS.md` declares `Test: pytest`, so the gate applies to
this work itself: the suite must be green before any step is checked.

Assert real behavior, not implementation shape. Per the project standard, avoid weak
assertions that only mirror the code, and never record a coverage percentage. An empty
or non-collecting suite is a failure, not a pass.

Do not add pytest plugins, coverage tooling, or new dependencies. `monkeypatch` is
built into pytest and is the only mocking mechanism needed here.

## Notes for the AI

- **No test may touch the network, `data/`, or `chroma_db/`.** Both directories are
  gitignored and absent on a fresh clone. This is the constraint that makes the suite
  deterministic and is the main thing to get right.
- **Never construct a real `SentenceTransformer` in a test.** It loads an 87 MB model
  and would make the suite slow and network-dependent on a cold cache. Monkeypatch
  `_embedding_model`.
- `retriever.py` caches `_model` and `_collection_handle` in module globals. Without a
  reset fixture a stale handle makes a missing-collection test pass for the wrong
  reason; this was hit for real during feature 5's repair, and step 4 asserts the
  fixture is load-bearing.
- `_months_back` reads `date.today()`. Assert structure and year rollover rather than
  hardcoded months, or the test starts failing on a calendar boundary.
- Section names from real filings contain non-breaking spaces. Where a test asserts on
  section text, use explicit `\xa0` rather than a normal space so the test documents
  the real data.
- If a test exposes a genuine defect in product code, stop and report it. Do not fix
  product code inside this feature, and do not weaken the test to make it pass.
- Type hints on test helpers are welcome but pytest test functions do not need return
  annotations. Keep tests boring and readable.
- No em dashes anywhere. Comment the why, not the what, and skip comments restating
  the code.


<!-- blueprint:completion {"schemaVersion":1,"specBytes":10655,"specSha256":"6a20002c1e469d2036673df6bba625386416e6fac90e886aa413b1bfffa89a65","branch":"refs/heads/feature/deterministic-tests","head":"227d9bb87a8b64d2fccf564019a1c50221c31689","baseRef":"refs/heads/master","baseCommit":"227d9bb87a8b64d2fccf564019a1c50221c31689","sourceTree":"8e3ed30669e52d038eacb7da5a8bfad24a83a67e","absentOptional":[]} -->
