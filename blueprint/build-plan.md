# Build Plan: edgar-analyst

- [x] 1. Ingest pipeline - descargar y parsear los 10-K/10-Q de 2-3 empresas desde SEC EDGAR a texto limpio
- [x] 2. Ingest pipeline - descargar y parsear los earnings-call transcripts públicos de esas mismas empresas
- [x] 3. Chunking - dividir los documentos ingestados en chunks para retrieval, con metadata (empresa, tipo de filing, sección, fecha)
- [ ] 4. Embedding + indexing - generar embeddings de los chunks y guardarlos en ChromaDB con su metadata
- [ ] 5. Retrieval - dada una pregunta, recuperar los top-k chunks relevantes junto con su cita
- [ ] 6. Answer generation - generar una respuesta fundamentada a partir de los chunks recuperados, citando filing + sección
- [ ] 7. Refusal path - detectar y responder correctamente cuando ningún chunk recuperado soporta una respuesta
- [ ] 8. CLI interface - hacer una pregunta desde terminal y ver la respuesta con sus citas
- [ ] 9. Tests deterministas - cobertura pytest para las funciones de ingesta, chunking y retrieval
- [ ] 10. Eval set - escribir 20-50 pares pregunta/respuesta etiquetados a mano con cita esperada
- [ ] 11. Eval runner - script que corre el eval set y puntúa corrección de citas y relevancia de respuesta
- [ ] 12. Logging - logs estructurados por query (fuentes, latencia, tokens, costo) a archivo local
- [ ] 13. README - problema, usuario, setup, comandos de run/test/eval, y trade-offs documentados

## Post-MVP
- [ ] 14. Comparación de cambios de riesgo entre trimestres (quarter-over-quarter)
- [ ] 15. Endpoint FastAPI HTTP envolviendo la lógica del CLI
- [ ] 16. UI mínima de demo en Streamlit
- [ ] 17. Docker + deploy básico
