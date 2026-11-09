import React from "react";
import { ApiError, api, errorMessage } from "../api";
import type {
  PeerAssignment,
  PeerDimension,
  PeerPayload,
  PeerReviewScale,
  RationaleFields,
  StudentState,
} from "../types";
import { BrandMark, ErrorNotice, Spinner } from "../components/common";
import { StageSchedule } from "../components/StageSchedule";

const RATIONALE_SEGMENTS = [
  { key: "heritage_knowledge", label: "从文物中学到了什么", label_en: "What they learned from the artifact" },
  { key: "cultural_translation", label: "怎样把知识用到设计里", label_en: "How they used it in the design" },
  { key: "design_reason", label: "为什么这样设计", label_en: "Why they designed it this way" },
] as const;

const STRUCTURED_LABELS = [
  ["cultural_features", "文化特征 / Visual & cultural features"],
  ["historical_function", "历史功能与社会意义 / Historical function & meaning"],
  ["sources_evidence", "资料与证据 / Sources & evidence"],
  ["cultural_continuity", "文化延续 / Cultural continuity"],
  ["cultural_translation", "文化转译 / 再情境化 / Translation into a new context"],
  ["innovation_rationale", "创新与设计理由 / Innovation & rationale"],
] as const;

type Draft = { scores: Record<string, number>; comment: string };

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

  const review = payload?.review || null;
  const dimensions = review?.dimensions || [];

  async function submit(item: PeerAssignment) {
    const draft = drafts[item.assignment_id];
    if (!draft || !dimensions.length || dimensions.some((dim) => !draft.scores[dim.key])) {
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
              <h1>等待全班完成第二次创作<span className="en">Waiting for the class to finish the second design</span></h1>
              <p className="muted">
                互评会在本班所有已进入的同学完成第二次创作后自动开放。请保持页面打开，不需要手动刷新。
            <span className="en">
              Peer review opens automatically once everyone who joined the class has finished the
              second design. Keep this page open; no manual refresh is needed.
            </span>
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
                  <span>有效作品 / T1+T2 works</span>
                </div>
              </div>
              <div className="notice notice-info">
                {gate?.message ||
                  "系统会自动检测本班第二次创作完成情况；全班完成后，匿名作品会自动出现。"}
                <span className="en">Anonymous works will appear automatically once everyone who joined the class has finished the second design.</span>
              </div>
              <p className="tiny muted">
                如果你已完成第二次创作但长时间停留在本页，请举手联系现场研究者；不要关闭页面或更换账号。
                <span className="en">If you have finished the second design but remain on this page for a long time, raise your hand to contact the researcher; keep the page open and use the same account.</span>
              </p>
            </div>
            {error ? <ErrorNotice message={error.message} requestId={error.requestId} /> : null}
          </section>
          <aside className="peer-sidebar">
            <StageSchedule currentStep={state.step} />
            <div className="side-card">
              <div className="side-card-icon">◎</div>
              <div>
                <strong>为什么会等待？ / Why wait?</strong>
                <p className="small muted">
                  只有本班所有已进入的同学都结束第二次创作，互评批次才会一次生成并冻结，避免提前开放造成作品遗漏。
                  <span className="en">
                    The peer-review batch is generated and frozen only after everyone who joined the
                    class has finished the second design, so no work is left out.
                  </span>
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

      <main className="peer-layout peer-review-layout">
        <section className="peer-main">
          <div className="panel peer-intro">
            <div className="peer-intro-heading">
              <div>
                <div className="eyebrow">研究评价 / Research assessment</div>
                <h1>{review?.title || "看看其他同学的设计"}</h1>
                {review?.title_en ? <p className="instruction-en">{review.title_en}</p> : null}
              </div>
              <div className="peer-progress">
                <strong>{submitted} / {total}</strong>
                <span>已完成 / submitted</span>
              </div>
            </div>
            <div className="peer-intro-body">
              <div>
                {payload?.deployment_mode === "beta" ? (
                  <p className="notice notice-info">
                    班级0支持陆续体验。这里展示你首次进入互评时可用的作品；没有其他作品时可以直接继续。
                    <span className="en">Class 0 supports participants joining at different times. You see the works available when you first enter peer review; if no other works are available, you can continue directly.</span>
                  </p>
                ) : null}
                <p className="muted">
                  {review?.instructions ||
                    "请根据作品图片和作品说明评价。重点是你能否看懂作品想表达的文化内容，以及设计怎样从文物中获得启发。"}
                  {review?.instructions_en ? <span className="instruction-en">{review.instructions_en}</span> : null}
                </p>
              </div>
              {review?.principles?.length ? (
                <div className="notice notice-info peer-principles">
                  <strong>评分说明 / How to rate</strong>
                  <ul>
                    {review.principles.map((principle, index) => (
                      <li key={principle}>{principle}{review.principles_en?.[index] ? <span className="en">{review.principles_en[index]}</span> : null}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
            <p className="tiny muted">
              这些评分是同伴评价，不是文物史实专家判断；文化准确性由研究者另行评审。
              <span className="en">These are peer ratings, not expert judgments about historical facts. Researchers assess cultural accuracy separately.</span>
            </p>
          </div>

          {total === 0 ? (
            <div className="notice notice-info">
              当前没有可分配的同伴作品（可能作品尚未提交或班级作品不足）。你可以继续进入作品广场。
            </div>
          ) : null}

          {!dimensions.length ? (
            <div className="notice notice-warning">
              互评量表未加载。请刷新页面或联系现场研究者。
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
                      <div className="eyebrow">{item.work_code} · {item.round_no === 1 ? "T1" : item.round_no === 2 ? "T2" : "作品"}</div>
                      <h2>{item.product_name || "未命名作品 / Untitled work"}</h2>
                      <p className="small muted">{item.product_category || "文创产品 / Cultural product"}</p>
                    </div>
                    <span className={`status-pill ${isSubmitted ? "ok" : ""}`}>
                      {isSubmitted ? "已提交 / Submitted" : "待评价 / To review"}
                    </span>
                  </div>
                  <div className="peer-card-workspace">
                    <div className="peer-card-body">
                      <div className="peer-media-column">
                        {item.image_url ? (
                          <img
                            className="peer-work-image"
                            src={item.image_url}
                            alt={`作品 ${item.work_code}`}
                          />
                        ) : (
                          <div className="peer-work-image placeholder">作品图片暂无 / No image</div>
                        )}
                        {item.artifact_title ? (
                          <div className="peer-artifact">
                            <strong>{item.artifact_title}</strong>
                            {item.artifact_era || item.artifact_type ? (
                              <p className="tiny muted">
                                {[item.artifact_era, item.artifact_type]
                                  .filter(Boolean)
                                  .join(" · ")}
                              </p>
                            ) : null}
                            {item.artifact_introduction ? (
                              <p className="small muted">{item.artifact_introduction}</p>
                            ) : null}
                          </div>
                        ) : null}
                      </div>
                      <WorkStatement item={item} />
                    </div>

                    <div className="peer-ratings">
                      {dimensions.map((dimension) => (
                        <PeerRatingRow
                          key={dimension.key}
                          assignmentId={item.assignment_id}
                          dimension={dimension}
                          scale={review}
                          value={draft.scores[dimension.key]}
                          disabled={isSubmitted || busy === item.assignment_id}
                          onChange={(value) => setScore(item.assignment_id, dimension.key, value)}
                        />
                      ))}
                      <label className="field-label">
                        简短意见（可选） <span className="en">Optional comment</span>
                        <textarea
                          value={draft.comment}
                          onChange={(event) => setComment(item.assignment_id, event.target.value)}
                          disabled={isSubmitted || busy === item.assignment_id}
                          rows={2}
                          maxLength={1000}
                          placeholder={`${review?.comment_prompt || "可以写一条具体、尊重作者的建议…"} / ${review?.comment_prompt_en || "Write one specific, respectful suggestion…"}`}
                        />
                      </label>
                      {!isSubmitted ? (
                        <button
                          type="button"
                          className="button button-primary"
                          onClick={() => void submit(item)}
                          disabled={busy === item.assignment_id || !dimensions.length}
                        >
                          {busy === item.assignment_id ? "提交中… / Submitting…" : "提交这件评价 / Submit"}
                        </button>
                      ) : null}
                    </div>
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
              ? "正在继续… / Continuing…"
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
              <strong>盲评说明 / Anonymous peer review</strong>
              <p className="small muted">
                作品编号由系统分配；你的评分与评论不会向作者显示。请独立判断，不根据熟悉程度评分。
                <span className="en">
                  Work codes are assigned by the system; your ratings and comments are not shown to
                  the author. Judge independently and do not score by familiarity.
                </span>
              </p>
            </div>
          </div>
        </aside>
      </main>
    </div>
  );
}

function WorkStatement({ item }: { item: PeerAssignment }) {
  const rationale: Partial<RationaleFields> = item.rationale_fields || {};
  const hasRationale = RATIONALE_SEGMENTS.some((segment) =>
    String(rationale[segment.key] || "").trim(),
  );
  if (hasRationale) {
    return (
      <div className="peer-statement">
        <strong>作品说明 / Design statement</strong>
        <div className="peer-rationale">
          {RATIONALE_SEGMENTS.map((segment) => (
            <div key={segment.key}>
              <div className="peer-rationale-label">
                {segment.label}
                <span className="en">{segment.label_en}</span>
              </div>
              <p>{String(rationale[segment.key] || "").trim() || "（未填写 / Not provided）"}</p>
            </div>
          ))}
        </div>
      </div>
    );
  }
  const structured = item.structured_fields || {};
  const hasStructured = STRUCTURED_LABELS.some(([key]) =>
    String(structured[key] || "").trim(),
  );
  if (hasStructured) {
    return (
      <div className="peer-statement">
        <strong>作品说明（旧版六字段） / Design statement (legacy fields)</strong>
        <dl className="peer-structured">
          {STRUCTURED_LABELS.map(([key, label]) => (
            <React.Fragment key={key}>
              <dt>{label}</dt>
              <dd>{String(structured[key] || "").trim() || "（未填写 / Not provided）"}</dd>
            </React.Fragment>
          ))}
        </dl>
      </div>
    );
  }
  return (
    <div className="peer-statement">
      <strong>作品说明 / Design statement</strong>
      <p>{item.open_statement || item.design_concept || "作者未填写说明。 / No design statement provided."}</p>
    </div>
  );
}

function PeerRatingRow({
  assignmentId,
  dimension,
  scale,
  value,
  disabled,
  onChange,
}: {
  assignmentId: string;
  dimension: PeerDimension;
  scale: PeerReviewScale | null;
  value?: number;
  disabled: boolean;
  onChange: (value: number) => void;
}) {
  const low = scale?.score_min ?? 1;
  const high = scale?.score_max ?? 5;
  const anchors = dimension.anchors || [];
  const values = Array.from({ length: Math.max(0, high - low + 1) }, (_, index) => low + index);
  return (
    <div className="peer-rating-row peer-rating-row-stacked">
      <div>
        <strong>
          {dimension.short ? `${dimension.short}｜` : ""}
          {dimension.label}
          {dimension.label_en ? <span className="en">{dimension.label_en}</span> : null}
        </strong>
        {dimension.prompt ? <p className="peer-rating-prompt">{dimension.prompt}{dimension.prompt_en ? <span className="en">{dimension.prompt_en}</span> : null}</p> : null}
      </div>
      <div className="peer-rating-options">
        {values.map((point) => (
          <label key={point} className="peer-rating-option">
            <input
              type="radio"
              name={`${assignmentId}-${dimension.key}`}
              checked={value === point}
              disabled={disabled}
              onChange={() => onChange(point)}
            />
            <span className="peer-rating-value">{point}</span>
            {anchors[point - low] ? (
              <span className="peer-rating-anchor">{anchors[point - low]}{dimension.anchors_en?.[point - low] ? <span className="en">{dimension.anchors_en[point - low]}</span> : null}</span>
            ) : null}
          </label>
        ))}
      </div>
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
