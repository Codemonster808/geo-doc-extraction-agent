# ADR 0002 — Validación de dominio vs solo-tipo

## Contexto

float lat/lon válidos pueden ser NYC. Un schema "types only" lo acepta.

## Decisión

Bounds CRS + profundidad + whitelist de minerales en Pydantic.

## Alternativas consideradas

- **JSON Schema tipos**: no captura "fuera del survey".
- **Post-check en Spark**: el record ya habría aterrizado en DDB.

## Consecuencias

NYC y 50 km de profundidad fallan aunque parseen. Bounds un poco más
anchos que el generador para slack del validador.
