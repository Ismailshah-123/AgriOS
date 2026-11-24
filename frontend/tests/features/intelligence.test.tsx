import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { AgentRun } from "@/services/api/agents";
import type { WaterDemand, WeatherReport } from "@/services/api/intelligence";
import type { FieldRecord } from "@/services/api/types";
import { callsTo, expectNoA11yViolations, jsonResponse, mockFetch, page, renderRoute, signedIn } from "../helpers";

const field = {
  id: "fd-1", farm_id: "f-1", farm_name: "Green Acres", name: "North Field",
  area: { hectares: 1, value: 1, unit: "ha", data_origin: "measured" }, notes: null, active_cycle_count: 1,
} as FieldRecord;  // prettier-ignore
const fields = { "GET /api/v1/fields": () => jsonResponse(page([field])) };

const weather = {
  status: "stale", reason: "provider_error", data_origin: "retrieved",
  location: { farm_id: "f-1", farm_name: "Green Acres", field_id: "fd-1", latitude: 31.52, longitude: 74.36 },
  provider: { name: "Open-Meteo", url: "https://open-meteo.com/", licence: "CC BY 4.0", model: "blend" },
  retrieved_at: "2026-11-23T10:00:00Z", age_minutes: 95, timezone: "Asia/Karachi",
  units: { temperature: "°C", precipitation: "mm" },
  current: { time: "2026-11-23T15:00", temperature_c: 21.5, relative_humidity_pct: 60, precipitation_mm: 0, wind_speed_kmh: 7.2, weather_code: 1 },
  hourly: [{ time: "2026-11-23T16:00", temperature_c: 20, relative_humidity_pct: 65, precipitation_mm: 0, precipitation_probability_pct: 10 }],
  daily: [
    { date: "2026-11-24", temperature_max_c: 24, temperature_min_c: 11, precipitation_sum_mm: 70, precipitation_probability_max_pct: 80, wind_speed_max_kmh: 12, et0_fao_mm: 3.1 },
    { date: "2026-11-25", temperature_max_c: 23, temperature_min_c: 10, precipitation_sum_mm: null, precipitation_probability_max_pct: null, wind_speed_max_kmh: 10, et0_fao_mm: 3.0 },
  ],
  indicators: [{
    id: "heavy_rainfall", level: "watch", kind: "indicator", message: "Heavy rainfall forecast: 2026-11-24 70 mm (heavy).",
    basis: "IMD categories", source: "India Meteorological Department", review_status: "regional_classification",
    limitations: "Grid-cell model rainfall.", time_window: { start: "2026-11-24", end: "2026-11-24" }, evidence: {},
  }],
  not_evaluated: [{ indicator: "heat_stress", reason: "No reviewed crop-specific threshold source yet." }],
  disclaimer: "Forecasts are model estimates.",
} as unknown as WeatherReport;  // prettier-ignore
const water = {
  field_id: "fd-1", status: "unavailable", missing_information: ["crop_cycle.sowing_date"], limitations: [],
} as unknown as WaterDemand;  // prettier-ignore

