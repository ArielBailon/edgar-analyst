# Feature: Embedding + Indexing

**From build-plan:** feature 4
**Build attempt:** 1
**Status:** verified
**Branch:** `feature/embedding-indexing`

## Goal

Generate embeddings for every chunk already persisted under `data/chunks/`
(feature 3) and index them into a local ChromaDB collection alongside their
`company`/`document_type`/`section`/`date` metadata, so later build steps
(retrieval, item 5; answer generation, item 6) have a queryable vector store to
search against.

## In scope

- An embedding model choice that needs no external API key: `sentence-transformers`
  running locally on CPU (`all-MiniLM-L6-v2`, 384-dim), decided with the user
  because it keeps the MVP's local-only deployment story intact at zero cost.
- A persistent ChromaDB client writing to `chroma_db/` at the repo root (already
  listed in `.gitignore`).
- A pipeline that reads every chunk file under `data/chunks/*/*.json`, embeds
  each chunk's `text`, and upserts it into one ChromaDB collection with the
  chunk's `id` as the vector id, `text` as the document, and
  `company`/`document_type`/`section`/`date` (ISO string) as metadata.
- Idempotent re-runs: running the pipeline again after new chunk files appear
  must not duplicate existing vectors (upsert by chunk id, not insert).
- Adding `chromadb` and `sentence-transformers` to `requirements.txt`.

## Out of scope

- Retrieval/querying the collection (build-plan item 5) - this feature only
  writes to ChromaDB, it does not search it.
- Answer generation, refusal path, CLI (items 6-8).
- Choosing the answer-generation LLM provider - still open per
  `project-overview.md`'s TODO; unrelated to the embedding model decided here,
  since sentence-transformers only produces vectors, not text completions.
- Re-embedding or changing `data/chunks/*.json` on disk - chunk files stay
  exactly as feature 3 wrote them; embeddings live only in ChromaDB.
- A hosted/remote vector database - ChromaDB's embedded local mode matches the
  project's local-only MVP deployment story (`project-overview.md`).

## Build loop

Build one small step at a time. Follow `workflow.stepReview` in
`blueprint/config.json`: currently `feature`, so this produces one review
packet after all steps complete (no per-step approval pauses).
`workflow.checkpointCommits` is `disabled`, so no checkpoint commits are
offered mid-feature. `/complete` makes the final feature commit.

## Build steps

- [x] **Step 1 - Add and verify dependencies** - add `chromadb` and
  `sentence-transformers` to `requirements.txt` (pinned to the versions that
  install cleanly alongside the existing pins) and install them. *Done when:*
  `pip install -r requirements.txt` completes without error and
  `python -c "import chromadb, sentence_transformers"` succeeds in the
  project's environment.
- [x] **Step 2 - Embedding + indexing pipeline** - add `app/embedding/pipeline.py`
  with an `index_all() -> int` function that: iterates every file under
  `data/chunks/*/*.json` (same glob pattern as `app/chunking/pipeline.py`),
  parses each into a list of `Chunk` (reusing `app.chunking.models.Chunk`),
  loads the `all-MiniLM-L6-v2` `SentenceTransformer` model once, encodes each
  file's chunk texts in a batch, and upserts them into a persistent ChromaDB
  collection (client at `chroma_db/`, collection name `edgar_chunks`) using
  `ids=[chunk.id]`, `embeddings=[...]`, `documents=[chunk.text]`, and
  `metadatas=[{"company", "document_type", "section", "date": chunk.date.isoformat()}]`.
  Returns the total number of chunks indexed. Add an
  `if __name__ == "__main__":` guard calling `index_all()` and printing the
  count. *Done when:* running `python -m app.embedding.pipeline` against the
  real `data/chunks/` output from feature 3 completes without error, prints a
  count matching the number of chunks on disk, and the resulting
  `edgar_chunks` collection's `.count()` matches that same number; running it
  a second time leaves `.count()` unchanged (upsert, not duplicate insert).

## Files / areas

- `requirements.txt` - add `chromadb`, `sentence-transformers`
- `app/embedding/__init__.py` - new package
- `app/embedding/pipeline.py` - new: embedding + ChromaDB indexing pipeline
- `.gitignore` - no change needed; `chroma_db/` is already ignored

## Data / contracts

- Reuses `Chunk` from `app.chunking.models` as read-only input; the `Chunk`
  pydantic model and the `data/chunks/*.json` files are unchanged by this
  feature. Embeddings are not added as a field on `Chunk` or serialized into
  the chunk JSON files - ChromaDB is the single store for vectors, matching
  `project-overview.md`'s Data model note that the embedding is "almacenado en
  ChromaDB junto con su metadata." Keeping vectors out of the JSON chunk files
  avoids a second, easily-stale copy of the same data.
- ChromaDB collection `edgar_chunks`, persisted at `chroma_db/`: vector id =
  `Chunk.id` (already globally unique per feature 3), document = `Chunk.text`,
  metadata = `{"company": str, "document_type": str, "section": str, "date":
  str}` (ISO `YYYY-MM-DD`, since Chroma metadata values must be primitives).
  Item 5 (retrieval) queries this exact collection/schema - do not change the
  collection name or metadata keys without updating it.
- No database beyond ChromaDB; no multi-user or auth boundary in this feature.

## Testing

- No test runner is configured yet (`AGENTS.md` declares none); build-plan
  item 9 owns adding pytest coverage, so this feature does not add one.
- Verify `index_all()` manually against the real `data/chunks/` output from
  feature 3 per the Step 2 *Done when*: run it, confirm the printed count
  matches the on-disk chunk count, spot-check a few vector ids/metadata via
  `collection.get(ids=[...])`, then re-run and confirm the count is unchanged.

## Notes for the AI

- Feature 3's notes suggested item 4 might add an `embedding` field to the
  `Chunk` pydantic model. This spec deviates deliberately: the model's own
  Data model section already states the embedding is stored in ChromaDB
  alongside its metadata, and ChromaDB is purpose-built to hold vector +
  document + metadata together. Duplicating the vector into the JSON chunk
  files would create a second source of truth that can drift from the index.
  If a later feature finds it genuinely needs the raw vector outside
  ChromaDB, add the field then with a concrete reason.
- `sentence-transformers` pulls in `torch` as a transitive dependency (a large
  install) and downloads the `all-MiniLM-L6-v2` weights (~90MB) from the
  Hugging Face Hub on first use, caching them locally afterward. This one-time
  network fetch is expected, not a bug; if the environment has no network
  access on first run, say so rather than treating it as a code defect.
- Metadata values must be Chroma-primitive (str/int/float/bool); `Chunk.date`
  is a Python `date` and must be serialized with `.isoformat()` before being
  passed as metadata, not passed as-is.
- Batch the `SentenceTransformer.encode()` call per source chunk file (the
  same file granularity `chunk_all()` used in feature 3), not one call per
  chunk - encoding one string at a time is far slower and defeats the point of
  batching.
- Use `collection.upsert(...)`, not `collection.add(...)` - `add` raises or
  duplicates on an id that already exists, which breaks re-running the
  pipeline after new documents are chunked.


<!-- blueprint:completion {"schemaVersion":1,"specBytes":7394,"specSha256":"3f348ee5693591823c7243d229f32871b6dd6cb2b17064a8e31e1f474b7dec59","branch":"refs/heads/feature/embedding-indexing","head":"8c65996061ee2823a13e4aff49d2771d55434d34","baseRef":"refs/heads/master","baseCommit":"8c65996061ee2823a13e4aff49d2771d55434d34","sourceTree":"670092525349693621c5c278cc311c59425eb0f4","absentOptional":[]} -->