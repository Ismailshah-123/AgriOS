/** Weather + Soil Intelligence API (backend app/weather, app/soil). Types mirror Pydantic. */
import { apiRequest } from "./client";

export interface WeatherIndicator {
  id: string;
  level: "info" | "watch" | "warning";
  kind: "indicator";
  message: string;
  basis: string;
  source: string;
  review_status: string;
  limitations?: string | null;
  time_window?: { start: string; end: string } | null;
  evidence: Record<string, unknown>;
}

export interface WeatherDaily {
  date: string;
  temperature_max_c: number | null;
  temperature_min_c: number | null;
  precipitation_sum_mm: number | null;
  precipitation_probability_max_pct: number | null;
  wind_speed_max_kmh: number | null;
  et0_fao_mm: number | null;
}

export interface WeatherHourly {
  time: string;
  temperature_c: number | null;
  relative_humidity_pct: number | null;
  precipitation_mm: number | null;
  precipitation_probability_pct: number | null;
}

export interface WeatherReport {
  status: "fresh" | "stale" | "unavailable";
  reason: string | null;
  data_origin: "retrieved";
  location: {
    farm_id: string;
    farm_name: string;
    field_id: string | null;
    latitude: number | null;
    longitude: number | null;
    precision: "0.01_degree";
  };
  provider: { name: string; url: string; licence: string; model: string } | null;
  retrieved_at: string | null;
  age_minutes: number | null;
  timezone: string | null;
  units: Record<string, string>;
  current: {
    time: string | null;
    temperature_c: number | null;
    relative_humidity_pct: number | null;
    precipitation_mm: number | null;
    wind_speed_kmh: number | null;
    weather_code: number | null;
  } | null;
  hourly: WeatherHourly[];
  daily: WeatherDaily[];
  indicators: WeatherIndicator[];
  not_evaluated: { indicator: string; reason: string }[];
  disclaimer: string;
}

export const weatherApi = {
  forField: (fieldId: string) => apiRequest<WeatherReport>(`/weather?field_id=${encodeURIComponent(fieldId)}`),
  forFarm: (farmId: string) => apiRequest<WeatherReport>(`/weather?farm_id=${encodeURIComponent(farmId)}`),
};

// ------------------------------------------------------------------------- soil

export type PhMethod = "water_1_1" | "water_1_2_5" | "saturated_paste" | "cacl2" | "unknown";
export type EcMethod = "saturated_paste_ece" | "extract_1_1" | "extract_1_2_5" | "extract_1_5" | "unknown";
export type PMethod = "olsen" | "bray_1" | "mehlich_3" | "unknown";
export type SoilOrigin = "measured" | "farmer_entered";
export const TEXTURES = [
  "sand", "loamy_sand", "sandy_loam", "loam", "silt_loam", "silt", "sandy_clay_loam",
  "clay_loam", "silty_clay_loam", "sandy_clay", "silty_clay", "clay",
] as const;
export type Texture = (typeof TEXTURES)[number];

export interface SoilValues {
  lab_name: string | null;
  lab_reference: string | null;
  depth_from_cm: number | null;
  depth_to_cm: number | null;
  ph: number | null;
  ph_method: PhMethod;
  ec_ds_m: number | null;
  ec_method: EcMethod;
  organic_matter_pct: number | null;
  organic_carbon_pct: number | null;
  nitrogen_total_pct: number | null;
  phosphorus_mg_kg: number | null;
  phosphorus_method: PMethod;
  potassium_mg_kg: number | null;
  calcium_mg_kg: number | null;
  magnesium_mg_kg: number | null;
  sulfur_mg_kg: number | null;
  zinc_mg_kg: number | null;
  iron_mg_kg: number | null;
  boron_mg_kg: number | null;
  cec_cmol_kg: number | null;
  texture: Texture | null;
  notes: string | null;
}

export interface SoilObservation extends SoilValues {
  id: string;
  field_id: string;
  sampled_on: string;
  data_origin: SoilOrigin;
  created_at: string;
  units: Record<string, string>;
  nutrient_methods: Record<string, string> | null;
}

export interface SoilFlag {
  measure: string;
  value: number;
  unit: string;
  class: string;
  level: "info" | "watch" | "warning";
  source: string;
  message: string;
  crop?: string;
  expected_relative_yield_pct?: number;
}

export interface SoilDetail extends SoilObservation {
  interpretation: {
    flags: SoilFlag[];
    not_evaluated: { measure: string; reason: string }[];
    warnings: { code: string; measures: string[]; message: string }[];
    dose_policy: string;
  };
  crops_considered: string[];
}

export interface TrendPoint {
  sampled_on: string;
  value: number;
  data_origin: SoilOrigin;
  observation_id: string;
}

export interface SoilSummary {
  field_id: string;
  field_name: string;
  observations: number;
  latest: SoilDetail | null;
  trends: Record<string, TrendPoint[]>;
}

/** Decimal values are sent as strings so they are never rounded by float conversion. */
export type SoilInput = {
  field_id: string;
  sampled_on: string;
  data_origin: SoilOrigin;
} & Partial<Record<keyof SoilValues, string | null>> & {
  nutrient_methods?: Partial<Record<string, string>> | null;
};

export const soilApi = {
  list: (fieldId: string) =>
    apiRequest<SoilObservation[]>(`/soil-observations?field_id=${encodeURIComponent(fieldId)}`),
  get: (id: string) => apiRequest<SoilDetail>(`/soil-observations/${id}`),
  create: (body: SoilInput) => apiRequest<SoilDetail>("/soil-observations", { method: "POST", json: body }),
  update: (id: string, body: Omit<SoilInput, "field_id">) =>
    apiRequest<SoilDetail>(`/soil-observations/${id}`, { method: "PATCH", json: body }),
  remove: (id: string) => apiRequest<void>(`/soil-observations/${id}`, { method: "DELETE" }),
  summary: (fieldId: string) => apiRequest<SoilSummary>(`/fields/${fieldId}/soil-summary`),
};

// ------------------------------------------------------------------ water demand

export interface WaterDay {
  date: string;
  stage: string | null;
  kc_low: number | null;
  kc_high: number | null;
  et0_mm: number | null;
  etc_low_mm: number | null;
  etc_high_mm: number | null;
  rain_mm: number | null;
}

export interface WaterDemand {
  field_id: string;
  status: "ok" | "unavailable";
  data_origin: "inferred";
  units: Record<string, string>;
  method: string;
  source: string;
  crop: string | null;
  planting_date: string | null;
  days_after_planting: number | null;
  current_stage: string | null;
  daily: WaterDay[];
  totals: { days: number; et0_mm: number; etc_low_mm: number; etc_high_mm: number; gross_rain_mm: number | null } | null;
  effective_rainfall: "not_applied";
  soil_moisture: "not_measured";
  missing_information: string[];
  limitations: string[];
}

export const irrigationApi = {
  waterDemand: (fieldId: string) => apiRequest<WaterDemand>(`/fields/${fieldId}/water-demand`),
};
