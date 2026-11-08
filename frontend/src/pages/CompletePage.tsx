import React from "react";
import { api } from "../api";
import type { StudentState } from "../types";
import { BrandMark, clearLocalStudyData } from "../components/common";

export default function CompletePage({ state }: { state: StudentState }) {
  const [loggingOut, setLoggingOut] = React.useState(false);

  async function logout() {
    setLoggingOut(true);
    try {
      await api("/api/auth/logout", { method: "POST" });
    } finally {
      clearLocalStudyData();
      window.location.href = "/";
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <BrandMark />
        <div className="topbar-spacer" />
        <span className="step-badge">完成 / Complete</span>
      </header>
      <main className="complete-layout">
        <div className="complete-mark">✓</div>
        <h1>今天的创作已完成</h1>
        <div className="en heading-en">Your designs are complete</div>
        <p className="lede">
          感谢你参与本次文化遗产学习与创作工作坊。你的对话、文创设计、概念图、回答和问卷已经保存，
          研究者将仅以匿名编号进行整体分析。
        </p>
        <p className="muted">
          Thank you. Your dialogue, product designs, concept images, responses and survey
          have been recorded under an anonymous identifier.
        </p>
        <div className="complete-meta">
          <span>{state.participant.class_name}</span>
          <span>匿名编号 / Anonymous ID</span>
          <code>{state.participant.id.slice(0, 8).toUpperCase()}</code>
        </div>
        <button type="button" className="button" onClick={() => void logout()} disabled={loggingOut}>
          结束并退出 / Exit
        </button>
        <p className="tiny muted">现在可以安全关闭浏览器页面。/ You can now close this page safely.</p>
      </main>
    </div>
  );
}
