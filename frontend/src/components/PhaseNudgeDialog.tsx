import React from "react";

/**
 * Non-blocking prompt shown when a student keeps chatting inside one learning
 * phase without moving on.  It offers the hint, the next phase, or simply
 * carrying on.
 */
export default function PhaseNudgeDialog({
  phaseLabel,
  phaseLabelEn,
  hintUsed,
  onHint,
  onAdvance,
  onDismiss,
}: {
  phaseLabel: string;
  phaseLabelEn?: string;
  hintUsed: boolean;
  onHint: () => void;
  onAdvance: () => void;
  onDismiss: () => void;
}) {
  const primaryRef = React.useRef<HTMLButtonElement>(null);

  React.useEffect(() => {
    primaryRef.current?.focus();
  }, []);

  React.useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onDismiss();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onDismiss]);

  return (
    <div
      className="submit-hint-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="phase-nudge-title"
      onClick={onDismiss}
    >
      <div
        className="submit-hint-card phase-nudge-card"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="eyebrow">学习引导 / Learning Guide</div>
        <h3 id="phase-nudge-title">要进入下一阶段吗？</h3>
        <p>
          你在「{phaseLabel}」阶段已经对话 3 轮。可以点「获取一次提示」看看还能问什么，
          也可以直接进入下一阶段；想继续聊也没问题。
        </p>
        <p className="muted tiny">
          You have chatted for 3 turns in the {phaseLabelEn || phaseLabel} phase. Take a
          hint, move on to the next phase, or keep talking.
        </p>
        <div className="phase-nudge-actions">
          {hintUsed ? null : (
            <button type="button" className="button button-small button-ghost" onClick={onHint}>
              获取一次提示 / Hint
            </button>
          )}
          <button
            type="button"
            className="button button-small button-primary"
            ref={primaryRef}
            onClick={onAdvance}
          >
            进入下一阶段 / Next
          </button>
          <button type="button" className="text-button" onClick={onDismiss}>
            继续对话 / Keep chatting
          </button>
        </div>
      </div>
    </div>
  );
}
