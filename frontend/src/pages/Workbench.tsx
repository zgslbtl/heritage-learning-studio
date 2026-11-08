import React from "react";
import { ApiError, api, errorMessage } from "../api";
import type {
  Artifact,
  ChatMessage,
  Guide,
  ImageJob,
  RationaleFields,
  RoundData,
  StudentState,
  StructuredFields,
  Work,
} from "../types";
import {
  Bilingual,
  BrandMark,
  ErrorNotice,
  Spinner,
  formatClock,
  formatTime,
  safeRandomId,
  useCountdown,
} from "../components/common";
import { StageSchedule } from "../components/StageSchedule";
import ArtifactReader from "../components/ArtifactReader";

type SaveStatus = "idle" | "saving" | "saved" | "unsaved" | "error";

function normalizeWork(work: Work): Work {
  return {
    ...work,
    rationale_fields: {
      heritage_knowledge: work.rationale_fields?.heritage_knowledge || "",
      cultural_translation: work.rationale_fields?.cultural_translation || "",
      design_reason: work.rationale_fields?.design_reason || "",
    },
  };
}

export default function Workbench({
  state,
  onState,
  onRefresh,
}: {
  state: StudentState;
  onState: (state: StudentState) => void;
  onRefresh: (silent?: boolean) => Promise<void>;
}) {
  const roundNo = state.stage === "t1_active" ? 1 : 2;
  const [roundData, setRoundData] = React.useState<RoundData | null>(null);
  const [messages, setMessages] = React.useState<ChatMessage[]>([]);
  const [guide, setGuide] = React.useState<Guide | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [loadError, setLoadError] = React.useState<{ message: string; requestId?: string } | null>(
    null,
  );
  const [saveStatus, setSaveStatus] = React.useState<SaveStatus>("idle");
  const [expired, setExpired] = React.useState(false);
  const expirationHandled = React.useRef(false);

  const load = React.useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [roundPayload, messagePayload] = await Promise.all([
        api<RoundData>(`/api/student/rounds/${roundNo}`),
        api<{ messages: ChatMessage[]; guide: Guide | null }>(
          `/api/student/rounds/${roundNo}/messages`,
        ),
      ]);
      setRoundData(roundPayload);
      setMessages(messagePayload.messages);
      setGuide(roundPayload.guide || messagePayload.guide);
    } catch (err) {
      setLoadError({
        message: errorMessage(err),
        requestId: err instanceof ApiError ? err.requestId : undefined,
      });
    } finally {
      setLoading(false);
    }
  }, [roundNo]);

  React.useEffect(() => {
    void load();
  }, [load]);

  const deadline = roundData?.deadline_at || state.active_round?.deadline_at || "";
  const onExpire = React.useCallback(() => {
    if (expirationHandled.current) return;
    expirationHandled.current = true;
    setExpired(true);
    window.setTimeout(() => {
      void onRefresh(true);
    }, 1200);
  }, [onRefresh]);

  const remaining = useCountdown(deadline || null, onExpire);

  if (loading) {
    return (
      <div className="app-shell">
        <header className="topbar">
          <BrandMark />
        </header>
        <main className="centered-panel">
          <Spinner label="正在加载创作工作台… / Loading workspace…" />
        </main>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="app-shell">
        <header className="topbar">
          <BrandMark />
        </header>
        <main className="centered-panel">
          <ErrorNotice
            message={loadError.message}
            requestId={loadError.requestId}
            onRetry={() => void load()}
          />
          <button type="button" className="button" onClick={() => void onRefresh()}>
            同步当前阶段 / Sync stage
          </button>
        </main>
      </div>
    );
  }

  if (!roundData) return null;
  const locked = expired || remaining <= 0;

  return (
    <div className="app-shell workspace-shell">
      <header className="topbar workspace-topbar">
        <BrandMark compact />
        <div className="topbar-separator" />
        <div className="task-block">
          <div className="task-kicker">{roundNo === 1 ? "第一次文物创作" : "第二次文物创作"}</div>
          <div className="task-title">{roundData.artifact.title}</div>
        </div>
        <div className="topbar-spacer" />
        <div
          className={`timer-pill ${remaining < 120 ? "timer-urgent" : ""}`}
          aria-live={remaining < 120 ? "polite" : "off"}
        >
          <span className="timer-icon">◷</span>
          <span>剩余时间 / Time left</span>
          <strong>{formatClock(remaining)}</strong>
        </div>
        <div className={`save-indicator save-${saveStatus}`} aria-live="polite">
          {saveStatus === "saving" && "保存中… / Saving…"}
          {saveStatus === "saved" && "已自动保存 / Autosaved"}
          {saveStatus === "unsaved" && "未保存 / Unsaved"}
          {saveStatus === "error" && "保存失败 / Save failed"}
          {saveStatus === "idle" && "已自动保存 / Autosaved"}
        </div>
        <div className="participant-chip" title="Anonymous participant identifier">
          <span aria-hidden="true">◎</span>
          {state.participant.id.slice(0, 6).toUpperCase()}
        </div>
      </header>

      {locked ? (
        <div className="notice notice-warning workspace-banner">
          本轮时间已结束，正在保存最后的记录并进入下一阶段…
          <span className="en">Time is up. Saving the final record and moving to the next stage…</span>
        </div>
      ) : null}

      <main className="workspace-grid">
        <ArtifactReader artifact={roundData.artifact} roundNo={roundNo} disabled={locked} />
        <ChatPanel
          roundNo={roundNo}
          initialMessages={messages}
          initialGuide={guide || roundData.guide}
          onMessages={setMessages}
          onGuide={setGuide}
          disabled={locked}
        />
        <CreationPanel
          roundNo={roundNo}
          runId={state.run_id}
          data={roundData}
          disabled={locked}
          onSaveStatus={setSaveStatus}
          onState={onState}
          onRefresh={onRefresh}
        />
      </main>
    </div>
  );
}

