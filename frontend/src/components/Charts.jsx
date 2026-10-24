import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatINR, formatINRCompact, formatInt, formatPct, monthLabel } from "../utils/format";

// Single-series charts: one hue (validated against the light surface), no legend.
const SERIES = "var(--chart-1)";
const GRID = "var(--chart-grid)";
const AXIS = { fontSize: 12, fill: "var(--text-muted)" };

function ChartTooltip({ active, payload, labelFormatter }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip__title">{labelFormatter(row)}</div>
      <div className="chart-tooltip__row">
        <span className="swatch" aria-hidden="true" />
        Net revenue <strong>{formatINR(row.revenue)}</strong>
      </div>
      {row.transactions !== undefined && (
        <div className="chart-tooltip__sub">{formatInt(row.transactions)} transactions</div>
      )}
      {row.share_pct !== undefined && <div className="chart-tooltip__sub">{formatPct(row.share_pct)} of total</div>}
      {row.change_pct !== undefined && row.change_pct !== null && (
        <div className="chart-tooltip__sub">{formatPct(row.change_pct, { sign: true })} vs previous month</div>
      )}
    </div>
  );
}

export function RevenueLineChart({ data, height = 280 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 12, right: 16, bottom: 4, left: 4 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="month" tickFormatter={(m) => monthLabel(m)} tick={AXIS} axisLine={false} tickLine={false} />
        <YAxis tickFormatter={formatINRCompact} tick={AXIS} axisLine={false} tickLine={false} width={64} />
        <Tooltip
          content={<ChartTooltip labelFormatter={(r) => monthLabel(r.month, { long: true })} />}
          cursor={{ stroke: "var(--text-muted)", strokeDasharray: "3 3" }}
        />
        <Line
          type="linear"
          dataKey="revenue"
          stroke={SERIES}
          strokeWidth={2}
          dot={{ r: 4, fill: SERIES, stroke: "var(--surface)", strokeWidth: 2 }}
          activeDot={{ r: 6, fill: SERIES, stroke: "var(--surface)", strokeWidth: 2 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function RevenueBarChart({ data, xKey = "label", height = 280, horizontal = false, labelFormatter }) {
  const fmt = labelFormatter || ((v) => v);
  if (horizontal) {
    return (
      <ResponsiveContainer width="100%" height={Math.max(height, data.length * 40)}>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 8 }} barCategoryGap={8}>
          <CartesianGrid stroke={GRID} horizontal={false} />
          <XAxis type="number" tickFormatter={formatINRCompact} tick={AXIS} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey={xKey} tickFormatter={fmt} tick={AXIS} axisLine={false} tickLine={false} width={110} />
          <Tooltip content={<ChartTooltip labelFormatter={(r) => fmt(r[xKey])} />} cursor={{ fill: "var(--hover)" }} />
          <Bar dataKey="revenue" fill={SERIES} radius={[0, 4, 4, 0]} maxBarSize={24} />
        </BarChart>
      </ResponsiveContainer>
    );
  }
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 12, right: 16, bottom: 4, left: 4 }} barCategoryGap="25%">
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey={xKey} tickFormatter={fmt} tick={AXIS} axisLine={false} tickLine={false} interval={0} />
        <YAxis tickFormatter={formatINRCompact} tick={AXIS} axisLine={false} tickLine={false} width={64} />
        <Tooltip content={<ChartTooltip labelFormatter={(r) => fmt(r[xKey])} />} cursor={{ fill: "var(--hover)" }} />
        <Bar dataKey="revenue" fill={SERIES} radius={[4, 4, 0, 0]} maxBarSize={56} />
      </BarChart>
    </ResponsiveContainer>
  );
}
