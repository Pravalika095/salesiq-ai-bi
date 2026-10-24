import { RevenueBarChart, RevenueLineChart } from "../components/Charts";
import DataTable from "../components/DataTable";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { formatINR, formatInt, formatPct, monthLabel } from "../utils/format";
import ChartCard from "../components/ChartCard";

const breakdownColumns = (label) => [
  { key: "label", label },
  { key: "revenue", label: "Net revenue", align: "right", render: (r) => formatINR(r.revenue) },
  { key: "share_pct", label: "Share", align: "right", render: (r) => formatPct(r.share_pct) },
  { key: "transactions", label: "Txns", align: "right", render: (r) => formatInt(r.transactions) },
  { key: "units", label: "Units", align: "right", render: (r) => formatInt(r.units) },
];

const monthlyColumns = [
  { key: "month", label: "Month", render: (r) => monthLabel(r.month, { long: true }) },
  { key: "revenue", label: "Net revenue", align: "right", render: (r) => formatINR(r.revenue) },
  { key: "transactions", label: "Transactions", align: "right", render: (r) => formatInt(r.transactions) },
  { key: "units", label: "Units", align: "right", render: (r) => formatInt(r.units) },
  { key: "change", label: "MoM change", align: "right", render: (r) => (r.change === null ? "—" : formatINR(r.change)) },
  { key: "change_pct", label: "MoM %", align: "right", render: (r) => formatPct(r.change_pct, { sign: true }) },
];

export default function AnalyticsPage({ refreshKey }) {
  const monthly = useApi(api.monthly, [refreshKey]);
  const products = useApi(api.products, [refreshKey]);
  const regions = useApi(api.regions, [refreshKey]);
  const categories = useApi(api.categories, [refreshKey]);
  const channels = useApi(api.channels, [refreshKey]);

  return (
    <div className="page">
      <ChartCard title="Monthly revenue" subtitle="Chronological, with month-over-month change" state={monthly}>
        {(items) => (
          <>
            <RevenueLineChart data={items} />
            <DataTable columns={monthlyColumns} rows={items} caption="Monthly revenue table" />
          </>
        )}
      </ChartCard>

      <div className="grid-2">
        <ChartCard title="Products" subtitle="Ties broken alphabetically" state={products}>
          {(items) => (
            <>
              <RevenueBarChart data={items} horizontal />
              <DataTable columns={breakdownColumns("Product")} rows={items} />
            </>
          )}
        </ChartCard>
        <ChartCard title="Regions" state={regions}>
          {(items) => (
            <>
              <RevenueBarChart data={items} />
              <DataTable columns={breakdownColumns("Region")} rows={items} />
            </>
          )}
        </ChartCard>
        <ChartCard title="Categories" state={categories}>
          {(items) => (
            <>
              <RevenueBarChart data={items} height={220} />
              <DataTable columns={breakdownColumns("Category")} rows={items} />
            </>
          )}
        </ChartCard>
        <ChartCard title="Sales channels" state={channels}>
          {(items) => (
            <>
              <RevenueBarChart data={items} height={220} />
              <DataTable columns={breakdownColumns("Channel")} rows={items} />
            </>
          )}
        </ChartCard>
      </div>
    </div>
  );
}
