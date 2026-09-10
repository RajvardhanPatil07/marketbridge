import { expect, test } from "@playwright/test";

test("War Room demonstrates poisoned mark, preserved exit and counterfactual", async ({ page }) => {
  await page.goto("/demo/");
  await expect(page.getByRole("heading", { name: /Evidence, operating characteristics/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Market Truth War Room" })).toBeVisible();
  await page.screenshot({ path: "../../artifacts/ui-qa/proof-first-demo.png", fullPage: true });
  await expect(page.getByText("SYNTHETIC ADVERSARIAL DEMO", { exact: false })).toBeVisible();

  const decision = page.locator(".decision-monolith");

  await page.getByRole("button", { name: /Normal market/i }).click();
  await expect(decision.getByText("ALLOW", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: /Poison venue mark/i }).click();
  await expect(decision.getByText("BLOCK NEW RISK", { exact: true })).toBeVisible();
  await page.screenshot({ path: "../../artifacts/ui-qa/war-room-block.png", fullPage: true });
  await expect(decision.getByText("AVAILABLE", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: /Replay without safety gate/i }).click();
  const comparison = page.locator(".counterfactual");
  await expect(comparison.getByText("ADDITIONAL SIMULATED EXPOSURE PREVENTED", { exact: true })).toBeVisible();
  await expect(comparison.getByText("$10,000.00", { exact: true })).toBeVisible();
});