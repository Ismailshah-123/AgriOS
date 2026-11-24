import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { CycleEconomics } from "@/services/api/economics";
import { callsTo, expectNoA11yViolations, jsonResponse, mockFetch, page, renderRoute, signedIn, testUser } from "../helpers";

const cycle = {
  id: "cy-1", field_id: "fd-1", field_name: "North Field", farm_id: "f-1", farm_name: "Green Acres",
  crop: { id: "c-1", code: "tomato", name_en: "Tomato", name_ur: null, scientific_name: null },
  variety: null, season: null, status: "active", sowing_date: "2026-09-01", expected_harvest_date: null,
  harvest_date: null, area_ha: null, notes: null, created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-01T00:00:00Z",
};  // prettier-ignore

const econ: CycleEconomics = {
  cycle: { id: "cy-1", crop_name: "Tomato", field_name: "North Field", farm_name: "Green Acres", status: "active", area_ha: "2.0000" },
  currency: "PKR",
  expenses: [{ id: "e-1", crop_cycle_id: "cy-1", category: "fertilizer", amount_pkr: "20000.00", incurred_on: "2026-10-01", note: "DAP", currency: "PKR", data_origin: "farmer_entered" }],
  harvests: [
    { id: "h-1", crop_cycle_id: "cy-1", recorded_on: "2026-11-01", quantity_kg: "2000.00", price_pkr_per_kg: "30.00", buyer: "Mandi", note: null, revenue_pkr: "60000.00", currency: "PKR", data_origin: "farmer_entered" },
    { id: "h-2", crop_cycle_id: "cy-1", recorded_on: "2026-11-05", quantity_kg: "300.00", price_pkr_per_kg: null, buyer: null, note: null, revenue_pkr: null, currency: "PKR", data_origin: "farmer_entered" },
  ],
  summary: {
    total_cost_pkr: "20000.00", cost_by_category_pkr: { fertilizer: "20000.00" }, harvested_kg: "2300.00", sold_kg: "2000.00",
    unsold_kg: "300.00", revenue_pkr: "60000.00", profit_pkr: "40000.00", average_price_pkr_per_kg: "30.00",
    cost_per_ha_pkr: "10000.00", cost_per_acre_pkr: "4046.86", break_even_price_pkr_per_kg: "8.70", break_even_yield_kg: "666.67",
  },
  definitions: ["Profit = revenue - total cost (negative = loss)."],
  limitations: ["Calculated only from the records you entered; nothing is estimated or filled in."],
};  // prettier-ignore

