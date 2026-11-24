import { apiRequest } from "./client";
import type {
  Crop,
  CropCycle,
  CropCycleInput,
  CycleStatus,
  Farm,
  FarmInput,
  FieldInput,
  FieldRecord,
  Overview,
  Page,
  TokenResponse,
  User,
} from "./types";

function qs(params: object = {}): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params) as [string, unknown][]) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

// ------------------------------------------------------------------------- auth

export const authApi = {
  register: (body: { email: string; password: string; full_name: string }) =>
    apiRequest<TokenResponse>("/auth/register", { method: "POST", json: body, anonymous: true }),
  login: (body: { email: string; password: string }) =>
    apiRequest<TokenResponse>("/auth/login", { method: "POST", json: body, anonymous: true }),
  logout: () => apiRequest<void>("/auth/logout", { method: "POST", anonymous: true }),
  me: () => apiRequest<User>("/auth/me"),
  updateProfile: (body: Partial<Pick<User, "full_name" | "locale">>) =>
    apiRequest<User>("/users/me", { method: "PATCH", json: body }),
  changePassword: (body: { current_password: string; new_password: string }) =>
    apiRequest<void>("/users/me/password", { method: "POST", json: body }),
};

// ------------------------------------------------------------------------ farms

export const farmsApi = {
  list: (params: { q?: string; limit?: number; cursor?: string } = {}) =>
    apiRequest<Page<Farm>>(`/farms${qs(params)}`),
  get: (id: string) => apiRequest<Farm>(`/farms/${id}`),
  create: (body: FarmInput) => apiRequest<Farm>("/farms", { method: "POST", json: body }),
  update: (id: string, body: Partial<FarmInput>) =>
    apiRequest<Farm>(`/farms/${id}`, { method: "PATCH", json: body }),
  remove: (id: string) => apiRequest<void>(`/farms/${id}`, { method: "DELETE" }),
};

export const fieldsApi = {
  list: (params: { farm_id?: string; q?: string; limit?: number; cursor?: string } = {}) =>
    apiRequest<Page<FieldRecord>>(`/fields${qs(params)}`),
  get: (id: string) => apiRequest<FieldRecord>(`/fields/${id}`),
  create: (body: FieldInput) => apiRequest<FieldRecord>("/fields", { method: "POST", json: body }),
  update: (id: string, body: Partial<FieldInput>) =>
    apiRequest<FieldRecord>(`/fields/${id}`, { method: "PATCH", json: body }),
  remove: (id: string) => apiRequest<void>(`/fields/${id}`, { method: "DELETE" }),
};

export const cropsApi = {
  list: () => apiRequest<Crop[]>("/crops"),
};

export interface CycleFilters {
  farm_id?: string;
  field_id?: string;
  status?: CycleStatus;
  crop_id?: string;
  limit?: number;
  cursor?: string;
}

export const cyclesApi = {
  list: (params: CycleFilters = {}) => apiRequest<Page<CropCycle>>(`/crop-cycles${qs(params)}`),
  create: (body: CropCycleInput) =>
    apiRequest<CropCycle>("/crop-cycles", { method: "POST", json: body }),
  update: (id: string, body: CropCycleInput) =>
    apiRequest<CropCycle>(`/crop-cycles/${id}`, { method: "PATCH", json: body }),
  remove: (id: string) => apiRequest<void>(`/crop-cycles/${id}`, { method: "DELETE" }),
};

export const overviewApi = {
  get: () => apiRequest<Overview>("/overview"),
};
