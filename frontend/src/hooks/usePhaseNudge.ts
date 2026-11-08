import React from "react";
import type { ChatMessage, Guide } from "../types";

/** Chats allowed inside one learning phase before the stall prompt appears. */
export const NUDGE_TURN_THRESHOLD = 3;
const NUDGE_VERSION_PREFIX = "hlsf-v1.10";
const STORAGE_PREFIX = "hlsf_phase_nudge";

/** The stall prompt belongs to the v1.10 guided rounds only. */
export function supportsPhaseNudge(guide: Guide | null | undefined): boolean {
  return Boolean(guide && guide.version.startsWith(NUDGE_VERSION_PREFIX));
}

/**
 * Number of student messages sent since the current phase prompt.
 * `hlsf_hint` messages do not reset the count, a new `hlsf_prompt` does.
 */
export function countUserTurnsInPhase(messages: ChatMessage[]): number {
  let phaseStart = -1;
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index].source === "hlsf_prompt") {
      phaseStart = index;
      break;
    }
  }
  return messages
    .slice(phaseStart + 1)
    .filter((message) => message.role === "user").length;
}

export function isPhaseNudgeDue({
  guide,
  messages,
  dismissed,
  disabled,
  busy,
  composerEmpty,
}: {
  guide: Guide | null;
  messages: ChatMessage[];
  dismissed: boolean;
  disabled: boolean;
  busy: boolean;
  composerEmpty: boolean;
}): boolean {
  if (!supportsPhaseNudge(guide)) return false;
  if (!guide || guide.phase === "complete" || guide.completed_at) return false;
  if (disabled || busy || !composerEmpty || dismissed) return false;
  return countUserTurnsInPhase(messages) >= NUDGE_TURN_THRESHOLD;
}

function storageKeyFor(base: string, phase: string): string {
  return `${STORAGE_PREFIX}:${base}:${phase}`;
}

function readDismissed(base: string, phase: string): boolean {
  try {
    return window.localStorage.getItem(storageKeyFor(base, phase)) === "1";
  } catch {
    return false;
  }
}

/**
 * Tracks whether the "you have been in this phase for a while" prompt should be
 * visible.  The dismissal is remembered per participant, round and phase so a
 * page refresh does not bring the prompt back.
 */
export function usePhaseNudge({
  guide,
  messages,
  disabled,
  busy,
  composerEmpty,
  storageBase,
}: {
  guide: Guide | null;
  messages: ChatMessage[];
  disabled: boolean;
  busy: boolean;
  composerEmpty: boolean;
  storageBase: string;
}) {
  const phase = guide?.phase ?? null;
  // Read the stored dismissal during the first render so a reload never flashes
  // the prompt (and never logs a phantom "shown" event) before the check runs.
  const [dismissedPhase, setDismissedPhase] = React.useState<string | null>(() =>
    phase && readDismissed(storageBase, phase) ? phase : null,
  );

  React.useEffect(() => {
    if (!phase) {
      setDismissedPhase(null);
      return;
    }
    setDismissedPhase(readDismissed(storageBase, phase) ? phase : null);
  }, [storageBase, phase]);

  const due = isPhaseNudgeDue({
    guide,
    messages,
    dismissed: dismissedPhase !== null && dismissedPhase === phase,
    disabled,
    busy,
    composerEmpty,
  });

  const dismiss = React.useCallback(() => {
    if (!phase) return;
    setDismissedPhase(phase);
    try {
      window.localStorage.setItem(storageKeyFor(storageBase, phase), "1");
    } catch {
      // Private-mode storage failures must not break the chat.
    }
  }, [phase, storageBase]);

  return { visible: due, phase, dismiss };
}
