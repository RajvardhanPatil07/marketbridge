import { defineConfig } from "@playwright/test";

const port = 8013;
const baseURL = `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 2 : 0,
  reporter: "line",
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: `uv run uvicorn marketbridge.api:app --app-dir backend --host 127.0.0.1 --port ${port}`,
    cwd: "../..",
    env: {
      ...process.env,
      ALPACA_API_KEY: "",
      ALPACA_SECRET_KEY: "",
      ALPACA_FEED: "iex",
      HYPERLIQUID_COIN_MAP: "",
      MARKETBRIDGE_ALLOWED_ORIGINS: baseURL,
      MARKETBRIDGE_DISABLE_RESEARCH_FEED: "1",
      MARKETBRIDGE_REQUIRE_LIVE_DATA: "0",
    },
    url: `${baseURL}/health/ready`,
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
