import { expect, test } from "@playwright/test";
import { accessToken, makePng, registerViaUi, seedGrowingCrop, uniqueEmail } from "./support";

/** Overnight-sprint pages on the real stack (isolated e2e database, embedded worker). */

test("economics: costs and a sale reconcile to the rupee in the browser", async ({ page }) => {
  await registerViaUi(page, "Econ Farmer", uniqueEmail("econ"));
  await seedGrowingCrop(page, "Econ Farm");
  await page.goto("/economics");
  await page.getByRole("button", { name: "Add expense" }).click();
  let dialog = page.getByRole("dialog", { name: "Add an expense" });
  await dialog.getByLabel("Category").selectOption("labour");
  await dialog.getByLabel("Amount (PKR)").fill("1500.50");
  await dialog.getByRole("button", { name: "Save expense" }).click();
  await expect(dialog).toBeHidden();
  await page.getByRole("button", { name: "Add harvest / sale" }).click();
  dialog = page.getByRole("dialog", { name: "Add a harvest or sale" });
  await dialog.getByLabel("Quantity (kg)").fill("100");
  await dialog.getByLabel(/Sale price/).fill("40");
  await dialog.getByRole("button", { name: "Save harvest" }).click();
  await expect(dialog).toBeHidden();
  const summary = page.getByRole("region", { name: "Economics summary" });
  await expect(summary.getByText("PKR 1,500.50")).toBeVisible();
  await expect(summary.getByText("PKR 4,000.00")).toBeVisible(); // 100 kg x 40
  await expect(summary.getByText("PKR 2,499.50")).toBeVisible(); // profit
  await expect(summary.getByText("PKR 15.01/kg")).toBeVisible(); // 1500.50 / 100 = 15.005 -> 15.01
});

test("soil: add, edit and delete a test", async ({ page }) => {
  await registerViaUi(page, "Soil Farmer", uniqueEmail("soil"));
  await seedGrowingCrop(page, "Soil Farm");
  await page.goto("/soil");
  await page.getByRole("button", { name: "Add soil test" }).click();
  const add = page.getByRole("dialog", { name: "Add a soil test" });
  await add.getByLabel("Sample date").fill("2026-10-15");
  await add.getByLabel("Origin").selectOption("farmer_entered");
  await add.getByLabel("pH (pH units)").fill("8.1");
  await add.getByRole("button", { name: "Save soil test" }).click();
  await expect(add).toBeHidden();
  await page.getByRole("button", { name: "Edit soil test of 15 Oct 2026" }).click();
  const edit = page.getByRole("dialog", { name: "Edit soil test of 15 Oct 2026" });
  await expect(edit.getByLabel("pH (pH units)")).toHaveValue("8.1");
  await edit.getByLabel("pH (pH units)").fill("7.6");
  await edit.getByRole("button", { name: "Save changes" }).click();
  await expect(edit).toBeHidden();
  await expect(page.getByRole("cell", { name: "7.6" })).toBeVisible();
  await page.getByRole("button", { name: "Delete soil test of 15 Oct 2026" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Delete soil test" }).click();
  await expect(page.getByRole("heading", { name: "No soil test for this field yet" })).toBeVisible();
});

test("offline: a case is kept in IndexedDB and uploads exactly once when back online", async ({ page, context }) => {
  await registerViaUi(page, "Offline Farmer", uniqueEmail("offline"));
  await seedGrowingCrop(page, "Offline Farm");
  await page.goto("/crop-doctor/new");
  await page.getByLabel("Farm").selectOption({ label: "Offline Farm" });
  await page.getByLabel("Field").selectOption({ label: "Tomato Plot" });
  await page.getByLabel("Growing crop").selectOption({ index: 1 });
  await page.getByLabel("Choose photos").setInputFiles([{ name: "leaf.png", mimeType: "image/png", buffer: makePng() }]);
  await context.setOffline(true);
  await page.getByRole("button", { name: "Submit assessment" }).click();
  await expect(page.getByText(/Saved on this device. It will upload automatically/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Saved on this device" })).toBeVisible();
  await expect(page.getByText(/They upload when you are online/)).toBeVisible(); // IndexedDB available (not memory)
  const stored = await page.evaluate(() => new Promise<number>((resolve) => {
    const req = indexedDB.open("agrios-offline");
    req.onsuccess = () => {
      const r = req.result.transaction("case_drafts").objectStore("case_drafts").count();
      r.onsuccess = () => resolve(r.result);
    };
  }));
  expect(stored).toBe(1);
  await context.setOffline(false); // fires "online": automatic upload
  await expect(page.getByText("1 case uploaded.")).toBeVisible({ timeout: 15_000 });
  const token = await accessToken(page);
  const cases = await (await page.request.get("/api/v1/cases", { headers: { Authorization: `Bearer ${token}` } })).json();
  expect(cases.items).toHaveLength(1); // no duplicate
});

test("knowledge and fertilizer refuse honestly when no verified source exists", async ({ page }) => {
  await registerViaUi(page, "Refusal Farmer", uniqueEmail("refuse"));
  await seedGrowingCrop(page, "Refusal Farm");
  await page.goto("/knowledge");
  await page.getByLabel("Question").fill("tomato irrigation interval");
  await page.getByRole("button", { name: "Ask" }).click();
  // RAG v2: the refusal is the answer's status line (no passages, no language model used).
  const answer = page.getByRole("article", { name: "Answer" }).first();
  await expect(answer.getByRole("status")).toHaveText(/^No verified guidance found\./);
  await expect(answer.getByText(/0 passages .* no language model used/)).toBeVisible();
  await page.goto("/nutrients");
  await expect(page.getByRole("heading", { name: "No verified fertilizer guidance" })).toBeVisible();
  await expect(page.getByText(/kg\/(ha|acre)/)).toHaveCount(0);
});
