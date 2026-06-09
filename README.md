# Synapse

> **A Graph RAG system that bridges multi-hop questions a vector-only RAG can't.**
> Builds a knowledge graph from documents, fuses graph traversal with vector
> search, streams cited answers — and proves the improvement with a RAGAS-style eval.

[![python](https://img.shields.io/badge/python-3.12-3776ab)](https://www.python.org/)
[![next.js](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org/)
[![neo4j](https://img.shields.io/badge/Neo4j-5-008cc1)](https://neo4j.com/)
[![license: MIT](https://img.shields.io/badge/license-MIT-green)](#)

---

## The headline

Same questions. Same LLM. Same chunks. The only difference is whether we also
walked the knowledge graph.

| | Naive RAG | **Graph RAG** |
|---|---|---|
| Multi-hop **context recall** | 0.48 | **0.92** |
| Multi-hop faithfulness | 1.00 | 1.00 |
| Multi-hop answer relevancy | 0.83 | 0.88 |

> Graph RAG roughly **doubles context recall** on multi-hop questions while
> keeping faithfulness equal (zero added hallucinations). Full breakdown in
> [`docs/eval-results.md`](docs/eval-results.md).

The killer example — *"Name AI models created by people who previously worked
at OpenAI"*. Naive RAG can't bridge `OpenAI → its alumni → companies they
founded → models those companies built` — three articles, no single chunk has
it. Graph RAG walks the edge `OpenAI -worked-at→ Amodei` and the edge
`Amodei -founded→ Anthropic`, so the answer (Claude, Constitutional AI) appears.

---

## What it looks like

The UI is a neumorphic editorial layout with two synchronized panels:

- **Left** — streaming chat. Tokens arrive over SSE, citations render as pill chips, sources are tagged either *vector* (matched textually) or *graph* (reached via entity traversal).
- **Right** — the live subgraph the system used to answer. Seed entities glow amber, animated particles run along the edges, nodes are colored by type (Person / Organization / Model / Method / …). Click a node for its detail card.

There's a Naive ⟷ Graph mode toggle at the top so you can flip between them
on the same question, and an **Add documents** button in the header that
drag-drops `.pdf` / `.txt` / `.md` files into the corpus (queryable
immediately via `/query`; run `app.graph.build` to also pull them into the
graph). Dark mode included.

---

## Quickstart — one command

```bash
cp .env.example .env       # paste your free Groq key into GROQ_API_KEY
docker compose up -d --build

# Seed the corpus + build the graph (first time only, ~10 min total):
docker compose exec backend python -m app.ingestion.pipeline --embed
docker compose exec backend python -m app.graph.build
```

Open:
- **UI** — http://localhost:3000
- **API docs** (Swagger) — http://localhost:8000/docs
- **Neo4j Browser** — http://localhost:7474 (`neo4j` / `graphrag123`)

Deploying it for free (Neo4j Aura + Hugging Face Spaces + Vercel)?
See [`deploy/DEPLOYMENT.md`](deploy/DEPLOYMENT.md).

Free API keys: [Groq](https://console.groq.com/keys) (recommended, default in `.env`) or
[Gemini](https://aistudio.google.com/apikey).

---

## Architecture

```
                ┌─────────────────────────────────────────────┐
                │              Next.js 14 (frontend)           │
                │   Chat panel  ◄──SSE──►  Force-graph viz     │
                └───────────────┬─────────────────────────────┘
                                │ REST / SSE
                ┌───────────────▼─────────────────────────────┐
                │              FastAPI (backend)               │
                │  /query  /query/stream  /graph  /ingest  …   │
                ├──────────────────────────────────────────────┤
                │  Ingestion         │   Hybrid retrieval      │
                │  • PDF/TXT/MD/Wiki │   • entity-link query   │
                │  • recursive chunk │   • N-hop graph BFS     │
                │  • local embed     │   • vector top-k        │
                │  • Pydantic        │   • fuse chunks+triples │
                │    extraction →    │   • grounded LLM (Groq) │
                │    APOC writes     │                         │
                ├────────────────────┴─────────────────────────┤
                │   LLM provider (Groq / Gemini) — swappable    │
                │   Local sentence-transformers (BGE, 384-dim)  │
                └───────────────┬──────────────────────────────┘
                                │ Cypher + vector index
                        ┌───────▼────────┐
                        │     Neo4j 5    │  nodes=entities, edges=rels,
                        │ (graph+vector) │  :Chunk holds text+embedding
                        └────────────────┘
```

**Two pipelines:**

- **Offline (build-time):** Wikipedia / file → recursive chunker → local BGE
  embeddings → Neo4j vector index → per-document LLM extraction (constrained
  JSON; 9-type ontology) → entity resolution → typed entity-entity edges via
  APOC → `:MENTIONED_IN` backlinks from entities to the chunks they appear in.
- **Online (per query):** entity-link the question → BFS subgraph from those
  seeds → pull chunks the entities mention (via `:MENTIONED_IN`) + plain
  vector top-k → fuse → stream a grounded, cited answer over SSE. The first
  SSE event ships the subgraph immediately so the viz paints before the LLM
  produces its first token.

---

## Stack

| Layer | Pick | Why |
|---|---|---|
| Graph + vector store | **Neo4j 5** native vector index | One DB for both, less plumbing |
| Embeddings | **sentence-transformers** (`BAAI/bge-small-en-v1.5`, 384-dim) | Local, free, no rate limits, CPU-friendly |
| LLM | **Groq** (Llama 3.3 70B for chat, 3.1 8B for high-volume extraction) | Free tier; behind a swappable interface (Gemini also wired) |
| Backend | **FastAPI + uvicorn** | Async-friendly, native SSE, auto Swagger |
| Frontend | **Next.js 14 + react-force-graph-2d** | Recognizable stack; canvas is fast for 600+ nodes |
| Eval | **RAGAS-style** (in-house) | Implemented from the methodology — metric prompts are auditable |
| Packaging | **Docker Compose** (Neo4j + backend + frontend) | One command, three services |

Cost: **~$0** if you stay on the Groq free tier.

---

## Local dev (without Docker)

If you'd rather run things directly on your machine:

<details>
<summary><strong>Python setup</strong></summary>

```bash
cp .env.example .env       # add your Groq key

python -m venv .venv
# Windows PowerShell:  .\.venv\Scripts\Activate.ps1
# macOS / Linux:       source .venv/bin/activate

pip install --upgrade pip
pip install -e backend

# Start Neo4j (just the DB)
docker compose up -d neo4j

# Verify everything is wired up
cd backend && python -m app.smoke
```
</details>

<details>
<summary><strong>Seed the corpus</strong></summary>

```bash
cd backend

# Bundled Wikipedia AI-field corpus:
python -m app.ingestion.pipeline --reset
python -m app.retrieval.build_index
python -m app.graph.build

# …or your own files:
python -m app.ingestion.pipeline --files notes.pdf paper.md --embed
python -m app.ingestion.pipeline --folder ./my-docs --embed
```
</details>

<details>
<summary><strong>Run the API + UI</strong></summary>

```bash
# Backend
cd backend
python -m uvicorn app.api.main:app --reload --port 8000

# Frontend (new shell)
cd frontend
npm install      # first time only
npm run dev      # http://localhost:3000
```
</details>

<details>
<summary><strong>Query via CLI</strong></summary>

```bash
cd backend
python -m app.rag "Who founded OpenAI?"
python -m app.graph_rag --compare "Models created by OpenAI alumni?"
python -m app.graph_rag --stream "..."
python -m app.graph_rag --json "..."          # full RAGAnswer payload
```
</details>

---

## Evaluation

A RAGAS-style harness implemented in-house — four metrics ([judge prompts](backend/app/eval/judge.py)
are plain Python and auditable):

- **Faithfulness** — fraction of atomic claims in the answer supported by context
- **Answer relevancy** — back-generated questions' similarity to the original
- **Context precision** — fraction of retrieved contexts judged relevant
- **Context recall** — fraction of reference facts covered by retrieved context

```bash
cd backend
python -m app.eval.runner                    # all questions, both systems
python -m app.eval.runner --ids mh01,mh02    # specific questions
```

Outputs go to `data/eval/` (gitignored). The snapshot from the 4-question
pilot lives at [`docs/eval-results.md`](docs/eval-results.md).

---

## HTTP API

Full Swagger at http://localhost:8000/docs.

| Endpoint | Purpose |
|---|---|
| `GET /health` | liveness |
| `GET /stats` | corpus + graph counts |
| `GET /graph?limit_nodes=200` | full knowledge graph (top-N by degree) |
| `GET /graph/subgraph?question=…` | retrieved subgraph for a question (no LLM) |
| `POST /query` | Graph RAG → full `RAGAnswer` JSON |
| `POST /query/stream` | Graph RAG over **SSE** (`context` → `token`×N → `done`) |
| `POST /query/naive` | vector-only baseline (for side-by-side comparison) |
| `POST /ingest` | multipart upload of `.pdf` / `.txt` / `.md` |

The `RAGAnswer` shape ([`app/schemas.py`](backend/app/schemas.py)) is the
contract for everything — CLI `--json`, REST, and the frontend all consume
the same Pydantic model:

```jsonc
{ "answer": "…",
  "sources": [{"name", "score", "via"}],
  "chunks":  [{"id", "source", "text", "score"}],
  "subgraph": {
    "nodes": [{"id", "name", "type", "is_seed", "degree"}],
    "edges": [{"source", "target", "predicate"}],
    "seed_ids": ["…"]
  } }
```

---

## Project layout

```
.
├── docker-compose.yml          # Neo4j + backend + frontend
├── .env.example                # config template (LLM keys, Neo4j creds)
├── docs/
│   └── eval-results.md         # committed snapshot of the eval
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── tests/                  # pytest: chunker, schema, resolution
│   └── app/
│       ├── config.py           # env / .env settings
│       ├── smoke.py            # connectivity check
│       ├── console.py          # UTF-8 console helper
│       ├── embeddings.py       # local sentence-transformers
│       ├── generation.py       # prompt + grounded, cited LLM answer (+ stream)
│       ├── rag.py              # Naive RAG orchestrator + CLI
│       ├── graph_rag.py        # Graph RAG orchestrator + CLI
│       ├── schemas.py          # Pydantic response shapes (API contract)
│       ├── llm/                # provider abstraction (groq, gemini) + JSON mode
│       ├── db/                 # neo4j driver wrapper
│       ├── ingestion/          # loaders (PDF/TXT/MD/Wiki), chunker, pipeline
│       ├── graph/              # entity/relation extraction, resolution, store
│       ├── retrieval/          # vector + entity indexes, linker, traversal, hybrid
│       ├── eval/               # RAGAS-style metrics, dataset, runner
│       └── api/                # FastAPI app (lifespan, CORS, endpoints, SSE)
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── app/                    # Next.js App Router (page, layout, globals)
    ├── components/             # Header, Hero, AnswerPanel, GraphPanel,
    │                           # ModeToggle, ThemeToggle, UploadButton
    ├── hooks/                  # useScrollReveal (IntersectionObserver)
    └── lib/                    # api client, SSE parser, TS types mirroring schemas
```

---

## Run the tests

```bash
cd backend && python -m pytest -q
```

---

## License

MIT.
