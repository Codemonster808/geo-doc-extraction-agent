"""Schema/domain validation tests — these don't need the LLM at all,
they test ExtractedRecord directly, which is the actual safety net."""

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from models.extraction_agent import ExtractedRecord  # noqa: E402

VALID = dict(mineral="Copper", depth_m=150.0, lat=-22.5, lon=-68.0, grade_g_t=1.5, hole_id="DH-14")


def test_valid_record_passes():
    record = ExtractedRecord(**VALID)
    assert record.mineral == "Copper"


def test_unknown_mineral_rejected():
    with pytest.raises(ValidationError, match="not a recognized mineral"):
        ExtractedRecord(**{**VALID, "mineral": "Unobtainium"})


def test_negative_depth_rejected():
    with pytest.raises(ValidationError, match="out of plausible range"):
        ExtractedRecord(**{**VALID, "depth_m": -50.0})


def test_absurd_depth_rejected():
    with pytest.raises(ValidationError, match="out of plausible range"):
        ExtractedRecord(**{**VALID, "depth_m": 50_000.0})


def test_coordinate_outside_survey_region_rejected():
    """A record that passes type-checking but places a mine in the ocean is a bug, not a pass."""
    with pytest.raises(ValidationError, match="outside survey region bounds"):
        ExtractedRecord(
            **{**VALID, "lat": 40.7, "lon": -74.0}
        )  # New York, not the synthetic survey region


def test_extraction_json_parsing_from_noisy_llm_output():
    from models.extraction_agent import _extract_json

    noisy = 'Here is the extraction:\n```json\n{"mineral": "Gold", "depth_m": 100}\n```\nLet me know if you need anything else.'
    parsed = _extract_json(noisy)
    assert parsed == {"mineral": "Gold", "depth_m": 100}


def test_confidence_gate_fails_gracefully_not_silently(monkeypatch):
    """
    A provider that never produces valid extraction JSON (LLM_PROVIDER=fake
    here — it returns a fixed unrelated JSON blob) must retry up to
    MAX_ITERATIONS and then report status=failed with a reason, never
    return a record that passed validation by accident.
    """
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    # unique per run — the attempt counter is a real DynamoDB counter
    # (via the Step Functions gate), keyed by report_id
    import uuid

    from models.extraction_agent import MAX_ITERATIONS, extract_with_confidence_gate

    result = extract_with_confidence_gate(
        f"RPT-FAIL-TEST-{uuid.uuid4().hex[:8]}", "Some report text."
    )
    assert result["status"] == "failed"
    assert result["attempts"] == MAX_ITERATIONS
    assert result["reason"]
