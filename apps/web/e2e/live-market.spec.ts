import { expect, test } from "@playwright/test";

test("reports honest market health from API through the live UI", async ({ page, request }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  const readyResponse = await request.get("/health/ready");
  expect(readyResponse.status()).toBe(200);
  const ready = await readyResponse.json();
  expect(ready).toMatchObject({
    ready: true,
    market_health: {
      status: "DEGRADED",
      execution_ready: false,
    },
  });

  await page.goto("/");
  const snapshotResponsePromise = page.waitForResponse(
    (response) => response.url().endsWith("/v1/shadow/snapshot") && response.request().method() === "GET",
  );
  await page.getByRole("button", { name: "Live research" }).click();
  const snapshotResponse = await snapshotResponsePromise;
  expect(snapshotResponse.status()).toBe(200);

  const snapshot = await snapshotResponse.json();
  expect(snapshot.market_health).toMatchObject({
    status: "DEGRADED",
    execution_ready: false,
    authenticated_multi_venue_feeds: [],
  });
  expect(snapshot.configuration.alpaca.qualification_capable).toBe(false);

  await expect(page.getByText("WS connected", { exact: true })).toBeVisible();
  const marketHealth = page.locator(".market-kpis .kpi").filter({ hasText: "Market health" });
  await expect(marketHealth.getByText("Degraded", { exact: true })).toBeVisible();
  await expect(marketHealth).toContainText("WS connected");

  const liveFeeds = page.locator(".market-kpis .kpi").filter({ hasText: "Live feeds" });
  await expect(liveFeeds).toContainText("0 authenticated · 0 fresh multi-venue feeds");
  const alpaca = page.locator(".provider-health-row").filter({ hasText: "alpaca" });
  await expect(alpaca.getByText("Disabled", { exact: true })).toBeVisible();
  await expect(page.getByText("No matching assets have a live decision yet.", { exact: true })).toBeVisible();

  expect(consoleErrors).toEqual([]);
});
