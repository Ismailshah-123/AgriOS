import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { MODULES } from "@/app/modules";
import { healthy, jsonResponse, mockFetch, page, renderRoute, signedIn, signedOut } from "../helpers";

const emptyData = {
  "GET /api/v1/farms": () => jsonResponse(page([])),
  "GET /api/v1/fields": () => jsonResponse(page([])),
  "GET /api/v1/crop-cycles": () => jsonResponse(page([])),
  "GET /api/v1/overview": () =>
    jsonResponse({
      counts: { farms: 0, fields: 0, total_area_ha: 0, cycles_by_status: {} },
      active_cycles: [],
      upcoming: [],
      recent_changes: [],
    }),
};

describe("routing and shell", () => {
  it("sends anonymous visitors to the sign-in page", async () => {
    mockFetch({ ...signedOut });
    const { router } = renderRoute("/farms");
    expect(await screen.findByRole("heading", { level: 1, name: "Sign in" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/login");
  });

  it("opens the Overview at / instead of redirecting to Crop Doctor", async () => {
    mockFetch({ ...signedIn, ...emptyData, ...healthy });
    const { router } = renderRoute("/");
    expect(await screen.findByRole("heading", { level: 1, name: "Welcome, Amina" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/");
  });

  it("lists every module in the main navigation with honest status pills", async () => {
    mockFetch({ ...signedIn, ...emptyData });
    renderRoute("/fields");
    const nav = (await screen.findAllByRole("navigation", { name: "Main" }))[0]!;
    for (const m of MODULES.filter((x) => x.group !== "Account" && !x.roles)) {
      expect(within(nav).getByRole("link", { name: new RegExp(m.label) })).toHaveAttribute("href", m.path);
    }
    // Role-restricted modules (expert review) are hidden from a farmer account.
    expect(within(nav).queryByRole("link", { name: /Expert Review/ })).not.toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: /Fields/ })).toHaveAttribute("aria-current", "page");
    // Soil, weather, irrigation (FAO-56 ETc) and agents work end to end; nutrients is a preview (refuses without a reviewed table); knowledge (cited RAG) is live; reports is planned.
    for (const live of [/Soil Intelligence/, /Weather Intelligence/, /Smart Irrigation/, /AI Agents/, /Agricultural Knowledge/]) {
      expect(within(nav).getByRole("link", { name: live })).not.toHaveTextContent(/Preview|Planned/);
    }
    expect(within(nav).getByRole("link", { name: /Nutrient Management/ })).toHaveTextContent("Preview");
    expect(within(nav).getByRole("link", { name: /Reports/ })).toHaveTextContent("Planned");
    // Crop Doctor's case workflow is live (Phase 3); no status pill.
    expect(within(nav).getByRole("link", { name: /Crop Doctor/ })).not.toHaveTextContent(/Preview|Planned/);
  });

  it("shows an honest planned page with no inputs or fake actions", async () => {
    mockFetch({ ...signedIn });
    renderRoute("/reports");
    expect(await screen.findByRole("heading", { level: 1, name: "Reports" })).toBeInTheDocument();
    const main = screen.getByRole("main");
    expect(within(main).getByText(/Planned/)).toBeInTheDocument();
    expect(within(main).queryAllByRole("textbox")).toHaveLength(0);
    expect(within(main).queryAllByRole("spinbutton")).toHaveLength(0);
    expect(within(main).queryByText(/\d+(\.\d+)?\s?mm/)).not.toBeInTheDocument();
  });

  it("shows a not-found page that links back to the Overview", async () => {
    mockFetch({ ...signedIn });
    renderRoute("/no-such-page");
    expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to Overview" })).toHaveAttribute("href", "/");
  });

  it("opens and closes the mobile navigation drawer", async () => {
    mockFetch({ ...signedIn, ...emptyData });
    const user = userEvent.setup();
    renderRoute("/fields");
    await user.click(await screen.findByRole("button", { name: "Open menu" }));
    const drawer = screen.getByRole("dialog", { name: "Navigation" });
    await user.click(within(drawer).getByRole("button", { name: "Close menu" }));
    expect(screen.queryByRole("dialog", { name: "Navigation" })).not.toBeInTheDocument();
  });

  it("signs out from the account menu", async () => {
    mockFetch({ ...signedIn, ...emptyData, "POST /api/v1/auth/logout": () => new Response(null, { status: 204 }) });
    const user = userEvent.setup();
    const { router } = renderRoute("/fields");
    const account = await screen.findByRole("button", { name: /account menu/ });
    expect(account).toHaveAccessibleName("Amina Khan account menu");
    await user.click(account);
    await user.click(await screen.findByRole("menuitem", { name: "Sign out" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Sign in" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/login");
  });
});
