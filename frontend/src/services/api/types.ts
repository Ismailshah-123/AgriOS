/** Types mirroring backend Pydantic schemas (app/identity, app/farms). */
import type { ModelAvailability } from "./cropHealth";

export interface Page<T> {
  items: T[];
  next_cursor: string | null;
}

export type Role = "farmer" | "expert" | "admin";
export type Locale = "en" | "ur";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  locale: Locale;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: User;
}

export type DataOrigin = "measured" | "farmer_entered" | "retrieved" | "inferred" | "simulated";
export type AreaUnit = "ha" | "acre";

export type Province =
  | "punjab"
  | "sindh"
  | "khyber_pakhtunkhwa"
  | "balochistan"
  | "gilgit_baltistan"
  | "azad_jammu_kashmir"
  | "islamabad_capital_territory";

export interface Farm {
  id: string;
  name: string;
  province: Province | null;
  district: string | null;
  latitude: number | null;
  longitude: number | null;
  location_precision: "0.01_degree";
  notes: string | null;
  field_count: number;
  total_area_ha: number;
  created_at: string;
  updated_at: string;
}

export interface FarmInput {
  name: string;
  province?: Province | null;
  district?: string | null;
  latitude?: string | null;
  longitude?: string | null;
  notes?: string | null;
}

export interface Area {
  hectares: number;
  value: number;
  unit: AreaUnit;
  data_origin: DataOrigin;
}

export interface FieldRecord {
  id: string;
  farm_id: string;
  farm_name: string;
  name: string;
  area: Area;
  notes: string | null;
  active_cycle_count: number;
  created_at: string;
  updated_at: string;
}

export interface FieldInput {
  farm_id?: string;
  name: string;
  area: { value: string; unit: AreaUnit };
  area_origin?: "farmer_entered" | "measured";
  notes?: string | null;
}

export interface Crop {
  id: string;
  code: string;
  name_en: string;
  name_ur: string | null;
  scientific_name: string | null;
}

export type CycleStatus = "planned" | "active" | "harvested" | "abandoned";
export type Season = "kharif" | "rabi" | "other";

export interface CropCycle {
  id: string;
  field_id: string;
  field_name: string;
  farm_id: string;
  farm_name: string;
  crop: Crop;
  variety: string | null;
  season: Season | null;
  status: CycleStatus;
  sowing_date: string | null;
  expected_harvest_date: string | null;
  harvest_date: string | null;
  area_ha: number | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface CropCycleInput {
  field_id?: string;
  crop_id?: string;
  variety?: string | null;
  season?: Season | null;
  status?: CycleStatus;
  sowing_date?: string | null;
  expected_harvest_date?: string | null;
  harvest_date?: string | null;
  area_ha?: string | null;
  notes?: string | null;
}

// --------------------------------------------------------------------- overview

export interface CycleBrief {
  id: string;
  crop_name: string;
  variety: string | null;
  field_name: string;
  farm_name: string;
  status: CycleStatus;
  sowing_date: string | null;
  expected_harvest_date: string | null;
}

export interface Overview {
  counts: {
    farms: number;
    fields: number;
    total_area_ha: number;
    cycles_by_status: Record<CycleStatus, number>;
  };
  active_cycles: CycleBrief[];
  upcoming: {
    kind: "planned_sowing" | "expected_harvest";
    date: string;
    source: "farmer_entered";
    cycle: CycleBrief;
  }[];
  recent_changes: {
    action: string;
    entity: "farm" | "field" | "crop_cycle";
    entity_id: string | null;
    name: string | null;
    created_at: string;
  }[];
  /** Counts of stored records per module (backend app/dashboard/intelligence.py). */
  intelligence: {
    crop_health: {
      cases: number;
      awaiting_analysis: number;
      needs_follow_up: number;
      model_availability: ModelAvailability;
    };
    soil: { observations: number; fields_with_tests: number; latest_sampled_on: string | null };
    weather: { farms: number; farms_with_location: number };
    irrigation: { growing_cycles: number; cycles_with_estimate: number };
    agents: { runs: number; pending_approvals: number };
  };
}
