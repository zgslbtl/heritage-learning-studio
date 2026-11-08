import React from "react";
import { api, errorMessage, ApiError } from "../api";
import { ErrorNotice, Spinner } from "./common";

interface Detail {
  participant: {
    id: string;
    class_name: string;
    group: string;
    email: string | null;
    code_last4: string | null;
    created_at: string;
  };
  run: {
    id: string;
    stage: string;
    stage_label: string;
    created_at: string;
    last_activity_at: string;
    completed_at: string | null;
    protocol: Record<string, unknown> | null;
  } | null;
  stage_events: any[];
  rounds: any[];
  scripts: any[];
  works: any[];
  peer_assignments: any[];
  peer_scores_received: Array<{
    round_no: number;
    work_code: string;
    rating_count: number;
    review_version?: string;
    cultural_clarity_mean?: number | null;
    cultural_translation_mean?: number | null;
    design_originality_mean?: number | null;
    clarity_mean?: number | null;
    evidence_link_mean?: number | null;
    attraction_mean?: number | null;
    image_available?: boolean;
  }>;
  social_events: any[];
  messages: any[];
  hlsf_events: any[];
  evidence_events: any[];
  image_jobs: any[];
  assessments: any[];
  ai_calls: any[];
  api_errors: any[];
}

export default function ParticipantDetail({
  participantId,
  onBack,
}: {
  participantId: string;
  onBack: () => void;
}) {
  const [detail, setDetail] = React.useState<Detail | null>(null);
  const [error, setError] = React.useState<{ message: string; requestId?: string } | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    api<Detail>(`/api/admin/participants/${participantId}`)
      .then((data) => {
        if (!cancelled) setDetail(data);
      })
      .catch((err) => {
        if (!cancelled) {
          setError({
            message: errorMessage(err),
            requestId: err instanceof ApiError ? err.requestId : undefined,
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [participantId]);

  if (error) {
    return (
      <div className="admin-detail">
        <button className="text-button" onClick={onBack}>
          ← 返回列表 / Back
        </button>
        <ErrorNotice message={error.message} requestId={error.requestId} />
      </div>
    );
  }
  if (!detail) {
    return (
      <div className="admin-detail">
        <Spinner label="加载参与者详情…" />
      </div>
    );
  }

  return (
    <div className="admin-detail" data-testid="participant-detail">
      <button className="text-button" onClick={onBack}>
        ← 返回列表 / Back
      </button>
      <div className="admin-section-heading">
        <div>
          <div className="eyebrow">参与者详情 / Participant detail</div>
          <h1>{detail.participant.id.slice(0, 8).toUpperCase()}</h1>
        </div>
        <span className="group-badge">{detail.participant.group}</span>
      </div>
      <div className="detail-meta-grid">
        <div>
          <span className="label">班级</span>
          <strong>{detail.participant.class_name}</strong>
        </div>
        <div>
          <span className="label">内部标识</span>
          <strong>{detail.participant.email || `••••${detail.participant.code_last4 || ""}`}</strong>
        </div>
        <div>
          <span className="label">阶段</span>
          <strong>{detail.run?.stage_label || "尚未进入"}</strong>
        </div>
        <div>
          <span className="label">最近活动</span>
          <strong>{detail.run ? new Date(detail.run.last_activity_at).toLocaleString() : "—"}</strong>
        </div>
        <div>
          <span className="label">条件顺序</span>
          <strong>
            {detail.rounds.length
              ? detail.rounds.map((round) => `${round.condition}${round.round_no}`).join(" → ")
              : "—"}
          </strong>
        </div>
        <div>
          <span className="label">完成</span>
          <strong>{detail.run?.completed_at ? "是 / Yes" : "否 / No"}</strong>
        </div>
      </div>

      {detail.rounds.map((round) => (
        <section key={round.round_no} className="admin-subsection">
          <h2>
            第 {round.round_no} 轮 · 条件 {round.condition} · {round.artifact?.title}
          </h2>
          <div className="detail-meta-grid">
            <div>
              <span className="label">开始</span>
              <strong>{new Date(round.started_at).toLocaleString()}</strong>
            </div>
            <div>
              <span className="label">截止</span>
              <strong>{new Date(round.deadline_at).toLocaleString()}</strong>
            </div>
            <div>
              <span className="label">结束</span>
              <strong>{round.finished_at ? new Date(round.finished_at).toLocaleString() : "进行中"}</strong>
            </div>
            <div>
              <span className="label">结束原因</span>
              <strong>{round.finish_reason || "—"}</strong>
            </div>
          </div>
          {round.artifact ? (
            <div className="detail-artifact">
              <img src={round.artifact.image_url} alt={round.artifact.title} />
              <p className="small muted">{round.artifact.introduction}</p>
            </div>
          ) : null}
        </section>
      ))}

      <div className="detail-columns">
        <section className="admin-subsection">
          <h2>完整对话 / Messages ({detail.messages.length})</h2>
          <div className="admin-message-log">
            {detail.messages.map((message) => (
              <div key={message.id} className={`admin-message ${message.role}`}>
                <div className="tiny muted">
                  R{message.round_no} · {message.role} · {message.source} ·{" "}
                  {new Date(message.created_at).toLocaleString()}
                </div>
                <pre>{message.content}</pre>
              </div>
            ))}
            {!detail.messages.length ? <p className="muted">暂无对话。</p> : null}
          </div>
        </section>

        <section className="admin-subsection">
          <h2>脚本版本 / Scripts ({detail.scripts.length})</h2>
          {detail.scripts.map((script) => (
            <details key={`${script.round_no}-${script.revision_no}`} className="admin-accordion">
              <summary>
                R{script.round_no} · v{script.revision_no} · {script.title || "(untitled)"} ·{" "}
                {new Date(script.created_at).toLocaleTimeString()}
              </summary>
              <pre>{script.body}</pre>
            </details>
          ))}
          {!detail.scripts.length ? <p className="muted">暂无脚本。</p> : null}
        </section>
      </div>

      <div className="detail-columns">
        <section className="admin-subsection">
          <h2>文创作品 / Product works ({detail.works.length})</h2>
          {detail.works.map((work) => (
            <details key={`${work.round_no}-${work.revision_no}`} className="admin-accordion">
              <summary>
                {work.round_no === 1 ? "T1" : "T2"} · v{work.revision_no} ·{" "}
                {work.product_name || "(untitled)"} · {work.product_category}
              </summary>
              <pre>
                {JSON.stringify(
                  {
                    design_concept: work.design_concept,
                    structured_fields: work.structured_fields,
                    rationale_fields: work.rationale_fields,
                    open_statement: work.open_statement,
                  },
                  null,
                  2,
                )}
              </pre>
            </details>
          ))}
          {!detail.works.length ? <p className="muted">暂无文创作品。</p> : null}
        </section>

        <section className="admin-subsection">
          <h2>概念图任务 / Concept images</h2>
          {detail.image_jobs.map((job) => (
            <div key={job.id} className="admin-accordion static">
              <div>
                <strong>{job.status}</strong> · R{job.round_no} · attempt {job.attempts}
              </div>
              {job.error_message ? <p className="error-text small">{job.error_message}</p> : null}
              {job.image_url ? <img className="admin-job-image" src={job.image_url} alt="concept image" /> : null}
              <details>
                <summary>Prompt</summary>
                <pre>{job.prompt}</pre>
              </details>
            </div>
          ))}
          {!detail.image_jobs.length ? <p className="muted">暂无图片任务。</p> : null}
        </section>

        <section className="admin-subsection">
          <h2>研究问卷 / Assessments</h2>
          {detail.assessments.map((assessment) => (
            <details key={assessment.kind} className="admin-accordion">
              <summary>
                {assessment.kind} · {assessment.status} ·{" "}
                {assessment.duration_seconds != null ? `${assessment.duration_seconds}s` : "—"}
              </summary>
              <pre>{JSON.stringify(assessment.answers, null, 2)}</pre>
            </details>
          ))}
          {!detail.assessments.length ? <p className="muted">暂无问卷记录。</p> : null}
        </section>
      </div>

      <div className="detail-columns">
        <section className="admin-subsection">
          <h2>收到的互评成绩（T1 / T2）</h2>
          {detail.peer_scores_received?.length ? (
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>轮次</th>
                    <th>作品</th>
                    <th>版本</th>
                    <th>评分人数</th>
                    <th>P1 清晰</th>
                    <th>P2 转译</th>
                    <th>P3 创意</th>
                    <th>图片</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.peer_scores_received.map((score) => {
                    const v21 = (score.review_version || "").startsWith(
                      "peer-review-v2.1",
                    );
                    return (
                      <tr key={`${score.round_no}-${score.work_code}`}>
                        <td>{score.round_no === 1 ? "T1" : "T2"}</td>
                        <td>{score.work_code}</td>
                        <td className="tiny muted">{score.review_version || "—"}</td>
                        <td>{score.rating_count}</td>
                        <td>
                          {v21
                            ? score.cultural_clarity_mean ?? "—"
                            : score.clarity_mean ?? "—"}
                        </td>
                        <td>
                          {v21
                            ? score.cultural_translation_mean ?? "—"
                            : score.evidence_link_mean ?? "—"}
                        </td>
                        <td>
                          {v21
                            ? score.design_originality_mean ?? "—"
                            : score.attraction_mean ?? "—"}
                        </td>
                        <td>{score.image_available ? "有" : "无"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted">暂无收到的互评成绩。</p>
          )}
          <h2>我给出的互评 / 社交事件</h2>
          <pre className="compact-json">
            {JSON.stringify(
              { peer: detail.peer_assignments, social: detail.social_events },
              null,
              2,
            )}
          </pre>
        </section>

        <section className="admin-subsection">
          <h2>HLSF / 资料事件</h2>
          <pre className="compact-json">
            {JSON.stringify(
              { hlsf: detail.hlsf_events, evidence: detail.evidence_events },
              null,
              2,
            )}
          </pre>
        </section>
        <section className="admin-subsection">
          <h2>阶段时间 / Stage events</h2>
          <pre className="compact-json">{JSON.stringify(detail.stage_events, null, 2)}</pre>
        </section>
      </div>

      <section className="admin-subsection">
        <h2>AI 调用与错误 / AI calls and errors</h2>
        {detail.api_errors.length ? (
          <div className="notice notice-error">
            <strong>API errors</strong>
            <pre>{JSON.stringify(detail.api_errors, null, 2)}</pre>
          </div>
        ) : null}
        {detail.ai_calls.map((call) => (
          <details key={call.id} className="admin-accordion">
            <summary>
              {call.status} · {call.purpose} · {call.prompt_version} · {call.latency_ms ?? "—"}ms
            </summary>
            <pre>{JSON.stringify(call, null, 2)}</pre>
          </details>
        ))}
      </section>
    </div>
  );
}
