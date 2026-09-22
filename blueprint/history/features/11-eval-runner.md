# Feature: Eval runner

**From build-plan:** feature 11
**Build attempt:** 1
**Status:** verified
**Branch:** `feature/eval-runner`

## Goal

Run the hand-labeled eval set (feature 10) through the real pipeline
(`answer_question`, which composes retrieval, the refusal decision, and Claude
generation) and score each result for citation correctness and answer
relevance, per the build plan and the tech stack's "own eval script, no heavy
framework" note. This closes the eval loop item 10 set up but explicitly left
unconsumed.

## In scope

- `app/eval/runner.py`:
  - `citation_matches(result: AnswerResult, expected_citation: Citation) ->
    bool`: true iff any of `result.citations` has the same `chunk_id` as
    `expected_citation`.
  - `answer_relevance(actual_answer: str, expected_answer: str) -> float`:
    cosine similarity between the two texts' embeddings, using the same
    `SentenceTransformer(EMBEDDING_MODEL)` already used for indexing
    (`app.embedding.pipeline.EMBEDDING_MODEL`), computed with
    `sentence_transformers.util.cos_sim` (already an installed dependency's
    own utility; no new dependency).
  - `_load_eval_set() -> list[EvalPair]`: reads and parses
    `app/eval/eval_set.json`.
  - `run_eval() -> None`: for every `EvalPair`, calls `answer_question`, scores
    the result with the two functions above, prints a per-question hit/miss
    and relevance line, then prints a summary (citation accuracy as a
    fraction, average relevance).
  - `if __name__ == "__main__": run_eval()`, matching every other pipeline
    stage's module entry point.
- `app/eval/test_runner.py`: focused tests for `citation_matches`,
  `answer_relevance` (with a faked embedding model), and `_load_eval_set`,
  following `test_retriever.py`'s fake-model pattern. `run_eval` itself is
  integration glue against the live pipeline and is verified by running it,
  not unit-tested; see Notes for the AI.

## Out of scope

- Any pass/fail threshold or classification on top of the two scores. The
  build-plan line says the runner "puntúa" (scores); it does not say it grades
  pass/fail, and no such contract exists elsewhere. Report the raw citation
  accuracy fraction and average relevance score only.
- Persisting eval results to a file or database. Nothing in the overview asks
  for a report artifact; every other pipeline stage in this repo (`retriever.py`,
  `generator.py`, the embedding pipeline) reports to stdout only, and this
  follows the same convention.
- Adding this runner to the automated `pytest` suite, `Verify`, or CI.
  `run_eval()` calls the real Claude API (through `answer_question`) once per
  eval pair; running it automatically on every `pytest` invocation would break
  `AGENTS.md`'s existing guarantee that the suite needs no network access, and
  would spend real money on every run. See Notes for the AI.
- Changing `answer_question`, `generate_answer`, `retrieve`, `EvalPair`, or any
  of their existing contracts. This feature only calls and scores them.
- Query logging (item 12: timestamp, sources, model, latency, tokens, cost per
  query) and the README (item 13).
- Detecting or special-casing a refusal result. A refusal's empty `citations`
  list already scores as a citation miss through the normal path, and its
  fixed `REFUSAL_MESSAGE` will generally score low on relevance against a real
  `expected_answer` without any special-case branch.

## Build loop

`workflow.stepReview` is `feature`, so implement both build steps in order and
present one review packet after the last step rather than pausing after each.
Each step must still leave the project in a working state on its own.

`workflow.checkpointCommits` is `disabled`, so do not create per-step commits.
`/complete` creates the single feature commit.

`AGENTS.md` declares `Test: pytest`. Step 1 adds pure, testable logic and must
ship a passing test in the same diff. Step 2 adds `run_eval`, which is
integration glue against the live local index and the real Anthropic API; it
has no meaningful fake-based unit test (faking the entire pipeline it exists to
exercise would test nothing) and is verified by actually running it instead,
matching the precedent already set for `generator.py`'s and `main.py`'s own
`__main__` blocks.

## Build steps

- [x] 1. Add `app/eval/runner.py` with `citation_matches`,
  `answer_relevance` (plus its module-global `_model` cache and
  `_embedding_model()` helper, matching `app/retrieval/retriever.py`'s
  caching pattern), and `_load_eval_set`. Add `app/eval/test_runner.py` with
  an autouse fixture resetting `runner._model` between tests (matching
  `test_retriever.py`'s reset fixture).
  **Done when:** `pytest app/eval` passes, proving: `citation_matches` returns
  `True` when `expected_citation.chunk_id` appears among `result.citations`
  and `False` when it doesn't or when `result.citations` is empty (the
  refusal case); `answer_relevance`, given a faked embedding model returning
  fixed vectors, returns `1.0` for identical vectors and `0.0` for orthogonal
  ones; `_load_eval_set()` returns a list of `EvalPair` instances whose length
  matches the record count in `app/eval/eval_set.json`.

