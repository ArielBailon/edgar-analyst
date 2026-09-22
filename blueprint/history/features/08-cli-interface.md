# Feature: CLI interface

**From build-plan:** feature 8
**Build attempt:** 1
**Status:** verified
**Branch:** `feature/cli-interface`

## Goal

Give the project one real, documented command a user runs to ask a question
from the terminal and see the grounded, cited answer (or the refusal message),
instead of having to know that `app.generation.generator` happens to expose a
dev harness. This is the last piece connecting features 5-7 (retrieval,
generation, refusal) to an actual user-facing entry point; it adds no new
decision logic of its own.

## In scope

- `app/main.py` (currently empty): a `if __name__ == "__main__":` block that
  takes the question from `sys.argv`, calls
  `app.generation.generator.answer_question`, and prints the answer and its
  citations, exactly matching the print behavior already proven in
  `generator.py`'s own harness (blank/missing argument gets a usage message,
  not a traceback; citations only print when there are any).
- Updating `AGENTS.md`'s Commands section: replace the "CLI entry point: >
  TODO" bullet with the real command, and correct the intro paragraph, which
  currently says the CLI is unimplemented and lists only items "1-5 and 9" as
  shipped even though 6 and 7 have since landed.

## Out of scope

- `app = FastAPI()` or any other content in `app/main.py` beyond the CLI block.
  The Commands section already earmarks `app.main:app` for item 15's future
  ASGI app, but item 15 is explicitly post-MVP; `coding-standards.md` says not
  to build its surface ahead of the CLI-first MVP. See Notes for the AI.
  argparse or any flag beyond the single positional question (for example
  exposing `top_k`). No current requirement asks for one, and every existing
  dev harness in this repo (`retriever.py`, `generator.py`) uses the same plain
  `sys.argv` check this feature reuses.
- Changing `answer_question`, `generate_answer`, `retrieve`, or any of their
  contracts. This feature only calls `answer_question`; all of its decision
  logic (including the refusal path) is already implemented and tested.
- The existing per-module dev harnesses in `retriever.py` and `generator.py`.
  They stay as developer conveniences; `app/main.py` becomes the documented
  user-facing entry point alongside them, not a replacement for them.
- Query logging (item 12), the eval set and runner (items 10-11), and the
  README (item 13).

## Build loop

`workflow.stepReview` is `feature`, so implement both build steps in order and
present one review packet after the last step rather than pausing after each.
Each step must still leave the project in a working state on its own.

`workflow.checkpointCommits` is `disabled`, so do not create per-step commits.
`/complete` creates the single feature commit.

`AGENTS.md` declares `Test: pytest`, but both steps here are thin wiring or
documentation with no new decision logic, so neither is a testing gate; each is
verified by its own observable `Done when` instead, following the precedent
already set for `generator.py`'s own `__main__` block in the answer-generation
and refusal-path features.

## Build steps

- [x] 1. Add the CLI entry point to `app/main.py`:

  ```python
  """CLI entry point: ask a question about the ingested filings and transcripts."""

  import sys

  from app.generation.generator import answer_question

  if __name__ == "__main__":
      if len(sys.argv) < 2:
          raise SystemExit('Usage: python -m app.main "<question>"')

      answer = answer_question(sys.argv[1])

      print(answer.answer)
      if answer.citations:
          print()
          print("Sources:")
          for citation in answer.citations:
              print(f"  {citation.company} {citation.document_type} {citation.date} - {citation.section}")
  ```

  **Done when:** against the local index, `python -m app.main "What risk
  factors does Apple disclose about supply chain concentration?"` prints a
  grounded answer with a `Sources:` list; `python -m app.main "What is the
  capital of France?"` prints the refusal message with no `Sources:` section;
  `python -m app.main` with no argument exits with the usage message instead
  of a traceback.

- [x] 2. In `AGENTS.md`'s Commands section, replace the "CLI entry point: >
  TODO - not implemented yet (build plan item 8)" bullet with "CLI entry
  point: `python -m app.main "<question>"`", and update the paragraph above
  the bullet list so it names items 1-9 as shipped (adding 6, 7, and 8) and
  states that `app/main.py` is the CLI entry point instead of saying it's
  still empty.
  **Done when:** `AGENTS.md` no longer contains the string "not implemented
  yet (build plan item 8)", and its Commands section names the exact command
  from step 1.

## Files / areas

- `app/main.py` - new content, currently empty.
- `AGENTS.md` - update the Commands section only.
- `app/generation/generator.py` - read only, for `answer_question`. Do not
  modify.

## Data / contracts

No new contracts. This feature calls the existing
`app.generation.generator.answer_question(question: str) -> AnswerResult` and
prints its `answer` and `citations` fields, reusing the exact print format
already proven in `generator.py`'s own `__main__` block.

## Testing

Neither step introduces logic a test could usefully pin: step 1 is a straight
call into already-tested code (`answer_question` and everything it composes
have their own passing tests from features 6 and 7), and step 2 is a
documentation edit. Both are verified by the observable behavior in their
`Done when`, matching how `generator.py`'s own `__main__` block was verified in
the prior two features rather than unit-tested.

## Notes for the AI

- Do not add `app = FastAPI()` or any other API scaffolding to `app/main.py`.
  The Commands section's existing `uvicorn app.main:app --reload` line is a
  forward reference to item 15 (post-MVP); when that item is eventually
  built, it will need to reconcile the CLI block this feature adds with the
  ASGI app object, but that reconciliation is item 15's problem, not this
  feature's. Don't pre-empt it here.
- Reuse the exact print formatting already in `generator.py`'s `__main__`
  rather than inventing a new one; consistency between the two matters more
  than either one's specific format.
- No em dashes anywhere in code, comments, or docs. Comment the why, not the
  what.
- Fail loudly: let a missing `ANTHROPIC_API_KEY`, a missing/empty index
  (`retrieve`'s existing `RuntimeError` naming the reindex command), or an
  Anthropic SDK error propagate uncaught, matching every other entry point in
  this repo. Do not wrap the call in a `try/except`.


<!-- blueprint:completion {"schemaVersion":1,"specBytes":6623,"specSha256":"953ac37e1d80d2c2bb066fb4ad18d534d74f9d05108656d0a0c6ddc8de3c22d6","branch":"refs/heads/feature/cli-interface","head":"00ec58c06110384c9a6085406de12089537b3639","baseRef":"refs/heads/master","baseCommit":"00ec58c06110384c9a6085406de12089537b3639","sourceTree":"3698cc33f1aff5f985bb3288bb74a854c06b3091","absentOptional":[]} -->
