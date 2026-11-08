import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import AssessmentPage from "../pages/AssessmentPage";
import type { AssessmentPayload, Question, StudentState } from "../types";

const state: StudentState = {
  participant: {
    id: "11111111-1111-1111-1111-111111111111",
    class_id: 1,
    class_name: "Class 1",
  },
  run_id: "22222222-2222-2222-2222-222222222222",
  stage: "survey",
  stage_label: "Survey",
  step: 5,
  total_steps: 6,
  completed: false,
  assessment_kind: "survey",
  assessment_label: "Survey",
  active_round: null,
  server_time: new Date().toISOString(),
};

const questions: Question[] = [
  {
    id: "S1",
    type: "likert",
    section: "第一轮创作",
    prompt: "第一轮使用 AI 创作时，我能够探索不同的设计想法或可能性。",
    required: true,
    scale_min: 1,
    scale_max: 7,
    scale_labels: ["非常不同意", "非常同意"],
  },
  {
    id: "S2",
    type: "likert",
    section: "第一轮创作",
    prompt: "第一轮创作中，采用哪些设计想法主要由我自己决定。",
    required: true,
    scale_min: 1,
    scale_max: 7,
    scale_labels: ["非常不同意", "非常同意"],
  },
  {
    id: "S3",
    type: "likert",
    section: "第一轮创作",
    prompt: "完成第一轮文创任务时，你投入了多少心理努力？",
    required: true,
    scale_min: 1,
    scale_max: 9,
    scale_labels: ["极低", "极高"],
  },
  {
    id: "S4",
    type: "likert",
    section: "第二轮创作",
    prompt: "第二轮使用 AI 创作时，我能够探索不同的设计想法或可能性。",
    required: true,
    scale_min: 1,
    scale_max: 7,
    scale_labels: ["非常不同意", "非常同意"],
  },
  {
    id: "S5",
    type: "likert",
    section: "第二轮创作",
    prompt: "第二轮创作中，采用哪些设计想法主要由我自己决定。",
    required: true,
    scale_min: 1,
    scale_max: 7,
    scale_labels: ["非常不同意", "非常同意"],
  },
  {
    id: "S6",
    type: "likert",
    section: "第二轮创作",
    prompt: "完成第二轮文创任务时，你投入了多少心理努力？",
    required: true,
    scale_min: 1,
    scale_max: 9,
    scale_labels: ["极低", "极高"],
  },
  {
    id: "S7",
    type: "single_choice",
    section: "总体偏好",
    prompt:
      "如果只比较 AI 的互动与帮助方式，不考虑两件文物本身的差异，你更愿意在以后的文创设计中使用哪一轮的方式？",
    required: true,
    options: [
      { value: "first", label: "第一轮" },
      { value: "second", label: "第二轮" },
      { value: "same", label: "两种差不多" },
      { value: "uncertain", label: "不确定" },
    ],
  },
];

const payload: AssessmentPayload = {
  instrument: {
    id: "33333333-3333-3333-3333-333333333333",
    kind: "survey",
    version: 2,
    title: "最后几个问题",
    instructions:
      "下面的问题想了解你在两轮创作中的真实体验。两轮使用的文物和 AI 互动方式可能不同，请分别回想每一轮的情况。没有正确或错误答案。",
    questions,
  },
  answers: {},
  status: "draft",
  started_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

function selectFirstPerQuestion(user: ReturnType<typeof userEvent.setup>) {
  const questionIds = Array.from(document.querySelectorAll("fieldset[data-testid^='question-']"))
    .map((fieldset) => fieldset.getAttribute("data-testid")!)
    .map((testId) => testId.replace("question-", ""));
  return Promise.all(
    questionIds.map(async (questionId) => {
      const radios = within(screen.getByTestId(`question-${questionId}`)).getAllByRole(
        "radio",
      );
      await user.click(radios[radios.length - 1]);
    }),
  );
}

describe("Survey V2.1", () => {
  it("shows 7 items in three sections with 1-7, 1-9 and the four preference options", async () => {
    let submitted: Record<string, unknown> | null = null;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/survey/submit") && init?.method === "POST") {
        submitted = JSON.parse(String(init.body)).answers;
        return new Response(
          JSON.stringify({ state: { ...state, stage: "peer_assessment" } }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.endsWith("/survey/draft")) {
        return new Response(JSON.stringify({ status: "draft" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });

    const user = userEvent.setup();
    render(<AssessmentPage state={state} kind="survey" onState={() => undefined} />);

    expect(
      await screen.findByRole("heading", { name: "最后几个问题" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "下面的问题想了解你在两轮创作中的真实体验。两轮使用的文物和 AI 互动方式可能不同，请分别回想每一轮的情况。没有正确或错误答案。",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("第一轮创作")).toBeInTheDocument();
    expect(
      screen.getByText("第一轮使用 AI 创作时，我能够探索不同的设计想法或可能性。"),
    ).toBeInTheDocument();
    expect(
      within(screen.getByTestId("question-S1")).getAllByRole("radio"),
    ).toHaveLength(7);
    expect(
      within(screen.getByTestId("question-S3")).getAllByRole("radio"),
    ).toHaveLength(9);

    await selectFirstPerQuestion(user);
    await user.click(screen.getByRole("button", { name: "继续 / Continue" }));

    expect(await screen.findByText("第二轮创作")).toBeInTheDocument();
    expect(
      screen.getByText("第二轮使用 AI 创作时，我能够探索不同的设计想法或可能性。"),
    ).toBeInTheDocument();
    await selectFirstPerQuestion(user);
    await user.click(screen.getByRole("button", { name: "继续 / Continue" }));

    expect(await screen.findByText("总体偏好")).toBeInTheDocument();
    const preference = screen.getByTestId("question-S7");
    expect(within(preference).getAllByRole("radio")).toHaveLength(4);
    await user.click(within(preference).getByLabelText("两种差不多"));
    await user.click(screen.getByRole("button", { name: "继续 / Continue" }));

    await waitFor(() => expect(submitted).not.toBeNull());
    expect((submitted as any).S7).toBe("same");
    expect(Object.keys(submitted as any).sort()).toEqual([
      "S1",
      "S2",
      "S3",
      "S4",
      "S5",
      "S6",
      "S7",
    ]);
  });
});