describe("Weather Intelligence", () => {
  it("shows retrieved data with source, stale warning, risks and no invented values", async () => {
    mockFetch({
      ...signedIn, ...fields,
      "GET /api/v1/weather": () => jsonResponse(weather),
      "GET /api/v1/fields/fd-1/water-demand": () => jsonResponse(water),
    });
    renderRoute("/weather");
    expect(await screen.findByText("21.5 °C")).toBeInTheDocument();
    expect(screen.getByText(/Stale: provider unreachable/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open-Meteo" })).toHaveAttribute("href", "https://open-meteo.com/");
    expect(screen.getByText(/Heavy rainfall forecast/)).toBeInTheDocument();
    expect(screen.getByText(/heat stress \(No reviewed/)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /25 Nov 2026: — \(chance —\)/ })).toBeInTheDocument(); // missing day stays missing
    expect(await screen.findByText(/the sowing \/ transplanting date/)).toBeInTheDocument();
    expect(screen.getByLabelText("Field")).toHaveValue("fd-1");
  });

  it("asks for a farm location instead of guessing one", async () => {
    mockFetch({
      ...signedIn, ...fields,
      "GET /api/v1/weather": () =>
        jsonResponse({ ...weather, status: "unavailable", reason: "location_missing", current: null, daily: [], indicators: [] }),
    });
    renderRoute("/weather");
    expect(await screen.findByRole("heading", { name: "This farm has no location yet" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Edit farm location" })).toHaveAttribute("href", "/farms/f-1");
  });
});

describe("Smart Irrigation", () => {
  const ok = {
    field_id: "fd-1", status: "ok", data_origin: "inferred", units: { et0: "mm/day", etc: "mm/day", rain: "mm" },
    method: "ETc = Kc x ET0", source: "FAO-56 Tables 11-12", crop: "tomato", planting_date: "2026-10-01",
    days_after_planting: 53, current_stage: "development",
    daily: [
      { date: "2026-11-24", stage: "development", kc_low: 0.95, kc_high: 0.95, et0_mm: 3.1, etc_low_mm: 2.9, etc_high_mm: 2.9, rain_mm: 0 },
      { date: "2026-11-25", stage: "development", kc_low: 0.97, kc_high: 1.02, et0_mm: null, etc_low_mm: null, etc_high_mm: null, rain_mm: null },
    ],
    totals: { days: 2, et0_mm: 3.1, etc_low_mm: 2.9, etc_high_mm: 2.9, gross_rain_mm: 0 },
    effective_rainfall: "not_applied", soil_moisture: "not_measured", missing_information: [], limitations: ["Kc not calibrated for Pakistan."],
  } as WaterDemand;  // prettier-ignore

  it("shows the FAO-56 estimate day by day, keeps missing days empty and states what is not included", async () => {
    mockFetch({ ...signedIn, ...fields, "GET /api/v1/fields/fd-1/water-demand": () => jsonResponse(ok) });
    renderRoute("/irrigation");
    expect(await screen.findByRole("heading", { name: "Smart Irrigation" })).toBeInTheDocument();
    expect(await screen.findByText("2.9–2.9 mm")).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Daily crop water demand" });
    expect(within(table).getByText("0.97–1.02")).toBeInTheDocument();
    expect(within(table).getAllByText("—").length).toBeGreaterThanOrEqual(3); // missing ET0/ETc/rain stay missing
    expect(screen.getByText(/No irrigation schedule, depth or volume is calculated yet/)).toBeInTheDocument();
    expect(screen.getByTitle("Data origin: Estimated")).toBeInTheDocument();
  });

  it("explains what is missing instead of estimating", async () => {
    mockFetch({ ...signedIn, ...fields, "GET /api/v1/fields/fd-1/water-demand": () => jsonResponse(water) });
    renderRoute("/irrigation");
    expect(await screen.findByText(/the sowing \/ transplanting date/)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});

describe("Soil Intelligence", () => {
  it("validates the form and sends unmeasured values as null", async () => {
    const empty = { field_id: "fd-1", field_name: "North Field", observations: 0, latest: null, trends: {} };
    const fetchMock = mockFetch({
      ...signedIn, ...fields,
      "GET /api/v1/fields/fd-1/soil-summary": () => jsonResponse(empty),
      "GET /api/v1/soil-observations": () => jsonResponse([]),
      "POST /api/v1/soil-observations": () => jsonResponse({}, 201),
    });
    const user = userEvent.setup();
    renderRoute("/soil");
    expect(await screen.findByRole("heading", { name: "No soil test for this field yet" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Add soil test" }));
    const dialog = await screen.findByRole("dialog", { name: "Add a soil test" });
    await user.type(within(dialog).getByLabelText("Sample date"), "2026-10-15");
    await user.click(within(dialog).getByRole("button", { name: "Save soil test" }));
    expect(await within(dialog).findByText(/Enter at least one measured value/)).toBeInTheDocument();
    await user.type(within(dialog).getByLabelText("pH (pH units)", { exact: false }), "7.9");
    await user.type(within(dialog).getByLabelText(/^Laboratory/), "Test Lab");
    await user.click(within(dialog).getByRole("button", { name: "Save soil test" }));
    await waitFor(() => expect(callsTo(fetchMock, "POST", "/api/v1/soil-observations")).toHaveLength(1));
    const body = callsTo(fetchMock, "POST", "/api/v1/soil-observations")[0]!.body as Record<string, unknown>;
    expect(body).toMatchObject({ field_id: "fd-1", ph: "7.9", sulfur_mg_kg: null, zinc_mg_kg: null, data_origin: "measured" });
  });

  it("charts any measure with two or more tests, with its unit", async () => {
    const pt = (d: string, v: number) => ({ sampled_on: d, value: v, data_origin: "measured" });
    const latest = { id: "so-2", field_id: "fd-1", sampled_on: "2026-10-01", data_origin: "measured", created_at: "2026-10-02T00:00:00Z",
      lab_name: "Lab", lab_reference: null, depth_from_cm: null, depth_to_cm: null, ph: 8.0, ph_method: "unknown", ec_ds_m: 2.1,
      ec_method: "unknown", organic_matter_pct: null, organic_carbon_pct: null, nitrogen_total_pct: null, phosphorus_mg_kg: null,
      phosphorus_method: "unknown", potassium_mg_kg: null, calcium_mg_kg: null, magnesium_mg_kg: null, sulfur_mg_kg: null, zinc_mg_kg: null,
      iron_mg_kg: null, boron_mg_kg: null, cec_cmol_kg: null, texture: null, notes: null, units: {}, nutrient_methods: null,
      crops_considered: [], interpretation: { flags: [], warnings: [], not_evaluated: [], dose_policy: "No doses." } };  // prettier-ignore
    mockFetch({
      ...signedIn, ...fields,
      "GET /api/v1/fields/fd-1/soil-summary": () => jsonResponse({ field_id: "fd-1", field_name: "North Field", observations: 2, latest,
        trends: { ph: [pt("2026-04-01", 8.3), pt("2026-10-01", 8.0)], ec_ds_m: [pt("2026-04-01", 2.6), pt("2026-10-01", 2.1)], potassium_mg_kg: [pt("2026-10-01", 110)] } }),
      "GET /api/v1/soil-observations": () => jsonResponse([]),
    });  // prettier-ignore
    const user = userEvent.setup();
    renderRoute("/soil");
    expect(await screen.findByRole("heading", { name: "pH over time" })).toBeInTheDocument();
    const picker = screen.getByLabelText("Soil measure");
    expect(within(picker).getAllByRole("option").map((o) => o.textContent)).toEqual(["pH", "EC"]); // K has one test only
    await user.selectOptions(picker, "ec_ds_m");
    expect(screen.getByRole("heading", { name: "EC over time" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /1 Apr 2026: EC 2.6 dS\/m/ })).toBeInTheDocument();
  });

  it("edits a stored test with its values pre-filled, and deletes one after confirmation", async () => {
    const obs = {
      id: "so-1", field_id: "fd-1", sampled_on: "2026-10-01", data_origin: "measured", created_at: "2026-10-02T08:00:00Z",
      lab_name: "District Lab", lab_reference: null, depth_from_cm: 0, depth_to_cm: 15, ph: 8.6, ph_method: "water_1_2_5",
      ec_ds_m: 4.5, ec_method: "saturated_paste_ece", organic_matter_pct: null, organic_carbon_pct: null, nitrogen_total_pct: null,
      phosphorus_mg_kg: null, phosphorus_method: "unknown", potassium_mg_kg: null, calcium_mg_kg: null, magnesium_mg_kg: null,
      sulfur_mg_kg: null, zinc_mg_kg: null, iron_mg_kg: null, boron_mg_kg: null, cec_cmol_kg: null, texture: "silt_loam",
      notes: null, units: {}, nutrient_methods: null,
    };  // prettier-ignore
    const latest = { ...obs, crops_considered: [], interpretation: { flags: [], warnings: [], not_evaluated: [], dose_policy: "No doses." } };
    const fetchMock = mockFetch({
      ...signedIn, ...fields,
      "GET /api/v1/fields/fd-1/soil-summary": () => jsonResponse({ field_id: "fd-1", field_name: "North Field", observations: 1, latest, trends: {} }),
      "GET /api/v1/soil-observations": () => jsonResponse([obs]),
      "PATCH /api/v1/soil-observations/so-1": () => jsonResponse(latest),
      "DELETE /api/v1/soil-observations/so-1": () => new Response(null, { status: 204 }),
    });  // prettier-ignore
    const user = userEvent.setup();
    renderRoute("/soil");

    await user.click(await screen.findByRole("button", { name: "Edit soil test of 1 Oct 2026" }));
    const dialog = await screen.findByRole("dialog", { name: "Edit soil test of 1 Oct 2026" });
    const ph = within(dialog).getByLabelText("pH (pH units)", { exact: false });
    expect(ph).toHaveValue(8.6);
    expect(within(dialog).getByLabelText("pH method")).toHaveValue("water_1_2_5");
    await user.clear(ph);
    await user.type(ph, "8.2");
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(callsTo(fetchMock, "PATCH", "/api/v1/soil-observations/so-1")).toHaveLength(1));
    const patch = callsTo(fetchMock, "PATCH", "/api/v1/soil-observations/so-1")[0]!.body as Record<string, unknown>;
    expect(patch).toMatchObject({ ph: "8.2", lab_name: "District Lab", texture: "silt_loam", organic_matter_pct: null });
    expect(patch).not.toHaveProperty("field_id");

    await user.click(screen.getByRole("button", { name: "Delete soil test of 1 Oct 2026" }));
    const confirm = await screen.findByRole("dialog", { name: "Delete the soil test of 1 Oct 2026?" });
    await user.click(within(confirm).getByRole("button", { name: "Delete soil test" }));
    await waitFor(() => expect(callsTo(fetchMock, "DELETE", "/api/v1/soil-observations/so-1")).toHaveLength(1));
  });
});

const run = {
  id: "r-1", message: "Give me a complete condition report", intent: "field_report",
  agents: ["soil", "weather"], status: "partial", farm_id: "f-1", field_id: "fd-1", duration_ms: 42,
  created_at: "2026-11-23T10:00:00Z",
  response: {
    answer: "Soil condition: Latest test 2026-10-15 (measured).", intent: "field_report",
    agents: [{ name: "soil", title: "Soil condition", purpose: "Reads soil tests" }],
    sections: [{ agent: "soil", title: "Soil condition", status: "ok", findings: ["Soil reaction: slightly alkaline (pH 7.9)."], actions: [], missing: [], evidence: [], limitations: [] }],
    report: { title: "Field condition report — North Field", generated_at: "2026-11-23T10:00:00Z", field: { id: "fd-1", name: "North Field", area_ha: 1 },
      farm: { id: "f-1", name: "Green Acres", latitude: 31.52, longitude: 74.36 }, crop: null, risks: [], timestamps: {},
      coverage: { soil: "ok", weather: "unavailable", irrigation: "unavailable", crop_health: "unavailable" }, confidence: "Based on 1 of 4 data sources." },
    suggested_actions: [{ agent: "soil", action: "Ask the lab for: texture.", reason: "Missing." }],
    missing_information: ["crop_doctor_case"], evidence: [], pending_actions: [], limitations: [], llm_used: false, generated_by: "rules",
  },
  steps: [{ position: 0, agent: "farm_operations", tool: "get_field_context", mode: "read", input: {}, status: "ok", summary: "Field 'North Field'.", error_code: null, duration_ms: 3 }],
  actions: [{ id: "a-1", run_id: "r-1", agent: "farm_operations", tool: "set_farm_location", args: {}, description: "Set farm latitude/longitude",
    status: "pending", requested_by: "u", decided_by: null, decided_at: null, executed_by: null, executed_at: null,
    expires_at: "2026-11-24T10:00:00Z", result: null, error_code: null, created_at: "2026-11-23T10:00:00Z" }],
} as unknown as AgentRun;  // prettier-ignore

describe("AI Agents", () => {
  it("runs a report, shows what the agents did, and approves a proposed change", async () => {
    const fetchMock = mockFetch({
      ...signedIn, ...fields,
      "GET /api/v1/agent/runs": () => jsonResponse(page([])),
      "GET /api/v1/agent/actions": () => jsonResponse([]),
      "POST /api/v1/agent/runs": () => jsonResponse(run, 201),
      "GET /api/v1/agent/runs/r-1": () => jsonResponse(run),
      "POST /api/v1/agent/actions/a-1/approve": () => jsonResponse({ ...run.actions[0], status: "executed" }),
      "GET /api/v1/agent/catalogue": () => jsonResponse({ agents: [], tools: [], llm_used: false }),
    });
    const user = userEvent.setup();
    const { container } = renderRoute("/agents");
    await user.type(await screen.findByLabelText("Ask the agents"), "Give me a complete condition report");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Field condition report — North Field")).toBeInTheDocument();
    expect(callsTo(fetchMock, "POST", "/api/v1/agent/runs")[0]!.body).toMatchObject({ field_id: "fd-1" });
    expect(screen.getByText("weather: unavailable")).toBeInTheDocument();
    expect(screen.getByText(/no LLM: rules \+ typed tools/)).toBeInTheDocument();
    expect(screen.getByText("get_field_context")).toBeInTheDocument();
    await expectNoA11yViolations(container);
    await user.click(screen.getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(callsTo(fetchMock, "POST", "/api/v1/agent/actions/a-1/approve")).toHaveLength(1));
  });

  it("shows decided changes with outcome and time, and the tool catalogue with approval needs", async () => {
    const base = run.actions[0]!;
    const decided = [
      { ...base, id: "a-2", status: "executed", decided_at: "2026-11-23T10:05:00Z", executed_at: "2026-11-23T10:05:01Z" },
      { ...base, id: "a-3", status: "rejected", description: "Change sowing date", decided_at: "2026-11-23T11:00:00Z" },
      { ...base, id: "a-4", status: "failed", description: "Set farm location again", error_code: "validation_error" },
    ];
    mockFetch({
      ...signedIn, ...fields,
      "GET /api/v1/agent/runs": () => jsonResponse(page([])),
      "GET /api/v1/agent/actions": ({ url }) =>
        jsonResponse(url.searchParams.get("status") === "pending" ? [] : [base, ...decided]),
      "GET /api/v1/agent/catalogue": () => jsonResponse({
        agents: [{ name: "soil", title: "Soil condition", purpose: "Reads soil tests." }],
        tools: [
          { name: "get_soil_summary", description: "Latest soil test.", mode: "read", permission: "owner", requires_approval: false, agents: ["soil"] },
          { name: "set_farm_location", description: "Propose a farm location.", mode: "write", permission: "owner", requires_approval: true, agents: ["farm_operations"] },
        ],
        llm_used: false,
      }),
    });  // prettier-ignore
    renderRoute("/agents");
    const history = (await screen.findByRole("heading", { name: "Decided changes" })).closest("section, div")!;
    const outcomes = await screen.findByRole("list", { name: "Proposed changes by outcome" });
    expect(outcomes).toHaveTextContent(/pending.*1/); // activity counts every proposal incl. pending
    expect(screen.getAllByText("executed")).toHaveLength(2); // decided-history badge + activity label
    expect(screen.getAllByText("rejected")).toHaveLength(2);
    expect(screen.getByText(/error validation_error/)).toBeInTheDocument();
    expect(within(history as HTMLElement).queryByText("pending")).not.toBeInTheDocument(); // pending lives in approvals
    expect(await screen.findByText(/No language model is used/)).toBeInTheDocument();
    expect(screen.getByText("write · needs approval")).toBeInTheDocument();
    expect(screen.getByText("read only")).toBeInTheDocument();
  });
});
