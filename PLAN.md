# Graph RAG — Project Plan

A resume-grade **Graph RAG** application: ingest documents, build a knowledge graph,
combine graph traversal with vector search, and answer multi-hop questions an LLM
couldn't answer from plain chunk retrieval — then *prove* it's better than naive RAG
with a real evaluation harness.

**Target role:** AI/ML Engineer
**Headline for resume:** *"Built a Graph RAG system that improved multi-hop answer
faithfulness by X% over a vector-only RAG baseline (measured with RAGAS), using a
Neo4j knowledge graph, hybrid retrieval, and a swappable Groq/Gemini LLM layer."*

---

## 1. What is Graph RAG (and why it impresses)

Naive RAG: chunk text → embed → vector-similarity search → stuff top-k chunks into the
prompt. It fails on **multi-hop** questions ("How is person A connected to event B?")
because the answer is spread across chunks that aren't individually similar to the query.

Graph RAG adds a structured layer:
1. **Extract** entities + relationships from documents with an LLM.
2. **Store** them as a knowledge graph (nodes = entities, edges = relationships).
3. At query time, **retrieve** both relevant text chunks (vectors) *and* a relevant
   subgraph (graph traversal), then feed both to the LLM.
4. Multi-hop questions become graph walks — the structure carries the reasoning.

This single project lets you demonstrate the full AI stack: embeddings, vector search,
chunking strategy, LLM structured extraction, prompt engineering, retrieval fusion,
and quantitative evaluation.

---

## 2. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Language (backend) | **Python 3.11+** | Standard for AI/ML |
| API framework | **FastAPI** | Async, auto Swagger docs, typed |
| Graph + Vector DB | **Neo4j 5** (native vector index) | One DB for graph *and* vectors — clean & impressive. Free local via Docker, or AuraDB free tier |
| Embeddings | **sentence-transformers** (`BAAI/bge-small-en-v1.5`) | Free, local, no rate limits, shows ML knowledge |
| LLM (generation + extraction) | **Groq** (Llama 3.3 70B) primary, **Gemini** fallback | Both free tier; behind a swappable provider interface |
| Orchestration | **Mostly custom** + light LangChain utils | Custom pipeline shows you understand the internals (better for ML interviews than "I called a black box") |
| Doc parsing | `pypdf`, `python-docx`, plain text | Ingest PDFs/docs/markdown |
| Evaluation | **RAGAS** | Faithfulness, answer relevancy, context precision/recall — the resume differentiator |
| Frontend | **Next.js + TypeScript** | Modern, recruiter-recognized |
| Graph viz | **react-force-graph** (or Cytoscape.js) | Interactive, looks great in a demo |
| Chat UI | Custom React + streaming (SSE) | Token streaming = polished feel |
| Packaging | **Docker Compose** (neo4j + api + web) | One command to run everything |
| Deploy (optional) | Render / Railway / Fly.io free tier | Live demo link on resume |
| Testing | `pytest` (backend), basic component tests | Shows engineering rigor |

**Cost: ~$0.** Groq + Gemini free tiers, local embeddings, local Neo4j.

---

## 3. Architecture

```
                ┌─────────────────────────────────────────────┐
                │                 Next.js Web                  │
                │   Chat panel  ◄──SSE──►   Graph visualization │
                └───────────────┬─────────────────────────────┘
                                │ REST / SSE
                ┌───────────────▼─────────────────────────────┐
                │                  FastAPI                     │
                │  /ingest   /query   /graph   /eval           │
                ├──────────────────────────────────────────────┤
                │  Ingestion pipeline   │   Query pipeline      │
                │  • parse + chunk      │   • embed query       │
                │  • embed chunks       │   • vector search     │
                │  • entity/rel extract │   • graph traversal   │
                │  • write to Neo4j     │   • context fusion    │
                │                       │   • LLM answer (stream)│
                ├───────────────────────┴──────────────────────┤
                │  LLM Provider abstraction (Groq | Gemini)     │
                │  Embedding model (sentence-transformers)      │
                └───────────────┬──────────────────────────────┘
                                │ Cypher + vector index
                        ┌───────▼────────┐
                        │     Neo4j      │  nodes=entities, edges=rels,
                        │ (graph+vector) │  :Chunk nodes hold text+embedding
                        └────────────────┘
```

---

## 4. Phased Plan

Each phase ends with something runnable. Build naive RAG **first**, then layer the graph
on top — so you always have a working app and a baseline to measure against.

### Phase 0 — Foundations & Setup  *(~1-2 days)*
- Repo scaffold: `backend/`, `frontend/`, `docker-compose.yml`, `.env.example`, `README.md`.
- `docker-compose` with Neo4j; verify connection from Python.
- Provider abstraction: `LLMProvider` interface + `GroqProvider`, `GeminiProvider`.
- Get free API keys (Groq console, Google AI Studio).
- **Done when:** `python -m backend.smoke` answers "hello" via Groq, and Neo4j browser opens.

### Phase 1 — Ingestion & Chunking  *(~2-3 days)*
- Document loaders (PDF/txt/md).
- Chunking: recursive character splitter with overlap; make `chunk_size`/`overlap` configurable.
- Store `:Chunk` nodes in Neo4j with `text`, `source`, `chunk_index` metadata.
- Pick your **demo corpus** (see §6).
- **Done when:** `/ingest` loads docs and you can count chunks in Neo4j.

### Phase 2 — Vector Retrieval (Naive RAG baseline)  *(~2-3 days)*
- Embed chunks with sentence-transformers; store vectors on `:Chunk` nodes.
- Create Neo4j **vector index**; implement top-k cosine search.
- Simple `/query` → retrieve chunks → prompt → LLM answer (with citations).
- **Done when:** you have a working chatbot over your docs. *This is your baseline.*

