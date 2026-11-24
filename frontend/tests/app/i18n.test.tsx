import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { UR } from "@/i18n/messages";
import { jsonResponse, mockFetch, renderRoute, signedIn, testUser } from "../helpers";

const overview = {
  counts: { farms: 0, fields: 0, total_area_ha: 0, cycles_by_status: { planned: 0, active: 0, harvested: 0, abandoned: 0 } },
  active_cycles: [], upcoming: [], recent_changes: [],
  intelligence: {
    crop_health: { cases: 0, awaiting_analysis: 0, needs_follow_up: 0, model_availability: "not_registered" },
    soil: { observations: 0, fields_with_tests: 0, latest_sampled_on: null }, weather: { farms: 0, farms_with_location: 0 },
    irrigation: { growing_cycles: 0, cycles_with_estimate: 0 }, agents: { runs: 0, pending_approvals: 0 },
  },
};  // prettier-ignore

function as(locale: "en" | "ur") {
  const user = { ...testUser, locale };
  return {
    ...signedIn,
    "POST /api/v1/auth/refresh": () => jsonResponse({ access_token: "tok", token_type: "bearer", expires_in: 900, user }),
    "GET /api/v1/auth/me": () => jsonResponse(user),
    "GET /api/v1/overview": () => jsonResponse(overview),
  };
}

describe("EN/UR foundation", () => {
  afterEach(() => {
    document.documentElement.dir = "ltr";
    document.documentElement.lang = "en";
  });

  it("shows Urdu navigation right-to-left for an Urdu user", async () => {
    mockFetch(as("ur"));
    renderRoute("/");
    const nav = (await screen.findAllByRole("navigation", { name: "Main" }))[0]!;
    expect(within(nav).getByRole("link", { name: new RegExp(UR["nav.crop-doctor"]!) })).toHaveAttribute("href", "/crop-doctor");
    expect(within(nav).getByText(UR["group.Planning"]!)).toBeInTheDocument();
    await waitFor(() => expect(document.documentElement.dir).toBe("rtl"));
    expect(document.documentElement.lang).toBe("ur");
  });

  it("keeps English left-to-right by default", async () => {
    mockFetch(as("en"));
    renderRoute("/");
    const nav = (await screen.findAllByRole("navigation", { name: "Main" }))[0]!;
    expect(within(nav).getByRole("link", { name: /Crop Doctor/ })).toBeInTheDocument();
    await waitFor(() => expect(document.documentElement.lang).toBe("en"));
    expect(document.documentElement.dir).toBe("ltr");
  });
});
