#!/usr/bin/env python3
"""FastAPI serving layer: search resolved occurrences, look up a single doc's extraction."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI, HTTPException  # noqa: E402

from utils import aws, warehouse  # noqa: E402

app = FastAPI(title="geo-doc-extraction-agent")


def _occurrences_con():
    con = warehouse.connect()
    try:
        warehouse.read_parquet(con, "s3://geo-extracted/occurrences/**/*.parquet", "occurrences")
    except Exception:
        con.execute("CREATE OR REPLACE VIEW occurrences AS SELECT NULL AS mineral WHERE FALSE")
    return con


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/search")
def search(mineral: str | None = None):
    con = _occurrences_con()
    if mineral:
        rows = con.execute(
            "SELECT * FROM occurrences WHERE mineral = ? ORDER BY n_reports DESC", [mineral]
        ).fetchall()
    else:
        rows = con.execute("SELECT * FROM occurrences ORDER BY n_reports DESC").fetchall()
    columns = [d[0] for d in con.description] if rows or con.description else []
    return [dict(zip(columns, r)) for r in rows]


@app.get("/extract/{report_id}")
def get_extraction(report_id: str):
    ddb = aws.client("dynamodb")
    resp = ddb.get_item(TableName="geo-extractions", Key={"report_id": {"S": report_id}})
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="no extraction found for this report_id")
    return {
        "report_id": report_id,
        "mineral": item["mineral"]["S"],
        "depth_m": float(item["depth_m"]["N"]),
        "lat": float(item["lat"]["N"]),
        "lon": float(item["lon"]["N"]),
        "grade_g_t": float(item["grade_g_t"]["N"]),
        "hole_id": item["hole_id"]["S"],
    }
