# TriageAI: one container, one port (7860).
# FastAPI serves the JSON API and the built React app from the same origin.

# ---- Stage 1: build the React + Vite + Tailwind frontend ----------------------------------
FROM node:20-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python backend ----------------------------------------------------------------
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface \
    HF_HUB_DISABLE_TELEMETRY=1 \
    PORT=7860

# Hugging Face Spaces runs containers as uid 1000.
RUN useradd -m -u 1000 user
WORKDIR /app

# No torch: embeddings run on ONNX Runtime, so the image and memory footprint stay small.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Pre-download the quantized ONNX embedding model so container start-up is fast.
COPY app/__init__.py app/config.py app/duplicates.py ./app/
RUN python -c "from app.duplicates import OnnxEmbedder; OnnxEmbedder()"

COPY . .
COPY --from=frontend /frontend/dist ./frontend/dist

# Build the seeded SQLite DB + FAISS index at image build time. No API key is needed:
# seeding uses the offline classifier; live complaints use Claude when ANTHROPIC_API_KEY is set.
RUN python -m app.seed && chown -R user:user /app

USER user
EXPOSE 7860
CMD ["bash", "start.sh"]
