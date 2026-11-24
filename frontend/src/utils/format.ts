import type { Area, CycleStatus, DataOrigin, Province, Season } from "@/services/api/types";
import { ApiError } from "@/services/api/client";

const nf = new Intl.NumberFormat("en-PK", { maximumFractionDigits: 2 });

export function formatNumber(value: number): string {
  return nf.format(value);
}

export const UNIT_LABEL = { ha: "ha", acre: "acres" } as const;

/** "2.5 acres (1.01 ha)" — what the farmer typed, plus the stored hectares. */
export function formatArea(area: Area): string {
  const entered = `${formatNumber(area.value)} ${UNIT_LABEL[area.unit]}`;
  return area.unit === "ha" ? entered : `${entered} (${formatNumber(area.hectares)} ha)`;
}

export function formatHectares(ha: number): string {
  return `${formatNumber(ha)} ha`;
}

const df = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });

/** API dates are ISO "YYYY-MM-DD" (local calendar dates, no time zone shift). */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return df.format(new Date(y!, m! - 1, d!));
}

export const PROVINCE_LABEL: Record<Province, string> = {
  punjab: "Punjab",
  sindh: "Sindh",
  khyber_pakhtunkhwa: "Khyber Pakhtunkhwa",
  balochistan: "Balochistan",
  gilgit_baltistan: "Gilgit-Baltistan",
  azad_jammu_kashmir: "Azad Jammu and Kashmir",
  islamabad_capital_territory: "Islamabad Capital Territory",
};

export const STATUS_LABEL: Record<CycleStatus, string> = {
  planned: "Planned",
  active: "Growing",
  harvested: "Harvested",
  abandoned: "Ended early",
};

export const SEASON_LABEL: Record<Season, string> = {
  kharif: "Kharif",
  rabi: "Rabi",
  other: "Other",
};

export const ORIGIN_LABEL: Record<DataOrigin, string> = {
  measured: "Measured",
  farmer_entered: "Farmer entered",
  retrieved: "Retrieved",
  inferred: "Estimated",
  simulated: "Simulated",
};

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Something unexpected happened. Please try again.";
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return (parts[0]?.[0] ?? "") + (parts.length > 1 ? (parts.at(-1)?.[0] ?? "") : "");
}

/** Today's date as YYYY-MM-DD in the user's local calendar. */
export function todayIso(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
