.PHONY: demo test eval check-env build-gateway

check-env:
	python3 scripts/check_env.py

build-gateway:
	cd src/gateway && go build ./...

demo: build-gateway
	docker compose up -d
	python3 scripts/bootstrap.py
	python3 src/data_gen.py --reports 15 --out data

test: build-gateway
	pytest tests/ -v

eval:
	LLM_PROVIDER=minimax python3 src/eval.py
