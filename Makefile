.PHONY: demo test e2e eval resolve check-env build-gateway

check-env:
	python3 scripts/check_env.py

build-gateway:
	cd src/gateway && go build ./...

demo: build-gateway
	docker compose up -d
	python3 scripts/bootstrap.py
	python3 src/data_gen.py --reports 15 --out data
	VECTOR_BACKEND=chroma python3 src/index_docs.py --in data/reports

test: build-gateway
	pytest tests/ -v --ignore=tests/test_e2e.py

e2e: build-gateway
	pytest tests/test_e2e.py -v -s

eval:
	VECTOR_BACKEND=chroma LLM_PROVIDER=minimax python3 src/eval.py

resolve:
	python3 src/resolve.py

query:
	python3 -c "import sys; sys.path.insert(0,'src'); from common import warehouse; \
	con = warehouse.connect(); \
	warehouse.read_parquet(con, 's3://geo-extracted/occurrences/**/*.parquet', 'occurrences'); \
	print(con.execute(open('sql/occurrences_by_region.sql').read()).fetchall())"
