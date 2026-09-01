"""Reads a secret from AWS Secrets Manager, falling back to an env var.

    get_secret("geo/minimax-api-key", "MINIMAX_API_KEY")

The fallback is deliberate, not a hack: LLM_PROVIDER=fake (the default
for `make demo`, pytest, and CI) needs no secret at all, and a developer
without Secrets Manager seeded yet shouldn't be blocked from running
anything that doesn't actually need the real key. Run
`scripts/secrets_setup.py` to seed Secrets Manager from your current
env vars; after that, get_secret reads from there instead of `.env`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils import aws  # noqa: E402


def get_secret(secret_id: str, env_fallback: str) -> str | None:
    client = aws.client("secretsmanager")
    try:
        resp = client.get_secret_value(SecretId=secret_id)
        return resp["SecretString"]
    except client.exceptions.ResourceNotFoundException:
        return os.environ.get(env_fallback)
