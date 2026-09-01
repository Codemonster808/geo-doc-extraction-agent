import sys
from pathlib import Path

from pydantic import ValidationError
from pytest_bdd import given, scenarios, then, when

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from models.extraction_agent import ExtractedRecord  # noqa: E402

scenarios("../extraction-validation.feature")

VALID = dict(mineral="Copper", depth_m=150.0, lat=-22.5, lon=-68.0, grade_g_t=1.5, hole_id="DH-14")


@given(
    "a record that would type-check with lat 40.7 and lon -74.0",
    target_fixture="payload",
)
def nyc():
    return {**VALID, "lat": 40.7, "lon": -74.0}


@given("a record with depth_m 50000", target_fixture="payload")
def deep():
    return {**VALID, "depth_m": 50_000.0}


@given("a record with mineral Unobtainium", target_fixture="payload")
def bad_mineral():
    return {**VALID, "mineral": "Unobtainium"}


@when("ExtractedRecord is constructed", target_fixture="outcome")
def construct(payload):
    try:
        return ExtractedRecord(**payload)
    except ValidationError as exc:
        return exc


@then("validation fails because the point is outside the survey region")
def nyc_fail(outcome):
    assert isinstance(outcome, ValidationError)
    assert "outside survey region bounds" in str(outcome)


@then("validation fails because depth is out of plausible range")
def depth_fail(outcome):
    assert isinstance(outcome, ValidationError)
    assert "out of plausible range" in str(outcome)


@then("validation fails because the mineral is not recognized")
def mineral_fail(outcome):
    assert isinstance(outcome, ValidationError)
    assert "not a recognized mineral" in str(outcome)
