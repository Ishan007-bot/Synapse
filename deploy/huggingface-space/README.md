---
title: Synapse Backend
emoji: 🧠
colorFrom: yellow
colorTo: red
sdk: docker
app_port: 8000
pinned: false
license: mit
short_description: Graph-RAG backend powering the Synapse demo
---

# Synapse — Backend

FastAPI + Neo4j-aware Graph RAG service. Deployed as a Docker Space on
Hugging Face; the frontend ([Vercel](https://vercel.com)) and the graph
database ([Neo4j AuraDB Free](https://neo4j.com/cloud/aura-free/)) live elsewhere.

## What's wired up

- `GET /health`, `GET /stats`
- `GET /graph`, `GET /graph/subgraph`
- `POST /query`, `POST /query/stream` (SSE)
- `POST /query/naive`
- `POST /ingest`

Interactive docs at `/docs` once the Space is running.

## Required secrets (set in the Space's **Settings → Variables and secrets**)

| Name | Example | Purpose |
|---|---|---|
| `GROQ_API_KEY` | `gsk_…` | LLM provider for chat + extraction |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Model used for generation |
| `LLM_PROVIDER` | `groq` | `groq` or `gemini` |
| `NEO4J_URI` | `neo4j+s://<id>.databases.neo4j.io` | Aura connection URI |
| `NEO4J_USER` | `neo4j` | Aura username |
| `NEO4J_PASSWORD` | `…` | Aura password |
| `ALLOWED_ORIGINS` | `https://<your-app>.vercel.app` | CORS — the frontend's URL |

The repo it ships is the [Synapse Graph-RAG](https://github.com/Ishan007-bot/Synapse)
project. See the main README for architecture, eval numbers, and the full local-dev story.
