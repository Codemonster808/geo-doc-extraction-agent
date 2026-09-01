# ADR 0001 — Retry gateado por validación vs ciego vs single-shot

## Contexto

El LLM a veces omite lat/lon. Reintentar siempre gasta budget; no
reintentar deja huecos.

## Decisión

Hasta `MAX_ITERATIONS=2`, solo si `ExtractedRecord` falla validación.
Prompt más constricted en el retry.

## Alternativas consideradas

- **Blind N retries**: costo y no mejora un mineral inventado.
- **Single-shot**: pierde el caso "faltó la frase de coordenadas"
  (`RETRIEVAL_TOP_K` subió de 3 a 4 por eso).

## Consecuencias

`status=failed` explícito. Test
`test_confidence_gate_fails_gracefully_not_silently`.