function MessageText({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {parts.map((part, index) =>
        part.startsWith("**") && part.endsWith("**") ? (
          <strong key={index}>{part.slice(2, -2)}</strong>
        ) : (
          <React.Fragment key={index}>{part}</React.Fragment>
        ),
      )}
    </>
  );
}

function ChatPanel({
  roundNo,
  initialMessages,
  initialGuide,
  onMessages,
  onGuide,
  disabled,
}: {
  roundNo: number;
  initialMessages: ChatMessage[];
  initialGuide: Guide | null;
  onMessages: (messages: ChatMessage[]) => void;
  onGuide: (guide: Guide | null) => void;
  disabled: boolean;
}) {
  const [messages, setMessages] = React.useState<ChatMessage[]>(initialMessages);
  const [guide, setGuide] = React.useState<Guide | null>(initialGuide);
  const [input, setInput] = React.useState("");
  const [sending, setSending] = React.useState(false);
  const [guideBusy, setGuideBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [retryId, setRetryId] = React.useState<number | null>(null);
  const bottomRef = React.useRef<HTMLDivElement>(null);
  const pending = messages.length > 0 && messages[messages.length - 1].role === "user";

  React.useEffect(() => {
    setMessages(initialMessages);
    const last = initialMessages[initialMessages.length - 1];
    setRetryId(last?.role === "user" ? last.id : null);
  }, [initialMessages]);

  React.useEffect(() => {
    setGuide(initialGuide);
  }, [initialGuide]);

  React.useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, sending]);

  React.useEffect(() => {
    if (!pending || disabled) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const data = await api<{ messages: ChatMessage[]; guide: Guide | null }>(
          `/api/student/rounds/${roundNo}/messages`,
        );
        if (cancelled) return;
        const last = data.messages[data.messages.length - 1];
        setMessages(data.messages);
        onMessages(data.messages);
        setGuide(data.guide);
        onGuide(data.guide);
        setRetryId(last?.role === "user" ? last.id : null);
      } catch {
        // The main request path surfaces errors; keep waiting for the server reply.
      }
    };
    const interval = window.setInterval(() => void poll(), 3000);
    const waitTimer = window.setTimeout(() => {
      if (cancelled) return;
      setError(
        "No reply has arrived yet. Your message is saved; you can retry it. / 尚未收到回复，可重试这条消息。",
      );
      setRetryId((current) => current ?? messages[messages.length - 1]?.id ?? null);
    }, 75_000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
      window.clearTimeout(waitTimer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pending, disabled, roundNo]);

  function appendMessages(incoming: ChatMessage[]) {
    if (!incoming.length) return;
    setMessages((current) => {
      const seen = new Set(current.map((message) => message.id));
      const merged = [...current, ...incoming.filter((message) => !seen.has(message.id))];
      onMessages(merged);
      return merged;
    });
  }

  async function refreshAfterFailure() {
    try {
      const data = await api<{ messages: ChatMessage[]; guide: Guide | null }>(
        `/api/student/rounds/${roundNo}/messages`,
      );
      setMessages(data.messages);
      onMessages(data.messages);
      setGuide(data.guide);
      onGuide(data.guide);
      const last = data.messages[data.messages.length - 1];
      setRetryId(last?.role === "user" ? last.id : null);
    } catch {
      // A second network failure is displayed through the primary error.
    }
  }

  async function send() {
    const content = input.trim();
    if (!content || sending || pending || disabled) return;
    setSending(true);
    setError(null);
    try {
      const data = await api<{
        duplicate: boolean;
        messages: ChatMessage[];
        guide: Guide | null;
      }>(`/api/student/rounds/${roundNo}/messages`, {
        method: "POST",
        body: { content, client_message_id: safeRandomId() },
      });
      appendMessages(data.messages);
      if (data.guide) {
        setGuide(data.guide);
        onGuide(data.guide);
      }
      setRetryId(null);
      setInput("");
    } catch (err) {
      setError(errorMessage(err));
      await refreshAfterFailure();
    } finally {
      setSending(false);
    }
  }

  async function retry() {
    if (!retryId || sending || disabled) return;
    setSending(true);
    setError(null);
    try {
      const data = await api<{ messages: ChatMessage[] }>(
        `/api/student/rounds/${roundNo}/messages/${retryId}/retry`,
        { method: "POST" },
      );
      appendMessages(data.messages);
      setRetryId(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSending(false);
    }
  }

  async function guideAction(action: "advance" | "hint", skip = false) {
    if (!guide || guideBusy || disabled) return;
    setGuideBusy(true);
    setError(null);
    try {
      const path =
        action === "hint"
          ? `/api/student/rounds/${roundNo}/hlsf/hint`
          : `/api/student/rounds/${roundNo}/hlsf/advance`;
      const body =
        action === "hint"
          ? { phase: guide.phase }
          : { from_phase: guide.phase, skip };
      const data = await api<{ guide: Guide; messages: ChatMessage[] }>(path, {
        method: "POST",
        body,
      });
      setGuide(data.guide);
      onGuide(data.guide);
      appendMessages(data.messages || []);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setGuideBusy(false);
    }
  }

  const currentPhase = guide?.phase;
  const isComplete = currentPhase === "complete";

  return (
    <section className="workspace-panel chat-panel" aria-label="AI chat">
      <div className="panel-heading compact-heading">
        <div>
          <h2>AI 对话</h2>
          <div className="en">AI Chat{guide ? " · Learning guide" : ""}</div>
        </div>
        {guide ? <span className="guide-chip">学习引导 / Learning Guide</span> : null}
      </div>

      {guide ? (
        <div className="guide-rail" aria-label="Guided learning phases">
          <div className="guide-phases">
            {guide.phases.map((phase, index) => {
              const currentIndex = guide.phases.findIndex((item) => item.id === currentPhase);
              const stateClass =
                isComplete || index < currentIndex
                  ? "done"
                  : index === currentIndex
                    ? "current"
                    : "upcoming";
              return (
                <React.Fragment key={phase.id}>
                  {index > 0 ? <span className="guide-arrow">→</span> : null}
                  <div className={`guide-phase ${stateClass}`}>
                    <span className="guide-icon">{phase.id === "observe" ? "◉" : phase.id === "explain" ? "◌" : phase.id === "create" ? "▣" : "↻"}</span>
                    <span>
                      {phase.label_zh}
                      <span className="en"> {phase.label_en}</span>
                    </span>
                  </div>
                </React.Fragment>
              );
            })}
          </div>
          {!isComplete && currentPhase ? (
            <div className="guide-actions">
              <button
                type="button"
                className="button button-small button-ghost"
                onClick={() => void guideAction("hint")}
                disabled={guide.hint_used || guideBusy || disabled}
              >
                {guide.hint_used ? "本阶段提示已使用" : "获取一次提示 / Hint"}
              </button>
              <button
                type="button"
                className="button button-small"
                onClick={() => void guideAction("advance", false)}
                disabled={guideBusy || disabled}
              >
                下一阶段 / Next
              </button>
              <button
                type="button"
                className="text-button"
                onClick={() => void guideAction("advance", true)}
                disabled={guideBusy || disabled}
              >
                跳过 / Skip
              </button>
            </div>
          ) : (
            <div className="guide-complete">学习引导已完成 / Guide complete</div>
          )}
        </div>
      ) : null}

      <div className="chat-scroll" data-testid="chat-messages">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <div className="assistant-avatar">AI</div>
            <p>
              你可以询问文物资料、讨论文化含义，或请 AI 帮助你改进文创设计。
              <span className="en">
                Ask about the evidence, discuss cultural meanings, or request feedback on your product design.
              </span>
            </p>
          </div>
        ) : null}
        {messages.map((message) => (
          <div
            key={message.id}
            className={`chat-message ${message.role === "user" ? "from-user" : "from-assistant"}`}
          >
            {message.role === "assistant" ? (
              <div className="message-avatar" aria-hidden="true">
                AI
              </div>
            ) : null}
            <div className="message-body">
              {message.source === "hlsf_prompt" || message.source === "hlsf_hint" ? (
                <div className="message-label">
                  {message.source === "hlsf_hint" ? "针对性提示 / Hint" : "学习引导 / Learning Guide"}
                </div>
              ) : null}
              <div className="message-bubble"><MessageText text={message.content} /></div>
              <div className="message-time">{formatTime(message.created_at)}</div>
            </div>
            {message.role === "user" ? <div className="message-user-mark">你</div> : null}
          </div>
        ))}
        {sending ? (
          <div className="chat-message from-assistant">
            <div className="message-avatar">AI</div>
            <div className="message-bubble typing">正在思考… / Thinking…</div>
          </div>
        ) : null}
        <div ref={bottomRef} />
      </div>

      {error ? (
        <div className="chat-error">
          <ErrorNotice message={error} />
          {retryId ? (
            <button
              type="button"
              className="button button-small"
              onClick={() => void retry()}
              disabled={sending || disabled}
            >
              重试这条消息 / Retry
            </button>
          ) : null}
        </div>
      ) : null}

      <form
        className="chat-composer"
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        <textarea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder={
            pending
              ? "上一条消息尚未收到回复，请先重试。 / Retry the unanswered message first."
              : "请输入你的问题或想法… / Enter your question or idea…"
          }
          disabled={sending || disabled || pending}
          rows={2}
          maxLength={4000}
          aria-label="Message"
          onKeyDown={(event) => {
            if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
              event.preventDefault();
              void send();
            }
          }}
        />
        <div className="composer-footer">
          <span className="tiny muted">⌘/Ctrl + Enter 发送</span>
          <button
            type="submit"
            className="button button-primary send-button"
            disabled={sending || disabled || pending || !input.trim()}
            aria-label="Send message"
          >
            ➤
          </button>
        </div>
      </form>
    </section>
  );
}

