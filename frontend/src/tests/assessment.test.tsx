import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import AssessmentPage from "../pages/AssessmentPage";
import type { AssessmentPayload, StudentState } from "../types";

const state: StudentState = {
  participant: { id: "11111111-1111-1111-1111-111111111111", class_id: 1, class_name: "Class 1" },
  run_id: "22222222-2222-2222-2222-222222222222",
  stage: "k0",
  stage_label: "K0",
  step: 1,
  total_steps: 6,
  completed: false,
  assessment_kind: "k0",
  assessment_label: "Pre-test",
  active_round: null,
  server_time: new Date().toISOString(),
};

const instrument: AssessmentPayload = {
  instrument: {
    id: "33333333-3333-3333-3333-333333333333",
    kind: "k0",
    version: 1,
    title: "Placeholder assessment",
    instructions: "Read carefully",
    questions: [
      {
        id: "single",
        type: "single_choice",
        prompt: "A single choice",
        required: true,
        options: [
          { value: "a", label: "Option A" },
          { value: "b", label: "Option B" },
        ],
      },
      {
        id: "multi",
        type: "multi_choice",
        prompt: "A multiple choice",
        required: true,
        options: [
          { value: "x", label: "Choice X" },
          { value: "y", label: "Choice Y" },
        ],
      },
      {
        id: "text",
        type: "short_text",
        prompt: "A short answer",
        required: true,
        max_length: 100,
      },
      {
        id: "evidence",
        type: "evidence_judgment",
        prompt: "Evidence judgement",
        required: true,
        rows: [{ id: "e1", label: "Evidence one" }],
      },
      {
        id: "scale",
        type: "likert",
        prompt: "A rating",
        required: true,
        scale_min: 1,
        scale_max: 5,
      },
    ],
  },
  answers: {},
  status: "draft",
  started_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

function mockFetch(payload = instrument) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.includes("/draft")) {
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
}

