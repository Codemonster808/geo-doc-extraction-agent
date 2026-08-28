# Quality report — geo-doc-extraction-agent

Generated: 2026-08-28T20:59:32.103472+00:00

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
| consistency | cross_document_resolution_merges_same_site | 2 | 2 | PASS | two reports at the same coordinates must resolve to n_reports=2 in one occurrence row, got [(2, ['E2E-SITE-18edb91e-a', 'E2E-SITE-18edb91e-b'])] |
| timeliness | resolve_job_under_sla | 34.3 | 120.0 | PASS | PySpark cross-doc resolution wall time |
