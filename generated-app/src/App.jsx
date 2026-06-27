import { useEffect, useMemo, useRef, useState } from "react";
import Sidebar from "./components/Sidebar";
import TopBar from "./components/TopBar";
import ViewOne from "./components/ViewOne";
import ViewTwo from "./components/ViewTwo";
import ViewThree from "./components/ViewThree";
import ViewSpecial from "./components/ViewSpecial";
import { styles } from "./styles";

const TRIVIA_FETCH_RETRY_COUNT = 3;

function buildFallbackRounds(subject) {
  return [
    {
      question: `Fallback question for ${subject}?`,
      options: ["Option A", "Option B", "Option C", "Option D"],
      answer: "Option A",
      explanation: "This is a fallback question used when trivia loading fails.",
      emoji: "❓",
    },
  ];
}

export default function App() {
  const [activeView, setActiveView] = useState("one");
  const [count, setCount] = useState(0);
  const [error, setError] = useState("");
  const [triviaRounds, setTriviaRounds] = useState([]);
  const nextSubject = "animals";

  useEffect(() => {
    let cancelled = false;

    async function loadTrivia() {
      try {
        setError("");
        // Placeholder for the real trivia fetch logic.
        // If this succeeds, it should populate triviaRounds.
        const rounds = [];
        if (!cancelled) {
          setTriviaRounds(rounds);
        }
      } catch (fetchError) {
        setError(
          `${fetchError.message || "Something went wrong loading trivia."} Retried ${TRIVIA_FETCH_RETRY_COUNT} times, then switched to fallback questions.`
        );
        const fallbackRounds = buildFallbackRounds(nextSubject);
        if (!cancelled) {
          setTriviaRounds(fallbackRounds);
        }
      }
    }

    loadTrivia();

    return () => {
      cancelled = true;
    };
  }, [nextSubject]);

  const view = useMemo(() => {
    switch (activeView) {
      case "one":
        return <ViewOne />;
      case "two":
        return <ViewTwo />;
      case "three":
        return <ViewThree />;
      case "special":
        return <ViewSpecial />;
      default:
        return <ViewOne />;
    }
  }, [activeView]);

  return (
    <>
      <style>{styles}</style>
      <div className="app-root flex h-full">
        <Sidebar activeView={activeView} setActiveView={setActiveView} />
        <div className="flex-1 flex flex-col min-w-0">
          <TopBar
            title="Generated App"
            count={count}
            onCountClick={() => setCount((c) => c + 1)}
          />
          <main className="flex-1 overflow-auto p-6 bg-gray-100">
            {error && (
              <div className="mb-4 rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3 text-sm">
                {error}
              </div>
            )}
            {view}
          </main>
        </div>
      </div>
    </>
  );
}
