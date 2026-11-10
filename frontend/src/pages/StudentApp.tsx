import React from "react";
import { ApiError, api, errorMessage } from "../api";
import type { AssessmentKind, StudentState } from "../types";
import { Spinner, ErrorNotice, BrandMark } from "../components/common";
import EntryPage from "./EntryPage";
import AssessmentPage from "./AssessmentPage";
import ReadyPage from "./ReadyPage";
import Workbench from "./Workbench";
import CompletePage from "./CompletePage";
import TutorialPage from "./TutorialPage";
import PeerAssessmentPage from "./PeerAssessmentPage";
import SocialFeedPage from "./SocialFeedPage";

function assessmentKindFor(state: StudentState): AssessmentKind | null {
  return state.assessment_kind;
}

export default function App() {
  const [state, setState] = React.useState<StudentState | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [loadError, setLoadError] = React.useState<{ message: string; requestId?: string } | null>(
    null,
  );

  const loadState = React.useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const data = await api<StudentState>("/api/student/state");
      setState(data);
      setLoadError(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setState(null);
        setLoadError(null);
      } else if (!silent) {
        setLoadError({
          message: errorMessage(err),
          requestId: err instanceof ApiError ? err.requestId : undefined,
        });
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void loadState();
  }, [loadState]);

  React.useEffect(() => {
    if (!state) return;
    const timer = window.setInterval(() => {
      void loadState(true);
    }, 10000);
    return () => window.clearInterval(timer);
  }, [loadState, state]);

  React.useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
  }, [state?.stage]);

  if (loading) {
    return (
      <div className="app-shell">
        <header className="topbar">
          <BrandMark />
        </header>
        <main className="centered-panel">
          <Spinner label="正在恢复你的进度… / Restoring your progress…" />
        </main>
      </div>
    );
  }

  if (!state) {
    return (
      <>
        {loadError ? (
          <div className="global-error">
            <ErrorNotice
              message={loadError.message}
              requestId={loadError.requestId}
              onRetry={() => void loadState()}
            />
          </div>
        ) : null}
        <EntryPage onEnter={(next) => setState(next)} />
      </>
    );
  }

  if (state.stopped) {
    return <div className="app-shell"><header className="topbar"><BrandMark /></header>
      <main className="centered-panel"><section className="panel">
        <h1>任务已由管理员停止<span className="en">Your task has been stopped by the researcher</span></h1>
        <p>你的已保存作答和作品已保留。如需继续，请联系现场研究者。
          <span className="en">Your saved answers and works have been retained. Please contact the researcher if you need to continue.</span></p>
        <button className="button" onClick={() => void loadState()}>检查状态 / Check status</button>
      </section></main></div>;
  }

  const kind = assessmentKindFor(state);
  if (kind) {
    return (
      <AssessmentPage
        key={`${state.run_id}-${kind}`}
        state={state}
        kind={kind}
        onState={setState}
      />
    );
  }
  if (state.stage === "tutorial") {
    return <TutorialPage state={state} onState={setState} />;
  }
  if (state.stage === "t1_ready" || state.stage === "t2_ready") {
    return <ReadyPage key={state.stage} state={state} onState={setState} />;
  }
  if (state.stage === "t1_active" || state.stage === "t2_active") {
    return (
      <Workbench
        key={`${state.run_id}-${state.stage}`}
        state={state}
        onState={setState}
        onRefresh={loadState}
      />
    );
  }
  if (state.stage === "peer_assessment") {
    return <PeerAssessmentPage state={state} onState={setState} />;
  }
  if (state.stage === "social_feed") {
    return <SocialFeedPage state={state} onState={setState} />;
  }
  if (state.stage === "complete") {
    return <CompletePage state={state} />;
  }
  return (
    <div className="app-shell">
      <header className="topbar">
        <BrandMark />
      </header>
      <main className="centered-panel">
        <ErrorNotice message="当前阶段无法识别，请刷新页面。" onRetry={() => void loadState()} />
      </main>
    </div>
  );
}
