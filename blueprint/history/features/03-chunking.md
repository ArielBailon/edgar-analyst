# Feature: Chunking

**From build-plan:** feature 3
**Build attempt:** 1
**Status:** verified
**Branch:** `feature/chunking`

## Goal

Split the already-ingested filings (`data/filings/`) and transcripts
(`data/transcripts/`) into retrieval-sized `Chunk` records carrying company,
document type, section, and date metadata, and persist them locally so later
build steps (embedding/indexing, retrieval, answer generation) have real,
citable chunks to work against.

## Investigation before scoping

Real per-company data was inspected before writing this spec (all 9 filings
and 6 transcripts already in `data/filings/`/`data/transcripts/` from features
1-2):

- **Transcripts are reliable.** Motley Fool's own editorial content (DATE,
  CALL PARTICIPANTS, and sometimes TAKEAWAYS/SUMMARY/INDUSTRY GLOSSARY) always
  precedes a literal `"Full Conference Call Transcript"` marker (confirmed in
  all 6 real transcripts), after which the verbatim call is a clean sequence
  of `Speaker Name: ...` turns (confirmed for both executives and analysts).
- **Filings are filer-specific and messier than expected.** AAPL's 10-K/10-Q
  have a clean pattern: every `Item N.` heading appears exactly twice (once in
  a table of contents, once as the real section start), so the second
  occurrence is reliably the real one. But MSFT's 10-Q has ~90 repeated
  page-header artifacts (`"PART I\nItem 1"`, `"PART II\nItem 1A"`, etc.)
  scattered through the *entire* document body - a rendering artifact already
  baked into the `raw_text` feature 1 persisted - and MSFT's real headings are
  ALL CAPS (`"ITEM 2. MANAGEMENT'S DISCUSSION..."`) while the repeated noise
  and TOC use title case (`"Item 1"`/`"Item 1."`). TSLA has yet another flavor
  of repeated noise (`"Table of Contents"`, repeated table column headers like
  `"Three Months Ended March 31,"`, page numbers).
- The generalizable fix for the noise problem: it's always a handful of
  *short* lines repeated *many* times verbatim, regardless of what the noise
  text actually says. A generic "strip lines under ~40 chars that repeat 5+
  times" cleanup handles all three filers' distinct noise without per-filer
  rules.
- Decision (confirmed with the user): invest in real per-section detection for
  filings (not a coarse one-section-per-filing fallback), and clean the
  repeated noise at chunk time in this feature rather than reopening feature
  1's already-merged ingest code. The noise stays in the raw stored
  `data/filings/*.json` files; only chunking's view of the text is cleaned.

## In scope

- A paragraph-aware text chunker: splits a block of text into overlapping,
  size-bounded chunks without cutting mid-word where avoidable.
- A generic repeated-short-line stripper for filing text, applied before
  section detection and chunking (removes running headers/footers/table
  headers/page numbers regardless of their exact wording).
- Filing section detection: identifies real `Item N[Letter].` headings
  (case-insensitive, tolerant of the TOC-duplicate pattern) in 10-K/10-Q text
  and splits the document into `(section_name, section_text)` pairs. Falls
  back to a single `"Full Document"` section for a document whose structure
  this heuristic can't confidently parse, rather than crashing the whole
  pipeline run over one filer's formatting quirk.
- Transcript section detection: discards Motley Fool's editorial front matter
  before `"Full Conference Call Transcript"`, then splits the verbatim call
  into one section per contiguous speaker turn (section = speaker name).
