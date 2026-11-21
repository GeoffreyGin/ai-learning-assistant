import type { ReactNode } from "react";
import { STATUS_MASTERED, STATUS_WEAK, masteryStatus } from "../types";

export function StatusBadge({ status }: { status: string }) {
  const label =
    status === STATUS_MASTERED ? "Mastered" : status === STATUS_WEAK ? "Needs practice" : "Unknown";
  return <span className={`badge badge-${status.toLowerCase()}`}>{label}</span>;
}

export function MasteryBadge({ mastery }: { mastery: number | null | undefined }) {
  return <StatusBadge status={masteryStatus(mastery)} />;
}

export function MasteryBar({ mastery }: { mastery: number | null | undefined }) {
  const percent = mastery === null || mastery === undefined ? 0 : Math.round(mastery * 100);
  const status = masteryStatus(mastery);
  return (
    <span className="mastery-bar" title={`Estimated mastery ${percent}%`}>
      <span className={`mastery-fill mastery-${status.toLowerCase()}`} style={{ width: `${percent}%` }} />
    </span>
  );
}

export function Panel({ title, children, extra }: { title: string; children: ReactNode; extra?: ReactNode }) {
  return (
    <section className="panel">
      <header className="panel-header">
        <h2>{title}</h2>
        {extra}
      </header>
      <div className="panel-body">{children}</div>
    </section>
  );
}

export function ErrorBox({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <div className="error-box">
      <span>Error: {error}</span>
      {onRetry ? <button onClick={onRetry}>Retry</button> : null}
    </div>
  );
}

export function Loading({ text = "Loading…" }: { text?: string }) {
  return <div className="loading">{text}</div>;
}
