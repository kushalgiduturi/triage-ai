# Deployment

## Two editions

| | Full | Lite |
|---|---|---|
| Embeddings | sentence-transformers + torch | ONNX Runtime (quantized export of the same model) |
| Install | `pip install -r requirements.txt` | `pip install -r requirements-lite.txt` |
| Container | `Dockerfile.full` | `Dockerfile` |
| Memory, measured in Docker | about 980 MB after start, killed under a 512 MB limit | about 350 MB after start |
| Image size | 2.8 GB | 1.1 GB |
| Use | run locally | deployed demo, free 512 MB hosts |

`TRIAGE_EMBEDDINGS=auto` (default) uses sentence-transformers when it is installed and ONNX otherwise. The FAISS index records which backend built it and is rebuilt from the database when the edition changes.

## Docker

```bash
docker build -t triage-ai .                          # Lite
docker build -f Dockerfile.full -t triage-ai-full .  # Full
docker run -p 7860:7860 -e ANTHROPIC_API_KEY=... triage-ai
```

The image builds the frontend, downloads the embedding model and seeds the demo database at build time, so start-up is fast.

## Render (live demo)

`render.yaml` is a Blueprint for the Lite `Dockerfile` on the free plan. In the Render dashboard choose *New*, then *Blueprint*, and pick this repository. Set `ANTHROPIC_API_KEY` in the service's *Environment* page; it is declared with `sync: false`, so it never lives in git.

Free plan limits:

- The service sleeps after 15 minutes without traffic, and the first request then takes about a minute. An uptime monitor that calls `/health` every 5 minutes keeps it awake, but uses about 744 of the workspace's 750 free instance hours a month.
- The disk is not persistent: reviewer actions reset to the seeded state whenever the service restarts or redeploys.

## Hugging Face Spaces

A Docker Space needs this front matter at the top of the Space's `README.md`:

```yaml
---
title: TriageAI
sdk: docker
app_port: 7860
---
```

Hugging Face requires a PRO subscription to host Docker Spaces on free CPU, so this is not the live target.

## CI

`.github/workflows/ci.yml` builds the frontend, runs the tests with a coverage report, runs the evaluation smoke test and scans the git history for Anthropic key patterns on every push.
