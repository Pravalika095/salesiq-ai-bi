// Formatting helpers. They never render undefined/NaN/Infinity — they return "—".

const isNum = (v) => typeof v === "number" && Number.isFinite(v);

const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 });
const inr0 = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const int = new Intl.NumberFormat("en-IN");

export const formatINR = (v, { decimals = true } = {}) => (isNum(v) ? (decimals ? inr : inr0).format(v) : "—");
export const formatInt = (v) => (isNum(v) ? int.format(v) : "—");
export const formatPct = (v, { sign = false } = {}) =>
  isNum(v) ? `${sign && v > 0 ? "+" : ""}${v.toFixed(2)}%` : "—";

// Compact axis labels: 473000 -> "₹4.7L", 14392000 -> "₹1.4Cr"
export function formatINRCompact(v) {
  if (!isNum(v)) return "—";
  const abs = Math.abs(v);
  if (abs >= 1e7) return `₹${(v / 1e7).toFixed(1)}Cr`;
  if (abs >= 1e5) return `₹${(v / 1e5).toFixed(1)}L`;
  if (abs >= 1e3) return `₹${(v / 1e3).toFixed(0)}K`;
  return `₹${v}`;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export function monthLabel(ym, { long = false } = {}) {
  const m = /^(\d{4})-(\d{2})$/.exec(ym || "");
  if (!m) return ym ?? "—";
  const date = new Date(Number(m[1]), Number(m[2]) - 1, 1);
  return long
    ? date.toLocaleString("en-IN", { month: "long", year: "numeric" })
    : `${MONTHS[Number(m[2]) - 1]} ${m[1]}`;
}

export function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(`${iso}T00:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export const INTENT_LABELS = {
  total_revenue: "Total revenue",
  total_units: "Total units",
  top_product: "Top product",
  bottom_product: "Lowest product",
  top_region: "Top region",
  bottom_region: "Lowest region",
  monthly_revenue: "Monthly trend",
  compare_months: "Month comparison",
  product_breakdown: "Revenue by product",
  region_breakdown: "Revenue by region",
  category_breakdown: "Revenue by category",
  channel_breakdown: "Revenue by channel",
  unsupported: "Not supported",
};

export const AI_MODE_LABELS = {
  llm: "LLM",
  fallback: "Rule-based parser",
  fallback_after_llm_error: "Rule-based (LLM failed)",
};
