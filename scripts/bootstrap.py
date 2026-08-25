#!/usr/bin/env python3
"""Idempotent creation of the AWS resources this repo needs, against MiniStack."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from common import aws  # noqa: E402

BUCKETS = ["geo-docs", "geo-extracted"]
DEDUP_TABLE = "geo-doc-dedup"
EXTRACTIONS_TABLE = "geo-extractions"


def ensure_bucket(s3, name: str) -> None:
    existing = {b["Name"] for b in s3.list_buckets().get("Buckets", [])}
    if name not in existing:
        s3.create_bucket(Bucket=name)
        print(f"  created bucket: {name}")
    else:
        print(f"  bucket already exists: {name}")


def ensure_table(dynamodb, table_name: str, key_name: str) -> None:
    existing = dynamodb.list_tables()["TableNames"]
    if table_name in existing:
        print(f"  table already exists: {table_name}")
        return
    dynamodb.create_table(
        TableName=table_name,
        KeySchema=[{"AttributeName": key_name, "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": key_name, "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    print(f"  created table: {table_name}")


def main() -> None:
    print("S3 buckets:")
    s3 = aws.client("s3")
    for bucket in BUCKETS:
        ensure_bucket(s3, bucket)

    print("DynamoDB tables:")
    ddb = aws.client("dynamodb")
    ensure_table(ddb, DEDUP_TABLE, "content_hash")
    ensure_table(ddb, EXTRACTIONS_TABLE, "report_id")

    print("Bootstrap complete.")


if __name__ == "__main__":
    main()
