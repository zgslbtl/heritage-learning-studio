import React from "react";
import { ApiError, api, errorMessage } from "../api";
import { BrandMark, ErrorNotice, Spinner } from "../components/common";
import AdminLogin from "../components/AdminLogin";
import AdminOverview, { OverviewData } from "../components/AdminOverview";
import AdminContent from "../components/AdminContent";
import AdminReadiness from "../components/AdminReadiness";
import ParticipantDetail from "../components/ParticipantDetail";

type Tab = "overview" | "content" | "readiness";

export default function AdminApp() {
  const [authenticated, setAuthenticated] = React.useState<boolean | null>(null);
  const [data, setData] = React.useState<OverviewData | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<{ message: string; requestId?: string } | null>(null);
  const [tab, setTab] = React.useState<Tab>("overview");
  const [selectedParticipant, setSelectedParticipant] = React.useState<string | null>(null);
  const [activating, setActivating] = React.useState(false);
  const [activateError, setActivateError] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const overview = await api<OverviewData>("/api/admin/overview");
      setData(overview);
      setAuthenticated(true);
      setError(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setAuthenticated(false);
        setData(null);
      } else {
        setError({
          message: errorMessage(err),
          requestId: err instanceof ApiError ? err.requestId : undefined,
        });
        setAuthenticated(true);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void load();
  }, [load]);

  async function logout() {
    try {
      await api("/api/admin/logout", { method: "POST" });
    } finally {
      setAuthenticated(false);
      setData(null);
    }
  }

  async function activate() {
    setActivating(true);
    setActivateError(null);
    try {
      await api("/api/admin/protocol/activate", { method: "POST" });
      await load();
    } catch (err) {
      setActivateError(errorMessage(err));
    } finally {
      setActivating(false);
    }
  }

  if (authenticated === null || (loading && authenticated)) {
    return (
      <div className="app-shell admin-shell">
        <header className="topbar">
          <BrandMark />
        </header>
        <main className="centered-panel">
          <Spinner label="正在验证研究者身份…" />
        </main>
      </div>
    );
  }

  if (!authenticated) {
    return <AdminLogin onLogin={() => void load()} />;
  }

  if (error && !data) {
    return (
      <div className="app-shell admin-shell">
        <header className="topbar">
          <BrandMark />
        </header>
        <main className="centered-panel">
          <ErrorNotice
            message={error.message}
            requestId={error.requestId}
            onRetry={() => void load()}
          />
        </main>
      </div>
    );
  }

  return (
    <div className="app-shell admin-shell">
      <header className="topbar admin-topbar">
        <BrandMark compact />
        <div className="topbar-separator" />
        <span className="admin-badge">研究者后台 / Researcher Console</span>
        <nav className="admin-nav">
          <button
            type="button"
            className={tab === "overview" ? "active" : ""}
            onClick={() => {
              setTab("overview");
              setSelectedParticipant(null);
            }}
          >
            总览
          </button>
          <button
            type="button"
            className={tab === "content" ? "active" : ""}
            onClick={() => {
              setTab("content");
              setSelectedParticipant(null);
            }}
          >
            研究材料
          </button>
          <button
            type="button"
            className={tab === "readiness" ? "active" : ""}
            onClick={() => {
              setTab("readiness");
              setSelectedParticipant(null);
            }}
          >
            准备检查
          </button>
        </nav>
        <div className="topbar-spacer" />
        <a className="subtle-link" href="/">
          学生入口
        </a>
        <button type="button" className="text-button" onClick={() => void logout()}>
          退出登录
        </button>
      </header>

      {error ? <div className="admin-global-error"><ErrorNotice message={error.message} /></div> : null}
      {selectedParticipant ? (
        <main className="admin-main narrow">
          <ParticipantDetail
            participantId={selectedParticipant}
            onBack={() => setSelectedParticipant(null)}
          />
        </main>
      ) : (
        <main className="admin-main">
          {tab === "overview" && data ? (
            <AdminOverview
              data={data}
              onSelectParticipant={setSelectedParticipant}
              onRefresh={() => void load()}
            />
          ) : null}
          {tab === "content" ? <AdminContent onChanged={() => void load()} /> : null}
          {tab === "readiness" && data ? (
            <AdminReadiness
              readiness={data.readiness}
              activating={activating}
              error={activateError}
              onActivate={() => void activate()}
            />
          ) : null}
        </main>
      )}
    </div>
  );
}
