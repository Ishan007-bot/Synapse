# Synapse

A knowledge-graph-augmented Retrieval-Augmented Generation (Graph RAG) system.
Ingests documents (a curated Wikipedia corpus on the modern AI field), builds a
Neo4j knowledge graph, combines graph traversal with vector search, and answers
multi-hop questions a plain vector RAG can't — with a RAGAS evaluation harness
proving the improvement.

See [PLAN.md](PLAN.md) for the full roadmap and architecture.

**Status:** ingestion + local embeddings + Neo4j vector search + a working
naive-RAG baseline (vector retrieval → grounded, cited LLM answers). Knowledge
graph construction and hybrid retrieval come next.

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

## Build the vector index

Embed every chunk (local sentence-transformers) and create the Neo4j vector index:
```bash
cd backend
python -m app.retrieval.build_index     # first run downloads the model (~130MB)
```

## Ask questions (naive RAG baseline)

Needs an LLM key in `.env`. Embeds the question, retrieves top-k chunks, and
generates a grounded, cited answer:
```bash
cd backend
python -m app.rag "Who founded OpenAI?"
python -m app.rag                            # interactive
python -m app.rag --retrieve-only "..."      # show chunks only, no LLM (no key needed)
```

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
        ├── console.py      # UTF-8 console helper
        ├── embeddings.py   # local sentence-transformers embedder
        ├── generation.py   # prompt + grounded, cited LLM answer
        ├── rag.py          # naive RAG orchestrator + query CLI
        ├── llm/            # provider abstraction (groq, gemini)
        ├── db/             # neo4j client
        ├── ingestion/      # corpus, wikipedia loader, chunker, pipeline
        └── retrieval/      # vector index build + top-k search
```