describe("Farm Economics", () => {
  it("shows PKR totals from the API, validates and saves an expense, and deletes a harvest", async () => {
    const fetchMock = mockFetch({
      ...signedIn,
      "GET /api/v1/crop-cycles": () => jsonResponse(page([cycle])),
      "GET /api/v1/crop-cycles/cy-1/economics": () => jsonResponse(econ),
      "POST /api/v1/expenses": () => jsonResponse(econ.expenses[0], 201),
      "DELETE /api/v1/harvest-sales/h-2": () => new Response(null, { status: 204 }),
    });
    const user = userEvent.setup();
    const { container } = renderRoute("/economics");
    const summary = await screen.findByRole("region", { name: "Economics summary" });
    expect(within(summary).getByText("PKR 20,000.00")).toBeInTheDocument();
    expect(within(summary).getByText("PKR 40,000.00")).toBeInTheDocument();
    expect(within(summary).getByText("Profit")).toBeInTheDocument();
    expect(within(summary).getByText("PKR 4,046.86 per acre")).toBeInTheDocument();
    expect(screen.getByText("Not sold")).toBeInTheDocument();
    expect(screen.getByRole("listitem", { name: "Oct 26: PKR 20,000.00" })).toBeInTheDocument(); // costs per month
    expect(screen.getByRole("list", { name: "Costs by category for this crop cycle" })).toHaveTextContent(/Fertilizer.*PKR 20,000.00/);
    await expectNoA11yViolations(container);

    await user.click(screen.getByRole("button", { name: "Add expense" }));
    const dialog = await screen.findByRole("dialog", { name: "Add an expense" });
    await user.type(within(dialog).getByLabelText("Amount (PKR)"), "12.345");
    await user.click(within(dialog).getByRole("button", { name: "Save expense" }));
    expect(await within(dialog).findByText(/at most 2 decimals/)).toBeInTheDocument();
    await user.clear(within(dialog).getByLabelText("Amount (PKR)"));
    await user.type(within(dialog).getByLabelText("Amount (PKR)"), "1500.50");
    await user.selectOptions(within(dialog).getByLabelText("Category"), "labour");
    await user.click(within(dialog).getByRole("button", { name: "Save expense" }));
    await waitFor(() => expect(callsTo(fetchMock, "POST", "/api/v1/expenses")).toHaveLength(1));
    expect(callsTo(fetchMock, "POST", "/api/v1/expenses")[0]!.body).toMatchObject({ crop_cycle_id: "cy-1", category: "labour", amount_pkr: "1500.50" });

    await user.click(screen.getByRole("button", { name: "Delete harvest of 5 Nov 2026" }));
    await user.click(within(await screen.findByRole("dialog", { name: "Delete harvest of 5 Nov 2026?" })).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(callsTo(fetchMock, "DELETE", "/api/v1/harvest-sales/h-2")).toHaveLength(1));
  });

  it("shows a loss and dashes, never zeros, for unknown break-even values", async () => {
    const loss = { ...econ, harvests: [], summary: { ...econ.summary, revenue_pkr: "0.00", profit_pkr: "-20000.00", break_even_price_pkr_per_kg: null, break_even_yield_kg: null } };
    mockFetch({ ...signedIn, "GET /api/v1/crop-cycles": () => jsonResponse(page([cycle])), "GET /api/v1/crop-cycles/cy-1/economics": () => jsonResponse(loss) });
    renderRoute("/economics");
    const summary = await screen.findByRole("region", { name: "Economics summary" });
    expect(within(summary).getByText("Loss")).toBeInTheDocument();
    expect(within(summary).getByText("Needs harvest and sales records")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "No harvest recorded" })).toBeInTheDocument();
  });
});

