## Summary

<!-- What does this change do, and why? -->

## Related spec/ADR

<!-- Link the relevant docs/specs/*.md or docs/adr/*.md if this changes
     pipeline behavior, constants (VALID_MINERALS, bounds, MAX_ITERATIONS),
     or an architectural decision. -->

## Checklist

- [ ] `make test` passes locally (`build-gateway` + `pytest tests/ features/ --ignore=tests/data_quality`)
- [ ] `pre-commit run --all-files` passes (ruff, mypy, gofmt, hygiene hooks)
- [ ] Coverage threshold met (`--cov-fail-under` in CI)
- [ ] If `VALID_MINERALS`, the lat/lon bounds, or `MAX_ITERATIONS` changed:
      `docs/specs/spec-confidence-gated-extraction.md` and the matching
      `features/extraction-validation.feature` scenarios were updated too
- [ ] No real report data, coordinates, or PII introduced — synthetic data only
- [ ] No secrets committed (`.env`, API keys); defaults still
      `LLM_PROVIDER=fake` / `VECTOR_BACKEND=chroma`

## Test plan

<!-- How did you verify this? -->
