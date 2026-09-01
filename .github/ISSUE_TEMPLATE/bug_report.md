---
name: Bug report
about: Report a problem with the pipeline, gateway, or tooling
title: "[BUG] "
labels: bug
assignees: ''
---

**Describe the bug**
A clear, concise description of what's wrong.

**To reproduce**
Steps to reproduce the behavior, including the exact command(s) run (e.g.
`make test`, `make demo`, a specific `pytest` invocation).

**Expected behavior**
What you expected to happen instead.

**Environment**
- `AWS_ENDPOINT_URL` / `MINISTACK_PORT`:
- `LLM_PROVIDER` / `VECTOR_BACKEND`:
- Python version:
- Go version (if gateway-related):
- OS:

**Logs / output**
Paste relevant output. Do not paste full LLM payloads, full report text, or
any secrets (`.env` contents, API keys) — this repo's data is synthetic but
logs should still stay to identifiers and outcomes.

**Additional context**
Anything else relevant (e.g. which sibling MiniStack port you're running on).
