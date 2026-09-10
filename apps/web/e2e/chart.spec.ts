import { expect, test } from "@playwright/test";

const bars = Array.from({ length: 80 }, (_, index) => {
  const timestamp = new Date(Date.UTC(2026, 8, 1, 14, index * 5));
  const open = 170 + index * 0.2;
  return { timestamp: timestamp.toISOString(), open, high: open + 1, low: open - 0.7, close: open + 0.35, volume: 1000 + index * 10, vwap: open + 0.2, trade_count: 20 + index };
});

test.beforeEach(async ({ page }) => {
  await page.route("**/v1/market/bars/*", async (route) => {
    const url = new URL(route.request().url());
    await route.fulfill({ json: { symbol: "NVDA", provider: "alpaca", feed: "iex", resolution: url.searchParams.get("resolution") ?? "5Min", adjustment: "raw", currency: "USD", timezone: "America/New_York", start: bars[0].timestamp, end: bars.at(-1)!.timestamp, session: "regular", status: "DELAYED", is_delayed: true, entitlement: "LIMITED_SINGLE_EXCHANGE", cached: false, pages: 1, bars, has_more_history: url.searchParams.get("range") === "MAX", next_end: bars[0].timestamp, data_role: "DISPLAY_ONLY_NOT_ORACLE_EVIDENCE" } });
  });
});

test("asset chart renders ranges, chart types, indicators, status and persistence", async ({ page }) => {
  await page.goto("/asset/nvda/");
  const chart = page.locator(".market-chart-shell").first();
  await expect(chart).toBeVisible();
  await expect(chart.getByText("ALPACA IEX")).toBeVisible();
  await expect(chart.getByText("DISPLAY BARS ≠ ORACLE EVIDENCE")).toBeVisible();
  await expect(chart.locator("canvas").first()).toBeVisible();
  await expect(page.locator(".asset-chart-toolbar")).toBeHidden();

  await chart.getByRole("button", { name: "1M", exact: true }).click();
  await expect(chart.getByLabel("Candle resolution")).toHaveValue("30Min");
  await chart.getByLabel("Chart type").selectOption("Line");
  await chart.getByLabel("Add indicator").selectOption("EMA");
  await expect(chart.locator(".indicator-chips")).toContainText("EMA 20");

  await page.reload();
  const restored = page.locator(".market-chart-shell").first();
  await expect(restored.getByLabel("Chart type")).toHaveValue("Line");
  await expect(restored.locator(".indicator-chips")).toContainText("EMA 20");
  await restored.getByRole("button", { name: "MAX", exact: true }).click();
  await expect(restored.getByRole("button", { name: "Load older history" })).toBeVisible();
});

test("fullscreen shows only the chart and exposes drawing tools", async ({ page }) => {
  await page.goto("/asset/nvda/");
  const chart = page.locator(".market-chart-shell").first();
  await expect(chart.locator("canvas").first()).toBeVisible();
  await expect(chart.locator(".market-chart-live-price")).toBeVisible();
  await chart.getByRole("button", { name: "Fullscreen" }).click();

  await expect.poll(() => page.evaluate(() => document.fullscreenElement?.classList.contains("market-chart-shell"))).toBe(true);
  await expect(page.locator(".asset-side-rail")).toBeHidden();
  await expect(chart.locator(".market-chart-live-price")).toBeVisible();
  await expect(chart.getByRole("toolbar", { name: "Drawing tools" })).toBeVisible();
  await expect(chart.getByRole("button", { name: "Exit fullscreen" })).toBeVisible();

  await chart.getByRole("button", { name: "Trend line" }).click();
  const layer = chart.locator(".chart-drawing-layer");
  const bounds = await layer.boundingBox();
  if (!bounds) throw new Error("Drawing layer did not render");
  await page.mouse.move(bounds.x + 180, bounds.y + 180);
  await page.mouse.down();
  await page.mouse.move(bounds.x + 480, bounds.y + 320, { steps: 4 });
  await page.mouse.up();
  await expect(layer.locator("line")).toHaveCount(1);

  await chart.getByRole("button", { name: "Exit fullscreen" }).click();
  await expect.poll(() => page.evaluate(() => document.fullscreenElement)).toBeNull();
});

test("six-month candlestick range paints OHLC candles", async ({ page }) => {
  await page.goto("/asset/nvda/");
  const chart = page.locator(".market-chart-shell").first();
  await chart.getByRole("button", { name: "6M", exact: true }).click();
  await chart.getByLabel("Chart type").selectOption("Candlestick");
  await expect(chart.getByLabel("Candle resolution")).toHaveValue("1Day");
  await expect.poll(() => chart.locator(".market-chart-canvas canvas").evaluateAll((canvases) => {
    let candlePixels = 0;
    for (const canvas of canvases as HTMLCanvasElement[]) {
      const context = canvas.getContext("2d"); if (!context) continue;
      const data = context.getImageData(0, 0, canvas.width, canvas.height).data;
      for (let index = 0; index < data.length; index += 4) {
        const red = data[index]; const green = data[index + 1]; const blue = data[index + 2];
        if (Math.abs(red - 22) < 12 && Math.abs(green - 199) < 12 && Math.abs(blue - 132) < 12) candlePixels += 1;
      }
    }
    return candlePixels;
  })).toBeGreaterThan(20);
});

test("chart toolbar remains usable on a mobile viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/asset/nvda/");
  const chart = page.locator(".market-chart-shell").first();
  await expect(chart.getByRole("button", { name: "5D", exact: true })).toBeVisible();
  await expect(chart.getByLabel("Chart type")).toBeVisible();
});
