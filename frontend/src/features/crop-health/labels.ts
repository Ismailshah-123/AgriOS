import type {
  CaseStatus,
  InferenceStatus,
  ModelAvailability,
  PlantPart,
  ReviewDecision,
  Symptom,
} from "@/services/api/cropHealth";

export const PLANT_PART_LABEL: Record<PlantPart, string> = {
  leaf: "Leaf",
  stem: "Stem",
  fruit: "Fruit",
  flower: "Flower",
  root: "Root",
  whole_plant: "Whole plant",
  other: "Other",
};

/** Farmer-reported signs. Shown as observations, never as a diagnosis. */
export const SYMPTOM_LABEL: Record<Symptom, string> = {
  spots: "Spots",
  yellowing: "Yellowing",
  wilting: "Wilting",
  curling: "Curling leaves",
  holes: "Holes",
  mould: "Mould or powder",
  rot: "Rot",
  stunting: "Stunted growth",
  insects_seen: "Insects seen",
  other: "Other",
};

export const INFERENCE_LABEL: Record<InferenceStatus, string> = {
  not_started: "Not started",
  queued: "Waiting for analysis",
  running: "Analysing",
  completed: "Analysed",
  failed: "Analysis failed",
  model_unavailable: "Model not installed",
};

export const CASE_STATUS_LABEL: Record<CaseStatus, string> = {
  submitted: "Submitted",
  retake: "Retake photo",
  unsure: "Not sure",
  accepted: "Result available",
  out_of_scope: "Not supported",
  expert_review: "With expert",
  closed: "Closed",
};

export const AVAILABILITY_LABEL: Record<ModelAvailability, string> = {
  not_registered: "No model installed",
  not_installed: "Model file missing",
  checksum_mismatch: "Model failed verification",
  loading: "Loading",
  ready: "Ready",
  error: "Unavailable",
};

/** Mirrors backend defaults (app/core/config.py); the server remains authoritative. */
export const UPLOAD_RULES = {
  maxPhotos: 5,
  maxBytes: 8 * 1024 * 1024,
  types: ["image/jpeg", "image/png", "image/webp"],
  accept: "image/jpeg,image/png,image/webp",
};

/** Client-side checks give fast feedback only; the server re-validates every byte. */
export function checkPhoto(file: File): string | null {
  if (!UPLOAD_RULES.types.includes(file.type)) return `${file.name}: use a JPEG, PNG or WebP photo.`;
  if (file.size > UPLOAD_RULES.maxBytes) return `${file.name}: photos must be 8 MB or smaller.`;
  return null;
}

export const DECISION_LABEL: Record<ReviewDecision, string> = {
  confirmed_model: "Confirmed the model's result",
  diagnosed: "Expert diagnosis",
  needs_retake: "New photos needed",
  cannot_determine: "Cannot be determined from these photos",
  not_supported: "Outside supported crops or problems",
};

/** Model classes (tomato_v1). Urdu drafted by the development assistant: PENDING native + agronomist review. */
export const DISEASE_LABEL: Record<string, { en: string; ur: string }> = {
  bacterial_spot: { en: "Bacterial spot", ur: "بیکٹیریل دھبے" },
  early_blight: { en: "Early blight", ur: "اگیتی جھلسا" },
  healthy: { en: "Healthy leaf", ur: "صحت مند پتا" },
  late_blight: { en: "Late blight", ur: "پچھیتی جھلسا" },
  leaf_mold: { en: "Leaf mould", ur: "پتوں کی پھپھوندی" },
  mosaic_virus: { en: "Tomato mosaic virus", ur: "موزیک وائرس" },
  septoria_leaf_spot: { en: "Septoria leaf spot", ur: "سیپٹوریا دھبے" },
  spider_mites: { en: "Spider mites", ur: "سرخ مکڑی (اسپائیڈر مائٹ)" },
  target_spot: { en: "Target spot", ur: "ٹارگٹ اسپاٹ" },
  yellow_leaf_curl_virus: { en: "Tomato yellow leaf curl virus", ur: "پتا مروڑ وائرس" },
};

export function diseaseName(label: string | null | undefined, locale: string): string {
  if (!label) return "";
  const d = DISEASE_LABEL[label];
  return d ? (locale === "ur" ? d.ur : d.en) : label.replaceAll("_", " ");
}