- [x] 2. Add `run_eval()` and the `if __name__ == "__main__":` block to the
  same file.
  **Done when:** `python -m app.eval.runner`, run against the real local index
  and a real `ANTHROPIC_API_KEY`, prints one hit/miss-plus-relevance line per
  eval pair and ends with a citation-accuracy fraction and an average
  relevance score; this run makes 22 real Claude calls and has a real,
  small API cost, which is expected for this step (see Notes for the AI).

## Files / areas

- `app/eval/runner.py` - new.
- `app/eval/test_runner.py` - new.
- `app/eval/models.py` - read only, for `EvalPair`. Do not modify.
- `app/eval/eval_set.json` - read only. Do not modify.
- `app/generation/generator.py` - read only, for `answer_question`. Do not
  modify.
- `app/generation/models.py`, `app/retrieval/models.py` - read only, for
  `AnswerResult` and `Citation`. Do not modify.
- `app/embedding/pipeline.py` - read only, for the `EMBEDDING_MODEL` constant.
  Do not modify.

## Data / contracts

Existing contracts this feature consumes, unchanged:

- `app.eval.models.EvalPair`, `app.eval.eval_set.json`.
- `app.generation.generator.answer_question(question: str) -> AnswerResult`.
- `app.generation.models.AnswerResult`, `app.retrieval.models.Citation`.
- `app.embedding.pipeline.EMBEDDING_MODEL = "all-MiniLM-L6-v2"`.

New contracts introduced here:

- `citation_matches(result: AnswerResult, expected_citation: Citation) ->
  bool`.
- `answer_relevance(actual_answer: str, expected_answer: str) -> float`: a
  cosine similarity in roughly `[-1.0, 1.0]` (in practice close to `[0.0,
  1.0]` for real prose, since MiniLM's own architecture unit-normalizes every
  embedding, the same fact feature 7's refusal threshold relies on).
- `run_eval() -> None`: no return value; reports to stdout only.

## Testing

`AGENTS.md` declares `Test: pytest`. Step 1's three functions are pure logic
with real edge cases (a citation hit, a miss, an empty-citations refusal case,
identical vs. orthogonal embedding vectors) and ship passing tests in the same
diff, following `test_retriever.py`'s fake-model pattern: monkeypatch
`runner._embedding_model` rather than loading the real model or calling the
network. `_load_eval_set` is tested against the real, committed
`app/eval/eval_set.json`, which needs no network or ingested data to read.
`run_eval` is not unit-tested; it is verified by running it in step 2, per the
project's existing precedent for live pipeline entry points.

## Notes for the AI

- Why `run_eval` isn't wired into `pytest`/CI: it calls the real Claude API
  through `answer_question` once per eval pair. `AGENTS.md`'s fresh-clone
  setup promises `pytest` needs no network access to pass; adding a
  network-and-cost-bearing call to the default test run would break that
  promise and charge real money on every CI run. Keep it a manually-run
  script, exactly like `retriever.py`'s and `generator.py`'s own
  `__main__` harnesses.
- `answer_relevance` reuses the exact embedding model already used for
  indexing (`EMBEDDING_MODEL` from `app.embedding.pipeline`), not a second
  model. Reusing `sentence_transformers.util.cos_sim` avoids hand-rolling
  cosine similarity math.
- Feature 6's spec chose Haiku specifically because "item 11's eval runner
  will call this repeatedly over 20-50 questions per pass." This feature is
  that consumer; do not swap the model or add retries/backoff without a new
  requirement.
- Type hints on every signature, `snake_case` functions, no em dashes anywhere
  in code, comments, or docs.


<!-- blueprint:completion {"schemaVersion":1,"specBytes":8710,"specSha256":"5dcb75bb2465b8def51188956d367d0dcb458fde834f22ae2710cfad3dbc479f","branch":"refs/heads/feature/eval-runner","head":"c4fb5cadda5c073c282365fb9bd4d313d2244f2a","baseRef":"refs/heads/master","baseCommit":"c4fb5cadda5c073c282365fb9bd4d313d2244f2a","sourceTree":"e9f718da5d213f45a88860b6b164a71b7adc0542","absentOptional":[]} -->
