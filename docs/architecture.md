# Architecture

```mermaid
flowchart LR
    DOC[Synthetic geological reports] --> GATE[Go/Gin intake gateway\nvalidate, rate-limit, dedupe]
    GATE --> S3[(S3)]
    S3 --> OCR[Lambda: OCR/parse + chunk]
    OCR --> VEC[(Pinecone / Chroma)]
    SF[Step Functions extraction agent] --> PLAN[Plan]
    PLAN --> EXTRACT[Extract: mineral, depth, lat/lon, grade]
    EXTRACT --> VALIDATE[Validate: Pydantic schema\nunits + CRS bounds]
    VALIDATE -->|confidence high| DDB[(DynamoDB\nstructured records)]
    VALIDATE -->|confidence low, retry| PLAN
    VEC --> EXTRACT
    RESOLVE[PySpark: cross-doc entity resolution] --> DDB
    RESOLVE --> S3PARQUET[(S3 Parquet)]
    S3PARQUET --> RS[(Redshift)]
    RS --> API[FastAPI: /search /extract/id]
```

## Data flow notes

- The intake gateway is the only synchronous hop before expensive OCR/embedding work — its job is to reject junk cheaply.
- `Validate` enforces the domain schema (units, coordinate bounds) independently of the confidence score — a record can have high extraction confidence and still fail validation if, say, a coordinate falls outside plausible bounds.
- Entity resolution across documents (the same mineral occurrence reported in two different surveys) happens only in the batch PySpark step, not per-document.
