import { expect, test } from "@playwright/test";
import { addFarmViaUi, PASSWORD, registerViaUi, uniqueEmail } from "./support";

test("farmer journey: register, farm, field, crop cycle, overview, sign out and back in", async ({ page }) => {
  const email = uniqueEmail("journey");
  await registerViaUi(page, "Amina Khan", email);

  // New account: onboarding checklist; module status says what is missing, with no numbers invented.
  await expect(page.getByRole("heading", { name: "Get started" })).toBeVisible();
  await expect(page.getByText("No model installed")).toBeVisible();
  await expect(page.getByText("Add a farm with its location to see weather.")).toBeVisible();

  await addFarmViaUi(page, "Green Acres");
  await page.getByRole("link", { name: /Green Acres/ }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Green Acres" })).toBeVisible();

  // Field in acres: stored in hectares, echoed as entered.
  await page.getByRole("button", { name: "Add field" }).first().click();
  const fieldDialog = page.getByRole("dialog", { name: "Add a field" });
  await fieldDialog.getByLabel("Field name").fill("North Field");
  await fieldDialog.getByLabel("Area", { exact: true }).fill("2.5");
  await expect(fieldDialog.getByText("= 1.01 hectares")).toBeVisible();
  await fieldDialog.getByRole("button", { name: "Add field" }).click();
  await expect(fieldDialog).toBeHidden();
  await expect(page.getByText("2.5 acres (1.01 ha)")).toBeVisible();

  // Crop cycle: the server enforces the status/date rules too.
  await page.goto("/crop-cycles");
  await page.getByRole("button", { name: "Start crop cycle" }).first().click();
  const cycleDialog = page.getByRole("dialog", { name: "Start a crop cycle" });
  await cycleDialog.getByLabel("Field").selectOption({ label: "North Field · Green Acres" });
  await cycleDialog.getByLabel("Crop").selectOption({ label: "Tomato" });
  await cycleDialog.getByLabel("Status").selectOption("active");
  await cycleDialog.getByLabel(/Sowing date/).fill("2026-10-01");
  await cycleDialog.getByRole("button", { name: "Start cycle" }).click();
  await expect(cycleDialog).toBeHidden();
  const cycles = page.getByRole("list", { name: "Crop cycles" });
  await expect(cycles.getByText("Tomato")).toBeVisible();
  await expect(cycles.getByText("Growing")).toBeVisible();

  // Overview reflects the real records.
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Overview" }).click();
  await expect(page.getByText("1 farm · 1 field · 1.01 ha recorded")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Get started" })).toBeHidden();
  await expect(page.getByText("Crop cycle started")).toBeVisible();

  // Session survives a reload (httpOnly refresh cookie), then sign out and back in.
  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: "Welcome, Amina" })).toBeVisible();
  await page.getByRole("button", { name: "Amina Khan account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Sign in" })).toBeVisible();
  await page.goto("/farms");
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "My Farms" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Green Acres" })).toBeVisible();
});

test("the remaining planned module is an honest entry page", async ({ page }) => {
  await registerViaUi(page, "Bilal Ahmed", uniqueEmail("planned"));
  for (const [path, title] of [["/reports", "Reports"]] as const) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
    await expect(page.getByRole("main").getByText(/^Planned/)).toBeVisible();
    await expect(page.getByRole("main").getByRole("textbox")).toHaveCount(0);
  }
});
