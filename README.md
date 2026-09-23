# edgar-analyst

Ask natural-language questions about SEC filings (10-K and 10-Q) and
earnings-call transcripts, and get an answer grounded in the source text with a
citation to the exact filing and section it came from. When nothing retrieved
supports an answer, it says so instead of guessing or inventing a source.

It is a small retrieval-augmented generation (RAG) pipeline that runs entirely
from the command line on a local corpus: SEC EDGAR filings and Motley Fool
transcripts for three companies, embedded locally into ChromaDB, with answers
written by Claude.

## Problem

Equity analysts and informed retail investors often need a specific answer from
a company's filings or earnings calls: what risk factors it discloses, what
management said about a metric, where a claim actually comes from. Getting that
answer usually means reading dozens of pages per document, and tracing a claim
back to its exact source is slow and error-prone.

edgar-analyst answers the question directly and shows where the answer came
from, so the reader can check it instead of trusting it.

## Who it's for

A single kind of user: an equity analyst or informed retail investor
researching one specific public company, who wants a grounded, citable answer
rather than rereading a full 10-K, 10-Q, or call transcript. There are no
accounts and no multi-user features.

## How it works

1. **Ingest filings** (`app/ingest/pipeline.py`): downloads the latest 10-K and
   the two latest 10-Qs for Apple (AAPL), Microsoft (MSFT), and Tesla (TSLA)
   from SEC EDGAR and extracts clean text.
2. **Ingest transcripts** (`app/ingest/transcripts_pipeline.py`): finds the two
   most recent earnings-call transcripts per company on Motley Fool (fool.com)
   through its public monthly sitemaps and extracts the call text.
3. **Chunk** (`app/chunking/`): splits each filing by its `Item N.` headings and
   each transcript by speaker turn, then packs paragraphs into chunks of up to
   about 1,200 characters with a 150-character overlap. Every chunk carries its
   company, document type, section, and date.
4. **Embed and index** (`app/embedding/pipeline.py`): embeds every chunk with
   the local `all-MiniLM-L6-v2` sentence-transformers model and stores it in an
   embedded ChromaDB collection under `chroma_db/`.
5. **Retrieve** (`app/retrieval/`): embeds the question with the same model and
   returns the 5 nearest chunks with their citations and distances.
6. **Refuse or answer** (`app/generation/generator.py`): if nothing was
   retrieved, or the nearest chunk is too far away, it returns a fixed refusal
   without calling the model. Otherwise it sends the question and the numbered
   chunks to Claude Haiku 4.5, which is instructed to use only those chunks and
   to cite them as `[1]`, `[2]`, and so on.
7. **Log** (`app/logging/`): every question, answered or refused, appends one
   structured entry to a local JSON Lines file.

## Setup

Requires Python 3.13.

```text
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in both values:

- `SEC_EDGAR_USER_AGENT`: your name and email, for example
  `Jane Doe jane@example.com`. SEC EDGAR's fair-access policy requires a
  descriptive User-Agent on every request. Needed to ingest filings.
- `ANTHROPIC_API_KEY`: needed to answer questions and to run the eval. Not
  needed for ingest, chunking, indexing, retrieval, or the test suite.

`.env`, the virtual environment, `data/`, and `chroma_db/` are all gitignored.

## Build the local index

The corpus is not stored in the repository. Build it once, in this order:

```text
python -m app.ingest.pipeline
python -m app.ingest.transcripts_pipeline
python -m app.chunking.pipeline
python -m app.embedding.pipeline
```

The first two steps download from sec.gov and fool.com. The last step downloads
the `all-MiniLM-L6-v2` model (about 87 MB) the first time it runs. Until the
index exists, asking a question fails with a `RuntimeError` that names the
command to run.

## Ask a question

```text
python -m app.main "<question>"
```

An answerable question prints the answer, then the chunks it was given as
sources:

```text
$ python -m app.main "What risk factors does Apple disclose about supply chain concentration?"
Based on the provided context blocks, Apple discloses the following risk factors about supply chain concentration:

**Supplier Consolidation and Dependency Risks:**
Apple discloses that "component suppliers may fail, be subject to consolidation within a particular industry, or decide to concentrate on the production of common components instead of components customized to meet the Company's requirements, ..." [3]

**Supply Shortage and Price Increase Risks:**
Apple notes that it "remains subject to significant risks of supply shortages and price increases that can materially adversely affect its business, results of operations, financial condition and stock price." [3]

...

Sources:
  AAPL 10-Q 2026-05-01 - Item 1A.    Risk Factors
  AAPL 10-Q 2026-07-31 - Item 2.    Management’s Discussion and Analysis of Financial Condition and Results of Operations
  AAPL 10-K 2025-10-31 - Item 1A.    Risk Factors
  AAPL 10-K 2025-10-31 - Item 1A.    Risk Factors
  AAPL 10-K 2025-10-31 - Item 1A.    Risk Factors
