import type { AskResult } from "./knowledge";
/** Crop Doctor API (backend app/crop_health). Types mirror the Pydantic schemas. */
import { apiRequest, uploadForm } from "./client";
import type { Page } from "./types";

export type CaseStatus =
  | "submitted"
  | "retake"
  | "unsure"
  | "accepted"
  | "out_of_scope"
  | "expert_review"
  | "closed";
export type InferenceStatus =
  | "not_started"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "model_unavailable";
export type ModelAvailability =
  | "not_registered"
  | "not_installed"
  | "checksum_mismatch"
  | "loading"
  | "ready"
  | "error";
export type PlantPart = "leaf" | "stem" | "fruit" | "flower" | "root" | "whole_plant" | "other";
export type Symptom =
  | "spots"
  | "yellowing"
  | "wilting"
  | "curling"
  | "holes"
  | "mould"
  | "rot"
  | "stunting"
  | "insects_seen"
  | "other";

export interface CaseImage {
  id: string;
  position: number;
  width: number;
  height: number;
  url: string;
  thumb_url: string;
  urls_expire_at: string;
}

/** GET /cases/{id}/explanation (backend app/crop_health/explanation.py). */
export interface Explanation {
  available: boolean;
  reason: "no_completed_analysis" | "out_of_scope" | "not_provided_by_model" | null;
  method: string | null;
  target_class: string | null;
  decision: CaseStatus | null;
  note: string | null;
  maps: {
    image: CaseImage; grid: number[][]; crop_box: [number, number, number, number];
    focus: { position: string; strong_share_pct: number; hotspots: number; text_en: string; text_ur: string; caveat: string } | null;
  }[];
  model_name: string | null;
  model_version: string | null;
  limits_note: string;
}

export interface Submission {
  id: string;
  kind: "initial" | "follow_up";
  plant_part: PlantPart | null;
  symptoms: Symptom[];
  observed_on: string | null;
  notes: string | null;
  submitted_at: string;
  images: CaseImage[];
}

export interface Prediction {
  decision: CaseStatus;
  predicted_class: string | null;
  calibrated_confidence: number;
  ood_score: number | null;
  shortlist: { label: string; probability: number }[];
  model_name: string;
  model_version: string;
  analysed_at: string;
  image_count: number;
  explanation_available: boolean;
  limits_note: string;
}

export interface Analysis {
  inference_status: InferenceStatus;
  model_availability: ModelAvailability;
  error_code: string | null;
  message: string;
  can_retry: boolean;
  result: Prediction | null;
}

export interface CaseListItem {
  id: string;
  reference: string;
  status: CaseStatus;
  inference_status: InferenceStatus;
  crop: { id: string; code: string; name: string };
  farm: { id: string; name: string };
  field: { id: string; name: string };
  crop_cycle_id: string;
  image_count: number;
  submission_count: number;
  thumb_url: string | null;
  created_at: string;
  last_activity_at: string;
}

export interface CaseDetail extends CaseListItem {
  consent_training: boolean;
  submissions: Submission[];
  analysis: Analysis;
  timeline: { at: string; kind: string; text: string }[];
  expert_reviews?: ExpertReview[];
}

/** FR12: human expert outcome; always shown apart from model output. */
export type ReviewDecision = "confirmed_model" | "diagnosed" | "needs_retake" | "cannot_determine" | "not_supported";
export interface ExpertReview {
  id: string;
  decision: ReviewDecision;
  label: string | null;
  note: string | null;
  expert_name: string;
  reviewed_at: string;
  source: "expert_review";
}
export interface ReviewQueueItem {
  case_id: string;
  number: number;
  crop_name: string;
  status: CaseStatus;
  waiting_since: string;
  image_count: number;
}
export interface ReviewCase {
  case: CaseDetail;
  awaiting_review: boolean;
}

