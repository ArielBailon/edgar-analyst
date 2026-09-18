# Feature: Retrieval

**From build-plan:** feature 5
**Build attempt:** 1
**Status:** verified
**Branch:** `feature/retrieval`

## Goal

Given a natural-language question, return the top-k most relevant indexed chunks,
each paired with the citation identifying its exact source document and section.
This is the retrieval half of the RAG path: it selects and cites evidence, it does
not generate an answer and it does not decide whether the evidence is good enough.

## In scope

- A new `app/retrieval/` package holding the retrieval surface.
- `Citation` and `RetrievalResult` pydantic models matching the overview data model.
- `retrieve(question, top_k)` that embeds the question with the same model used at
  index time, queries the existing `edgar_chunks` ChromaDB collection, and returns
  results ordered most relevant first.
- Each result carries the chunk text, its citation, and the raw vector distance, so
  the refusal path (item 7) has a value to threshold on.
- Loud failures for a missing or empty collection and for invalid arguments, per the
  project error-handling standard.
- A minimal `__main__` dev entry point consistent with the other pipeline modules, so
  the behavior is observable without a test runner.

## Out of scope

- Any relevance threshold, "no supporting chunk" detection, or refusal wording. That
  is build-plan item 7 and must not be pre-empted here.
- Answer generation or any LLM call (item 6). No LLM provider is selected yet.
- The user-facing CLI with argument parsing and presentation (item 8). The `__main__`
  block in this feature is a developer harness, not that CLI.
- pytest coverage (item 9), the eval set and runner (items 10-11), and query logging
  (item 12).
- Metadata filters (by company, document type, or date range), reranking, hybrid or
  keyword search, and query expansion. No current requirement establishes them.
- FastAPI or any HTTP surface (post-MVP item 15).
- Re-indexing or changing how chunks are embedded. The existing collection is the
  input to this feature.

## Build loop

`workflow.stepReview` is `feature`, so implement all build steps in order and present
one review packet after the last step rather than pausing after each. Every step must
still leave the project in a working state on its own.

`workflow.checkpointCommits` is `disabled`, so do not create per-step commits.
`/complete` creates the single feature commit.

No `Verify` command is declared in the Commands section of `AGENTS.md`, and no test
runner is configured, so there is no automated gate to run. Prove each step with the
observable behavior named in its `Done when`.

## Build steps

- [x] 1. Create the `app/retrieval/` package with `models.py` defining `Citation`
  (`company`, `document_type`, `section`, `date`, `chunk_id`) and `RetrievalResult`
  (`chunk_id`, `text`, `citation`, `distance`). Reuse the `document_type` literal
  already used by `Chunk`.
  **Done when:** `from app.retrieval.models import Citation, RetrievalResult` succeeds;
  building a `Citation` from a real chunk metadata dict plus a chunk id validates and
  coerces the ISO date string to a `date`; a `document_type` outside the three allowed
  values raises a pydantic `ValidationError`.

- [x] 2. Add `app/retrieval/retriever.py` with `retrieve(question, top_k=DEFAULT_TOP_K)`.
  Import `CHROMA_DIR`, `COLLECTION_NAME`, and `EMBEDDING_MODEL` from
  `app/embedding/pipeline.py` instead of redefining them, so index and query cannot
  drift apart. Load the `SentenceTransformer` once per process via a module-level lazy
  accessor. Query the collection for `top_k` nearest chunks and map each hit to a
  `RetrievalResult`, preserving the order ChromaDB returns.
  Raise `ValueError` for a blank question or `top_k < 1`. Raise `RuntimeError` naming
  `python -m app.embedding.pipeline` when the collection is absent or empty. Let a hit
  with malformed or missing metadata fail loudly rather than being skipped.
  **Done when:** calling
  `retrieve("What risk factors does Apple disclose about supply chain concentration?")`
  against the local index returns 5 `RetrievalResult` objects, each with a populated
  citation and a float distance, in non-decreasing distance order; `top_k=0` and a
  blank question each raise `ValueError`; pointing at a non-existent collection raises
  the `RuntimeError` with the re-index command in its message.

- [x] 3. Add the `if __name__ == "__main__":` block to `retriever.py`, taking the
  question from the command line and printing each result's company, document type,
  section, date, chunk id, distance, and a short text preview.
  **Done when:** `python -m app.retrieval.retriever "What risk factors does Apple
  disclose about supply chain concentration?"` prints 5 results with all of those
  fields populated, and running it with no argument exits with a usage message instead
  of a traceback.

