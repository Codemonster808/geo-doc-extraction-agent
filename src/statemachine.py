#!/usr/bin/env python3
"""
Deploys the attempt-gate Lambda + Step Functions state machine, and
provides gate_attempt() — called once per confidence-gate retry in
extraction_agent.py to get a real Step-Functions-mediated decision
(Choice + Retry + Catch) instead of a bare Python for-loop counter.
"""
import json
import sys
import time
import zipfile
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import aws  # noqa: E402

LAMBDAS_DIR = Path(__file__).resolve().parent / "lambdas"
ASL_DIR = Path(__file__).resolve().parents[1] / "asl"
ROLE_ARN = "arn:aws:iam::000000000000:role/dummy-role"

FUNCTION_NAME = "geo-check-attempt"
FUNCTION_FILE = "check_attempt.py"
STATE_MACHINE_NAME = "geo-extraction-gate"
ASL_FILE = "extraction_gate.json"


def _zip_handler() -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.write(LAMBDAS_DIR / FUNCTION_FILE, arcname=FUNCTION_FILE)
    return buf.getvalue()


def _wait_active(lam, timeout_s: float = 20) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if lam.get_function(FunctionName=FUNCTION_NAME)["Configuration"]["State"] == "Active":
            return
        time.sleep(0.5)
    raise TimeoutError(f"Lambda {FUNCTION_NAME} did not become Active in time")


def deploy() -> str:
    lam = aws.client("lambda")
    sfn = aws.client("stepfunctions")

    zip_bytes = _zip_handler()
    existing = {f["FunctionName"] for f in lam.list_functions().get("Functions", [])}
    if FUNCTION_NAME in existing:
        lam.update_function_code(FunctionName=FUNCTION_NAME, ZipFile=zip_bytes)
    else:
        lam.create_function(FunctionName=FUNCTION_NAME, Runtime="python3.12", Role=ROLE_ARN,
                             Handler="check_attempt.handler", Code={"ZipFile": zip_bytes})
    _wait_active(lam)

    definition = (ASL_DIR / ASL_FILE).read_text()
    existing_sms = {sm["name"]: sm["stateMachineArn"] for sm in sfn.list_state_machines()["stateMachines"]}
    if STATE_MACHINE_NAME in existing_sms:
        sfn.update_state_machine(stateMachineArn=existing_sms[STATE_MACHINE_NAME], definition=definition)
        return existing_sms[STATE_MACHINE_NAME]
    resp = sfn.create_state_machine(name=STATE_MACHINE_NAME, definition=definition, roleArn=ROLE_ARN)
    return resp["stateMachineArn"]


_arn_cache: str | None = None


def gate_attempt(report_id: str, max_attempts: int, timeout_s: float = 15) -> dict:
    global _arn_cache
    if _arn_cache is None:
        _arn_cache = deploy()

    sfn = aws.client("stepfunctions")
    exec_resp = sfn.start_execution(
        stateMachineArn=_arn_cache,
        input=json.dumps({"report_id": report_id, "max_attempts": max_attempts}),
    )
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        desc = sfn.describe_execution(executionArn=exec_resp["executionArn"])
        if desc["status"] != "RUNNING":
            break
        time.sleep(0.3)
    else:
        raise TimeoutError("attempt gate execution did not finish in time")

    if desc["status"] != "SUCCEEDED":
        raise RuntimeError(f"attempt gate execution failed: {desc}")

    output = json.loads(desc.get("output", "{}"))
    return {"allowed": bool(output.get("allowed", False)), "attempts": output.get("attempts", max_attempts + 1)}


if __name__ == "__main__":
    arn = deploy()
    print(f"deployed state machine: {arn}")
