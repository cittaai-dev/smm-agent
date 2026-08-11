import { test, expect } from "@playwright/test";
import path from "node:path";

// step6_production_operations.md §0 -- proves the actual rendered UI wires
// up to the real API across a page navigation, something unit/component
// tests can't catch. Deliberately stops short of "Approve": that step needs
// a real LLM to synthesize every one of the 11 SOP-1 sections through the
// quality checkpoint gate (components/QualityCheckpointPanel.tsx), which
// requires SMM_LLM_OPENAI_API_KEY -- a secret this smoke run doesn't assume
// is configured (backend/.env.example ships it empty on purpose, see
// TESTING.md's "no real LLM calls in the general suite"). Extend to
// "...run -> review -> approve" once a nightly/staging job supplies that key.
test("upload -> onboard -> run research request reaches the API without a console crash", async ({
  page,
}) => {
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });

  const brandId = `smoke-${Date.now()}`;
  await page.goto(`/brands/${brandId}/onboard`);
  await expect(page.getByRole("heading", { name: "Onboard brand material" })).toBeVisible();

  await page.locator('input[type=file]').first().setInputFiles(path.join(__dirname, "fixtures/sample.txt"));
  await expect(page.getByText(/Queued for ingest/)).toBeVisible({ timeout: 10_000 });

  await page.getByRole("link", { name: "Continue to plan" }).click();
  await expect(page).toHaveURL(new RegExp(`/brands/${brandId}/plan`));

  await page.getByRole("button", { name: /Run research|Waiting for ingest/ }).click();
  // Without a configured LLM key this 503s with a visible, non-crashing
  // error message -- proving the request round-tripped to the real backend,
  // not that synthesis succeeded.
  await expect(page.getByText(/Run failed|Running/)).toBeVisible({ timeout: 15_000 });

  expect(consoleErrors).toEqual([]);
});
