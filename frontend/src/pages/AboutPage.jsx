import { ArrowDown, Bot, Database, Lock, Server, ShieldCheck, Sparkles, User } from "lucide-react";

const FLOW = [
  { icon: User, title: "User", text: "Types a question in plain English." },
  { icon: Sparkles, title: "React frontend", text: "POST /api/ask with { question }." },
  { icon: Server, title: "FastAPI", text: "Validates the request (non-empty, ≤ 500 chars); rejects SQL-like input." },
  { icon: Bot, title: "Intent interpreter", text: "LLM (if an API key is set) or the rule-based parser → JSON intent." },
  { icon: ShieldCheck, title: "Intent validation", text: "Pydantic schema: allowed intents only, months as YYYY-MM." },
  { icon: Database, title: "Analytics + SQLite", text: "Predefined, parameterized SELECT on a read-only connection." },
  { icon: Sparkles, title: "Answer", text: "Templated text + supporting rows + chart spec, built from query results." },
];

export default function AboutPage({ health }) {
  const llm = health?.ai_mode === "llm";
  return (
    <div className="page page--narrow">
      <section className="card prose">
        <h2>How SalesIQ answers a question</h2>
        <ol className="flow">
          {FLOW.map(({ icon: Icon, title, text }, i) => (
            <li key={title}>
              <div className="flow__step">
                <span className="flow__icon" aria-hidden="true">
                  <Icon size={16} />
                </span>
                <div>
                  <strong>{title}</strong>
                  <p>{text}</p>
                </div>
              </div>
              {i < FLOW.length - 1 && <ArrowDown size={14} className="flow__arrow" aria-hidden="true" />}
            </li>
          ))}
        </ol>
      </section>

      <section className="card prose">
        <h2>Current AI mode</h2>
        <p>
          {llm ? (
            <>
              <strong>LLM mode</strong> — questions are interpreted by <code>{health.ai_provider}</code> /{" "}
              <code>{health.ai_model}</code>. If the model is unreachable or returns invalid JSON, the rule-based parser takes
              over and the answer is labelled “Rule-based (LLM failed)”.
            </>
          ) : (
            <>
              <strong>Fallback mode</strong> — no LLM API key is configured, so a deterministic keyword and month-name parser
              interprets questions. It only recognises the supported question types and declines everything else. Set{" "}
              <code>LLM_PROVIDER</code> and <code>LLM_API_KEY</code> in <code>.env</code> to enable LLM mode.
            </>
          )}
        </p>
        <p>In both modes the AI only chooses <em>which</em> approved analysis to run. Every number comes from SQLite.</p>
      </section>

      <section className="card prose">
        <h2>Revenue definition</h2>
        <p className="formula">Net revenue = Quantity × Unit price − Discount amount</p>
        <p>
          Counted only for transactions with status <code>Completed</code> and a known unit price. Returned transactions
          are excluded. Amounts are stored as integer paise so totals are exact.
        </p>
      </section>

      <section className="card prose">
        <h2>
          <Lock size={16} aria-hidden="true" /> Safety controls
        </h2>
        <ul>
          <li>No text-to-SQL: each intent maps to a fixed SQL template with bound parameters.</li>
          <li>Analytics run on a read-only SQLite connection with an authorizer that denies anything except reads.</li>
          <li>LLM output is schema-validated; unknown intents or malformed months are rejected.</li>
          <li>Questions that look like SQL commands are refused before interpretation.</li>
          <li>Errors are returned as generic messages; stack traces and keys stay in the server log.</li>
        </ul>
      </section>
    </div>
  );
}
