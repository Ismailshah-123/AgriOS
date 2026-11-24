import { describe, expect, it, vi } from "vitest";
import { ApiError, apiRequest, tokenStore } from "@/services/api/client";
import { getReadiness } from "@/services/api/system";
import { callsTo, jsonResponse, mockFetch } from "../helpers";

describe("apiRequest", () => {
  it("returns parsed JSON on success", async () => {
    mockFetch({ "/api/v1/health": () => jsonResponse({ status: "ok" }) });
    await expect(apiRequest("/health")).resolves.toEqual({ status: "ok" });
  });

  it("maps the error envelope to ApiError", async () => {
    mockFetch({
      "/api/v1/thing": () =>
        jsonResponse(
          { error: { code: "file_too_large", message: "Image exceeds 8 MB.", field: "file" } },
          413,
        ),
    });
    const err = await apiRequest("/thing").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({
      status: 413,
      code: "file_too_large",
      message: "Image exceeds 8 MB.",
      field: "file",
    });
  });

  it("falls back to a generic error when the body is not an envelope", async () => {
    mockFetch({ "/api/v1/thing": () => new Response("<html>bad gateway</html>", { status: 502 }) });
    await expect(apiRequest("/thing")).rejects.toMatchObject({ status: 502, code: "http_error" });
  });

  it("reports network failures without leaking internals", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(apiRequest("/health")).rejects.toMatchObject({ status: 0, code: "network_error" });
  });

  it("treats a 503 readiness body as a valid response", async () => {
    const body = { status: "not_ready", checks: { database: "unavailable" } };
    mockFetch({ "/api/v1/ready": () => jsonResponse(body, 503) });
    await expect(getReadiness()).resolves.toEqual(body);
  });
});

describe("session handling", () => {
  it("sends the in-memory token and never stores it in web storage", async () => {
    tokenStore.set("abc");
    const fetchMock = mockFetch({ "/api/v1/farms": () => jsonResponse({ items: [] }) });
    await apiRequest("/farms");
    const headers = fetchMock.mock.calls[0]![1]!.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer abc");
    expect(localStorage.length + sessionStorage.length).toBe(0);
  });

  it("refreshes once on 401 and retries with the new token", async () => {
    tokenStore.set("expired");
    const seen: string[] = [];
    const fetchMock = mockFetch({
      "POST /api/v1/auth/refresh": () => jsonResponse({ access_token: "fresh" }),
      "GET /api/v1/farms": ({ init }) => {
        const auth = (init?.headers as Record<string, string>).Authorization!;
        seen.push(auth);
        return auth === "Bearer fresh"
          ? jsonResponse({ items: [] })
          : jsonResponse({ error: { code: "token_expired", message: "Your session has expired." } }, 401);
      },
    });
    await expect(apiRequest("/farms")).resolves.toEqual({ items: [] });
    expect(seen).toEqual(["Bearer expired", "Bearer fresh"]);
    expect(callsTo(fetchMock, "POST", "/api/v1/auth/refresh")).toHaveLength(1);
  });

  it("shares one refresh between concurrent 401s", async () => {
    tokenStore.set("expired");
    const fetchMock = mockFetch({
      "POST /api/v1/auth/refresh": () => jsonResponse({ access_token: "fresh" }),
      "GET /api/v1/a": ({ init }) =>
        (init?.headers as Record<string, string>).Authorization === "Bearer fresh"
          ? jsonResponse({ ok: 1 })
          : jsonResponse({ error: { code: "token_expired", message: "x" } }, 401),
    });
    await Promise.all([apiRequest("/a"), apiRequest("/a"), apiRequest("/a")]);
    expect(callsTo(fetchMock, "POST", "/api/v1/auth/refresh")).toHaveLength(1);
  });

  it("reports a lost session when the refresh fails", async () => {
    tokenStore.set("expired");
    const lost = vi.fn();
    tokenStore.onSessionLost(lost);
    mockFetch({
      "POST /api/v1/auth/refresh": () => jsonResponse({ error: { code: "session_expired", message: "x" } }, 401),
      "GET /api/v1/farms": () => jsonResponse({ error: { code: "token_expired", message: "Expired." } }, 401),
    });
    await expect(apiRequest("/farms")).rejects.toMatchObject({ status: 401 });
    expect(lost).toHaveBeenCalledOnce();
    expect(tokenStore.get()).toBeNull();
    tokenStore.onSessionLost(null);
  });
});
