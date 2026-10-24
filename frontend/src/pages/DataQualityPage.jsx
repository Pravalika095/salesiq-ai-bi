import { AlertTriangle, CheckCircle2, CopyX, FileCheck2, FileX2, Undo2 } from "lucide-react";
import StatCard from "../components/StatCard";
import DataTable from "../components/DataTable";
import { ErrorState, Loading } from "../components/States";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { formatDate, formatINR, formatInt } from "../utils/format";

const POLICY = [
  ["Completed sale with a known unit price", "Counted in revenue: quantity × unit price − discount."],
  ["Returned", "Stored, excluded from revenue (it was never completed revenue, so nothing is subtracted)."],
  ["Missing unit price", "Stored with price = NULL (never treated as 0), flagged, excluded from revenue."],
  ["Zero quantity", "Stored and counted with ₹0 revenue, flagged for review."],
  ["Unknown status", "Stored, flagged, excluded from revenue."],
  ["Discount larger than gross amount", "Stored, flagged, excluded from revenue."],
  ["Invalid date, missing field, negative or non-numeric number", "Rejected at import, reason recorded."],
  ["Repeated transaction ID", "First occurrence kept; later rows rejected as duplicates."],
];

const ISSUE_LABELS = {
  returned: "Returned transactions",
  missing_unit_price: "Missing unit price",
  zero_quantity: "Zero quantity",
  unknown_status: "Unknown status",
  discount_exceeds_gross: "Discount exceeds gross",
};

export default function DataQualityPage({ refreshKey }) {
  const { data, error, loading, reload } = useApi(api.dataQuality, [refreshKey]);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorState error={error} onRetry={reload} />;

  const imp = data.import;
  return (
    <div className="page">
      <div className="stats-grid">
        <StatCard icon={FileCheck2} label="Imported records" value={formatInt(imp.imported_rows)} hint={`of ${imp.total_rows} rows in ${imp.source_file}`} />
        <StatCard icon={FileX2} label="Rejected records" value={formatInt(imp.rejected_rows)} hint="Failed validation at import" />
        <StatCard icon={CopyX} label="Duplicate IDs" value={formatInt(imp.duplicate_rows)} hint="Later occurrences rejected" />
        <StatCard icon={Undo2} label="Returned" value={formatInt(data.issues.returned)} hint="Excluded from revenue" />
      </div>

      <div className="grid-2">
        <section className="card">
          <div className="card__head">
            <div>
              <h2>Issues found</h2>
              <p>
                {data.eligible_transactions} records count toward revenue; {data.excluded_from_revenue} stored records are excluded.
                Imported {formatDate(imp.imported_at?.slice(0, 10))}.
              </p>
            </div>
          </div>
          <ul className="issue-list">
            {Object.entries(data.issues).map(([key, count]) => (
              <li key={key}>
                {count > 0 ? <AlertTriangle size={16} className="warn" aria-hidden="true" /> : <CheckCircle2 size={16} className="ok" aria-hidden="true" />}
                <span>{ISSUE_LABELS[key] || key}</span>
                <strong>{count}</strong>
              </li>
            ))}
          </ul>
        </section>
        <section className="card">
          <div className="card__head">
            <div>
              <h2>Cleaning policy</h2>
              <p>Applied identically by the API, dashboard, charts and tests.</p>
            </div>
          </div>
          <dl className="policy">
            {POLICY.map(([k, v]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
        </section>
      </div>

      <section className="card">
        <div className="card__head">
          <div>
            <h2>Flagged records</h2>
            <p>Stored in the database but needing review.</p>
          </div>
        </div>
        <DataTable
          rows={data.flagged_records}
          empty="No flagged records."
          columns={[
            { key: "transaction_id", label: "ID", render: (r) => <code>{r.transaction_id}</code> },
            { key: "order_date", label: "Date", render: (r) => formatDate(r.order_date) },
            { key: "product", label: "Product" },
            { key: "status", label: "Status" },
            { key: "quantity", label: "Qty", align: "right" },
            { key: "unit_price", label: "Unit price", align: "right", render: (r) => (r.unit_price === null ? <span className="text-danger">Missing</span> : formatINR(r.unit_price)) },
            { key: "flags", label: "Flags", render: (r) => r.flags.map((f) => <span key={f} className="badge badge--warn">{ISSUE_LABELS[f] || f}</span>) },
            { key: "counted", label: "In revenue?", render: (r) => (r.counted_in_revenue ? "Yes" : "No") },
          ]}
        />
      </section>

      <section className="card">
        <div className="card__head">
          <div>
            <h2>Rejected rows</h2>
            <p>Not loaded into the sales table. Row numbers refer to data rows in the CSV (header excluded).</p>
          </div>
        </div>
        <DataTable
          rows={data.rejected_records}
          empty="No rows were rejected — every row passed validation."
          columns={[
            { key: "source_row", label: "Row", align: "right" },
            { key: "transaction_id", label: "ID", render: (r) => <code>{r.transaction_id || "—"}</code> },
            { key: "reason", label: "Reason" },
          ]}
        />
      </section>
    </div>
  );
}