- [x] 4. Repair the findings from the `/audit current` pass (F-01, F-02, F-03). Correct
  the disproven distance-metric note in this spec to the measured relationship, pass
  `strict=True` to the result `zip` so a mismatched ChromaDB response raises instead of
  silently truncating, and cache the resolved collection in a module global the way the
  embedding model is already cached.
  **Done when:** the step 2 and step 3 done-whens still hold unchanged; a second
  `retrieve` call in the same process reuses the cached collection; and the missing
  collection `RuntimeError` still raises once `_collection_handle` is reset, proving the
  cache is the only thing short-circuiting resolution.

## Files / areas

- `app/retrieval/__init__.py` - new, empty, matching the existing package convention.
- `app/retrieval/models.py` - new.
- `app/retrieval/retriever.py` - new.
- `app/embedding/pipeline.py` - read only, imported for `CHROMA_DIR`, `COLLECTION_NAME`,
  and `EMBEDDING_MODEL`. Do not modify it.
- `chroma_db/` - read only at query time. Never written by this feature.

## Data / contracts

Existing contract this feature consumes, established by `app/embedding/pipeline.py`
and `app/chunking/pipeline.py`:

- Collection `edgar_chunks` in the persistent client at `chroma_db/`.
- Stored per chunk: `ids`, `documents` (the chunk text), and `metadatas` with exactly
  `company`, `document_type`, `section`, and `date` (an ISO `YYYY-MM-DD` string).
- Chunk ids are deterministic and shaped
  `{company}-{document_type}-{date}-{section_slug}-{index}`. Treat them as opaque
  identifiers; do not parse them to recover metadata.
- Embeddings come from `all-MiniLM-L6-v2` (384 dimensions). The question must be
  embedded with that same model or distances are meaningless.

New contracts introduced here:

- `Citation`: `company: str`, `document_type: Literal["10-K", "10-Q", "transcript"]`,
  `section: str`, `date: date`, `chunk_id: str`.
- `RetrievalResult`: `chunk_id: str`, `text: str`, `citation: Citation`,
  `distance: float`.
- `DEFAULT_TOP_K = 5`.
- `distance` is the raw distance ChromaDB returns for the collection's configured
  metric, where lower means more similar. It is passed through unchanged and not
  normalized into a score, so item 7 can define its own threshold against a value with
  known meaning.
- Requesting a `top_k` larger than the number of indexed chunks returns every chunk
  rather than raising. That is ChromaDB behavior and is acceptable.

## Testing

No `test` command is declared in the Commands section of `AGENTS.md`, so per the
project testing standard tests are not a gate for this feature and no runner may be
installed mid-feature. Verify each step with the observable evidence in its
`Done when`, run against the populated local index.

Build-plan item 9 explicitly covers pytest coverage for retrieval. Keep `retrieve` and
the metadata-to-`Citation` mapping as plain, injectable functions so that item can test
them without reworking this code. Do not claim test coverage that was not run.

`retriever.py` caches the embedding model in `_model` and the collection in
`_collection_handle`. Both are module globals, so item 9 needs a fixture that resets
them between tests, otherwise a test that points `COLLECTION_NAME` at a missing
collection will be served the cached handle from an earlier test and pass for the wrong
reason.

## Notes for the AI

- The local index is populated: 2406 chunks across AAPL, MSFT, and TSLA, covering
  10-K (1029), 10-Q (872), and transcript (505). `data/` and `chroma_db/` are
  gitignored, so this data is local only and is not part of the feature commit.
- Section strings carry non-breaking spaces exactly as EDGAR emitted them, for example
  `Item 1A.` followed by four non-breaking spaces and `Risk Factors`. Pass them through
  untouched. Normalizing them here would silently disagree with what is stored in the
  index, and any cleanup belongs in the chunking layer as its own fix.
- `distance` is squared L2 over unit vectors, so it is bounded to `[0, 4]` and
  `cosine = 1 - distance / 2`. Measured, not assumed: the collection's configured space
  is `l2`, and `all-MiniLM-L6-v2` ends in a Normalize module, so query and stored
  vectors both have norm exactly 1.0. For unit vectors squared L2 equals
  `2 - 2 * cosine` (measured maximum deviation across the index: 2.6e-07), and the
  top-20 ranking is identical under either metric. Feature 7 can therefore set its
  refusal threshold against this value directly. No re-index is needed, and configuring
  a cosine space would change the numbers without changing the ordering.
- Fail loudly on retrieval errors. Never skip a hit or swallow an exception to return a
  shorter list, because citation accuracy depends on knowing exactly what matched.
- Type hints on every signature, pydantic for the structures crossing this boundary,
  `snake_case` functions, `SCREAMING_SNAKE_CASE` constants.
