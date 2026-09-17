# Feature: SEC EDGAR Filings Ingest Pipeline

**From build-plan:** feature 1
**Build attempt:** 1
**Status:** verified
**Branch:** `feature/sec-edgar-filings-ingest-pipeline`

## Goal

Download and parse a small, fixed set of real 10-K/10-Q filings from SEC EDGAR
for Apple (AAPL), Microsoft (MSFT), and Tesla (TSLA) into clean text with
citation metadata, and persist them locally so the next build steps (chunking,
indexing, retrieval) have real data to work against.

## In scope

- Fetching each company's filing history from SEC EDGAR's `data.sec.gov`
  submissions API for a fixed CIK list (AAPL, MSFT, TSLA).
- Selecting, per company, the 1 most-recent `10-K` and the 2 most-recent
  `10-Q` filings.
- Downloading each selected filing's primary document from
  `www.sec.gov/Archives/edgar/...`.
- Extracting clean plain text from that HTML document (tags, scripts, and
  styles stripped; whitespace collapsed).
- Persisting each filing as a `Filing` record (company, filing_type, date,
  raw_text, source_url) to local JSON files.
- Sending the SEC-required descriptive `User-Agent` header (contact identity)
  on every EDGAR request, sourced from a `.env` value, never hardcoded.

## Out of scope

- Earnings-call transcript ingestion (build-plan item 2).
- Chunking, embeddings, indexing, retrieval, or answer generation (items 3-6).
- CLI, tests, eval set/runner, logging (items 8-13) - item 9 explicitly owns
  adding pytest coverage for this ingestion code; this feature does not add a
  test runner.
- Any company beyond AAPL/MSFT/TSLA, or filings beyond the fixed
  1x10-K + 2x10-Q per company set.
- Rate-limiting machinery for SEC's request-volume limits - the fixed set is
  ~12 requests total, well under them. (A minimal 3-attempt retry for
  transient connection timeouts was added during implementation - see Notes
  for the AI. That addresses network reliability, not SEC rate limits, and
  adds no backoff/rate-limit logic.)
- FastAPI, Streamlit, Docker (post-MVP items 14-17).

## Build loop

Build one small step at a time. Follow `workflow.stepReview` in
`blueprint/config.json`: currently `feature`, so this produces one review
packet after all steps complete (no per-step approval pauses).
`workflow.checkpointCommits` is `disabled`, so no checkpoint commits are
offered mid-feature. `/complete` makes the final feature commit. Never accept
a review packet that has not been read; split any diff that is too large to
review.

## Build steps

- [x] **Step 1 - EDGAR client** - add `app/ingest/edgar_client.py` with a fixed
  `COMPANIES` list (ticker, CIK, name) for AAPL (CIK 0000320193), MSFT (CIK
  0000789019), and TSLA (CIK 0001318605); a function to fetch and parse a
  company's `data.sec.gov/submissions/CIK##########.json`; and a function to
  select the 1 most-recent `10-K` and 2 most-recent `10-Q` entries by
  `filingDate`. Every request sets `User-Agent` from the `SEC_EDGAR_USER_AGENT`
  env var (loaded via `python-dotenv`); missing the env var raises immediately
  instead of sending an unidentified request. Add `.env.example` documenting
  `SEC_EDGAR_USER_AGENT=Your Name your@email.com`. *Done when:* running the
  submissions fetch + selection for one real CIK (e.g. AAPL) returns exactly 1
  `10-K` and 2 `10-Q` entries with accession numbers and primary document
  names, verified by a manual run.
