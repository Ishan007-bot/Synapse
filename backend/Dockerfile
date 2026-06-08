# ──────────────────────────────────────────────────────────────────────────
# Synapse backend image — FastAPI + sentence-transformers + Groq/Gemini SDKs.
#
# We pre-download the embedding model during build so the container is ready
# to answer requests on first hit (no surprise 30s startup downloading weights).
# ──────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim AS base

# System deps:
#  - build-essential is needed for some wheels (e.g. neo4j driver native bits)
#  - curl + wget for healthchecks / debugging
# We keep them only in the build layer where practical.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Hugging Face: reuse the cached weights from the build step on every run
    HF_HOME=/root/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/root/.cache/torch/sentence_transformers

WORKDIR /app

# Copy the package definition + source. We don't split this into two stages
# because the editable install requires the package layout to exist.
COPY backend/pyproject.toml ./
COPY backend/app ./app

RUN pip install --upgrade pip \
    && pip install -e .

# Pre-download the BGE-small embedding model so first request is instant.
# This is what makes the resulting image self-contained for offline runs.
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('BAAI/bge-small-en-v1.5')"

# CLI scripts (ingest, build_index, graph.build, eval) all import from .app
# and run fine via `docker compose exec backend python -m app.<module>`.

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=4 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
