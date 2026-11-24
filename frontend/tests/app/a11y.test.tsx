import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it } from "vitest";
import {
  expectNoA11yViolations,
  healthy,
  jsonResponse,
  mockFetch,
  page,
  renderRoute,
  signedIn,
  signedOut,
} from "../helpers";

/** axe-core WCAG checks on representative screens (contrast checked separately). */
describe("accessibility (axe-core)", () => {
  it("sign-in page, including validation errors", async () => {
    mockFetch({ ...signedOut });
    const user = userEvent.setup();
    const { container } = renderRoute("/login");
    await user.click(await screen.findByRole("button", { name: "Sign in" }));
    await screen.findByText("Enter your email.");
    await expectNoA11yViolations(container);
  });

  it("registration page", async () => {
    mockFetch({ ...signedOut });
    const { container } = renderRoute("/register");
    await screen.findByRole("heading", { name: "Create your account" });
    await expectNoA11yViolations(container);
  });

  it("farms empty state inside the app shell", async () => {
    mockFetch({ ...signedIn, "GET /api/v1/farms": () => jsonResponse(page([])) });
    const { container } = renderRoute("/farms");
    await screen.findByRole("heading", { name: "Add your first farm" });
    await expectNoA11yViolations(container);
  });

  it("add-farm dialog", async () => {
    mockFetch({ ...signedIn, "GET /api/v1/farms": () => jsonResponse(page([])) });
    const user = userEvent.setup();
    renderRoute("/farms");
    await user.click((await screen.findAllByRole("button", { name: "Add farm" }))[0]!);
    await screen.findByRole("dialog", { name: "Add a farm" });
    await expectNoA11yViolations(document.body);
  });

  it("planned module page", async () => {
    mockFetch({ ...signedIn });
    const { container } = renderRoute("/economics");
    await screen.findByRole("heading", { level: 1, name: "Farm Economics" });
    await expectNoA11yViolations(container);
  });

  it("Crop Doctor overview", async () => {
    mockFetch({
      ...signedIn,
      ...healthy,
      "GET /api/v1/cases/summary": () =>
        jsonResponse({ total: 0, awaiting_analysis: 0, needs_follow_up: 0, by_inference_status: {}, model_availability: "not_registered" }),
      "GET /api/v1/cases": () => jsonResponse(page([])),
    });
    const { container } = renderRoute("/crop-doctor");
    await screen.findByRole("heading", { name: "No assessments yet" });
    await expectNoA11yViolations(container);
  });
});
