#!/usr/bin/env python3
"""
Generates synthetic geological survey report text with embedded facts
(mineral, depth, coordinates, assay grade) and their ground-truth labels
— used to measure field-level extraction precision/recall.
"""
import argparse
import json
from pathlib import Path
from random import Random

MINERALS = ["Copper", "Gold", "Silver", "Zinc", "Lithium", "Nickel"]

# Deliberately kept within a plausible bounding box for the synthetic
# survey region — this is what the domain schema validator checks against.
LAT_RANGE = (-25.0, -20.0)
LON_RANGE = (-70.0, -66.0)


def gen_report(rng: Random, report_id: str) -> dict:
    mineral = rng.choice(MINERALS)
    depth_m = rng.randint(20, 400)
    lat = round(rng.uniform(*LAT_RANGE), 4)
    lon = round(rng.uniform(*LON_RANGE), 4)
    grade = round(rng.uniform(0.1, 5.0), 2)
    hole_id = f"DH-{rng.randint(1, 99)}"

    text = (
        f"GEOLOGICAL SURVEY REPORT {report_id}\n\n"
        f"Drill hole {hole_id} intersected {grade} g/t {mineral} at a depth of {depth_m}m. "
        f"Coordinates recorded at the collar: {lat}, {lon}.\n\n"
        f"Field notes: core recovery was consistent throughout the interval. "
        f"Sample was logged by the site geologist and sent for assay confirmation. "
        f"No significant alteration was observed above {depth_m - 15}m."
    )

    return {
        "report_id": report_id,
        "text": text,
        "ground_truth": {
            "mineral": mineral,
            "depth_m": depth_m,
            "lat": lat,
            "lon": lon,
            "grade_g_t": grade,
            "hole_id": hole_id,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reports", type=int, default=15)
    parser.add_argument("--out", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = Random(args.seed)
    out_dir = Path(args.out)
    (out_dir / "reports").mkdir(parents=True, exist_ok=True)

    all_reports = []
    for i in range(args.reports):
        report_id = f"RPT-{i:03d}"
        report = gen_report(rng, report_id)
        (out_dir / "reports" / f"{report_id}.txt").write_text(report["text"])
        all_reports.append(report)

    (out_dir / "_ground_truth.json").write_text(json.dumps(all_reports, indent=2))
    print(f"wrote {len(all_reports)} synthetic reports with embedded ground truth to {out_dir}")


if __name__ == "__main__":
    main()
