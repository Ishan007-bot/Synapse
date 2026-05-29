# Synapse

A knowledge-graph-augmented Retrieval-Augmented Generation (Graph RAG) system.
Ingests documents (a curated Wikipedia corpus on the modern AI field), builds a
Neo4j knowledge graph, combines graph traversal with vector search, and answers
multi-hop questions a plain vector RAG can't — with a RAGAS evaluation harness
proving the improvement.

See [PLAN.md](PLAN.md) for the full roadmap and architecture.

**Status:** end-to-end Graph RAG working. Ingestion → local embeddings → Neo4j
vector index → LLM-based entity & relation extraction → 638-entity / 534-relation
knowledge graph → hybrid retrieval (vectors + graph traversal) → grounded
answers with citations. Naive-RAG baseline kept for the upcoming RAGAS
comparison.

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

## Build the knowledge graph

LLM-extracts entities & relations per document, dedupes them, and writes the
graph into Neo4j. The `data/cache/extractions/` directory caches per-doc
extractions so re-runs are free:
```bash
cd backend
python -m app.graph.build                    # full corpus
python -m app.graph.build --limit 3          # quick test
python -m app.graph.build --reset            # wipe entities/relations first
python -m app.graph.build --provider gemini  # override LLM for this run
```

After the graph build, rerun `python -m app.retrieval.build_index` to also
embed the new entity names for the linker.

## Ask questions (Graph RAG)

Hybrid retrieval: vector chunks + entity linking + N-hop graph traversal +
chunks linked via `:MENTIONED_IN`. Multi-hop questions that fail in naive RAG
work here:
```bash
cd backend
python -m app.graph_rag "Name AI models created by people who worked at OpenAI."
python -m app.graph_rag --compare "..."        # naive vs graph side by side
python -m app.graph_rag --retrieve-only "..."  # show context, no LLM
python -m app.graph_rag --hops 3 "..."         # deeper traversal
python -m app.graph_rag --stream "..."         # token-by-token output
python -m app.graph_rag --json "..."           # structured payload (answer + sources + subgraph)
```

The `--json` shape (defined in [app/schemas.py](backend/app/schemas.py)) is the contract for the upcoming FastAPI + Next.js layers:
```jsonc
{ "answer": "...",
  "sources": [{"name", "score", "via"}],
  "chunks":  [{"id", "source", "text", "score"}],
  "subgraph": {
    "nodes": [{"id", "name", "type", "is_seed", "degree"}],
    "edges": [{"source", "target", "predicate"}],
    "seed_ids": ["..."]
  } }
```

## Run the HTTP API

The same Graph RAG core, exposed over HTTP for the upcoming Next.js frontend
(and for direct curl/Postman use). **Make sure the `.venv` is activated first**
(your global Python doesn't have these deps):
```bash
# from the project root:
# Windows PowerShell:   .\.venv\Scripts\Activate.ps1
# macOS / Linux:        source .venv/bin/activate

cd backend
python -m uvicorn app.api.main:app --reload --port 8000
```
…or without activating, call the venv's interpreter directly:
```bash
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.api.main:app --reload --port 8000   # Windows
# ../.venv/bin/python -m uvicorn app.api.main:app --reload --port 8000          # macOS/Linux
```
Then open http://localhost:8000/docs for interactive Swagger UI.

| Endpoint | What |
|---|---|
| `GET /health` | liveness |
| `GET /stats` | corpus + graph counts |
| `GET /graph?limit_nodes=200` | full graph (top-N by degree) |
| `GET /graph/subgraph?question=…` | retrieved subgraph for a question (no LLM) |
| `POST /query` | Graph RAG, returns full `RAGAnswer` JSON |
| `POST /query/stream` | Graph RAG over **SSE**: `context` → many `token` → `done` |
| `POST /query/naive` | vector-only baseline (for the comparison demo) |

## Run the frontend

A Next.js + react-force-graph-2d UI: neumorphic editorial design, streaming
chat, an interactive force-directed knowledge graph that lights up with each
question's subgraph, and a toggle to compare Naive vs Graph RAG side by side.
```bash
cd frontend
npm install          # first time only
npm run dev          # http://localhost:3000
```
The frontend expects the FastAPI backend on `http://localhost:8000`. Set
`NEXT_PUBLIC_API_BASE` if you run it elsewhere.

## Evaluate Graph RAG vs Naive RAG

A RAGAS-style evaluation (Es et al. 2023) implemented in-house using the same
LLM provider as the judge — no `ragas` package dependency, full transparency
into the metric prompts (see [backend/app/eval/judge.py](backend/app/eval/judge.py)).
Four metrics, scored 0–1:

- **Faithfulness** — fraction of atomic claims in the answer supported by context
- **Answer relevancy** — back-generated questions' semantic similarity to the original
- **Context precision** — fraction of retrieved context items judged relevant
- **Context recall** — fraction of reference-answer facts covered by retrieved context

The eval set ([backend/app/eval/dataset.py](backend/app/eval/dataset.py)) is six
**multi-hop** questions (where Graph RAG should shine) and three **single-hop**
questions (sanity check — graph layer shouldn't degrade easy cases).

```bash
cd backend
python -m app.eval.runner                  # all questions, both systems
python -m app.eval.runner --ids mh01,mh02   # specific questions
python -m app.eval.runner --no-cache        # bypass judgment cache
```
Results land in `data/eval/results.json` + `data/eval/report.md`
(both gitignored — commit a hand-picked snapshot if the numbers belong in the repo).

**Snapshot results:** [docs/eval-results.md](docs/eval-results.md)

Headline (4-question pilot, multi-hop subset):

| | Naive RAG | Graph RAG |
|---|---|---|
| Faithfulness | 1.00 | 1.00 |
| Answer relevancy | 0.83 | 0.88 |
| **Context recall** | **0.48** | **0.92** |

Graph RAG roughly doubles context recall on multi-hop questions — the structured graph
brings in chunks from articles vector similarity alone never reaches — while keeping
faithfulness equal (no extra hallucination). Context precision is lower for Graph RAG
(0.54 vs 0.90), the expected cost of broader retrieval.

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
        ├── llm/            # provider abstraction (groq, gemini) + JSON mode
        ├── db/             # neo4j client
        ├── ingestion/      # corpus, wikipedia loader, chunker, pipeline
        ├── graph/          # entity/relation extraction, resolution, neo4j writes
        ├── retrieval/      # chunk + entity vector indexes, entity linker, traversal, hybrid
        ├── graph_rag.py    # Graph RAG orchestrator + CLI
        ├── schemas.py      # Pydantic response shapes (API contract)
        └── api/            # FastAPI app (lifespan, CORS, endpoints, SSE)
```
