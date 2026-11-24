import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { CropCycle, Farm, FieldRecord } from "@/services/api/types";
import { callsTo, jsonResponse, mockFetch, page, renderRoute, signedIn } from "../helpers";

const farm = { id: "f-1", name: "Green Acres" } as Farm;
const field = {
  id: "fd-1", farm_id: "f-1", farm_name: "Green Acres", name: "North Field",
  area: { hectares: 1, value: 1, unit: "ha", data_origin: "measured" }, notes: null,
  active_cycle_count: 0,
} as FieldRecord;  // prettier-ignore
const tomato = { id: "c-tom", code: "tomato", name_en: "Tomato", name_ur: null, scientific_name: null };
const cycle: CropCycle = {
  id: "cy-1", field_id: "fd-1", field_name: "North Field", farm_id: "f-1", farm_name: "Green Acres",
  crop: tomato, variety: "Local", season: "rabi", status: "active", sowing_date: "2026-10-01",
  expected_harvest_date: "2027-02-15", harvest_date: null, area_ha: null, notes: null,
  created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-01T00:00:00Z",
};  // prettier-ignore

describe("Fields", () => {
  it("asks for a farm first when there are none", async () => {
    mockFetch({
      ...signedIn,
      "GET /api/v1/farms": () => jsonResponse(page([])),
      "GET /api/v1/fields": () => jsonResponse(page([])),
    });
    renderRoute("/fields");
    expect(await screen.findByRole("heading", { name: "Add a farm first" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to My Farms" })).toHaveAttribute("href", "/farms");
  });

  it("converts area live and only offers exactly defined units", async () => {
    const fetchMock = mockFetch({
      ...signedIn,
      "GET /api/v1/farms": () => jsonResponse(page([farm])),
      "GET /api/v1/fields": () => jsonResponse(page([])),
      "POST /api/v1/fields": () => jsonResponse(field, 201),
    });
    const user = userEvent.setup();
    renderRoute("/fields");
    await user.click((await screen.findAllByRole("button", { name: "Add field" }))[0]!);
    const dialog = await screen.findByRole("dialog", { name: "Add a field" });
    const unit = within(dialog).getByLabelText("Unit");
    expect(within(unit).getAllByRole("option").map((o) => o.textContent)).toEqual(["acres", "hectares"]);
    await user.type(within(dialog).getByLabelText("Area"), "2.5");
    expect(within(dialog).getByText("= 1.01 hectares")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Add field" }));
    expect(await within(dialog).findByText("Choose a farm.")).toBeInTheDocument();
    await user.selectOptions(within(dialog).getByLabelText("Farm"), "f-1");
    await user.type(within(dialog).getByLabelText("Field name"), "North Field");
    await user.click(within(dialog).getByRole("button", { name: "Add field" }));
    await waitFor(() => expect(callsTo(fetchMock, "POST", "/api/v1/fields")).toHaveLength(1));
    expect(callsTo(fetchMock, "POST", "/api/v1/fields")[0]?.body).toEqual({
      farm_id: "f-1", name: "North Field", area: { value: "2.5", unit: "acre" },
      area_origin: "farmer_entered", notes: null,
    });  // prettier-ignore
  });

  it("rejects a non-numeric or over-precise area", async () => {
    mockFetch({
      ...signedIn,
      "GET /api/v1/farms": () => jsonResponse(page([farm])),
      "GET /api/v1/fields": () => jsonResponse(page([])),
    });
    const user = userEvent.setup();
    renderRoute("/fields");
    await user.click((await screen.findAllByRole("button", { name: "Add field" }))[0]!);
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Area"), "1.00001");
    await user.click(within(dialog).getByRole("button", { name: "Add field" }));
    expect(await within(dialog).findByText("Enter a positive number with up to 4 decimals.")).toBeInTheDocument();
  });
});

describe("Crop cycles", () => {
  const base = {
    ...signedIn,
    "GET /api/v1/fields": () => jsonResponse(page([field])),
    "GET /api/v1/crops": () => jsonResponse([tomato]),
  };

  it("lists cycles and filters by status through the API", async () => {
    const fetchMock = mockFetch({ ...base, "GET /api/v1/crop-cycles": () => jsonResponse(page([cycle])) });
    const user = userEvent.setup();
    renderRoute("/crop-cycles");
    const list = await screen.findByRole("list", { name: "Crop cycles" });
    expect(within(list).getByText("Tomato (Local)")).toBeInTheDocument();
    expect(within(list).getByText("Growing")).toBeInTheDocument();
    expect(within(list).getByText("1 Oct 2026")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Harvested" }));
    await waitFor(() =>
      expect(
        callsTo(fetchMock, "GET", "/api/v1/crop-cycles").some((c) => c.url.searchParams.get("status") === "harvested"),
      ).toBe(true),
    );
    expect(screen.getByRole("button", { name: "Harvested" })).toHaveAttribute("aria-pressed", "true");
  });

  it("applies the same date and status rules as the server", async () => {
    const fetchMock = mockFetch({ ...base, "GET /api/v1/crop-cycles": () => jsonResponse(page([])) });
    const user = userEvent.setup();
    renderRoute("/crop-cycles");
    await user.click((await screen.findAllByRole("button", { name: "Start crop cycle" }))[0]!);
    const dialog = await screen.findByRole("dialog", { name: "Start a crop cycle" });
    await user.selectOptions(within(dialog).getByLabelText("Field"), "fd-1");
    await user.selectOptions(within(dialog).getByLabelText("Crop"), "c-tom");
    await user.selectOptions(within(dialog).getByLabelText("Status"), "active");
    await user.click(within(dialog).getByRole("button", { name: "Start cycle" }));
    expect(await within(dialog).findByText("A sowing date is required for this status.")).toBeInTheDocument();
    await user.type(within(dialog).getByLabelText(/Sowing date/), "2026-10-01");
    await user.type(within(dialog).getByLabelText(/Harvest date/), "2026-09-01");
    await user.click(within(dialog).getByRole("button", { name: "Start cycle" }));
    expect(await within(dialog).findByText("Harvest date must be on or after the sowing date.")).toBeInTheDocument();
    expect(callsTo(fetchMock, "POST", "/api/v1/crop-cycles")).toHaveLength(0);
  });

  it("guides the farmer to add a field first", async () => {
    mockFetch({
      ...signedIn,
      "GET /api/v1/fields": () => jsonResponse(page([])),
      "GET /api/v1/crop-cycles": () => jsonResponse(page([])),
    });
    renderRoute("/crop-cycles");
    expect(await screen.findByRole("heading", { name: "Add a field first" })).toBeInTheDocument();
  });
});
