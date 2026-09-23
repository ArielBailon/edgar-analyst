# Fix: Stale AGENTS.md commands

**Type:** Fix
**Status:** verified
**Branch:** `fix/stale-agents-md-commands`

## The problem

The `## Commands` section of `AGENTS.md` (lines 292-355) still describes the
project as it was after build-plan item 9. Every AI agent reads this section
before running anything, so the stale parts cause wrong actions:

- Lines 294-297 say "Build-plan items 1-9 are shipped" and list only those.
  Items 10-13 (eval set, eval runner, logging, README) have shipped since, which
  completes the MVP.
- Line 300 lists `uvicorn app.main:app --reload` as the way to "Run the API once
  it's implemented". `app/main.py` is a CLI script with no `app` object, so the
  command fails. The FastAPI endpoint is post-MVP build-plan item 15 and does not
  exist.
- The eval command, `python -m app.eval.runner`, is not listed at all.
- Lines 313-314 say "Build plan item 9 still owns real coverage for ingest,
  chunking, and retrieval; the current suite only proves the runner works."
  Item 9 shipped that coverage; the suite now has 135 tests.
- The query log that feature 12 added (`data/logs/queries.jsonl`) is not
  mentioned, although it is a gitignored runtime output next to `data/` and
  `chroma_db/`.

## The fix

Edit only the `## Commands` section of `AGENTS.md`, keeping its structure,
headings, and the parts that are still true:

1. Replace the opening paragraph: Python 3.13 (pip); build-plan items 1-13 (the
   full MVP) are shipped; `app/main.py` is the CLI entry point; FastAPI and
   uvicorn are installed but unused until post-MVP item 15.
2. Remove the `uvicorn app.main:app --reload` bullet. Do not replace it with a
   different API command, because no API exists.
3. Add an `Eval` bullet, `python -m app.eval.runner`, noting that it needs the
   local index and `ANTHROPIC_API_KEY` and makes real Claude calls.
4. Replace the "item 9 still owns real coverage" sentence with a true statement:
   the pytest suite covers ingest, chunking, retrieval, generation, eval scoring,
   and query logging, with no network, index, API key, or real log file needed.
5. In Fresh clone setup, mention that answering questions appends to
   `data/logs/queries.jsonl` (already covered by the `data/` gitignore rule).
   Change "`ANTHROPIC_API_KEY` is needed from build plan item 6 onward" to say it
   is needed to answer questions and run the eval.

Must not change:

- Any other section of `AGENTS.md`, `CLAUDE.md`, or any skill file. No workflow
  behavior changes, so there is no `.agents`/`.claude` adapter sync to do.
- `Lint/format: > TODO`, the no-`Verify` note, the browser-testing note, and the
  four index regeneration commands, which are all still accurate.
- `README.md`. It is the user-facing document; `AGENTS.md` stays the
  agent-facing one. Commands must agree between the two, but neither copies the
  other's prose.
- No code, tests, or configuration.

## Build steps

- [x] 1. Apply the five edits above to the `## Commands` section of `AGENTS.md`.
  **Done when:** `git diff` touches only lines inside `## Commands` in
  `AGENTS.md`; no line mentions `uvicorn app.main:app`, "items 1-9", or "item 9
  still owns"; `python -m app.eval.runner` appears as the Eval command; every
  command listed in the section also appears, spelled the same, in `README.md`
  or is a pytest invocation; the section has no em dashes; `pytest -q` still
  passes.

## Verify

- Read the updated `## Commands` section top to bottom against the code: each
  command must name a module that exists (`app/main.py`,
  `app/eval/runner.py`, the four pipeline modules), and no command may reference
  something that is not built.
- `pytest -q` passes (no code changed, so this only confirms nothing else moved).


<!-- blueprint:completion {"schemaVersion":1,"specBytes":3732,"specSha256":"453ae8040fa05ab39554ca7e93dc5564f27333d94cba1bd6eb94b5d83538f0f4","branch":"refs/heads/fix/stale-agents-md-commands","head":"762366e8d189e2f682639c8bb53c303b215c6344","baseRef":"refs/heads/master","baseCommit":"762366e8d189e2f682639c8bb53c303b215c6344","sourceTree":"273f8c064355fc48e0614bb22d38bda99cd68f81","absentOptional":[]} -->
