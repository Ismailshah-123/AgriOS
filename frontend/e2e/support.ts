import { crc32, deflateSync } from "node:zlib";
import { expect, type Page } from "@playwright/test";

export const PASSWORD = "e2e-long-password-1";

export function uniqueEmail(tag: string): string {
  return `${tag}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
}

/** Register through the real UI and wait for the Overview. */
export async function registerViaUi(page: Page, name: string, email: string): Promise<void> {
  await page.goto("/register");
  await page.getByLabel("Full name").fill(name);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { level: 1, name: `Welcome, ${name.split(" ")[0]}` })).toBeVisible();
}

export async function addFarmViaUi(page: Page, name: string): Promise<void> {
  await page.goto("/farms");
  await page.getByRole("button", { name: "Add farm" }).first().click();
  const dialog = page.getByRole("dialog", { name: "Add a farm" });
  await dialog.getByLabel("Farm name").fill(name);
  await dialog.getByLabel(/Province/).selectOption("punjab");
  await dialog.getByLabel(/District/).fill("Okara");
  await dialog.getByRole("button", { name: "Add farm" }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByRole("heading", { name })).toBeVisible();
}

/** A valid RGB PNG generated in memory (no binary fixtures in the repo). */
export function makePng(width = 320, height = 240, rgb: [number, number, number] = [60, 140, 70]): Buffer {
  const chunk = (tag: string, data: Buffer) => {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length);
    const body = Buffer.concat([Buffer.from(tag, "ascii"), data]);
    const crc = Buffer.alloc(4);
    crc.writeUInt32BE(crc32(body));
    return Buffer.concat([len, body, crc]);
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr.set([8, 2, 0, 0, 0], 8);
  const row = Buffer.concat([Buffer.from([0]), Buffer.from(Array.from({ length: width }, () => rgb).flat())]);
  const raw = Buffer.concat(Array.from({ length: height }, () => row));
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

/** Access token for API calls made by the test itself (refresh cookie in this context). */
export async function accessToken(page: Page): Promise<string> {
  return page.evaluate(async () => {
    const res = await fetch("/api/v1/auth/refresh", { method: "POST", credentials: "include" });
    return ((await res.json()) as { access_token: string }).access_token;
  });
}

/** Farm + field + growing tomato cycle through the real API. */
export async function seedGrowingCrop(page: Page, farmName = "Doctor Farm"): Promise<void> {
  const token = await accessToken(page);
  const headers = { Authorization: `Bearer ${token}` };
  const api = page.request;
  const farm = await (await api.post("/api/v1/farms", { headers, data: { name: farmName } })).json();
  const field = await (await api.post("/api/v1/fields", {
    headers, data: { farm_id: farm.id, name: "Tomato Plot", area: { value: "1", unit: "acre" } },
  })).json();
  const crops = await (await api.get("/api/v1/crops", { headers })).json();
  const tomato = crops.find((c: { code: string }) => c.code === "tomato");
  const res = await api.post("/api/v1/crop-cycles", {
    headers, data: { field_id: field.id, crop_id: tomato.id, status: "active", sowing_date: "2026-10-01" },
  });
  expect(res.status()).toBe(201);
}
