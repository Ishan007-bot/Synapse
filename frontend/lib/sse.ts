/* SSE streaming over POST.

   Native EventSource doesn't support POST bodies, so we use fetch + a manual
   parser. The backend (FastAPI `/query/stream`) emits three event kinds:

     event: context  data: { sources, chunks, subgraph }
     event: token    data: { text }
     event: done     data: <RAGAnswer>
     event: error    data: { message }

   `streamQuery` calls back into the UI as each event lands.
*/
import { API_BASE } from "./api";
import type { ChunkInfo, RAGAnswer, SourceInfo, SubgraphPayload } from "./types";

export interface StreamHandlers {
  onContext?: (ctx: { sources: SourceInfo[]; chunks: ChunkInfo[]; subgraph: SubgraphPayload }) => void;
  onToken?: (text: string) => void;
  onDone?: (answer: RAGAnswer) => void;
  onError?: (message: string) => void;
}

export async function streamQuery(
  question: string,
  handlers: StreamHandlers,
  opts: { hops?: number; k_chunks?: number; signal?: AbortSignal } = {},
): Promise<void> {
  const res = await fetch(`${API_BASE}/query/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      hops: opts.hops ?? 2,
      k_chunks: opts.k_chunks ?? 5,
    }),
    signal: opts.signal,
  });

  if (!res.ok || !res.body) {
    const detail = await res.text().catch(() => "");
    throw new Error(`stream request failed: ${res.status} ${detail}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE events are separated by a blank line (\n\n).
    let sepIdx: number;
    while ((sepIdx = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, sepIdx);
      buffer = buffer.slice(sepIdx + 2);
      dispatch(raw, handlers);
    }
  }
  // Flush any trailing event.
  if (buffer.trim()) dispatch(buffer, handlers);
}

function dispatch(raw: string, h: StreamHandlers): void {
  let event = "message";
  const dataParts: string[] = [];
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataParts.push(line.slice(5).trimStart());
    }
  }
  if (dataParts.length === 0) return;
  let payload: unknown;
  try {
    payload = JSON.parse(dataParts.join("\n"));
  } catch {
    return; // ignore malformed event
  }
  switch (event) {
    case "context": h.onContext?.(payload as never); break;
    case "token":   h.onToken?.((payload as { text: string }).text); break;
    case "done":    h.onDone?.(payload as RAGAnswer); break;
    case "error":   h.onError?.((payload as { message: string }).message); break;
  }
}
