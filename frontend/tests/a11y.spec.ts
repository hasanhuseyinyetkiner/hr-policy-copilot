import { expect, test } from "@playwright/test";

test("accessibility smoke: skip link, labeled ask, telemetry dialog", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeAttached();
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Switch to (dark|light) theme/ })).toBeVisible();

  await page.getByRole("link", { name: "Ask" }).click();
  const question = page.getByLabel("Policy question");
  await expect(question).toBeVisible();
  await question.fill("How many days of annual leave does a full-time employee receive?");
  await page.getByRole("button", { name: "Ask" }).click();
  const answer = page.getByTestId("answer");
  await expect(answer).toBeVisible();
  await expect(answer).toHaveAttribute("aria-live", "polite");

  await page.getByTestId("open-telemetry").click();
  const drawer = page.getByTestId("telemetry-drawer");
  await expect(drawer).toBeVisible();
  await expect(page.getByRole("dialog", { name: "Retrieval telemetry" })).toBeVisible();
  await expect(page.getByTestId("retrieval-meta")).toContainText("Corpus version");
  await drawer.getByRole("button", { name: "Close", exact: true }).click();
  await expect(drawer).toBeHidden();
});
