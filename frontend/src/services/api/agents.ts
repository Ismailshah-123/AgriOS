/** Agent orchestrator API (backend app/agents). Types mirror the Pydantic models. */
import { apiRequest } from "./client";
import type { Page } from "./types";
import type { WeatherIndicator } from "./intelligence";

export type StepStatus = "ok" | "unavailable" | "error" | "timeout" | "denied" | "proposed";
export type ActionStatus = "pending" | "approved" | "rejected" | "expired" | "executed" | "failed";

export interface AgentStep {
  position: number;
  agent: string;
  tool: string;
  mode: "read" | "write";
  input: Record<string, unknown>;
  status: StepStatus;
  summary: string | null;
  error_code: string | null;
  duration_ms: number;
}

export interface AgentAction {
  id: string;
  run_id: string;
  agent: string;
  tool: string;
  args: Record<string, unknown>;
  description: string;
  status: ActionStatus;
  requested_by: string;
  decided_by: string | null;
  decided_at: string | null;
  executed_by: string | null;
  executed_at: string | null;
  expires_at: string;
  result: Record<string, unknown> | null;
  error_code: string | null;
  created_at: string;
}

export interface SuggestedAction {
  agent: string;
  action: string;
  reason: string;
}

export interface AgentSection {
  agent: string;
  title: string;
  status: "ok" | "partial" | "unavailable";
  findings: string[];
  actions: SuggestedAction[];
  missing: string[];
  evidence: Record<string, unknown>[];
  limitations: string[];
}

export interface FieldReport {
  title: string;
  generated_at: string;
  field: { id: string; name: string; area_ha: number } | null;
  farm: { id: string; name: string; latitude: number | null; longitude: number | null } | null;
  crop: {
    crop: string;
    variety: string | null;
    sowing_date: string | null;
    days_after_planting: number | null;
    fao56_stage: string | null;
  } | null;
  risks: WeatherIndicator[];
  timestamps: Record<string, string | null>;
  coverage: Record<string, "ok" | "partial" | "unavailable" | "not_run">;
  confidence: string;
}

export interface AgentResponse {
  answer: string;
  intent: string;
  agents: { name: string; title: string; purpose: string }[];
  sections: AgentSection[];
  report: FieldReport | null;
  suggested_actions: SuggestedAction[];
  missing_information: string[];
  evidence: Record<string, unknown>[];
  pending_actions: { id: string; tool: string; description: string; status: ActionStatus }[];
  limitations: string[];
  llm_used: boolean;
  generated_by: string;
}

export interface AgentRunSummary {
  id: string;
  message: string;
  intent: string;
  agents: string[];
  status: "completed" | "partial" | "failed";
  farm_id: string | null;
  field_id: string | null;
  duration_ms: number;
  created_at: string;
}

export interface AgentCatalogue {
  agents: { name: string; title: string; purpose: string }[];
  tools: {
    name: string;
    description: string;
    mode: "read" | "write";
    permission: string;
    requires_approval: boolean;
    agents: string[];
  }[];
  llm_used: boolean;
}

export interface AgentRun extends AgentRunSummary {
  response: AgentResponse;
  steps: AgentStep[];
  actions: AgentAction[];
}

export const agentsApi = {
  run: (body: { message: string; field_id?: string; farm_id?: string }) =>
    apiRequest<AgentRun>("/agent/runs", { method: "POST", json: body }),
  history: () => apiRequest<Page<AgentRunSummary>>("/agent/runs?limit=20"),
  get: (id: string) => apiRequest<AgentRun>(`/agent/runs/${id}`),
  actions: (status?: ActionStatus) =>
    apiRequest<AgentAction[]>(`/agent/actions${status ? `?status=${status}` : ""}`),
  approve: (id: string) => apiRequest<AgentAction>(`/agent/actions/${id}/approve`, { method: "POST" }),
  reject: (id: string) => apiRequest<AgentAction>(`/agent/actions/${id}/reject`, { method: "POST" }),
  catalogue: () => apiRequest<AgentCatalogue>("/agent/catalogue"),
};
