import React from "react";
import { api, errorMessage, ApiError } from "../api";
import type {
  AssessmentKind,
  AssessmentPayload,
  Question,
  StudentState,
} from "../types";
import { BrandMark, Bilingual, ErrorNotice, Spinner } from "../components/common";
import { StageSchedule } from "../components/StageSchedule";

const KIND_LABELS: Record<AssessmentKind, { zh: string; en: string }> = {
  k0: { zh: "开始前的小问题", en: "Before we begin" },
  k1: { zh: "刚才的学习回顾", en: "A quick look back" },
  k2: { zh: "下一件文物之前", en: "Before the next artifact" },
  k3: { zh: "最后的学习回顾", en: "One last look" },
  survey: { zh: "最后几个问题", en: "A few last questions" },
};

interface LocalDraft {
  answers: Record<string, unknown>;
  savedAt: string;
}

export default function AssessmentPage({
  state,
  kind,
  onState,
}: {
  state: StudentState;
  kind: AssessmentKind;
  onState: (state: StudentState) => void;
}) {
  const [payload, setPayload] = React.useState<AssessmentPayload | null>(null);
  const [answers, setAnswers] = React.useState<Record<string, unknown>>({});
  const [localDraft, setLocalDraft] = React.useState<LocalDraft | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<{ message: string; requestId?: string } | null>(null);
  const [saveState, setSaveState] = React.useState<"idle" | "saving" | "saved" | "error">("idle");
  const [submitting, setSubmitting] = React.useState(false);
  const [submitError, setSubmitError] = React.useState<string | null>(null);
  const [activeGroup, setActiveGroup] = React.useState(0);
  const dirty = React.useRef(false);
  const storageKey = `hls:assessment:${state.run_id}:${kind}`;
  const groups = React.useMemo(() => {
    const result: Array<{ label: string; labelEn?: string | null; questions: Question[] }> = [];
    for (const question of payload?.instrument.questions || []) {
      const label = question.section || "";
      const last = result[result.length - 1];
      if (last && last.label === label) last.questions.push(question);
      else result.push({ label, labelEn: question.section_en, questions: [question] });
    }
    return result;
  }, [payload]);
  const currentGroup = groups[activeGroup] || groups[0];
  const showArtifactImage = Boolean(
    payload?.artifact_image_url && (kind !== "k0" || activeGroup > 0),
  );

  React.useEffect(() => {
    setActiveGroup(0);
  }, [payload?.instrument.id]);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api<AssessmentPayload>(`/api/student/instruments/${kind}`)
      .then((data) => {
        if (cancelled) return;
        setPayload(data);
        setAnswers(data.answers || {});
        dirty.current = false;
        try {
          const raw = window.localStorage.getItem(storageKey);
          if (raw) {
            const parsed = JSON.parse(raw) as LocalDraft;
            if (
              parsed?.answers &&
              JSON.stringify(parsed.answers) !== JSON.stringify(data.answers || {})
            ) {
              setLocalDraft(parsed);
            }
          }
        } catch {
          // corrupted local backup is ignored; server remains authoritative
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError({
            message: errorMessage(err),
            requestId: err instanceof ApiError ? err.requestId : undefined,
          });
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [kind, storageKey]);

  React.useEffect(() => {
    if (!payload || !dirty.current) return;
    setSaveState("saving");
    const timer = window.setTimeout(async () => {
      try {
        await api(`/api/student/instruments/${kind}/draft`, {
          method: "PUT",
          body: { answers },
        });
        setSaveState("saved");
      } catch {
        setSaveState("error");
      }
    }, 900);
    return () => window.clearTimeout(timer);
  }, [answers, kind, payload]);

  function updateAnswers(next: Record<string, unknown>) {
    dirty.current = true;
    setAnswers(next);
    const savedAt = new Date().toISOString();
    window.localStorage.setItem(storageKey, JSON.stringify({ answers: next, savedAt }));
  }

  function nextOrSubmit() {
    if (!payload || submitting || !currentGroup) return;
    const missing = currentGroup.questions.filter((question) => {
      const value = answers[question.id];
      if (!question.required) return false;
      if (value === undefined || value === "") return true;
      if (value && typeof value === "object" && "value" in (value as Record<string, unknown>)) {
        return !String((value as { text?: string }).text || "").trim();
      }
      return false;
    });
    if (missing.length) {
      setSubmitError(
        "还有问题没有填写，请选择或填写后再继续。 / Some questions are still unanswered; please fill them in before continuing.",
      );
      return;
    }
    if (activeGroup < groups.length - 1) {
      setSubmitError(null);
      setActiveGroup(activeGroup + 1);
      return;
    }
    void submit();
  }

  async function submit() {
    if (!payload || submitting) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const result = await api<{ state: StudentState }>(
        `/api/student/instruments/${kind}/submit`,
        { method: "POST", body: { answers } },
      );
      window.localStorage.removeItem(storageKey);
      onState(result.state);
    } catch (err) {
      setSubmitError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  const label = KIND_LABELS[kind];
  if (loading) {
    return (
      <div className="app-shell">
        <header className="topbar">
          <BrandMark />
        </header>
        <main className="centered-panel">
          <Spinner label="正在准备内容… / Preparing…" />
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
          <div>{label.zh}</div>
          <div className="en">{label.en}</div>
        </div>
        <div className="topbar-spacer" />
        <span className="step-badge">第 {state.step} 步 / Step {state.step} of 6</span>
      </header>

      <main className="assessment-layout">
        <section className="assessment-main">
          {kind !== "survey" ? (
            <div className="notice notice-warning" data-testid="ai-disabled-banner">
              这一段先不使用 AI 和左侧资料，按你现在的想法填写即可。
              <span className="en">Please answer from your current understanding; AI and the evidence panel are paused here.</span>
            </div>
          ) : null}
          {error ? <ErrorNotice
            message={error.message}
            requestId={error.requestId}
            onRetry={() => window.location.reload()}
          /> : null}
          {payload ? (
            <div className="panel">
              <div className="assessment-title-row">
                <div>
                  <h2>{payload.instrument.title}</h2>
                  {payload.instrument.title_en ? <p className="instruction-en">{payload.instrument.title_en}</p> : null}
                  <p className="muted">
                    {payload.instrument.instructions}
                    {payload.instrument.instructions_en ? (
                      <span className="instruction-en">{payload.instrument.instructions_en}</span>
                    ) : null}
                  </p>
                </div>
              </div>
              {localDraft ? (
                <div className="notice notice-info">
                  发现此浏览器上尚未同步的本地草稿。
                  <span className="en">An unsynced local draft was found.</span>
                  <div className="button-row">
                    <button
                      type="button"
                      className="button button-small"
                      onClick={() => {
                        updateAnswers(localDraft.answers);
                        setLocalDraft(null);
                      }}
                    >
                      恢复本地草稿 / Restore
                    </button>
                    <button
                      type="button"
                      className="button button-small button-ghost"
                      onClick={() => {
                        window.localStorage.removeItem(storageKey);
                        setLocalDraft(null);
                      }}
                    >
                      使用服务器版本 / Use server
                    </button>
                  </div>
                </div>
              ) : null}
              {showArtifactImage ? (
                <figure className="assessment-artifact-image">
                  <img src={payload.artifact_image_url || undefined} alt="文物图片" />
                </figure>
              ) : null}
              {currentGroup?.label ? (
                <div className="assessment-section-label">
                  {currentGroup.label}
                  {currentGroup.labelEn ? <span className="instruction-en">{currentGroup.labelEn}</span> : null}
                </div>
              ) : null}
              <div className="assessment-form">
                {(currentGroup?.questions || []).map((question, groupIndex) => (
                  <React.Fragment key={question.id}>
                  {question.subsection && question.subsection !== currentGroup.questions[groupIndex - 1]?.subsection ? (
                    <h3 className="survey-subsection">{question.subsection}<span className="instruction-en">{question.subsection_en}</span></h3>
                  ) : null}
                  <QuestionField
                    key={question.id}
                    question={question}
                    index={payload.instrument.questions.indexOf(question)}
                    value={answers[question.id]}
                    onChange={(value) => {
                      const next = { ...answers };
                      if (value === undefined) delete next[question.id];
                      else next[question.id] = value;
                      updateAnswers(next);
                    }}
                  />
                  </React.Fragment>
                ))}
              </div>
              <div className="assessment-footer">
                {activeGroup > 0 ? (
                  <button
                    type="button"
                    className="button button-ghost button-small"
                    onClick={() => {
                      setSubmitError(null);
                      setActiveGroup(activeGroup - 1);
                    }}
                  >
                    返回 / Back
                  </button>
                ) : null}
                <div className={`save-indicator save-${saveState}`} aria-live="polite">
                  {saveState === "saving" && "正在保存… / Saving…"}
                  {saveState === "saved" && "已自动保存 / Autosaved"}
                  {saveState === "error" && "自动保存失败 / Autosave failed"}
                </div>
                <button
                  type="button"
                  className="button button-primary"
                  onClick={nextOrSubmit}
                  disabled={submitting}
                >
                  {submitting ? "正在保存… / Saving…" : "继续 / Continue"}
                </button>
              </div>
              {submitError ? <ErrorNotice message={submitError} /> : null}
            </div>
          ) : null}
        </section>
        <div className="assessment-sidebar">
          <StageSchedule currentStep={state.step} />
          <div className="side-card">
            <div className="side-card-icon">◎</div>
            <div>
              <strong>匿名学习数据 / Anonymous learning data</strong>
              <p className="small muted">
                你的回答会自动保存。按现在的想法填写即可，之后可以继续创作。
                <span className="en">
                  Your answers save automatically; answer with your current thinking and continue afterwards.
                </span>
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

function QuestionField({
  question,
  index,
  value,
  onChange,
}: {
  question: Question;
  index: number;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  const idPrefix = `q-${question.id}`;
  const selectedOther =
    value && typeof value === "object" && "value" in (value as Record<string, unknown>)
      ? (value as { value?: string; text?: string })
      : null;
  return (
    <fieldset className="question-card" data-testid={`question-${question.id}`}>
      <legend>
        <span className="question-number">{index + 1}</span>
        <span>
          {question.heading ? <strong className="survey-item-heading">{question.id}｜{question.heading}<span className="prompt-en">{question.heading_en}</span></strong> : null}
          {question.prompt}
          {question.prompt_en ? (
            <span className="prompt-en">{question.prompt_en}</span>
          ) : null}
        </span>
      </legend>

      {question.type === "single_choice" ? (
        <div className="choice-list">
          {(question.options || []).map((option) => {
            const selected =
              (value && typeof value === "object" && "value" in (value as Record<string, unknown>)
                ? (value as { value?: string }).value === option.value
                : value === option.value);
            return (
              <div key={option.value} className="choice-option">
              <label className="choice-row">
                <input
                  type="radio"
                  name={question.id}
                  id={`${idPrefix}-${option.value}`}
                  checked={selected}
                  onChange={() => {
                    if (option.allow_text) {
                      onChange({ value: option.value, text: "" });
                    } else {
                      onChange(option.value);
                    }
                  }}
                />
                <span>
                  {option.label}
                  {option.label_en ? <span className="option-en">{option.label_en}</span> : null}
                </span>
              </label>
              {option.allow_text ? (
                <input
                  className="choice-other-input"
                  type="text"
                  value={selected ? selectedOther?.text || "" : ""}
                  onFocus={() => {
                    if (!selected) onChange({ value: option.value, text: "" });
                  }}
                  onChange={(event) => onChange({ value: option.value, text: event.target.value })}
                  maxLength={200}
                  placeholder="请填写你的专业背景… / Describe your discipline…"
                  aria-label="其他专业背景说明"
                  required={selected}
                />
              ) : null}
              </div>
            );
          })}
        </div>
      ) : null}

      {question.type === "multi_choice" ? (
        <div className="choice-list">
          {(question.options || []).map((option) => {
            const selected = Array.isArray(value) ? (value as string[]) : [];
            const checked = selected.includes(option.value);
            return (
              <label key={option.value} className="choice-row">
                <input
                  type="checkbox"
                  id={`${idPrefix}-${option.value}`}
                  checked={checked}
                  onChange={() => {
                    const next = checked
                      ? selected.filter((item) => item !== option.value)
                      : [...selected, option.value];
                    onChange(next.length ? next : undefined);
                  }}
                />
                <span>
                  {option.label}
                  {option.label_en ? <span className="option-en">{option.label_en}</span> : null}
                </span>
              </label>
            );
          })}
        </div>
      ) : null}

      {question.type === "short_text" ? (
        <div>
          <textarea
            value={typeof value === "string" ? value : ""}
            onChange={(event) => onChange(event.target.value || undefined)}
            maxLength={question.max_length || 200}
            rows={4}
            aria-label={question.prompt}
          />
          <div className="tiny muted text-right">
            {typeof value === "string" ? Array.from(value).length : 0} /{" "}
            {question.max_length || 200}
          </div>
        </div>
      ) : null}

      {question.type === "evidence_judgment" ? (
        <div className="evidence-table-wrap">
          <table className="evidence-table">
            <thead>
              <tr>
                <th>材料 Evidence</th>
                <th>可以 / Yes</th>
                <th>不可以 / No</th>
              </tr>
            </thead>
            <tbody>
              {(question.rows || []).map((row) => {
                const current = (value && typeof value === "object"
                  ? (value as Record<string, string>)
                  : {})[row.id];
                return (
                  <tr key={row.id}>
                    <td>{row.label}</td>
                    <td>
                      <input
                        type="radio"
                        name={`${question.id}-${row.id}`}
                        checked={current === "yes"}
                        onChange={() => {
                          const next = { ...(value as Record<string, string> || {}) };
                          next[row.id] = "yes";
                          onChange(next);
                        }}
                        aria-label={`${row.label}: yes`}
                      />
                    </td>
                    <td>
                      <input
                        type="radio"
                        name={`${question.id}-${row.id}`}
                        checked={current === "no"}
                        onChange={() => {
                          const next = { ...(value as Record<string, string> || {}) };
                          next[row.id] = "no";
                          onChange(next);
                        }}
                        aria-label={`${row.label}: no`}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}

      {question.type === "likert" ? (
        <div className="likert-row">
          {Array.from(
            {
              length:
                (question.scale_max ?? 5) - (question.scale_min ?? 1) + 1,
            },
            (_, i) => (question.scale_min ?? 1) + i,
          ).map((point) => (
            <label key={point} className="likert-item">
              <input
                type="radio"
                name={question.id}
                checked={value === point}
                onChange={() => onChange(point)}
              />
              <span className="likert-number">{point}</span>
              {question.scale_anchors?.[point] ? <span className="tiny muted scale-anchor">{question.scale_anchors[point]}{question.scale_anchors_en?.[point] ? <span className="option-en">{question.scale_anchors_en[point]}</span> : null}</span> : null}
              {!question.scale_anchors?.[point] && point === (question.scale_min ?? 1) && question.scale_labels?.[0] ? (
                <span className="tiny muted">{question.scale_labels[0]}</span>
              ) : null}
              {!question.scale_anchors?.[point] && point === (question.scale_max ?? 5) &&
              question.scale_labels?.length &&
              question.scale_labels[question.scale_labels.length - 1] ? (
                <span className="tiny muted">
                  {question.scale_labels[question.scale_labels.length - 1]}
                </span>
              ) : null}
            </label>
          ))}
        </div>
      ) : null}
    </fieldset>
  );
}

