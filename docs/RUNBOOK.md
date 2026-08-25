# Runbook — aprender extracción + RAG (P5)

Complementa `docs/BUILD_GUIDE.md`. Escala (15 reportes) ya es aprendible; `make demo` y `make demo-full` son el mismo tamaño.

Usa `LLM_PROVIDER=fake` para iterar gratis. `make eval` con MiniMax cuesta centavos y genera las métricas del README.

---

## 0. Setup por terminal

```bash
cd /home/lesaint/Documentos/life_plans/geo-doc-extraction-agent
source env.sh
docker compose up -d
make check-env
python3 scripts/bootstrap.py
cd src/gateway && go build ./... && cd ../..
python3 src/statemachine.py    # gate de intentos vía Step Functions
python3 scripts/aws_inspect.py all
```

---

## 1. Flujo paso a paso

### 1.1 Reportes sintéticos + ground truth

```bash
python3 src/data_gen.py --reports 15 --out data --seed 42
ls data/reports
python3 -c "import json; print(json.load(open('data/_ground_truth.json'))[0]['ground_truth'])"
```

Cada `.txt` tiene mineral, depth, lat/lon, grade, hole_id embebidos. El JSON es la etiqueta para eval.

### 1.2 Indexar chunks (RAG scoped por documento)

```bash
VECTOR_BACKEND=chroma python3 src/index_docs.py --in data/reports
```

**Qué entender:** retrieval **sin** `where=report_id` mezclaba 15 reportes casi idénticos y perdía las coordenadas. El bug está documentado en `common/vectors.py`.

### 1.3 Extraer un reporte y persistir

```bash
python3 - <<'PY'
import json, sys
sys.path.insert(0, "src")
from extraction_agent import extract_with_confidence_gate
reports = json.load(open("data/_ground_truth.json"))
r = reports[0]
print(extract_with_confidence_gate(r["report_id"], r["text"]))
PY
python3 scripts/aws_inspect.py ddb
python3 scripts/aws_inspect.py sfn
```

**Qué inspeccionar:** `geo-extractions` tiene el record validado; `geo-extraction-attempts` cuenta reintentos; Step Functions `geo-extraction-gate` tiene executions Succeeded.

### 1.4 Resolver entidades cross-doc + eval

```bash
python3 src/resolve.py
LLM_PROVIDER=fake VECTOR_BACKEND=chroma python3 src/eval.py --data data
```

---

## 2. Explorar con AWS CLI

`aws` respeta `AWS_ENDPOINT_URL` (exportado por `env.sh`), sin flags extra. P5 no usa SNS/SQS — el intake pasa por el gateway Go (`src/gateway`) directo a S3, y el gate de reintentos vive en Step Functions + Lambda.

```bash
# S3 — solo se llena si pasaste por el gateway Go (curl al intake), no en el flujo directo de Python de la sección 1
aws s3 ls s3://geo-docs/ --recursive
aws s3 ls s3://geo-extracted/ --recursive

# DynamoDB — el record validado y el contador de intentos
aws dynamodb scan --table-name geo-extractions --max-items 3
aws dynamodb scan --table-name geo-extraction-attempts --max-items 5

# Lambda — la función que evalúa el gate de confianza dentro del loop
aws lambda get-function --function-name geo-check-attempt --query 'Configuration.[State,Runtime,LastModified]'

# Step Functions — cuántos intentos tomó llegar a un extract válido
SM_ARN=$(aws stepfunctions list-state-machines --query "stateMachines[0].stateMachineArn" --output text)
EXEC_ARN=$(aws stepfunctions list-executions --state-machine-arn "$SM_ARN" --max-results 1 --query "executions[0].executionArn" --output text)
aws stepfunctions get-execution-history --execution-arn "$EXEC_ARN"
```

**Qué mirar que `aws_inspect.py` no te muestra:** cuántas veces se repite el ciclo `TaskStateEntered`/`ChoiceStateEntered` en `get-execution-history` antes del `ExecutionSucceeded` final — ese conteo es el número real de reintentos del confidence gate, no solo el campo `iterations` que devuelve la función Python.

