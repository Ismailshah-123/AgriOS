/** Farm economics API (backend app/economics). Money/quantities are decimal strings; currency PKR. */
import { apiRequest } from "./client";

export type ExpenseCategory =
  | "seed" | "fertilizer" | "pesticide" | "labour" | "machinery" | "irrigation"
  | "energy" | "land_rent" | "transport" | "other";  // prettier-ignore

export const EXPENSE_CATEGORIES: ExpenseCategory[] = [
  "seed", "fertilizer", "pesticide", "labour", "machinery", "irrigation", "energy", "land_rent", "transport", "other",
];  // prettier-ignore

export interface Expense {
  id: string;
  crop_cycle_id: string;
  category: ExpenseCategory;
  amount_pkr: string;
  incurred_on: string;
  note: string | null;
  currency: "PKR";
  data_origin: "farmer_entered";
}

export interface HarvestSale {
  id: string;
  crop_cycle_id: string;
  recorded_on: string;
  quantity_kg: string;
  price_pkr_per_kg: string | null;
  buyer: string | null;
  note: string | null;
  revenue_pkr: string | null;
  currency: "PKR";
  data_origin: "farmer_entered";
}

export interface EconomicsSummary {
  total_cost_pkr: string;
  cost_by_category_pkr: Record<string, string>;
  harvested_kg: string;
  sold_kg: string;
  unsold_kg: string;
  revenue_pkr: string;
  profit_pkr: string;
  average_price_pkr_per_kg: string | null;
  cost_per_ha_pkr: string | null;
  cost_per_acre_pkr: string | null;
  break_even_price_pkr_per_kg: string | null;
  break_even_yield_kg: string | null;
}

export interface CycleEconomics {
  cycle: { id: string; crop_name: string; field_name: string; farm_name: string; status: string; area_ha: string | null };
  currency: "PKR";
  expenses: Expense[];
  harvests: HarvestSale[];
  summary: EconomicsSummary;
  definitions: string[];
  limitations: string[];
}

export type ExpenseInput = { crop_cycle_id: string; category: ExpenseCategory; amount_pkr: string; incurred_on: string; note: string | null };
export type HarvestInput = { crop_cycle_id: string; recorded_on: string; quantity_kg: string; price_pkr_per_kg: string | null; buyer: string | null; note: string | null };

export const economicsApi = {
  forCycle: (cycleId: string) => apiRequest<CycleEconomics>(`/crop-cycles/${cycleId}/economics`),
  addExpense: (b: ExpenseInput) => apiRequest<Expense>("/expenses", { method: "POST", json: b }),
  updateExpense: (id: string, b: Omit<ExpenseInput, "crop_cycle_id">) =>
    apiRequest<Expense>(`/expenses/${id}`, { method: "PATCH", json: b }),
  removeExpense: (id: string) => apiRequest<void>(`/expenses/${id}`, { method: "DELETE" }),
  addHarvest: (b: HarvestInput) => apiRequest<HarvestSale>("/harvest-sales", { method: "POST", json: b }),
  updateHarvest: (id: string, b: Omit<HarvestInput, "crop_cycle_id">) =>
    apiRequest<HarvestSale>(`/harvest-sales/${id}`, { method: "PATCH", json: b }),
  removeHarvest: (id: string) => apiRequest<void>(`/harvest-sales/${id}`, { method: "DELETE" }),
};

const pkrFmt = new Intl.NumberFormat("en-PK", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const kgFmt = new Intl.NumberFormat("en-PK", { maximumFractionDigits: 2 });

/** "PKR 41,500.00"; null stays an explicit dash, never 0. */
export function pkr(v: string | null | undefined): string {
  return v == null ? "—" : `PKR ${pkrFmt.format(Number(v))}`;
}

export function kg(v: string | null | undefined): string {
  return v == null ? "—" : `${kgFmt.format(Number(v))} kg`;
}

export const CATEGORY_LABEL: Record<ExpenseCategory, string> = {
  seed: "Seed", fertilizer: "Fertilizer", pesticide: "Pesticide", labour: "Labour", machinery: "Machinery",
  irrigation: "Irrigation", energy: "Energy / fuel", land_rent: "Land rent", transport: "Transport", other: "Other",
};  // prettier-ignore
