#!/usr/bin/env python3
"""
Runs the confidence-gated extraction agent over every synthetic report
and compares to the embedded ground truth (from src/data_gen.py), field
by field, to compute precision/recall — not just "did it parse".
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from extraction_agent import extract_with_confidence_gate  # noqa: E402

FIELDS = ["mineral", "depth_m", "lat", "lon", "grade_g_t", "hole_id"]


def fields_match(predicted: dict, truth: dict) -> dict:
    result = {}
    for field in FIELDS:
        pred_val, true_val = predicted.get(field), truth.get(field)
        if isinstance(pred_val, float) and isinstance(true_val, (int, float)):
            result[field] = abs(pred_val - true_val) < 0.01
        else:
            result[field] = pred_val == true_val
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data")
    parser.add_argument("--out", default="docs/eval-report.json")
    args = parser.parse_args()

    reports = json.loads((Path(args.data) / "_ground_truth.json").read_text())

    results = []
    for report in reports:
        outcome = extract_with_confidence_gate(report["report_id"], report["text"])
        if outcome["status"] == "extracted":
            match = fields_match(outcome["record"], report["ground_truth"])
        else:
            match = {f: False for f in FIELDS}
        results.append({
            "report_id": report["report_id"],
            "status": outcome["status"],
            "attempts": outcome["attempts"],
            "field_matches": match,
        })

    n_reports = len(results)
    n_extracted = sum(1 for r in results if r["status"] == "extracted")
    total_fields = n_reports * len(FIELDS)
    correct_fields = sum(sum(r["field_matches"].values()) for r in results)

    summary = {
        "n_reports": n_reports,
        "n_extracted": n_extracted,
        "schema_conformance_rate": round(n_extracted / n_reports, 4) if n_reports else 0,
        "field_level_precision": round(correct_fields / total_fields, 4) if total_fields else 0,
        "avg_attempts": round(sum(r["attempts"] for r in results) / n_reports, 2) if n_reports else 0,
        "results": results,
    }

    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=2))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
