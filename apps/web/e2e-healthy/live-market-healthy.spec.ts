import { expect, test } from "@playwright/test";

test("qualified direct evidence and a venue mark are healthy through the browser", async ({ page, request }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await expect.poll(async () => {
    const response = await request.get("/health/ready");
    return (await response.json()).market_health.execution_ready;
  }).toBe(true);

  await page.goto("/");
  await page.getByRole("button", { name: "Live research" }).click();
  await expect(page.getByText("WS connected", { exact: true })).toBeVisible();
  const marketHealth = page.locator(".market-kpis .kpi").filter({ hasText: "Market health" });
  await expect(marketHealth.getByText("Healthy", { exact: true })).toBeVisible();
  await expect(page.getByRole("cell", { name: "direct consensus" })).toBeVisible();
  await expect(page.getByText("Direct independent venues agree.", { exact: true })).toBeVisible();
  expect(consoleErrors).toEqual([]);
});