- No em dashes anywhere in code, comments, or docs. Comment the why, not the what, and
  skip comments that restate the code.


<!-- blueprint:completion {"schemaVersion":1,"specBytes":9939,"specSha256":"82123ec74a2c569e649375d3b0c56dd8457696cf31ffb10da4f3519f878f7eff","branch":"refs/heads/feature/retrieval","head":"b68da8b3a1b9ea05b77355a0c4059f6144a8bb8b","baseRef":"refs/heads/master","baseCommit":"b68da8b3a1b9ea05b77355a0c4059f6144a8bb8b","sourceTree":"988c4abc8e021e763951e14844b37c974905260f","absentOptional":[]} -->

## Findings

### 5/F-01 [P2] closed - Spec records a disproven claim about the distance metric

**File:** blueprint/context/current-feature.md:159
**Found:** 2026-09-18 by /audit (scope: current; lens: quality)
**Why it matters:** The Notes for the AI section states the collection "uses the
ChromaDB default rather than cosine, and the indexed vectors are not normalized"
and instructs the next implementer not to assume cosine. Measurement disproves
both halves. `all-MiniLM-L6-v2` ends in a Normalize module, so query and stored
vectors both have norm exactly 1.0, and the collection's configured space is
`l2`. For unit vectors squared-L2 equals `2 - 2*cosine` (measured max deviation
2.6e-07), so the returned distance is a strictly monotonic function of cosine
similarity and the top-20 ranking is byte-identical under both metrics.
`/complete` archives this spec permanently, and build-plan item 7 reads it to
choose a refusal threshold. Left as written, it tells that implementer the
distance has no known relation to cosine, which removes the one principled basis
for picking a threshold and invites an unnecessary re-index of feature 4.
**Suggested fix:** Replace the note with the proven relationship: distance is
squared L2 over unit vectors, bounded to [0, 4], and `cosine = 1 - distance / 2`.
Drop the re-index suggestion.
**Resolution:** Fixed 2026-09-18 in build step 4. The note now states the measured
relationship (squared L2 over unit vectors, bounded to [0, 4], `cosine = 1 - distance / 2`)
with the evidence behind it, and says no re-index is needed. Re-verified live:
distances 0.7270, 0.7471, 0.7938 map to cosine 0.6365, 0.6265, 0.6031, and all
returned distances fall within [0, 4].

### 5/F-02 [P3] closed - zip can silently truncate a mismatched ChromaDB response

**File:** app/retrieval/retriever.py:64
**Found:** 2026-09-18 by /audit (scope: current; lens: quality)
**Why it matters:** The coding standard is explicit that retrieval must fail
loudly "rather than silently skipping a document or chunk, since citation
accuracy depends on knowing exactly what was and wasn't indexed." Bare `zip`
stops at the shortest input, so if ChromaDB ever returned parallel lists of
differing length, `retrieve` would return a quietly short result set rather than
raising. That is the exact failure mode the standard names. No current ChromaDB
behavior is known to produce it, so this is defensive, not a live bug.
**Suggested fix:** Pass `strict=True` to `zip`. The project runs Python 3.13, so
it is available and turns the silent truncation into a `ValueError`.
**Resolution:** Fixed 2026-09-18 in build step 4. `zip(..., strict=True)` at
`app/retrieval/retriever.py:73`. Re-verified: the live query still returns the same 5
results with identical distances, so the guard changed no behavior on the healthy path.

### 5/F-03 [P3] closed - PersistentClient and count() are rebuilt on every query

**File:** app/retrieval/retriever.py:28
**Found:** 2026-09-18 by /audit (scope: current; lens: performance)
**Why it matters:** `_collection()` constructs a fresh `PersistentClient`, calls
`get_collection`, and calls `count()` on each `retrieve` call, while the
embedding model beside it is deliberately cached in a module global. Measured
cost is about 5 ms per call, so this is not a current bottleneck. It becomes
repeated avoidable work once item 8's CLI and item 11's eval runner call
`retrieve` in a loop over 20-50 questions.
**Suggested fix:** Cache the resolved collection in a module global the same way
`_embedding_model()` caches the model. Keep the existing missing and empty
collection errors on the first resolution.
**Resolution:** Fixed 2026-09-18 in build step 4. `_collection()` now caches into
`_collection_handle` after validating, so the missing and empty errors still run on
first resolution. Re-verified: the handle is populated after the first call, a second
call reuses it, and the missing-collection `RuntimeError` still raises with the
re-index command once the handle is reset. Accepted cost recorded in the spec's Testing
section: item 9 needs a fixture resetting `_model` and `_collection_handle` between
tests, since a stale handle would otherwise mask a missing-collection test.
