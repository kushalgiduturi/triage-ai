# TriageAI developer commands. Linux / macOS (or Git Bash / WSL with make installed).
# Embeddings default to the Lite edition (ONNX, no torch). Override: make eval TRIAGE_EMBEDDINGS=sentence-transformers
PY ?= python
export TRIAGE_EMBEDDINGS ?= onnx
PORT ?= 7860
EVAL = $(PY) eval/run_eval.py

.PHONY: help setup setup-full seed test coverage demo eval eval-category eval-urgency eval-dupes \
        eval-routing eval-latency eval-cost test-pii test-bias eval-agreement

help:
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

setup: ## Install the Lite edition, build the UI and seed the demo database
	$(PY) -m pip install -r requirements-lite.txt
	cd frontend && npm ci --no-audit --no-fund && npm run build
	$(PY) -m app.seed

setup-full: ## Same as setup, with sentence-transformers + torch (Full edition)
	$(PY) -m pip install -r requirements.txt
	cd frontend && npm ci --no-audit --no-fund && npm run build
	TRIAGE_EMBEDDINGS=sentence-transformers $(PY) -m app.seed

seed: ## Rebuild the demo database from data/complaints.csv
	$(PY) -m app.seed

test: ## Unit and API tests (offline, no API key needed)
	$(PY) -m pytest -q

coverage: ## Tests with a coverage report for app/
	$(PY) -m pytest -q --cov=app --cov-report=term

demo: ## Start the app on http://localhost:$(PORT) (API + UI)
	$(PY) -m app.seed --if-empty
	$(PY) -m uvicorn app.main:app --host 0.0.0.0 --port $(PORT)

eval: ## Every metric for all three systems, plus PII, bias and agreement
	$(EVAL) --system all
	$(PY) eval/pii_leak_test.py
	$(PY) eval/pii_leak_test.py --heldout
	$(PY) eval/agreement.py

eval-category: ## Category accuracy (rule, tfidf, llm)
	$(EVAL) --system all --metrics category

eval-urgency: ## Urgency macro-F1
	$(EVAL) --system all --metrics urgency

eval-dupes: ## Duplicate precision and recall at threshold 0.85
	$(EVAL) --system all --metrics dupes

eval-routing: ## Routing accuracy and manual-triage rate
	$(EVAL) --system all --metrics routing

eval-latency: ## End-to-end latency per complaint
	$(EVAL) --system all --metrics latency

eval-cost: ## Cost per 1000 complaints (API cost; local systems are 0)
	$(EVAL) --system all --metrics cost

test-pii: ## PII leak test on 120 Indian-style complaints (tuning set and held-out set)
	$(PY) eval/pii_leak_test.py
	$(PY) eval/pii_leak_test.py --heldout

test-bias: ## Urgency consistency across tone and dialect rewrites
	$(EVAL) --system all --metrics bias

eval-agreement: ## Human override rate from the audit log of data/triage.db
	$(PY) eval/agreement.py
