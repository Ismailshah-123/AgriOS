import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import axe from "axe-core";
import { createMemoryRouter, RouterProvider } from "react-router";
import { expect, vi } from "vitest";
import { routes } from "@/app/routes";
import { AuthProvider } from "@/features/auth/AuthProvider";
import { tokenStore } from "@/services/api/client";
import type { Page, User } from "@/services/api/types";

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export const noContent = () => new Response(null, { status: 204 });

export function page<T>(items: T[]): Page<T> {
  return { items, next_cursor: null };
}

type Handler = (req: { url: URL; init?: RequestInit; body: unknown }) => Response | Promise<Response>;

/**
 * Stub global fetch. Keys are "METHOD /path" or just "/path" (any method).
 * Unknown requests fail loudly so tests never hit an unexpected endpoint.
 */
export function mockFetch(handlers: Record<string, Handler>) {
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(typeof input === "string" ? input : input.toString(), "http://localhost");
    const method = (init?.method ?? "GET").toUpperCase();
    const handler = handlers[`${method} ${url.pathname}`] ?? handlers[url.pathname];
    if (!handler) throw new Error(`Unexpected fetch: ${method} ${url.pathname}`);
    const body = typeof init?.body === "string" ? JSON.parse(init.body) : undefined;
    return handler({ url, init, body });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

/** Requests made to `path` (any method), with parsed JSON bodies. */
export function callsTo(fn: ReturnType<typeof mockFetch>, method: string, path: string) {
  return fn.mock.calls
    .filter(([u, init]) => {
      const p = new URL(String(u), "http://localhost").pathname;
      return p === path && (init?.method ?? "GET").toUpperCase() === method;
    })
    .map(([u, init]) => ({
      url: new URL(String(u), "http://localhost"),
      body: typeof init?.body === "string" ? JSON.parse(init.body) : undefined,
    }));
}

export const testUser: User = {
  id: "u-1",
  email: "amina@example.com",
  full_name: "Amina Khan",
  role: "farmer",
  locale: "en",
  created_at: "2026-11-01T00:00:00Z",
};

/** Handlers that restore a signed-in session on load (silent refresh + /auth/me). */
export const signedIn: Record<string, Handler> = {
  "POST /api/v1/auth/refresh": () =>
    jsonResponse({ access_token: "tok", token_type: "bearer", expires_in: 900, user: testUser }),
  "GET /api/v1/auth/me": () => jsonResponse(testUser),
};

/** Handlers for an anonymous visitor (refresh cookie missing). */
export const signedOut: Record<string, Handler> = {
  "POST /api/v1/auth/refresh": () =>
    jsonResponse({ error: { code: "session_expired", message: "Your session has ended." } }, 401),
};

export const healthy: Record<string, Handler> = {
  "/api/v1/health": () =>
    jsonResponse({ status: "ok", service: "agrios-api", version: "0.1.0", environment: "test" }),
  "/api/v1/ready": () => jsonResponse({ status: "ready", checks: { database: "ok" } }),
};

export function renderRoute(path: string) {
  tokenStore.set(null);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const view = render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>,
  );
  return { ...view, router };
}

/**
 * Automated accessibility check (axe-core). Colour contrast is excluded only because
 * jsdom cannot compute styles; token contrast is verified separately (globals.css).
 */
export async function expectNoA11yViolations(container: Element) {
  const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
  const summary = results.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.length})`);
  expect(summary).toEqual([]);
}

// ------------------------------------------------------------------ fake XHR

export interface XhrCall {
  method: string;
  url: string;
  headers: Record<string, string>;
  form: FormData;
}

/** Replaces XMLHttpRequest for multipart uploads; emits progress, then responds. */
export function mockXhr(respond: (call: XhrCall) => { status: number; body: unknown }) {
  const calls: XhrCall[] = [];
  class FakeXhr {
    status = 0;
    responseText = "";
    withCredentials = false;
    upload: { onprogress: ((e: { lengthComputable: boolean; loaded: number; total: number }) => void) | null } = {
      onprogress: null,
    };
    onload: (() => void) | null = null;
    onerror: (() => void) | null = null;
    private call: Partial<XhrCall> = { headers: {} };
    open(method: string, url: string) {
      this.call.method = method;
      this.call.url = url;
    }
    setRequestHeader(k: string, v: string) {
      this.call.headers![k] = v;
    }
    send(form: FormData) {
      const call = { ...this.call, form } as XhrCall;
      calls.push(call);
      setTimeout(() => {
        this.upload.onprogress?.({ lengthComputable: true, loaded: 50, total: 100 });
        const r = respond(call);
        if (r.status === 0) return this.onerror?.(); // simulate a dropped connection
        this.status = r.status;
        this.responseText = JSON.stringify(r.body);
        this.onload?.();
      }, 0);
    }
  }
  vi.stubGlobal("XMLHttpRequest", FakeXhr);
  return calls;
}

export function photoFile(name = "leaf.jpg", type = "image/jpeg", size = 1024): File {
  return new File([new Uint8Array(size)], name, { type });
}
