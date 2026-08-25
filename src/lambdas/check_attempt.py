"""
Lambda-shaped handler: atomically increments the extraction attempt
counter for a report and reports whether another attempt is allowed.
Deployed to MiniStack Lambda, invoked from Step Functions with
Retry/Catch (asl/extraction_gate.json) once per confidence-gate retry —
the same control-flow-in-SF pattern as fintech-txn-integrity-pipeline's
daily job and agentic-claims-copilot's budget gate.
"""
import boto3

ATTEMPTS_TABLE = "geo-extraction-attempts"


def handler(event, context):
    endpoint = "http://127.0.0.1:4566"
    ddb = boto3.client("dynamodb", endpoint_url=endpoint, region_name="us-east-1")

    report_id = event["report_id"]
    max_attempts = event.get("max_attempts", 2)

    resp = ddb.update_item(
        TableName=ATTEMPTS_TABLE,
        Key={"report_id": {"S": report_id}},
        UpdateExpression="ADD attempts :inc",
        ExpressionAttributeValues={":inc": {"N": "1"}},
        ReturnValues="UPDATED_NEW",
    )
    attempts = int(resp["Attributes"]["attempts"]["N"])

    return {"report_id": report_id, "attempts": attempts, "allowed": attempts <= max_attempts}
