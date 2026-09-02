# CLAUDE.md — geo-doc-extraction-agent

Operative constitution for working in this repo. Not general documentation —
that's `README.md` (pitch card), `docs/architecture.md`, `docs/RUNBOOK.md`.
This file is what an agent (or a new engineer) needs to *act* correctly here
without re-deriving it from the code first.

## 1. Domain context

This repo extracts structured facts (mineral, depth, coordinates, assay
grade, drill-hole id) from geological survey report text, validates them
against a domain schema, and resolves the same real-world occurrence
reported across multiple documents into one row.

"Correct data" here means, concretely:

- An `ExtractedRecord` either satisfies **every** domain constraint (known
  mineral, plausible depth, coordinates inside the survey region) or it does
  not exist — there is no partially-valid record. A record that
  type-checks but places a mine in the Atlantic (or in New York) is a bug,
  not a pass. See `src/models/extraction_agent.py::ExtractedRecord`.
- A document is identified by the SHA-256 hash of its raw text
  (`src/ingestion/gateway/main.go`). Re-uploading identical content under a
  **different** `report_id` is still a duplicate and gets `409`, not a new
  row in `geo-doc-dedup` or a new object in `s3://geo-docs/`.
- An extraction attempt is always recorded in `geo-extraction-attempts`
  (the retry counter), whether it succeeds or not. A validated record only
  ever lands in `geo-extractions` on success — never as a side effect of a
  failed attempt.
- When retries are exhausted, the pipeline returns
  `{"status": "failed", "reason": ..., "attempts": N}` explicitly. It never
  silently drops the report or returns a record that only *happened* to
  parse.
- Two occurrences resolve to the same site when `(mineral, round(lat, 2),
  round(lon, 2))` match (`src/transformation/resolve.py`) — a deliberate
  ~1km-ish tolerance, not floating-point equality.

## 2. Exact commands

Every recipe runs under `set -a && source ./env.sh --quiet && set +a` —
this loads `.env.example` → `.env` → `~/.config/de-portfolio/.env` in that
order and exports AWS/LLM/vector defaults. Don't hand-roll env exports in a
new Makefile target; reuse `$(ENV)`.

```bash
make check-env      # curl $AWS_ENDPOINT_URL/health, fail fast if MiniStack is down
make inspect         # scripts/aws_inspect.py all — dump S3/DDB/Lambda/SFN state
make build-gateway    # cd src/ingestion/gateway && go build ./...
make demo             # build-gateway, docker compose up, bootstrap, data_gen,
                       # index_docs, deploy the statemachine (DEMO_REPORTS=15 default)
make demo-full        # demo with DEMO_FULL_REPORTS
make test             # build-gateway, pytest tests/ --ignore=tests/data_quality
make e2e              # build-gateway, pytest tests/data_quality/test_e2e.py -v -s
make eval             # VECTOR_BACKEND=chroma LLM_PROVIDER=minimax scripts/eval.py
                       # — COSTS MONEY, see §5
make resolve          # src/transformation/resolve.py — cross-doc entity resolution
make query            # ad-hoc DuckDB query over s3://geo-extracted/occurrences/
```

Bring the stack up/down directly with `docker compose up -d` /
`docker compose down`. MiniStack's default host port is `4585` in this repo
(see `docker-compose.yml` / `env.sh`) — several sibling portfolio repos run
their own MiniStack concurrently on other ports, so don't assume `4566` and
don't hardcode a port anywhere new; always read `AWS_ENDPOINT_URL`.

Dependencies: `requirements.in` (direct runtime deps) and `requirements-dev.in`
(lint/type/security tooling, constrained against `requirements.txt` so the two
never disagree) are the source of truth — never hand-edit `requirements.txt`
or `requirements-dev.txt`, they're generated:
```bash
.venv/bin/pip-compile requirements.in --output-file requirements.txt
.venv/bin/pip-compile requirements-dev.in --output-file requirements-dev.txt
```
This is also what makes Dependabot's pip PRs resolvable instead of hand-editing
one pinned line into a conflict with another.

## 3. Naming conventions

- **S3 buckets**: `geo-docs` (raw uploaded report text), `geo-extracted`
  (resolved occurrences Parquet, written by `resolve.py`).
- **DynamoDB tables**: `geo-doc-dedup` (PK `content_hash`, dedup gate before
  OCR/embedding), `geo-extractions` (PK `report_id`, validated records
  only), `geo-extraction-attempts` (PK `report_id`, atomic `ADD attempts`
  counter, incremented once per confidence-gate attempt regardless of
  outcome).
- **Lambda**: `geo-check-attempt` (handler in
  `src/orchestration/lambdas/check_attempt.py`). Its endpoint
  (`http://127.0.0.1:4566`) is hardcoded intentionally — it runs *inside*
  MiniStack's own container network, where the internal port is always
  `4566` regardless of the host-side port mapping. Don't "fix" this to
  match `AWS_ENDPOINT_URL`.
- **Step Functions**: `geo-extraction-gate`, defined in
  `asl/extraction_gate.json`, driven from
  `src/orchestration/statemachine.py::gate_attempt()`.
