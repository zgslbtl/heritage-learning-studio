import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import PeerAssessmentPage from "../pages/PeerAssessmentPage";
import type { PeerPayload, StudentState } from "../types";

const state: StudentState = {
  participant: {
    id: "11111111-1111-1111-1111-111111111111",
    class_id: 1,
    class_name: "Class 1",
  },
  run_id: "22222222-2222-2222-2222-222222222222",
  stage: "peer_assessment",
  stage_label: "Peer assessment",
  step: 5,
  total_steps: 6,
  completed: false,
  assessment_kind: null,
  assessment_label: null,
  active_round: null,
  server_time: new Date().toISOString(),
};

const review = {
  title_en: "Look at other students’ designs",
  instructions_en: "Rate the image and design statement.",
  principles_en: ["A creative design need not change every pattern."],
  comment_prompt_en: "What is interesting, or what could be improved?",
  version: "peer-review-v2.1-pilot",
  title: "看看其他同学的设计",
  instructions:
    "请根据作品图片和作品说明评价。重点是你能否看懂作品想表达的文化内容，以及设计怎样从文物中获得启发。",
  principles: ["设计有创意不等于一定要完全改变文物图案。"],
  comment_prompt: "你觉得这件作品最有意思的地方是什么？或者还有哪里可以改进？",
  score_min: 1,
  score_max: 5,
  dimensions: [
    {
      key: "cultural_clarity",
      short: "P1",
      label: "文化表达清晰度",
      label_en: "Clarity of cultural expression",
      prompt_en: "Is the cultural meaning clear?",
      anchors_en: ["Almost impossible to understand.", "Not very clear.", "Partly understandable.", "Fairly clear.", "Very clear."],
      prompt: "这件作品想表达的文物知识或文化意义是否清楚？",
      anchors: [
        "几乎无法理解。",
        "表达不太清楚。",
        "能够理解一部分。",
        "表达比较清楚。",
        "表达非常清楚。",
      ],
    },
    {
      key: "cultural_translation",
      short: "P2",
      label: "文化转译清晰度",
      prompt: "你能否看出这件作品如何将文物的特征、结构、功能或文化意义转化为新的设计？",
      anchors: [
        "看不出明确联系。",
        "联系比较模糊。",
        "能够看出一定联系。",
        "联系清楚。",
        "联系清楚且有说服力。",
      ],
    },
    {
      key: "design_originality",
      short: "P3",
      label: "设计创意",
      prompt: "你认为这件作品对文物内容的设计转化有多少新意？",
      anchors: [
        "缺少明显的新构思。",
        "新意较少。",
        "有一定新想法。",
        "构思比较新颖。",
        "构思有明显的新意。",
      ],
    },
  ],
};

function peerPayload(): PeerPayload {
  return {
    deployment_mode: "study",
    waiting: false,
    gate: {
      status: "open",
      entered: 2,
      t2_ended: 2,
      valid_work_count: 4,
      can_open: true,
      message: "",
    },
    batch: {
      id: "33333333-3333-3333-3333-333333333333",
      algorithm_version: "peer-v3-two-rounds",
      scale_version: "peer-review-v2.1-pilot",
      review_version: "peer-review-v2.1-pilot",
      eligible_work_count: 4,
      work_target: 6,
      reviewer_target: 12,
    },
    review,
    assignments: [
      {
        assignment_id: "44444444-4444-4444-4444-444444444444",
        work_code: "W-ABC123",
        round_no: 1,
        artifact_title: "明代纱绣彩云莲塘鹭鸶纹文官六品方补",
        artifact_era: "明代（1368—1644）",
        artifact_type: "方形官服品级织绣标识",
        artifact_introduction:
          "一件明代文官六品方补。本页整理馆藏登记、图像观察、制度背景、工艺与未明信息。",
        product_name: "莲塘鹭影徽章",
        product_category: "徽章",
        design_concept: "",
        rationale_fields: {
          heritage_knowledge: "鹭鸶与六品文官身份有关。",
          cultural_translation: "保留鹭鸶与莲塘组合。",
          design_reason: "便于日常佩戴。",
        },
        structured_fields: {},
        open_statement: "",
        image_url: null,
        status: "pending",
        scores: {},
        comment: "",
      },
    ],
    completed: false,
    submitted: 0,
    total: 1,
  };
}

describe("PeerAssessmentPage", () => {
  it("renders P1-P3 anchors, the frozen artifact introduction and the three rationale parts", async () => {
    let submittedBody: Record<string, unknown> | null = null;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.includes("/impression")) {
        return new Response(JSON.stringify({ viewed_ms: 0 }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (init?.method === "POST" && url.includes("/peer-assessment/")) {
        submittedBody = JSON.parse(String(init.body));
        const payload = peerPayload();
        return new Response(
          JSON.stringify({
            ...payload,
            submitted: 1,
            completed: true,
            assignments: payload.assignments.map((item) => ({
              ...item,
              status: "submitted",
            })),
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      return new Response(JSON.stringify(peerPayload()), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });

    render(
      <PeerAssessmentPage state={state} onState={() => undefined} />,
    );

    expect(await screen.findByText("看看其他同学的设计")).toBeInTheDocument();
    expect(screen.getByText("P1｜文化表达清晰度")).toBeInTheDocument();
    expect(screen.getByText("Clarity of cultural expression")).toBeInTheDocument();
    expect(screen.getByText("Is the cultural meaning clear?")).toBeInTheDocument();
    expect(screen.getByText("Very clear.")).toBeInTheDocument();
    expect(screen.getByText("Rate the image and design statement.")).toBeInTheDocument();
    expect(screen.getByText("A creative design need not change every pattern.")).toBeInTheDocument();
    expect(screen.getByText("P2｜文化转译清晰度")).toBeInTheDocument();
    expect(screen.getByText("P3｜设计创意")).toBeInTheDocument();
    expect(screen.getByText("表达非常清楚。")).toBeInTheDocument();
    expect(screen.getByText("联系清楚且有说服力。")).toBeInTheDocument();
    expect(screen.getByText("构思有明显的新意。")).toBeInTheDocument();
    expect(
      screen.getByText("明代纱绣彩云莲塘鹭鸶纹文官六品方补"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "一件明代文官六品方补。本页整理馆藏登记、图像观察、制度背景、工艺与未明信息。",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("从文物中学到了什么")).toBeInTheDocument();
    expect(screen.getByText("怎样把知识用到设计里")).toBeInTheDocument();
    expect(screen.getByText("为什么这样设计")).toBeInTheDocument();
    expect(screen.queryByText(/HLSF/)).toBeNull();
    expect(screen.queryByText(/Standard AI/)).toBeNull();
    expect(screen.queryByText(/第一轮作品/)).toBeNull();

    const user = userEvent.setup();
    await user.click(screen.getByText("表达非常清楚。"));
    await user.click(screen.getByText("联系清楚且有说服力。"));
    await user.click(screen.getByText("构思有明显的新意。"));
    await user.click(screen.getByRole("button", { name: "提交这件评价 / Submit" }));

    await waitFor(() => expect(submittedBody).not.toBeNull());
    expect((submittedBody as any).scores).toEqual({
      cultural_clarity: 5,
      cultural_translation: 5,
      design_originality: 5,
    });
  });
});
