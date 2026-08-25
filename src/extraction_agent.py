#!/usr/bin/env python3
"""
Confidence-gated extraction agent: retrieve the report text, ask the LLM
to extract structured fields, validate against a domain schema (units,
coordinate bounds), and retry with a more constrained prompt only when
confidence is low — not blindly, and not never.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pydantic import BaseModel, ValidationError, field_validator  # noqa: E402

from common.llm import get_provider  # noqa: E402

VALID_MINERALS = {"Copper", "Gold", "Silver", "Zinc", "Lithium", "Nickel"}
LAT_BOUNDS = (-30.0, -15.0)  # a bit wider than the generator's range, for validator slack
LON_BOUNDS = (-75.0, -60.0)
MAX_DEPTH_M = 1000
MAX_ITERATIONS = 2


class ExtractedRecord(BaseModel):
    mineral: str
    depth_m: float
    lat: float
    lon: float
    grade_g_t: float
    hole_id: str

    @field_validator("mineral")
    @classmethod
    def mineral_must_be_known(cls, v):
        if v not in VALID_MINERALS:
            raise ValueError(f"'{v}' is not a recognized mineral")
        return v

    @field_validator("depth_m")
    @classmethod
    def depth_must_be_plausible(cls, v):
        if not (0 < v <= MAX_DEPTH_M):
            raise ValueError(f"depth_m={v} is out of plausible range (0, {MAX_DEPTH_M}]")
        return v

    @field_validator("lat")
    @classmethod
    def lat_in_bounds(cls, v):
        if not (LAT_BOUNDS[0] <= v <= LAT_BOUNDS[1]):
            raise ValueError(f"lat={v} outside survey region bounds {LAT_BOUNDS}")
        return v

    @field_validator("lon")
    @classmethod
    def lon_in_bounds(cls, v):
        if not (LON_BOUNDS[0] <= v <= LON_BOUNDS[1]):
            raise ValueError(f"lon={v} outside survey region bounds {LON_BOUNDS}")
        return v


def _extract_json(llm_output: str) -> dict:
    match = re.search(r"\{.*\}", llm_output, re.DOTALL)
    if not match:
        raise ValueError(f"no JSON object found in LLM output: {llm_output[:200]!r}")
    return json.loads(match.group(0))


def extract_fields(llm, report_text: str, hint: str = "") -> dict:
    prompt = (
        "Extract the following fields from this geological survey report as a single JSON object "
        "with keys exactly: mineral, depth_m, lat, lon, grade_g_t, hole_id.\n"
        + (f"Note: {hint}\n" if hint else "")
        + f"\nReport:\n{report_text}\n\nReturn only the JSON object, nothing else."
    )
    response = llm.complete(prompt, max_tokens=300)
    return _extract_json(response)


def extract_with_confidence_gate(report_id: str, report_text: str) -> dict:
    """
    Returns {"status": "extracted", "record": {...}} on success, or
    {"status": "failed", "reason": ..., "attempts": N} if validation
    still fails after MAX_ITERATIONS — never a record that silently
    passed a field it shouldn't have.
    """
    llm = get_provider()
    hint = ""
    last_error = None

    for attempt in range(1, MAX_ITERATIONS + 1):
        try:
            raw = extract_fields(llm, report_text, hint=hint)
            record = ExtractedRecord(**raw)
            return {"status": "extracted", "record": record.model_dump(), "attempts": attempt}
        except (ValidationError, ValueError, json.JSONDecodeError) as e:
            last_error = str(e)
            hint = f"A previous extraction attempt failed validation: {last_error}. Be precise about field types and value ranges."

    return {"status": "failed", "reason": last_error, "attempts": MAX_ITERATIONS, "report_id": report_id}
