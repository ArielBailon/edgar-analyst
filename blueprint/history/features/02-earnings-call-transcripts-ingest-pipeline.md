# Feature: Earnings Call Transcripts Ingest Pipeline

**From build-plan:** feature 2
**Build attempt:** 1
**Status:** verified
**Branch:** `feature/earnings-call-transcripts-ingest-pipeline`

## Goal

Download and parse a small, fixed set of real earnings-call transcripts for the
same three companies as feature 1 (AAPL, MSFT, TSLA) from Motley Fool's public
transcript pages into a `Transcript` record, and persist them locally so later
build steps (chunking, indexing, retrieval) have real transcript data alongside
the filings from feature 1.

## Source change from the original spec

This spec originally targeted the Financial Modeling Prep (FMP) API. During
Step 1's live verification, FMP's transcript endpoints returned HTTP 402/403 on
a real free-tier key: the legacy `v3`/`v4` endpoints are closed to new users
("Legacy Endpoint... only available for legacy users who have valid
subscriptions prior to August 31, 2025") and the current `stable` endpoint is
plan-restricted ("Restricted Endpoint... not available under your current
subscription"). FMP no longer offers transcript access on any free tier. The
user chose to switch to scraping Motley Fool (fool.com) instead. Everything
below reflects that source; the `fmp_client.py` code from the abandoned attempt
was deleted.

## In scope

- Discovering each company's recent earnings-call transcript URLs on
  `fool.com` via its public monthly sitemaps
  (`https://www.fool.com/sitemap/<YYYY>/<MM>`), scanning back a bounded window
  of months.
- Selecting the 2 most recent transcripts per company.
- Fetching each selected transcript page and extracting just its transcript
  article body (not surrounding site chrome/ads/related content).
- Parsing the real earnings-call date out of the transcript's own "DATE"
  heading (not the article's publish date, which can lag the call by over a
  week).
- Persisting each transcript as a `Transcript` record (company, date, raw_text,
  source_url) to local JSON files, matching the `project-overview.md` data
  model.
- Sending a descriptive `User-Agent` on every fool.com request as reasonable
  scraping etiquette (fool.com's `robots.txt` does not disallow `/earnings/` or
  `/sitemap/` for general crawlers; no API key or login is involved).

## Out of scope

- Any transcript source other than fool.com scraping (FMP, Seeking Alpha,
  manual files) - abandoned or not chosen.
- Any company beyond AAPL/MSFT/TSLA, or more than the fixed 2 most-recent
  transcripts per company.
- Chunking, embeddings, indexing, retrieval, or answer generation (build-plan
  items 3-6).
- CLI, tests, eval set/runner, logging (items 8-13) - item 9 explicitly owns
  adding pytest coverage for ingestion code; this feature does not add a test
  runner.
- Rate-limiting/backoff machinery beyond the existing 3-attempt transient-retry
  pattern - the fixed set is at most ~9 monthly-sitemap fetches (shared across
  all 3 companies) plus 6 transcript-page fetches, well under any reasonable
  volume for a handful of manual runs.
- Guaranteeing the literal single most-recent transcript is always found:
  Motley Fool's own slug format is not perfectly consistent (one observed AAPL
  transcript's URL omitted the ticker), so discovery matches on a ticker token
  in the URL and accepts that a slug-format outlier could be skipped in favor
  of the next-most-recent match. This is a disclosed scraping limitation, not
  a silent failure - discovery still fails loudly if fewer than 2 matches turn
  up within the scan window.

## Build loop

Build one small step at a time. Follow `workflow.stepReview` in
`blueprint/config.json`: currently `feature`, so this produces one review
packet after all steps complete (no per-step approval pauses).
`workflow.checkpointCommits` is `disabled`, so no checkpoint commits are
offered mid-feature. `/complete` makes the final feature commit. Never accept
a review packet that has not been read; split any diff that is too large to
review.

## Build steps

- [x] **Step 0 - Shared HTTP helper (carried over)** - `app/ingest/http_client.py`
  with `get_with_retry` already exists from this feature's abandoned FMP
  attempt (extracted out of `edgar_client._get`); no further change needed.
  Confirmed done: `edgar_client` imports and uses it, verified by import.
- [x] **Step 1 - Fool transcript discovery** - add `app/ingest/fool_client.py`
  with: a `USER_AGENT` constant identifying this project; a function that
  fetches one month's sitemap from
  `https://www.fool.com/sitemap/{year}/{month:02d}` via `get_with_retry`; a
  function that extracts `<loc>` URLs matching
  `/earnings/call-transcripts/.../` whose slug contains `-{ticker.lower()}-q`
  from that sitemap's XML; and `discover_transcript_urls()` that scans back up
  to 9 months from the current month (shared across all companies - fetch each
  month's sitemap once, filter per ticker) and returns each ticker's
  deduplicated candidate URLs, unsorted. Import the ticker list from
  `edgar_client.COMPANIES`. Do not select "most recent" here: the sitemap
  listing month is only a discovery filter, not a trustworthy recency signal
  (see Notes for the AI) - final selection happens in Step 3 after each
  candidate's real call date is parsed. *Done when:* running discovery for one
  real ticker (e.g. AAPL) against the live site returns at least 2 candidate
  transcript URLs, verified by a manual run. Done - verified live: AAPL, MSFT,
  and TSLA each returned exactly 2 candidates within the 6-month window.
- [x] **Step 2 - Transcript extraction + model** - add `extract_article_text(html:
  str) -> str` and `parse_call_date(article_text: str) -> date` to
  `app/ingest/text_extract.py`: `extract_article_text` isolates the
  `<div id="article-body-transcript">` container (tracking tag depth to find
  its matching close tag, reused via a `container_id` parameter on the
  existing collector so `clean_text`'s hidden-element logic is shared, not
  duplicated) so site chrome outside the container never reaches the output;
  `parse_call_date` finds the text following the transcript's "DATE" heading
  and parses the month/day/year into a `date`, ignoring weekday and time, and
  handling both the full-month and abbreviated-month formats found live.
  Add a `Transcript` pydantic model to `app/ingest/models.py`: `company: str`,
  `date: date`, `raw_text: str`, `source_url: str`, matching the Data model in
  `project-overview.md` (no `filing_type`, since a transcript is not a
  filing). *Done when:* `extract_article_text` on a real fetched transcript
  page produces non-empty text with no `<`/`>` markup and no leftover nav/ad
  text, `parse_call_date` returns the correct real call date from that same
  page, and constructing a `Transcript` from that output validates without
  error - all verified by manual inspection against one real page. Done -
  verified live against the real AAPL Q3 2026 page (parsed date 2026-07-30,
  matching its actual call date) and the mislabeled TSLA page from Step 1
  (parsed date 2024-10-23, matching its real DATE heading despite the
  misleading URL/slug) - both formats parse correctly.
- [x] **Step 3 - Pipeline + storage** - add
  `app/ingest/transcripts_pipeline.py` with `ingest_all_transcripts() ->
  list[Transcript]` that, for each company: discovers candidate URLs (Step 1),
  fetches every candidate page and parses its real call date (Step 2) first,
  then selects the 2 candidates with the most recent parsed dates (never by
  the sitemap/URL date), builds a `Transcript` for each selected one
  (company=ticker, date=parsed call date, raw_text=extracted text,
  source_url=the transcript page URL), and writes it as
  `data/transcripts/<TICKER>/<date>.json`. A transcript that fails to fetch,
  isolate, or parse raises rather than being silently skipped; fewer than 2
  successfully-dated candidates for any company also raises. Add an `if
  __name__ == "__main__":` guard calling `ingest_all_transcripts()` for manual
  runs. *Done when:* running `python -m app.ingest.transcripts_pipeline`
  against the live site produces exactly 6 JSON files under
  `data/transcripts/` (3 companies x 2 transcripts each), each with non-empty
  `raw_text` containing no HTML markup, a correct `company`/`date` matching
  that transcript's real earnings call, and a `source_url` that is the real
  fool.com page it came from. Done - verified live: 6 files generated
  (AAPL 2026-04-30/2026-07-30, MSFT 2026-04-29/2026-07-29, TSLA
  2026-01-28/2026-07-22), spot-checked two for clean text and correct
  metadata.

## Files / areas

- `app/ingest/http_client.py` - already added (Step 0, carried over)
- `app/ingest/edgar_client.py` - already refactored to use the shared helper
  (Step 0, carried over)
- `app/ingest/fool_client.py` - new: sitemap-based transcript discovery
- `app/ingest/text_extract.py` - modified: add `extract_article_text` and
  `parse_call_date`
- `app/ingest/models.py` - modified: add `Transcript` pydantic model
- `app/ingest/transcripts_pipeline.py` - new: orchestration + local JSON
  persistence
- `.gitignore` - no change needed; `data/` is already ignored (feature 1)
- `.env.example` - no change needed; no API key or login is required for this
  source

## Data / contracts

- **Transcript** (matches `project-overview.md`): `company` (ticker string),
  `date` (the real earnings-call date, parsed from the transcript page's own
  "DATE" heading), `raw_text` (extracted transcript body text, no markup),
  `source_url` (the exact fool.com transcript page URL, freely browsable by
  anyone - unlike the abandoned FMP approach, this is a real public citation
  target). Stored one JSON file per transcript at
  `data/transcripts/<TICKER>/<date>.json`. Later features (chunking, item 3)
  read this exact shape and path convention alongside `Filing` - do not change
  either without updating them.
- Same fixed company list as feature 1 (only the ticker matters here, not the
  CIK): AAPL, MSFT, TSLA - imported from `edgar_client.COMPANIES` rather than
  redefined, so the two "same companies" lists in the overview can't drift
  apart.
- External source boundary: `fool.com` (public site, no auth, no API key).
  Respect `robots.txt` (already checked: `/earnings/` and `/sitemap/` are not
  disallowed for general crawlers) and send a descriptive `User-Agent`. This is
  HTML scraping, not a stable versioned API - if fool.com changes its
  `article-body-transcript` container id/class or sitemap structure in the
  future, extraction will need updating; that fragility is accepted as the
  tradeoff for a free, ToS-compatible, citable source.
- No database; no multi-user or auth boundary in this feature.

## Testing

- No test runner is configured yet (`AGENTS.md` declares none); build-plan
  item 9 explicitly owns adding pytest coverage for ingestion, so this feature
  does not add one.
- Verify each step manually against the real fool.com site per its *Done
  when*, since these steps depend on live network/HTML structure and a runner
  isn't in scope here. Confirm the final `data/transcripts/` output by
  inspecting a couple of the generated JSON files for readable `raw_text` and
  correct metadata.

## Notes for the AI

- Reuse stdlib `urllib.request`/`html.parser`/`re` for HTTP and extraction,
  matching `edgar_client.py`/`text_extract.py`'s existing style - no new
  dependency is needed.
- Confirmed live (during specing, against real fool.com pages): the sitemap at
  `https://www.fool.com/sitemap/{year}/{month:02d}` returns plain XML
  (`<urlset><url><loc>...</loc><lastmod>...</lastmod></url>...</urlset>`);
  transcript URLs look like
  `https://www.fool.com/earnings/call-transcripts/{year}/{month}/{day}/{name}-{ticker}-q{n}-{year}-earnings-call-transcript/`;
  and the transcript page's real DOM (not just an SSR data blob) contains
  `<div id="article-body-transcript" class="article-body transcript-content">`
  wrapping a "DATE"/"Date" heading (`id="date"`, casing varies by page), a
  "CALL PARTICIPANTS"/"Call participants" list, and the prepared remarks/Q&A
  body as `<p>`/`<strong>` speaker tags. Re-confirm this structure against a
  real page in Step 1/2 before relying on it further, since it can change
  without notice.
- Confirmed live during Step 1: the DATE heading's text format is not
  consistent between pages - e.g. `"Thursday, July 30, 2026 at 5:00 p.m. ET"`
  on one transcript vs `"Oct. 23, 2024, 5:30 p.m. ET"` on another (abbreviated
  month with a period, no weekday). `parse_call_date` must handle both: match
  a `<month name/abbrev>[.]? <day>, <year>` pattern and try both `%B` (full
  month) and `%b` (abbreviated month) when parsing.
- Confirmed live during Step 1: a candidate URL's sitemap listing month can be
  wrong as a recency signal - a real example found is a TSLA transcript whose
  URL was listed in the April 2026 sitemap (and whose slug even says
  `q3-2024`) but whose actual DATE heading is `Oct. 23, 2024`, i.e. Motley Fool
  relisted/touched an old transcript months later. This is exactly why Step 3
  selects by parsed call date, never by the sitemap/URL date - do not
  "simplify" that back to a URL-date sort.
- Confirmed live during Step 3: with a 6-month scan window, TSLA had only 2
  candidates - the real July 2026 transcript and the stale relisted Oct 2024
  one above - because fool.com apparently never published a TSLA "Q1 2026"
  transcript (confirmed absent via search), leaving a real gap in that
  quarter's coverage. `ingest_all_transcripts` therefore checks every selected
  transcript's age (`MAX_TRANSCRIPT_AGE_DAYS = 400`) and raises rather than
  silently shipping a multi-year-old transcript as if it were recent.
  Widening `SCAN_MONTHS_BACK` from 6 to 9 found the real next-most-recent one
  instead (TSLA Q4 2025, published 2026-01-28) - keep the window at 9 and keep
  the staleness guard; both are load-bearing, not arbitrary.
- Fail loudly: raise on HTTP errors, a company with fewer than 2 discovered
  transcripts, a page missing the expected container, or an unparseable call
  date, rather than skipping silently - citation accuracy later depends on
  knowing exactly what was ingested.
- `extract_article_text` should reuse `clean_text`'s existing hidden-element
  logic (script/style/`display:none`/`hidden`) rather than duplicating it -
  isolate the container substring first, then feed it through the same
  collection logic, since the transcript container itself is expected to be
  clean of hidden XBRL-style noise (unlike EDGAR filings) but may contain
  empty ad-placeholder `<div>`s with no text, which `clean_text`'s approach
  already ignores.
- Confirmed live during Step 2: Motley Fool's HTML has no whitespace between
  adjacent block tags (e.g. `<h2>Date</h2><p>Oct. 23, 2024...`), so naive tag
  stripping glues heading and paragraph text together with no separator -
  `parse_call_date`'s first real run misparsed "DateOct" as the month. Fixed
  by having `_TextCollector` emit a newline whenever it enters a block-level
  tag (`p`, `div`, `h1`-`h6`, `li`, `ul`, `ol`, `tr`, etc.) or a `<br>`, shared
  by both `clean_text` and `extract_article_text`. This only adds whitespace
  that the existing collapse regexes normalize away, so feature 1's EDGAR
  output is unaffected (spot-checked after the change).


<!-- blueprint:completion {"schemaVersion":1,"specBytes":15318,"specSha256":"1d59b4677ffea6e18e442094f8391cbaec243dd7c944934872abc85872a9dc03","branch":"refs/heads/feature/earnings-call-transcripts-ingest-pipeline","head":"083cdcc82442cfd684085658849e3999010a3330","baseRef":"refs/heads/master","baseCommit":"083cdcc82442cfd684085658849e3999010a3330","sourceTree":"2397998bd89e2a7931ddbc527bb3882d14acf4c5","absentOptional":[]} -->
