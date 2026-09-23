# Feature: README

**From build-plan:** feature 13
**Build attempt:** 1
**Status:** verified
**Branch:** `feature/readme`

## Goal

Write the project's root `README.md`: the problem, the user, setup, the
run/test/eval commands, and the documented trade-offs, per build-plan item 13.
This is the last MVP item. The overview's Deployment section already promises
that the MVP "corre desde `venv` con comandos documentados en el README", so the
README is the user-facing contract for running the project locally.

## In scope

- One new file, `README.md` at the repository root, written in English (the
  code, comments, docstrings, and `.env.example` are all English, and the
  project is a portfolio piece aimed at US finance AI roles). Sections, in
  order:
  1. **Title and one-paragraph summary**: RAG over SEC 10-K/10-Q filings and
     earnings-call transcripts that answers with a grounded citation or
     refuses when nothing retrieved supports an answer.
  2. **Problem**: from `project-plan.md` section 1 / overview Problem.
  3. **Who it's for**: the single user type from overview Users (equity
     analyst or informed retail investor researching one public company; no
     accounts, no multi-tenancy).
  4. **How it works**: the pipeline as it exists in code, in order: ingest
     (SEC EDGAR filings, Motley Fool transcripts) -> chunking -> embedding and
     ChromaDB indexing -> retrieval -> refusal check -> Claude answer
     generation -> query log. Name the corpus actually ingested: AAPL, MSFT,
     TSLA; one 10-K and two 10-Qs each (`FILING_TYPES_WANTED`); two
     transcripts each (`TRANSCRIPTS_PER_COMPANY`).
  5. **Setup**: Python 3.13, create and activate a virtual environment,
     `pip install -r requirements.txt`, copy `.env.example` to `.env` and fill
     `SEC_EDGAR_USER_AGENT` and `ANTHROPIC_API_KEY` (what each is for, which
     steps need which). Matches `AGENTS.md`'s Fresh clone setup.
  6. **Build the local index**: the four regeneration commands in order,
     from `AGENTS.md`, noting which hit the network (sec.gov, fool.com) and
     that the last one downloads the `all-MiniLM-L6-v2` model on first run,
     and that retrieval raises a `RuntimeError` naming the re-index command
     until the index exists.
  7. **Ask a question**: `python -m app.main "<question>"`, with one real
     example answer excerpt plus its `Sources:` block, and one real refusal,
     both copied from actual runs during this feature (not invented).
  8. **Run the tests**: `pytest`, noting it needs no network, no index, no API
     key, and no real log file.
  9. **Run the eval**: `python -m app.eval.runner`, what it scores (citation
     accuracy = an answer cites the expected chunk by exact `chunk_id`; answer
     relevance = cosine similarity of actual vs expected answer embeddings
     under the index-time model), that it needs the index and the API key, and
     the observed summary (`Citation accuracy` and `Average relevance` lines)
     from a real run during this feature, labeled with its run date.
  10. **Query log**: where it lives (`data/logs/queries.jsonl`), one JSON line
      per `answer_question` call, its fields (the `QueryLog` model), refusal
      sentinel values (`model == ""`, `tokens == 0`, `cost == 0.0`), and that
      `cost` uses Claude Haiku 4.5's published per-token rates as fixed
      constants.
  11. **Project layout**: short map of `app/` subpackages (`ingest`,
      `chunking`, `embedding`, `retrieval`, `generation`, `eval`, `logging`)
      and `app/main.py`.
  12. **Trade-offs and limitations**: each item a decision actually made in
      this repository, stated with its reason and its cost. At minimum:
      - Tiny fixed corpus (3 companies, 3 filings + 2 transcripts each) rather
        than on-demand ingestion: keeps the index small and evals
        reproducible; cannot answer about any other company or period.
      - Transcripts scraped from Motley Fool's public pages instead of a paid
        transcript API: free and citable; depends on that site's markup and
        sitemap.
      - Local `all-MiniLM-L6-v2` embeddings instead of a hosted embedding API:
        free, offline after first download, no second API key; weaker
        retrieval quality than larger models.
      - Section-aware fixed-size character chunking (1200 chars, 150 overlap,
        sections from `Item N.` headings in filings and speaker turns in
        transcripts): simple and deterministic; can split a table or thought
        across chunks, and falls back to a whole-document section when
        headings are not found.
      - Refusal by a single nearest-distance threshold
        (`DISTANCE_THRESHOLD = 1.0`) checked before calling Claude: no API
        call and no invented source on off-topic questions; the threshold is a
        reasoned default, not tuned against the eval set, so it can refuse a
        borderline answerable question or let a weakly related one through
        (in which case the model is still instructed to say the context does
        not support an answer).
      - Claude Haiku 4.5 for generation: low cost and latency per query;
        a larger model may write better syntheses.
      - Eval relevance scored by embedding similarity, not an LLM judge:
        free, deterministic, no extra API calls; rewards wording similarity,
        not factual correctness. Citation accuracy requires the exact expected
        chunk, so an answer that cites a neighboring chunk with the same fact
        counts as a miss.
      - Query log is an append-only local JSON Lines file with no rotation or
        reader: enough for one local user; grows without bound.
      - CLI only: FastAPI endpoint, Streamlit UI, and Docker/deploy are
        post-MVP (build plan items 15-17), as is quarter-over-quarter risk
        comparison (item 14).