export const reviewApi = {
  request: (caseId: string) => apiRequest<void>(`/cases/${caseId}/expert-review`, { method: "POST" }),
  queue: () => apiRequest<ReviewQueueItem[]>("/review/queue"),
  get: (caseId: string) => apiRequest<ReviewCase>(`/review/cases/${caseId}`),
  explanation: (caseId: string) => apiRequest<Explanation>(`/review/cases/${caseId}/explanation`),
  submit: (caseId: string, body: { decision: ReviewDecision; label: string | null; note: string | null }) =>
    apiRequest<ExpertReview>(`/review/cases/${caseId}`, { method: "POST", json: body }),
};

export interface CaseStats {
  total: number;
  awaiting_analysis: number;
  needs_follow_up: number;
  by_inference_status: Record<InferenceStatus, number>;
  model_availability: ModelAvailability;
}

export interface CaseFilters {
  q?: string;
  status?: CaseStatus;
  inference_status?: InferenceStatus;
  crop_id?: string;
  created_from?: string;
  created_to?: string;
  needs_follow_up?: boolean;
  limit?: number;
  cursor?: string;
}

export interface Observations {
  plant_part: PlantPart | "";
  symptoms: Symptom[];
  observed_on: string;
  notes: string;
}

function appendObservations(form: FormData, o: Observations) {
  if (o.plant_part) form.append("plant_part", o.plant_part);
  for (const s of o.symptoms) form.append("symptoms", s);
  if (o.observed_on) form.append("observed_on", o.observed_on);
  if (o.notes.trim()) form.append("notes", o.notes.trim());
}

function qs(f: object): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(f) as [string, unknown][]) {
    if (v !== undefined && v !== null && v !== "" && v !== false) p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

export interface SetMetrics { n: number; accuracy: number; macro_f1: number; ece_15?: number }
export interface ModelInfo {
  status: ModelAvailability;
  reason: string;
  model_name: string | null;
  model_version: string | null;
  arch: string | null;
  supported_crops: string[];
  classes: string[];
  metrics_summary: Partial<Record<"val" | "val_calibrated" | "test" | "external_test", SetMetrics>> | null;
  metrics_ref: string | null;
}

export const cropHealthApi = {
  modelInfo: () => apiRequest<ModelInfo>("/models/availability"),
  assistantHistory: (id: string) => apiRequest<AskResult[]>(`/cases/${id}/assistant`),
  askAssistant: (id: string, body: { question?: string; language: "en" | "ur"; send_photo: boolean }) =>
    apiRequest<AskResult>(`/cases/${id}/assistant`, { method: "POST", json: body }),
  summary: () => apiRequest<CaseStats>("/cases/summary"),
  list: (f: CaseFilters = {}) => apiRequest<Page<CaseListItem>>(`/cases${qs(f)}`),
  get: (id: string) => apiRequest<CaseDetail>(`/cases/${id}`),
  retry: (id: string) => apiRequest<Analysis>(`/cases/${id}/analysis/retry`, { method: "POST" }),
  explanation: (id: string) => apiRequest<Explanation>(`/cases/${id}/explanation`),
  create: (
    input: { crop_cycle_id: string; consent_training: boolean; photos: File[]; client_id?: string } & Observations,
    onProgress?: (f: number) => void,
  ) => {
    const form = new FormData();
    form.append("crop_cycle_id", input.crop_cycle_id);
    form.append("consent_training", String(input.consent_training));
    if (input.client_id) form.append("client_id", input.client_id); // idempotent retry / offline sync
    appendObservations(form, input);
    for (const p of input.photos) form.append("images", p, p.name);
    return uploadForm<CaseDetail>("/cases", form, onProgress);
  },
  followUp: (id: string, input: { photos: File[] } & Observations, onProgress?: (f: number) => void) => {
    const form = new FormData();
    appendObservations(form, input);
    for (const p of input.photos) form.append("images", p, p.name);
    return uploadForm<CaseDetail>(`/cases/${id}/follow-ups`, form, onProgress);
  },
};
