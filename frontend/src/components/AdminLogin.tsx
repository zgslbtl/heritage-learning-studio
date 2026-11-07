import React from "react";
import { api, errorMessage, ApiError } from "../api";
import { BrandMark, ErrorNotice } from "./common";

export default function AdminLogin({ onLogin }: { onLogin: () => void }) {
  const [password, setPassword] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<{ message: string; requestId?: string } | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api("/api/admin/login", { method: "POST", body: { password } });
      onLogin();
    } catch (err) {
      setError({
        message: errorMessage(err),
        requestId: err instanceof ApiError ? err.requestId : undefined,
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="app-shell admin-shell">
      <header className="topbar">
        <BrandMark />
        <div className="topbar-spacer" />
        <a className="subtle-link" href="/">
          学生入口 / Student entry
        </a>
      </header>
      <main className="admin-login-layout">
        <div className="admin-login-card panel">
          <div className="eyebrow">研究者后台 / Researcher Console</div>
          <h1>登录</h1>
          <p className="muted">
            仅用于授权研究者查看实验进度、管理协议内容与导出研究数据。
          </p>
          <form onSubmit={submit} className="entry-form">
            <label>
              研究者密码 / Researcher password
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                required
              />
            </label>
            <button className="button button-primary" type="submit" disabled={submitting}>
              {submitting ? "正在验证…" : "登录 / Sign in"}
            </button>
          </form>
          {error ? <ErrorNotice message={error.message} requestId={error.requestId} /> : null}
          <p className="tiny muted">
            连续失败会触发临时限流。密码只保存在服务端环境变量中。
          </p>
        </div>
      </main>
    </div>
  );
}
