import React from "react";

export function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`brand ${compact ? "brand-compact" : ""}`}>
      <div className="brand-icon" aria-hidden="true">
        <svg viewBox="0 0 48 48" width="42" height="42">
          <path d="M5 40h38" stroke="currentColor" strokeWidth="2" />
          <path d="M9 36V22M17 36V18M25 36V16M33 36V20M41 36V24" stroke="currentColor" strokeWidth="2" />
          <path d="M6 21L24 8l18 13" fill="none" stroke="currentColor" strokeWidth="2" />
          <path d="M12 36h30" stroke="currentColor" strokeWidth="2" />
        </svg>
      </div>
      <div>
        <div className="brand-title">Heritage Learning Studio</div>
        {!compact && (
          <div className="brand-subtitle">
            AI-Assisted Cultural Heritage Learning &amp; Creation
          </div>
        )}
      </div>
    </div>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <div className="spinner-row" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function Bilingual({ zh, en }: { zh: string; en?: string }) {
  return (
    <span>
      {zh}
      {en ? <span className="en"> {en}</span> : null}
    </span>
  );
}

export function ErrorNotice({
  message,
  onRetry,
  requestId,
}: {
  message: string;
  onRetry?: () => void;
  requestId?: string;
}) {
  return (
    <div className="notice notice-error" role="alert">
      <div>{message}</div>
      {requestId ? <div className="tiny muted">Request ID: {requestId}</div> : null}
      {onRetry ? (
        <button type="button" className="button button-small" onClick={onRetry}>
          重试 / Retry
        </button>
      ) : null}
    </div>
  );
}

export function formatClock(totalSeconds: number): string {
  const safe = Math.max(0, Math.floor(totalSeconds));
  const minutes = Math.floor(safe / 60);
  const seconds = safe % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

export function formatTime(value: string | null | undefined): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function useCountdown(
  deadlineAt: string | null,
  onExpire?: () => void,
): number {
  const compute = React.useCallback(
    () =>
      deadlineAt
        ? Math.max(0, Math.ceil((Date.parse(deadlineAt) - Date.now()) / 1000))
        : 0,
    [deadlineAt],
  );
  const [remaining, setRemaining] = React.useState(compute);
  const fired = React.useRef(false);

  React.useEffect(() => {
    fired.current = false;
    setRemaining(compute());
    if (!deadlineAt) return;
    const timer = window.setInterval(() => {
      const next = compute();
      setRemaining(next);
      if (next <= 0 && !fired.current) {
        fired.current = true;
        onExpire?.();
      }
    }, 500);
    return () => window.clearInterval(timer);
  }, [compute, deadlineAt, onExpire]);

  return remaining;
}

export function clearLocalStudyData(): void {
  try {
    const keys: string[] = [];
    for (let index = 0; index < window.localStorage.length; index += 1) {
      const key = window.localStorage.key(index);
      if (key && key.startsWith("hls:")) keys.push(key);
    }
    keys.forEach((key) => window.localStorage.removeItem(key));
  } catch {
    // Browsers can disable storage; the server remains authoritative.
  }
}

export function safeRandomId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
