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

test("HLSF narrative phases, hints and refresh persistence", async ({ page, request }) => {
  const rows = readCodes();
  await request.post("/api/admin/login", {
    data: { password: "local-dev-admin-password-123" },
  });
  const overviewResponse = await request.get("/api/admin/overview");
  expect(overviewResponse.status()).toBe(200);
  const overview = await overviewResponse.json();
  const available = new Set(
    overview.participants
      .filter(
        (participant: any) =>
          participant.stage === "not_started" &&
          (participant.group === "G3" || participant.group === "G4"),
      )
      .map((participant: any) => participant.participant_id),
  );
  const row = rows.find((item) => available.has(item.participant_id));
  if (!row) throw new Error("No unused B-first participant found");

  const loginResponse = await page.request.post("/api/auth/enter", {
    data: { code: row.access_code, class_id: Number(row.class_id) },
  });
  expect(loginResponse.ok()).toBeTruthy();
  await page.goto("/");
  await page.getByTestId("question-demo_prior").locator('input[type="radio"]').first().check();
  await page.getByRole("button", { name: /提交 \/ Submit/ }).click();
  await page.getByRole("button", { name: /开始本轮/ }).click();

  const currentPhase = page.locator(".guide-phase.current");
  await expect(currentPhase).toContainText("观察");
  const chat = page.getByTestId("chat-messages");
  await expect(chat).toContainText("想围绕它提出什么问题");
  await expect(chat).toContainText("what question you would want the story to raise");

  await page.getByRole("button", { name: /获取一次提示/ }).click();
  await expect(page.getByRole("button", { name: /本阶段提示已使用/ })).toBeDisabled();
  await expect(chat).toContainText("为什么");

  await page.getByRole("button", { name: /下一阶段 \/ Next/ }).click();
  await expect(currentPhase).toContainText("解释");
  await expect(chat).toContainText("哪些事实或证据能解释它");

  await page.getByRole("button", { name: /下一阶段 \/ Next/ }).click();
  await expect(currentPhase).toContainText("创作");
  await expect(chat).toContainText("历史侦探");
  await expect(chat).toContainText("过程重建");

  await page.locator("#script-title").fill("叙事测试脚本");
  await page.locator("#script-body").fill("一只白鹤越过水面，回到莲花与云纹之间，讲述高洁与仕途理想的文化含义。");
  await expect(page.getByText("已自动保存 / Autosaved").first()).toBeVisible({ timeout: 10_000 });

  await page.getByRole("button", { name: /下一阶段 \/ Next/ }).click();
  await expect(currentPhase).toContainText("反思");
  await expect(chat).toContainText("请对照右侧你已保存的脚本");
  await expect(chat).toContainText("哪些内容有证据支持");

  await page.getByRole("button", { name: /下一阶段 \/ Next/ }).click();
  await expect(page.getByText("学习引导已完成 / Guide complete")).toBeVisible();

  await page.reload();
  await expect(page.getByText("学习引导已完成 / Guide complete")).toBeVisible();
  await expect(chat).toContainText("哪些事实或证据能解释它");
  await expect(page.locator("#script-body")).toHaveValue(/白鹤越过水面/);
});
