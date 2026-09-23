# Feature: Logging

**From build-plan:** feature 12
**Build attempt:** 1
**Status:** verified
**Branch:** `feature/logging`

## Goal

Record one structured `QueryLog` entry per call to `answer_question` (sources
retrieved, model, latency, tokens, cost), written to a local file, per the
`QueryLog` data model and the build-plan line. This gives item 13's README
something concrete to point at and is the last piece before that closes the
MVP.

## In scope

- `app/logging/` (new package): `__init__.py`, `models.py` defining
  `QueryLog` (`timestamp: datetime`, `question: str`, `retrieved_sources:
  list[Citation]`, `model: str`, `latency_ms: int`, `tokens: int`, `cost:
  float`), matching `project-overview.md`'s `QueryLog` data model exactly.
- `app/logging/query_logger.py`:
  - `LOG_PATH = Path("data/logs/queries.jsonl")`.
  - `compute_cost(input_tokens: int, output_tokens: int) -> float`, using
    Claude Haiku 4.5's published per-token pricing ($1.00 / 1M input, $5.00 /
    1M output, verified today, not recalled from memory).
  - `log_query(question, retrieved_sources, model, latency_ms, input_tokens,
    output_tokens) -> None`: builds a `QueryLog` and appends it as one JSON
    line via the standard library `logging` module (a cached `FileHandler` on
    `LOG_PATH`), creating `data/logs/` on first use. This is the "Logging
    estándar" half of the tech stack's "Logging estándar / structlog" choice;
    `structlog` is not installed and buys nothing extra for one JSON line per
    call.
- `app/logging/test_query_logger.py`: tests for `compute_cost` and `log_query`
  (writing to a `tmp_path`, never the real log file).
- Wiring `answer_question` in `app/generation/generator.py` to time the whole
  call, capture token usage from the Claude call when one happens, and log
  exactly one `QueryLog` entry per invocation, for both the generate and
  refusal paths. This requires factoring `generate_answer`'s Claude call into
  a private `_call_claude` helper that also returns the response's `usage`,
  since `generate_answer` currently discards it entirely. `generate_answer`'s
  own public contract (signature, return type, validation, raised errors) is
  unchanged; only its internals are reorganized to expose usage to
  `answer_question`. See Notes for the AI for why this touches `generator.py`
  and its existing tests.

## Out of scope

- The README (item 13): this feature only produces the log, not the
  documentation describing it.
- Reading, aggregating, rotating, or capping the log file. "Una entrada por
  query, a un archivo local" is an append-only write; nothing in the overview
  asks for log rotation, a size cap, or a reader.
- Logging from the eval runner (`app/eval/runner.py`) or the CLI
  (`app/main.py`) separately. Both already call `answer_question`, so they
  get one log entry per call for free without any change to either file.
- Configurable log level, log destination, or third-party log aggregation
  (Sentry, CloudWatch, etc.). No current requirement asks for any of them.
- Changing `retrieve()`, `RetrievalResult`, `AnswerResult`, or
  `generate_answer`'s public signature/contract. `generate_answer` still takes
  `(question, results)` and returns only `AnswerResult`; it still raises on a
  blank question or empty `results`.
- A live pricing lookup or a configurable price per model. `compute_cost`'s
  two constants are a point-in-time fact (Claude Haiku 4.5's current published
  rate), not a product surface; if pricing changes or a second model is ever
  used, updating two numbers is a one-line fix, not a new requirement.

## Build loop

`workflow.stepReview` is `feature`, so implement both build steps in order and
present one review packet after the last step rather than pausing after each.
Each step must still leave the project in a working state on its own.

`workflow.checkpointCommits` is `disabled`, so do not create per-step commits.
`/complete` creates the single feature commit.

`AGENTS.md` declares `Test: pytest`. Both steps add testable logic and must
ship passing tests in the same diff.

## Build steps

