# Spec: confidence-gated extraction

## Objetivo de negocio

Un JSON que type-checkea pero pone la mina en Nueva York no es un
registro. Retry solo cuando la validación de dominio falla, no a ciegas.

## Fuentes de entrada

Texto del report (RAG `RETRIEVAL_TOP_K=4`). LLM fake o MiniMax.

## Transformaciones

`ExtractedRecord` Pydantic: mineral en whitelist, `depth_m` in (0, 1000],
lat ∈ [-30, -15], lon ∈ [-75, -60]. `MAX_ITERATIONS=2`. Agotar →
`status=failed` con reason, nunca un record a medias. Intentos siempre
en `geo-extraction-attempts`.

## Salida esperada

Éxito → `geo-extractions`. Fallo → failed payload, no fila de extracción.

## Casos borde

lat 40.7 / lon -74.0 rechazado. depth 50000 rechazado. mineral `Helium`
rechazado.

## Criterios de aceptación

`features/extraction-validation.feature`, `tests/unit/test_extraction.py`.
