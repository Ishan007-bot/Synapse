// TypeScript mirrors of backend/app/schemas.py — keep these in sync.

export type EntityType =
  | "Person"
  | "Organization"
  | "Model"
  | "Method"
  | "Concept"
  | "Place"
  | "Event"
  | "Field"
  | "Award";

export interface GraphNode {
  id: string;
  name: string;
  type: EntityType | string;
  is_seed: boolean;
  degree: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  predicate: string;
}

export interface SubgraphPayload {
  nodes: GraphNode[];
  edges: GraphEdge[];
  seed_ids: string[];
}

export interface SourceInfo {
  name: string;
  score: number;
  via: "vector" | "entity";
}

export interface ChunkInfo {
  id: string;
  source: string;
  text: string;
  score: number;
}

export interface RAGAnswer {
  answer: string;
  sources: SourceInfo[];
  chunks: ChunkInfo[];
  subgraph: SubgraphPayload;
}

export interface NaiveAnswer {
  answer: string;
  sources: SourceInfo[];
  chunks: ChunkInfo[];
}

export interface Stats {
  documents: number;
  chunks: number;
  chunks_with_vector: number;
  entities: number;
  entities_with_vector: number;
  entity_relations: number;
  mentions: number;
}

export interface IngestSkip {
  file: string;
  reason: string;
}

export interface IngestResponse {
  documents_ingested: number;
  chunks_created: number;
  chunks_embedded: number;
  documents_in_db: number;
  chunks_in_db: number;
  accepted: string[];
  skipped: IngestSkip[];
  note: string;
}
