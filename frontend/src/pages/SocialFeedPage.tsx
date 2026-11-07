import React from "react";
import { ApiError, api, errorMessage } from "../api";
import type { SocialWork, StudentState, RationaleFields} from "../types";
import { BrandMark, ErrorNotice, Spinner } from "../components/common";
import { StageSchedule } from "../components/StageSchedule";

function statementText(work: {
  rationale_fields?: RationaleFields;
  open_statement?: string;
  design_concept?: string;
}): string {
  const rationale = work.rationale_fields;
  if (rationale && (rationale.heritage_knowledge || rationale.cultural_translation || rationale.design_reason)) {
    return [rationale.heritage_knowledge, rationale.cultural_translation, rationale.design_reason]
      .filter(Boolean)
      .join(" ");
  }
  return work.open_statement || work.design_concept || "作者未填写说明。";
}

export default function SocialFeedPage({
  state,
  onState,
}: {
  state: StudentState;
  onState: (state: StudentState) => void;
}) {
  const [works, setWorks] = React.useState<SocialWork[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState<number | "complete" | null>(null);
  const [commentDrafts, setCommentDrafts] = React.useState<Record<number, string>>({});
  const [notice, setNotice] = React.useState<string | null>(null);
  const [error, setError] = React.useState<{ message: string; requestId?: string } | null>(null);
  const viewed = React.useRef(new Set<number>());

  const load = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api<{ works: SocialWork[]; count: number }>("/api/student/social-feed");
      setWorks(data.works);
      for (const work of data.works) {
        if (!viewed.current.has(work.work_id)) {
          viewed.current.add(work.work_id);
          void api(`/api/student/social/works/${work.work_id}/view`, { method: "POST" }).catch(() => undefined);
        }
      }
    } catch (err) {
      setError({
        message: errorMessage(err),
        requestId: err instanceof ApiError ? err.requestId : undefined,
      });
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void load();
  }, [load]);

  async function like(work: SocialWork) {
    if (work.is_own) return;
    setBusy(work.work_id);
    setError(null);
    try {
      const result = await api<{ work_id: number; liked: boolean }>(
        `/api/student/social/works/${work.work_id}/like`,
        { method: "POST" },
      );
      setWorks((current) =>
        current.map((item) =>
          item.work_id === result.work_id ? { ...item, liked_by_me: result.liked } : item,
        ),
      );
    } catch (err) {
      setError({ message: errorMessage(err) });
    } finally {
      setBusy(null);
    }
  }

  async function comment(work: SocialWork) {
    const content = (commentDrafts[work.work_id] || "").trim();
    if (!content || work.is_own) return;
    setBusy(work.work_id);
    setError(null);
    try {
      await api(`/api/student/social/works/${work.work_id}/comment`, {
        method: "POST",
        body: { content },
      });
      setCommentDrafts((current) => ({ ...current, [work.work_id]: "" }));
      setNotice("评论已提交。 / Comment posted.");
    } catch (err) {
      setError({ message: errorMessage(err) });
    } finally {
      setBusy(null);
    }
  }

  async function complete() {
    setBusy("complete");
    setError(null);
    try {
      const result = await api<{ state: StudentState }>("/api/student/social/complete", {
        method: "POST",
      });
      onState(result.state);
    } catch (err) {
      setError({ message: errorMessage(err) });
    } finally {
      setBusy(null);
    }
  }

  if (loading) {
    return (
      <div className="app-shell">
        <header className="topbar"><BrandMark /></header>
        <main className="centered-panel"><Spinner label="正在加载作品广场… / Loading work feed…" /></main>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <BrandMark />
        <div className="topbar-separator" />
        <div className="stage-heading">
          <div>作品广场 · 模拟 Instagram</div>
          <div className="en">Class Work Feed</div>
        </div>
        <div className="topbar-spacer" />
        <span className="step-badge">第 {state.step} 步 / Step {state.step} of 6</span>
      </header>

      <main className="social-layout">
        <section className="social-main">
          <div className="panel social-intro">
            <div className="eyebrow">模拟社交 / Simulated social feed</div>
            <h1>浏览本班同学的第二次创作作品</h1>
            <p className="muted">
              这是站内研究界面，不连接真实 Instagram，也不会公开发布作品。你可以自由浏览、给不同作品点赞或取消点赞，
              也可以发表评论；不要求每件都互动。为避免从众效应，页面不显示点赞总数或热度排名。
            </p>
            <p className="tiny muted">不能给自己的作品点赞或评论；所有互动会以匿名记录保存。</p>
          </div>

          {notice ? <div className="notice notice-success">{notice}</div> : null}
          {error ? <ErrorNotice message={error.message} requestId={error.requestId} onRetry={() => void load()} /> : null}

          <div className="social-grid">
            {works.map((work) => (
              <article className="social-card" key={work.work_id}>
                <div className="social-card-media">
                  {work.image_url ? (
                    <img src={work.image_url} alt={`作品 ${work.work_code}`} />
                  ) : (
                    <div className="social-image-placeholder">作品图片暂无</div>
                  )}
                </div>
                <div className="social-card-body">
                  <div className="social-card-meta">
                    <span className="eyebrow">{work.work_code}</span>
                    {work.is_own ? <span className="status-pill ok">我的作品</span> : null}
                  </div>
                  <h2>{work.product_name || "未命名作品"}</h2>
                  <p className="small muted">{work.product_category || "文创产品"}</p>
                  <p className="small social-statement">
                    {statementText(work)}
                  </p>
                  <div className="social-actions">
                    <button
                      type="button"
                      className={`button button-small ${work.liked_by_me ? "button-primary" : "button-ghost"}`}
                      onClick={() => void like(work)}
                      disabled={work.is_own || busy === work.work_id}
                    >
                      {work.liked_by_me ? "♥ 已赞" : "♡ 喜欢"}
                    </button>
                    <span className="tiny muted">{work.is_own ? "不能评价自己的作品" : "匿名互动"}</span>
                  </div>
                  {!work.is_own ? (
                    <div className="social-comment-box">
                      <textarea
                        value={commentDrafts[work.work_id] || ""}
                        onChange={(event) =>
                          setCommentDrafts((current) => ({
                            ...current,
                            [work.work_id]: event.target.value,
                          }))
                        }
                        rows={2}
                        maxLength={600}
                        placeholder="写一条简短评论…"
                      />
                      <button
                        type="button"
                        className="button button-small"
                        onClick={() => void comment(work)}
                        disabled={busy === work.work_id || !(commentDrafts[work.work_id] || "").trim()}
                      >
                        发表评论
                      </button>
                    </div>
                  ) : null}
                </div>
              </article>
            ))}
          </div>

          {!works.length ? (
            <div className="notice notice-info">当前还没有可浏览的第二次创作作品。</div>
          ) : null}

          <button
            type="button"
            className="button button-primary button-wide"
            onClick={() => void complete()}
            disabled={busy === "complete"}
          >
            {busy === "complete" ? "正在完成…" : "完成浏览，结束工作坊 / Finish"}
          </button>
        </section>
        <aside className="social-sidebar">
          <StageSchedule currentStep={state.step} />
          <div className="side-card">
            <div className="side-card-icon">◎</div>
            <div>
              <strong>研究说明</strong>
              <p className="small muted">
                点赞和评论只用于探索性分析，不等同于真实公众偏好或知识掌握；页面不显示热度。
              </p>
            </div>
          </div>
        </aside>
      </main>
    </div>
  );
}
