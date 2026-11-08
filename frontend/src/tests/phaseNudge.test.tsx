import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import PhaseNudgeDialog from "../components/PhaseNudgeDialog";
import {
  countUserTurnsInPhase,
  isPhaseNudgeDue,
  supportsPhaseNudge,
} from "../hooks/usePhaseNudge";
import type { ChatMessage, Guide } from "../types";

function message(id: number, role: "user" | "assistant", source = "student"): ChatMessage {
  return {
    id,
    role,
    source,
    content: role === "user" ? "question" : "answer",
    created_at: "2026-11-08T10:00:00Z",
  };
}

const guide: Guide = {
  version: "hlsf-v1.10-evidence-reading-pilot",
  phase: "observe",
  hint_used: false,
  completed_at: null,
  phases: [
    { id: "observe", label_zh: "观察", label_en: "Observe" },
    { id: "explain", label_zh: "解释", label_en: "Explain" },
  ],
};

describe("countUserTurnsInPhase", () => {
  it("counts student messages after the phase prompt", () => {
    const messages = [
      message(1, "assistant", "hlsf_prompt"),
      message(2, "user"),
      message(3, "assistant"),
      message(4, "user"),
    ];
    expect(countUserTurnsInPhase(messages)).toBe(2);
  });

  it("does not reset on hint messages", () => {
    const messages = [
      message(1, "assistant", "hlsf_prompt"),
      message(2, "user"),
      message(3, "assistant", "hlsf_hint"),
      message(4, "user"),
    ];
    expect(countUserTurnsInPhase(messages)).toBe(2);
  });

  it("resets when the next phase prompt arrives", () => {
    const messages = [
      message(1, "assistant", "hlsf_prompt"),
      message(2, "user"),
      message(3, "user"),
      message(4, "assistant", "hlsf_prompt"),
      message(5, "user"),
    ];
    expect(countUserTurnsInPhase(messages)).toBe(1);
  });
});

describe("isPhaseNudgeDue", () => {
  const base = {
    guide,
    messages: [
      message(1, "assistant", "hlsf_prompt"),
      message(2, "user"),
      message(3, "user"),
      message(4, "user"),
    ],
    dismissed: false,
    disabled: false,
    busy: false,
    composerEmpty: true,
  };

  it("is due from the third student turn in a v1.10 phase", () => {
    expect(isPhaseNudgeDue(base)).toBe(true);
    expect(isPhaseNudgeDue({ ...base, messages: base.messages.slice(0, 3) })).toBe(false);
  });

  it("stays quiet for older prompt versions, dismissals and busy states", () => {
    expect(supportsPhaseNudge({ ...guide, version: "hlsf-v1.9-open-design-exploration-pilot" })).toBe(
      false,
    );
    expect(isPhaseNudgeDue({ ...base, guide: { ...guide, version: "hlsf-v1.9-x" } })).toBe(false);
    expect(isPhaseNudgeDue({ ...base, dismissed: true })).toBe(false);
    expect(isPhaseNudgeDue({ ...base, disabled: true })).toBe(false);
    expect(isPhaseNudgeDue({ ...base, busy: true })).toBe(false);
    expect(isPhaseNudgeDue({ ...base, composerEmpty: false })).toBe(false);
  });

  it("never fires once the guide is complete", () => {
    expect(isPhaseNudgeDue({ ...base, guide: { ...guide, phase: "complete" } })).toBe(false);
  });
});

describe("PhaseNudgeDialog", () => {
  it("offers hint, next phase and continuing", async () => {
    const onHint = vi.fn();
    const onAdvance = vi.fn();
    const onDismiss = vi.fn();
    render(
      <PhaseNudgeDialog
        phaseLabel="观察"
        phaseLabelEn="Observe"
        hintUsed={false}
        onHint={onHint}
        onAdvance={onAdvance}
        onDismiss={onDismiss}
      />,
    );
    expect(screen.getByRole("dialog")).toHaveAttribute("aria-modal", "true");
    await userEvent.click(screen.getByRole("button", { name: /获取一次提示/ }));
    expect(onHint).toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: /进入下一阶段/ }));
    expect(onAdvance).toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: /继续对话/ }));
    expect(onDismiss).toHaveBeenCalled();
  });

  it("hides the hint once it has been used", () => {
    render(
      <PhaseNudgeDialog
        phaseLabel="观察"
        hintUsed
        onHint={vi.fn()}
        onAdvance={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );
    expect(screen.queryByRole("button", { name: /获取一次提示/ })).not.toBeInTheDocument();
  });

  it("closes on escape", () => {
    const onDismiss = vi.fn();
    render(
      <PhaseNudgeDialog
        phaseLabel="观察"
        hintUsed={false}
        onHint={vi.fn()}
        onAdvance={vi.fn()}
        onDismiss={onDismiss}
      />,
    );
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onDismiss).toHaveBeenCalled();
  });
});
