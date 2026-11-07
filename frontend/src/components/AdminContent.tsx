import React from "react";
import { api, errorMessage, ApiError } from "../api";
import type {
  AdminArtifact,
  AdminInstrument,
  ArtifactSummary,
  InstrumentSummary,
  Question,
} from "../types";
import { ErrorNotice, Spinner } from "./common";

type ArtifactListing = Record<
  string,
  { latest: AdminArtifact | null; versions: ArtifactSummary[] }
>;
type InstrumentListing = Record<
  string,
  { latest: AdminInstrument | null; versions: InstrumentSummary[] }
>;

const KIND_NAMES: Record<string, string> = {
  k0: "K0 · 文物知识前测",
  k1: "K1 · T1 知识后测",
  k2: "K2 · T2 知识前测",
  k3: "K3 · T2 知识后测",
  survey: "体验问卷 / Survey",
};

export default function AdminContent({
  onChanged,
}: {
  onChanged: () => void;
}) {
  const [tab, setTab] = React.useState<"artifacts" | "instruments">("artifacts");
  const [artifacts, setArtifacts] = React.useState<ArtifactListing | null>(null);
  const [instruments, setInstruments] = React.useState<InstrumentListing | null>(null);
  const [selectedKind, setSelectedKind] = React.useState("k0");
  const [error, setError] = React.useState<{ message: string; requestId?: string } | null>(null);
  const [reloadToken, setReloadToken] = React.useState(0);

  const load = React.useCallback(async () => {
    setError(null);
    try {
      const [artifactData, instrumentData] = await Promise.all([
        api<ArtifactListing>("/api/admin/artifacts"),
        api<InstrumentListing>("/api/admin/instruments"),
      ]);
      setArtifacts(artifactData);
      setInstruments(instrumentData);
    } catch (err) {
      setError({
        message: errorMessage(err),
        requestId: err instanceof ApiError ? err.requestId : undefined,
      });
    }
  }, []);

  React.useEffect(() => {
    void load();
  }, [load, reloadToken]);

  function refresh() {
    setReloadToken((value) => value + 1);
    onChanged();
  }

  return (
    <div className="admin-content">
      <div className="admin-section-heading">
        <div>
          <div className="eyebrow">研究材料 / Study materials</div>
          <h1>文物证据包与测验</h1>
        </div>
        <div className="segmented">
          <button
            type="button"
            className={tab === "artifacts" ? "active" : ""}
            onClick={() => setTab("artifacts")}
          >
            文物 Evidence Packs
          </button>
          <button
            type="button"
            className={tab === "instruments" ? "active" : ""}
            onClick={() => setTab("instruments")}
          >
            测验与问卷 Instruments
          </button>
        </div>
      </div>
      <p className="muted">
        保存内容会创建不可变的新版本，不会修改学生已经开始的冻结协议。正式数据收集前需完成审核并重新激活协议。
      </p>
      {error ? <ErrorNotice message={error.message} requestId={error.requestId} /> : null}

      {tab === "artifacts" ? (
        artifacts ? (
          <div className="content-editor-grid">
            {["X", "Y"].map((slot) => (
              <ArtifactForm
                key={`${slot}-${artifacts[slot]?.latest?.id || "empty"}`}
                slot={slot}
                latest={artifacts[slot]?.latest || null}
                versions={artifacts[slot]?.versions || []}
                onSaved={refresh}
              />
            ))}
          </div>
        ) : (
          <Spinner label="加载文物证据包…" />
        )
      ) : instruments ? (
        <div className="instrument-editor-layout">
          <nav className="kind-nav">
            {Object.keys(KIND_NAMES).map((kind) => (
              <button
                key={kind}
                type="button"
                className={selectedKind === kind ? "active" : ""}
                onClick={() => setSelectedKind(kind)}
              >
                <span>{KIND_NAMES[kind]}</span>
                <span className="tiny muted">
                  {instruments[kind]?.latest
                    ? `v${instruments[kind].latest!.version}`
                    : "未配置"}
                </span>
              </button>
            ))}
          </nav>
          <InstrumentForm
            key={`${selectedKind}-${instruments[selectedKind]?.latest?.id || "empty"}`}
            kind={selectedKind}
            latest={instruments[selectedKind]?.latest || null}
            versions={instruments[selectedKind]?.versions || []}
            onSaved={refresh}
          />
        </div>
      ) : (
        <Spinner label="加载测验与问卷…" />
      )}
    </div>
  );
}

