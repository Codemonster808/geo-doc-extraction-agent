# Data dictionary — geo-doc-extraction-agent

| Resource | Key / grain | Lineage |
|---|---|---|
| `geo-doc-dedup` | `content_hash` SHA-256 | gateway PutItem |
| `s3://geo-docs/` | object per accepted upload | gateway |
| `geo-extraction-attempts` | report_id + attempt | `extraction_agent` / `check_attempt` Lambda |
| `geo-extractions` | validated `ExtractedRecord` | success path only |
| `s3://geo-extracted/occurrences/` | resolved site | `resolve.py` |
| Chroma/Pinecone `geo_reports` | chunks | `index_docs.py` |

`ExtractedRecord`: `mineral`, `depth_m`, `lat`, `lon`, `grade_g_t`, `hole_id`.
