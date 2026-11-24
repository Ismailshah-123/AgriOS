/**
 * Typed fetch wrapper for the AgriOS API.
 * - Parses the standard error envelope: {"error": {"code", "message", "field?"}}.
 * - Sends the in-memory access token; on a 401 it refreshes ONCE through the httpOnly
 *   refresh cookie (deduplicated across concurrent requests) and retries.
 * The access token is never written to localStorage/sessionStorage.
 */

export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly field?: string;

  constructor(status: number, code: string, message: string, field?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.field = field;
  }
}

interface ErrorEnvelope {
  error: { code: string; message: string; field?: string };
}

function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  if (typeof value !== "object" || value === null || !("error" in value)) return false;
  const err = (value as { error: unknown }).error;
  return (
    typeof err === "object" &&
    err !== null &&
    typeof (err as { code?: unknown }).code === "string" &&
    typeof (err as { message?: unknown }).message === "string"
  );
}

// ---------------------------------------------------------------- token session

let accessToken: string | null = null;
let refreshInFlight: Promise<string | null> | null = null;
let onSessionLost: (() => void) | null = null;

export const tokenStore = {
  get: () => accessToken,
  set: (token: string | null) => {
    accessToken = token;
  },
  /** Called when a refresh fails, so the UI can return to the sign-in page. */
  onSessionLost: (handler: (() => void) | null) => {
    onSessionLost = handler;
  },
};

/** Resolves to a fresh access token, or null when the session has ended. */
export function refreshAccessToken(): Promise<string | null> {
  refreshInFlight ??= fetch(`${API_BASE_URL}/auth/refresh`, {
    method: "POST",
    credentials: "include",
    headers: { Accept: "application/json" },
  })
    .then(async (res) => {
      if (!res.ok) return null;
      const body = (await res.json()) as { access_token: string };
      return body.access_token;
    })
    .catch(() => null)
    .then((token) => {
      tokenStore.set(token);
      return token;
    })
    .finally(() => {
      refreshInFlight = null;
    });
  return refreshInFlight;
}

// --------------------------------------------------------------------- requests

export interface RequestOptions extends Omit<RequestInit, "body"> {
  /** Non-2xx statuses whose JSON body is a valid response (e.g. 503 from /ready). */
  acceptStatuses?: number[];
  /** JSON body; serialised automatically. */
  json?: unknown;
  /** Skip the Authorization header and refresh logic (public endpoints). */
  anonymous?: boolean;
}

async function send(path: string, options: RequestOptions, token: string | null) {
  // Strip our own options; everything else is passed to fetch unchanged.
  const { json, headers, ...rest } = options;
  const init: RequestInit = { ...rest };
  delete (init as RequestOptions).acceptStatuses;
  delete (init as RequestOptions).anonymous;
  const finalHeaders: Record<string, string> = {
    Accept: "application/json",
    ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(headers as Record<string, string> | undefined),
  };
  try {
    return await fetch(`${API_BASE_URL}${path}`, {
      credentials: "include",
      ...init,
      headers: finalHeaders,
      body: json !== undefined ? JSON.stringify(json) : undefined,
    });
  } catch {
    throw new ApiError(0, "network_error", "Cannot reach the AgriOS server. Check your connection.");
  }
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { acceptStatuses = [], anonymous = false } = options;
  let res = await send(path, options, anonymous ? null : tokenStore.get());

  if (res.status === 401 && !anonymous) {
    const token = await refreshAccessToken();
    if (token) {
      res = await send(path, options, token);
    } else {
      onSessionLost?.();
    }
  }

  if (res.status === 204) return undefined as T;
  const body: unknown = await res.json().catch(() => null);

  if (res.ok || acceptStatuses.includes(res.status)) {
    return body as T;
  }
  if (isErrorEnvelope(body)) {
    throw new ApiError(res.status, body.error.code, body.error.message, body.error.field);
  }
  throw new ApiError(res.status, "http_error", `Request failed (${res.status}).`);
}

// ------------------------------------------------------------------ uploads

function xhrSend(path: string, form: FormData, token: string | null,
  onProgress?: (fraction: number) => void): Promise<{ status: number; body: unknown }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}${path}`);
    xhr.withCredentials = true;
    xhr.setRequestHeader("Accept", "application/json");
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress?.(e.loaded / e.total);
    };
    xhr.onload = () => {
      let body: unknown;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        body = null;
      }
      resolve({ status: xhr.status, body });
    };
    xhr.onerror = () =>
      reject(new ApiError(0, "network_error", "Cannot reach the AgriOS server. Check your connection."));
    xhr.send(form);
  });
}

/**
 * Multipart upload with progress (fetch cannot report upload progress). Same session
 * rules as apiRequest: in-memory token, one refresh on 401, error envelope parsing.
 */
export async function uploadForm<T>(path: string, form: FormData,
  onProgress?: (fraction: number) => void): Promise<T> {
  let res = await xhrSend(path, form, tokenStore.get(), onProgress);
  if (res.status === 401) {
    const token = await refreshAccessToken();
    if (!token) {
      onSessionLost?.();
    } else {
      res = await xhrSend(path, form, token, onProgress);
    }
  }
  if (res.status >= 200 && res.status < 300) return res.body as T;
  if (isErrorEnvelope(res.body)) {
    const e = res.body.error;
    throw new ApiError(res.status, e.code, e.message, e.field);
  }
  throw new ApiError(res.status, "http_error", `Upload failed (${res.status}).`);
}
