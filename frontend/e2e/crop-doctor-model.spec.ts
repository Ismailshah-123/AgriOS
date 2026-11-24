import { readFileSync } from "node:fs";
import { basename } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { accessToken, makePng, registerViaUi, seedGrowingCrop, uniqueEmail } from "./support";

/*
 * Crop Doctor with the REAL registered model, against a running app:
 *   E2E_BASE_URL=http://localhost:5173 E2E_TOMATO_IMAGE=<genuine tomato leaf photo> npx playwright test crop-doctor-model
 * Skipped unless both are set and the app reports an active, ready model. Asserts only what
 * the model genuinely returned (no expected class is hard-coded): a diagnosis is shown only for
 * "accepted"; otherwise the honest unsure/out-of-scope text. Also checks persistence (reload),
 * GPS/EXIF removal from the stored photo, the unsupported-crop path and a not-a-leaf image.
 */
const IMAGE = process.env.E2E_TOMATO_IMAGE;
test.skip(!process.env.E2E_BASE_URL || !IMAGE, "needs E2E_BASE_URL (running app) and E2E_TOMATO_IMAGE");

async function api(page: Page) {
  const headers = { Authorization: `Bearer ${await accessToken(page)}` };
  return { headers, req: page.request };
}

async function submit(page: Page, field: string, file: { name: string; mimeType: string; buffer: Buffer }) {
  await page.goto("/crop-doctor/new");
  await page.getByLabel("Farm").selectOption({ label: "Doctor Farm" });
  await page.getByLabel("Field").selectOption({ label: field });
  await page.getByLabel("Growing crop").selectOption({ index: 1 });
  await page.getByLabel("Choose photos").setInputFiles([file]);
  await page.getByRole("button", { name: "Submit assessment" }).click();
  await expect(page).toHaveURL(/\/crop-doctor\/cases\/[0-9a-f-]{36}$/);
  return page.url().split("/").pop() as string;
}

test("real model: tomato photo -> stored without GPS -> calibrated result that persists", async ({ page }) => {
  test.setTimeout(120_000);
  await registerViaUi(page, "Model Check (test data)", uniqueEmail("model"));
  const { headers, req } = await api(page);
  const avail = await (await req.get("/api/v1/models/availability", { headers })).json();
  test.skip(avail.status !== "ready", `no ready model (status ${avail.status})`);
  await seedGrowingCrop(page);

  const caseId = await submit(page, "Tomato Plot", {
    name: basename(IMAGE!), mimeType: "image/jpeg", buffer: readFileSync(IMAGE!),
  });
  await expect(page.getByText(/Analysis complete|Most likely|The model is not sure|does not look like the tomato leaves/).first())
    .toBeVisible({ timeout: 60_000 });

  const detail = await (await req.get(`/api/v1/cases/${caseId}`, { headers })).json();
  const r = detail.analysis.result;
  expect(detail.analysis.inference_status).toBe("completed");
  if (r.decision === "accepted") {
    await expect(page.getByText("Most likely")).toBeVisible();
    await expect(page.getByText(/Confidence for this photo:/)).toBeVisible();
  } else {
    await expect(page.getByText("Most likely")).toHaveCount(0);
  }
  // Heatmap: shown only if this model version provides one; otherwise said so plainly.
  if (r.explanation_available) {
    await expect(page.getByRole("heading", { name: /Where the model looked/ })).toBeVisible();
  } else if (r.decision !== "out_of_scope") {
    await expect(page.getByText(/No heatmap for this result/)).toBeVisible();
  }
  await page.screenshot({ path: "test-results/screens/crop-doctor-real-model.png", fullPage: true });
  test.info().annotations.push({ type: "result", description: JSON.stringify({
    decision: r.decision, predicted_class: r.predicted_class, confidence: r.calibrated_confidence,
    shortlist: r.shortlist, model: `${r.model_name} ${r.model_version}`, explanation: r.explanation_available,
  }) });

  // Persistence: a fresh page load shows the same stored result.
  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: /Case CD-/ })).toBeVisible();
  const again = await (await req.get(`/api/v1/cases/${caseId}`, { headers })).json();
  expect(again.analysis.result).toEqual(r);

  // Stored photo: re-encoded server-side, no EXIF block (GPS removed).
  const src = await page.getByRole("button", { name: /Open photo 1 full size/ }).locator("img").getAttribute("src");
  const bytes = await (await req.get(src!)).body();
  expect(bytes.subarray(0, 4).toString("ascii")).toBe("RIFF"); // WebP container
  expect(bytes.includes(Buffer.from("Exif"))).toBe(false);
  expect(bytes.includes(Buffer.from("GPS"))).toBe(false);
});

test("real model: unsupported crop and a not-a-leaf photo get no diagnosis", async ({ page }) => {
  test.setTimeout(120_000);
  await registerViaUi(page, "Model Limits (test data)", uniqueEmail("limits"));
  const { headers, req } = await api(page);
  const avail = await (await req.get("/api/v1/models/availability", { headers })).json();
  test.skip(avail.status !== "ready", `no ready model (status ${avail.status})`);
  await seedGrowingCrop(page);
  const farm = (await (await req.get("/api/v1/farms", { headers })).json()).items[0];
  const field = await (await req.post("/api/v1/fields", {
    headers, data: { farm_id: farm.id, name: "Wheat Plot", area: { value: "1", unit: "acre" } },
  })).json();
  const crops = await (await req.get("/api/v1/crops", { headers })).json();
  const wheat = crops.find((c: { code: string }) => c.code === "wheat");
  expect((await req.post("/api/v1/crop-cycles", {
    headers, data: { field_id: field.id, crop_id: wheat.id, status: "active", sowing_date: "2026-11-01" },
  })).status()).toBe(201);

  await submit(page, "Wheat Plot", { name: "wheat.jpg", mimeType: "image/jpeg", buffer: readFileSync(IMAGE!) });
  await expect(page.getByRole("status").filter({ hasText: /does not support this crop/ })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("Most likely")).toHaveCount(0);

  await submit(page, "Tomato Plot", { name: "flat.png", mimeType: "image/png", buffer: makePng(400, 300, [128, 128, 128]) });
  await expect(page.getByText(/The model is not sure|does not look like the tomato leaves/).first()).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("Most likely")).toHaveCount(0);
});