```

A question the corpus cannot support is refused, with no sources:

```text
$ python -m app.main "What is the best recipe for chocolate chip cookies?"
The retrieved filings and transcripts do not contain information to answer this question.
```

## Run the tests

```text
pytest
```

The suite is deterministic: it needs no network, no index, no API key, and it
never writes the real query log. It is the fastest way to confirm a fresh clone
is healthy.

## Run the eval

```text
python -m app.eval.runner
```

The eval runs the 22 hand-labeled question/answer pairs in
`app/eval/eval_set.json` through the full pipeline and prints one `[HIT]` or
`[MISS]` line per question, then two summary scores:

- **Citation accuracy**: the share of questions whose answer cites the exact
  expected chunk (matched by `chunk_id`).
- **Average relevance**: the mean cosine similarity between each actual answer
  and its expected answer, embedded with the same `all-MiniLM-L6-v2` model used
  for the index.

It needs the local index and `ANTHROPIC_API_KEY`, and it makes one Claude call
per question that is not refused.

Result of a full run on 2026-09-23:

```text
Citation accuracy: 6/22 (27%)
Average relevance: 0.730
```

Citation accuracy is low. Part of that is the strict metric (see Trade-offs):
an answer that cites a neighboring chunk containing the same fact still counts
as a miss. The rest is real retrieval weakness, and improving it is the most
obvious next step.

## Query log

Every call to answer a question appends one JSON line to
`data/logs/queries.jsonl`, with these fields:

| Field | Meaning |
| --- | --- |
| `timestamp` | UTC time of the call |
| `question` | the question as asked |
| `retrieved_sources` | citations for every retrieved chunk, including ones a refusal rejected |
| `model` | the Claude model used, or `""` when the question was refused |
| `latency_ms` | wall time for the whole call, retrieval included |
| `tokens` | input plus output tokens, or `0` when refused |
| `cost` | dollar cost of the Claude call, or `0.0` when refused |

`cost` is computed from Claude Haiku 4.5's published rates ($1.00 per million
input tokens, $5.00 per million output tokens), stored as two constants in
`app/logging/query_logger.py`. It is not a live price lookup.

## Project layout

```text
app/
  main.py        CLI entry point
  ingest/        SEC EDGAR filing and Motley Fool transcript download and text extraction
  chunking/      section detection and paragraph-aware chunking
  embedding/     embedding model and ChromaDB indexing
  retrieval/     top-k nearest-chunk search and the Citation model
  generation/    refusal check and Claude answer generation
  eval/          hand-labeled eval set and eval runner
  logging/       QueryLog model and JSON Lines query logger
```

Tests live next to the code they cover, as `test_<module>.py`.

## Trade-offs and limitations

- **A tiny, fixed corpus.** Three companies, each with one 10-K, two 10-Qs,
  and two transcripts, instead of ingesting on demand. This keeps the index
  small and the eval reproducible. It cannot answer about any other company or
  any earlier period.
- **Transcripts scraped from Motley Fool.** Free, public, and citable, with no
  paid transcript API. The cost is a dependency on that site's page markup and
  sitemaps; if either changes, transcript ingest breaks.
- **Local embeddings.** `all-MiniLM-L6-v2` runs locally, costs nothing, works
  offline after its first download, and needs no second API key. It is a small
  model, and retrieval quality is weaker than with larger hosted embedding
  models.
- **Simple, deterministic chunking.** Sections come from `Item N.` headings in
  filings and speaker turns in transcripts; within a section, whole paragraphs
  are packed into chunks of up to about 1,200 characters with a 150-character
  overlap. This is easy to reason about and test. The cost: a paragraph longer
  than the limit is cut mid-text, and a document whose headings are not found
  falls back to a single `Full Document` or `Full Transcript` section, which
  makes its citations less precise.
- **Refusal by one distance threshold.** If the nearest chunk's distance is at
  or above `DISTANCE_THRESHOLD = 1.0`, the question is refused before any model
  call, so off-topic questions cost nothing and never get an invented source.
  The threshold is a reasoned default, not tuned against the eval set, so it can
  refuse a borderline answerable question or let a weakly related one through.
  In that second case the model is still instructed to say the context does not
  support an answer.
- **Claude Haiku 4.5 for answers.** Low cost and latency per question. A larger
  model might write better syntheses across several chunks.
- **Eval scoring without an LLM judge.** Relevance is embedding similarity,
  which is free, deterministic, and needs no extra API calls, but it rewards
  similar wording rather than factual correctness. Citation accuracy requires
  the exact expected chunk, so it undercounts answers that cite a different
  chunk stating the same fact.
- **An append-only local log.** One JSON Lines file with no rotation, size cap,
  or reader. Enough for one local user; it grows without bound.
- **CLI only.** An HTTP API (FastAPI), a Streamlit demo UI, Docker and
  deployment, and quarter-over-quarter risk comparison are all planned but not
  built.
