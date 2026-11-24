import { createRequire } from "node:module";
import { expect, test, type Page } from "@playwright/test";
import { accessToken, addFarmViaUi, registerViaUi, seedGrowingCrop, uniqueEmail } from "./support";

const require = createRequire(import.meta.url);
const AXE_PATH = require.resolve("axe-core/axe.min.js");

const VIEWPORTS = [
  { name: "phone", width: 360, height: 780 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "desktop", width: 1280, height: 860 },
];
const PAGES = ["/", "/farms", "/fields", "/crop-cycles", "/crop-doctor", "/soil", "/settings"];

async function horizontalOverflow(page: Page): Promise<number> {
  return page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
}

test.describe.configure({ mode: "serial" });

test("all routes fit 8 phone, tablet and desktop viewports without horizontal scrolling", async ({ page }) => {
  test.setTimeout(300_000);
  await registerViaUi(page, "Dina Layout", uniqueEmail("layout"));
  await addFarmViaUi(page, "Layout Farm With A Fairly Long Name For Wrapping");
  await seedGrowingCrop(page, "Second Layout Farm");
  for (const vp of VIEWPORTS) {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    for (const path of PAGES) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      expect(await horizontalOverflow(page), `${vp.name} ${path}`).toBeLessThanOrEqual(0);
      const safe = path === "/" ? "overview" : path.slice(1);
      await page.screenshot({ path: `test-results/screens/${vp.name}-${safe}.png`, fullPage: true });
    }
    // Phones/tablets use the bottom bar; desktop uses the sidebar.
    const quick = page.getByRole("navigation", { name: "Quick" });
    if (vp.width < 1024) await expect(quick).toBeVisible();
    else await expect(quick).toBeHidden();
  }
});

test("real-browser accessibility scan, including colour contrast", async ({ page }) => {
  await registerViaUi(page, "Eli Access", uniqueEmail("axe"));
  await addFarmViaUi(page, "Contrast Farm");
  for (const path of ["/", "/farms", "/crop-cycles", "/crop-doctor", "/soil", "/irrigation", "/nutrients", "/economics", "/agents", "/knowledge", "/settings"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.addScriptTag({ path: AXE_PATH });
    const violations = await page.evaluate(async () => {
      type Node = { html: string };
      type Result = { violations: { id: string; nodes: Node[] }[] };
      const axe = (window as unknown as { axe: { run: (c: Document) => Promise<Result> } }).axe;
      const result = await axe.run(document);
      // Include the offending markup so a failure says exactly what to fix.
      return result.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.html.slice(0, 160)).join(" | ")}`);
    });
    expect(violations, path).toEqual([]);
  }
});

test("Urdu (RTL) shell fits a 360 px phone and mirrors navigation", async ({ page }) => {
  await registerViaUi(page, "Rida Urdu", uniqueEmail("rtl"));
  const token = await accessToken(page);
  const res = await page.request.patch("/api/v1/users/me", {
    headers: { Authorization: `Bearer ${token}` }, data: { locale: "ur" },
  });
  expect(res.status()).toBe(200);
  await page.setViewportSize({ width: 360, height: 800 });
  for (const path of ["/", "/crop-doctor", "/economics"]) {
    await page.goto(path);
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    expect(await horizontalOverflow(page), `rtl ${path}`).toBeLessThanOrEqual(0);
    await page.screenshot({ path: `test-results/screens/rtl-360${path === "/" ? "-overview" : path.replace(/\//g, "-")}.png`, fullPage: true });
  }
  await expect(page.getByRole("navigation", { name: "Quick" }).getByText("فصل ڈاکٹر").or(page.getByRole("navigation", { name: "Quick" }).getByText("ڈاکٹر"))).toBeVisible();
});