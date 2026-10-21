import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { expect, test } from "@playwright/test";

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

test("critical ask / cite / abstain journey", async ({ page }) => {
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
  await expect(page.getByTestId("open-telemetry")).toBeVisible();
  await page.getByTestId("open-telemetry").click();
  const telemetry = page.getByTestId("telemetry-drawer");
  await expect(telemetry).toBeVisible();
  await expect(page.getByTestId("retrieval-meta")).toContainText("ms");
  await telemetry.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByTestId("citation-link").first().click();
  await expect(page.getByTestId("cited-passage")).toContainText("25 days of annual leave");

  await page.goto("/ask");
  await page.getByLabel("Policy question").fill("What is the sabbatical policy for pet iguanas?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByTestId("abstain")).toBeVisible();
  await expect(page.getByTestId("answer")).toContainText("No cited answer is available");
});

test("upload indexes then query opens a citation", async ({ page }) => {
  const runToken = `RUN${Date.now()}`;
  const title = `Shuttle Allowance Note ${runToken}`;
  const uploadPath = path.join(os.tmpdir(), `hr-shuttle-policy-${runToken}.txt`);
  const body =
    "SYNTHETIC DOCUMENT — not a real policy and not legal advice.\n\n" +
    `1. Shuttle\nThe ORANGE-SHUTTLE-${runToken} allowance grants field staff 11 shuttle days each quarter.\n`;
  fs.writeFileSync(uploadPath, body, "utf8");

  await page.goto("/library");
  await page.getByLabel("Title").fill(title);
  await page.getByTestId("upload-file").setInputFiles(uploadPath);
  await page.getByRole("button", { name: "Upload" }).click();
  // indexingLabel: "indexed" → "is indexed."; "indexed_sparse" → "is sparse only."
  await expect(
    page.getByText(new RegExp(`${escapeRegExp(title)} is (indexed|sparse only)\\.?`, "i")),
  ).toBeVisible({
    timeout: 60_000,
  });
  await expect(page.getByRole("link", { name: title })).toBeVisible();

  await page.getByRole("link", { name: "Ask" }).click();
  await page
    .getByLabel("Policy question")
    .fill(
      `How many shuttle days does the ORANGE-SHUTTLE-${runToken} allowance grant field staff each quarter?`,
    );
  await page.getByRole("button", { name: "Ask" }).click();
  const answer = page.getByTestId("answer");
  await expect(answer).toContainText("Evidence-backed");
  await expect(answer).toContainText("11 shuttle days");
  await page.getByTestId("citation-link").first().click();
  await expect(page.getByTestId("cited-passage")).toContainText(`ORANGE-SHUTTLE-${runToken}`);
});
