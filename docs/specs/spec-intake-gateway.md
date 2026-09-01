# Spec: intake gateway

## Objetivo de negocio

No pagar OCR/embedding por un duplicado o un texto basura.

## Fuentes de entrada

`POST` JSON `{report_id, text}` al gateway Go (`src/ingestion/gateway`).

## Transformaciones

Texto menor a 20 chars → 400. SHA-256 del texto → `PutItem` condicional en
`geo-doc-dedup`. Nuevo → 200 + objeto en `s3://geo-docs/`. Hash ya visto → 409.

## Salida esperada

200 / 409 / 400. Duplicado de contenido con otro `report_id` sigue 409.

## Criterios de aceptación

`features/intake-gateway.feature`.
