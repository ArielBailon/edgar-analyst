# Feature: Answer generation

**From build-plan:** feature 6
**Build attempt:** 1
**Status:** verified
**Branch:** `feature/answer-generation`

## Goal

Given a question and the top-k retrieved chunks for it, generate a grounded answer
using Claude, citing the exact filing (or transcript) and section each part of the
answer draws from. This is the generation half of the RAG path: it turns already-
retrieved evidence into prose. It does not retrieve, does not decide whether the
evidence is sufficient, and does not present the result to an end user.

## In scope

- A new `app/generation/` package.
- `AnswerResult` pydantic model: the generated `answer` text plus the `citations`
  (the `Citation` of every chunk that was given to the model as context).
- `generate_answer(question, results)` that builds a numbered context block from
  the given `RetrievalResult`s, calls the Claude Messages API with a system prompt
  that restricts the model to that context and requires inline `[n]` citations, and
  returns an `AnswerResult`.
- The `anthropic` Python SDK as a new dependency, pinned in `requirements.txt`.
- Reading `ANTHROPIC_API_KEY` from the environment (already documented in
  `.env.example`), failing loudly with a message pointing at `.env` when it is
  unset, matching the existing `SEC_EDGAR_USER_AGENT` pattern in
  `app/ingest/edgar_client.py`.
- Loud failures for a blank question and for an empty `results` list, per the
  project error-handling standard: generating an answer from zero evidence is a
  contract violation, not a business feature.
- A minimal `__main__` dev entry point that chains `retrieve()` into
  `generate_answer()` and prints the answer with its citations, consistent with
  the other pipeline modules' dev harnesses.

## Out of scope

- Any relevance threshold or "no supporting chunk" decision. That is build-plan
  item 7 (refusal path) and must not be pre-empted here. This feature always
  calls Claude with whatever `results` it is given; it does not inspect
  `distance` or decide when evidence is too weak.
- The user-facing CLI with argument parsing and presentation (item 8). The
  `__main__` block here is a developer harness, not that CLI.
- Query logging: timestamp, latency, tokens, cost (item 12). Nothing here writes
  a log file.
- Eval set and eval runner (items 10-11).
- Parsing the model's answer text to determine which specific `[n]` markers it
  actually used. `citations` is the full set of chunks given as context, not a
  parsed subset; that keeps the contract deterministic and independent of the
  model's output formatting.
- Streaming responses, conversation history / multi-turn, or configurable
  model/temperature via environment or CLI flags. No current requirement needs
  them.
- FastAPI or any HTTP surface (post-MVP item 15).

## Build loop

`workflow.stepReview` is `feature`, so implement all build steps in order and
present one review packet after the last step rather than pausing after each.
Every step must still leave the project in a working state on its own.

`workflow.checkpointCommits` is `disabled`, so do not create per-step commits.
`/complete` creates the single feature commit.

`AGENTS.md` now declares a `Test` command (`pytest`), so per the project testing
standard, tests are a gate for logic-bearing steps: steps 1 and 2 below must ship
a passing pytest test in the same reviewable diff. No `Verify` command is
declared yet, so there is no combined typecheck/build gate to run. Step 3 is thin
CLI wiring with no new logic; verify it with the observable behavior in its
`Done when` instead of a test.

## Build steps

- [x] 1. Add `anthropic==1.7.0` to `requirements.txt`. Create the `app/generation/`
  package with `__init__.py` and `models.py` defining `AnswerResult` (`answer:
  str`, `citations: list[Citation]`, importing `Citation` from
  `app.retrieval.models`).
  **Done when:** `pip install -r requirements.txt` succeeds and `import anthropic`
  works; `from app.generation.models import AnswerResult` succeeds; a test in
  `app/generation/test_models.py` builds an `AnswerResult` from a real `Citation`
  and asserts the fields round-trip.

