import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SystemStatusCard } from "@/features/system/SystemStatusCard";
import { jsonResponse, mockFetch } from "../helpers";

function renderCard() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SystemStatusCard />
    </QueryClientProvider>,
  );
}

const health = () =>
  jsonResponse({ status: "ok", service: "agrios-api", version: "0.1.0", environment: "test" });

describe("SystemStatusCard", () => {
  it("shows online API and connected database", async () => {
    mockFetch({
      "/api/v1/health": health,
      "/api/v1/ready": () => jsonResponse({ status: "ready", checks: { database: "ok" } }),
    });
    renderCard();
    expect(await screen.findByText("Online")).toBeInTheDocument();
    expect(await screen.findByText("Connected")).toBeInTheDocument();
    expect(screen.getByText("API version 0.1.0")).toBeInTheDocument();
  });

  it("shows database unavailable from a 503 readiness response", async () => {
    mockFetch({
      "/api/v1/health": health,
      "/api/v1/ready": () =>
        jsonResponse({ status: "not_ready", checks: { database: "unavailable" } }, 503),
    });
    renderCard();
    expect(await screen.findByText("Unavailable")).toBeInTheDocument();
  });

  it("shows the API as unreachable when the network fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    renderCard();
    expect(await screen.findByText("Unreachable")).toBeInTheDocument();
    expect(await screen.findByText("Unknown")).toBeInTheDocument();
  });
});
