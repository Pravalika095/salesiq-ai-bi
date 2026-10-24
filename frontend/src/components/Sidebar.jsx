import { BarChart3, Database, Info, LayoutDashboard, ShieldCheck, Sparkles } from "lucide-react";

export const NAV_ITEMS = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "ask", label: "Ask AI", icon: Sparkles },
  { id: "analytics", label: "Sales Analytics", icon: BarChart3 },
  { id: "transactions", label: "Transactions", icon: Database },
  { id: "quality", label: "Data Quality", icon: ShieldCheck },
  { id: "about", label: "About / Architecture", icon: Info },
];

export default function Sidebar({ route, onNavigate }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand__mark" aria-hidden="true">
          <BarChart3 size={18} />
        </span>
        <div>
          <div className="brand__name">SalesIQ</div>
          <div className="brand__tag">AI Business Intelligence</div>
        </div>
      </div>
      <nav aria-label="Main">
        {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
          <a
            key={id}
            href={`#/${id}`}
            className={`nav-link ${route === id ? "is-active" : ""}`}
            aria-current={route === id ? "page" : undefined}
            onClick={(e) => {
              e.preventDefault();
              onNavigate(id);
            }}
          >
            <Icon size={18} aria-hidden="true" />
            <span>{label}</span>
          </a>
        ))}
      </nav>
      <div className="sidebar__foot">Data: supplied sales CSV → SQLite</div>
    </aside>
  );
}
