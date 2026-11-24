import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { callsTo, jsonResponse, mockFetch, page, renderRoute, signedOut, testUser } from "../helpers";

const tokens = { access_token: "tok", token_type: "bearer", expires_in: 900, user: testUser };
const overviewData = {
  "GET /api/v1/overview": () =>
    jsonResponse({
      counts: { farms: 0, fields: 0, total_area_ha: 0, cycles_by_status: {} },
      active_cycles: [],
      upcoming: [],
      recent_changes: [],
    }),
  "GET /api/v1/farms": () => jsonResponse(page([])),
};

describe("sign in", () => {
  it("validates before calling the server", async () => {
    const fetchMock = mockFetch({ ...signedOut });
    const user = userEvent.setup();
    renderRoute("/login");
    await user.click(await screen.findByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Enter your email.")).toBeInTheDocument();
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true");
    await user.type(screen.getByLabelText("Email"), "not-an-email");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Enter a valid email address.")).toBeInTheDocument();
    expect(callsTo(fetchMock, "POST", "/api/v1/auth/login")).toHaveLength(0);
  });

  it("shows the server message on wrong credentials", async () => {
    mockFetch({
      ...signedOut,
      "POST /api/v1/auth/login": () =>
        jsonResponse({ error: { code: "invalid_credentials", message: "Email or password is incorrect." } }, 401),
    });
    const user = userEvent.setup();
    renderRoute("/login");
    await user.type(await screen.findByLabelText("Email"), "amina@example.com");
    await user.type(screen.getByLabelText("Password"), "wrong-password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Email or password is incorrect.");
  });

  it("signs in and returns to the page the visitor asked for", async () => {
    const fetchMock = mockFetch({
      ...signedOut,
      ...overviewData,
      "POST /api/v1/auth/login": () => jsonResponse(tokens),
    });
    const user = userEvent.setup();
    const { router } = renderRoute("/farms");
    await user.type(await screen.findByLabelText("Email"), "amina@example.com");
    await user.type(screen.getByLabelText("Password"), "a-long-password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("heading", { level: 1, name: "My Farms" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/farms");
    expect(callsTo(fetchMock, "POST", "/api/v1/auth/login")[0]?.body).toEqual({
      email: "amina@example.com",
      password: "a-long-password",
    });
  });
});

describe("registration", () => {
  it("requires a 10-character password", async () => {
    mockFetch({ ...signedOut });
    const user = userEvent.setup();
    renderRoute("/register");
    await user.type(await screen.findByLabelText("Full name"), "Amina Khan");
    await user.type(screen.getByLabelText("Email"), "amina@example.com");
    await user.type(screen.getByLabelText("Password"), "short");
    await user.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Use at least 10 characters.")).toBeInTheDocument();
  });

  it("puts a taken email error on the email field", async () => {
    mockFetch({
      ...signedOut,
      "POST /api/v1/auth/register": () =>
        jsonResponse(
          { error: { code: "email_taken", message: "An account with this email already exists.", field: "email" } },
          409,
        ),
    });
    const user = userEvent.setup();
    renderRoute("/register");
    await user.type(await screen.findByLabelText("Full name"), "Amina Khan");
    await user.type(screen.getByLabelText("Email"), "amina@example.com");
    await user.type(screen.getByLabelText("Password"), "a-long-password");
    await user.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("An account with this email already exists.")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true");
  });
});