describe("Nutrient Management (FR6)", () => {
  it("shows the refusal and never a dose when no reviewed table exists", async () => {
    mockFetch({
      ...signedIn,
      "GET /api/v1/crop-cycles": () => jsonResponse(page([cycle])),
      "GET /api/v1/crop-cycles/cy-1/fertilizer": () => jsonResponse({
        crop_cycle_id: "cy-1", crop_code: "tomato", status: "refused", reason: "no_reviewed_source",
        message: "No reviewed, cited fertilizer requirement table is stored for Tomato.", escalation: "expert_review",
        doses: null, soil_test_note: "Soil tests are on the Soil page.",
      }),
    });  // prettier-ignore
    const { container } = renderRoute("/nutrients");
    expect(await screen.findByRole("heading", { name: "No verified fertilizer guidance" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("No reviewed, cited fertilizer requirement table");
    expect(screen.queryByText(/kg\/(ha|acre)/)).not.toBeInTheDocument();
    await expectNoA11yViolations(container);
  });
});

describe("Expert review", () => {
  const expert = { ...testUser, role: "expert" as const };
  const asExpert = {
    ...signedIn,
    "POST /api/v1/auth/refresh": () => jsonResponse({ access_token: "tok", token_type: "bearer", expires_in: 900, user: expert }),
    "GET /api/v1/auth/me": () => jsonResponse(expert),
  };
  const caseDetail = {
    id: "case-1", reference: "TC-0001", number: 1, status: "expert_review", inference_status: "model_unavailable",
    crop: { id: "c-1", code: "tomato", name: "Tomato" }, field: { id: "fd-1", name: "North Field" }, farm: { id: "f-1", name: "Green Acres" },
    consent_training: false, submissions: [{ id: "s1", kind: "initial", plant_part: "leaf", symptoms: ["spots"], observed_on: null, notes: "Brown spots",
      submitted_at: "2026-11-23T08:00:00Z", images: [{ id: "i1", position: 0, width: 400, height: 300, url: "/full", thumb_url: "/thumb", urls_expire_at: "2026-11-23T08:10:00Z" }] }],
    analysis: { inference_status: "model_unavailable", model_availability: "not_registered", error_code: null, message: "No model.", can_retry: true, result: null },
    timeline: [], expert_reviews: [], created_at: "2026-11-23T08:00:00Z", last_activity_at: "2026-11-23T08:00:00Z",
  };  // prettier-ignore

  it("lets an expert see the queue in navigation, open a case and submit a labelled diagnosis", async () => {
    const fetchMock = mockFetch({
      ...asExpert,
      "GET /api/v1/review/queue": () => jsonResponse([{ case_id: "case-1", number: 1, crop_name: "Tomato", status: "expert_review", waiting_since: "2026-11-23T08:00:00Z", image_count: 1 }]),
      "GET /api/v1/review/cases/case-1": () => jsonResponse({ case: caseDetail, awaiting_review: true }),
      "POST /api/v1/review/cases/case-1": () => jsonResponse({ id: "r1", decision: "diagnosed", label: "Early blight", note: null, expert_name: "Dr A", reviewed_at: "2026-11-24T01:00:00Z", source: "expert_review" }, 201),
    });  // prettier-ignore
    const user = userEvent.setup();
    renderRoute("/review");
    const nav = (await screen.findAllByRole("navigation", { name: "Main" }))[0]!;
    expect(within(nav).getByRole("link", { name: /Expert Review/ })).toHaveAttribute("href", "/review");
    await user.click(await screen.findByRole("link", { name: /Case #1 · Tomato/ }));
    expect(await screen.findByText(/No model result: no model installed/)).toBeInTheDocument();
    expect(screen.getByText("“Brown spots”")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Submit review" }));
    expect(await screen.findByText("Enter the diagnosis label for this decision.")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Diagnosis label"), "Early blight");
    await user.click(screen.getByRole("button", { name: "Submit review" }));
    await waitFor(() => expect(callsTo(fetchMock, "POST", "/api/v1/review/cases/case-1")).toHaveLength(1));
    expect(callsTo(fetchMock, "POST", "/api/v1/review/cases/case-1")[0]!.body).toEqual({ decision: "diagnosed", label: "Early blight", note: null });
  });

  it("lets the farmer ask an expert, then shows the expert outcome apart from the model", async () => {
    let reviewed = false;
    const farmerCase = () => ({ ...caseDetail, status: reviewed ? "closed" : "submitted",
      expert_reviews: reviewed ? [{ id: "r1", decision: "diagnosed", label: "Early blight", note: "Remove lower leaves.", expert_name: "Dr A", reviewed_at: "2026-11-24T01:00:00Z", source: "expert_review" }] : [] });  // prettier-ignore
    const fetchMock = mockFetch({
      ...signedIn,
      "GET /api/v1/cases/case-1": () => jsonResponse(farmerCase()),
      "POST /api/v1/cases/case-1/expert-review": () => new Response(null, { status: 204 }),
    });
    const user = userEvent.setup();
    const { unmount } = renderRoute("/crop-doctor/cases/case-1");
    await user.click(await screen.findByRole("button", { name: "Ask an expert" }));
    await waitFor(() => expect(callsTo(fetchMock, "POST", "/api/v1/cases/case-1/expert-review")).toHaveLength(1));
    unmount();
    reviewed = true;
    renderRoute("/crop-doctor/cases/case-1");
    expect(await screen.findByText("Expert diagnosis")).toBeInTheDocument();
    expect(screen.getByText("Early blight")).toBeInTheDocument();
    expect(screen.getByText("Remove lower leaves.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ask an expert" })).not.toBeInTheDocument();
  });

  it("tells a farmer account the queue is for experts only", async () => {
    mockFetch({ ...signedIn, "GET /api/v1/review/queue": () => jsonResponse({ error: { code: "forbidden", message: "No." } }, 403) });
    renderRoute("/review");
    expect(await screen.findByRole("heading", { name: "Experts only" })).toBeInTheDocument();
  });
});
