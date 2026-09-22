# Feature: Refusal path

**From build-plan:** feature 7
**Build attempt:** 1
**Status:** verified
**Branch:** `feature/refusal-path`

## Goal

Given a question, decide whether the retrieved chunks actually support an
answer, and refuse cleanly, with no citations attached, when none of them do.
This closes the gap feature 6 deliberately left open: `generate_answer` always
calls Claude with whatever chunks it is given and always returns every one of
them as a citation, so a weakly-matched or off-topic question currently gets an
answer dressed up with citations that don't really support it. This feature
adds the distance-based decision and a single entry point that ties retrieval,
the decision, and generation together; it does not change `retrieve()` or
`generate_answer()`'s own contracts.

## In scope

- `app/generation/generator.py`:
  - `DISTANCE_THRESHOLD` and `REFUSAL_MESSAGE` module constants.
  - `answer_question(question, top_k=DEFAULT_TOP_K) -> AnswerResult`: calls
    `retrieve(question, top_k)`, decides refuse-or-answer from the nearest
    result's `distance`, and either returns the fixed refusal `AnswerResult`
    (never calling Claude) or delegates to the existing `generate_answer`.
  - Updating the `__main__` block to call `answer_question` instead of
    chaining `retrieve()` and `generate_answer()` itself, and to only print a
    `Sources:` section when there are citations to show.
- Tests in `app/generation/test_generator.py` for the new decision and entry
  point, following the file's existing fake-client pattern.

## Out of scope

- Changing `retrieve()`, `RetrievalResult`, or `Citation` (build plan items 4-5,
  already shipped).
- Changing `generate_answer()`'s own contract: it still always calls Claude
  with whatever `results` it's given and still raises on a blank question or an
  empty `results` list when called directly. `answer_question` is a new,
  higher-level entry point layered on top, not a rewrite of that contract.