---

## 3. Romper a propósito

### Extraer sin indexar

En un clone limpio de chroma (borra `.chroma/`):

```bash
rm -rf .chroma
python3 - <<'PY'
import json, sys
sys.path.insert(0, "src")
from extraction_agent import extract_with_confidence_gate
r = json.load(open("data/_ground_truth.json"))[0]
print(extract_with_confidence_gate(r["report_id"], r["text"]))
PY
```

Debe **degradar** al texto completo (`fallback_text`), no crashear. Eso es el diseño.

### Schema fuera de bounds

El validador Pydantic rechaza lat/lon fuera del bounding box de la encuesta. Un extracto alucinado con lat=40 falla y reintenta (hint en el prompt) hasta el tope de intentos.

---

## 4. Errores

| Error | Significado |
|---|---|
| `ResourceNotFoundException` en DDB | Falta bootstrap **o** env.sh. Histórico: la tabla se creó con PK `doc_id` y el código usaba `report_id`. |
| Retrieval vacío | No corriste `index_docs.py` o `VECTOR_BACKEND` distinto entre index y extract |
| MiniMax `<think>` en JSON | Ya se limpia en `common/llm/minimax.py`; si parsea mal, estás en un proveedor viejo |
| IDs fijos en DDB | Contadores persisten entre corridas — usa report_ids nuevos o `uuid` |
| S3 vacío pese a `make demo` | Normal si no pasaste por el gateway Go — el flujo de la sección 1 llama `extraction_agent` directo en Python |

---

## 5. Ejercicios

**1. Cuenta los reintentos reales del confidence gate con el CLI, no con el campo `attempts`**

Extrae un reporte con `.chroma/` borrado (sección 3, fuerza reintentos por confianza baja), luego cuenta ejecuciones con `aws stepfunctions list-executions --state-machine-arn $SM_ARN` — **no** mires `get-execution-history` de una sola ejecución, cada reintento es una ejecución nueva, no una tarea dentro de la misma.

<details><summary>Verificar</summary>

El número de ejecuciones (`SUCCEEDED`) para esa máquina coincide con `attempts` en `geo-extraction-attempts` de DynamoDB para ese `report_id` — el loop en `extraction_agent.py` no reintenta *dentro* de una ejecución de Step Functions, dispara una ejecución nueva por cada vuelta del loop Python. Es una distinción real: "Step Functions controla el flujo" no siempre significa "todo el loop vive dentro de una sola ejecución".
</details>

**2. Verifica con `aws dynamodb scan` que el schema rechaza coordenadas fuera de rango, no solo que el test pasa**

Corre `pytest tests/test_extraction.py::test_coordinate_outside_survey_region_rejected -v`, luego revisa si ese record llegó a `geo-extractions`.

<details><summary>Verificar</summary>

El record con lat/lon fuera del bounding box **no** aparece en `geo-extractions` — el validador Pydantic lo bloqueó antes de persistir. Comparado con `geo-extraction-attempts`, donde sí verás el intento fallido registrado. La distinción entre las dos tablas es el punto: un intento se registra siempre, un record solo se persiste si pasa el schema.
</details>

**3. Lee el estado real de la función Lambda antes vs. después de `statemachine.py`**

`aws lambda get-function --function-name geo-check-attempt` **antes** de correr `python3 src/statemachine.py`, y otra vez después.

<details><summary>Verificar</summary>

Antes: `ResourceNotFoundException` (no existe). Después: `State=Active`, con un `LastModified` de hace segundos. Es la misma distinción que hace `aws_inspect.py` con el mensaje "not deployed yet", pero viendo el código de error real (`ResourceNotFoundException`) en vez del texto ya traducido por el script.
</details>

---

## 6. Quality report

```bash
make e2e
cat docs/quality-report.md
```

---

## 7. Cerrar

```bash
docker compose down
```
