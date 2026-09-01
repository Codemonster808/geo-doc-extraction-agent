import hashlib
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest
import requests
from pytest_bdd import given, parsers, scenarios, then, when

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

scenarios("../intake-gateway.feature")

REPO_ROOT = Path(__file__).resolve().parents[2]
GATEWAY_URL = f"http://localhost:{os.environ.get('GATEWAY_PORT', '8081')}"
GATEWAY_BIN = REPO_ROOT / "src" / "ingestion" / "gateway" / "gateway"


@pytest.fixture(scope="module", autouse=True)
def gateway_process():
    """Starts the real Go intake gateway binary for these steps, the same
    way tests/data_quality/test_e2e.py does it — forward the full
    environment so the subprocess inherits AWS_ENDPOINT_URL/AWS_REGION/
    credentials from env.sh instead of falling back to its hardcoded
    localhost:4566 default.
    """
    if not GATEWAY_BIN.exists():
        pytest.skip("gateway binary not built — run `cd src/ingestion/gateway && go build ./...` first")
    proc = subprocess.Popen([str(GATEWAY_BIN)], env={**os.environ, "GIN_MODE": "release"})
    for _ in range(20):
        try:
            if requests.get(f"{GATEWAY_URL}/health", timeout=1).status_code == 200:
                break
        except requests.ConnectionError:
            time.sleep(0.25)
    else:
        proc.terminate()
        pytest.fail("gateway did not become healthy in time")
    yield proc
    proc.terminate()
    proc.wait(timeout=5)


@pytest.fixture
def ctx():
    return {}


@given(
    parsers.parse("a report with id {report_id} and unique text long enough to be a real report"),
)
def unique_report(ctx, report_id):
    run_id = uuid.uuid4().hex[:8]
    ctx["report_id"] = report_id
    ctx["text"] = f"Intake gateway BDD test report {run_id}: geological survey narrative content."


@given(parsers.parse('a report with id {report_id} and text "{text}"'))
def literal_report(ctx, report_id, text):
    ctx["report_id"] = report_id
    ctx["text"] = text


@given("the document has already been uploaded once")
def upload_once(ctx):
    resp = requests.post(
        f"{GATEWAY_URL}/upload", json={"report_id": ctx["report_id"], "text": ctx["text"]}
    )
    assert resp.status_code == 200, f"seed upload failed: {resp.status_code} {resp.text}"


@when("the document is uploaded to the intake gateway")
def upload(ctx):
    ctx["response"] = requests.post(
        f"{GATEWAY_URL}/upload", json={"report_id": ctx["report_id"], "text": ctx["text"]}
    )


@when(parsers.parse("the same content is uploaded again with report id {report_id}"))
def upload_duplicate(ctx, report_id):
    ctx["response"] = requests.post(
        f"{GATEWAY_URL}/upload", json={"report_id": report_id, "text": ctx["text"]}
    )


@then("the gateway responds 200 accepted")
def assert_accepted(ctx):
    resp = ctx["response"]
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "accepted"


@then("the gateway responds 409 duplicate")
def assert_duplicate(ctx):
    resp = ctx["response"]
    assert resp.status_code == 409, resp.text
    assert resp.json()["status"] == "duplicate"


@then("the response includes the content_hash")
def assert_content_hash(ctx):
    body = ctx["response"].json()
    assert "content_hash" in body
    assert body["content_hash"] == hashlib.sha256(ctx["text"].encode()).hexdigest()


@then("the gateway responds 400 rejected")
def assert_rejected(ctx):
    resp = ctx["response"]
    assert resp.status_code == 400, resp.text