- [x] 1. Create the `app/logging/` package: `__init__.py` (empty), `models.py`
  with `QueryLog`, and `query_logger.py` with `LOG_PATH`, `compute_cost`, and
  `log_query` (plus the module-global cached `logging.Logger` and its
  `_query_logger()` helper, matching the module-global caching convention
  already used in `retriever.py`/`generator.py`/`runner.py`). Add
  `test_query_logger.py` with an autouse fixture resetting the module's cached
  logger between tests (same reset-fixture convention as those other
  modules), plus tests monkeypatching `query_logger.LOG_PATH` to a `tmp_path`.
  **Done when:** `pytest app/logging` passes, proving: `compute_cost` returns
  the exact expected dollar amount for at least one known input/output token
  pair, computed by hand against the $1.00/$5.00-per-million-token rate;
  `log_query`, called twice, appends two separate valid JSON lines to the
  file at `LOG_PATH` (not two objects on one line, not an overwrite), each
  parsing back into the fields it was given; `log_query` creates
  `LOG_PATH.parent` when it doesn't already exist.

- [x] 2. In `app/generation/generator.py`, extract the existing Claude call
  and `AnswerResult` construction out of `generate_answer` into `_call_claude(question, results) -> tuple[AnswerResult, Usage]` (import `Usage` from
  `anthropic.types`), returning the response's `.usage` alongside the result.
  `generate_answer` calls `_call_claude` and returns only its `AnswerResult`,
  unchanged from its current behavior. Update `answer_question` to: time the
  call with `time.perf_counter()`; on refusal, use `model=""` and
  `input_tokens=output_tokens=0` (no Claude call happens); on generation, call
  `_call_claude` and use `MODEL` plus the returned usage's `input_tokens`/
  `output_tokens`; either way, call `app.logging.query_logger.log_query` once
  with the question, `[r.citation for r in results]` as `retrieved_sources`
  (the retrieved candidates, not `AnswerResult.citations`, so a refusal's log
  entry still shows what was retrieved and rejected), the chosen model,
  latency in milliseconds, and the token counts, before returning the
  original result unchanged.

  In `app/generation/test_generator.py`: add a `usage` attribute (fixed fake
  `input_tokens`/`output_tokens`) to the existing fake message class so
  `generate_answer`'s current tests keep passing against the refactored
  `_call_claude`; add an autouse fixture that monkeypatches
  `generator.log_query` to a `unittest.mock.Mock()` so no existing test
  performs real file I/O; add two new tests asserting `answer_question` calls
  `log_query` exactly once, with the expected model/token values, on the
  generate path and on the refusal path.
  **Done when:** `pytest app/generation` passes, including the existing
  `generate_answer` tests unchanged in behavior and the two new
  `answer_question` logging assertions; `pytest -q` (full suite) passes;
  running `python -m app.main "What risk factors does Apple disclose about
  supply chain concentration?"` against the real local index and API still
  prints a grounded answer as before, and appends one new valid JSON line to
  `data/logs/queries.jsonl` with a non-empty `model`, `tokens > 0`, and
  `cost > 0`; running it again with an off-topic question appends a second
  line with `model == ""`, `tokens == 0`, `cost == 0.0`.

## Files / areas

- `app/logging/__init__.py` - new, empty.
- `app/logging/models.py` - new.
- `app/logging/query_logger.py` - new.
- `app/logging/test_query_logger.py` - new.
- `app/generation/generator.py` - modify: extract `_call_claude`, wire
  `answer_question` to time and log every call.
- `app/generation/test_generator.py` - modify: fake `.usage`, mock
  `log_query`, two new tests.
- `app/retrieval/models.py` - read only, for `Citation`. Do not modify.

## Data / contracts

Existing contracts this feature consumes, unchanged:

- `app.retrieval.models.Citation`.
- `app.generation.generator.generate_answer(question, results) ->
  AnswerResult`: same signature, same validation, same return type.
- `app.generation.generator.answer_question(question, top_k) ->
  AnswerResult`: same signature and return type; now has the side effect of
  writing one log entry per call.

New contracts introduced here:

