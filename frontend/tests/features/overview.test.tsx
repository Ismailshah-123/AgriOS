import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { Overview } from "@/services/api/types";
import { expectNoA11yViolations, jsonResponse, mockFetch, renderRoute, signedIn } from "../helpers";

const empty: Overview = {
  counts: { farms: 0, fields: 0, total_area_ha: 0, cycles_by_status: { planned: 0, active: 0, harvested: 0, abandoned: 0 } },
  active_cycles: [],
  upcoming: [],
  recent_changes: [],
  intelligence: {
    crop_health: { cases: 0, awaiting_analysis: 0, needs_follow_up: 0, model_availability: "not_registered" },
    soil: { observations: 0, fields_with_tests: 0, latest_sampled_on: null },
    weather: { farms: 0, farms_with_location: 0 },
    irrigation: { growing_cycles: 0, cycles_with_estimate: 0 },
    agents: { runs: 0, pending_approvals: 0 },
  },
};  // prettier-ignore

const brief = {
  id: "cy-1", crop_name: "Wheat", variety: "Akbar-2019", field_name: "North Field",
  farm_name: "Green Acres", status: "active" as const, sowing_date: "2026-11-05",
  expected_harvest_date: "2027-04-20",
};  // prettier-ignore

const populated: Overview = {
  counts: { farms: 2, fields: 3, total_area_ha: 4.5, cycles_by_status: { planned: 1, active: 2, harvested: 0, abandoned: 0 } },
  active_cycles: [brief],
  upcoming: [{ kind: "expected_harvest", date: "2026-12-10", source: "farmer_entered", cycle: brief }],
  recent_changes: [
    { action: "crop_cycle.created", entity: "crop_cycle", entity_id: "cy-1", name: "Wheat on North Field", created_at: "2026-11-22T09:15:00Z" },
    { action: "farm.deleted", entity: "farm", entity_id: "f-9", name: null, created_at: "2026-11-21T08:00:00Z" },
  ],
  intelligence: {
    crop_health: { cases: 3, awaiting_analysis: 1, needs_follow_up: 2, model_availability: "not_registered" },
    soil: { observations: 2, fields_with_tests: 1, latest_sampled_on: "2026-10-01" },
    weather: { farms: 2, farms_with_location: 1 },
    irrigation: { growing_cycles: 2, cycles_with_estimate: 1 },
    agents: { runs: 4, pending_approvals: 1 },
  },
};  // prettier-ignore


