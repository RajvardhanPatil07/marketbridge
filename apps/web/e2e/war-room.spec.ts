import { expect, test } from "@playwright/test";

test("War Room recomputes editable attack inputs, preserves exits and replays proof", async ({ page }) => {
  await page.goto("/demo/");
  await expect(page.getByRole("heading", { name: /Evidence, operating characteristics/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Market Truth War Room" })).toBeVisible();
  await page.screenshot({ path: "../../artifacts/ui-qa/proof-first-demo.png", fullPage: true });
  await expect(page.getByText("PARAMETERIZED ADVERSARIAL DEMO", { exact: false })).toBeVisible();

  const reset = page.getByRole("button", { name: /Reset incident/i });
  await reset.click();
  await expect(reset).toBeEnabled();
  await page.getByLabel("Evidence mode").selectOption("SYNTHETIC");
  await page.getByLabel("Order notional").fill("12000");
  await page.getByLabel("Attack (bps)").fill("600");

  const decision = page.locator(".decision-monolith");

  await page.getByRole("button", { name: /Normal market/i }).click();
  await expect(decision.getByText("ALLOW", { exact: true })).toBeVisible();
  await expect(page.getByText("12,000", { exact: false }).first()).toBeVisible();

  await page.getByRole("button", { name: /Poison venue mark/i }).click();
  await expect(decision.getByText("BLOCK NEW RISK", { exact: true })).toBeVisible();
  await expect(page.locator(".war-provenance-strip").getByText("600 bps", { exact: true })).toBeVisible();
  await page.screenshot({ path: "../../artifacts/ui-qa/war-room-block.png", fullPage: true });
  await expect(decision.getByText("AVAILABLE", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: /Replay without safety gate/i }).click();
  const comparison = page.locator(".counterfactual");
  await expect(comparison.getByText("ADDITIONAL SIMULATED EXPOSURE PREVENTED", { exact: true })).toBeVisible();
  await expect(comparison.getByText("$12,000.00", { exact: true })).toBeVisible();
});
