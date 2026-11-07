import React from "react";
import { ApiError, api, errorMessage } from "../api";
import type { PeerAssignment, PeerPayload, StudentState, RationaleFields} from "../types";
import { BrandMark, ErrorNotice, Spinner } from "../components/common";
import { StageSchedule } from "../components/StageSchedule";

const DIMENSIONS = [
  { key: "clarity", label: "文化信息表达是否清楚？", en: "Cultural information clarity" },
  { key: "evidence_link", label: "文物知识与设计选择的联系是否容易理解？", en: "Evidence-to-design link" },
  { key: "attraction", label: "作品整体设计吸引力如何？", en: "Overall design appeal" },
];

type Draft = { scores: Record<string, number>; comment: string };

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

export default function PeerAssessmentPage({
  state,
  onState,
}: {
  state: StudentState;
  onState: (state: StudentState) => void;
}) {
  const [payload, setPayload] = React.useState<PeerPayload | null>(null);
  const [drafts, setDrafts] = React.useState<Record<string, Draft>>({});
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [error, setError] = React.useState<{ message: string; requestId?: string } | null>(null);

  const load = React.useCallback(async (showSpinner = true) => {
    if (showSpinner) setLoading(true);
    setError(null);
    try {
      const data = await api<PeerPayload>("/api/student/peer-assessment");
      setPayload(data);
      const next: Record<string, Draft> = {};
      for (const item of data.assignments) {
        next[item.assignment_id] = {
          scores: { ...item.scores },
          comment: item.comment || "",
        };
      }
      setDrafts(next);
    } catch (err) {
      setError({
        message: errorMessage(err),
        requestId: err instanceof ApiError ? err.requestId : undefined,
      });
    } finally {
      if (showSpinner) setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void load();
  }, [load]);

  React.useEffect(() => {
    if (!payload?.waiting) return;
    const timer = window.setInterval(() => {
      void load(false);
    }, 8000);
    return () => window.clearInterval(timer);
  }, [payload?.waiting, load]);

  function setScore(assignmentId: string, key: string, value: number) {
    setDrafts((current) => ({
      ...current,
      [assignmentId]: {
        ...current[assignmentId],
        scores: { ...(current[assignmentId]?.scores || {}), [key]: value },
      },
    }));
  }

  function setComment(assignmentId: string, value: string) {
    setDrafts((current) => ({
      ...current,
      [assignmentId]: {
        ...current[assignmentId],
        comment: value,
      },
    }));
  }

  async function submit(item: PeerAssignment) {
    const draft = drafts[item.assignment_id];
    if (!draft || DIMENSIONS.some((dim) => !draft.scores[dim.key])) {
      setError({ message: "请先完成三项评分再提交。 / Please rate all three dimensions." });
      return;
    }
    setBusy(item.assignment_id);
    setError(null);
    try {
      const data = await api<PeerPayload & { rating: unknown }>(
        `/api/student/peer-assessment/${item.assignment_id}`,
        { method: "POST", body: { scores: draft.scores, comment: draft.comment } },
      );
      setPayload(data);
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
      const result = await api<{ state: StudentState }>("/api/student/peer-assessment/complete", {
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
        <main className="centered-panel"><Spinner label="正在加载同伴互评… / Loading peer assessment…" /></main>
      </div>
    );
  }

  const waiting = Boolean(payload?.waiting || (payload?.gate && payload.gate.status !== "open"));
  const assignments = payload?.assignments || [];
  const submitted = payload?.submitted || 0;
  const total = payload?.total || 0;
  const ready = total === 0 || submitted >= total;

  if (waiting) {
    const gate = payload?.gate;
    return (
      <div className="app-shell">
        <header className="topbar">
          <BrandMark />
          <div className="topbar-separator" />
          <div className="stage-heading">
            <div>同伴互评 / Peer Assessment</div>
            <div className="en">Waiting for the class</div>
          </div>
          <div className="topbar-spacer" />
          <span className="step-badge">第 {state.step} 步 / Step {state.step} of 6</span>
        </header>
        <main className="peer-layout">
          <section className="peer-main">
            <div className="panel peer-intro">
              <div className="eyebrow">自动闸门 / Automatic class gate</div>
              <h1>等待全班完成第二次创作</h1>
              <p className="muted">
                互评会在本班所有已进入的同学完成第二次创作后自动开放。请保持页面打开，不需要手动刷新。
              </p>
              <div className="peer-gate-stats">
                <div>
                  <strong>{gate?.entered ?? 0}</strong>
                  <span>已进入 / entered</span>
                </div>
                <div>
                  <strong>{gate?.t2_ended ?? 0}</strong>
                  <span>第二次创作已结束 / second design ended</span>
                </div>
                <div>
                  <strong>{gate?.valid_work_count ?? 0}</strong>
                  <span>有效作品 / valid works</span>
                </div>
              </div>
              <div className="notice notice-info">
                {gate?.message ||
                  "系统会自动检测本班第二次创作完成情况；全班完成后，匿名作品会自动出现。"}
              </div>
              <p className="tiny muted">
                如果你已完成第二次创作但长时间停留在本页，请举手联系现场研究者；不要关闭页面或更换账号。
              </p>
            </div>
            {error ? <ErrorNotice message={error.message} requestId={error.requestId} /> : null}
          </section>
          <aside className="peer-sidebar">
            <StageSchedule currentStep={state.step} />
            <div className="side-card">
              <div className="side-card-icon">◎</div>
              <div>
                <strong>为什么会等待？</strong>
                <p className="small muted">
                  只有本班所有已进入的同学都结束第二次创作，互评批次才会一次生成并冻结，避免提前开放造成作品遗漏。
                </p>
              </div>
            </div>
          </aside>
        </main>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <BrandMark />
        <div className="topbar-separator" />
        <div className="stage-heading">
          <div>同伴互评 / Peer Assessment</div>
          <div className="en">Blind review of works</div>
        </div>
        <div className="topbar-spacer" />
        <span className="step-badge">第 {state.step} 步 / Step {state.step} of 6</span>
      </header>

      <main className="peer-layout">
        <section className="peer-main">
          <div className="panel peer-intro">
            <div className="eyebrow">研究评价 / Research assessment</div>
            <h1>请评价分配给你的匿名作品</h1>
            {payload?.deployment_mode === "beta" ? <p className="notice notice-info">班级0支持陆续体验。这里展示你首次进入互评时可用的作品；没有其他作品时可以直接继续。</p> : null}
            <p className="muted">
              你将看到若干件同班同学的第二次创作作品。作品以匿名编号显示，不显示作者或他人评分。
              每件作品请按三个维度独立评分；你的评分不会显示给作品作者。
            </p>
            <div className="peer-progress">
              <strong>{submitted} / {total}</strong>
              <span>已完成 / submitted</span>
            </div>
            <p className="tiny muted">
              这些评分是同伴评价，不是文物史实专家判断；文化准确性由研究者另行评审。
            </p>
          </div>

          {total === 0 ? (
            <div className="notice notice-info">
              当前没有可分配的同伴作品（可能作品尚未提交或班级作品不足）。你可以继续进入作品广场。
            </div>
          ) : null}

          {assignments.map((item) => {
            const draft = drafts[item.assignment_id] || { scores: {}, comment: "" };
            const isSubmitted = item.status === "submitted";
            return (
              <PeerImpressionWrap assignmentId={item.assignment_id} key={item.assignment_id}>
              <article className="panel peer-card">
                <div className="peer-card-head">
                  <div>
                    <div className="eyebrow">{item.work_code}</div>
                    <h2>{item.product_name || "未命名作品"}</h2>
                    <p className="small muted">{item.product_category || "文创产品"}</p>
                  </div>
                  <span className={`status-pill ${isSubmitted ? "ok" : ""}`}>
                    {isSubmitted ? "已提交" : "待评价"}
                  </span>
                </div>
                <div className="peer-card-body">
                  {item.image_url ? (
                    <img className="peer-work-image" src={item.image_url} alt={`作品 ${item.work_code}`} />
                  ) : (
                    <div className="peer-work-image placeholder">作品图片暂无</div>
                  )}
                  <div className="peer-statement">
                    <strong>作品说明</strong>
                    <p>{statementText(item)}</p>
                  </div>
                </div>

                <div className="peer-ratings">
                  {DIMENSIONS.map((dim) => (
                    <div className="peer-rating-row" key={dim.key}>
                      <div>
                        <strong>{dim.label}</strong>
                        <span className="en"> {dim.en}</span>
                      </div>
                      <div className="likert-row compact">
                        {[1, 2, 3, 4, 5].map((value) => (
                          <label key={value} className="likert-item">
                            <input
                              type="radio"
                              name={`${item.assignment_id}-${dim.key}`}
                              checked={draft.scores[dim.key] === value}
                              disabled={isSubmitted || busy === item.assignment_id}
                              onChange={() => setScore(item.assignment_id, dim.key, value)}
                            />
                            <span className="likert-number">{value}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                  ))}
                  <label className="field-label">
                    简短意见（可选） <span className="en">Optional comment</span>
                    <textarea
                      value={draft.comment}
                      onChange={(event) => setComment(item.assignment_id, event.target.value)}
                      disabled={isSubmitted || busy === item.assignment_id}
                      rows={2}
                      maxLength={1000}
                      placeholder="可以写一条具体、尊重作者的建议…"
                    />
                  </label>
                  {!isSubmitted ? (
                    <button
                      type="button"
                      className="button button-primary"
                      onClick={() => void submit(item)}
                      disabled={busy === item.assignment_id}
                    >
                      {busy === item.assignment_id ? "提交中…" : "提交这件评价 / Submit"}
                    </button>
                  ) : null}
                </div>
              </article>
              </PeerImpressionWrap>
            );
          })}

          {error ? <ErrorNotice message={error.message} requestId={error.requestId} onRetry={() => void load()} /> : null}

          <button
            type="button"
            className="button button-primary button-wide"
            onClick={() => void complete()}
            disabled={!ready || busy === "complete"}
          >
            {busy === "complete"
              ? "正在继续…"
              : ready
                ? "完成互评，进入作品广场 / Continue"
                : "请先完成所有分配作品 / Complete all assigned works"}
          </button>
        </section>
        <aside className="peer-sidebar">
          <StageSchedule currentStep={state.step} />
          <div className="side-card">
            <div className="side-card-icon">◎</div>
            <div>
              <strong>盲评说明</strong>
              <p className="small muted">
                作品编号由系统分配；你的评分与评论不会向作者显示。请独立判断，不根据熟悉程度评分。
              </p>
            </div>
          </div>
        </aside>
      </main>
    </div>
  );
}


function usePeerImpression(assignmentId: string) {
  const ref = React.useRef<HTMLDivElement | null>(null);
  const total = React.useRef(0);
  const visibleAt = React.useRef<number | null>(null);
  const initialSent = React.useRef(false);

  React.useEffect(() => {
    const element = ref.current;
    if (!element || typeof IntersectionObserver === "undefined") return;

    function send(viewedMs: number) {
      void fetch(`/api/student/peer-assessment/${assignmentId}/impression`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ viewed_ms: Math.max(0, Math.round(viewedMs)) }),
        keepalive: true,
      }).catch(() => {
        // Exposure logging must never block the peer rating flow.
      });
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const now = Date.now();
          if (entry.isIntersecting && entry.intersectionRatio >= 0.5) {
            if (visibleAt.current === null) {
              visibleAt.current = now;
              if (!initialSent.current) {
                initialSent.current = true;
                send(0);
              }
            }
          } else if (visibleAt.current !== null) {
            total.current += now - visibleAt.current;
            visibleAt.current = null;
            send(total.current);
          }
        }
      },
      { threshold: [0, 0.5, 1] },
    );
    observer.observe(element);
    return () => {
      observer.disconnect();
      if (visibleAt.current !== null) {
        total.current += Date.now() - visibleAt.current;
        visibleAt.current = null;
        send(total.current);
      }
    };
  }, [assignmentId]);

  return ref;
}

function PeerImpressionWrap({
  assignmentId,
  children,
}: {
  assignmentId: string;
  children: React.ReactNode;
}) {
  const ref = usePeerImpression(assignmentId);
  return (
    <div className="peer-impression-wrap" ref={ref}>
      {children}
    </div>
  );
}