- [x] 2. Add `app/generation/generator.py` with:
  - Constants `MODEL = "claude-haiku-4-5-20251001"`, `MAX_TOKENS = 1024`, and a
    module-level `SYSTEM_PROMPT` string instructing the
    model to answer only from the numbered context blocks it is given, to cite
    the source of every claim with the matching `[n]` marker, and to say plainly
    that the context does not contain the answer rather than using outside
    knowledge when it doesn't.
  - `_client()`: a lazy module-global `anthropic.Anthropic` instance, reading
    `ANTHROPIC_API_KEY` via `os.environ.get` after `load_dotenv()` (mirroring
    `app/ingest/edgar_client.py`'s `_user_agent()`), raising `RuntimeError`
    naming `.env` and `ANTHROPIC_API_KEY` when it is unset.
  - `_build_context(results: list[RetrievalResult]) -> str`: a pure function that
    numbers each result `[1]`, `[2]`, ... and renders its company, document type,
    date, section, and text, in the order given.
  - `generate_answer(question: str, results: list[RetrievalResult]) ->
    AnswerResult`: raises `ValueError` for a blank question or an empty
    `results` list; otherwise builds the context, calls
    `client.messages.create(model=MODEL, max_tokens=MAX_TOKENS,
    temperature=TEMPERATURE, system=SYSTEM_PROMPT, messages=[...])`, extracts the
    text from the response's first content block, and returns an `AnswerResult`
    with that text and `citations=[r.citation for r in results]`.
  **Done when:** `app/generation/test_generator.py` monkeypatches `_client()`
  with a fake exposing `messages.create` (same style as `test_retriever.py`
  fakes `chromadb`), and proves: a blank question raises `ValueError`; an empty
  `results` list raises `ValueError`; `_build_context` renders every result with
  a distinct `[n]` and its citation fields; `generate_answer` returns an
  `AnswerResult` whose `answer` is the fake response's text and whose
  `citations` list matches the input results' citations in order; and a missing
  `ANTHROPIC_API_KEY` raises `RuntimeError` naming `.env`.

- [x] 3. Add the `if __name__ == "__main__":` block to `generator.py`: take the
  question from the command line (usage message on no argument, matching
  `retriever.py`), call `retrieve()` then `generate_answer()`, and print the
  answer text followed by the citation list (company, document type, date,
  section per line).
  **Done when:** `python -m app.generation.generator "What risk factors does
  Apple disclose about supply chain concentration?"` prints a grounded answer
  with inline `[n]` markers and a matching citation list, against the local
  index; running it with no argument exits with a usage message instead of a
  traceback.

## Files / areas

- `app/generation/__init__.py` - new, empty, matching the existing package
  convention.
- `app/generation/models.py` - new.
- `app/generation/generator.py` - new.
- `app/generation/test_models.py` - new.
- `app/generation/test_generator.py` - new.
- `requirements.txt` - add `anthropic==1.7.0`.
- `app/retrieval/models.py`, `app/retrieval/retriever.py` - read only, imported
  for `Citation`, `RetrievalResult`, and `retrieve()`. Do not modify.
- `app/ingest/edgar_client.py` - read only, referenced as the existing pattern
  for reading a required env var and failing loudly. Do not modify.

## Data / contracts

Existing contracts this feature consumes:

- `app.retrieval.models.Citation`: `company`, `document_type` (`"10-K"` |
  `"10-Q"` | `"transcript"`), `section`, `date`, `chunk_id`.
- `app.retrieval.models.RetrievalResult`: `chunk_id`, `text`, `citation`,
  `distance`.
- `app.retrieval.retriever.retrieve(question, top_k)`.
- `ANTHROPIC_API_KEY` in `.env`, already documented in `.env.example`.

New contracts introduced here:

- `AnswerResult`: `answer: str`, `citations: list[Citation]`.
- `MODEL = "claude-haiku-4-5-20251001"`. Chosen over Sonnet 5 for lower per-query
  cost, since item 11's eval runner will call this repeatedly over 20-50
  questions per pass. Item 12 will log this value per query; do not make it
  configurable without a new requirement.
- `MAX_TOKENS = 1024`. Reversible internal default (not a product decision):
  comfortably covers a filing-analysis answer citing a handful of sections.
  `anthropic==1.7.0`'s `messages.create` has no `temperature` parameter for this
  model generation (confirmed against the installed SDK and a live call);
  sampling is not configured, and there is no equivalent knob to set for
  Haiku 4.5.
- `citations` on `AnswerResult` is always every chunk passed in `results`, in the
  same order, regardless of which `[n]` markers appear in the generated text.
  This is a deliberate simplification: parsing the model's citation markers back
  out of free text would make the contract depend on output formatting the model
  doesn't strictly guarantee. Item 7 and item 12 should treat `citations` as "the
  evidence considered," not "the evidence the model claims to have used."
- The Anthropic Messages API response's first content block exposes the
  generated text as `.text` (a `TextBlock`). This feature reads only that field
  and does not handle multi-block or tool-use responses, since the system prompt
  never asks for either.

## Testing

`AGENTS.md` declares `Test: pytest`. Steps 1 and 2 add testable logic
(`AnswerResult` construction, blank/empty validation, `_build_context`, and the
response-to-`AnswerResult` mapping) and must ship passing tests in the same
diff, following `test_retriever.py`'s pattern: fake the external client rather
than calling the real Anthropic API, and never call the real network in a test.
Step 3's `__main__` block is thin CLI wiring with no new logic and is verified
by running it, not by a test.

## Notes for the AI

- The model choice (Haiku 4.5) was confirmed with the user during `/feature`,
  specifically to keep cost down given the repeated calls item 11's eval runner
  will make. Do not swap it for Sonnet or another model without a new decision.
- Fail loudly: let `anthropic` SDK errors (auth, rate limit, API errors)
  propagate uncaught rather than catching and hiding them, matching the
  project's error-handling standard already applied in retrieval and ingest.
- Reuse `Citation` and `RetrievalResult` from `app.retrieval.models` rather than
  redefining them; `app/generation/` only introduces `AnswerResult`.
- Type hints on every signature, pydantic for structures crossing this boundary,
  `snake_case` functions, `SCREAMING_SNAKE_CASE` constants.
- No em dashes anywhere in code, comments, or docs. Comment the why, not the
  what, and skip comments that restate the code.
- `retriever.py`'s `_model`/`_collection_handle` module-global caching and its
  autouse pytest fixture that resets them are the precedent for `_client()`
  here: `test_generator.py` needs the same reset pattern so a cached fake client
  from one test cannot leak into another.


<!-- blueprint:completion {"schemaVersion":1,"specBytes":11059,"specSha256":"9a18eb78abd4ebb58d2a311ee821ca399aa51cedffa7c7b52d12b1e31209a244","branch":"refs/heads/feature/answer-generation","head":"92aac707303d172b6e9a77a3ad5990aac4603d87","baseRef":"refs/heads/master","baseCommit":"92aac707303d172b6e9a77a3ad5990aac4603d87","sourceTree":"eaa6b046fa2d157eb2db7dcecde6f232075c52e8","absentOptional":[]} -->
