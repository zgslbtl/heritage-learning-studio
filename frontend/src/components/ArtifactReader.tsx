import React from "react";
import { api } from "../api";
import type { Artifact, ArtifactMedia, ArtifactSection } from "../types";

type SectionLog = { openedAt: number | null };

function fallbackSections(artifact: Artifact): ArtifactSection[] {
  const sections: ArtifactSection[] = [];
  if (artifact.introduction) {
    sections.push({
      key: "introduction",
      title: "文物简介",
      body: artifact.introduction,
      source_ids: [],
      media_keys: [],
    });
  }
  if (artifact.facts?.length) {
    sections.push({
      key: "facts",
      title: "历史事实",
      body: artifact.facts.join("\n\n"),
      source_ids: [],
      media_keys: [],
    });
  }
  if (artifact.evidence?.length) {
    sections.push({
      key: "evidence",
      title: "相关证据",
      body: artifact.evidence.join("\n\n"),
      source_ids: [],
      media_keys: [],
    });
  }
  if (artifact.uncertainty?.length) {
    sections.push({
      key: "uncertainty",
      title: "仍待探究",
      body: artifact.uncertainty.join("\n\n"),
      source_ids: [],
      media_keys: [],
    });
  }
  return sections;
}

export default function ArtifactReader({
  artifact,
  roundNo,
  disabled,
}: {
  artifact: Artifact;
  roundNo: number;
  disabled: boolean;
}) {
  const sections = React.useMemo(
    () => (artifact.sections?.length ? artifact.sections : fallbackSections(artifact)),
    [artifact],
  );
  const media = React.useMemo(() => artifact.media || [], [artifact.media]);
  const byKey = React.useMemo(() => {
    const result: Record<string, ArtifactMedia> = {};
    for (const item of media) result[item.key] = item;
    return result;
  }, [media]);
  const [openKey, setOpenKey] = React.useState<string | null>(sections[0]?.key || null);
  const [lightbox, setLightbox] = React.useState<ArtifactMedia | null>(null);
  const openedAt = React.useRef<Record<string, number>>({});
  const openKeyRef = React.useRef(openKey);

  React.useEffect(() => {
    openKeyRef.current = openKey;
  }, [openKey]);

  React.useEffect(() => {
    if (!openKey) return;
    openedAt.current[openKey] = Date.now();
    record(openKey, "section_open", undefined, { initial: true });
    // Initial section is already expanded; log the exposure once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  React.useEffect(() => {
    if (!lightbox) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setLightbox(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [lightbox]);

  function record(
    section: string,
    eventType: string,
    durationMs?: number,
    meta?: Record<string, unknown>,
  ) {
    if (disabled) return;
    api(`/api/student/rounds/${roundNo}/evidence-events`, {
      method: "POST",
      body: {
        section,
        event_type: eventType,
        ...(durationMs !== undefined ? { duration_ms: durationMs } : {}),
        ...(meta ? { meta } : {}),
      },
    }).catch(() => {
      // Evidence logging must never interrupt reading or creation.
    });
  }

  function closeCurrent(nextKey: string | null) {
    const current = openKey;
    if (!current) return;
    const started = openedAt.current[current];
    record(current, "section_close", started ? Date.now() - started : undefined);
    delete openedAt.current[current];
    if (nextKey) {
      openedAt.current[nextKey] = Date.now();
      record(nextKey, "section_open");
    }
  }

  function toggle(key: string) {
    if (key === openKey) {
      closeCurrent(null);
      setOpenKey(null);
    } else {
      closeCurrent(key);
      setOpenKey(key);
    }
  }

  React.useEffect(() => {
    return () => {
      const current = openKeyRef.current;
      const started = current ? openedAt.current[current] : undefined;
      if (current && started) {
        record(current, "section_close", Date.now() - started);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const primary = media[0];
  const primaryUrl = primary?.url || artifact.image_url;
  const primaryAlt = primary?.alt || artifact.title;

  function openMedia(item: ArtifactMedia) {
    record(`media:${item.key}`, "media_open", undefined, {
      media_key: item.key,
      caption: item.caption,
    });
    setLightbox(item);
  }

  return (
    <section className="workspace-panel evidence-panel" aria-label="文物资料">
      <div className="panel-heading compact-heading">
        <div>
          <h2>文物资料</h2>
          <div className="en">Artifact evidence</div>
        </div>
        <span className="reader-hint">点击展开</span>
      </div>
      <div className="panel-scroll">
        <figure className="artifact-figure">
          <img src={primaryUrl} alt={primaryAlt} />
          <button
            type="button"
            className="image-zoom"
            aria-label="放大查看文物图片"
            onClick={() => primary && openMedia(primary)}
          >
            ⤢
          </button>
          {primary?.caption ? <figcaption>{primary.caption}</figcaption> : null}
        </figure>
        <h3 className="artifact-title">{artifact.title}</h3>
        <dl className="artifact-meta">
          <div>
            <dt>年代 / Era</dt>
            <dd>{artifact.era || "—"}</dd>
          </div>
          <div>
            <dt>类型 / Type</dt>
            <dd>{artifact.type || "—"}</dd>
          </div>
        </dl>

        <div className="artifact-section-list" aria-label="文物资料章节">
          {sections.map((section) => {
            const open = section.key === openKey;
            const sectionMedia = section.media_keys
              .map((key) => byKey[key])
              .filter(Boolean) as ArtifactMedia[];
            return (
              <div className={`artifact-section${open ? " is-open" : ""}`} key={section.key}>
                <button
                  type="button"
                  className="artifact-section-toggle"
                  aria-expanded={open}
                  onClick={() => toggle(section.key)}
                >
                  <span>{section.title}</span>
                  <span className="artifact-section-chevron" aria-hidden="true">
                    {open ? "−" : "+"}
                  </span>
                </button>
                {open ? (
                  <div className="artifact-section-body">
                    {section.body.split(/\n{2,}/).map((paragraph, index) => (
                      <p key={index}>{paragraph}</p>
                    ))}
                    {sectionMedia.length ? (
                      <div className="artifact-inline-gallery">
                        {sectionMedia.map((item) => (
                          <button
                            type="button"
                            className="artifact-inline-media"
                            key={item.key}
                            onClick={() => openMedia(item)}
                          >
                            <img src={item.url} alt={item.alt} loading="lazy" />
                            <span>{item.caption}</span>
                          </button>
                        ))}
                      </div>
                    ) : null}
                    {section.source_ids?.length ? (
                      <div className="artifact-sources" aria-label="本段来源">
                        {section.source_ids.map((source) => (
                          <button
                            type="button"
                            className="source-chip"
                            key={source}
                            onClick={() =>
                              record(`source:${source}`, "source_open", undefined, {
                                source_id: source,
                                section: section.key,
                              })
                            }
                          >
                            {source}
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>

        <p className="artifact-footnote">
          AI 只能依据以上资料回答；资料不足时，请允许它明确说明不确定之处。
        </p>
      </div>

      {lightbox ? (
        <div
          className="artifact-lightbox"
          role="dialog"
          aria-modal="true"
          aria-label={lightbox.caption || "文物图片"}
          onClick={() => setLightbox(null)}
        >
          <div className="artifact-lightbox-inner" onClick={(event) => event.stopPropagation()}>
            <button
              type="button"
              className="artifact-lightbox-close"
              aria-label="关闭图片"
              onClick={() => setLightbox(null)}
            >
              ×
            </button>
            <img src={lightbox.original_url} alt={lightbox.alt} />
            <div className="artifact-lightbox-caption">{lightbox.caption}</div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