const analytics = {
  generated_at: "2026-11-24T01:00:00Z",
  area_by_crop: [{ crop: "Tomato", cycles: 1, area_ha: 2 }, { crop: "Wheat", cycles: 1, area_ha: 1 }],
  cases: {
    by_status: { submitted: 0, retake: 0, unsure: 0, accepted: 0, out_of_scope: 0, expert_review: 1, closed: 2 },
    by_month: ["2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11"].map((m, i) => ({ month: m, cases: i === 5 ? 3 : 0 })),
  },
  pending_expert_reviews: 1,
  economics: {
    currency: "PKR", total_cost_pkr: "1500.50", total_revenue_pkr: "3000.00", profit_pkr: "1499.50",
    cost_by_category_pkr: { seed: "1000.00", labour: "500.50" },
    cycles: [{ crop_cycle_id: "cy-1", crop: "Tomato", field: "North Field", cost_pkr: "1500.50", revenue_pkr: "3000.00", profit_pkr: "1499.50" }],
  },
};  // prettier-ignore
describe("Overview dashboard", () => {
  it("guides a new farmer and shows no invented values", async () => {
    mockFetch({ ...signedIn, "GET /api/v1/overview": () => jsonResponse(empty) });
    renderRoute("/");
    expect(await screen.findByRole("heading", { name: "Get started" })).toBeInTheDocument();
    expect(screen.getAllByText("(to do)")).toHaveLength(3);
    const summary = screen.getByRole("region", { name: "Farm summary" });
    expect(within(summary).getAllByText("0")).toHaveLength(4);
    expect(screen.getByText("No model installed")).toBeInTheDocument();
    expect(screen.getByText("Add a farm with its location to see weather.")).toBeInTheDocument();
    expect(screen.getByText("Nothing to review")).toBeInTheDocument();
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/°C|\bmm\b|PKR|Rs\.?\s?\d|%/);
  });

  it("shows real counts, crops, upcoming dates with their origin, and recent changes", async () => {
    mockFetch({ ...signedIn, "GET /api/v1/overview": () => jsonResponse(populated), "GET /api/v1/analytics": () => jsonResponse(analytics) });
    renderRoute("/");
    expect(await screen.findByText("2 farms · 3 fields · 4.5 ha recorded")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Get started" })).not.toBeInTheDocument();
    const summary = screen.getByRole("region", { name: "Farm summary" });
    expect(within(summary).getByText("4.5 ha in total")).toBeInTheDocument();
    expect(screen.getByText("Expected harvest: Wheat")).toBeInTheDocument();
    expect(screen.getByText("10 Dec 2026")).toBeInTheDocument();
    expect(screen.getByText("Farmer entered")).toBeInTheDocument();
    expect(screen.getByText("Crop cycle started")).toBeInTheDocument();
    expect(screen.getByText(/Wheat on North Field/)).toBeInTheDocument();
    expect(screen.getByText(/deleted record/)).toBeInTheDocument();
    // Intelligence card: counts straight from the API, each linking to its module.
    expect(screen.getByText("3 cases · 1 awaiting analysis · 2 need follow-up")).toBeInTheDocument();
    expect(screen.getByText("2 soil tests on 1 field, latest 1 Oct 2026")).toBeInTheDocument();
    expect(screen.getByText("Forecast available for 1 of 2 farms (farm location set).")).toBeInTheDocument();
    expect(screen.getByText("FAO-56 estimate for 1 of 2 growing crops.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /AI agents\s*1 to review/ })).toHaveAttribute("href", "/agents");
  });

  it("shows an error with retry when the overview cannot load", async () => {
    let fail = true;
    mockFetch({
      ...signedIn,
      "GET /api/v1/overview": () =>
        fail
          ? jsonResponse({ error: { code: "database_unavailable", message: "The service is temporarily unavailable. Try again shortly." } }, 503)
          : jsonResponse(empty),
    });
    const user = userEvent.setup();
    renderRoute("/");
    expect(await screen.findByRole("heading", { name: "Could not load your overview" })).toBeInTheDocument();
    fail = false;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: "Get started" })).toBeInTheDocument();
  });

  it("has no automated accessibility violations", async () => {
    mockFetch({ ...signedIn, "GET /api/v1/overview": () => jsonResponse(populated), "GET /api/v1/analytics": () => jsonResponse(analytics) });
    const { container } = renderRoute("/");
    await screen.findByText("Expected harvest: Wheat");
    await expectNoA11yViolations(container);
  });
  it("charts only the API's own sums and counts, with units", async () => {
    mockFetch({ ...signedIn, "GET /api/v1/overview": () => jsonResponse(populated), "GET /api/v1/analytics": () => jsonResponse(analytics) });
    renderRoute("/");
    const section = await screen.findByRole("region", { name: "Farm analytics" });
    expect(within(section).getByText("3 ha")).toBeInTheDocument();
    expect(within(section).getAllByText("PKR 1,499.50")).toHaveLength(2); // profit tile + cycle table
    expect(within(section).getByRole("list", { name: "Growing area by crop" })).toHaveTextContent(/Tomato.*2 ha.*Wheat.*1 ha/);
    expect(within(section).getByRole("listitem", { name: /Nov 26: 3 cases/ })).toBeInTheDocument();
    expect(within(section).getByRole("list", { name: "Costs by category" })).toHaveTextContent(/Seed.*PKR 1,000.00.*Labour.*PKR 500.50/);
    expect(within(section).getByRole("table", { name: "Profit by crop cycle" })).toHaveTextContent("Tomato · North Field");
  });
});