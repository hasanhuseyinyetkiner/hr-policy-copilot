import path from "node:path";
import { expect, test } from "@playwright/test";
import { fileURLToPath } from "node:url";

const screenshots = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../docs/screenshots");

async function captureThemePair(
  page: import("@playwright/test").Page,
  basename: string,
): Promise<void> {
  await page.screenshot({ path: path.join(screenshots, `${basename}-light.png`) });
  await page.getByRole("button", { name: "Switch to dark theme" }).click();
  await page.screenshot({ path: path.join(screenshots, `${basename}-dark.png`) });
  await page.getByRole("button", { name: "Switch to light theme" }).click();
}

test("capture library, cited conflict, abstention, and source", async ({ page }) => {
  await page.goto("/library");
  await expect(page.getByRole("link", { name: "Remote Work Policy" })).toBeVisible();
  await captureThemePair(page, "library");

  await page.goto("/ask");
  await page.getByLabel("Policy question").fill("How many in-office days per week are required?");
  await page.getByRole("button", { name: "Ask" }).click();
  const answer = page.getByTestId("answer");
  await expect(answer).toContainText("Sources disagree");
  await expect(answer).toContainText("in-office days");
  await captureThemePair(page, "answer");

  await page.getByTestId("citation-link").first().click();
  await expect(page.getByTestId("cited-passage")).toBeVisible();
  await captureThemePair(page, "source");

  await page.goto("/ask");
  await page.getByLabel("Policy question").fill("What is the sabbatical policy for pet iguanas?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByTestId("abstain")).toBeVisible();
  await expect(page.getByTestId("answer")).toContainText("No cited answer is available");
  await captureThemePair(page, "abstain");
});