### Phase 3 — Knowledge Graph Construction  *(~4-5 days, the core ML work)*
- LLM-based **entity + relationship extraction** with a structured-output prompt
  (JSON schema: entities `{name,type}`, relations `{source,target,type}`).
- **Entity resolution / dedup:** normalize names, merge aliases (embedding similarity
  + string matching) so "NYC"/"New York City" become one node.
- Write `:Entity` nodes and typed relationships to Neo4j; link entities back to the
  `:Chunk` nodes they came from (`MENTIONED_IN`).
- **Done when:** Neo4j browser shows a real knowledge graph from your corpus.

### Phase 4 — Graph + Hybrid Retrieval  *(~3-4 days)*
- Map query → seed entities (NER or embedding match against entity names).
- **Graph traversal:** expand N hops around seed entities, collect subgraph.
- **Fusion:** combine vector chunks + subgraph facts into one context block;
  rank/dedup; respect a token budget.
- (Optional, advanced) community detection (Leiden) + community summaries for
  "global" questions — the Microsoft GraphRAG idea, kept optional.
- **Done when:** a multi-hop question your baseline failed now answers correctly.

### Phase 5 — Generation & Prompt Engineering  *(~2 days)*
- Answer prompt that uses graph facts + chunks, cites sources, says "I don't know" when unsupported.
- **Streaming** responses (SSE) to the frontend.
- Return the retrieved subgraph alongside the answer (for visualization).
- **Done when:** answers stream, cite sources, and ship a subgraph payload.

### Phase 6 — API Layer  *(~2 days)*
- Endpoints: `POST /ingest`, `POST /query` (stream), `GET /graph` (full/subgraph),
  `POST /eval`. Pydantic models, error handling, CORS.
- **Done when:** Swagger docs at `/docs` exercise the whole system.

### Phase 7 — Frontend  *(~4-5 days)*
- Next.js app: chat panel with streaming tokens + source citations.
- **Graph visualization** (react-force-graph): show the full KG and highlight the
  subgraph used to answer the current question. Click a node → see facts.
- Upload/ingest UI.
- **Done when:** a stranger can open it, ask a question, and watch the graph light up.

### Phase 8 — Evaluation (the resume differentiator)  *(~2-3 days)*
- Build a small eval set of Q/A pairs (include several multi-hop questions).
- Run **RAGAS**: faithfulness, answer relevancy, context precision, context recall.
- **Compare Naive RAG (Phase 2) vs Graph RAG (Phase 4)** on the same questions.
- Produce a results table + chart. *This is the slide that gets you the interview.*
- **Done when:** you have numbers showing where Graph RAG wins (and honestly, where it doesn't).

### Phase 9 — Polish & Deploy  *(~2-3 days)*
- Strong README: problem, architecture diagram, GIF demo, eval results, "how to run".
- Docker Compose one-command startup; seed script for the demo corpus.
- Optional: deploy live (Render/Railway) + put the link on your resume.
- Add a few `pytest` tests (chunking, extraction parsing, retrieval).
- **Done when:** `docker compose up` gives a working app, README sells it.

**Total: roughly 4–6 weeks part-time.** Phases 0→2 give you a working RAG in week one;
everything after is the "graph" differentiation.

---

## 5. Skills this project demonstrates (map to resume bullets)
- Embeddings & vector search (sentence-transformers, Neo4j vector index)
- Chunking strategy & retrieval tuning
- LLM structured extraction & prompt engineering
- Knowledge graph construction + entity resolution
- Hybrid retrieval / context fusion
- RAG evaluation with RAGAS (quantitative, not vibes)
- Provider abstraction (Groq/Gemini), streaming, FastAPI
- Full-stack delivery + Docker + (optional) deployment

---

## 6. Choosing a demo corpus
Graph RAG shines where **relationships across documents** matter. Good options:
- A connected set of Wikipedia articles (e.g., a historical period, a company + its
  people/products, a fictional universe).
- A novel or screenplay (characters & their relationships → fun, visual graph).
- Research papers in one subfield (authors, methods, citations).
- Company/org docs (people, teams, projects).

Pick one where you can write **multi-hop questions** ("Which character betrayed the ally
of X?", "What method did the co-author of paper Y also use?"). Those are the questions
that make Graph RAG beat the baseline in your eval.

---

## 7. Suggested repo structure
```
graph-rag/
├── docker-compose.yml
├── .env.example
├── README.md
├── PLAN.md
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI
│   │   ├── config.py
│   │   ├── llm/               # provider abstraction (groq, gemini)
│   │   ├── embeddings.py
│   │   ├── ingestion/         # loaders, chunking
│   │   ├── graph/             # extraction, entity resolution, neo4j client
│   │   ├── retrieval/         # vector, graph, hybrid fusion
│   │   ├── generation.py
│   │   └── eval/              # ragas harness + datasets
│   ├── tests/
│   └── pyproject.toml
└── frontend/
    ├── app/                   # Next.js
    ├── components/            # Chat, GraphView, Upload
    └── package.json
```

---

## 8. Risks & how we handle them
- **LLM extraction is noisy** → constrain with JSON schema, validate, retry; keep entity
  types to a small controlled list.
- **Free-tier rate limits (Groq/Gemini)** → batch + cache extraction results; embeddings
  are local so ingestion isn't rate-limited.
- **Graph gets messy / huge** → entity resolution + limit traversal depth + token budget.
- **Scope creep** → community detection, multi-user auth, and live deploy are all *optional*.
  Ship Phases 0–8 first.
```
```
