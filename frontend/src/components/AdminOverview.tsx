import React from "react";
import type { Readiness } from "../types";
import { ErrorNotice } from "./common";
import ClassGatePanel from "./ClassGatePanel";
import ExportButton from "./ExportButton";

export interface ParticipantRow {
  participant_id: string;
  class_id: number;
  class_name: string;
  group: string;
  email: string | null;
  code_last4: string | null;
  run_id: string | null;
  stage: string;
  stage_label: string;
  step: number;
  last_activity_at: string | null;
  completed_at: string | null;
  completed: boolean;
}

export interface OverviewData {
  readiness: Readiness;
  protocol: Record<string, unknown> | null;
  participants: ParticipantRow[];
  counts: {
    participants: number;
    started: number;
    completed: number;
    by_stage: Record<string, number>;
    by_group: Record<string, number>;
  };
  server_time: string;
}

export default function AdminOverview({
  data,
  onSelectParticipant,
  onRefresh,
}: {
  data: OverviewData;
  onSelectParticipant: (id: string) => void;
  onRefresh: () => void;
}) {
  const [classFilter, setClassFilter] = React.useState("all");
  const [groupFilter, setGroupFilter] = React.useState("all");
  const [stageFilter, setStageFilter] = React.useState("all");
  const [query, setQuery] = React.useState("");

  const rows = data.participants.filter((row) => {
    if (classFilter !== "all" && String(row.class_id) !== classFilter) return false;
    if (groupFilter !== "all" && row.group !== groupFilter) return false;
    if (stageFilter !== "all" && row.stage !== stageFilter) return false;
    if (query) {
      const haystack = `${row.participant_id} ${row.email || ""} ${row.code_last4 || ""} ${row.class_name}`.toLowerCase();
      if (!haystack.includes(query.toLowerCase())) return false;
    }
    return true;
  });

  return (
    <div className="admin-content">
      <div className="admin-section-heading">
        <div>
          <div className="eyebrow">研究总览 / Research overview</div>
          <h1>实验进度</h1>
        </div>
        <div className="button-row">
          <button type="button" className="button button-ghost" onClick={onRefresh}>
            刷新 / Refresh
          </button>
          <ExportButton />
        </div>
      </div>

      {data.readiness.deployment_mode === "beta" ? <div className="notice notice-info">班级0内部测试 · 数据与正式班级分开保存，支持用户陆续体验。</div> : null}
      {!data.readiness.ready_for_students ? (
        <div className="notice notice-warning">
          研究尚未准备完毕。请到“准备检查”完成配置并激活协议后再开放学生入口。
        </div>
      ) : null}

      <div className="stat-grid">
        <Stat label="参与者" value={data.counts.participants} />
        <Stat label="已进入实验" value={data.counts.started} />
        <Stat label="已完成" value={data.counts.completed} />
        <Stat label="图片并发上限" value={data.readiness.active_protocol ? "服务端配置" : "—"} />
      </div>

      <ClassGatePanel refreshToken={data.server_time} />

      <div className="admin-split">
        <section className="admin-subsection">
          <h2>分组分布 / Group balance</h2>
          <div className="mini-bar-list">
            {["G1", "G2", "G3", "G4"].map((group) => {
              const value = data.counts.by_group[group] || 0;
              const width = data.counts.participants ? (value / data.counts.participants) * 100 : 0;
              return (
                <div key={group} className="mini-bar-row">
                  <span>{group}</span>
                  <div className="mini-bar">
                    <span style={{ width: `${width}%` }} />
                  </div>
                  <strong>{value}</strong>
                </div>
              );
            })}
          </div>
        </section>
        <section className="admin-subsection">
          <h2>阶段分布 / Stage distribution</h2>
          <div className="stage-count-list">
            {Object.entries(data.counts.by_stage).map(([stage, count]) => (
              <div key={stage}>
                <span>{stage}</span>
                <strong>{count}</strong>
              </div>
            ))}
          </div>
        </section>
      </div>

      <div className="table-toolbar">
        <h2>参与者列表</h2>
        <div className="filters">
          <input
            placeholder="搜索邮箱、编号或班级"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <select value={classFilter} onChange={(event) => setClassFilter(event.target.value)}>
            <option value="all">全部班级</option>
            {Array.from(new Set(data.participants.map((row) => row.class_id)))
              .sort((a, b) => a - b)
              .map((id) => (
                <option key={id} value={String(id)}>
                  {id === 0 ? "班级 0（内部测试）" : `班级 ${id}`}
                </option>
              ))}
          </select>
          <select value={groupFilter} onChange={(event) => setGroupFilter(event.target.value)}>
            <option value="all">全部分组</option>
            {["G1", "G2", "G3", "G4"].map((group) => (
              <option key={group} value={group}>
                {group}
              </option>
            ))}
          </select>
          <select value={stageFilter} onChange={(event) => setStageFilter(event.target.value)}>
            <option value="all">全部阶段</option>
            {Array.from(new Set(data.participants.map((row) => row.stage))).map((stage) => (
              <option key={stage} value={stage}>
                {stage}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>参与者</th>
              <th>班级</th>
              <th>分组</th>
              <th>阶段</th>
              <th>最近活动</th>
              <th>完成</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.participant_id}>
                <td>
                  <code>{row.participant_id.slice(0, 8).toUpperCase()}</code>
                  <span className="tiny muted">
                    {row.email ? ` · ${row.email}` : row.code_last4 ? ` · ••••${row.code_last4}` : ""}
                  </span>
                </td>
                <td>{row.class_name}</td>
                <td>
                  <span className="group-badge small">{row.group}</span>
                </td>
                <td>{row.stage_label}</td>
                <td>{row.last_activity_at ? new Date(row.last_activity_at).toLocaleString() : "—"}</td>
                <td>
                  {row.completed ? (
                    <span className="status-pill ok">完成</span>
                  ) : (
                    <span className="status-pill">进行中</span>
                  )}
                </td>
                <td>
                  <button
                    type="button"
                    className="text-button"
                    onClick={() => onSelectParticipant(row.participant_id)}
                  >
                    查看 / View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length ? <ErrorNotice message="没有符合筛选条件的参与者。" /> : null}
      </div>
      <p className="tiny muted">
        参与者以服务器随机 UUID 标识；邮箱仅供研究团队内部核对，不写入研究分析导出。
        班级 0 仅用于内部测试，正式上线时应使用班级 1–4。
      </p>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="stat-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
