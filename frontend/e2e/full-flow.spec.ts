import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

interface CodeRow {
  class_id: string;
  access_code: string;
  group: string;
  participant_id: string;
}

const projectRoot = path.resolve(process.cwd(), "..");
const codesPath = path.join(projectRoot, ".local-runtime", "data", "private", "access_codes.csv");

function readCodes(): CodeRow[] {
  const content = fs.readFileSync(codesPath, "utf8").replace(/^\uFEFF/, "");
  const [header, ...lines] = content.trim().split(/\r?\n/);
  const columns = header.split(",");
  return lines.map((line) => {
    const values = line.split(",");
    return {
      class_id: values[columns.indexOf("class_id")],
      access_code: values[columns.indexOf("access_code")],
      group: values[columns.indexOf("group")],
      participant_id: values[columns.indexOf("participant_id")],
    };
  });
}

async function login(page: any, row: CodeRow) {
  const response = await page.request.post("/api/auth/enter", {
    data: { code: row.access_code, class_id: Number(row.class_id) },
  });
  expect(response.ok()).toBeTruthy();
  await page.goto("/");
  await expect(page.getByText("前测占位 / Pre-test placeholder")).toBeVisible();
}

test("B then A full participant flow, resume, and researcher inspection", async ({ page, request }) => {
  const rows = readCodes();
  await request.post("/api/admin/login", { data: { password: "local-dev-admin-password-123" } });
  const overviewResponse = await request.get("/api/admin/overview");
  expect(overviewResponse.status()).toBe(200);
  const overview = await overviewResponse.json();
  const available = new Set(
    overview.participants
      .filter((participant: any) => participant.stage === "not_started" && (participant.group === "G3" || participant.group === "G4"))
      .map((participant: any) => participant.participant_id),
  );
  const row = rows.find((item) => available.has(item.participant_id));
  if (!row) throw new Error("No unused B-first participant found");
  await login(page, row);
  await expect(page.locator("body")).not.toContainText("条件 A");
  await expect(page.locator("body")).not.toContainText("Condition A");
  await expect(page.locator("body")).not.toContainText(row.group);

  await page.getByTestId("question-demo_prior").locator('input[type="radio"]').first().check();
  await page.getByRole("button", { name: /提交 \/ Submit/ }).click();

  await expect(page.getByRole("button", { name: /开始本轮/ })).toBeVisible();
  await page.getByRole("button", { name: /开始本轮/ }).click();

  await expect(page.getByRole("heading", { name: "AI 对话" })).toBeVisible();
  await expect(page.getByText("学习引导 / Learning Guide").first()).toBeVisible();
  await expect(page.getByText("Observe").first()).toBeVisible();
  await expect(page.locator("body")).not.toContainText(row.group);

  const messageBox = page.getByPlaceholder("请输入你的问题或想法… / Enter your question or idea…");
  await messageBox.fill("What should I notice in this artifact?");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.locator(".message-bubble").filter({ hasText: "[LOCAL TEST STUB" }).last()).toBeVisible();

  const title = page.locator("#script-title");
  const body = page.locator("#script-body");
  await title.fill("A test video title");
  await body.fill("This is a saved draft about the cultural heritage artifact. It should survive a reload.");
  await expect(page.getByText("已自动保存 / Autosaved").first()).toBeVisible({ timeout: 10_000 });

  await page.reload();
  await expect(page.locator("#script-title")).toHaveValue("A test video title");
  await expect(page.locator("#script-body")).toHaveValue(/survive a reload/);
  await expect(page.locator(".message-bubble").filter({ hasText: "[LOCAL TEST STUB" }).last()).toBeVisible();
  await expect(page.getByText("学习引导 / Learning Guide").first()).toBeVisible();
  await page.screenshot({ path: path.join(projectRoot, "e2e", "screenshots", "workbench-resumed.png"), fullPage: true });

  await page.getByRole("button", { name: /生成关键帧/ }).click();
  await expect(page.getByAltText("Generated keyframe")).toBeVisible({ timeout: 45_000 });
  await page.getByRole("button", { name: /保存并继续/ }).click();

  await expect(page.getByTestId("ai-disabled-banner")).toBeVisible();
  await page.getByTestId("question-demo_reflection").locator("textarea").fill("An independent R1 answer.");
  await page.getByRole("button", { name: /提交 \/ Submit/ }).click();

  await expect(page.getByRole("button", { name: /开始本轮/ })).toBeVisible();
  await page.getByRole("button", { name: /开始本轮/ }).click();
  await expect(page.getByText("学习引导 / Learning Guide")).toHaveCount(0);
  await expect(page.getByText("HLSF-Guided Creation")).toHaveCount(0);

  const messageBox2 = page.getByPlaceholder("请输入你的问题或想法… / Enter your question or idea…");
  await messageBox2.fill("Independent second-round question.");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.locator(".message-bubble").filter({ hasText: "[LOCAL TEST STUB" }).last()).toBeVisible();

  await page.locator("#script-title").fill("Second round title");
  await page.locator("#script-body").fill("A second-round script saved for the browser test.");
  await expect(page.getByText("已自动保存 / Autosaved").first()).toBeVisible({ timeout: 10_000 });
  await page.getByRole("button", { name: /生成关键帧/ }).click();
  await expect(page.getByAltText("Generated keyframe")).toBeVisible({ timeout: 45_000 });
  await page.getByRole("button", { name: /保存并继续/ }).click();

  await expect(page.getByText("后测占位 / Post-test placeholder")).toBeVisible();
  await page.getByTestId("question-demo_post").locator('input[type="radio"]').first().check();
  await page.getByRole("button", { name: /提交 \/ Submit/ }).click();

  await expect(page.getByText("迁移题占位 / Transfer placeholder")).toBeVisible();
  await page.getByTestId("question-demo_transfer").locator("textarea").fill("A transfer response.");
  await page.getByRole("button", { name: /提交 \/ Submit/ }).click();

  await expect(page.getByText("问卷占位 / Questionnaire placeholder")).toBeVisible();
  await page.getByTestId("question-demo_satisfaction").locator('input[type="radio"]').nth(3).check();
  await page.getByRole("button", { name: /提交 \/ Submit/ }).click();

  await expect(page.getByRole("heading", { name: "实验已完成" })).toBeVisible();
  await page.screenshot({ path: path.join(projectRoot, "e2e", "screenshots", "participant-complete.png"), fullPage: true });

  await page.goto("/admin");
  await page.getByLabel("研究者密码 / Researcher password").fill("local-dev-admin-password-123");
  await page.getByRole("button", { name: /登录 \/ Sign in/ }).click();
  await expect(page.getByRole("heading", { name: "实验进度" })).toBeVisible();
  await expect(page.getByText("已生成参与者")).toBeVisible();
  expect(await page.locator(".admin-table tbody tr").count()).toBeGreaterThanOrEqual(120);
  await page.screenshot({ path: path.join(projectRoot, "e2e", "screenshots", "admin-overview.png"), fullPage: true });

  await page.getByRole("button", { name: "研究材料" }).click();
  await expect(page.getByText("Evidence Pack X")).toBeVisible();
  await expect(page.getByText("Evidence Pack Y")).toBeVisible();
  await page.getByRole("button", { name: "准备检查" }).click();
  await expect(page.getByRole("heading", { name: "协议冻结与准备检查" })).toBeVisible();
  await expect(page.locator(".readiness-item")).toHaveCount(13);

  const exportResponse = await page.request.get("/api/admin/export");
  expect(exportResponse.status()).toBe(200);
  expect(exportResponse.headers()["content-type"]).toContain("application/zip");
});
