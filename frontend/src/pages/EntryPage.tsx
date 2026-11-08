import React from "react";
import { api, errorMessage } from "../api";
import type { StudentState } from "../types";
import { BrandMark, ErrorNotice, Spinner } from "../components/common";
import { StageSchedule } from "../components/StageSchedule";

export default function EntryPage({
  onEnter,
}: {
  onEnter: (state: StudentState) => void;
}) {
  const [email, setEmail] = React.useState("");
  const [classId, setClassId] = React.useState(0);
  const [classes, setClasses] = React.useState<{ id: number; name: string }[]>([]);
  const [configLoading, setConfigLoading] = React.useState(true);
  const [beta, setBeta] = React.useState(false);
  const [linkValid, setLinkValid] = React.useState(true);
  const [classToken, setClassToken] = React.useState<string | null>(null);
  const [classLocked, setClassLocked] = React.useState(false);
  const [linkLoading, setLinkLoading] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<{ message: string; requestId?: string } | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    api<{ deployment_mode: string; classes: { id: number; name: string }[] }>("/api/auth/config")
      .then((data) => {
        if (cancelled) return;
        if (!Array.isArray(data.classes) || !data.classes.length) throw new Error("入口配置不可用，请稍后重试。");
        setClasses(data.classes);
        setBeta(data.deployment_mode === "beta");
        setClassId((current) => data.classes.some((item) => item.id === current) ? current : data.classes[0]?.id ?? 0);
      })
      .catch((err) => { if (!cancelled) setError({ message: errorMessage(err) }); })
      .finally(() => { if (!cancelled) setConfigLoading(false); });
    return () => { cancelled = true; };
  }, []);

  React.useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("token");
    if (!token) return;
    setClassToken(token);
    setLinkValid(false);
    setLinkLoading(true);
    api<{ class_id: number; class_name: string; label: string }>(
      `/api/auth/class-link?token=${encodeURIComponent(token)}`,
    )
      .then((data) => {
        setClassId(data.class_id);
        setClassLocked(true);
        setLinkValid(true);
      })
      .catch((err) => {
        setError({ message: errorMessage(err) });
        setClassLocked(true);
      })
      .finally(() => setLinkLoading(false));
  }, []);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const result = await api<{ state: StudentState }>("/api/auth/enter", {
        method: "POST",
        body: {
          email: email.trim(),
          class_id: classId,
          ...(classToken ? { class_token: classToken } : {}),
        },
      });
      onEnter(result.state);
    } catch (err) {
      setError({
        message: errorMessage(err),
        requestId: err instanceof Error && "requestId" in err ? String((err as any).requestId || "") : undefined,
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="app-shell entry-shell">
      <header className="topbar">
        <BrandMark />
        <div className="mode-chip">{beta ? "班级0 · 内部测试 / Internal testing" : "学生模式 / Student Mode"}</div>
        <div className="topbar-spacer" />
        <a className="subtle-link" href="/admin">
          研究者后台 / Researcher
        </a>
      </header>

      <main className="entry-layout">
        <section className="entry-hero">
          <div className="hero-medallion" aria-hidden="true">
            <div className="hero-clouds" />
            <div className="hero-symbol">文</div>
          </div>
          <h1 className="hero-brief">
            <span className="brief-scenario">
              假设博物馆正在策划一场丝绸文化主题推广活动，希望通过具有创造性的设计，让更多公众对馆藏文物产生兴趣，并理解其背后的历史与文化。
            </span>
            <span className="brief-task">
              邀请你使用我们的设计平台与 AI 一起共创，设计 2 件作品，既能吸引公众，也要具有清楚的文化解释价值。
            </span>
            <span className="en">
              Imagine the museum is planning a promotional campaign on silk culture. Through
              creative design, it hopes to spark greater public interest in the collection and
              in the history and culture behind it. You are invited to co-create with AI on our
              design platform: design 2 works that both attract the public and offer clear
              cultural interpretation.
            </span>
          </h1>
          <p>
            本次工作坊约 94 分钟：你将在 AI 辅助下阅读文物资料、理解文化内涵，
            并完成两次文创设计。
          </p>
          <p className="muted">
            The workshop runs about 94 minutes: with AI support you will read about the objects,
            interpret their cultural meanings, and complete two design works.
          </p>
          <div className="notice notice-info">
            平台会保存你输入的邮箱用于登录和防止重复参与；邮箱仅供研究团队内部使用，
            学习数据以匿名编号进行分析。请勿使用他人邮箱。
          </div>
        </section>

        <section className="entry-main">
          <div className="panel">
            <div className="panel-heading">
              <div>
                <h2>进入平台</h2>
                <div className="en">Enter the Platform</div>
              </div>
              <span className="step-badge">第 1 步 / Step 1</span>
            </div>
            <p className="muted">
              {classLocked
                ? "班级已由专属链接锁定，请输入包含 polyu 的邮箱。"
                : beta ? "内部测试仅开放班级0，请输入包含 polyu 的邮箱。" : "请输入你的 PolyU 邮箱并选择班级。"}
              <span className="en">
                {classLocked
                  ? "Your class is fixed by the class link. Enter an address containing polyu."
                  : beta ? "Internal testing uses Class 0. Enter an address containing polyu." : "Enter your PolyU email and select your class."}
              </span>
            </p>
            <form onSubmit={submit} className="entry-form">
              <label>
                PolyU 邮箱 <span className="en">PolyU Email</span>
                <input
                  type="text"
                  inputMode="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  maxLength={320}
                  autoComplete="email"
                  spellCheck={false}
                  placeholder="yourname@polyu.edu.hk"
                  aria-label="PolyU email"
                  required
                />
              </label>
              <label>
                所属班级 <span className="en">Class</span>
                <select
                  value={classId}
                  onChange={(event) => setClassId(Number(event.target.value))}
                  aria-label="Class"
                  disabled={classLocked || linkLoading}
                >
                  {classes.map(({ id, name }) => (
                    <option key={id} value={id}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
              <button
                className="button button-primary"
                type="submit"
                disabled={submitting || linkLoading || configLoading || !linkValid || !classes.length || !email.trim()}
              >
                {linkLoading
                  ? "正在验证班级链接… / Checking link…"
                  : submitting
                    ? "正在进入… / Entering…"
                    : "开始创作 / Start"}
              </button>
            </form>
            {error ? (
              <ErrorNotice message={error.message} requestId={error.requestId} />
            ) : null}
            <p className="tiny muted">
              使用同一个邮箱再次进入会恢复原有进度；同一邮箱只能创建一个参与者记录。
              <span className="en">
                Re-entering the same email restores your progress; one email can create only one participant record.
              </span>
            </p>
          </div>

          <StageSchedule currentStep={1} />
        </section>
      </main>
    </div>
  );
}
