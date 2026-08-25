SHELL := /bin/bash
.PHONY: demo demo-full test e2e eval resolve check-env build-gateway inspect query

ENV := set -a && source ./env.sh --quiet && set +a

DEMO_REPORTS ?= 15
DEMO_FULL_REPORTS ?= 15

check-env:
	$(ENV) && python3 scripts/check_env.py

inspect:
	$(ENV) && python3 scripts/aws_inspect.py all

build-gateway:
	cd src/gateway && go build ./...

demo: build-gateway
	$(ENV) && docker compose up -d
	$(ENV) && python3 scripts/bootstrap.py
	$(ENV) && python3 src/data_gen.py --reports $(DEMO_REPORTS) --out data
	$(ENV) && VECTOR_BACKEND=chroma python3 src/index_docs.py --in data/reports
	$(ENV) && python3 src/statemachine.py

demo-full:
	$(MAKE) demo DEMO_REPORTS=$(DEMO_FULL_REPORTS)

test: build-gateway
	$(ENV) && pytest tests/ -v --ignore=tests/test_e2e.py

e2e: build-gateway
	$(ENV) && pytest tests/test_e2e.py -v -s

eval:
	$(ENV) && VECTOR_BACKEND=chroma LLM_PROVIDER=minimax python3 src/eval.py

resolve:
	$(ENV) && python3 src/resolve.py

query:
	$(ENV) && python3 -c "import sys; sys.path.insert(0,'src'); from common import warehouse; \
	con = warehouse.connect(); \
	warehouse.read_parquet(con, 's3://geo-extracted/occurrences/**/*.parquet', 'occurrences'); \
	print(con.execute(open('sql/occurrences_by_region.sql').read()).fetchall())"
