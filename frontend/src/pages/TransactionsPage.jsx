import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import DataTable from "../components/DataTable";
import { ErrorState, Loading } from "../components/States";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { formatDate, formatINR, formatInt } from "../utils/format";

const PAGE_SIZE = 15;
const FILTERS = [
  { key: "product", label: "Product" },
  { key: "region", label: "Region" },
  { key: "category", label: "Category" },
  { key: "channel", label: "Channel" },
  { key: "status", label: "Status" },
];
const FLAG_LABELS = {
  missing_unit_price: "Missing price",
  zero_quantity: "Zero qty",
  returned: "Returned",
  unknown_status: "Unknown status",
  discount_exceeds_gross: "Discount > gross",
};

const columns = [
  { key: "transaction_id", label: "ID", render: (r) => <code>{r.transaction_id}</code> },
  { key: "order_date", label: "Date", render: (r) => formatDate(r.order_date) },
  { key: "product", label: "Product" },
  { key: "category", label: "Category" },
  { key: "region", label: "Region" },
  { key: "sales_channel", label: "Channel" },
  { key: "quantity", label: "Qty", align: "right", render: (r) => formatInt(r.quantity) },
  { key: "unit_price", label: "Unit price", align: "right", render: (r) => (r.unit_price === null ? <span className="text-danger">Missing</span> : formatINR(r.unit_price)) },
  { key: "discount", label: "Discount", align: "right", render: (r) => formatINR(r.discount) },
  { key: "status", label: "Status", render: (r) => <span className={`badge badge--${r.status === "Completed" ? "success" : "warn"}`}>{r.status}</span> },
  {
    key: "net_revenue", label: "Net revenue", align: "right",
    render: (r) => (r.net_revenue === null ? <span className="muted" title="Excluded from revenue">Excluded</span> : formatINR(r.net_revenue)),
  },
  {
    key: "flags", label: "Flags",
    render: (r) => (r.flags.length ? r.flags.map((f) => <span key={f} className="badge badge--warn">{FLAG_LABELS[f] || f}</span>) : ""),
  },
];

export default function TransactionsPage({ refreshKey }) {
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({});
  const options = useApi(api.transactionFilters, [refreshKey]);
  const result = useApi(() => api.transactions({ page, page_size: PAGE_SIZE, ...filters }), [page, filters, refreshKey]);

  const totalPages = result.data ? Math.max(1, Math.ceil(result.data.total / PAGE_SIZE)) : 1;

  return (
    <div className="page">
      <section className="card">
        <div className="filters">
          {FILTERS.map(({ key, label }) => (
            <label key={key} className="field">
              <span>{label}</span>
              <select
                value={filters[key] || ""}
                onChange={(e) => {
                  setPage(1);
                  setFilters((f) => ({ ...f, [key]: e.target.value }));
                }}
              >
                <option value="">All</option>
                {(options.data?.[key] || []).map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
          ))}
          {Object.values(filters).some(Boolean) && (
            <button className="link-btn" onClick={() => { setFilters({}); setPage(1); }}>
              Clear filters
            </button>
          )}
        </div>

        {result.loading && !result.data ? (
          <Loading />
        ) : result.error ? (
          <ErrorState error={result.error} onRetry={result.reload} />
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={result.data.items.map((r) => ({ ...r, _muted: r.net_revenue === null }))}
              empty="No transactions match these filters."
              caption="Sales transactions"
            />
            <div className="pager">
              <span>
                {result.data.total === 0
                  ? "0 records"
                  : `${(page - 1) * PAGE_SIZE + 1}–${Math.min(page * PAGE_SIZE, result.data.total)} of ${result.data.total} records`}
              </span>
              <div>
                <button className="btn btn--ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} aria-label="Previous page">
                  <ChevronLeft size={16} />
                </button>
                <span className="pager__page">
                  Page {page} / {totalPages}
                </span>
                <button className="btn btn--ghost" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)} aria-label="Next page">
                  <ChevronRight size={16} />
                </button>
              </div>
            </div>
          </>
        )}
      </section>
      <p className="fineprint">Read-only view. Greyed rows are stored but excluded from revenue (see Data Quality).</p>
    </div>
  );
}
