# Synapse

A knowledge-graph-augmented Retrieval-Augmented Generation (Graph RAG) system.
Ingests documents (a curated Wikipedia corpus on the modern AI field), builds a
Neo4j knowledge graph, combines graph traversal with vector search, and answers
multi-hop questions a plain vector RAG can't — with a RAGAS evaluation harness
proving the improvement.

See [PLAN.md](PLAN.md) for the full roadmap and architecture.

**Status:** scaffold + Neo4j + swappable Groq/Gemini LLM layer in place;
document ingestion working (Wikipedia AI-field corpus chunked into Neo4j).

---

## Stack
- **Backend:** Python 3.11+, FastAPI (later phases)
- **Graph + Vector DB:** Neo4j 5 (native vector index)
- **Embeddings:** sentence-transformers (local, free) — added in Phase 2
- **LLM:** Groq (Llama 3.3 70B) or Gemini, behind a swappable interface
- **Frontend:** Next.js (Phase 7)

---

## Phase 0 — Setup

### 1. Start Neo4j
```bash
docker compose up -d
```
Neo4j Browser: http://localhost:7474  (user `neo4j`, password `graphrag123`)

### 2. Configure environment
```bash
cp .env.example .env
```
Then fill in **at least one** API key in `.env`:
- Groq (default): get a free key at https://console.groq.com/keys
- Gemini: get a free key at https://aistudio.google.com/apikey

### 3. Create the Python environment & install
```bash
# from the project root
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# macOS / Linux
# source .venv/bin/activate

python -m pip install --upgrade pip
pip install -e backend
```

### 4. Run the smoke test
```bash
cd backend
python -m app.smoke
```
Expected output:
```
=== Synapse (Graph RAG) — Phase 0 smoke test ===
[LLM] provider = groq
[LLM] OK  -> Hello! ...
[Neo4j] OK  -> {'project': 'graph-rag', 'ok': 1}
All checks passed.
```

---

## Ingest the corpus

With Neo4j running, fetch the Wikipedia AI-field corpus, chunk it, and store it
as `(:Document)-[:HAS_CHUNK]->(:Chunk)`:
```bash
cd backend
python -m app.ingestion.pipeline --reset      # full corpus (~27 articles)
python -m app.ingestion.pipeline --limit 3     # quick test with 3 articles
```
Options: `--chunk-size`, `--chunk-overlap`, `--reset` (wipe docs/chunks first).
The article list lives in [backend/app/ingestion/corpus.py](backend/app/ingestion/corpus.py).

Run the tests:
```bash
cd backend && python -m pytest -q
```

---

## Project layout
```
.
├── docker-compose.yml      # Neo4j
├── .env.example            # config template
├── PLAN.md                 # full roadmap
└── backend/
    ├── pyproject.toml
    ├── tests/              # pytest (chunker, ...)
    └── app/
        ├── config.py       # settings from .env
        ├── smoke.py        # connectivity check
        ├── llm/            # provider abstraction (groq, gemini)
        ├── db/             # neo4j client
        └── ingestion/      # corpus, wikipedia loader, chunker, pipeline
```
