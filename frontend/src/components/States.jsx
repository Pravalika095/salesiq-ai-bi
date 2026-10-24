import { AlertTriangle, Inbox, Loader2, RotateCw } from "lucide-react";

export function Loading({ label = "Loading…", compact = false }) {
  return (
    <div className={`state ${compact ? "state--compact" : ""}`} role="status" aria-live="polite">
      <Loader2 className="spin" size={20} aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function ErrorState({ error, onRetry, title = "Something went wrong" }) {
  return (
    <div className="state state--error" role="alert">
      <AlertTriangle size={22} aria-hidden="true" />
      <div>
        <strong>{title}</strong>
        <p>{error?.message || String(error)}</p>
      </div>
      {onRetry && (
        <button className="btn btn--ghost" onClick={onRetry}>
          <RotateCw size={14} aria-hidden="true" /> Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title = "Nothing to show", message }) {
  return (
    <div className="state">
      <Inbox size={22} aria-hidden="true" />
      <div>
        <strong>{title}</strong>
        {message && <p>{message}</p>}
      </div>
    </div>
  );
}

export function Skeleton({ height = 16, width = "100%" }) {
  return <span className="skeleton" style={{ height, width }} aria-hidden="true" />;
}