- Tuning `DISTANCE_THRESHOLD` against real graded questions. There is no eval
  set yet (that's item 10) to tune it against; see Data / contracts for the
  reasoning behind the chosen default and Notes for the AI for how it should be
  revisited once one exists.
- The user-facing CLI with argument parsing (item 8). The `__main__` block
  stays a developer harness, not that CLI.
- Query logging (item 12) and anything in the eval set / eval runner (items
  10-11).
- Parsing which `[n]` markers the model actually used, or otherwise inspecting
  the generated answer text to detect a refusal after the fact. The decision is
  made once, before calling Claude, from retrieval distance alone.

## Build loop

`workflow.stepReview` is `feature`, so implement both build steps in order and
present one review packet after the last step rather than pausing after each.
Each step must still leave the project in a working state on its own.

`workflow.checkpointCommits` is `disabled`, so do not create per-step commits.
`/complete` creates the single feature commit.

`AGENTS.md` declares `Test: pytest`, so per the project testing standard, tests
are a gate for logic-bearing steps: step 1 below must ship a passing pytest
test in the same reviewable diff. No `Verify` command is declared yet. Step 2
is thin CLI wiring with no new decision logic; verify it with the observable
behavior in its `Done when` instead of a test.

## Build steps

- [x] 1. In `app/generation/generator.py`, add `DISTANCE_THRESHOLD = 1.0`,
  `REFUSAL_MESSAGE = "The retrieved filings and transcripts do not contain
  information to answer this question."`, and:

  ```python
  def answer_question(question: str, top_k: int = DEFAULT_TOP_K) -> AnswerResult:
      results = retrieve(question, top_k)
      if not results or results[0].distance >= DISTANCE_THRESHOLD:
          return AnswerResult(answer=REFUSAL_MESSAGE, citations=[])
      return generate_answer(question, results)
  ```

  Import `DEFAULT_TOP_K` alongside the existing `retrieve` import from
  `app.retrieval.retriever`. `retrieve()` already sorts nearest first and
  already raises `ValueError` on a blank question, so `answer_question` needs
  no extra validation of its own.
  **Done when:** `app/generation/test_generator.py` proves, using a
  monkeypatched `generator.retrieve` (fixture results, no real embeddings or
  ChromaDB): a nearest distance below `DISTANCE_THRESHOLD` returns
  `generate_answer`'s own result unchanged; a nearest distance at or above
  `DISTANCE_THRESHOLD` returns `AnswerResult(answer=REFUSAL_MESSAGE,
  citations=[])` and never invokes the fake Anthropic client (assert on its
  call count); an empty `results` list from `retrieve` produces the same
  refusal without invoking the client; a blank question raises `ValueError`
  (via `retrieve`'s existing check, with `retrieve` unpatched for that one
  test). `pytest` passes.

- [x] 2. Update the `if __name__ == "__main__":` block in `generator.py` to
  call `answer_question(question)` instead of chaining `retrieve()` then
  `generate_answer()`, and to print the `Sources:` header and citation lines
  only when `answer.citations` is non-empty.
  **Done when:** `python -m app.generation.generator "What risk factors does
  Apple disclose about supply chain concentration?"` still prints a grounded
  answer with a `Sources:` list, and `python -m app.generation.generator "What
  is the capital of France?"` prints the refusal message with no `Sources:`
  section, against the local index.

## Files / areas

- `app/generation/generator.py` - add the two constants, `answer_question`,
  and update `__main__`.
- `app/generation/test_generator.py` - add tests for the refusal decision and
  `answer_question`.
- `app/generation/models.py` - read only; `AnswerResult` already supports an
  empty `citations` list, no change needed.
- `app/retrieval/models.py`, `app/retrieval/retriever.py` - read only, for
  `RetrievalResult.distance` and `DEFAULT_TOP_K`. Do not modify.

## Data / contracts

Existing contracts this feature consumes, unchanged:

- `app.retrieval.models.RetrievalResult`: `chunk_id`, `text`, `citation`,
  `distance` (nearest-first from `retrieve()`).
- `app.retrieval.retriever.retrieve(question, top_k)` and its
  `DEFAULT_TOP_K = 5`.
- `app.generation.models.AnswerResult`: `answer: str`, `citations:
  list[Citation]`. Already permits an empty `citations` list; no schema change.
- `app.generation.generator.generate_answer(question, results)`: unchanged
  contract, still raises on blank question or empty `results` when called
  directly.

New contracts introduced here:

- `DISTANCE_THRESHOLD = 1.0`. Reversible internal default, not a tuned product
  guarantee: `app/embedding/pipeline.py`'s `get_or_create_collection` sets no
  `hnsw:space`, so ChromaDB uses its default squared-L2 distance. The
  `all-MiniLM-L6-v2` model's own `modules.json` ends in a `Normalize` module,
  so every embedding `retrieve()` compares is already unit-length regardless of
  caller options. For unit vectors, squared L2 distance and cosine similarity
  are related by `distance = 2 * (1 - cosine_similarity)`, so `1.0` corresponds
  to a cosine similarity cutoff of `0.5`. That is a defensible starting point,
  not a measured one: there is no eval set yet to tune it against. Do not read
  this as a settled threshold; see Notes for the AI.
- `REFUSAL_MESSAGE`: fixed string, used verbatim as `AnswerResult.answer` on
  refusal. Not configurable; no current requirement needs that.
- `answer_question(question: str, top_k: int = DEFAULT_TOP_K) -> AnswerResult`:
  the new single entry point that ties `retrieve()`, the refusal decision, and
  `generate_answer()` together. This is what item 8's CLI and item 12's
  logging should eventually call instead of assembling the pipeline
  themselves.

## Testing

`AGENTS.md` declares `Test: pytest`. Step 1 adds testable logic (the refusal
decision and its threshold boundary) and must ship a passing test in the same
diff, following `test_generator.py`'s existing pattern: monkeypatch
`generator.retrieve` and the fake Anthropic client rather than touching
ChromaDB, the embedding model, or the real API. Step 2 is thin CLI wiring with
no new logic and is verified by running it, not by a test.

## Notes for the AI

- `DISTANCE_THRESHOLD` is a best-effort default backed by the normalization
  math above, not an empirically tuned one. Item 11's eval runner is the right
  place to measure it against real graded questions and adjust it; don't
  present `1.0` as validated, and don't spend this feature's time hand-tuning
  it against ad hoc queries.
- Use `>=` at the boundary (`distance >= DISTANCE_THRESHOLD` refuses), so tests
  can pin the exact edge case deterministically.
- The refusal check only looks at `results[0].distance` (the nearest, since
  `retrieve()` returns nearest-first). It does not average or otherwise combine
  multiple results' distances; the nearest chunk is the best case for
  supporting an answer, so if it's still too far, none of the others are
  closer.
- Fail loudly, matching the project standard already applied in retrieval and
  generation: `answer_question` still lets a missing `ANTHROPIC_API_KEY` or an
  Anthropic SDK error propagate uncaught when it does call Claude. The refusal
  path itself is a deliberate business response, not error handling, per
  `coding-standards.md`'s Error Handling section, so it returns a normal
  `AnswerResult` rather than raising.
- Reuse `AnswerResult` for the refusal case instead of introducing a new type;
  an empty `citations` list already says "no evidence," and a second type
  would duplicate that distinction for no current benefit.
- Type hints on every signature, `snake_case` functions, `SCREAMING_SNAKE_CASE`
  constants, no em dashes anywhere in code, comments, or docs.


<!-- blueprint:completion {"schemaVersion":1,"specBytes":9826,"specSha256":"b4b0ca5841bf562d92de7a06c4b0636c80d74825cdcf203470cba1a92a9845a9","branch":"refs/heads/feature/refusal-path","head":"973959be091e3445851f00bb359025714ca8826a","baseRef":"refs/heads/master","baseCommit":"973959be091e3445851f00bb359025714ca8826a","sourceTree":"edaf73ced058a20c1dce833c888274f56b5328de","absentOptional":[]} -->
