import { Bot, Calendar, Database, RefreshCw } from "lucide-react";
import { formatDate } from "../utils/format";

function Pill({ tone, icon: Icon, children, title }) {
  return (
    <span className={`pill pill--${tone}`} title={title}>
      <Icon size={14} aria-hidden="true" />
      {children}
    </span>
  );
}

export default function Header({ title, description, health, healthError, summary, onRefresh, refreshing }) {
  const dbOk = health?.database_connected && health?.data_loaded;
  const dbLabel = healthError ? "API offline" : !health ? "Checking…" : dbOk ? "SQLite connected" : "Database unavailable";
  const llm = health?.ai_mode === "llm";
  const range = summary?.date_range;

  return (
    <header className="topbar">
      <div className="topbar__titles">
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="topbar__meta">
        <Pill tone={healthError || (health && !dbOk) ? "danger" : dbOk ? "success" : "neutral"} icon={Database}>
          {dbLabel}
        </Pill>
        {health && (
          <Pill
            tone={llm ? "primary" : "neutral"}
            icon={Bot}
            title={
              llm
                ? `Questions are interpreted by ${health.ai_provider} (${health.ai_model})`
                : "No LLM API key configured: questions are interpreted by the deterministic rule-based parser"
            }
          >
            {llm ? `LLM: ${health.ai_model}` : "Rule-based parser"}
          </Pill>
        )}
        {range?.start && (
          <Pill tone="neutral" icon={Calendar}>
            {formatDate(range.start)} – {formatDate(range.end)}
          </Pill>
        )}
        <button className="btn btn--ghost" onClick={onRefresh} disabled={refreshing} aria-label="Refresh data">
          <RefreshCw size={15} className={refreshing ? "spin" : ""} aria-hidden="true" />
          Refresh
        </button>
      </div>
    </header>
  );
}
