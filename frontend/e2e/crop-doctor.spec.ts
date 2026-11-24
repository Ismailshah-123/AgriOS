import { expect, test, type Page } from "@playwright/test";
import { createRequire } from "node:module";
import { accessToken, makePng, registerViaUi, seedGrowingCrop, uniqueEmail } from "./support";

const require = createRequire(import.meta.url);
const AXE_PATH = require.resolve("axe-core/axe.min.js");

async function startAssessment(page: Page, files: { name: string; mimeType: string; buffer: Buffer }[]) {
  await page.goto("/crop-doctor/new");
  await page.getByLabel("Farm").selectOption({ label: "Doctor Farm" });
  await page.getByLabel("Field").selectOption({ label: "Tomato Plot" });
  await page.getByLabel("Growing crop").selectOption({ index: 1 });
  await page.getByLabel("Choose photos").setInputFiles(files);
}

test("farmer journey: new assessment, real worker status, follow-up, history", async ({ page }) => {
  await registerViaUi(page, "Hina Doctor", uniqueEmail("doctor"));
  await seedGrowingCrop(page);

  await page.goto("/crop-doctor");
  await expect(page.getByRole("heading", { name: "No assessments yet" })).toBeVisible();
  await expect(page.getByText("No model installed")).toBeVisible();

  await startAssessment(page, [
    { name: "leaf1.png", mimeType: "image/png", buffer: makePng() },
    { name: "leaf2.png", mimeType: "image/png", buffer: makePng(400, 300, [120, 90, 40]) },
  ]);
  await expect(page.getByRole("img", { name: /Selected photo/ })).toHaveCount(2);
  await page.getByText("Spots", { exact: true }).click();
  await page.getByLabel(/Notes/).fill("Brown spots on lower leaves");
  await page.getByRole("button", { name: "Submit assessment" }).click();

  await expect(page).toHaveURL(/\/crop-doctor\/cases\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("heading", { level: 1, name: "Case CD-000001" })).toBeVisible();
  // Stored photos are served through signed links and actually decode in the browser.
  const thumbs = page.getByRole("button", { name: /Open photo \d full size/ });
  await expect(thumbs).toHaveCount(2);
  await expect.poll(() => thumbs.first().locator("img").evaluate((i: HTMLImageElement) => i.naturalWidth)).toBeGreaterThan(0);
  // The embedded worker processes the job: no model installed -> honest status, no diagnosis.
  // (The same message also appears in the timeline, so assert on the status region.)
  await expect(page.getByRole("status").filter({ hasText: /No validated analysis model is installed yet/ }))
    .toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Most likely")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Request analysis again" })).toBeVisible();

  await page.getByRole("button", { name: "Add follow-up" }).click();
  const dialog = page.getByRole("dialog", { name: "Add a follow-up" });
  await dialog.getByLabel(/Notes/).fill("Spreading to upper leaves");
  await dialog.getByLabel("Choose photos").setInputFiles([{ name: "later.png", mimeType: "image/png", buffer: makePng() }]);
  await dialog.getByRole("button", { name: "Add follow-up" }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByRole("heading", { name: "Follow-up" })).toBeVisible();
  await expect(page.getByText("Spreading to upper leaves")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Initial report" })).toBeVisible();

  await page.goto("/crop-doctor/cases");
  await page.getByLabel("Search").fill("CD-000001");
  await expect(page.getByRole("link", { name: /CD-000001/ })).toBeVisible();
  await page.goto("/crop-doctor");
  await expect(page.getByRole("region", { name: "Case summary" }).getByText("1").first()).toBeVisible();
});

test("a disguised non-image is rejected by the server with a clear message", async ({ page }) => {
  await registerViaUi(page, "Imran Upload", uniqueEmail("evil"));
  await seedGrowingCrop(page);
  await startAssessment(page, [
    { name: "photo.jpg", mimeType: "image/jpeg", buffer: Buffer.from("<html><script>alert(1)</script></html>") },
  ]);
  await page.getByRole("button", { name: "Submit assessment" }).click();
  await expect(page.getByText("Photo 1: This file could not be read as a photo.")).toBeVisible();
  await expect(page).toHaveURL(/\/crop-doctor\/new$/);
});

test("another user cannot open a case, its analysis, or its photos", async ({ browser }) => {
  const alice = await browser.newContext();
  const a = await alice.newPage();
  await registerViaUi(a, "Alice Grower", uniqueEmail("alice-cd"));
  await seedGrowingCrop(a);
  await startAssessment(a, [{ name: "a.png", mimeType: "image/png", buffer: makePng() }]);
  await a.getByRole("button", { name: "Submit assessment" }).click();
  await expect(a).toHaveURL(/\/crop-doctor\/cases\//);
  const caseUrl = new URL(a.url()).pathname;
  const caseId = caseUrl.split("/").at(-1)!;
  const imgSrc = await a.getByRole("button", { name: "Open photo 1 full size" }).locator("img").getAttribute("src");

  const bob = await browser.newContext();
  const b = await bob.newPage();
  await registerViaUi(b, "Bob Grower", uniqueEmail("bob-cd"));
  await b.goto(caseUrl);
  await expect(b.getByRole("heading", { name: "Case not found" })).toBeVisible();
  const headers = { Authorization: `Bearer ${await accessToken(b)}` };
  for (const path of [`/api/v1/cases/${caseId}`, `/api/v1/cases/${caseId}/analysis`]) {
    expect((await b.request.get(path, { headers })).status(), path).toBe(404);
  }
  expect((await b.request.post(`/api/v1/cases/${caseId}/analysis/retry`, { headers })).status()).toBe(404);
  // Image links only work with a valid signature; tampering gives the same 404.
  const tampered = imgSrc!.replace(/sig=[0-9a-f]+/, `sig=${"0".repeat(64)}`);
  expect((await b.request.get(tampered)).status()).toBe(404);
  expect((await b.request.get(imgSrc!.split("?")[0]!)).status()).toBe(422);
  await alice.close();
  await bob.close();
});

test("Crop Doctor screens fit 360/768/1280 and pass axe including contrast", async ({ page }) => {
  await registerViaUi(page, "Rida Layout", uniqueEmail("cd-layout"));
  await seedGrowingCrop(page);
  await startAssessment(page, [{ name: "a.png", mimeType: "image/png", buffer: makePng() }]);
  await page.getByRole("button", { name: "Submit assessment" }).click();
  await expect(page).toHaveURL(/\/crop-doctor\/cases\//);
  const detail = new URL(page.url()).pathname;
  for (const width of [360, 768, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of ["/crop-doctor", "/crop-doctor/new", "/crop-doctor/cases", detail]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow, `${width} ${path}`).toBeLessThanOrEqual(0);
      const name = path === detail ? "case" : path.split("/").at(-1);
      await page.screenshot({ path: `test-results/screens/cd-${width}-${name}.png`, fullPage: true });
      if (width === 1280) {
        await page.addScriptTag({ path: AXE_PATH });
        const violations = await page.evaluate(async () => {
          type R = { violations: { id: string; nodes: { html: string }[] }[] };
          const axe = (window as unknown as { axe: { run: (d: Document) => Promise<R> } }).axe;
          const r = await axe.run(document);
          return r.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.html.slice(0, 120)).join(" | ")}`);
        });
        expect(violations, path).toEqual([]);
      }
    }
  }
});
