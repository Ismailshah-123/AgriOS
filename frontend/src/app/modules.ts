import {
  BookOpenText,
  Bot,
  CloudSun,
  Droplets,
  FileText,
  FlaskConical,
  LayoutDashboard,
  Layers,
  Leaf,
  Map,
  Settings,
  Sprout,
  Stethoscope,
  UserCheck,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import type { Role } from "@/services/api/types";

/**
 * Single source of truth for navigation and module status.
 * "available" = works end to end in this build. "preview" = an entry page exists but
 * the core workflow is not built yet. "planned" = described honestly, no controls.
 * Descriptions follow the academic proposal and docs; they promise nothing beyond them.
 */
export type ModuleStatus = "available" | "preview" | "planned";

export interface ModuleDef {
  key: string;
  path: string;
  label: string;
  icon: LucideIcon;
  group: "Overview" | "Farm" | "Intelligence" | "Planning" | "AI & Knowledge" | "Account";
  status: ModuleStatus;
  summary: string;
  /** Planned modules: what it will do, and what it will rely on. */
  capabilities?: string[];
  needs?: string[];
  roadmap?: string;
  /** Only these roles see it in navigation (the API enforces access regardless). */
  roles?: Role[];
}

export const MODULES: ModuleDef[] = [
  { key: "overview", path: "/", label: "Overview", icon: LayoutDashboard, group: "Overview",
    status: "available", summary: "Your farms, fields and crop cycles at a glance." },
  { key: "farms", path: "/farms", label: "My Farms", icon: Map, group: "Farm",
    status: "available", summary: "Farms you manage, with location and total area." },
  { key: "fields", path: "/fields", label: "Fields", icon: Layers, group: "Farm",
    status: "available", summary: "Fields on each farm, with area in hectares or acres." },
  { key: "crop-cycles", path: "/crop-cycles", label: "Crop Cycles", icon: Sprout, group: "Farm",
    status: "available", summary: "Each crop grown on a field, from planning to harvest." },
  {
    key: "crop-doctor", path: "/crop-doctor", label: "Crop Doctor", icon: Stethoscope,
    group: "Intelligence", status: "available",
    summary: "Crop health cases with photos and observations; analysis when a validated model is installed.",
  },
  {
    key: "soil", path: "/soil", label: "Soil Intelligence", icon: FlaskConical,
    group: "Intelligence", status: "available",
    summary: "Soil test records with clear flags for pH and salinity constraints.",
    capabilities: [
      "Record pH, EC, N, P, K, organic carbon, texture and moisture per field.",
      "Flag pH and salinity constraints using thresholds from cited sources.",
      "Label every value: lab-measured, farmer-entered or retrieved estimate.",
    ],
    needs: ["A field to attach soil tests to", "Reviewed threshold sources"],
  },
  {
    key: "weather", path: "/weather", label: "Weather Intelligence", icon: CloudSun,
    group: "Intelligence", status: "available",
    summary: "Forecast and recent weather per farm, with crop risk indicators.",
    capabilities: [
      "Forecast and recent weather from a replaceable provider, with source and time shown.",
      "Indicators for heat stress, water stress, drought and disease-favourable conditions.",
      "Indicators describe conditions. They never state that a disease is present.",
    ],
    needs: ["A farm location (stored approximately)", "A connected weather provider"],
  },
  {
    key: "irrigation", path: "/irrigation", label: "Smart Irrigation", icon: Droplets,
    group: "Planning", status: "available",
    summary: "Crop water demand following FAO-56, with every assumption shown.",
    capabilities: [
      "Crop water need ETc = Kc × ET0, with each input and its source visible.",
      "Day-by-day stage, Kc range, ET0 and forecast gross rain for the growing crop.",
      "Estimates only: no schedule, soil moisture or equipment control.",
    ],
    needs: ["An active crop cycle", "Weather data", "Cited crop coefficients (Kc)"],
  },
  {
    key: "nutrients", path: "/nutrients", label: "Nutrient Management", icon: Leaf,
    group: "Planning", status: "preview",
    summary: "Fertilizer quantities from cited requirement tables only.",
    capabilities: [
      "Nutrient need and product quantity from stored, reviewed requirement tables.",
      "No quantity is shown without a source; otherwise you are referred to an expert.",
      "The arithmetic behind every number is shown.",
    ],
    needs: ["An active crop cycle", "Reviewed nutrient requirement tables"],
  },
  {
    key: "economics", path: "/economics", label: "Farm Economics", icon: Wallet,
    group: "Planning", status: "available",
    summary: "Expenses, harvest and sales per crop cycle in PKR, with profit and break-even.",
    capabilities: [
      "Record seed, fertilizer, pesticide, labour, machinery, irrigation and energy costs.",
      "Record harvest quantity and sales.",
      "Cost per acre, profit or loss, break-even yield and price, calculated from your records only.",
    ],
    needs: ["Crop cycles to attach costs and harvests to"],
  },
  {
    key: "agents", path: "/agents", label: "AI Agents", icon: Bot, group: "AI & Knowledge",
    status: "available",
    summary: "Six agents that use AgriOS tools for you, with your approval for changes.",
    capabilities: [
      "Uses the same AgriOS services you use. It cannot invent measurements or doses.",
      "Asks for your approval before saving any plan, reminder or record change.",
      "Every step is recorded in an audit trail you can review.",
    ],
    needs: ["The modules whose tools it uses (irrigation, crop health, knowledge)"],
  },
  {
    key: "knowledge", path: "/knowledge", label: "Agricultural Knowledge", icon: BookOpenText,
    group: "AI & Knowledge", status: "available",
    summary: "Cited answers from licence-verified sources, in English or Urdu.",
    capabilities: [
      "Hybrid search (keyword + semantic) over licence-verified sources only.",
      "Every answer cites its source passages; uncited or unsupported text is rejected.",
      "When no source supports an answer, it says so and suggests an expert. Never gives doses.",
    ],
    needs: ["Licence-verified sources (an administrator registers and verifies them)"],
  },
  {
    key: "reports", path: "/reports", label: "Reports", icon: FileText, group: "AI & Knowledge",
    status: "planned", roadmap: "Later phase",
    summary: "Season summaries and exports built from your own records.",
    capabilities: [
      "Crop cycle summaries from your farm records.",
      "Exports for your own records.",
    ],
    needs: ["Records from the farm, economics and crop health modules"],
  },
  { key: "review", path: "/review", label: "Expert Review", icon: UserCheck, group: "AI & Knowledge",
    status: "available", roles: ["expert", "admin"],
    summary: "Crop Doctor cases farmers sent to an expert." },
  { key: "settings", path: "/settings", label: "Settings", icon: Settings, group: "Account",
    status: "available", summary: "Profile, language and password." },
];  // prettier-ignore

export const NAV_GROUPS: ModuleDef["group"][] = [
  "Overview",
  "Farm",
  "Intelligence",
  "Planning",
  "AI & Knowledge",
];

export const STATUS_LABEL: Record<ModuleStatus, string> = {
  available: "Available",
  preview: "Preview",
  planned: "Planned",
};

export function moduleByKey(key: string): ModuleDef {
  const found = MODULES.find((m) => m.key === key);
  if (!found) throw new Error(`Unknown module: ${key}`);
  return found;
}