describe("AssessmentPage", () => {
  it("saves and restores other background detail and clears it on category changes", async () => {
    const fetchMock = mockFetch({
      ...instrument,
      instrument: { ...instrument.instrument, questions: [{
        id: "B-01", type: "single_choice", prompt: "专业背景", required: true,
        options: [{ value: "a", label: "设计相关" }, { value: "d", label: "其他", allow_text: true }],
      }] },
      answers: { "B-01": { value: "d", text: "工程" } },
    });
    render(<AssessmentPage state={state} kind="k0" onState={() => undefined} />);
    const detail = await screen.findByRole("textbox", { name: "其他专业背景说明" });
    expect(detail).toHaveValue("工程");
    expect(screen.getByRole("radio", { name: "其他" })).toBeChecked();
    const user = userEvent.setup();
    await user.clear(detail);
    await user.type(detail, "计算机科学");
    await waitFor(() => {
      const saved = fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/draft"));
      expect(saved.length).toBeGreaterThan(0);
      expect(JSON.parse(saved[saved.length - 1][1]?.body as string).answers)
        .toEqual({ "B-01": { value: "d", text: "计算机科学" } });
    }, { timeout: 2500 });
    await user.click(screen.getByRole("radio", { name: "设计相关" }));
    expect(detail).toHaveValue("");
    const draft = JSON.parse(localStorage.getItem(`hls:assessment:${state.run_id}:k0`)!);
    expect(draft.answers).toEqual({ "B-01": "a" });
    await user.click(detail);
    expect(screen.getByRole("radio", { name: "其他" })).toBeChecked();
  });

  it("renders all supported question types and records answers", async () => {
    mockFetch();
    render(<AssessmentPage state={state} kind="k0" onState={() => undefined} />);
    expect(await screen.findByText("Placeholder assessment")).toBeInTheDocument();
    expect(screen.getByText("A single choice")).toBeInTheDocument();
    expect(screen.getByText("A multiple choice")).toBeInTheDocument();
    expect(screen.getByText("A short answer")).toBeInTheDocument();
    expect(screen.getByText("Evidence judgement")).toBeInTheDocument();
    expect(screen.getByText("A rating")).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByLabelText("Option A"));
    await user.click(screen.getByLabelText("Choice X"));
    await user.type(screen.getByLabelText("A short answer"), "My answer");
    await user.click(screen.getByLabelText("5"));
    await waitFor(() => expect(screen.getByTestId("question-single")).toBeInTheDocument());
  });

  it("shows the AI-disabled banner during the R1 assessment", async () => {
    mockFetch({
      ...instrument,
      instrument: { ...instrument.instrument, kind: "k1", title: "K1 placeholder" },
    });
    render(
      <AssessmentPage
        state={{ ...state, stage: "k1", step: 3, assessment_kind: "k1" }}
        kind="k1"
        onState={() => undefined}
      />,
    );
    expect(await screen.findByTestId("ai-disabled-banner")).toBeInTheDocument();
  });

  it("shows an image-only artifact and no score or test wording", async () => {
    mockFetch({
      ...instrument,
      artifact_image_url: "/api/files/artifacts/version/media/M-full",
      instrument: {
        ...instrument.instrument,
        title: "开始前的小问题",
        questions: [instrument.instrument.questions[0]],
      },
    });
    render(<AssessmentPage state={{ ...state, stage: "k1", assessment_kind: "k1" }} kind="k1" onState={() => undefined} />);
    expect(await screen.findByRole("img", { name: "文物图片" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /继续/ })).toBeInTheDocument();
    expect(screen.queryByText(/总分|分值|得分|测试|考试/)).not.toBeInTheDocument();
    expect(screen.queryByText(/required/i)).not.toBeInTheDocument();
  });

  it("moves from the baseline block to the artifact questions without exposing both at once", async () => {
    const q = instrument.instrument.questions[0];
    mockFetch({
      ...instrument,
      instrument: {
        ...instrument.instrument,
        title: "开始前的小问题",
        questions: [
          { ...q, id: "baseline", prompt: "A baseline question", section: "开始前" },
          { ...q, id: "artifact", prompt: "An artifact question", section: "关于这件文物" },
        ],
      },
    });
    render(<AssessmentPage state={state} kind="k0" onState={() => undefined} />);
    expect(await screen.findByText("A baseline question")).toBeInTheDocument();
    expect(screen.queryByText("An artifact question")).not.toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(screen.getByLabelText("Option A"));
    await user.click(screen.getByRole("button", { name: /继续/ }));
    expect(await screen.findByText("An artifact question")).toBeInTheDocument();
    expect(screen.queryByText("A baseline question")).not.toBeInTheDocument();
  });

  it("shows an inline text field when the Other option is selected", async () => {
    const q = instrument.instrument.questions[0];
    mockFetch({
      ...instrument,
      instrument: {
        ...instrument.instrument,
        questions: [
          {
            ...q,
            prompt: "专业背景",
            options: [
              { value: "design", label: "设计相关" },
              { value: "other", label: "其他", allow_text: true },
            ],
          },
        ],
      },
    });
    render(<AssessmentPage state={state} kind="k0" onState={() => undefined} />);
    const user = userEvent.setup();
    await screen.findByText("专业背景");
    await user.click(screen.getByLabelText("其他"));
    const otherInput = await screen.findByLabelText("其他专业背景说明");
    await user.type(otherInput, "建筑学");
    expect(otherInput).toHaveValue("建筑学");
  });

  it("shows Likert endpoint labels only at 1 and the maximum", async () => {
    mockFetch({
      ...instrument,
      instrument: {
        ...instrument.instrument,
        questions: [
          {
            id: "scale7",
            type: "likert",
            prompt: "A seven point rating",
            required: true,
            scale_min: 1,
            scale_max: 7,
            scale_labels: ["非常不同意", "非常同意"],
          },
        ],
      },
    });
    render(<AssessmentPage state={state} kind="survey" onState={() => undefined} />);
    await screen.findByText("A seven point rating");
    expect(screen.getAllByText("非常不同意")).toHaveLength(1);
    expect(screen.getAllByText("非常同意")).toHaveLength(1);
  });

  it("restores a differing local draft only after explicit action", async () => {
    mockFetch();
    window.localStorage.setItem(
      `hls:assessment:${state.run_id}:k0`,
      JSON.stringify({ answers: { single: "b" }, savedAt: new Date().toISOString() }),
    );
    render(<AssessmentPage state={state} kind="k0" onState={() => undefined} />);
    expect(await screen.findByText(/尚未同步的本地草稿/)).toBeInTheDocument();
  });
});