function ArtifactForm({
  slot,
  latest,
  versions,
  onSaved,
}: {
  slot: string;
  latest: AdminArtifact | null;
  versions: ArtifactSummary[];
  onSaved: () => void;
}) {
  const [title, setTitle] = React.useState(latest?.title || "");
  const [era, setEra] = React.useState(latest?.era || "");
  const [artifactType, setArtifactType] = React.useState(latest?.type || "");
  const [introduction, setIntroduction] = React.useState(latest?.introduction || "");
  const [facts, setFacts] = React.useState((latest?.facts || []).join("\n"));
  const [evidence, setEvidence] = React.useState((latest?.evidence || []).join("\n"));
  const [uncertainty, setUncertainty] = React.useState((latest?.uncertainty || []).join("\n"));
  const [imageFile, setImageFile] = React.useState<File | null>(null);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [notice, setNotice] = React.useState<string | null>(null);
  const formalSections = Boolean(latest?.sections?.length);

  function lines(value: string): string[] {
    return value
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const form = new FormData();
      form.append("title", title);
      form.append("era", era);
      form.append("artifact_type", artifactType);
      form.append("introduction", introduction);
      form.append("facts_json", JSON.stringify(lines(facts)));
      form.append("evidence_json", JSON.stringify(lines(evidence)));
      form.append("uncertainty_json", JSON.stringify(lines(uncertainty)));
      if (imageFile) {
        const upload = await api<{ direct_upload: boolean; upload_id?: string; url?: string; headers?: Record<string, string> }>("/api/admin/uploads", {
          method: "POST", body: { size: imageFile.size, mime: imageFile.type },
        });
        if (upload.direct_upload && upload.url && upload.upload_id) {
          const response = await fetch(upload.url, { method: "PUT", headers: upload.headers, body: imageFile, credentials: "omit" });
          if (!response.ok) throw new Error("图片上传失败，请重试。 / Image upload failed.");
          form.append("upload_id", upload.upload_id);
        } else {
          form.append("image", imageFile);
        }
      }
      const result = await api<{ artifact: AdminArtifact }>(
        `/api/admin/artifacts/${slot}/versions`,
        { method: "POST", body: form },
      );
      setNotice(`已创建 v${result.artifact.version}，后续学生将使用最新协议内容（若尚未收集数据）。`);
      setImageFile(null);
      onSaved();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="content-editor panel" onSubmit={save}>
      <div className="section-heading-row">
        <div>
          <div className="eyebrow">Evidence Pack {slot}</div>
          <h2>文物 {slot}</h2>
        </div>
        <span className="version-chip">{latest ? `v${latest.version}` : "未配置"}</span>
      </div>
      {latest?.is_demo ? (
        <div className="notice notice-warning small-notice">演示占位内容，不可用于正式研究。</div>
      ) : null}
      {formalSections ? (
        <div className="notice notice-info small-notice">
          正式章节与高清图片已由导入脚本写入。为避免丢失章节，请勿用此简化编辑器保存；
          内容修订请通过新的正式内容版本导入。
        </div>
      ) : null}
      {latest?.image_url ? (
        <img className="admin-artifact-preview" src={latest.image_url} alt={latest.title} />
      ) : null}
      <label>
        标题 / Title
        <input value={title} onChange={(event) => setTitle(event.target.value)} required maxLength={200} />
      </label>
      <div className="two-col">
        <label>
          年代 / Era
          <input value={era} onChange={(event) => setEra(event.target.value)} maxLength={120} />
        </label>
        <label>
          类型 / Type
          <input
            value={artifactType}
            onChange={(event) => setArtifactType(event.target.value)}
            maxLength={120}
          />
        </label>
      </div>
      <label>
        简介 / Introduction
        <textarea
          value={introduction}
          onChange={(event) => setIntroduction(event.target.value)}
          rows={5}
        />
      </label>
      <label>
        历史事实 / Facts（每行一条）
        <textarea value={facts} onChange={(event) => setFacts(event.target.value)} rows={5} />
      </label>
      <label>
        来源证据 / Evidence（每行一条）
        <textarea
          value={evidence}
          onChange={(event) => setEvidence(event.target.value)}
          rows={5}
        />
      </label>
      <label>
        待探究 / Uncertainty（每行一条）
        <textarea
          value={uncertainty}
          onChange={(event) => setUncertainty(event.target.value)}
          rows={3}
        />
      </label>
      <label>
        图片 / Image {latest ? "（不选择则沿用当前图片）" : "（首次配置必须选择）"}
        <input
          type="file"
          accept="image/png,image/jpeg,image/webp"
          onChange={(event) => setImageFile(event.target.files?.[0] || null)}
        />
      </label>
      <div className="notice notice-info small-notice">
        保存将创建一个新的不可变版本 {latest ? `v${latest.version + 1}` : "v1"}。
      </div>
      {error ? <ErrorNotice message={error} /> : null}
      {notice ? <div className="notice notice-success">{notice}</div> : null}
      <button
        type="submit"
        className="button button-primary"
        disabled={saving || !title.trim() || formalSections}
      >
        {saving ? "保存中…" : "保存为新版本 / Save version"}
      </button>
      {versions.length ? (
        <details className="admin-accordion">
          <summary>历史版本 / Versions ({versions.length})</summary>
          <ul className="plain-list">
            {versions.map((version) => (
              <li key={version.id}>
                v{version.version} · {version.title} ·{" "}
                {new Date(version.created_at).toLocaleString()} {version.is_demo ? "· DEMO" : ""}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </form>
  );
}

function defaultQuestion(type: Question["type"], index: number): Question {
  const id = `q${index}_${Date.now().toString(36).slice(-4)}`;
  const base: Question = {
    id,
    type,
    prompt: "",
    required: true,
  };
  if (type === "single_choice" || type === "multi_choice") {
    base.options = [
      { value: "a", label: "选项 A / Option A" },
      { value: "b", label: "选项 B / Option B" },
    ];
  }
  if (type === "short_text") base.max_length = 200;
  if (type === "evidence_judgment") {
    base.rows = [{ id: "row1", label: "材料条目 / Evidence item" }];
  }
  if (type === "likert") {
    base.scale_min = 1;
    base.scale_max = 5;
    base.scale_labels = ["低 / Low", "", "中 / Mid", "", "高 / High"];
  }
  return base;
}

function InstrumentForm({
  kind,
  latest,
  versions,
  onSaved,
}: {
  kind: string;
  latest: AdminInstrument | null;
  versions: InstrumentSummary[];
  onSaved: () => void;
}) {
  const [title, setTitle] = React.useState(latest?.title || KIND_NAMES[kind]);
  const [instructions, setInstructions] = React.useState(latest?.instructions || "");
  const [questions, setQuestions] = React.useState<Question[]>(
    latest ? JSON.parse(JSON.stringify(latest.questions)) : [defaultQuestion("short_text", 1)],
  );
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [notice, setNotice] = React.useState<string | null>(null);
  const formalForm = Boolean(latest?.object_code);

  function update(index: number, patch: Partial<Question>) {
    setQuestions((current) =>
      current.map((question, idx) => (idx === index ? { ...question, ...patch } : question)),
    );
  }

  function changeType(index: number, type: Question["type"]) {
    setQuestions((current) =>
      current.map((question, idx) =>
        idx === index ? { ...defaultQuestion(type, index + 1), id: question.id, prompt: question.prompt, required: question.required } : question,
      ),
    );
  }

  function serialize(question: Question): Record<string, unknown> {
    const result: Record<string, unknown> = {
      id: question.id,
      type: question.type,
      prompt: question.prompt,
      required: question.required,
    };
    if (question.type === "single_choice" || question.type === "multi_choice") {
      result.options = question.options || [];
    }
    if (question.type === "short_text") {
      result.max_length = question.max_length || 200;
    }
    if (question.type === "evidence_judgment") {
      result.rows = question.rows || [];
    }
    if (question.type === "likert") {
      result.scale_min = question.scale_min || 1;
      result.scale_max = question.scale_max || 5;
      result.scale_labels = question.scale_labels || [];
    }
    return result;
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const payload = {
        title,
        instructions,
        questions: questions.map(serialize),
      };
      const result = await api<{ instrument: AdminInstrument }>(
        `/api/admin/instruments/${kind}/versions`,
        { method: "POST", body: payload },
      );
      setNotice(`已创建 v${result.instrument.version}。`);
      onSaved();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="content-editor panel instrument-editor" onSubmit={save}>
      <div className="section-heading-row">
        <div>
          <div className="eyebrow">{KIND_NAMES[kind]}</div>
          <h2>题目编辑</h2>
        </div>
        <span className="version-chip">{latest ? `v${latest.version}` : "未配置"}</span>
      </div>
      {latest?.is_demo ? (
        <div className="notice notice-warning small-notice">演示占位问卷，不可用于正式研究。</div>
      ) : null}
      {formalForm ? (
        <div className="notice notice-info small-notice">
          正式平行题本已由导入脚本写入（{latest?.object_code}-{latest?.form_code}）。
          此简化编辑器不保存 form 元数据；正式题本修订请通过新的内容版本导入。
        </div>
      ) : null}
      <label>
        标题 / Title
        <input value={title} onChange={(event) => setTitle(event.target.value)} required />
      </label>
      <label>
        说明 / Instructions
        <textarea
          value={instructions}
          onChange={(event) => setInstructions(event.target.value)}
          rows={3}
        />
      </label>

      <div className="question-builder">
        {questions.map((question, index) => (
          <div className="builder-question" key={`${question.id}-${index}`}>
            <div className="builder-question-head">
              <span className="question-number">{index + 1}</span>
              <input
                className="id-input"
                value={question.id}
                onChange={(event) => update(index, { id: event.target.value })}
                aria-label="Question ID"
                required
              />
              <select
                value={question.type}
                onChange={(event) => changeType(index, event.target.value as Question["type"])}
                aria-label="Question type"
              >
                <option value="single_choice">单选 / Single choice</option>
                <option value="multi_choice">多选 / Multiple choice</option>
                <option value="short_text">简答 / Short text</option>
                <option value="evidence_judgment">证据判断 / Evidence judgement</option>
                <option value="likert">量表 / Likert</option>
              </select>
              <label className="inline-check">
                <input
                  type="checkbox"
                  checked={question.required}
                  onChange={(event) => update(index, { required: event.target.checked })}
                />
                必答
              </label>
              <button
                type="button"
                className="text-button danger"
                onClick={() => setQuestions((current) => current.filter((_, idx) => idx !== index))}
                disabled={questions.length <= 1}
              >
                删除
              </button>
            </div>
            <textarea
              value={question.prompt}
              onChange={(event) => update(index, { prompt: event.target.value })}
              placeholder="题目文本 / Question prompt"
              rows={2}
              required
            />
            {question.type === "single_choice" || question.type === "multi_choice" ? (
              <label>
                选项（每行 value|label）
                <textarea
                  value={(question.options || []).map((option) => `${option.value}|${option.label}`).join("\n")}
                  onChange={(event) =>
                    update(index, {
                      options: event.target.value
                        .split("\n")
                        .map((line) => line.trim())
                        .filter(Boolean)
                        .map((line) => {
                          const [value, ...label] = line.split("|");
                          return { value: value.trim(), label: (label.join("|") || value).trim() };
                        }),
                    })
                  }
                  rows={3}
                />
              </label>
            ) : null}
            {question.type === "short_text" ? (
              <label>
                最大字数
                <input
                  type="number"
                  min={1}
                  max={4000}
                  value={question.max_length || 200}
                  onChange={(event) => update(index, { max_length: Number(event.target.value) })}
                />
              </label>
            ) : null}
            {question.type === "evidence_judgment" ? (
              <label>
                材料行（每行 id|label）
                <textarea
                  value={(question.rows || []).map((row) => `${row.id}|${row.label}`).join("\n")}
                  onChange={(event) =>
                    update(index, {
                      rows: event.target.value
                        .split("\n")
                        .map((line) => line.trim())
                        .filter(Boolean)
                        .map((line) => {
                          const [id, ...label] = line.split("|");
                          return { id: id.trim(), label: (label.join("|") || id).trim() };
                        }),
                    })
                  }
                  rows={3}
                />
              </label>
            ) : null}
            {question.type === "likert" ? (
              <div className="two-col">
                <label>
                  最小
                  <input
                    type="number"
                    value={question.scale_min || 1}
                    onChange={(event) => update(index, { scale_min: Number(event.target.value) })}
                  />
                </label>
                <label>
                  最大
                  <input
                    type="number"
                    value={question.scale_max || 5}
                    onChange={(event) => update(index, { scale_max: Number(event.target.value) })}
                  />
                </label>
              </div>
            ) : null}
          </div>
        ))}
      </div>
      <div className="button-row">
        <button
          type="button"
          className="button"
          onClick={() => setQuestions((current) => [...current, defaultQuestion("short_text", current.length + 1)])}
        >
          + 添加题目 / Add question
        </button>
      </div>
      {error ? <ErrorNotice message={error} /> : null}
      {notice ? <div className="notice notice-success">{notice}</div> : null}
      <button
        type="submit"
        className="button button-primary"
        disabled={saving || !title.trim() || formalForm}
      >
        {saving ? "保存中…" : "保存为新版本 / Save version"}
      </button>
      {versions.length ? (
        <details className="admin-accordion">
          <summary>历史版本 / Versions ({versions.length})</summary>
          <ul className="plain-list">
            {versions.map((version) => (
              <li key={version.id}>
                v{version.version} · {version.title} ·{" "}
                {new Date(version.created_at).toLocaleString()}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </form>
  );
}
