import { AlertCircle, Bot, CheckCircle2, HelpCircle, Info, Loader2 } from "lucide-react";
import DataTable from "./DataTable";
import { RevenueBarChart, RevenueLineChart } from "./Charts";
import {
  AI_MODE_LABELS,
  INTENT_LABELS,
  formatINR,
  formatInt,
  formatPct,
  monthLabel,
} from "../utils/format";

const MONTH_RE = /^\d{4}-\d{2}$/;

const COUNT_METRICS = new Set(["Eligible transactions", "Units sold"]);

const DIMENSION_LABEL = {
  top_product: "Product", bottom_product: "Product", product_breakdown: "Product",
  top_region: "Region", bottom_region: "Region", region_breakdown: "Region",
  category_breakdown: "Category", channel_breakdown: "Sales channel",
};

// Pick table columns that match the shape of the supporting data for each intent.
function columnsFor(intent) {
  if (intent === "total_revenue" || intent === "total_units") {
    return [
      { key: "metric", label: "Metric" },
      {
        key: "value", label: "Value", align: "right",
        render: (r) => (COUNT_METRICS.has(r.metric) ? formatInt(r.value) : formatINR(r.value)),
      },
    ];
  }
  if (intent === "monthly_revenue") {
    return [
      { key: "month", label: "Month", render: (r) => monthLabel(r.month, { long: true }) },
      { key: "revenue", label: "Net revenue", align: "right", render: (r) => formatINR(r.revenue) },
      { key: "transactions", label: "Transactions", align: "right", render: (r) => formatInt(r.transactions) },
      { key: "change", label: "Change", align: "right", render: (r) => (r.change === null ? "—" : formatINR(r.change)) },
      { key: "change_pct", label: "Change %", align: "right", render: (r) => formatPct(r.change_pct, { sign: true }) },
    ];
  }
  if (intent === "compare_months") {
    return [
      { key: "month", label: "Period", render: (r) => (MONTH_RE.test(r.month) ? monthLabel(r.month, { long: true }) : <strong>{r.month}</strong>) },
      {
        key: "revenue", label: "Net revenue", align: "right",
        render: (r) => `${!MONTH_RE.test(r.month) && r.revenue > 0 ? "+" : ""}${formatINR(r.revenue)}`,
      },
      {
        key: "detail", label: "Transactions / change %", align: "right",
        render: (r) => (MONTH_RE.test(r.month) ? formatInt(r.transactions) : formatPct(r.change_pct, { sign: true })),
      },
    ];
  }
  return [
    { key: "label", label: DIMENSION_LABEL[intent] || "Item" },
    { key: "revenue", label: "Net revenue", align: "right", render: (r) => formatINR(r.revenue) },
    { key: "share_pct", label: "Share", align: "right", render: (r) => formatPct(r.share_pct) },
    { key: "transactions", label: "Transactions", align: "right", render: (r) => formatInt(r.transactions) },
    { key: "units", label: "Units", align: "right", render: (r) => formatInt(r.units) },
  ];
}

function headline(response) {
  if (response.value === null || response.value === undefined) return null;
  if (response.unit === "units") return `${formatInt(response.value)} units`;
  if (response.intent === "compare_months" && response.value > 0) return `+${formatINR(response.value)}`;
  return formatINR(response.value);
}

export default function AnswerCard({ entry }) {
  const { question, response, error, loading } = entry;

  if (loading) {
    return (
      <article className="card answer">
        <p className="answer__question">{question}</p>
        <div className="answer__pending">
          <Loader2 size={16} className="spin" aria-hidden="true" /> Interpreting your question and querying the database…
        </div>
      </article>
    );
  }

  if (error) {
    return (
      <article className="card answer answer--error" role="alert">
        <p className="answer__question">{question}</p>
        <div className="answer__status">
          <AlertCircle size={18} aria-hidden="true" />
          <div>
            <strong>Request failed</strong>
            <p>{error.message}</p>
          </div>
        </div>
      </article>
    );
  }

  const { success, intent, answer, supporting_data: rows = [], chart, metadata } = response;
  const unsupported = intent === "unsupported";
  const chartRows = chart ? rows.filter((r) => chart.x_key !== "month" || MONTH_RE.test(r.month)) : [];
  const value = success ? headline(response) : null;

  return (
    <article className={`card answer ${success ? "" : "answer--warn"}`}>
      <p className="answer__question">{question}</p>

      <div className="answer__status">
        {success ? (
          <CheckCircle2 size={18} className="ok" aria-hidden="true" />
        ) : unsupported ? (
          <HelpCircle size={18} aria-hidden="true" />
        ) : (
          <AlertCircle size={18} aria-hidden="true" />
        )}
        <div>
          {!success && <strong>{unsupported ? "I can't answer that one reliably" : "Couldn't complete that analysis"}</strong>}
          <p className="answer__text">{answer}</p>
        </div>
        {value && <div className="answer__value">{value}</div>}
      </div>

      <div className="answer__meta">
        <span className="tag">Intent: {INTENT_LABELS[intent] || intent}</span>
        <span className={`tag ${metadata.ai_mode === "llm" ? "tag--primary" : ""}`}>
          <Bot size={12} aria-hidden="true" /> {AI_MODE_LABELS[metadata.ai_mode] || metadata.ai_mode}
          {metadata.ai_model && metadata.ai_mode === "llm" ? ` · ${metadata.ai_model}` : ""}
        </span>
        {success && <span className="tag">Source: {metadata.source}</span>}
        {success && <span className="tag">{metadata.row_count} supporting rows</span>}
        {metadata.filters?.month && <span className="tag">Month: {monthLabel(metadata.filters.month)}</span>}
      </div>

      {metadata.notes?.length > 0 && (
        <ul className="answer__notes">
          {metadata.notes.map((n) => (
            <li key={n}>
              <Info size={13} aria-hidden="true" /> {n}
            </li>
          ))}
        </ul>
      )}

      {success && chart && chartRows.length > 0 && (
        <div className="answer__chart">
          <h3>{chart.title}</h3>
          {chart.type === "line" ? (
            <RevenueLineChart data={chartRows} height={240} />
          ) : (
            <RevenueBarChart
              data={chartRows}
              xKey={chart.x_key}
              height={240}
              labelFormatter={chart.x_key === "month" ? (m) => monthLabel(m) : undefined}
            />
          )}
        </div>
      )}

      {success && rows.length > 0 && (
        <details className="answer__table" open>
          <summary>Supporting figures</summary>
          <DataTable columns={columnsFor(intent)} rows={rows} caption="Supporting figures for the answer" />
          <p className="fineprint">
            Eligible sales only: status Completed, known unit price. Net revenue = quantity × unit price − discount.
          </p>
        </details>
      )}
    </article>
  );
}
