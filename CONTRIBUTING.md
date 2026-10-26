# Contributing to TriageAI

Thanks for helping. Small, focused pull requests are easiest to review.

## Ground rules

- **The AI recommends. A human always decides.** Do not add anything that dispatches work, sends messages or changes a complaint's status without a named human reviewer.
- **Synthetic or anonymised data only.** Never add real complaints, names, phone numbers or other personal data, not even in tests or screenshots.
- **No secrets in git.** API keys go in `.env`, which is git-ignored. CI fails if an Anthropic key pattern appears in the history.
- **Measured numbers only.** If a change affects results, re-run the evaluation and update `docs/RESULTS.md` from the output. Never edit a number by hand.

## Set up

Requires Python 3.10 or newer, Node 20 and `make`.

```bash
git clone https://github.com/kushalgiduturi/triage-ai.git
cd triage-ai
make setup
make test
```

`make help` lists every target. Without `make`, run the commands listed under each target in the [Makefile](Makefile).

## Making a change

1. Pick an issue, or open one describing the change first if it is large. Good starting points are in [docs/ROADMAP.md](docs/ROADMAP.md).
2. Create a branch from `main`.
3. Write or update tests in `tests/`. Tests must run offline: they use hash embeddings and never call an LLM.
4. Run `make test`. If you touched extraction, PII masking, duplicates, urgency or routing, also run `make eval` and `make test-pii`, and say in the pull request how the numbers changed.
5. If you changed the frontend, run `cd frontend && npm run build` and check it in the browser at 1440, 1024 and 768 px. The design rules (white and sky blue, three elevation levels, red only for Critical, functional motion only) are described in `frontend/src/ui.jsx`.
6. Open a pull request using the template.

## Style

- Python: type hints, short docstrings, comments that explain why rather than what. Keep modules focused (`app/pii.py` only masks, `app/routing.py` only routes).
- Frontend: build pages from the shared components in `frontend/src/ui.jsx` (`Surface`, `Button`, `Table`, `Field`). Do not add colours, shadows or radii outside the tokens in `tailwind.config.js`.
- Docs: plain sentences. Do not use em dashes.

## Code of conduct

This project follows the [Code of Conduct](CODE_OF_CONDUCT.md). Report security issues privately as described in [SECURITY.md](SECURITY.md), not in public issues.
