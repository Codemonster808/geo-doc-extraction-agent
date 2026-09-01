# Security Policy

## Portfolio/demo disclaimer

This is a portfolio/demo project, not a production service. It exists to
demonstrate engineering practices (confidence-gated extraction, domain
validation, cross-document entity resolution) against synthetic,
deterministic data. There is no production deployment, no real user data,
and no SLA. Treat any findings here as you would for a personal project,
not a commercial product.

## Why secrets still matter here

Even though this is a demo, `LLM_PROVIDER=minimax` calls the real MiniMax
M3 API and **costs real money** per call — an exposed `MINIMAX_API_KEY`
(or `PINECONE_API_KEY`, if `VECTOR_BACKEND=pinecone` is used) is a
financial exposure, not just a data one. Keep these out of source control:

- Real credentials belong in `.env` (gitignored) or
  `~/.config/de-portfolio/.env`, never in `.env.example`, committed code,
  or a pull request.
- Default configuration (`env.sh`, tests, CI, `make demo`) always uses
  `LLM_PROVIDER=fake` and `VECTOR_BACKEND=chroma` — no real API calls, no
  cost. Only `make eval` opts into the real provider intentionally.
- `scripts/secrets_setup.py` reads from your live environment and is
  meant for local/manual use only — it should not run unattended in CI.

## Reporting a vulnerability

If you find a security issue (e.g. a way to exfiltrate secrets, bypass the
intake gateway's dedup/validation, or otherwise misuse this repo), please
open a private report via GitHub's "Report a vulnerability" flow on this
repository, or open an issue if that's unavailable. There is no bug bounty
— this is a demo project maintained on a best-effort basis.
