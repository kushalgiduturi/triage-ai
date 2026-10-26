# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [1.1.0] - 2026-10-26

### Added
- Evaluation harness comparing three systems (rule-only, TF-IDF + LogReg, LLM pipeline) with `make eval-*` targets and raw outputs in `eval/results/`. Measured results in `docs/RESULTS.md`.
- Rule-only keyword baseline (`app/baselines.py`).
- PII leak test on 120 Indian-style complaints with a tuning set and a held-out set (`eval/pii_leak_test.py`).
- Ollama provider for open-source models (`PROVIDER=ollama`); Claude remains the default.
- `triageai.Pipeline` library interface and `pyproject.toml`.
- CSV export of triage decisions (`GET /export.csv`, masked text only).
- Two editions: Full (sentence-transformers + torch, run locally) and Lite (ONNX Runtime, deployed, fits 512 MB).
- Global audit log endpoint and page, optional contact field on submissions.
- Makefile, open-source policies (CONTRIBUTING, Code of Conduct, SECURITY), roadmap and dataset datasheet.

### Changed
- Frontend rebuilt in React, Vite, Tailwind and Framer Motion with a spatial white and sky-blue design system; audited for WCAG AA, keyboard use and reduced motion.
- Duplicate detection anchors each complaint vector with its issue label and requires the same sub-issue, raising pair F1 from 0.35 to 0.82 on the synthetic set.
- PII masking catches Indian honorific and speaker cues (garu, bhaiya, bol raha hoon), repeats of a detected name, 3-3-4 phone numbers and JNTU-style roll numbers.

### Fixed
- Out-of-memory crash on 512 MB hosts (tokenizer and ONNX optimiser memory).
- A lone first name after "contact" was not masked.

### Known issues
- Rule-based name masking does not generalise: every name leaked on the held-out PII set.
- LLM-path metrics are not measured yet (no API key or local model was available).
- Times display in UTC on the deployed demo.

## [1.0.0] - 2026-10-26

### Added
- Initial release: synthetic data generator, PII masking, structured extraction with Claude and an offline fallback, hybrid urgency scoring, FAISS duplicate detection, routing table, FastAPI backend with review endpoints and audit log, reviewer UI, evaluation script, Docker image and CI.
