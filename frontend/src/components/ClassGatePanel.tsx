import React from "react";
import { api, errorMessage } from "../api";
import type { ClassEntryLink, ClassPeerGate } from "../types";
import { ErrorNotice, Spinner } from "./common";

export default function ClassGatePanel({ refreshToken }: { refreshToken?: string }) {
  const [gates, setGates] = React.useState<ClassPeerGate[]>([]);
  const [links, setLinks] = React.useState<ClassEntryLink[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [selectedClass, setSelectedClass] = React.useState(1);
  const [label, setLabel] = React.useState("");
  const [copiedLink, setCopiedLink] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  const load = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [gateData, linkData] = await Promise.all([
        api<{ classes: ClassPeerGate[] }>("/api/admin/class-peer-gates"),
        api<{ links: ClassEntryLink[] }>("/api/admin/class-links"),
      ]);
      setGates(gateData.classes);
      setSelectedClass((current) => gateData.classes.some((gate) => gate.class_id === current) ? current : gateData.classes[0]?.class_id ?? 0);
      setLinks(linkData.links);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void load();
  }, [load, refreshToken]);

  async function createLink() {
    setBusy(true);
    setError(null);
    try {
      await api("/api/admin/class-links", {
        method: "POST",
        body: { class_id: selectedClass, label },
      });
      setLabel("");
      await load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function revokeLink(id: string) {
    setBusy(true);
    setError(null);
    try {
      await api(`/api/admin/class-links/${id}/revoke`, { method: "POST" });
      await load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function rotateLink(id: string) {
    setBusy(true);
    setError(null);
    try {
      await api(`/api/admin/class-links/${id}/rotate`, {
        method: "POST",
      });
      await load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function copyUrl(link: ClassEntryLink) {
    if (!link.url) return;
    try {
      await navigator.clipboard.writeText(link.url);
      setCopiedLink(link.id);
    } catch {
      // Clipboard may be blocked; the input is still selectable.
    }
  }

  if (loading && !gates.length) {
    return (
      <section className="admin-subsection">
        <h2>班级链接与自动互评闸门 / Class links & peer gates</h2>
        <Spinner label="加载班级闸门…" />
      </section>
    );
  }

  return (
    <section className="admin-subsection class-gate-panel">
      <div className="section-heading-row">
        <div>
          <h2>班级链接与自动互评闸门 / Class links & peer gates</h2>
          <p className="small muted">
            正式班全员就绪即开放；否则第10人开始第一轮后满60分钟且至少90%就绪时开放。班级0持续开放。
            <span className="en">Formal classes open when everyone is ready, or after 60 minutes from the tenth round-1 start with at least 90% ready. Class 0 remains continuous.</span>
          </p>
        </div>
        <button type="button" className="button button-small button-ghost" onClick={() => void load()}>
          刷新 / Refresh
        </button>
      </div>
      {error ? <ErrorNotice message={error} /> : null}

      <div className="class-gate-grid">
        {gates.map((gate) => (
          <article className="class-gate-card" key={gate.class_id}>
            <div className="class-gate-head">
              <div>
                <div className="eyebrow">Class {gate.class_id}</div>
                <h3>{gate.class_name}</h3>
              </div>
              <span className={`status-pill ${gate.status === "open" ? "ok" : "warn"}`}>
                {gate.status === "open" ? "互评已开放" : "收集中"}
              </span>
            </div>
            <div className="class-gate-counts">
              <div>
                <strong>{gate.active_count ?? gate.entered}</strong>
                <span>有效参与者 / Active</span>
              </div>
              <div>
                <strong>{gate.ready_count ?? 0}</strong>
                <span>就绪 / Ready · {gate.completion_percent ?? 0}%</span>
              </div>
              <div>
                <strong>{gate.valid_work_count}</strong>
                <span>有效作品（T1+T2）</span>
                <span className="tiny muted">
                  T1 {gate.t1_work_count ?? "—"} / T2 {gate.t2_work_count ?? "—"}
                </span>
              </div>
            </div>
            <p className="small muted">
              {gate.continuous_entry ? "内部测试：持续开放 / Continuous internal testing" : gate.status === "open"
                ? `已开放 / Open: ${gate.peer_opened_at ? new Date(gate.peer_opened_at).toLocaleString() : "—"} · ${gate.opening_reason || "历史批次 / Historical batch"}`
                : gate.timer_started_at
                  ? `倒计时 / Time remaining: ${Math.ceil((gate.remaining_seconds ?? 0) / 60)} min · 停止人数 / Stopped: ${gate.stopped_count ?? 0}`
                  : `等待第10人开始第一轮 / Waiting for 10 round-1 starts (${gate.t1_started_count ?? 0}/10) · 停止人数 / Stopped: ${gate.stopped_count ?? 0}`}
              <span className="en">{gate.status === "open" ? "The main review list is frozen; existing participants can continue." : "Ready means two valid works, post-test and survey submitted. Stopped participants are excluded."}</span>
            </p>
            {gate.batch_id ? (
              <p className="tiny muted">批次：{gate.batch_id.slice(0, 8)}…</p>
            ) : null}
            {gate.last_event ? (
              <p className="tiny muted">
                最近事件：{gate.last_event.event_type} ·{" "}
                {new Date(gate.last_event.created_at).toLocaleString()}
              </p>
            ) : null}
            <div className="class-link-state">
              {links.filter((link) => link.class_id === gate.class_id && link.active).length ? (
                <span className="status-pill ok">已有有效链接</span>
              ) : (
                <span className="status-pill">未生成链接</span>
              )}
            </div>
          </article>
        ))}
      </div>

      <div className="class-link-manager">
        <h3>班级专属链接 / Class entry links</h3>
        <p className="small muted">
          链接绑定班级；学生打开后班级锁定，不需要手动选择。各班级的有效链接会保留在下方，刷新或重新登录后仍可查看、复制。
          <span className="en">Saved links remain available here when you switch classes, refresh, or sign in again.</span>
        </p>
        <div className="class-link-form">
          <select
            value={selectedClass}
            onChange={(event) => setSelectedClass(Number(event.target.value))}
            aria-label="Class for link"
          >
            {gates.map((gate) => (
              <option key={gate.class_id} value={gate.class_id}>
                {gate.class_name}
              </option>
            ))}
          </select>
          <input
            value={label}
            onChange={(event) => setLabel(event.target.value)}
            placeholder="链接标签（可选，如 2026-11 Class 1）"
            maxLength={120}
            aria-label="Link label"
          />
          <button
            type="button"
            className="button button-primary button-small"
            onClick={() => void createLink()}
            disabled={busy}
          >
            生成链接 / Generate
          </button>
        </div>
        <div className="class-link-list">
          {links.map((link) => (
            <div className={`class-link-row ${link.active ? "" : "inactive"}`} key={link.id}>
              <div className="class-link-details">
                <strong>Class {link.class_id}</strong>
                <span className="small muted"> · {link.label || "未命名"}</span>
                <div className="tiny muted">
                  {link.active ? "有效" : "已撤销"} ·{" "}
                  {new Date(link.created_at).toLocaleString()}
                </div>
                {link.active && link.url ? (
                  <div className="class-link-copy">
                    <input
                      value={link.url}
                      readOnly
                      aria-label={`Class ${link.class_id} link ${link.id}`}
                      onFocus={(event) => event.currentTarget.select()}
                    />
                    <button
                      type="button"
                      className="button button-small"
                      aria-label={`复制班级 ${link.class_id} 链接 / Copy Class ${link.class_id} link`}
                      onClick={() => void copyUrl(link)}
                    >
                      {copiedLink === link.id ? "已复制 / Copied" : "复制 / Copy"}
                    </button>
                  </div>
                ) : link.active ? (
                  <p className="tiny muted">旧版链接无法再次显示，请点击重新生成。<span className="en">Regenerate this older link to save it here.</span></p>
                ) : null}
              </div>
              <div className="button-row">
                {link.active ? (
                  <>
                    <button
                      type="button"
                      className="button button-small"
                      onClick={() => void rotateLink(link.id)}
                      disabled={busy}
                    >
                      重新生成 / Regenerate
                    </button>
                    <button
                      type="button"
                      className="text-button danger"
                      onClick={() => void revokeLink(link.id)}
                      disabled={busy}
                    >
                      撤销 / Revoke
                    </button>
                  </>
                ) : null}
              </div>
            </div>
          ))}
          {!links.length ? <p className="small muted">还没有生成班级链接。</p> : null}
        </div>
      </div>
    </section>
  );
}
