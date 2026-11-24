/** GET /analytics (backend app/dashboard/analytics.py): owner-scoped grouped sums/counts. */
import type { CaseStatus } from "./cropHealth";
import { apiRequest } from "./client";

export interface Analytics {
  generated_at: string;
  area_by_crop: { crop: string; cycles: number; area_ha: number }[];
  cases: { by_status: Record<CaseStatus, number>; by_month: { month: string; cases: number }[] };
  pending_expert_reviews: number;
  economics: {
    currency: "PKR";
    total_cost_pkr: string;
    total_revenue_pkr: string;
    profit_pkr: string;
    cost_by_category_pkr: Record<string, string>;
    cycles: { crop_cycle_id: string; crop: string; field: string; cost_pkr: string; revenue_pkr: string; profit_pkr: string }[];
  };
}

export const analyticsApi = { get: () => apiRequest<Analytics>("/analytics") };
