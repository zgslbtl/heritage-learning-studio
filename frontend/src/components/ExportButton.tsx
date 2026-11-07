import React from "react";
import { api, errorMessage } from "../api";

type ExportState = { id?: string; status: string; download_url?: string | null; error_code?: string | null };

export default function ExportButton() {
  const [task, setTask] = React.useState<ExportState | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  React.useEffect(() => {
    if (!task?.id || !["queued", "running"].includes(task.status)) return;
    let cancelled = false;
    const timer = window.setInterval(async () => {
      try {
        const next = await api<ExportState>(`/api/admin/export-tasks/${task.id}`);
        if (cancelled) return;
        setTask(next);
        setError(next.status === "failed" ? "导出失败，请重试。" : next.error_code === "queue_dispatch_failed" ? "任务正在等待队列恢复，可稍后再查看。" : null);
      } catch (err) { if (!cancelled) setError(errorMessage(err)); }
    }, 3000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [task?.id, task?.status]);

  async function start() {
    setBusy(true); setError(null);
    try { setTask(await api<ExportState>("/api/admin/export-tasks", { method: "POST" })); }
    catch (err) { setError(errorMessage(err)); }
    finally { setBusy(false); }
  }
  const pending = task && ["queued", "running"].includes(task.status);
  return <div>
    {task?.download_url ? <a className="button button-primary" href={task.download_url}>下载数据 ZIP</a> :
      <button className="button button-primary" type="button" disabled={busy || Boolean(pending)} onClick={() => void start()}>
        {busy || pending ? "正在准备数据…" : "导出完整研究数据"}
      </button>}
    {task?.download_url ? <button type="button" className="button button-ghost button-small" onClick={() => void start()} disabled={busy}>重新导出</button> : null}
    {error ? <p className="tiny" role="alert">{error}</p> : null}
  </div>;
}
