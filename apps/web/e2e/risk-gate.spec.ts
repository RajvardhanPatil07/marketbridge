import { expect, test } from "@playwright/test";

test("paper ticket uses the real gate for allow, block, close, passport and replay", async ({ page }) => {
  await page.goto("/terminal/");
  const gate = page.locator(".safety-order-ticket");
  await expect(gate.getByRole("heading", { name: "Order risk gate" })).toBeVisible();

  await gate.getByRole("button", { name: "CHECK ORDER" }).click();
  await expect(gate.getByText("ALLOW", { exact: true })).toBeVisible();
  await expect(gate.getByText("REDUCE / CLOSE AVAILABLE")).toBeVisible();

  await gate.getByRole("button", { name: "POISONED MARK" }).click();
  await gate.getByRole("button", { name: "CHECK ORDER" }).click();
  await expect(gate.getByText("BLOCK NEW RISK", { exact: true })).toBeVisible();
  await page.screenshot({ path: "../../artifacts/ui-qa/safety-gate-block.png", fullPage: true });

  await gate.getByLabel("Intent").selectOption("CLOSE");
  await gate.getByRole("button", { name: "CHECK ORDER" }).click();
  await expect(gate.getByText("ALLOW", { exact: true })).toBeVisible();

  await gate.getByRole("button", { name: "Open passport" }).click();
  const passport = page.getByRole("dialog", { name: "Safety Passport" });
  await expect(passport.getByText("Cryptographically verified")).toBeVisible();
  await expect(passport.getByText("REDUCE / CLOSE", { exact: false })).toBeVisible();
  await page.screenshot({ path: "../../artifacts/ui-qa/safety-passport-verified.png", fullPage: true });
  await passport.getByRole("button", { name: "Close Safety Passport" }).click();

  await gate.getByRole("button", { name: "Replay current" }).click();
  await expect(gate.getByText("Replay parity: PASS")).toBeVisible();
});

test("restored evidence enters recovery pending instead of immediately allowing", async ({ page }) => {
  await page.goto("/terminal/");
  const gate = page.locator(".safety-order-ticket");
  await gate.getByRole("button", { name: "POISONED MARK" }).click();
  await gate.getByRole("button", { name: "CHECK ORDER" }).click();
  await expect(gate.getByText("BLOCK NEW RISK", { exact: true })).toBeVisible();
  await gate.getByRole("button", { name: "RECOVERY" }).click();
  await gate.getByRole("button", { name: "CHECK ORDER" }).click();
  await expect(gate.locator(".safety-decision").getByText(/^RECOVERY_PENDING ·/)).toBeVisible();
  await expect(gate.getByText("BLOCK NEW RISK", { exact: true })).toBeVisible();
});
