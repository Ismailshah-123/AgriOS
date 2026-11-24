import { expect, test } from "@playwright/test";
import { addFarmViaUi, registerViaUi, uniqueEmail } from "./support";

test("another user's farm is not reachable by changing the URL or calling the API", async ({ browser }) => {
  const alice = await browser.newContext();
  const alicePage = await alice.newPage();
  await registerViaUi(alicePage, "Alice Farmer", uniqueEmail("alice"));
  await addFarmViaUi(alicePage, "Alice Orchard");
  await alicePage.getByRole("link", { name: /Alice Orchard/ }).click();
  await expect(alicePage).toHaveURL(/\/farms\/[0-9a-f-]{36}$/);
  const farmUrl = new URL(alicePage.url()).pathname;
  const farmId = farmUrl.split("/").at(-1)!;

  const bob = await browser.newContext();
  const bobPage = await bob.newPage();
  await registerViaUi(bobPage, "Bob Farmer", uniqueEmail("bob"));

  // Through the UI: a not-found page, never Alice's data.
  await bobPage.goto(farmUrl);
  await expect(bobPage.getByRole("heading", { name: "Farm not found" })).toBeVisible();
  await expect(bobPage.getByText("Alice Orchard")).toHaveCount(0);

  // Through the API with Bob's own session: 404 for read, update and delete.
  const token = await bobPage.evaluate(async () => {
    const res = await fetch("/api/v1/auth/refresh", { method: "POST", credentials: "include" });
    return ((await res.json()) as { access_token: string }).access_token;
  });
  const headers = { Authorization: `Bearer ${token}` };
  const api = bobPage.request;
  expect((await api.get(`/api/v1/farms/${farmId}`, { headers })).status()).toBe(404);
  expect((await api.patch(`/api/v1/farms/${farmId}`, { headers, data: { name: "Hijack" } })).status()).toBe(404);
  expect((await api.delete(`/api/v1/farms/${farmId}`, { headers })).status()).toBe(404);
  const list = await (await api.get("/api/v1/farms", { headers })).json();
  expect(list.items).toEqual([]);

  // Alice's farm is untouched.
  await alicePage.reload();
  await expect(alicePage.getByRole("heading", { level: 1, name: "Alice Orchard" })).toBeVisible();
  await alice.close();
  await bob.close();
});

test("session tokens: refresh cookie is httpOnly + SameSite=Strict; access token never in web storage", async ({ page, context }) => {
  await registerViaUi(page, "Cara Tokens", uniqueEmail("tokens"));
  const refresh = (await context.cookies()).find((c) => c.name === "agrios_refresh");
  expect(refresh).toBeDefined();
  expect(refresh!.httpOnly).toBe(true);
  expect(refresh!.sameSite).toBe("Strict");
  expect(refresh!.path).toBe("/api/v1/auth");
  const storage = await page.evaluate(() => ({
    local: JSON.stringify(localStorage),
    session: JSON.stringify(sessionStorage),
    cookieVisibleToJs: document.cookie.includes("agrios_refresh"),
  }));
  expect(storage.local).not.toMatch(/eyJ/); // no JWT
  expect(storage.session).not.toMatch(/eyJ/);
  expect(storage.cookieVisibleToJs).toBe(false);
});

test("unauthenticated API calls are rejected", async ({ request }) => {
  for (const path of ["/api/v1/farms", "/api/v1/fields", "/api/v1/crop-cycles", "/api/v1/overview"]) {
    const res = await request.get(path); // relative to baseURL (isolated or external env)
    expect(res.status(), path).toBe(401);
    expect((await res.json()).error.code).toBe("not_authenticated");
  }
});
