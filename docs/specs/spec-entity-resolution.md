# Spec: entity resolution

## Objetivo de negocio

El mismo yacimiento en dos surveys no debe contar dos veces.

## Fuentes de entrada

`geo-extractions` (DynamoDB).

## Transformaciones

`resolve.py`: clave `(mineral, round(lat, 2), round(lon, 2))` (~1 km).
Parquet `s3://geo-extracted/occurrences/`.

## Salida esperada

Una occurrence por sitio. SQL `sql/occurrences_by_region.sql`.

## Criterios de aceptación

e2e / `make resolve`.
