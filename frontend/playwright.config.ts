import { randomBytes } from "node:crypto";
import { defineConfig, devices } from "@playwright/test";

/*
 * End-to-end tests against the REAL stack: FastAPI + an isolated, freshly reset
 * PostgreSQL database (agrios_e2e_test in the throwaway test cluster) + Vite.
 * Browser: the locally installed Microsoft Edge (channel "msedge"), so no browser
 * download is needed. Prerequisite: PostgreSQL binaries (see backend/scripts/test_db.py).
 */
// E2E_BASE_URL=http://localhost:5180 runs the suite against an ALREADY RUNNING local
// environment (scripts/dev/start.ps1) instead of starting servers on an isolated db.
const EXTERNAL = process.env.E2E_BASE_URL;
const E2E_DB = "postgresql+psycopg://agrios_test@127.0.0.1:54329/agrios_e2e_test";
const API_PORT = 8011;
const WEB_PORT = 5174;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  outputDir: "./test-results",
  use: {
    baseURL: EXTERNAL ?? `http://localhost:${WEB_PORT}`,
    channel: "msedge",
    trace: "retain-on-failure",
  },
  projects: [{ name: "edge", use: { ...devices["Desktop Edge"], channel: "msedge" } }],
  webServer: EXTERNAL ? [] : [
    {
      cwd: "../backend",
      command:
        "uv run python scripts/test_db.py reset agrios_e2e_test && uv run alembic upgrade head && " +
        `uv run uvicorn app.main:app --port ${API_PORT}`,
      url: `http://127.0.0.1:${API_PORT}/api/v1/health`,
      timeout: 120_000,
      reuseExistingServer: false,
      env: {
        APP_ENV: "test",
        DATABASE_URL: E2E_DB,
        JWT_SECRET: randomBytes(48).toString("base64url"),
        ALLOWED_ORIGINS: `http://localhost:${WEB_PORT}`,
        LOG_LEVEL: "WARNING",
        // Real job processing in the API process; throwaway upload/model directories.
        EMBEDDED_WORKER: "true",
        // Every test registers fresh users from 127.0.0.1; the default is 10/hour per IP.
        REGISTER_LIMIT_PER_HOUR: "500",
        STORAGE_PATH: "./var/e2e-uploads",
        MODEL_PATH: "./var/e2e-models",
      },
    },
    {
      command: `npx vite --port ${WEB_PORT} --strictPort`,
      url: `http://localhost:${WEB_PORT}`,
      timeout: 60_000,
      reuseExistingServer: false,
      env: { VITE_API_PROXY_TARGET: `http://127.0.0.1:${API_PORT}` },
    },
  ],
});
