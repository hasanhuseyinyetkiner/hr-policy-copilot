import path from "node:path";
import { expect, test } from "@playwright/test";
import { fileURLToPath } from "node:url";

const screenshots = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../docs/screenshots");

test("capture the working library, answer, and source", async ({ page }) => {
  await page.goto("/library");
  await expect(page.getByRole("link", { name: "Remote Work Policy" })).toBeVisible();
  await page.screenshot({ path: path.join(screenshots, "library-light.png") });
  await page.getByRole("button", { name: "Switch to dark theme" }).click();
  await page.screenshot({ path: path.join(screenshots, "library-dark.png") });
  await page.getByRole("button", { name: "Switch to light theme" }).click();

  await page.goto("/ask");
  await page.getByLabel("Policy question").fill("How many in-office days per week are required?");
  await page.getByRole("button", { name: "Ask" }).click();
  const answer = page.getByTestId("answer");
  await expect(answer).toContainText("Sources disagree");
  await expect(answer).toContainText("in-office days");
  await page.screenshot({ path: path.join(screenshots, "answer-light.png") });
  await page.getByRole("button", { name: "Switch to dark theme" }).click();
  await page.screenshot({ path: path.join(screenshots, "answer-dark.png") });
  await page.getByRole("button", { name: "Switch to light theme" }).click();

  await page.getByTestId("citation-link").first().click();
  await expect(page.getByTestId("cited-passage")).toBeVisible();
  await page.screenshot({ path: path.join(screenshots, "source-light.png") });
  await page.getByRole("button", { name: "Switch to dark theme" }).click();
  await page.screenshot({ path: path.join(screenshots, "source-dark.png") });
});
