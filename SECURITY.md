# Security policy

## Reporting a vulnerability

Please do not open a public issue for security problems. Use GitHub's private vulnerability reporting instead: on the repository page go to **Security**, then **Report a vulnerability**. You should get a reply within 7 days.

Useful details: what you found, how to reproduce it, and what an attacker could do with it.

## In scope

- Personal data reaching the LLM prompt or the CSV export unmasked (see `eval/pii_leak_test.py` for how leaks are measured).
- Prompt injection through complaint text that changes the AI suggestion in ways the schema and validation should prevent.
- Any path that changes a complaint's status without a named human reviewer, or that bypasses the audit log.
- Secrets exposed in the repository, the Docker image, logs or API responses.

## Known limitations (not vulnerabilities, already documented)

- Rule-based name masking misses names in phrasings it was not designed for. On the held-out PII set every name leaked. See `docs/RESULTS.md`.
- The demo deployment has no authentication. It is a public demo with synthetic data only and must not be used with real complaints.

## Handling secrets

- `ANTHROPIC_API_KEY` is read only from the environment (`.env` locally, the host's secret store in deployment). `.env` is git-ignored.
- CI scans the full git history for Anthropic key patterns on every push.
- If you accidentally commit a key, revoke it with the provider immediately. Rewriting history does not make an exposed key safe.
