"""
End-to-end quality test: Go intake gateway (real dedup) -> extraction
persistence -> cross-document entity resolution, scored on the 5
standard quality dimensions. Uses LLM_PROVIDER=fake for the extraction
mechanics (graceful-failure path) — real field precision is measured
separately via `make eval` with LLM_PROVIDER=minimax (see docs/eval-report.json).
"""
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from common import aws  # noqa: E402
from common.quality import Dimension, QualityReport  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
GATEWAY_URL = "http://localhost:8081"
GATEWAY_BIN = REPO_ROOT / "src" / "gateway" / "gateway"


@pytest.fixture(scope="module")
def gateway_process():
    if not GATEWAY_BIN.exists():
        pytest.skip(f"gateway binary not built — run `cd src/gateway && go build ./...` first")
    proc = subprocess.Popen([str(GATEWAY_BIN)], env={"GIN_MODE": "release"})
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


def _seed_extraction(ddb, report_id: str, mineral: str, lat: float, lon: float) -> None:
    ddb.put_item(TableName="geo-extractions", Item={
        "report_id": {"S": report_id},
        "mineral": {"S": mineral},
        "depth_m": {"N": "100.0"},
        "lat": {"N": str(lat)},
        "lon": {"N": str(lon)},
        "grade_g_t": {"N": "2.0"},
        "hole_id": {"S": f"DH-{report_id}"},
    })


def test_full_pipeline_quality(gateway_process):
    run_id = uuid.uuid4().hex[:8]

    # --- gateway: real dedup by content hash ---
    doc_text = f"E2E test report {run_id}: identical content should be rejected as a duplicate upload."
    first = requests.post(f"{GATEWAY_URL}/upload", json={"report_id": f"E2E-{run_id}-a", "text": doc_text})
    dup = requests.post(f"{GATEWAY_URL}/upload", json={"report_id": f"E2E-{run_id}-b", "text": doc_text})
    malformed = requests.post(f"{GATEWAY_URL}/upload", json={"report_id": f"E2E-{run_id}-c", "text": "short"})

    # --- extraction: schema validation domain checks (no LLM needed) ---
    from extraction_agent import ExtractedRecord
    from pydantic import ValidationError
    bad_coords_rejected = False
    try:
        ExtractedRecord(mineral="Gold", depth_m=100.0, lat=40.7, lon=-74.0, grade_g_t=1.0, hole_id="DH-1")
    except ValidationError:
        bad_coords_rejected = True

    # --- extraction: confidence-gate graceful failure with a non-cooperating provider ---
    import os
    os.environ["LLM_PROVIDER"] = "fake"
    from extraction_agent import MAX_ITERATIONS, extract_with_confidence_gate
    fail_result = extract_with_confidence_gate("e2e-fail-test", "Some report text with no real content.")

    # --- resolution: two reports at the SAME site must merge into 1 occurrence ---
    ddb = aws.client("dynamodb")
    site_a, site_b = f"E2E-SITE-{run_id}-a", f"E2E-SITE-{run_id}-b"
    _seed_extraction(ddb, site_a, "Gold", -22.5, -68.123)
    _seed_extraction(ddb, site_b, "Gold", -22.5, -68.123)  # same site, different report
    different_site = f"E2E-SITE-{run_id}-c"
    _seed_extraction(ddb, different_site, "Gold", -10.0, -50.0)

    t0 = time.perf_counter()
    resolve = subprocess.run(
        [sys.executable, "src/resolve.py"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
    )
    resolve_seconds = time.perf_counter() - t0
    assert resolve.returncode == 0, resolve.stderr

    from common import warehouse
    con = warehouse.connect()
    warehouse.read_parquet(con, "s3://geo-extracted/occurrences/**/*.parquet", "occurrences")
    same_site_rows = con.execute(
        "SELECT n_reports, report_ids FROM occurrences WHERE mineral = 'Gold' AND lat_bucket = -22.5 AND lon_bucket = -68.12"
    ).fetchall()

    report = QualityReport(pipeline="geo-doc-extraction-agent")

    report.check(
        Dimension.VALIDITY, "gateway_accepts_new_content", measured=1.0 if first.status_code == 200 else 0.0,
        threshold=1.0, detail=f"first upload status={first.status_code}",
    )
    report.check(
        Dimension.VALIDITY, "gateway_rejects_duplicate_content", measured=1.0 if dup.status_code == 409 else 0.0,
        threshold=1.0, detail=f"duplicate upload status={dup.status_code}",
    )
    report.check(
        Dimension.VALIDITY, "gateway_rejects_malformed_upload",
        measured=1.0 if malformed.status_code == 400 else 0.0, threshold=1.0,
        detail=f"malformed upload status={malformed.status_code}",
    )
    report.check(
        Dimension.VALIDITY, "schema_rejects_out_of_region_coordinates",
        measured=1.0 if bad_coords_rejected else 0.0, threshold=1.0,
        detail="a lat/lon outside the survey bounding box must fail validation even though it type-checks",
    )
    report.check(
        Dimension.CORRECTNESS, "confidence_gate_fails_gracefully_not_silently",
        measured=1.0 if fail_result["status"] == "failed" and fail_result["attempts"] == MAX_ITERATIONS else 0.0,
        threshold=1.0, detail=f"fail_result={fail_result['status']}, attempts={fail_result['attempts']}",
    )
    report.check(
        Dimension.CONSISTENCY, "cross_document_resolution_merges_same_site",
        measured=(same_site_rows[0][0] if same_site_rows else 0), threshold=2,
        detail=f"two reports at the same coordinates must resolve to n_reports=2 in one occurrence row, got {same_site_rows}",
    )
    report.check(
        Dimension.TIMELINESS, "resolve_job_under_sla", measured=round(resolve_seconds, 1),
        threshold=120.0, higher_is_better=False, detail="PySpark cross-doc resolution wall time",
    )

    report.to_json(str(REPO_ROOT / "benchmarks" / "quality-report.json"))
    report.to_markdown(str(REPO_ROOT / "docs" / "quality-report.md"))

    report.assert_all_passed()
