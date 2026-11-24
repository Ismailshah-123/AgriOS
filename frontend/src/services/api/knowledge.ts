import { API_BASE_URL, apiRequest, refreshAccessToken, tokenStore, uploadForm } from "./client";

export type AskStatus = "answered" | "extractive" | "abstained" | "clarify" | "error";

export interface Citation {
  n: number;
  marker: string;
  cited: boolean;
  chunk_id: string;
  text: string;
  page: number | null;
  section: string | null;
  source_id: string;
  title: string;
  publisher: string;
  author: string | null;
  year: number | null;
  publication_date: string | null;
  url: string | null;
  licence: string;
  review_status: string;
  document_type: string | null;
  fts_rank: number;
  dense_score: number | null;
  matched_by: string[];
}

export interface FarmContext {
  empty: boolean;
  missing: string[];
  fields: {
    farm: string; field: string; area_ha: number; district: string | null;
    cycles: { crop: string; status: string; variety: string | null; sowing_date: string | null; days_after_sowing: number | null }[];
    latest_soil_test: { sampled_on: string; origin: string; values: Record<string, string>; not_measured: string[]; texture: string | null } | null;
  }[];
  economics?: { recorded_expenses_pkr: number | null; recorded_revenue_pkr: number | null; origin: string };
  crop_doctor_cases?: Record<string, number>;
  recent_crop_doctor_results?: { predicted_class: string | null; decision: string; origin: string }[];
}  // prettier-ignore

export interface AskMeta {
  warnings: string[];
  evidence_quality: "multiple_sources" | "single_source_multiple_passages" | "single_passage" | "none";
  speech_text: string;
  retrieval_method?: string;
  retrieval_query?: string;
  language_detected?: string;
  domains?: string[];
  grounded_share?: number | null;
  farm_context?: FarmContext | null;
  farm_cited?: boolean;
  escalate_to_expert?: boolean;
  sections?: { seen_in_photo: string; explanation: string; next_steps: string };
  photo_sent?: boolean;
}

export interface AskResult {
  id: string;
  conversation_id: string;
  question: string;
  retrieval_query: string;
  language: string;
  domain: string | null;
  crops: string[];
  status: AskStatus;
  answer: string | null;
  citations: Citation[];
  meta: AskMeta;
  n_passages: number;
  retrieval_ms: number;
  total_ms: number;
  llm_provider: string | null;
  llm_model: string | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  feedback_rating: number | null;
  created_at: string | null;
}

export interface AskInput {
  question: string;
  conversation_id?: string;
  language: "auto" | "en" | "ur";
  domain?: string;
  crop?: string;
  farm_context: "auto" | "on" | "off";
}

export interface Conversation { id: string; title: string; created_at: string; updated_at: string }

export interface KnowledgeSource {
  id: string; title: string; publisher: string; author: string | null; year: number | null;
  publication_date: string | null; retrieved_at: string | null; url: string | null; licence: string;
  licence_url: string | null; commercial_use: string; attribution: string | null; language: string;
  region: string | null; country: string | null; domain: string | null; crops: string[];
  document_type: string | null; version: number; is_active: boolean; review_status: string;
  review_note: string | null; verified_at: string | null; file_name: string | null; file_bytes: number | null;
  ingest_status: "not_ingested" | "queued" | "processing" | "indexed" | "failed"; ingest_error: string | null;
  chunk_count: number; indexed_at: string | null; created_at: string | null;
  ingest_log?: { at: string; event: string; [k: string]: unknown }[];
}  // prettier-ignore

export interface KnowledgeStats {
  sources_by_status: Record<string, number>;
  searchable_sources: number;
  sources_with_chunks: number;
  chunks: number;
  embedded_chunks: number;
  ingestion: Record<string, number>;
  last_indexed_at: string | null;
  queries_total: number;
  providers: {
    llm: { provider: string; model: string | null; enabled: boolean; reason: string | null; external: boolean };
    embeddings: { provider: string; model: string | null; enabled: boolean };
    vision?: { model: string | null; enabled: boolean };
  };
  not_tracked: string[];
}

export interface KnowledgeAnalytics {
  queries_total: number;
  by_status: Record<string, number>;
  no_result_queries: number;
  failed_queries: number;
  by_domain: Record<string, number>;
  by_language: Record<string, number>;
  latency_ms: { retrieval_p50: number | null; retrieval_p95: number | null; total_p50: number | null; total_p95: number | null };
  tokens: { prompt: number; completion: number };
  daily: { day: string; queries: number }[];
  source_usage: { title: string; citations: number }[];
  feedback: { helpful: number; not_helpful: number };
  ingestion: Record<string, number>;
  ingestion_jobs: Record<string, number>;
  not_tracked: string[];
}

export interface Taxonomy { domains: string[]; document_types: string[]; crops: string[] }