- **Vector collection**: `geo_reports` (Chroma/Pinecone, scoped queries via
  `where={"report_id": ...}` — see the docstring in
  `src/utils/vectors.py` for the retrieval bug this scoping fixes).
- **Commits**: short imperative present-tense sentences (`Add real RAG...`,
  `Close a remaining gap: ...`), no enforced prefix convention. Look at
  `git log --oneline` before adding a commit if consistency matters.

## 4. Schema and data rules

- `ExtractedRecord` (`src/models/extraction_agent.py`) is the only gate
  that matters for `geo-extractions`. Its Pydantic validators enforce:
  - `mineral` ∈ `VALID_MINERALS` = `{Copper, Gold, Silver, Zinc, Lithium,
    Nickel}`
  - `0 < depth_m <= MAX_DEPTH_M` (`MAX_DEPTH_M = 1000`)
  - `LAT_BOUNDS = (-30.0, -15.0)`, `LON_BOUNDS = (-75.0, -60.0)` — wider
    than the synthetic generator's own range (`LAT_RANGE = (-25.0,
    -20.0)`, `LON_RANGE = (-70.0, -66.0)` in
    `src/ingestion/data_gen.py`) to leave validator slack, but still a
    real bounding box, not `-90..90`/`-180..180`. A syntactically valid
    coordinate outside this box (e.g. New York, lat 40.7 lon −74.0) must
    be rejected — this is asserted directly in
    `tests/unit/test_extraction.py::test_coordinate_outside_survey_region_rejected`.
- `extract_with_confidence_gate()` retries at most `MAX_ITERATIONS = 2`
  times, gated by a real Step Functions execution per attempt (not a bare
  Python loop). Each failed attempt is fed back into the next prompt as a
  hint. After `MAX_ITERATIONS`, it returns `status=failed` with a reason —
  never a record that slipped through.
- Intake dedup happens in the Go gateway (`POST /upload`), by content hash,
  **before** anything expensive (OCR/embedding/LLM) runs. A conditional
  `PutItem` on `geo-doc-dedup` is the atomicity primitive — don't replace it
  with a read-then-write check.
- If you change `VALID_MINERALS`, the bounds, or `MAX_ITERATIONS`, update
  `docs/specs/spec-confidence-gated-extraction.md` and the matching
  `features/extraction-validation.feature` scenarios in the same change —
  they assert these exact constants.

## 5. What NOT to touch without confirming first

- `.env` — never commit it (it's gitignored; `.env.example` is the
  template).
- `LLM_PROVIDER=minimax` — **costs real money** per call (MiniMax M3 API).
  The default everywhere that matters (`env.sh`, tests, CI, `make demo`) is
  `LLM_PROVIDER=fake`. Only `make eval` explicitly opts into `minimax`
  because it's measuring real field-level precision for the README. Don't
  flip the default, and don't add a new code path that silently calls the
  real provider.
- `VECTOR_BACKEND=pinecone` — also costs money / needs a real API key. The
  default is `chroma` (local, free). Same rule: don't flip the default.
- `scripts/secrets_setup.py` — seeds Secrets Manager from your live env
  vars. Safe to run (it's a no-op if the vars aren't set), but don't call
  it from a script or test that runs unattended in CI.
- Deleting S3 buckets or DynamoDB tables directly (`aws s3 rb`, `aws
  dynamodb delete-table`) — `scripts/bootstrap.py` is idempotent
  create-only; there's no corresponding teardown script, so don't improvise
  one against a shared/demo stack without asking.
- Ports: don't hardcode `4566` anywhere new, and don't change
  `docker-compose.yml`/`env.sh` back to `4566` as the default — this repo's
  MiniStack runs on `4585` so it can run alongside sibling repos' own
  stacks.

## 6. Where specs and features live

Read these **before** implementing or changing behavior — they're the
source of truth for "what is this pipeline supposed to do," not the code
you happen to be looking at:

- `docs/specs/` — one spec per pipeline/feature: objective, inputs,
  transformations, expected output (schema/grain/SLA), edge cases,
  acceptance criteria (each linked to a BDD scenario).
- `docs/adr/` — why a design was chosen and what was explicitly rejected
  (confidence-gated retry vs. blind retry, domain validation vs.
  type-only validation, Go gateway dedup-before-OCR).
- `features/*.feature` + `features/steps/*.py` — executable `pytest-bdd`
  scenarios, run as part of `make test`/`make e2e`/CI, not decorative.
- `docs/data-dictionary.md` — every table/dataset, its columns, grain, and
  which file produces it.

No `notebooks/` or `dbt/` directory exists in this repo, and none should be
added just to look complete — there's no exploratory notebook work or dbt
usage here. If one genuinely appears later: notebooks never feed the
production pipeline directly: promote anything that needs to run
repeatably into `src/` first.

## 7. PII and synthetic data

All data in this repo is synthetic and deterministic: `src/ingestion/data_gen.py
--seed 42` (default) always produces the same 15 reports and ground truth.
Do not introduce real report data, real coordinates, or any real-world PII.
Do not log full LLM payloads or full report text at INFO level or above —
log identifiers (`report_id`, `content_hash`) and outcomes, not content.
