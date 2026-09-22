# edgar-analyst - Project Overview

<!-- blueprint:source-hash 4c72dc27acfaa11b681a0f1bcdf509afa005381798d8a654462df76de61bebb4 -->

> RAG sobre filings SEC (10-K/10-Q) y earnings-call transcripts: responde
> preguntas en lenguaje natural con una cita fundamentada, o se rehúsa cuando
> no hay soporte.

## Problem

Los analistas de equity y los inversionistas retail informados necesitan
responder preguntas específicas sobre filings SEC y earnings-call transcripts
sin leerse manualmente decenas de páginas por documento. Encontrar risk
factors, comparar lenguaje entre trimestres, o rastrear una afirmación hasta su
fuente exacta es lento y propenso a error. Proyecto de portafolio alineado con
roles reales de AI engineering en finance (Capital One, Wells Fargo,
BlackRock) y con el patrón que LlamaIndex validó en su repo "SEC Insights".

## Users

Analista de equity o inversionista retail informado investigando una empresa
pública específica, que necesita una respuesta fundamentada y citable en vez
de releerse un 10-K/10-Q o transcript completo. Un solo tipo de usuario, sin
cuentas ni multi-tenancy en el MVP.

## Features

El set de MVP, en orden de build plan. **Answer generation** y **Refusal
path** son el diferenciador central: citas fundamentadas sin alucinar fuente.

1. **Ingest pipeline (filings)** - descarga y parsea 10-K/10-Q desde SEC EDGAR
   a texto limpio, para 2-3 empresas fijas.
2. **Ingest pipeline (transcripts)** - descarga y parsea earnings-call
   transcripts públicos de esas mismas empresas.
3. **Chunking** - divide los documentos en chunks con metadata (empresa, tipo
   de filing, sección, fecha).
4. **Embedding + indexing** - genera embeddings de los chunks y los guarda en
   ChromaDB con su metadata.
5. **Retrieval** - dada una pregunta, recupera los top-k chunks relevantes
   junto con su cita.
6. **Answer generation** - genera una respuesta fundamentada citando filing +
   sección exacta.
7. **Refusal path** - detecta y responde correctamente cuando ningún chunk
   soporta la pregunta, sin alucinar fuente.
8. **CLI interface** - hace una pregunta desde terminal y muestra la
   respuesta con sus citas.
9. **Tests deterministas** - cobertura pytest para ingesta, chunking y
   retrieval.
10. **Eval set** - 20-50 pares pregunta/respuesta etiquetados a mano con cita
    esperada.
11. **Eval runner** - corre el eval set y puntúa corrección de citas y
    relevancia de la respuesta.
12. **Logging** - logs estructurados por query (fuentes, latencia, tokens,
    costo).
13. **README** - problema, usuario, setup, comandos de run/test/eval, y
    trade-offs documentados.

Post-MVP (no programado en esta fase): comparación de riesgo
quarter-over-quarter (14), endpoint FastAPI sobre la lógica del CLI (15), UI
de demo en Streamlit (16), Docker + deploy básico (17).

## Data model

### Filing

- `company` (str) - empresa (una de las 2-3 fijas en el MVP)
- `filing_type` (str) - `"10-K"` | `"10-Q"`
- `date` (date) - fecha del filing
- `raw_text` (str) - texto limpio parseado desde SEC EDGAR
- `source_url` (str) - URL original en SEC EDGAR

### Transcript

- `company` (str) - misma empresa que sus filings
- `date` (date) - fecha del earnings call
- `raw_text` (str) - texto limpio del transcript
- `source_url` (str) - URL pública de origen

### Chunk

- `id` (str) - identificador único
- `company`, `document_type` (`"10-K"` | `"10-Q"` | `"transcript"`), `section`,
  `date` - metadata heredada del `Filing`/`Transcript` de origen
- `text` (str) - contenido del chunk
- `embedding` (vector) - almacenado en ChromaDB junto con la metadata

> Locks the shape retrieval, answer generation, and citations depend on.

### Citation

- `company`, `document_type`, `section`, `date` - identifican la fuente exacta
- `chunk_id` - referencia al `Chunk` que soporta la respuesta

### EvalPair

- `question` (str)
- `expected_answer` (str)
- `expected_citation` (`Citation`)
- Etiquetado a mano, almacenado en CSV/JSON (20-50 pares).

### QueryLog

- `timestamp` (datetime), `question` (str)
- `retrieved_sources` (list[`Citation`])
- `model` (str), `latency_ms` (int), `tokens` (int), `cost` (float)
- Una entrada por query, a un archivo local.

## Tech stack

- **Python** - lenguaje del proyecto
- **FastAPI** - capa de API; post-MVP (build plan item 15), el MVP corre solo
  por CLI
- **ChromaDB (embebido, local)** - vector store para chunks + embeddings
- **Anthropic (Claude)** - proveedor de LLM para generación, vía el SDK
  `anthropic` y `ANTHROPIC_API_KEY` en `.env`. Decidido el 2026-09-18.
- **pytest** - tests deterministas de ingesta, chunking y retrieval
- **Script de eval propio** - sin framework pesado; puntúa corrección de
  citas y relevancia
- **Logging estándar / structlog** - logs estructurados a archivo local

## Monetization

No aplica - proyecto de portafolio para entrevistas, no un producto comercial.

## UI/UX

CLI primero: se hace una pregunta y se imprime en terminal la respuesta con
su cita. Sin dashboard, sin cuentas, sin trabajo de estilos en el MVP.
Streamlit o FastAPI+Swagger como capa de demo posterior (post-MVP, items
15-16).

- CLI - pregunta en lenguaje natural -> respuesta fundamentada + cita en
  terminal.

## Deployment

Solo local en el MVP: corre desde `venv` con comandos documentados en el
README (item 13). Docker + deploy básico se deja para después de que el path
de RAG funcione y los evals pasen (item 17).

El único secreto del proyecto vive en `.env` (gitignored): `SEC_EDGAR_USER_AGENT`
para la fair-access policy de SEC EDGAR, y `ANTHROPIC_API_KEY` para generación.

## Open questions

- Tech (project-plan §5) lista FastAPI como parte del stack, pero build-plan
  pone el endpoint FastAPI (item 15) en Post-MVP y UI/UX (§7) confirma que el
  MVP corre solo por CLI. Este overview trata FastAPI como capa post-MVP;
  confirma si es correcto.
- Modelo de Claude, límites de tokens y presupuesto de costo por query sin
  definir. Item 12 registra `model`, `tokens` y `cost` por query, así que el
  item 6 tiene que fijar un modelo concreto.
- Deployment más allá de "local" (Docker, host, env vars) queda sin definir
  hasta el item 17.
