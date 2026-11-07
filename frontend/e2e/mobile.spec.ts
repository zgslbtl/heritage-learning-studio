import { expect, test } from "@playwright/test";
import path from "node:path";

test.use({ viewport: { width: 390, height: 844 } });

test("entry page remains readable on a narrow viewport", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByLabel("PolyU email")).toBeVisible();
  await expect(page.getByRole("button", { name: /开始实验/ })).toBeVisible();
  const widths = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(widths.scroll).toBeLessThanOrEqual(widths.client + 1);
  await page.screenshot({
    path: path.resolve(process.cwd(), "..", "e2e", "screenshots", "mobile-entry.png"),
    fullPage: true,
  });
});
