#!/usr/bin/env python3
"""Seeds AWS Secrets Manager from the current environment, idempotently.

    source env.sh
    python3 scripts/secrets_setup.py

Only seeds a secret if its env var is actually set — this script is
meant to be safe to run in CI or a fresh `LLM_PROVIDER=fake` checkout
where MINIMAX_API_KEY/PINECONE_API_KEY don't exist and don't need to.
After this runs, utils/secrets.get_secret() reads from Secrets Manager
instead of falling back to the env var directly.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from utils import aws  # noqa: E402

SECRETS = {
    "geo/minimax-api-key": "MINIMAX_API_KEY",
    "geo/pinecone-api-key": "PINECONE_API_KEY",
}


def ensure_secret(client, secret_id: str, value: str) -> None:
    try:
        client.put_secret_value(SecretId=secret_id, SecretString=value)
        print(f"  {secret_id}: updated")
    except client.exceptions.ResourceNotFoundException:
        client.create_secret(Name=secret_id, SecretString=value)
        print(f"  {secret_id}: created")


def main() -> None:
    client = aws.client("secretsmanager")
    print("Secrets Manager:")
    seeded = 0
    for secret_id, env_var in SECRETS.items():
        value = os.environ.get(env_var)
        if not value:
            print(f"  {secret_id}: skipped ({env_var} not set)")
            continue
        ensure_secret(client, secret_id, value)
        seeded += 1
    if seeded == 0:
        print("  nothing to seed — this is normal for LLM_PROVIDER=fake / VECTOR_BACKEND=chroma")


if __name__ == "__main__":
    main()