function CreationPanel({
  roundNo,
  runId,
  data,
  disabled,
  onSaveStatus,
  onState,
  onRefresh,
}: {
  roundNo: number;
  runId: string;
  data: RoundData;
  disabled: boolean;
  onSaveStatus: (status: SaveStatus) => void;
  onState: (state: StudentState) => void;
  onRefresh: (silent?: boolean) => Promise<void>;
}) {
  const [work, setWork] = React.useState<Work>(() => normalizeWork(data.work));
  const [revision, setRevision] = React.useState(data.work.revision);
  const [jobs, setJobs] = React.useState<ImageJob[]>(data.image_jobs);
  const [saveError, setSaveError] = React.useState<string | null>(null);
  const [actionError, setActionError] = React.useState<string | null>(null);
  const [generating, setGenerating] = React.useState(false);
  const [finishing, setFinishing] = React.useState(false);
  const [submitHintOpen, setSubmitHintOpen] = React.useState(false);
  const [selectedImageId, setSelectedImageId] = React.useState<string | null>(
    data.selected_image_job_id || null,
  );
  const [pollError, setPollError] = React.useState<string | null>(null);
  const [localDraft, setLocalDraft] = React.useState<Work | null>(null);
  const workForm = data.work_form || (roundNo === 1 ? "structured" : "open");
  const isRationale = workForm === "rationale";
  const dirty = React.useRef(false);
  const latestValues = React.useRef<Work>(normalizeWork(data.work));
  const saveInFlight = React.useRef<Promise<boolean> | null>(null);
  const storageKey = `hls:work:${runId}:${roundNo}:${data.artifact.id}`;

  React.useEffect(() => {
    latestValues.current = work;
  }, [work]);

  React.useEffect(() => {
    try {
      const raw = window.localStorage.getItem(storageKey);
      if (!raw) return;
      const parsed = JSON.parse(raw) as Work;
      if (parsed && JSON.stringify(parsed) !== JSON.stringify(data.work)) {
        setLocalDraft(normalizeWork(parsed));
      }
    } catch {
      // ignore corrupt local backup
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function persistLocal(next: Work) {
    window.localStorage.setItem(storageKey, JSON.stringify(next));
  }

  function update(patch: Partial<Work>) {
    setWork((current) => {
      const next = { ...current, ...patch };
      latestValues.current = next;
      persistLocal(next);
      return next;
    });
    dirty.current = true;
    onSaveStatus("unsaved");
  }

  function updateRationale(key: keyof RationaleFields, value: string) {
    setWork((current) => {
      const next = {
        ...current,
        rationale_fields: { ...current.rationale_fields, [key]: value },
      };
      latestValues.current = next;
      persistLocal(next);
      return next;
    });
    dirty.current = true;
    onSaveStatus("unsaved");
  }

  function updateStructured(key: keyof StructuredFields, value: string) {
    setWork((current) => {
      const next = {
        ...current,
        structured_fields: { ...current.structured_fields, [key]: value },
      };
      latestValues.current = next;
      persistLocal(next);
      return next;
    });
    dirty.current = true;
    onSaveStatus("unsaved");
  }

  const saveNow = React.useCallback(async (): Promise<boolean> => {
    if (disabled) return false;
    if (saveInFlight.current) return saveInFlight.current;
    const snapshot = latestValues.current;
    onSaveStatus("saving");
    setSaveError(null);
    const promise = (async () => {
      try {
        const result = await api<{ work: Work; revision: number; created: boolean }>(
          `/api/student/rounds/${roundNo}/work`,
          { method: "PUT", body: snapshot },
        );
        setRevision(result.revision);
        if (JSON.stringify(latestValues.current) === JSON.stringify(snapshot)) {
          dirty.current = false;
          onSaveStatus("saved");
        } else {
          dirty.current = true;
          onSaveStatus("unsaved");
          window.setTimeout(() => {
            void saveNow();
          }, 500);
        }
        return true;
      } catch (err) {
        setSaveError(errorMessage(err));
        onSaveStatus("error");
        return false;
      } finally {
        saveInFlight.current = null;
      }
    })();
    saveInFlight.current = promise;
    return promise;
  }, [disabled, onSaveStatus, roundNo]);

  React.useEffect(() => {
    if (!dirty.current || disabled) return;
    const timer = window.setTimeout(() => {
      void saveNow();
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [work, disabled, saveNow]);

  const activeJobs = jobs.filter((job) => job.status === "queued" || job.status === "running");
  const activeSignature = activeJobs.map((job) => job.id).join(",");
  React.useEffect(() => {
    if (!activeSignature || disabled) return;
    const ids = activeSignature.split(",");
    let cancelled = false;
    const poll = async () => {
      for (const id of ids) {
        try {
          const result = await api<{ job: ImageJob }>(`/api/student/image-jobs/${id}`);
          if (cancelled) return;
          setJobs((current) =>
            current.map((job) => (job.id === result.job.id ? result.job : job)),
          );
          setPollError(null);
        } catch (err) {
          setPollError(`概念图状态刷新失败 / Status refresh failed: ${errorMessage(err)}`);
        }
      }
    };
    const timer = window.setInterval(() => void poll(), 2000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [activeSignature, disabled]);

  const successfulJobs = jobs.filter((job) => job.status === "succeeded" && job.image_url);
  const selectedJob =
    successfulJobs.find((job) => job.id === selectedImageId) || successfulJobs[0] || null;
  const latestFailed = jobs.find((job) => job.status === "failed") || null;
  const quotaUsed = jobs.length;
  const quotaReached = data.image_job_limit > 0 && quotaUsed >= data.image_job_limit;
  const hasWorkContent = Boolean(
    work.product_name.trim() ||
      work.product_category.trim() ||
      work.design_concept.trim() ||
      work.open_statement.trim() ||
      (work.image_prompt || "").trim() ||
      Object.values(work.structured_fields).some((value) => value.trim()) ||
      Object.values(work.rationale_fields).some((value) => value.trim()),
  );
  const canGenerate =
    !disabled &&
    !generating &&
    !activeJobs.length &&
    !quotaReached &&
    hasWorkContent;

  React.useEffect(() => {
    if (!selectedImageId && successfulJobs[0]) {
      setSelectedImageId(successfulJobs[0].id);
    }
  }, [selectedImageId, successfulJobs]);

  async function selectImage(jobId: string) {
    if (disabled) return;
    setActionError(null);
    try {
      await api(`/api/student/rounds/${roundNo}/image-jobs/${jobId}/select`, {
        method: "POST",
      });
      setSelectedImageId(jobId);
    } catch (err) {
      setActionError(errorMessage(err));
    }
  }

  async function generate(retryOf?: string) {
    if (disabled || generating) return;
    setActionError(null);
    setGenerating(true);
    try {
      const saved = await saveNow();
      if (!saved) {
        setGenerating(false);
        return;
      }
      const result = await api<{ job: ImageJob }>(
        `/api/student/rounds/${roundNo}/image-jobs`,
        { method: "POST", body: retryOf ? { retry_of: retryOf } : {} },
      );
      setJobs((current) => [result.job, ...current]);
    } catch (err) {
      setActionError(errorMessage(err));
    } finally {
      setGenerating(false);
    }
  }

  async function finish() {
    if (disabled || finishing) return;
    setFinishing(true);
    setActionError(null);
    try {
      const saved = await saveNow();
      if (!saved) {
        setFinishing(false);
        return;
      }
      const result = await api<{ state: StudentState }>(
        `/api/student/rounds/${roundNo}/finish`,
        {
          method: "POST",
          body: roundNo === 2 ? { consent_future_research: true } : undefined,
        },
      );
      window.localStorage.removeItem(storageKey);
      onState(result.state);
      await onRefresh(true);
    } catch (err) {
      if (err instanceof ApiError && err.code === "work_incomplete") {
        setActionError(null);
        setSubmitHintOpen(true);
      } else {
        setActionError(errorMessage(err));
      }
    } finally {
      setFinishing(false);
    }
  }

  return (
    <>
    <section className="workspace-panel creation-panel" aria-label="My product design">
      <div className="panel-heading compact-heading">
        <div>
          <h2>我的文创设计</h2>
          <div className="en">My Product Design</div>
        </div>
        <span className="revision-chip">v{revision}</span>
      </div>
      <div className="panel-scroll creation-scroll">
        {localDraft ? (
          <div className="notice notice-info small-notice">
            此浏览器有未同步的本地设计草稿。
            <div className="button-row">
              <button
                type="button"
                className="button button-small"
                onClick={() => {
                  latestValues.current = localDraft;
                  setWork(localDraft);
                  setLocalDraft(null);
                  dirty.current = true;
                  onSaveStatus("unsaved");
                }}
              >
                恢复 / Restore
              </button>
              <button
                type="button"
                className="button button-small button-ghost"
                onClick={() => {
                  window.localStorage.removeItem(storageKey);
                  setLocalDraft(null);
                }}
              >
                忽略 / Discard
              </button>
            </div>
          </div>
        ) : null}

        <div className="keyframe-section">
          <div className="section-heading-row">
            <h3>产品概念图 <span className="en">Concept Image</span></h3>
            <span className="quota-label">
              {data.image_job_limit > 0 ? `生成额度 ${quotaUsed}/${data.image_job_limit}` : "可多次生成"}
            </span>
          </div>
          <label className="field-label" htmlFor="image-prompt">
            用文字描述你希望的产品图 <span className="en">Describe your image</span>
          </label>
          <p className="field-hint image-prompt-hint">
            尽量写出外观、材质、颜色、构图、场景和氛围。你的描述会作为图片生成的主要视觉提示；右侧作品字段作为补充。
            <span className="prompt-help-note">
              说清需求，可以让 AI 帮助你写提示词来生成图像。
            </span>
          </p>
          <textarea
            id="image-prompt"
            className="image-prompt-input"
            value={work.image_prompt || ""}
            onChange={(event) => update({ image_prompt: event.target.value })}
            disabled={disabled}
            rows={6}
            maxLength={6000}
            placeholder="例如：一件米白色棉质 T 恤，胸前是鹭鸶与莲塘纹样的细线刺绣，袖口有深蓝色滚边；产品平铺在浅灰色石面上，柔和侧光，背景有少量莲叶投影，整体安静、当代、适合博物馆商店。"
          />
          <div className="tiny muted text-right">{Array.from(work.image_prompt || "").length} / 6000</div>
          {successfulJobs.length ? (
            <div className="concept-gallery" aria-label="已生成的产品概念图">
              {successfulJobs.map((job) => {
                const selected = selectedJob?.id === job.id;
                return (
                  <div className={`concept-card${selected ? " is-selected" : ""}`} key={job.id}>
                    <img src={job.image_url || ""} alt="Generated product concept" />
                    <div className="concept-card-actions">
                      <button
                        type="button"
                        className={`button button-small ${selected ? "button-primary" : "button-ghost"}`}
                        onClick={() => void selectImage(job.id)}
                        disabled={disabled || selected}
                      >
                        {selected ? "✓ 已选用于提交" : "选择这张"}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : activeJobs.length ? (
            <div className="keyframe-placeholder generating">
              <div className="pulse-mark" />
              <strong>
                {activeJobs[0].status === "queued"
                  ? "图片任务排队中… / Queued…"
                  : "正在生成产品概念图… / Generating…"}
              </strong>
              <span className="tiny muted">图片由服务端任务队列处理，请保持页面打开。</span>
            </div>
          ) : (
            <div className="keyframe-placeholder">
              <div className="empty-landscape" aria-hidden="true" />
              <span>根据你的产品设计生成一张概念效果图</span>
            </div>
          )}

          {latestFailed && !activeJobs.length ? (
            <div className="notice notice-error small-notice">
              <strong>图片生成失败</strong>
              <div>{latestFailed.error_message || latestFailed.error_code || "Unknown image error"}</div>
              <button
                type="button"
                className="button button-small"
                onClick={() => void generate(latestFailed.id)}
                disabled={!canGenerate}
              >
                重试生成 / Retry
              </button>
            </div>
          ) : null}

          {!activeJobs.length ? (
            <button
              type="button"
              className="button button-secondary button-wide"
              onClick={() => void generate()}
              disabled={!canGenerate}
            >
              {generating
                ? "提交中… / Submitting…"
                : quotaReached
                  ? "生成额度已用完 / Quota used"
                  : successfulJobs.length
                    ? "再生成一张 / Generate Another"
                    : "生成概念图 / Generate Concept Image"}
            </button>
          ) : null}
          {pollError ? <p className="tiny error-text">{pollError}</p> : null}
          {actionError ? <p className="tiny error-text">{actionError}</p> : null}
        </div>
        <label className="field-label" htmlFor="product-name">
          产品名称 <span className="required">（必填）</span>
          <span className="en">Product Name</span>
        </label>
        <div className="input-with-count">
          <input
            id="product-name"
            value={work.product_name}
            onChange={(event) => update({ product_name: event.target.value })}
            maxLength={200}
            disabled={disabled}
            placeholder="例如：纹样新生 · 文化 T 恤"
          />
          <span>{Array.from(work.product_name).length} / 200</span>
        </div>

        {workForm !== "open" ? (
          <div className="two-col">
            <label className="field-label" htmlFor="product-category">
              产品类别 / 用途 <span className="en">Category / Use</span>
              <input
                id="product-category"
                value={work.product_category}
                onChange={(event) => update({ product_category: event.target.value })}
                maxLength={160}
                disabled={disabled}
                placeholder="T 恤、手提袋、文具…"
              />
            </label>
            <label className="field-label" htmlFor="target-audience">
              目标受众 <span className="en">Audience</span>
              <input
                id="target-audience"
                value={work.target_audience}
                onChange={(event) => update({ target_audience: event.target.value })}
                maxLength={300}
                disabled={disabled}
                placeholder="博物馆观众、上班族、学生…"
              />
              <span className="field-hint">
                例如：博物馆观众、上班族、学生、亲子家庭、老年观众、文化爱好者。
              </span>
            </label>
          </div>
        ) : null}

        {!isRationale ? (
          <>
            <label className="field-label" htmlFor="design-concept">
              {workForm === "structured" ? "设计概念" : "简短概念"}{" "}
              <span className="en">Design Concept</span>
            </label>
            <textarea
              id="design-concept"
              value={work.design_concept}
              onChange={(event) => update({ design_concept: event.target.value })}
              disabled={disabled}
              rows={4}
              maxLength={4000}
              placeholder="用几句话说明你的产品概念和设计方向…"
            />
          </>
        ) : null}

        {isRationale ? (
          <div className="rationale-fields">
            <div className="field-label">
              三段作品说明 <span className="en">Three-part rationale</span>
              <span className="field-hint">
                每段写几句话即可，建议合计 100–150 字；不强制字数。
              </span>
            </div>
            {RATIONALE_FIELD_DEFS.map((field) => (
              <label key={field.key} className="field-label t1-field">
                {field.zh} <span className="en">{field.en}</span>
                <span className="field-hint">{field.hint}</span>
                <textarea
                  value={work.rationale_fields[field.key]}
                  onChange={(event) => updateRationale(field.key, event.target.value)}
                  disabled={disabled}
                  rows={3}
                  maxLength={1000}
                  placeholder={field.placeholder}
                />
              </label>
            ))}
          </div>
        ) : workForm === "structured" ? (
          <details className="evidence-accordion" open>
            <summary>作品说明（六个方面） / Design statement</summary>
            <div className="accordion-body">
              {T1_FIELD_DEFS.map((field) => (
                <label key={field.key} className="field-label t1-field">
                  {field.zh} <span className="en">{field.en}</span>
                  <span className="field-hint">{field.hint}</span>
                  <textarea
                    value={work.structured_fields[field.key]}
                    onChange={(event) => updateStructured(field.key, event.target.value)}
                    disabled={disabled}
                    rows={3}
                    maxLength={2000}
                    placeholder={field.placeholder}
                  />
                </label>
              ))}
            </div>
          </details>
        ) : (
          <>
            <label className="field-label" htmlFor="open-statement">
              开放作品说明 <span className="required">（必填）</span>
              <span className="en">Open Design Statement</span>
            </label>
            <textarea
              id="open-statement"
              value={work.open_statement}
              onChange={(event) => update({ open_statement: event.target.value })}
              disabled={disabled}
              rows={7}
              maxLength={4000}
              placeholder="请介绍你的设计，以及为什么这样设计（建议 120–220 字）…"
            />
          </>
        )}
        {saveError ? <p className="tiny error-text">自动保存失败：{saveError}</p> : null}

      </div>
      {roundNo === 2 ? (
        <p className="consent-note">
          提交即表示同意将今天的学习数据用于后续研究。
        </p>
      ) : null}
      <div className="creation-footer">
        <div className={`save-indicator footer-save save-${saveError ? "error" : "saved"}`}>
          {saveError ? "未保存 / Not saved" : "系统自动保存 / Autosaved"}
        </div>
        <button
          type="button"
          className="button button-primary button-wide"
          onClick={() => void finish()}
          disabled={disabled || finishing}
        >
          {finishing ? "正在结束… / Finishing…" : "✓ 保存并继续 / Save & Continue"}
        </button>
      </div>
    </section>
    {submitHintOpen ? (
      <div
        className="submit-hint-backdrop"
        role="dialog"
        aria-modal="true"
        aria-label="请下滑填写产品说明"
        onClick={() => setSubmitHintOpen(false)}
      >
        <div className="submit-hint-card">
          <div className="eyebrow">还差一点 / Almost there</div>
          <h3>请下滑填写产品说明后提交</h3>
          <p>Please scroll down and complete the product statement before submitting.</p>
          <p className="tiny muted">点击任意处关闭 / Click anywhere to close</p>
        </div>
      </div>
    ) : null}
    </>
  );
}

const RATIONALE_FIELD_DEFS: Array<{
  key: keyof RationaleFields;
  zh: string;
  en: string;
  hint: string;
  placeholder: string;
}> = [
  {
    key: "heritage_knowledge",
    zh: "① 你从文物中学到了什么？",
    en: "What you learned",
    hint: "建议 30–45 字：写一条与你的设计有关的具体文物知识，并注明资料章节或来源。",
    placeholder: "例如：鹭鸶与六品文官身份有关（M03）。",
  },
  {
    key: "cultural_translation",
    zh: "② 你怎样把它用到设计里？",
    en: "How you used it",
    hint: "建议 35–55 字：说明保留或改变了哪项纹样、功能、文化关系或故事意义。",
    placeholder: "例如：保留鹭鸶与莲塘的组合，把它转成徽章的主图。",
  },
  {
    key: "design_reason",
    zh: "③ 为什么这样设计？",
    en: "Why this design",
    hint: "建议 30–50 字：说明产品用途、目标人群，以及你作出这一设计选择的理由。",
    placeholder: "例如：面向青年博物馆观众，便于日常佩戴和识别。",
  },
];

const T1_FIELD_DEFS: Array<{
  key: keyof StructuredFields;
  zh: string;
  en: string;
  hint: string;
  placeholder: string;
}> = [
  {
    key: "cultural_features",
    zh: "① 文物与视觉特征",
    en: "Artifact & visual features",
    hint: "建议 25–50 字：你在文物中识别出的重要视觉、材料或结构特征。",
    placeholder: "例如：鹭鸶、莲塘纹样与方形服饰标识。",
  },
  {
    key: "historical_function",
    zh: "② 历史功能与社会文化意义",
    en: "Historical function & meaning",
    hint: "建议 40–70 字：说明它在原有历史语境中的功能、制度或文化关系。",
    placeholder: "例如：与明代文官的身份标识和服饰制度有关。",
  },
  {
    key: "sources_evidence",
    zh: "③ 信息与证据",
    en: "Information & evidence",
    hint: "建议 20–50 字：你依据了哪些资料？哪些地方仍不确定？",
    placeholder: "例如：依据左侧经过核实的馆藏资料；关于具体品级仍有不确定性。",
  },
  {
    key: "cultural_continuity",
    zh: "④ 文化知识的保留",
    en: "Cultural continuity",
    hint: "建议 30–60 字：哪些知识、形式或文化关系被你保留下来？",
    placeholder: "例如：保留纹样及其作为服饰标识的视觉结构。",
  },
  {
    key: "cultural_translation",
    zh: "⑤ 新情境的转译",
    en: "Translation into a new context",
    hint: "建议 40–70 字：哪些功能、身份或意义被重新解释到新的产品与受众中？",
    placeholder: "例如：从等级身份标识转化为现代服饰的个体表达。",
  },
  {
    key: "innovation_rationale",
    zh: "⑥ 创新与设计依据",
    en: "Innovation & rationale",
    hint: "建议 40–70 字：说明你的设计选择及其依据。",
    placeholder: "例如：宽松 T 恤、胸前小图和背面主题印花。",
  },
];
