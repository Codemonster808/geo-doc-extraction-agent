#!/usr/bin/env python3
"""
Cross-document entity resolution: the same mineral occurrence can be
reported in two different surveys — this groups extracted records by
(mineral, rounded lat/lon) so they resolve to one occurrence instead of
being counted twice, then writes the resolved table to S3 Parquet for
the DuckDB serving layer (sql/occurrences_by_region.sql).
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def build_spark(app_name: str = "resolve-occurrences"):
    from pyspark.sql import SparkSession

    endpoint = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4585")
    return (
        SparkSession.builder.appName(app_name)
        .master("local[2]")
        .config("spark.driver.memory", "1g")
        .config("spark.jars.packages", "org.apache.hadoop:hadoop-aws:3.5.0")
        .config("spark.hadoop.fs.s3a.endpoint", endpoint)
        .config("spark.hadoop.fs.s3a.access.key", os.environ.get("AWS_ACCESS_KEY_ID", "test"))
        .config("spark.hadoop.fs.s3a.secret.key", os.environ.get("AWS_SECRET_ACCESS_KEY", "test"))
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .getOrCreate()
    )


def resolve_from_dynamodb() -> dict:
    """Reads all extracted records from DynamoDB, groups by
    (mineral, lat rounded to 2dp, lon rounded to 2dp) — close enough to
    be the same drill site — and writes the resolved occurrence table."""
    import sys as _sys

    _sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from pyspark.sql import functions as F

    from utils import aws

    ddb = aws.client("dynamodb")
    items = []
    paginator = ddb.get_paginator("scan")
    for page in paginator.paginate(TableName="geo-extractions"):
        for item in page.get("Items", []):
            items.append(
                {
                    "report_id": item["report_id"]["S"],
                    "mineral": item["mineral"]["S"],
                    "depth_m": float(item["depth_m"]["N"]),
                    "lat": float(item["lat"]["N"]),
                    "lon": float(item["lon"]["N"]),
                    "grade_g_t": float(item["grade_g_t"]["N"]),
                    "hole_id": item["hole_id"]["S"],
                }
            )

    spark = build_spark()
    try:
        if not items:
            return {"n_raw_records": 0, "n_resolved_occurrences": 0}

        df = spark.createDataFrame(items)
        n_raw = df.count()

        resolved = (
            df.withColumn("lat_bucket", F.round(F.col("lat"), 2))
            .withColumn("lon_bucket", F.round(F.col("lon"), 2))
            .groupBy("mineral", "lat_bucket", "lon_bucket")
            .agg(
                F.count("*").alias("n_reports"),
                F.collect_list("report_id").alias("report_ids"),
                F.avg("depth_m").alias("avg_depth_m"),
                F.avg("grade_g_t").alias("avg_grade_g_t"),
            )
        )
        n_resolved = resolved.count()

        (resolved.coalesce(1).write.mode("overwrite").parquet("s3a://geo-extracted/occurrences/"))

        return {"n_raw_records": n_raw, "n_resolved_occurrences": n_resolved}
    finally:
        spark.stop()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    stats = resolve_from_dynamodb()
    print(f"resolved: {stats}")


if __name__ == "__main__":
    main()
