import { expect, test } from "@playwright/test";
import { addFarmViaUi, registerViaUi, uniqueEmail } from "./support";

// Regression (found 2026-11-23): a long farm name in "Recent changes" widened the
// Overview grid to 548px on a 360px phone. Long, unbroken names must never widen a page.
test("long record names never cause horizontal scrolling on a phone", async ({ page }) => {
  await registerViaUi(page, "Long Names", uniqueEmail("long"));
  const name = "Chak-Number-Two-Hundred-And-Twelve-Extremely-Long-Farm-Name-Without-Spaces";
  await addFarmViaUi(page, name);
  await page.setViewportSize({ width: 360, height: 780 });
  for (const path of ["/", "/farms", "/fields", "/crop-cycles"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    );
    expect(overflow, path).toBeLessThanOrEqual(0);
  }
});
