import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

// jsdom does not implement object URLs (used for photo previews).
if (!URL.createObjectURL) {
  Object.assign(URL, { createObjectURL: () => "blob:preview", revokeObjectURL: () => undefined });
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