- [x] **Step 2 - Text extraction** - add `app/ingest/text_extract.py` with
  `clean_text(html: str) -> str`, built on stdlib `html.parser.HTMLParser`,
  that drops `<script>`/`<style>` content and tags, decodes entities, and
  collapses whitespace. *Done when:* running it on a real downloaded filing
  document (from Step 1's selection) produces non-empty plain text with no
  `<`/`>` tag markup remaining, verified by manual inspection of the output.
- [x] **Step 3 - Filing model** - add `app/ingest/models.py` with a pydantic
  `Filing` model: `company: str`, `filing_type: Literal["10-K", "10-Q"]`,
  `date: date`, `raw_text: str`, `source_url: str`, matching the Data model in
  `project-overview.md`. *Done when:* constructing a `Filing` from one real
  extracted document (Steps 1-2's output) validates without error, and passing
  an invalid `filing_type` raises a validation error.
- [x] **Step 4 - Pipeline + storage** - add `app/ingest/pipeline.py` with
  `ingest_all() -> list[Filing]` that, for each company in `COMPANIES`, fetches
  submissions, selects filings (Step 1), downloads each primary document,
  cleans it (Step 2), builds a `Filing` (Step 3), and writes it as
  `data/filings/<TICKER>/<filing_type>_<date>.json`. A document that fails to
  download or parse raises rather than being silently skipped. Add a
  `if __name__ == "__main__":` guard calling `ingest_all()` for manual runs.
  Add `data/` to `.gitignore`. *Done when:* running
  `python -m app.ingest.pipeline` against live SEC EDGAR produces exactly 9
  JSON files under `data/filings/` (3 companies x 3 filings each), each with a
  non-empty `raw_text`, correct `company`/`filing_type`/`date`, and a valid
  `source_url`.

## Files / areas

- `app/ingest/__init__.py` - new package
- `app/ingest/edgar_client.py` - new: SEC EDGAR HTTP client + fixed company
  config
- `app/ingest/text_extract.py` - new: HTML-to-clean-text extraction
- `app/ingest/models.py` - new: `Filing` pydantic model
- `app/ingest/pipeline.py` - new: orchestration + local JSON persistence
- `.env.example` - new: documents `SEC_EDGAR_USER_AGENT`
- `.gitignore` - add `data/` (downloaded filings are local generated data)

## Data / contracts

- **Filing** (matches `project-overview.md`): `company` (ticker string),
  `filing_type` (`"10-K"` | `"10-Q"`), `date` (filing date), `raw_text`
  (cleaned plain text), `source_url` (the exact SEC Archives URL the document
  was fetched from). Stored one JSON file per filing at
  `data/filings/<TICKER>/<filing_type>_<date>.json`. Later features (chunking,
  item 3) read this exact shape and path convention - do not change it without
  updating them.
- Fixed company list (ticker -> CIK): AAPL -> 0000320193, MSFT -> 0000789019,
  TSLA -> 0001318605.
- External API boundary: SEC EDGAR (`data.sec.gov`, `www.sec.gov`), public, no
  auth, but requires a descriptive `User-Agent` (SEC's fair-access policy) on
  every request - sourced from `SEC_EDGAR_USER_AGENT` in `.env`, never
  committed or hardcoded.
- No database; no multi-user or auth boundary in this feature.

## Testing

- No test runner is configured yet (`AGENTS.md` declares none); build-plan
  item 9 explicitly owns adding pytest coverage for ingestion, so this feature
  does not add one.
- Verify each step manually against the real SEC EDGAR API per its *Done
  when*, since these steps depend on live network data and a runner isn't in
  scope here. Confirm the final `data/filings/` output by inspecting a couple
  of the generated JSON files for readable `raw_text` and correct metadata.

## Notes for the AI

- Use stdlib `urllib.request` for HTTP and stdlib `html.parser` for text
  extraction - no new dependency is needed (`pydantic` and `python-dotenv` are
  already in `requirements.txt` and unused so far).
- Fail loudly: raise on HTTP errors, missing `SEC_EDGAR_USER_AGENT`, or a
  company with fewer than 1 `10-K`/2 `10-Q` available, rather than skipping
  silently - citation accuracy later depends on knowing exactly what was
  ingested.
- CIK values in EDGAR URLs need different padding in different places: the
  submissions JSON filename wants a 10-digit zero-padded CIK
  (`CIK0000320193.json`), while the Archives document URL wants the CIK
  without leading zeros (`.../data/320193/...`).
- Accession numbers appear with dashes in the submissions JSON
  (`0000320193-24-000123`) but the Archives document path needs them without
  dashes (`000032032024000123`).
- `edgar_client._get` retries up to 3 attempts (2s delay) on `URLError` -
  connections to SEC EDGAR from this environment timed out intermittently
  during implementation; this is transient network resilience, not SEC
  rate-limit handling.
- SEC filings are Inline XBRL: the primary HTML document embeds a
  `display:none` block of XBRL tagging metadata before the human-readable
  body. `text_extract.clean_text` must skip any element hidden via
  `display:none` or the `hidden` attribute, not just `<script>`/`<style>`, or
  the extracted text is dominated by XBRL noise instead of filing prose.


<!-- blueprint:completion {"schemaVersion":1,"specBytes":8406,"specSha256":"78bdcffb1c1c6ea7e92e8d5901aa996db8bb5fc6560c9b6fffdae658b3320e6b","branch":"refs/heads/feature/sec-edgar-filings-ingest-pipeline","head":"bc29097ac5d17af4384fe52f5093cca410369f5a","baseRef":"refs/heads/master","baseCommit":"bc29097ac5d17af4384fe52f5093cca410369f5a","sourceTree":"a876799875273f703aa1e29844f8cf10292f4837","absentOptional":[]} -->
