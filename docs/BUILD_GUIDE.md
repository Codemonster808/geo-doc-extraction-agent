# Build Guide — geo-doc-extraction-agent

This repo reuses patterns from `agentic-claims-copilot` (Step Functions agent loop) and `fintech-txn-integrity-pipeline` (Go gateway) — build those two first if possible; this guide assumes that familiarity but repeats every step so it stands alone. Estimated total: ~20 hours across 2 weeks of evenings (cheaper than the others because of the reuse).

## Glossary

- **OCR**: turning a scanned/image PDF into machine-readable text.
- **CRS (Coordinate Reference System)**: the standard defining how a latitude/longitude pair maps to a real location on Earth — different reports may use different ones.
- **Confidence-gated retry**: only retry when the system's own confidence score says the first attempt was weak, instead of always retrying or never retrying.
- **Entity resolution**: recognizing that two mentions ("Cu occurrence at site A" in two different reports) refer to the same real-world thing.

## 0. Before you start (20 min)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
go version   # 1.21+
cp ~/.config/de-portfolio/.env .env   # MINIMAX_API_KEY, PINECONE_API_KEY
docker compose up -d
curl http://localhost:4566/_health
```

## 1. Get the environment running (45 min) → checkpoint: `make check-env`

```bash
docker compose up -d
python3 scripts/bootstrap.py
make check-env
```

## 2. Generate synthetic data + labels (2-3 h) → checkpoint: `make check-data`

Write 15 synthetic geological report "documents" (plain text is fine, no need for real scanned PDFs) containing embedded facts like "Drill hole DH-14 intersected 2.1 g/t Au at 145m depth, coordinates -23.45, -68.90." Hand-label the ground truth fields for each (`mineral`, `depth_m`, `lat`, `lon`, `grade`) in a JSON file.

```bash
python3 src/data_gen.py --reports 15 --out data/
make check-data   # "OK: 15 reports, 15 label sets, all fields present"
```

## 3. Build the Go intake gateway (2-3 h) → checkpoint: `make check-gateway`

```bash
cd src/gateway && go build ./...
make check-gateway   # asserts duplicate content is rejected, malformed uploads are rejected
```

## 4. Build OCR/parse + chunking + embedding (3 h) → checkpoint: `make check-embed`

```bash
make check-embed   # asserts each doc produces >0 chunks and all chunks are embedded
```

## 5. Build the extraction agent (5-6 h) → checkpoint: `make check-extract`

Reuse the Step Functions `Plan → Tool → Observe → Choice` pattern from `agentic-claims-copilot`, but the "Tool" step here extracts structured fields (not just retrieves text) and "Observe" checks confidence against the domain schema, not evidence sufficiency.

```bash
make check-extract   # runs all 15 docs, compares to labels, prints precision/recall
```

## 6. Build domain schema validation (2 h) → checkpoint: `pytest tests/test_schema_conformance.py`

Write the Pydantic model: mineral must be from a known list, `depth_m` must be positive and under a plausible max, lat/lon must fall within the survey region's real bounding box.

```bash
pytest tests/test_schema_conformance.py   # inject an out-of-bounds coordinate, confirm it's rejected
```

## 7. Build cross-document resolution + serving (3 h) → checkpoint: `make check-resolve`

```bash
make check-resolve   # asserts the same occurrence mentioned in two docs resolves to one record
```

## 8. Measure, model, ship (2-3 h)

```bash
make eval   # writes field-level precision/recall to docs/eval-report.md
make bench
```

Fill `docs/impact-model.md` and both README metric tables.

## Troubleshooting index

| Symptom | Likely cause | Fix |
|---|---|---|
| Precision looks great but recall is low | confidence threshold too strict, valid extractions being discarded | loosen threshold, re-run `make eval`, compare |
| Coordinates pass validation but are clearly wrong | bounding box too loose for your synthetic region | tighten to the actual synthetic survey area |

## Total estimated effort: ~20 hours (2 weeks of evenings)
