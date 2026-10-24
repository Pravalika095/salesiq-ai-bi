import { IndianRupee, Package, Receipt, Trophy } from "lucide-react";
import StatCard from "../components/StatCard";
import AskPanel from "../components/AskPanel";
import AnswerCard from "../components/AnswerCard";
import { RevenueBarChart, RevenueLineChart } from "../components/Charts";
import ChartCard from "../components/ChartCard";
import { ErrorState } from "../components/States";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { formatINR, formatInt, formatPct } from "../utils/format";

export default function DashboardPage({ summary, summaryState, refreshKey, conversation, onAsk, asking, onNavigate }) {
  const monthly = useApi(api.monthly, [refreshKey]);
  const products = useApi(api.products, [refreshKey]);
  const regions = useApi(api.regions, [refreshKey]);
  const latest = conversation[0];
  const s = summary;
  const loading = summaryState.loading && !s;

  return (
    <div className="page">
      {summaryState.error && !s ? (
        <ErrorState error={summaryState.error} onRetry={summaryState.reload} title="Couldn't load the summary" />
      ) : (
        <div className="stats-grid">
          <StatCard
            icon={IndianRupee}
            label="Total Revenue"
            loading={loading}
            value={formatINR(s?.total_revenue, { decimals: false })}
            hint={s ? `Net of ${formatINR(s.total_discounts, { decimals: false })} discounts` : ""}
          />
          <StatCard
            icon={Receipt}
            label="Eligible Transactions"
            loading={loading}
            value={formatInt(s?.eligible_transactions)}
            hint={s ? `${s.data_quality.excluded_from_revenue} excluded from revenue` : ""}
          />
          <StatCard
            icon={Package}
            label="Total Units Sold"
            loading={loading}
            value={formatInt(s?.total_units)}
            hint="Across eligible transactions"
          />
          <StatCard
            icon={Trophy}
            label="Top-Performing Product"
            loading={loading}
            value={s?.top_product?.name ?? "—"}
            hint={
              s?.top_product
                ? `${formatINR(s.top_product.revenue, { decimals: false })} · ${formatPct(s.top_product.share_pct)} of revenue`
                : ""
            }
          />
        </div>
      )}

      <div className="dash-ask">
        <AskPanel onAsk={onAsk} loading={asking} />
        {latest ? (
          <>
            <AnswerCard entry={latest} />
            {conversation.length > 1 && (
              <button className="link-btn" onClick={() => onNavigate("ask")}>
                View all {conversation.length} questions in Ask AI →
              </button>
            )}
          </>
        ) : null}
      </div>

      <ChartCard title="Monthly revenue trend" subtitle="Net revenue per calendar month" state={monthly}>
        {(items) => <RevenueLineChart data={items} />}
      </ChartCard>

      <div className="grid-2">
        <ChartCard title="Revenue by product" subtitle="Highest first" state={products}>
          {(items) => <RevenueBarChart data={items} horizontal />}
        </ChartCard>
        <ChartCard title="Revenue by region" subtitle={s?.top_region ? `${s.top_region.name} leads` : "Highest first"} state={regions}>
          {(items) => <RevenueBarChart data={items} />}
        </ChartCard>
      </div>
    </div>
  );
}
