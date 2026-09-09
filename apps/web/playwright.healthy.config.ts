import { defineConfig } from "@playwright/test";

const port = 8014;
const baseURL = `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: "./e2e-healthy",
  fullyParallel: false,
  workers: 1,
  reporter: "line",
  use: { baseURL, trace: "retain-on-failure", screenshot: "only-on-failure" },
  webServer: {
    command: `uv run python scripts/run_healthy_e2e_server.py --port ${port}`,
    cwd: "../..",
    env: {
      ...process.env,
      ALPACA_API_KEY: "",
      ALPACA_SECRET_KEY: "",
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
