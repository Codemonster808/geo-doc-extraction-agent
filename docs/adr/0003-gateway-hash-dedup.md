# ADR 0003 — Gateway Go y dedup por hash antes del RAG

## Contexto

Embedding/OCR es el costo. Dedup al final del pipeline ya gastó.

## Decisión

Go/Gin: SHA-256 del texto, conditional Put en `geo-doc-dedup`, 409 barato.

## Alternativas consideradas

- **Dedup en PySpark**: tarde. Hash de `report_id` no detecta re-upload
  de contenido.

## Consecuencias

Frontera políglota acotada (honesty note). Endpoint AWS del binario es
`AWS_ENDPOINT_URL` (host); Lambdas internas siguen en :4566.
