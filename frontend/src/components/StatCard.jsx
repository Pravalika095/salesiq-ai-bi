import { Skeleton } from "./States";

export default function StatCard({ icon: Icon, label, value, hint, loading }) {
  return (
    <div className="card stat">
      <div className="stat__head">
        <span className="stat__label">{label}</span>
        {Icon && (
          <span className="stat__icon" aria-hidden="true">
            <Icon size={16} />
          </span>
        )}
      </div>
      <div className="stat__value">{loading ? <Skeleton height={28} width="70%" /> : value}</div>
      <div className="stat__hint">{loading ? <Skeleton height={12} width="50%" /> : hint}</div>
    </div>
  );
}
