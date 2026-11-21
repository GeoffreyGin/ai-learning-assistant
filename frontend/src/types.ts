// Types mirroring app/api/schemas.py response models.

export interface DocumentMeta {
  id: number;
  title: string;
  file_type: string;
  created_at: string;
}

export interface SourceChunk {
  id: number;
  document_id: number;
  text: string;
  page_number: number | null;
  chunk_index: number;
}

export interface DocumentDetail extends DocumentMeta {
  chunks: SourceChunk[];
}

export interface KnowledgeSummary {
  document_id: number;
  overview: string;
  key_concepts: string[];
  claims: { text: string; source_chunk_id: number }[];
}

export interface UploadResult {
  document: DocumentMeta;
  chunk_count: number;
  extracted_mentions: number;
  new_concept_count: number;
  new_relationship_count: number;
  llm_fallback_chunks: number;
}

export interface Concept {
  id: number;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface ConceptDetail extends Concept {
  source_chunks: SourceChunk[];
}

export interface Prerequisite {
  concept: Concept;
  distance: number;
}

export interface RelatedConcept {
  concept: Concept;
  relation_type: string;
  confidence: number;
}

export interface GraphNode {
  id: number;
  name: string;
  mastery: number | null;
}

export interface GraphEdge {
  source: number;
  target: number;
  type: string;
  confidence: number;
  evidence_source_id: number | null;
}

export interface Graph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface GapEntry {
  concept: Concept;
  distance: number;
  status: string;
  mastery: number | null;
  evidence_count: number;
  has_source_evidence: boolean;
}

export interface GapReport {
  target: Concept;
  prerequisites: GapEntry[];
  gaps: GapEntry[];
}

export interface RecommendedTopic {
  concept: Concept;
  status: string;
  mastery: number | null;
  evidence_count: number;
  reason: string;
}

export interface AgentAction {
  tool: string;
  detail: string;
}

export interface PendingQuestion {
  attempt_id: number;
  concept_id: number;
  concept_name: string;
  question: string;
  worked_steps?: string[];
  hint_count?: number;
}

export interface Course { id: number; name: string }
export interface TutorOptions {
  document_id?: number;
  concept_id?: number;
  attempt_id?: number;
  hint?: boolean;
  step?: number;
}
export interface ChatTurn extends ChatResponse { message: string }
export interface CourseProgress {
  total: number; correct: number; untested: number;
  recent: { id: number; concept: string; correct: boolean; question: string; answer: string; hints: number }[];
}

export interface ChatResponse {
  reply: string;
  actions: AgentAction[];
  pending: PendingQuestion | null;
}

export interface LogEntry {
  timestamp: string;
  tool: string;
  detail: string;
}

export const STATUS_MASTERED = "MASTERED";
export const STATUS_WEAK = "WEAK";
export const STATUS_UNKNOWN = "UNKNOWN";

export const MASTERED_THRESHOLD = 0.8;
export const WEAK_THRESHOLD = 0.4;

export function masteryStatus(mastery: number | null | undefined): string {
  if (mastery === null || mastery === undefined) return STATUS_UNKNOWN;
  if (mastery >= MASTERED_THRESHOLD) return STATUS_MASTERED;
  if (mastery >= WEAK_THRESHOLD) return STATUS_WEAK;
  return STATUS_UNKNOWN;
}
