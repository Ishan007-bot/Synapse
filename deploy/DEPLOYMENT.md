# Deploying Synapse for free

Three-tier topology, **$0/month**:

| Layer | Where | Free-tier note |
|---|---|---|
| **Neo4j** (graph + vector DB) | [Neo4j AuraDB Free](https://neo4j.com/cloud/platform/aura-graph-database/) | 200K nodes / 400K rels; pauses after 72h idle (resumes in ~30s) |
| **Backend** (FastAPI) | [Hugging Face Spaces](https://huggingface.co/spaces) — Docker SDK | 16 GB RAM, stays warm; ~5 min to build the image once |
| **Frontend** (Next.js) | [Vercel](https://vercel.com) | Auto-deploy from GitHub, perfect Next.js support |

The order matters: **Aura → backend → frontend**. Each later step needs the
URL of the previous one.

---

## 0. Prep

You need:
- A **Hugging Face** account ([sign up](https://huggingface.co/join))
- A **Vercel** account ([sign up with GitHub](https://vercel.com/signup))
- A **Neo4j Aura** account ([sign up](https://console.neo4j.io/))
- Your existing **GitHub repo** for this project pushed to a remote

You already have:
- A working **Groq API key** in your local `.env`
- The full corpus locally (27 docs, 1987 chunks, 638 entities)

---

## 1. Spin up Neo4j AuraDB Free

1. Go to https://console.neo4j.io → **New Instance** → **AuraDB Free**
2. Pick a region close to where the backend will run
   (Hugging Face hosts on AWS us-east — `us-east-1` keeps latency low)
3. **Save the auto-generated password** when it shows it once — you can't recover it
4. Wait until the instance is **Running**
5. From the instance details, copy:
   - **Connection URI** — looks like `neo4j+s://abc123.databases.neo4j.io`
   - **Username** — always `neo4j`
   - **Password** — the one Aura generated

### Seed the cloud Neo4j with your local data

Point your **local** backend at Aura temporarily, then run the seed commands.

In `.env` (locally — *don't commit this*):
```bash
NEO4J_URI=neo4j+s://<your-aura-id>.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=<the-aura-password>
```

Then from the project root:
```bash
# Activate the venv if you haven't:  .\.venv\Scripts\Activate.ps1

cd backend

# 1. Push the Wikipedia corpus + embed chunks  (~5 min, no LLM cost)
python -m app.ingestion.pipeline --reset --embed

# 2. Push the extracted graph from local cache  (~1 min, ZERO LLM calls —
#    the extraction cache from your local Phase-3 run does all the work)
python -m app.graph.build

# 3. Build the entity vector index
python -m app.retrieval.build_index
```

The graph cache lives in `data/cache/extractions/`. Because the cache key is
the doc title and your titles haven't changed, step 2 will be ~100% cache
hits and won't burn any Groq quota.

After seeding, **revert your local `.env`** back to `NEO4J_URI=bolt://localhost:7687`
so local dev still works against your Docker Neo4j.

---

## 2. Deploy the backend to Hugging Face Spaces

### 2a. Create the Space
1. Go to https://huggingface.co/new-space
2. **Owner**: your account
3. **Space name**: `synapse-backend` (or anything — this becomes the URL)
4. **License**: MIT
5. **SDK**: **Docker** → **Blank**
6. **Visibility**: Public
7. Click **Create Space**

You'll land on a page with a `git clone` URL like
`https://huggingface.co/spaces/<username>/synapse-backend`.

### 2b. Push the backend code to the Space

Clone the (empty) Space repo locally and copy the right files in:

```bash
# Pick any working directory outside the main repo
cd ~/somewhere

git clone https://huggingface.co/spaces/<username>/synapse-backend
cd synapse-backend

# Copy backend code in (note: contents of backend/, not the folder itself)
cp -r <path-to-synapse-repo>/backend/app .
cp <path-to-synapse-repo>/backend/pyproject.toml .

# Copy the HF Space metadata + Dockerfile (these go at the root of the Space)
cp <path-to-synapse-repo>/deploy/huggingface-space/README.md .
cp <path-to-synapse-repo>/deploy/huggingface-space/Dockerfile .

# You may want a .gitignore so build artifacts don't get committed
echo -e "__pycache__/\n*.egg-info/\n.pytest_cache/\n.venv/\ndata/\n" > .gitignore

# Push
git add .
git commit -m "Initial deploy"
git push
```

> If `git push` asks for credentials: use your HF **username** and a
> [HF access token](https://huggingface.co/settings/tokens) (Write scope) as
> the password.

Once you push, the Space starts building. **First build takes ~5–8 minutes**
(it installs torch, transformers, sentence-transformers, and pre-downloads
the BGE model). You can watch progress on the Space page → **Logs** tab.

### 2c. Set the runtime secrets

In your Space → **Settings → Variables and secrets** → **New secret** for
each row:

| Name | Value | Why |
|---|---|---|
| `GROQ_API_KEY` | `gsk_…` (your Groq key) | LLM access |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Chat model |
| `LLM_PROVIDER` | `groq` | Default provider |
| `NEO4J_URI` | `neo4j+s://<id>.databases.neo4j.io` | From step 1 |
| `NEO4J_USER` | `neo4j` | Aura username |
| `NEO4J_PASSWORD` | (your Aura password) | From step 1 |
| `ALLOWED_ORIGINS` | `https://placeholder.vercel.app` | We'll update after step 3 |

After saving the secrets, **restart the Space** (Settings → "Factory reboot") so it picks them up.

### 2d. Verify the backend

Your Space URL is `https://<username>-synapse-backend.hf.space`. Smoke-check:

```bash
curl https://<username>-synapse-backend.hf.space/health
# {"status":"ok","service":"synapse"}

curl https://<username>-synapse-backend.hf.space/stats
# {"documents":27,"chunks":1987,…}
```

Swagger docs are at `https://<username>-synapse-backend.hf.space/docs`.

---

## 3. Deploy the frontend to Vercel

### 3a. Connect the repo
1. Go to https://vercel.com/new
2. Import your GitHub repo (you'll need to authorize Vercel to read it first time)
3. **Root Directory**: `frontend`
4. **Framework Preset**: Next.js (auto-detected)
5. **Build & Output Settings**: leave defaults
6. **Environment Variables**:

| Name | Value |
|---|---|
| `NEXT_PUBLIC_API_BASE` | `https://<username>-synapse-backend.hf.space` |

7. Click **Deploy**

First build takes ~2 minutes. You'll get a URL like
`https://synapse-<random>.vercel.app`.

### 3b. Set up CORS so the browser can talk to the backend
Go back to your HF Space → **Settings → Variables and secrets** → edit
**ALLOWED_ORIGINS** to the actual Vercel URL:

```
https://synapse-<random>.vercel.app
```

Restart the Space. Now the frontend can call the backend.

---

## 4. Try it

Open your Vercel URL in a browser. You should see:
- The header stats chips populate (`27 docs · 1987 chunks · 638 entities · 534 relations`)
- The "online" badge turn green
- Sample questions you can click

Ask *"Name AI models created by people who previously worked at OpenAI"* and
watch the subgraph paint on the right, then the answer stream into the left.

---

## 5. Pin it to your resume

Add the Vercel URL to your resume. Recruiters click → they land on the live
demo with stats already loaded.

---

## Troubleshooting

**The Space build fails on `pip install`**
→ The `pyproject.toml` is probably missing or you copied `backend/` instead
of `backend/`'s *contents*. The Dockerfile expects `pyproject.toml` and `app/`
at the Space repo root.

**CORS errors in the browser console**
→ `ALLOWED_ORIGINS` doesn't include the exact Vercel URL (https + no trailing slash).

**Aura times out / 503**
→ Aura Free pauses after 72h of no traffic. Just hit the URL once; it'll wake.

**Backend returns 500 on `/query`**
→ Most often a missing/wrong Aura credential. Check the Space logs.

**Vercel build fails on `output: "standalone"`**
→ Make sure the Root Directory is set to `frontend` so Vercel sees that
directory's `next.config.mjs`.

---

## Optional cleanups

- **Custom domain on Vercel** — Settings → Domains → add (free if your registrar supports it)
- **Lock CORS further** — keep only the production Vercel URL in `ALLOWED_ORIGINS`; remove the placeholder
- **HF Space privacy** — if you want it private, switch under Settings; you'll need to embed a token in the frontend's calls (not recommended for a portfolio link)
