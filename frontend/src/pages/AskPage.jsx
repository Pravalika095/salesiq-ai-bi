import { MessageSquareText } from "lucide-react";
import AskPanel, { EXAMPLE_QUESTIONS } from "../components/AskPanel";
import AnswerCard from "../components/AnswerCard";

const MORE_EXAMPLES = [
  ...EXAMPLE_QUESTIONS,
  "Which products generated the least revenue?",
  "Show revenue by region.",
  "Revenue by sales channel",
  "How many units did we sell in May?",
];

export default function AskPage({ conversation, onAsk, asking, onClear }) {
  return (
    <div className="page page--narrow">
      <AskPanel onAsk={onAsk} loading={asking} examples={MORE_EXAMPLES} autoFocus />
      {conversation.length === 0 ? (
        <div className="card empty-hero">
          <MessageSquareText size={28} aria-hidden="true" />
          <h2>No questions yet</h2>
          <p>
            Try one of the examples above. Each answer shows the detected intent, which interpreter was used, and the
            exact figures from the database.
          </p>
        </div>
      ) : (
        <>
          <div className="section-bar">
            <span>
              {conversation.length} question{conversation.length > 1 ? "s" : ""} this session
            </span>
            <button className="link-btn" onClick={onClear}>
              Clear history
            </button>
          </div>
          {conversation.map((entry) => (
            <AnswerCard key={entry.id} entry={entry} />
          ))}
        </>
      )}
    </div>
  );
}
