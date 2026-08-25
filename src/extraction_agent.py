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
from common.vectors import get_vector_store  # noqa: E402

# A fixed retrieval query targeting the fact-bearing sentences in a
# geological report — RAG here isn't "answer this specific question",
# it's "surface the passages likely to contain the structured fields",
# so a single well-chosen query works across all reports.
RETRIEVAL_QUERY = "mineral occurrence depth coordinates assay grade drill hole"
# These synthetic reports are short (~5 sentences) and split the facts
# across 2 distinct sentences (mineral/depth/grade/hole_id in one,
# coordinates in another) — top_k=3 measurably missed the coordinates
# sentence in testing, silently dropping lat/lon from every extraction.
# 4 keeps genuine filtering (excludes the boilerplate closing sentence)
# while reliably covering both fact-bearing sentences.
RETRIEVAL_TOP_K = 4

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


def retrieve_relevant_context(report_id: str, fallback_text: str) -> str:
    """
    Retrieves the top-k chunks of THIS report most relevant to
    extraction, instead of handing the LLM the entire raw text. Falls
    back to the full text if the vector store has nothing indexed for
    this report (e.g. index_docs.py wasn't run) — extraction should
    degrade gracefully, not hard-fail on a missing index.
    """
    try:
        from sentence_transformers import SentenceTransformer
        model = retrieve_relevant_context._model if hasattr(retrieve_relevant_context, "_model") \
            else SentenceTransformer("all-MiniLM-L6-v2")
        retrieve_relevant_context._model = model

        store = get_vector_store("geo_reports")
        query_embedding = model.encode([RETRIEVAL_QUERY])[0].tolist()
        # Scoped to this report's own chunks via `where` — an unscoped
        # global query would rank this report's best chunk against every
        # other report's near-identical sentences, and it can lose (see
        # common/vectors.py docstring for the bug this fixes).
        top = store.query(query_embedding, top_k=RETRIEVAL_TOP_K, where={"report_id": report_id})
        if not top:
            return fallback_text
        # metadata only carries report_id/chunk_index — reconstruct order but not text,
        # so re-split the fallback text and pick the retrieved indices' sentences.
        import re as _re
        sentences = [s.strip() for s in _re.split(r"(?<=[.\n])\s+", fallback_text) if s.strip()]
        indices = sorted(r["metadata"]["chunk_index"] for r in top if r["metadata"]["chunk_index"] < len(sentences))
        return " ".join(sentences[i] for i in indices) or fallback_text
    except Exception:
        return fallback_text


def extract_fields(llm, report_text: str, hint: str = "") -> dict:
    prompt = (
        "Extract the following fields from this geological survey report as a single JSON object "
        "with keys exactly: mineral, depth_m, lat, lon, grade_g_t, hole_id.\n"
        + (f"Note: {hint}\n" if hint else "")
        + f"\nReport:\n{report_text}\n\nReturn only the JSON object, nothing else."
    )
    response = llm.complete(prompt, max_tokens=600)
    return _extract_json(response)


def extract_with_confidence_gate(report_id: str, report_text: str) -> dict:
    """
    Returns {"status": "extracted", "record": {...}} on success, or
    {"status": "failed", "reason": ..., "attempts": N} if validation
    still fails after MAX_ITERATIONS — never a record that silently
    passed a field it shouldn't have.
    """
    from statemachine import gate_attempt

    llm = get_provider()
    hint = ""
    last_error = None
    retrieved_context = retrieve_relevant_context(report_id, report_text)

    attempt = 0
    while True:
        gate = gate_attempt(report_id, MAX_ITERATIONS)  # real Step Functions Choice/Retry/Catch
        if not gate["allowed"]:
            break
        attempt = gate["attempts"]

        try:
            raw = extract_fields(llm, retrieved_context, hint=hint)
            record = ExtractedRecord(**raw)
            _persist_extraction(report_id, record.model_dump())
            return {"status": "extracted", "record": record.model_dump(), "attempts": attempt}
        except (ValidationError, ValueError, json.JSONDecodeError) as e:
            last_error = str(e)
            hint = f"A previous extraction attempt failed validation: {last_error}. Be precise about field types and value ranges."

    return {"status": "failed", "reason": last_error, "attempts": attempt, "report_id": report_id}


def _persist_extraction(report_id: str, record: dict) -> None:
    """Writes a successfully validated extraction to DynamoDB — the
    table src/resolve.py's cross-document entity resolution reads from."""
    from common import aws
    ddb = aws.client("dynamodb")
    ddb.put_item(
        TableName="geo-extractions",
        Item={
            "report_id": {"S": report_id},
            "mineral": {"S": record["mineral"]},
            "depth_m": {"N": str(record["depth_m"])},
            "lat": {"N": str(record["lat"])},
            "lon": {"N": str(record["lon"])},
            "grade_g_t": {"N": str(record["grade_g_t"])},
            "hole_id": {"S": record["hole_id"]},
        },
    )
