import { EmptyState, ErrorState, Loading } from "./States";

// Card wrapper for a chart backed by a useApi() state whose data has `items`.
export default function ChartCard({ title, subtitle, state, children }) {
  return (
    <section className="card chart-card">
      <div className="card__head">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
      </div>
      {state.loading && !state.data ? (
        <Loading compact />
      ) : state.error ? (
        <ErrorState error={state.error} onRetry={state.reload} title="Couldn't load chart" />
      ) : !state.data?.items?.length ? (
        <EmptyState title="No data" message="No eligible sales found." />
      ) : (
        children(state.data.items)
      )}
    </section>
  );
}
