import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { Farm, FieldRecord } from "@/services/api/types";
import { callsTo, jsonResponse, mockFetch, page, renderRoute, signedIn } from "../helpers";

const farm: Farm = {
  id: "f-1", name: "Green Acres", province: "punjab", district: "Okara", latitude: 30.81,
  longitude: 73.46, location_precision: "0.01_degree", notes: null, field_count: 2,
  total_area_ha: 3.0117, created_at: "2026-11-20T00:00:00Z", updated_at: "2026-11-20T00:00:00Z",
};  // prettier-ignore

const field: FieldRecord = {
  id: "fd-1", farm_id: "f-1", farm_name: "Green Acres", name: "North Field",
  area: { hectares: 1.0117, value: 2.5, unit: "acre", data_origin: "farmer_entered" },
  notes: null, active_cycle_count: 1, created_at: "2026-11-20T00:00:00Z",
  updated_at: "2026-11-20T00:00:00Z",
};  // prettier-ignore

describe("My Farms", () => {
  it("shows a loading state, then a helpful empty state", async () => {
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    mockFetch({ ...signedIn, "GET /api/v1/farms": async () => (await gate, jsonResponse(page([]))) });
    renderRoute("/farms");
    expect(await screen.findByRole("status", { name: "Loading farms" })).toBeInTheDocument();
    release();
    expect(await screen.findByRole("heading", { name: "Add your first farm" })).toBeInTheDocument();
  });

  it("shows an error state with a working retry", async () => {
    let fail = true;
    mockFetch({
      ...signedIn,
      "GET /api/v1/farms": () =>
        fail
          ? jsonResponse({ error: { code: "database_unavailable", message: "The service is temporarily unavailable. Try again shortly." } }, 503)
          : jsonResponse(page([farm])),
    });
    const user = userEvent.setup();
    renderRoute("/farms");
    expect(await screen.findByText("The service is temporarily unavailable. Try again shortly.")).toBeInTheDocument();
    fail = false;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: "Green Acres" })).toBeInTheDocument();
  });

  it("lists farms with real field counts and area", async () => {
    mockFetch({ ...signedIn, "GET /api/v1/farms": () => jsonResponse(page([farm])) });
    renderRoute("/farms");
    const card = (await screen.findByRole("heading", { name: "Green Acres" })).closest("a")!;
    expect(card).toHaveAttribute("href", "/farms/f-1");
    expect(within(card).getByText("Okara, Punjab")).toBeInTheDocument();
    expect(within(card).getByText("3.01 ha")).toBeInTheDocument();
    expect(within(card).getByText("2")).toBeInTheDocument();
  });

  it("validates and creates a farm, then refreshes the list", async () => {
    let farms: Farm[] = [];
    const fetchMock = mockFetch({
      ...signedIn,
      "GET /api/v1/farms": () => jsonResponse(page(farms)),
      "POST /api/v1/farms": ({ body }) => {
        farms = [{ ...farm, ...(body as object), field_count: 0, total_area_ha: 0 }];
        return jsonResponse(farms[0], 201);
      },
    });
    const user = userEvent.setup();
    renderRoute("/farms");
    await user.click((await screen.findAllByRole("button", { name: "Add farm" }))[0]!);
    const dialog = await screen.findByRole("dialog", { name: "Add a farm" });
    await user.click(within(dialog).getByRole("button", { name: "Add farm" }));
    expect(await within(dialog).findByText("Enter a farm name.")).toBeInTheDocument();
    await user.type(within(dialog).getByLabelText("Farm name"), "Green Acres");
    await user.type(within(dialog).getByLabelText(/Latitude/), "30.8");
    await user.click(within(dialog).getByRole("button", { name: "Add farm" }));
    expect(await within(dialog).findByText("Enter both latitude and longitude, or neither.")).toBeInTheDocument();
    await user.type(within(dialog).getByLabelText(/Longitude/), "73.4");
    await user.selectOptions(within(dialog).getByLabelText(/Province/), "punjab");
    await user.click(within(dialog).getByRole("button", { name: "Add farm" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(callsTo(fetchMock, "POST", "/api/v1/farms")[0]?.body).toEqual({
      name: "Green Acres", province: "punjab", district: null, latitude: "30.8",
      longitude: "73.4", notes: null,
    });  // prettier-ignore
    expect(await screen.findByRole("heading", { name: "Green Acres" })).toBeInTheDocument();
  });

  it("farm detail shows its fields with the entered unit and origin", async () => {
    mockFetch({
      ...signedIn,
      "GET /api/v1/farms/f-1": () => jsonResponse(farm),
      "GET /api/v1/fields": ({ url }) => {
        expect(url.searchParams.get("farm_id")).toBe("f-1");
        return jsonResponse(page([field]));
      },
    });
    renderRoute("/farms/f-1");
    expect(await screen.findByRole("heading", { level: 1, name: "Green Acres" })).toBeInTheDocument();
    expect(await screen.findByText("2.5 acres (1.01 ha)")).toBeInTheDocument();
    expect(screen.getByText("Farmer entered")).toBeInTheDocument();
    expect(screen.getByText("30.81, 73.46 (approximate)")).toBeInTheDocument();
  });

  it("shows a not-found state for a farm that is not yours", async () => {
    mockFetch({
      ...signedIn,
      "GET /api/v1/farms/other": () => jsonResponse({ error: { code: "not_found", message: "Farm not found." } }, 404),
      "GET /api/v1/fields": () => jsonResponse(page([])),
    });
    renderRoute("/farms/other");
    expect(await screen.findByRole("heading", { name: "Farm not found" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
  });

  it("explains why a farm with fields cannot be deleted", async () => {
    mockFetch({
      ...signedIn,
      "GET /api/v1/farms/f-1": () => jsonResponse(farm),
      "GET /api/v1/fields": () => jsonResponse(page([field])),
      "DELETE /api/v1/farms/f-1": () =>
        jsonResponse({ error: { code: "farm_not_empty", message: "Remove this farm's fields before deleting it." } }, 409),
    });
    const user = userEvent.setup();
    renderRoute("/farms/f-1");
    await user.click(await screen.findByRole("button", { name: "Delete farm" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Delete farm" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Remove this farm's fields before deleting it.");
  });
});
