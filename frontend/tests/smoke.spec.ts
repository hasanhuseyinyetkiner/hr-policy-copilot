import path from "node:path";
import { expect, test } from "@playwright/test";
import { fileURLToPath } from "node:url";

const fixtures = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "fixtures");

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

test("upload indexes then query opens a citation", async ({ page }) => {
  const uploadPath = path.join(fixtures, "shuttle-policy.txt");
  await page.goto("/library");
  await page.getByLabel("Title").fill("Shuttle Allowance Note");
  await page.getByTestId("upload-file").setInputFiles(uploadPath);
  await page.getByRole("button", { name: "Upload" }).click();
  await expect(page.getByText(/Shuttle Allowance Note is indexed/i)).toBeVisible({
    timeout: 60_000,
  });
  await expect(page.getByRole("link", { name: "Shuttle Allowance Note" })).toBeVisible();

  await page.getByRole("link", { name: "Ask" }).click();
  await page
    .getByLabel("Policy question")
    .fill("How many shuttle days does the ORANGE-SHUTTLE allowance grant field staff each quarter?");
  await page.getByRole("button", { name: "Ask" }).click();
  const answer = page.getByTestId("answer");
  await expect(answer).toContainText("Evidence-backed");
  await expect(answer).toContainText("11 shuttle days");
  await page.getByTestId("citation-link").first().click();
  await expect(page.getByTestId("cited-passage")).toContainText("ORANGE-SHUTTLE");
});