export interface OpenedChunk {
  chunk: { id: string; page: number | null; section: string | null; text: string };
  context: { id: string; page: number | null; section: string | null; text: string; is_cited: boolean }[];
  source: KnowledgeSource & { has_file: boolean };
}

export type SourceInput = Pick<KnowledgeSource, "title" | "publisher" | "licence" | "commercial_use" | "language"> &
  Partial<Pick<KnowledgeSource, "author" | "year" | "url" | "licence_url" | "attribution" | "region" | "country" | "domain" | "crops" | "document_type">>;

const K = "/knowledge";
export const knowledgeApi = {
  ask: (body: AskInput) => apiRequest<AskResult>(`${K}/ask`, { method: "POST", json: body }),
  feedback: (id: string, rating: 1 | -1) =>
    apiRequest<void>(`${K}/queries/${id}/feedback`, { method: "POST", json: { rating } }),
  conversations: () => apiRequest<Conversation[]>(`${K}/conversations`),
  conversation: (id: string) => apiRequest<AskResult[]>(`${K}/conversations/${id}`),
  deleteConversation: (id: string) => apiRequest<void>(`${K}/conversations/${id}`, { method: "DELETE" }),
  chunk: (id: string) => apiRequest<OpenedChunk>(`${K}/chunks/${id}`),
  stats: () => apiRequest<KnowledgeStats>(`${K}/stats`),
  taxonomy: () => apiRequest<Taxonomy>(`${K}/taxonomy`),
  sources: () => apiRequest<KnowledgeSource[]>(`${K}/sources`),
  source: (id: string) => apiRequest<KnowledgeSource>(`${K}/sources/${id}`),
  createSource: (body: SourceInput) => apiRequest<KnowledgeSource>(`${K}/sources`, { method: "POST", json: body }),
  patchSource: (id: string, body: Partial<KnowledgeSource>) =>
    apiRequest<KnowledgeSource>(`${K}/sources/${id}`, { method: "PATCH", json: body }),
  review: (id: string, status: string, note: string) =>
    apiRequest<KnowledgeSource>(`${K}/sources/${id}/review`, { method: "POST", json: { status, note } }),
  upload: (id: string, file: File, onProgress?: (f: number) => void) => {
    const form = new FormData();
    form.append("file", file);
    return uploadForm<KnowledgeSource>(`${K}/sources/${id}/file`, form, onProgress);
  },
  reprocess: (id: string) => apiRequest<KnowledgeSource>(`${K}/sources/${id}/reprocess`, { method: "POST" }),
  deleteSource: (id: string) => apiRequest<void>(`${K}/sources/${id}`, { method: "DELETE" }),
  analytics: () => apiRequest<KnowledgeAnalytics>(`${K}/analytics`),
};

/** Opens the stored original in a new tab (authenticated fetch -> blob URL; the API sends
 * it with a sandbox CSP). Returns false when the file is unavailable. */
export async function openSourceFile(id: string): Promise<boolean> {
  const get = (t: string | null) => fetch(`${API_BASE_URL}/knowledge/sources/${id}/file`, {
    credentials: "include", headers: t ? { Authorization: `Bearer ${t}` } : {} });
  let res = await get(tokenStore.get());
  if (res.status === 401) res = await get(await refreshAccessToken());
  if (!res.ok) return false;
  const url = URL.createObjectURL(await res.blob());
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
  return true;
}

export const DOMAIN_LABEL: Record<string, string> = {
  crop_science: "Crop science", plant_protection: "Plant diseases & pests", soil_science: "Soil science",
  nutrient_management: "Nutrient management", irrigation_water: "Irrigation & water",
  weather_climate: "Weather & climate", farm_operations: "Farm operations",
  economics_business: "Economics & business", livestock_allied: "Livestock & allied",
  research_policy: "Research & policy", unclassified: "Unclassified",
};  // prettier-ignore

export const WARNING_TEXT: Record<string, string> = {
  invalid_citation_removed: "A citation that did not match a retrieved passage was removed.",
  dose_removed: "A dose or application rate was removed. AgriOS never gives doses.",
  dose_request_refused_escalate_to_expert: "Dose questions are referred to the product label or an expert.",
  generated_answer_failed_grounding_check: "The generated answer was not well supported by the sources, so quoted passages are shown instead.",
  groundedness_check_citation_presence_only: "Urdu answers are checked for citations only (no word-overlap check).",
  no_citations: "The answer carried no citations.",
  embeddings_unavailable_fulltext_only: "Semantic search is unavailable; keyword search only.",
  veterinary_general_information_only: "Animal health: general information only. Consult a veterinarian.",
};  // prettier-ignore

export function warningText(code: string): string {
  if (code.startsWith("llm_unavailable")) return "The language model was unavailable, so quoted passages are shown instead.";
  if (code.startsWith("rewrite_failed")) return "Follow-up rewriting failed; the question was searched as written.";
  return WARNING_TEXT[code] ?? code.replaceAll("_", " ");
}
