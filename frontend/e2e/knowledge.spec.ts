import { expect, test, type Page } from "@playwright/test";
import { accessToken, registerViaUi, uniqueEmail } from "./support";

/**
 * Knowledge (RAG) journey. Needs a library with at least one indexed, licence-verified
 * source, so it is meant for E2E_BASE_URL=<running app> (skipped on an empty library).
 * With an LLM configured the answer is generated + validated; without one it is quoted
 * passages. Either way it must carry citations that open in the passage viewer.
 */
const VIEWPORTS = [
  { name: "phone-360", width: 360, height: 800 },
  { name: "phone-390", width: 390, height: 844 },
  { name: "phone-430", width: 430, height: 932 },
  { name: "tablet-768", width: 768, height: 1024 },
  { name: "tablet-1024", width: 1024, height: 768 },
  { name: "desktop-1280", width: 1280, height: 800 },
  { name: "desktop-1440", width: 1440, height: 900 },
  { name: "desktop-1920", width: 1920, height: 1080 },
];

async function overflow(page: Page): Promise<number> {
  return page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
}

test("ask a question, get a cited answer, open the source, and fit every viewport", async ({ page }) => {
  test.setTimeout(240_000);
  await registerViaUi(page, "Rafi Knowledge", uniqueEmail("knowledge"));
  await page.goto("/knowledge");
  await expect(page.getByRole("heading", { level: 1, name: "Agricultural Knowledge" })).toBeVisible();
  const stats = await (await page.request.get("/api/v1/knowledge/stats", {
    headers: { Authorization: `Bearer ${await accessToken(page)}` },
  })).json();
  test.skip(!(stats.searchable_sources > 0), "verified library is empty");

  await page.getByLabel("Question").fill("What are the recommended practices for managing soil salinity?");
  await page.getByRole("button", { name: "Ask" }).click();
  const answer = page.getByRole("article", { name: "Answer" }).first();
  await expect(answer).toBeVisible({ timeout: 90_000 });
  await expect(answer.getByText(/Grounded answer|Quoted passages/)).toBeVisible();
  const sources = answer.getByRole("region", { name: "Sources" });
  await expect(sources.getByRole("listitem").first()).toBeVisible();
  await page.screenshot({ path: "test-results/screens/knowledge-answer-desktop.png", fullPage: true });

  await sources.getByRole("button", { name: "Open source" }).first().click();
  await expect(page.getByText(/Cited passage/)).toBeVisible();
  await page.screenshot({ path: "test-results/screens/knowledge-source-viewer.png" });
  await page.keyboard.press("Escape");

  await page.getByLabel("Follow-up question").fill("ٹماٹر کے پتوں پر پیلے دھبے کیوں آتے ہیں؟");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByRole("article", { name: "Answer" })).toHaveCount(2, { timeout: 90_000 });

  for (const vp of VIEWPORTS) {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.waitForTimeout(150);
    expect(await overflow(page), vp.name).toBeLessThanOrEqual(0);
    await page.screenshot({ path: `test-results/screens/knowledge-${vp.name}.png`, fullPage: true });
  }
  await page.getByRole("tab", { name: "Sources" }).click();
  await expect(page.getByRole("table", { name: "Knowledge sources" })).toBeVisible();
  for (const vp of [VIEWPORTS[0]!, VIEWPORTS[5]!]) {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    expect(await overflow(page), `sources ${vp.name}`).toBeLessThanOrEqual(0);
    await page.screenshot({ path: `test-results/screens/knowledge-sources-${vp.name}.png`, fullPage: true });
  }
});
