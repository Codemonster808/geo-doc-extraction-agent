# Quality report — geo-doc-extraction-agent

Generated: 2026-09-01T17:12:30.725829+00:00

**Overall score: 100%** (7/7 checks passed)

| Dimension | Score |
|---|---|
| correctness | 100% |
| consistency | 100% |
| validity | 100% |
| timeliness | 100% |

## Checks

| Dimension | Check | Measured | Threshold | Status | Detail |
|---|---|---|---|---|---|
| validity | gateway_accepts_new_content | 1.0 | 1.0 | PASS | first upload status=200 |
| validity | gateway_rejects_duplicate_content | 1.0 | 1.0 | PASS | duplicate upload status=409 |
| validity | gateway_rejects_malformed_upload | 1.0 | 1.0 | PASS | malformed upload status=400 |
| validity | schema_rejects_out_of_region_coordinates | 1.0 | 1.0 | PASS | a lat/lon outside the survey bounding box must fail validation even though it type-checks |
| correctness | confidence_gate_fails_gracefully_not_silently | 1.0 | 1.0 | PASS | fail_result=failed, attempts=2 |
| consistency | cross_document_resolution_merges_same_site | 10 | 2 | PASS | two reports at the same coordinates must resolve to n_reports=2 in one occurrence row, got [(10, ['E2E-SITE-119ca59e-a', 'E2E-SITE-119ca59e-b', 'E2E-SITE-2cdfb24b-a', 'E2E-SITE-2cdfb24b-b', 'E2E-SITE-8f225d00-a', 'E2E-SITE-8f225d00-b', 'E2E-SITE-974f9941-a', 'E2E-SITE-974f9941-b', 'E2E-SITE-ca0045c2-a', 'E2E-SITE-ca0045c2-b'])] |
| timeliness | resolve_job_under_sla | 92.6 | 120.0 | PASS | PySpark cross-doc resolution wall time |
