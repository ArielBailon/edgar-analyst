# Project Plan: edgar-analyst

## 1. Problem

Los analistas de equity y los inversionistas retail informados necesitan responder
preguntas específicas sobre los filings SEC (10-K/10-Q) y las earnings-call
transcripts de una empresa, sin leerse manualmente decenas de páginas por
documento. Los documentos financieros largos hacen lento y propenso a error
encontrar risk factors, comparar lenguaje entre trimestres, o rastrear una
afirmación hasta su fuente exacta.

Este problema aparece de forma explícita en ofertas reales de AI engineering en
el dominio finance: Capital One (Senior Lead AI Engineer, GenAI Platform
Services), Wells Fargo (Lead Specialty AI Engineer, electronic trading), y
BlackRock (AI Engineer). Y es exactamente el problema que LlamaIndex resolvió
con su repo open source "SEC Insights" (RAG sobre SEC filings).

## 2. Users

Analista de equity o inversionista retail informado investigando una empresa
pública específica, que necesita una respuesta fundamentada y citable en vez de
releerse un 10-K/10-Q o transcript completo.

## 3. Features (MVP)

- Ingestar un conjunto pequeño y fijo de filings SEC públicos (10-K/10-Q desde
  SEC EDGAR) y earnings-call transcripts públicos, para 2-3 empresas de ejemplo.
- Chunkear e indexar esos documentos en un vector store (ChromaDB).
- Responder una pregunta en lenguaje natural sobre un filing con una respuesta
  fundamentada que cite el filing y la sección exacta de donde sale.
- Detectar y señalar cuando la pregunta no está soportada por los documentos
  ingestados (sin citas inventadas / sin alucinar fuente).
- Correr completo desde CLI (sin cuentas, sin multi-usuario, sin dashboard en
  esta versión).
- Set de evaluación de 20-50 pares pregunta/respuesta escritos a mano, midiendo
  corrección de citas y relevancia de la respuesta.
- Tests deterministas (pytest) para el pipeline de ingesta y chunking.
- Logs por cada query: fuentes recuperadas, modelo usado, latencia, costo en
  tokens.

Fuera de alcance en esta versión (decisión explícita, no descuido): comparación
de cambios de riesgo entre trimestres, cuentas multi-usuario, respuestas en
streaming, dashboard web, más de un puñado de empresas. La comparación
trimestre-a-trimestre es una candidata fuerte para v2 una vez el path de RAG
básico esté sólido y evaluado.

## 4. Data

- SEC EDGAR (público, gratis, sin auth): 10-K/10-Q de 2-3 empresas de ejemplo.
- Transcripts públicos de earnings calls de esas mismas empresas (páginas de
  investor relations o agregadores públicos de transcripts).
- Derivado: texto chunkeado + embeddings almacenados en ChromaDB (local,
  embebido, sin servidor).
- Set de eval: preguntas + respuesta esperada + cita esperada, etiquetadas a
  mano en CSV/JSON.

## 5. Tech

- Python + FastAPI para la capa de API.
- ChromaDB (embebido, local) como vector store.
- Un proveedor de LLM para generación (a definir según a qué API ya tengas
  acceso — comúnmente OpenAI o Anthropic).
- pytest para tests deterministas.
- Un script de eval propio y chico (no un framework pesado) que puntúe
  corrección de citas y relevancia de respuesta.
- Logging estructurado (logging estándar o structlog) a un archivo local,
  capturando fuentes recuperadas, latencia, tokens y costo.

## 6. Monetize

No aplica — proyecto de portafolio para entrevistas, no un producto comercial.

## 7. UI/UX

CLI primero: se hace una pregunta y se imprime en terminal la respuesta con su
cita. Sin dashboard, sin cuentas, sin trabajo de estilos en esta versión. Una UI
mínima en Streamlit o FastAPI+Swagger puede llegar después, como capa de demo,
una vez el path de RAG esté sólido y evaluado.

## 8. Deployment

Solo local en esta versión (corre desde `venv` con comandos documentados en el
README). Docker/deploy en la nube se deja para después de que la v1 funcione y
los evals pasen, y solo si aporta a la señal de hiring.