- `app.logging.models.QueryLog`: `timestamp: datetime`, `question: str`,
  `retrieved_sources: list[Citation]`, `model: str`, `latency_ms: int`,
  `tokens: int`, `cost: float`.
- `app.logging.query_logger.LOG_PATH = Path("data/logs/queries.jsonl")`.
  Deliberately under the gitignored `data/` directory: unlike feature 10's
  hand-authored eval set, this is ephemeral runtime output from actually
  using the app, the same category as the ingest/chunk/index artifacts
  already excluded there. See Notes for the AI.
- `compute_cost(input_tokens: int, output_tokens: int) -> float`:
  `input_tokens * (1.00 / 1_000_000) + output_tokens * (5.00 / 1_000_000)`,
  Claude Haiku 4.5's published Anthropic API pricing verified today
  (2026-09-22). Not a live lookup; a constant, documented fact.
- `log_query(question: str, retrieved_sources: list[Citation], model: str,
  latency_ms: int, input_tokens: int, output_tokens: int) -> None`.
- `generator._call_claude(question: str, results: list[RetrievalResult]) ->
  tuple[AnswerResult, anthropic.types.Usage]`: new private helper.
- Refusal-path sentinel values in the log: `model=""`, `input_tokens=0`,
  `output_tokens=0` (so `tokens == 0` and `cost == 0.0`), since no Claude call
  happens. `retrieved_sources` is still populated from whatever `retrieve()`
  returned, even on refusal.

## Testing

`AGENTS.md` declares `Test: pytest`. Both steps add testable logic and ship
passing tests in the same diff. `query_logger`'s tests never touch the real
`data/logs/queries.jsonl` (they monkeypatch `LOG_PATH` to `tmp_path`), and
`generator`'s existing and new tests never perform real file I/O either (the
new autouse fixture mocks `log_query`), so `pytest` keeps needing no network,
no ingested data, and now no real log file to pass, exactly as `AGENTS.md`'s
fresh-clone setup promises.

## Notes for the AI

- Why `generator.py` and its tests need to change here, despite prior specs
  marking `generate_answer` as an established, unchanged contract: token
  usage only exists inside the Claude API response, which only
  `generate_answer`'s internals ever touched, and it discarded that data.
  Logging tokens and cost is impossible without exposing it somewhere.
  Extracting `_call_claude` is the smallest change that does this without
  altering `generate_answer`'s own signature, validation, or return type; its
  existing tests keep passing once the fake response gains a `.usage`
  attribute, since nothing about its observable behavior changes.
- `data/logs/` sits under the same blanket `data/` gitignore rule that
  excludes ingest/chunk/embedding artifacts. That is correct here (opposite
  of feature 10's eval set, which had to avoid `data/` specifically because
  it was hand-authored ground truth with no regenerating source). Query logs
  are the regenerating case: they are produced by using the app, contain
  arbitrary user questions, and have no reason to be committed.
- Pricing was verified against Anthropic's current published rates for Claude
  Haiku 4.5 ($1.00 / $5.00 per million input/output tokens) rather than
  recalled from training data. If this ever needs updating, only
  `compute_cost`'s two constants change.
- Use `datetime.now(timezone.utc)` for `QueryLog.timestamp`; pydantic's
  `model_dump_json()` serializes both `datetime` and `date` (inside each
  `Citation`) to ISO 8601 strings with no custom encoder needed.
- Type hints on every signature, `snake_case` functions,
  `SCREAMING_SNAKE_CASE` constants, no em dashes anywhere in code, comments,
  or docs.


<!-- blueprint:completion {"schemaVersion":1,"specBytes":11919,"specSha256":"ff3b828aa854c873fc79718f456fe3091c2e141175a365a65ea31964784dd4ee","branch":"refs/heads/feature/logging","head":"1060bbc6aa1697d689b7c640255de5eb4175685a","baseRef":"refs/heads/master","baseCommit":"1060bbc6aa1697d689b7c640255de5eb4175685a","sourceTree":"a38d86b9347eb16ea342c06217c47da65ffbda2e","absentOptional":[]} -->
