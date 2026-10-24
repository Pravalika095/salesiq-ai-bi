import { useCallback, useRef, useState } from "react";
import Sidebar, { NAV_ITEMS } from "./components/Sidebar";
import Header from "./components/Header";
import { ErrorState } from "./components/States";
import DashboardPage from "./pages/DashboardPage";
import AskPage from "./pages/AskPage";
import AnalyticsPage from "./pages/AnalyticsPage";
import TransactionsPage from "./pages/TransactionsPage";
import DataQualityPage from "./pages/DataQualityPage";
import AboutPage from "./pages/AboutPage";
import { useApi, useHashRoute } from "./hooks/useApi";
import { api } from "./services/api";

const DESCRIPTIONS = {
  dashboard: "Key sales metrics and quick answers from your transaction data.",
  ask: "Ask questions in plain English. Every figure is computed by a database query.",
  analytics: "Revenue broken down by month, product, region, category and channel.",
  transactions: "Browse every stored transaction and its calculated net revenue.",
  quality: "What the import found in the CSV and how each issue is treated.",
  about: "Architecture, AI integration and the safety controls behind each answer.",
};

export default function App() {
  const [route, navigate] = useHashRoute("dashboard");
  const [refreshKey, setRefreshKey] = useState(0);
  const health = useApi(api.health, [refreshKey]);
  const summary = useApi(api.summary, [refreshKey]);

  // Conversation lives here so it survives switching between Dashboard and Ask AI.
  const [conversation, setConversation] = useState([]);
  const [asking, setAsking] = useState(false);
  const nextId = useRef(1);

  const ask = useCallback(async (question) => {
    const id = nextId.current++;
    setAsking(true);
    setConversation((c) => [{ id, question, loading: true }, ...c]);
    let patch;
    try {
      patch = { response: await api.ask(question) };
    } catch (error) {
      patch = { error };
    }
    setConversation((c) => c.map((e) => (e.id === id ? { id, question, loading: false, ...patch } : e)));
    setAsking(false);
  }, []);

  const page = NAV_ITEMS.find((n) => n.id === route) ? route : "dashboard";
  const title = NAV_ITEMS.find((n) => n.id === page).label;
  const apiDown = health.error && health.error.status === 0;

  return (
    <div className="app">
      <Sidebar route={page} onNavigate={navigate} />
      <main className="main">
        <Header
          title={title}
          description={DESCRIPTIONS[page]}
          health={health.data}
          healthError={health.error}
          summary={summary.data}
          refreshing={health.loading || summary.loading}
          onRefresh={() => setRefreshKey((k) => k + 1)}
        />
        {apiDown ? (
          <div className="page">
            <ErrorState
              title="The SalesIQ API is not reachable"
              error={health.error}
              onRetry={() => setRefreshKey((k) => k + 1)}
            />
          </div>
        ) : health.data && !health.data.data_loaded ? (
          <div className="page">
            <ErrorState
              title="Sales data is not available"
              error={{ message: "The database could not be opened or the CSV import failed. Check the backend log, then refresh." }}
              onRetry={() => setRefreshKey((k) => k + 1)}
            />
          </div>
        ) : (
          <>
            {page === "dashboard" && (
              <DashboardPage
                summary={summary.data}
                summaryState={summary}
                refreshKey={refreshKey}
                conversation={conversation}
                onAsk={ask}
                asking={asking}
                onNavigate={navigate}
              />
            )}
            {page === "ask" && (
              <AskPage conversation={conversation} onAsk={ask} asking={asking} onClear={() => setConversation([])} />
            )}
            {page === "analytics" && <AnalyticsPage refreshKey={refreshKey} />}
            {page === "transactions" && <TransactionsPage refreshKey={refreshKey} />}
            {page === "quality" && <DataQualityPage refreshKey={refreshKey} />}
            {page === "about" && <AboutPage health={health.data} />}
          </>
        )}
      </main>
    </div>
  );
}
