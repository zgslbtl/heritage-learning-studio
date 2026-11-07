import React from "react";
import type { Readiness } from "../types";
import { ErrorNotice } from "./common";

export default function AdminReadiness({
  readiness,
  activating,
  error,
  onActivate,
}: {
  readiness: Readiness;
  activating: boolean;
  error: string | null;
  onActivate: () => void;
}) {
  return (
    <div className="admin-content">
      <div className="admin-section-heading">
        <div>
          <div className="eyebrow">研究准备 / Study readiness</div>
          <h1>协议冻结与准备检查</h1>
        </div>
        <span className={`status-pill ${readiness.ready_for_students ? "ok" : "warn"}`}>
          {readiness.ready_for_students ? "可供学生使用" : "尚未准备好"}
        </span>
      </div>
      <p className="muted">
        正式收集数据前，必须配置两套经审核的文物证据包、K0–K3 与体验问卷、以及真实 AI
        模型。激活后协议版本将冻结；已有学生研究记录时，旧协议保留可读，新测评版本通过
        `import-formal-v2` 新建协议，不覆盖旧数据。
      </p>
      {readiness.demo_present ? (
        <div className="notice notice-warning">
          当前存在演示占位内容。演示内容仅用于工程测试，不能作为正式研究材料。
        </div>
      ) : null}
      {error ? <ErrorNotice message={error} /> : null}

      <div className="readiness-grid">
        {readiness.checks.map((check) => (
          <div key={check.key} className={`readiness-item ${check.ok ? "ok" : "fail"}`}>
            <span className="readiness-icon">{check.ok ? "✓" : "!"}</span>
            <div>
              <strong>{check.label}</strong>
              <p className="small muted">{check.detail}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="admin-subsection">
        <h2>冻结新协议 / Freeze a protocol</h2>
        {readiness.active_protocol ? (
          <div className="protocol-summary">
            <div>
              <span className="label">当前协议</span>
              <code>{readiness.active_protocol.id}</code>
            </div>
            <div>
              <span className="label">激活时间</span>
              <strong>
                {readiness.active_protocol.activated_at
                  ? new Date(readiness.active_protocol.activated_at).toLocaleString()
                  : "—"}
              </strong>
            </div>
            <div>
              <span className="label">内容状态</span>
              <strong>{readiness.active_protocol.is_demo ? "DEMO" : "Research content"}</strong>
            </div>
            <div>
              <span className="label">测评版本</span>
              <strong>{readiness.active_protocol.assessment_version || "assessment_v1"}</strong>
            </div>
          </div>
        ) : (
          <p className="muted">尚未激活协议。学生进入时会看到“研究尚未开放”。</p>
        )}
        <button
          type="button"
          className="button button-primary"
          onClick={onActivate}
          disabled={!readiness.ready_to_activate || activating || readiness.run_count > 0}
        >
          {activating ? "正在激活…" : "激活当前内容为新协议 / Activate protocol"}
        </button>
        {readiness.run_count > 0 ? (
          <p className="tiny warning-text">
            已有 {readiness.run_count} 条研究记录；协议已锁定，不能再次激活。
          </p>
        ) : null}
      </div>

      <div className="admin-subsection">
        <h2>研究伦理与正式运行前提</h2>
        <ul className="doc-list">
          <li>两套 Evidence Pack 与评分标准完成学术审核。</li>
          <li>研究参与同意、数据保留期限与删除流程得到伦理审批。</li>
          <li>外部 AI 服务的数据处理、跨境传输与费用安排经过确认。</li>
          <li>完成试点、备份恢复演练与独立安全检查。</li>
        </ul>
        <p className="tiny muted">
          本 MVP 不包含同意流程、自动评分或自动删除。正式运行前必须由研究者补齐。
        </p>
      </div>
    </div>
  );
}
