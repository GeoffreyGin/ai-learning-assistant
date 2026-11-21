import type {
  ChatResponse,
  Concept,
  ConceptDetail,
  DocumentDetail,
  DocumentMeta,
  GapReport,
  Graph,
  KnowledgeSummary,
  LogEntry,
  Prerequisite,
  RecommendedTopic,
  RelatedConcept,
  UploadResult,
  Course, ChatTurn, TutorOptions, CourseProgress,
} from "./types";

// A course belongs to this tab's URL, including after a reload or a shared link.
export const courseId = new URLSearchParams(location.search).get("course") || "0";
const coursePrefix = courseId === "0" ? "" : `/courses/${encodeURIComponent(courseId)}/workspace`;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    const globalEndpoint = path === "/courses" || path === "/health";
    response = await fetch((globalEndpoint ? "" : coursePrefix) + path, init);
  } catch {
    throw new Error(
      "Cannot connect to the server (http://localhost:8000)— Start the server: python -m uvicorn app.main:app",
    );
  }
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    const text = await response.text();
    try {
      const body = JSON.parse(text);
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // Non-JSON error body (e.g. the Vite dev proxy's plain-text 500 when the
      // backend is down) — surface the body so the real cause is visible.
      if (text.trim()) detail = text.trim().slice(0, 200);
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  courses: () => request<Course[]>("/courses"),
  createCourse: (name: string) => request<Course>("/courses", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }),
  }),
  lectureTopics: (id: number) => request<{ id: number; name: string }[]>(`/documents/${id}/topics`),
  history: () => request<ChatTurn[]>("/agent/history"),
  progress: () => request<CourseProgress>("/learning/progress"),

  listDocuments: () => request<DocumentMeta[]>("/documents"),
  getDocument: (id: number) => request<DocumentDetail>(`/documents/${id}`),
  summarizeDocument: (id: number) =>
    request<KnowledgeSummary>(`/documents/${id}/knowledge-summary`, { method: "POST" }),
  uploadDocument: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<UploadResult>("/documents/upload", { method: "POST", body: form });
  },

  listConcepts: () => request<Concept[]>("/concepts"),
  getConcept: (id: number) => request<ConceptDetail>(`/concepts/${id}`),
  getPrerequisites: (id: number) => request<Prerequisite[]>(`/concepts/${id}/prerequisites`),
  getRelated: (id: number) => request<RelatedConcept[]>(`/concepts/${id}/related`),
  getGraph: () => request<Graph>("/graph"),
  getPassage: (id: number) => request<{ title: string; document_id: number; page: number | null; text: string }>(`/passages/${id}`),
  createRelationship: (source: string, target: string, relation_type: string, confidence: number) =>
    request<unknown>("/relationships", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source, target, relation_type, confidence }),
    }),

  getRecommendations: () => request<{ topics: RecommendedTopic[] }>("/learning/recommendation"),
  getGaps: (conceptId: number) => request<GapReport>(`/learning/gaps/${conceptId}`),

  chat: (message: string, options: TutorOptions = {}) =>
    request<ChatResponse>("/agent/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, ...options }),
    }),
  getLog: (limit = 200) => request<LogEntry[]>(`/agent/log?limit=${limit}`),
};