## Out of scope

- Any code, test, or configuration change. This feature adds one Markdown
  file.
- Tuning `DISTANCE_THRESHOLD`, changing the model, or improving eval scores.
  The README reports whatever the real run produces, good or bad.
- Updating `AGENTS.md`'s Commands section, which is stale in places (it says
  "items 1-9 are shipped", describes FastAPI as "once it's implemented", and
  says item 9 still owns real coverage). That is agent-facing documentation;
  correcting it is a separate `/fix` so this diff stays one user-facing file.
- Architecture diagrams, badges, screenshots, a license file, or a
  contributing guide. None is asked for by the plan.
- Post-MVP items 14-17 beyond naming them as not built.

## Build loop

`workflow.stepReview` is `feature`, so implement both build steps in order and
present one review packet after the last step rather than pausing after each.
Each step must leave the project in a working state.

`workflow.checkpointCommits` is `disabled`, so do not create per-step commits.
`/complete` creates the single feature commit.

`AGENTS.md` declares `Test: pytest`. Neither step adds testable logic, so no
new tests are required; the full suite must still pass at the end.

## Build steps

- [x] 1. Collect real evidence before writing: with the existing local index
  and `.env`, run `python -m app.main` once with an answerable question (for
  example "What risk factors does Apple disclose about supply chain
  concentration?") and once with an off-topic question, and run
  `python -m app.eval.runner` once. Keep the answer excerpt, `Sources:` block,
  refusal text, and the two eval summary lines for the README. Confirm each
  trade-off fact in In scope against the code it names (`edgar_client.py`,
  `fool_client.py`, `chunker.py`, `filing_sections.py`,
  `transcript_sections.py`, `embedding/pipeline.py`, `generator.py`,
  `eval/runner.py`, `logging/query_logger.py`); if any stated value differs,
  the code wins and the README states the code's value.
  **Done when:** both CLI runs and the eval run completed and their outputs
  are captured for step 2, and every trade-off value has been checked against
  its source file. If the local index or API key is missing, stop and ask the
  user rather than inventing output.

- [x] 2. Write `README.md` at the repository root with the twelve sections in
  In scope, using only the evidence from step 1 for example output and eval
  numbers.
  **Done when:** `README.md` exists and covers all twelve sections; every
  command in it is copied exactly from `AGENTS.md` or verified in step 1; it
  contains no em dashes; `pytest -q` passes; and a fresh read-through finds no
  claim about behavior, values, or results that is not backed by the code or
  a step 1 run.

## Files / areas

- `README.md` - new, repository root.
- Read only, as sources: `blueprint/project-plan.md`,
  `blueprint/context/project-overview.md`, `AGENTS.md` (Commands, Fresh clone
  setup), `.env.example`, `app/main.py`, `app/ingest/edgar_client.py`,
  `app/ingest/fool_client.py`, `app/chunking/chunker.py`,
  `app/chunking/filing_sections.py`, `app/chunking/transcript_sections.py`,
  `app/embedding/pipeline.py`, `app/retrieval/retriever.py`,
  `app/generation/generator.py`, `app/eval/runner.py`,
  `app/logging/query_logger.py`, `app/logging/models.py`.

## Data / contracts

No code contracts change. The README documents these existing ones as they
stand:

- CLI: `python -m app.main "<question>"`; prints the answer, then a
  `Sources:` block when there are citations.
- Eval: `python -m app.eval.runner`; prints one `[HIT]`/`[MISS]` line per pair,
  then `Citation accuracy: N/M (P%)` and `Average relevance: X.XXX`.
- Query log: `data/logs/queries.jsonl`, one `QueryLog` JSON object per line
  (`timestamp`, `question`, `retrieved_sources`, `model`, `latency_ms`,
  `tokens`, `cost`).
- Environment: `SEC_EDGAR_USER_AGENT` (required by SEC EDGAR fair-access
  policy for filing ingest) and `ANTHROPIC_API_KEY` (answer generation and the
  eval run); neither is needed for `pytest`.

## Testing

Documentation only; no new tests. `pytest -q` must still pass. The real
evidence is step 1's live CLI and eval runs, which cost a small number of
Claude Haiku calls (two for the CLI checks, plus one per answerable eval pair)
and append those calls to the local query log.

## Notes for the AI

- The plans are written in Spanish; the README is English on purpose (see In
  scope). Translate intent, do not paste Spanish text.
- Setup uses `python -m venv .venv` to match `AGENTS.md`'s Fresh clone setup.
  Any virtual environment name works because both `.venv/` and `venv/` are
  gitignored.
- Do not round, embellish, or omit unfavorable eval numbers. Report exactly
  what the runner printed and the date it ran.
- Trim long example output with a visible `...` rather than rewriting it.
- No em dashes anywhere, per the project convention.


<!-- blueprint:completion {"schemaVersion":1,"specBytes":10781,"specSha256":"de1f25c1c4b0b9e4abd269fec4784f3a066fa644a98642454b0f146aaf826b9e","branch":"refs/heads/feature/readme","head":"d417502414a87d91c5596e60740ecac0562e31d2","baseRef":"refs/heads/master","baseCommit":"d417502414a87d91c5596e60740ecac0562e31d2","sourceTree":"01c892f8a0ffc9c7d189887f6493c2ec736f3627","absentOptional":[]} -->
