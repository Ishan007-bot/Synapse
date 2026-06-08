/* API client for the Synapse FastAPI backend. */
import type { IngestResponse, NaiveAnswer, RAGAnswer, Stats, SubgraphPayload } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => jsonFetch<{ status: string }>("/health"),

  stats: () => jsonFetch<Stats>("/stats"),

  query: (question: string, hops = 2, k_chunks = 5) =>
    jsonFetch<RAGAnswer>("/query", {
      method: "POST",
      body: JSON.stringify({ question, hops, k_chunks }),
    }),

  queryNaive: (question: string, k = 5) =>
    jsonFetch<NaiveAnswer>("/query/naive", {
      method: "POST",
      body: JSON.stringify({ question, k }),
    }),

  fullGraph: (limit_nodes = 120, min_degree = 1) =>
    jsonFetch<SubgraphPayload>(
      `/graph?limit_nodes=${limit_nodes}&min_degree=${min_degree}`,
    ),

  uploadFiles: async (files: File[]): Promise<IngestResponse> => {
    // FormData sets its own Content-Type with a boundary — don't override it,
    // or the multipart body becomes unparseable on the server.
    const form = new FormData();
    for (const f of files) form.append("files", f);
    const res = await fetch(`${API_BASE}/ingest`, { method: "POST", body: form });
    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      throw new Error(`${res.status} ${res.statusText} ${detail}`);
    }
    return (await res.json()) as IngestResponse;
  },
};

export { API_BASE };
