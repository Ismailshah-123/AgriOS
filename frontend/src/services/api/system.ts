import { apiRequest } from "./client";

// Mirrors backend/app/api/v1/endpoints/health.py response models.
export interface HealthResponse {
  status: "ok";
  service: string;
  version: string;
  environment: string;
}

export type DatabaseState = "ok" | "not_configured" | "unavailable";

export interface ReadinessResponse {
  status: "ready" | "not_ready";
  checks: { database: DatabaseState };
}

export const getHealth = (signal?: AbortSignal) =>
  apiRequest<HealthResponse>("/health", { signal });

export const getReadiness = (signal?: AbortSignal) =>
  apiRequest<ReadinessResponse>("/ready", { signal, acceptStatuses: [503] });