- A `Chunk` pydantic model (`id`, `company`, `document_type`, `section`,
  `date`, `text`) matching the Data model in `project-overview.md`, minus
  `embedding` (build-plan item 4's job - see Notes for the AI).
- A pipeline that reads every persisted `Filing`/`Transcript` JSON file,
  derives sections, chunks each section, and writes `Chunk` records to
  `data/chunks/<TICKER>/<document_type>_<date>.json`.

## Out of scope

- Embeddings, ChromaDB, indexing, retrieval, or answer generation (build-plan
  items 4-6) - the `Chunk` model here has no `embedding` field; item 4 adds it.
- Fixing the repeated-header noise in feature 1's stored `data/filings/*.json`
  raw text at its source - deferred per the user's explicit choice; this
  feature only cleans the text it uses for chunking, in memory.
- CLI, tests, eval set/runner, logging (items 8-13) - item 9 explicitly owns
  adding pytest coverage; this feature does not add a test runner.
- A fully general, provably-correct SEC filing section parser. The heading
  detection here is a validated-against-real-data heuristic (AAPL, MSFT, TSLA
  10-K/10-Q as currently ingested), not a guarantee against every filer's HTML
  quirks; the single-section fallback exists specifically so an unrecognized
  structure degrades gracefully instead of blocking the pipeline or silently
  mis-splitting content.
- Chunking any data beyond what features 1-2 already ingested (still AAPL,
  MSFT, TSLA; still the fixed 9 filings + 6 transcripts).

## Build loop

Build one small step at a time. Follow `workflow.stepReview` in
`blueprint/config.json`: currently `feature`, so this produces one review
packet after all steps complete (no per-step approval pauses).
`workflow.checkpointCommits` is `disabled`, so no checkpoint commits are
offered mid-feature. `/complete` makes the final feature commit. Never accept
a review packet that has not been read; split any diff that is too large to
review.

## Build steps

- [x] **Step 1 - Chunk model + text chunker** - add `app/chunking/models.py`
  with a `Chunk` pydantic model: `id: str`, `company: str`, `document_type:
  Literal["10-K", "10-Q", "transcript"]`, `section: str`, `date: date`, `text:
  str`. Add `app/chunking/chunker.py` with `chunk_text(text: str, chunk_size:
  int = 1200, overlap: int = 150) -> list[str]` that splits on paragraph
  boundaries (`"\n\n"`) where possible to avoid mid-sentence cuts, falling
  back to plain slicing only when a single paragraph exceeds `chunk_size`.
  *Done when:* running `chunk_text` on a real long section of text (e.g. a
  slice of AAPL's ingested 10-K `raw_text`) produces multiple chunks each
  within a reasonable size of `chunk_size`, with visible overlap between
  consecutive chunks, verified by manual inspection; constructing a `Chunk`
  from one real chunk validates without error.
- [x] **Step 2 - Filing section detection** - add
  `app/chunking/filing_sections.py` with `strip_repeated_lines(text: str,
  min_repeats: int = 5, max_line_len: int = 40) -> str` (removes any line at
  most `max_line_len` chars that occurs at least `min_repeats` times verbatim
  anywhere in the document) and `split_filing_sections(text: str) ->
  list[tuple[str, str]]` that runs the stripper first, then finds `Item
  N[Letter].` headings case-insensitively, resolves the real heading among
  duplicates (the TOC-then-real pattern), and returns `(section_name,
  section_text)` pairs - falling back to `[("Full Document", text)]` when it
  can't confidently identify headings. *Done when:* running
  `split_filing_sections` against all 6 real ingested 10-K/10-Q files (AAPL,
  MSFT, TSLA) produces a plausible section list for each - spot-checked by
  printing section names and comparing against each filing's real Item
  structure, confirming MSFT's repeated-header noise no longer appears as
  spurious sections. Done - verified live against all 6 files: no noise
  leaked through as a spurious section, and all substantive sections (Risk
  Factors, MD&A, Financial Statements) resolved with correct titles and
  plausible lengths. A handful of trivial/reserved items (e.g. MSFT's Item 6,
  9A) resolved with bare `"Item N."` names instead of their full title -
  their heading text apparently sits after a paragraph break rather than on
  the same line, so the display name is incomplete, but the section content
  itself is a plausible length. Documented as a residual cosmetic limitation
  rather than chased further, per proportional scope.
- [x] **Step 3 - Transcript section detection** - add
  `app/chunking/transcript_sections.py` with `split_transcript_sections(text:
  str) -> list[tuple[str, str]]` that locates `"Full Conference Call
  Transcript"`, discards everything before it, and splits the remainder into
  one `(speaker_name, turn_text)` pair per contiguous speaker turn (turn
  boundary: a line matching `Name: ` at the start of a paragraph). *Done
  when:* running `split_transcript_sections` against all 6 real ingested
  transcripts correctly excludes the editorial front matter (TAKEAWAYS,
  SUMMARY, INDUSTRY GLOSSARY where present) and produces sections whose names
  match that transcript's real `CALL PARTICIPANTS` list plus `"Operator"` and
  analyst names, verified by manual inspection. Done - verified live against
  all 6 transcripts: speaker lists were plausible and no editorial content
  leaked into any section's text.
- [x] **Step 4 - Pipeline + storage** - add `app/chunking/pipeline.py` with
  `chunk_all() -> list[Chunk]` that reads every JSON file under
  `data/filings/*/*.json` and `data/transcripts/*/*.json`, parses each into
  `Filing`/`Transcript` (reusing `app.ingest.models`), derives `document_type`
  (the filing's `filing_type`, or the literal `"transcript"`), splits into
  sections (Step 2 or 3), chunks each section's text (Step 1), builds a
  `Chunk` per resulting piece with `id` = `f"{company}-{document_type}-
  {date}-{section_slug}-{index}"`, and writes each source document's chunks to
  `data/chunks/<TICKER>/<document_type>_<date>.json` as a JSON array. Add an
  `if __name__ == "__main__":` guard calling `chunk_all()`. *Done when:*
  running `python -m app.chunking.pipeline` against all 15 currently-ingested
  documents produces one chunk file per source document under `data/chunks/`,
  each containing valid, non-empty `Chunk` records with correct
  `company`/`document_type`/`date` and a plausible `section` per chunk,
  spot-checked across at least one file per company and per document type.
  Done - verified live: 2406 chunks across 15 files, all IDs globally unique,
  no markup leaked into any chunk text, MSFT's 10-K correctly resolved all 23
  Item sections.

## Files / areas

- `app/chunking/__init__.py` - new package
- `app/chunking/models.py` - new: `Chunk` pydantic model
- `app/chunking/chunker.py` - new: paragraph-aware text chunking
- `app/chunking/filing_sections.py` - new: noise stripping + filing section
  detection
- `app/chunking/transcript_sections.py` - new: transcript section detection
- `app/chunking/pipeline.py` - new: orchestration + local JSON persistence
- `.gitignore` - no change needed; `data/` is already ignored (feature 1)

## Data / contracts

- **Chunk** (matches `project-overview.md`'s Data model, minus `embedding`
  which item 4 adds): `id` (unique, deterministic:
  `<company>-<document_type>-<date>-<section-slug>-<index>`), `company`
  (ticker), `document_type` (`"10-K"` | `"10-Q"` | `"transcript"`), `section`
  (an `Item N. Title` heading for filings, or a speaker name for
  transcripts), `date` (inherited from the source `Filing`/`Transcript`),
  `text` (the chunk's content, `chunk_size` ~1200 chars with ~150 char
  overlap). Stored as one JSON array per source document at
  `data/chunks/<TICKER>/<document_type>_<date>.json`. Later features
  (embedding/indexing, item 4; retrieval, item 5) read this exact shape and
  path convention - do not change it without updating them.
- Reuses `Filing`/`Transcript` from `app.ingest.models` as read-only input;
  does not modify feature 1/2's ingest code or stored filing/transcript JSON.
- No database; no multi-user or auth boundary in this feature.

## Testing

- No test runner is configured yet (`AGENTS.md` declares none); build-plan
  item 9 explicitly owns adding pytest coverage for chunking, so this feature
  does not add one.
- Verify each step manually against the real ingested `data/filings/` and
  `data/transcripts/` files per its *Done when* - these steps depend on the
  real, messy structure of already-ingested data, not a runner. Confirm the
  final `data/chunks/` output by inspecting a couple of generated files for
  correct metadata and readable, appropriately-sized chunk text.

## Notes for the AI

- Item 4 (embedding/indexing) will need to add an `embedding` field to this
  feature's `Chunk` model - same pattern as `Transcript` not having
  `filing_type` in feature 2. Don't add a placeholder `embedding: None` field
  now; that's item 4's contract to define.
- The noise-stripping threshold (`min_repeats=5`, `max_line_len=40`) is a
  starting point validated against AAPL/MSFT/TSLA's real ingested filings
  during Step 2 - confirm it doesn't also strip legitimate short repeated
  content (e.g. a recurring short table label) before relying on it; adjust
  the thresholds if a real document shows over- or under-stripping, and note
  what changed and why.
- For filing section detection, resolving "which occurrence is the real
  heading" needs to handle at least: AAPL's clean 2x-duplicate (TOC then
  real - take the second), and MSFT/TSLA's noisier documents where the count
  per label may differ after noise-stripping. Prefer a rule that generalizes
  (e.g. "the last occurrence with substantial content before the next
  distinct heading") over a filer-specific special case. When no rule
  produces a confident split for a given document, use the `"Full Document"`
  fallback and note which document needed it - don't force a bad split to
  avoid the fallback.
- Confirmed live during Step 2: picking "the occurrence with the largest
  content span" alone isn't enough - TSLA's 10-K had an inline cross-reference
  sentence (`"...Item 7. Management's Discussion...in our Annual Report on
  Form 10-K for fiscal year 2024, which was filed..."`) win the span
  comparison over the real heading, because the real Item 7/8 boundary
  happened to sit close to other content while this inline mention's "next
  Item" was far away. Fixed by first discarding any occurrence whose text
  runs past ~150 chars before the next newline (a real heading is its own
  short line; an inline reference keeps flowing as prose) - only then compare
  spans among what's left. Keep this filter; removing it reintroduces
  multi-sentence "section names" and wildly wrong span attribution.
- `chunk_text`'s paragraph splitting should reuse the fact that
  `text_extract.clean_text`/`extract_article_text` already normalize multiple
  blank lines to exactly `"\n\n"` - split on that rather than re-deriving
  paragraph boundaries a different way.
- Confirmed live during Step 3: a plain `"Name: "` regex on its own produces
  false-positive speakers - MSFT's transcript had rhetorical sentences like
  `"I want to be transparent: when you have revenue..."` and `"Our north star
  remains the same: delivering..."` match the pattern purely coincidentally.
  Fixed by requiring every word in the candidate name to start with a capital
  letter (real names are Title Case throughout; sentence fragments have
  lowercase words like "want"/"remains"). Keep this filter.
- Fail loudly on a file that can't be parsed as `Filing`/`Transcript` JSON, or
  on an empty section after chunking - don't silently skip a source document,
  since citation completeness later depends on knowing exactly what was
  chunked. The `"Full Document"` fallback for unparseable filing structure is
  a deliberate, logged degradation, not a silent skip - it still produces
  chunks, just coarser ones.
- Confirmed live during Step 4: a chunk `id` built from a per-tuple
  `enumerate()` index collides across turns, because a speaker (or, less
  often, a section label) can appear as more than one separate
  `(section_name, section_text)` tuple - a transcript speaker who talks more
  than once, for example. Fixed by tracking the next index per `section_slug`
  across the whole document instead of resetting it per tuple. Global
  uniqueness across all 2406 chunks in this run was verified directly; don't
  regress to a per-tuple counter.
- A few chunks came out very short (as low as 18 chars) when a section's
  final leftover piece after chunking is tiny. Left as-is rather than adding
  merge-trailing-fragment logic - not wrong, just a minor efficiency nit;
  worth revisiting if item 4/5 finds these low-value for retrieval.


<!-- blueprint:completion {"schemaVersion":1,"specBytes":16391,"specSha256":"387a187636cc6176ebd9adb0f956bc9129dfdbc8c904a0f49a7bd5e342180c41","branch":"refs/heads/feature/chunking","head":"84979931810cc1b27a538b66a0a3c5055e7a0374","baseRef":"refs/heads/master","baseCommit":"84979931810cc1b27a538b66a0a3c5055e7a0374","sourceTree":"0ade190128074e38b8bb677677488d4bb313d161","absentOptional":[]} -->
