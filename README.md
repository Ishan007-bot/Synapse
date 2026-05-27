# Synapse

A knowledge-graph-augmented Retrieval-Augmented Generation (Graph RAG) system.
Ingests documents (a curated Wikipedia corpus on the modern AI field), builds a
Neo4j knowledge graph, combines graph traversal with vector search, and answers
multi-hop questions a plain vector RAG can't — with a RAGAS evaluation harness
proving the improvement.

See [PLAN.md](PLAN.md) for the full roadmap and architecture.

**Status:** Phase 0 complete — project scaffold, Neo4j, and the swappable
Groq/Gemini LLM provider layer.

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
=== Graph RAG — Phase 0 smoke test ===
[LLM] provider = groq
[LLM] OK  -> Hello! ...
[Neo4j] OK  -> {'project': 'graph-rag', 'ok': 1}
All checks passed. Phase 0 is wired up correctly.
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
    └── app/
        ├── config.py       # settings from .env
        ├── smoke.py        # Phase 0 verification
        ├── llm/            # provider abstraction (groq, gemini)
        └── db/             # neo4j client
```
