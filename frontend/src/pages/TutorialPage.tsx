import React from "react";
import { ApiError, api, errorMessage } from "../api";
import type { StudentState } from "../types";
import { BrandMark, ErrorNotice } from "../components/common";
import { StageSchedule } from "../components/StageSchedule";

export default function TutorialPage({
  state,
  onState,
}: {
  state: StudentState;
  onState: (state: StudentState) => void;
}) {
  const [starting, setStarting] = React.useState(false);
  const [error, setError] = React.useState<{ message: string; requestId?: string } | null>(null);

  async function begin() {
    setStarting(true);
    setError(null);
    try {
      const result = await api<{ state: StudentState }>("/api/student/tutorial/complete", {
        method: "POST",
      });
      onState(result.state);
    } catch (err) {
      setError({
        message: errorMessage(err),
        requestId: err instanceof ApiError ? err.requestId : undefined,
      });
    } finally {
      setStarting(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <BrandMark />
        <div className="topbar-separator" />
        <div className="stage-heading">
          <div>操作说明 / Tutorial</div>
          <div className="en">A short guide before you begin</div>
        </div>
        <div className="topbar-spacer" />
        <span className="step-badge">第 {state.step} 步 / Step {state.step} of 6</span>
      </header>

      <main className="ready-layout">
        <section className="ready-main panel">
          <div className="eyebrow">创作说明 / Creative guide</div>
          <h1>接下来你会完成两个文创设计任务</h1>
          <div className="en heading-en">Two creation tasks, one learning journey</div>
          <p className="lede">
            你将先围绕一件文物完成一次<strong>文创设计</strong>，再围绕另一件文物完成第二次设计。
            在阅读资料和使用 AI 的过程中，平台会记录你的操作与草稿，帮助你随时继续。
            <span className="en">
              You will first design a cultural product around one artifact, then a second design
              around another artifact. While you read and work with the AI, the platform records
              your actions and drafts so you can continue at any time.
            </span>
          </p>

          <div className="brief-grid">
            <div className="brief-card">
              <div className="brief-icon">◷</div>
              <strong>第一次创作约 24 分钟</strong>
              <p className="small muted">阅读资料、与 AI 讨论、完成产品设计与作品说明。<span className="en">Read the material, discuss with AI, then design and write your statement.</span></p>
            </div>
            <div className="brief-card">
              <div className="brief-icon">▧</div>
              <strong>第二次创作约 20 分钟</strong>
              <p className="small muted">另一件文物、AI 对话、开放式作品说明。<span className="en">A second artifact, AI dialogue and an open design statement.</span></p>
            </div>
            <div className="brief-card">
              <div className="brief-icon">✎</div>
              <strong>自动保存</strong>
              <p className="small muted">计时由服务端控制；断网或刷新不会暂停计时。<span className="en">Server-timed: refreshing or losing connection does not pause it.</span></p>
            </div>
          </div>

          <div className="notice notice-info">
            <div>
              <strong>工作台分三栏：</strong>左侧文物资料，中间 AI 对话，右侧你的文创设计。
              <span className="en">
                The workspace has three columns: artifact material on the left, AI chat in the
                middle, and your design on the right.
              </span>
            </div>
            <div className="small muted" style={{ marginTop: 6 }}>
              两轮创作都填写产品名称、类别/用途、目标受众、设计概念和三段作品说明，并生成 1 张概念图。
              图片生成失败也可以提交文字作品。
              <span className="en">
                In both rounds you complete the product name, category/use, audience, design
                concept and three-part rationale, and generate one concept image. If image
                generation fails you can still submit the written work.
              </span>
            </div>
          </div>

          <div className="notice notice-warning">
            <div>
              过程中会有几个简短问题，帮助我们了解你现在的想法。填写时先不使用 AI 和资料，
              按自己的理解继续即可。
              <span className="en">
                A few short questions along the way help us understand your current thinking.
                Answer from your own understanding, without using the AI or the material.
              </span>
            </div>
          </div>

          {error ? <ErrorNotice message={error.message} requestId={error.requestId} /> : null}
          <button
            type="button"
            className="button button-primary button-wide"
            onClick={() => void begin()}
            disabled={starting}
          >
            {starting ? "正在进入… / Starting…" : "我已了解，开始第一次创作 / Start"}
          </button>
          <p className="tiny muted text-center">
            点击后进入第一次创作的任务说明；计时从你点击“开始本轮”时开始。
            <span className="en">
              This opens the first design briefing; the timer starts when you click “Start Round”.
            </span>
          </p>
        </section>

        <div className="ready-sidebar">
          <StageSchedule currentStep={state.step} />
          <div className="side-card">
            <div className="side-card-icon">i</div>
            <div>
              <strong>匿名与数据 / Anonymity & data</strong>
              <p className="small muted">
                你的对话、作品、回答和操作记录会以匿名参与者编号保存，供研究分析使用。
                <span className="en">
                  Your dialogue, designs, answers and activity logs are stored under an anonymous
                  participant ID and used for research analysis.
                </span>
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
