import { expect, test } from "@playwright/test";

test("seeded question cites a passage and an unknown question abstains", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Local demo · synthetic data")).toBeVisible();
  await expect(page.getByText("Indexed documents")).toBeVisible();

  await page.getByRole("link", { name: "Ask" }).click();
  await page
    .getByLabel("Policy question")
    .fill("How many days of annual leave does a full-time employee receive?");
  await page.getByRole("button", { name: "Ask" }).click();
  const answer = page.getByTestId("answer");
  await expect(answer).toContainText("25 days of annual leave");
  await expect(answer).toContainText("hybrid retrieval");
  await page.getByTestId("citation-link").first().click();
  await expect(page.getByTestId("cited-passage")).toContainText("25 days of annual leave");

  await page.goto("/ask");
  await page.getByLabel("Policy question").fill("What is the sabbatical policy for pet iguanas?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByTestId("abstain")).toBeVisible();
});
