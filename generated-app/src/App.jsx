import { useState, useEffect } from "react";
import { triviaQuestions as fallbackQuestions } from "./trivia";

function decodeHTML(html) {
  const txt = document.createElement("textarea");
  txt.innerHTML = html;
  return txt.value;
}

const CATEGORY_EMOJIS = ["🐾", "🌍", "🔬", "🎨", "🏆", "🎭", "🍕", "🚀", "🎵", "💡"];

async function fetchQuestions() {
  const res = await fetch(
    "https://opentdb.com/api.php?amount=10&type=boolean&difficulty=medium"
  );
  const data = await res.json();

  if (data.response_code !== 0 || !data.results?.length) {
    throw new Error("Bad response from API");
  }

  return data.results.map((item, i) => ({
    question: decodeHTML(item.question),
    answer: `${item.correct_answer === "True" ? "✅ True" : "❌ False"} — Category: ${decodeHTML(item.category)}`,
    emoji: CATEGORY_EMOJIS[i % CATEGORY_EMOJIS.length],
  }));
}

export default function App() {
  const [questions, setQuestions] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [finished, setFinished] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadQuestions = async () => {
    setLoading(true);
    setError(null);
    setCurrentIndex(0);
    setRevealed(false);
    setFinished(false);
    try {
      const fetched = await fetchQuestions();
      setQuestions(fetched);
    } catch (err) {
      console.error("Failed to fetch questions, using fallback.", err);
      // Shuffle fallback questions and pick 10
      const shuffled = [...fallbackQuestions].sort(() => Math.random() - 0.5).slice(0, 10);
      setQuestions(shuffled);
      setError("Couldn't reach the trivia API — using built-in questions instead.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadQuestions();
  }, []);

  const current = questions[currentIndex];

  const handleReveal = () => setRevealed(true);

  const handleNext = () => {
    if (currentIndex + 1 >= questions.length) {
      setFinished(true);
    } else {
      setCurrentIndex(currentIndex + 1);
      setRevealed(false);
    }
  };

  const handlePlayAgain = () => {
    loadQuestions();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100">
        <div className="text-center bg-white rounded-2xl shadow-lg p-10 max-w-md w-full mx-4">
          <div className="text-6xl mb-4 animate-bounce">🎲</div>
          <h1 className="text-2xl font-bold text-gray-700 mb-2">Loading Questions...</h1>
          <p className="text-gray-400">Fetching fresh trivia from the internet!</p>
        </div>
      </div>
    );
  }

  if (finished) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100">
        <div className="text-center bg-white rounded-2xl shadow-lg p-10 max-w-md w-full mx-4">
          <div className="text-6xl mb-4">🎉</div>
          <h1 className="text-3xl font-bold mb-2 text-green-600">Game Over!</h1>
          <p className="text-gray-600 mb-6">You've gone through all the trivia questions!</p>
          <button
            onClick={handlePlayAgain}
            className="bg-green-500 hover:bg-green-600 text-white font-semibold py-3 px-8 rounded-xl transition-colors duration-200"
          >
            Play Again with New Questions 🎲
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-100">
      <div className="bg-white rounded-2xl shadow-lg p-8 max-w-lg w-full mx-4">
        {/* Header */}
        <div className="text-center mb-6">
          <h1 className="text-3xl font-bold text-gray-800">🎲 Random Trivia</h1>
          <p className="text-sm text-gray-400 mt-1">
            Question {currentIndex + 1} of {questions.length}
          </p>
          {error && (
            <p className="text-xs text-orange-400 mt-1">{error}</p>
          )}
        </div>

        {/* Progress Bar */}
        <div className="w-full bg-gray-200 rounded-full h-2 mb-8">
          <div
            className="bg-blue-500 h-2 rounded-full transition-all duration-500"
            style={{ width: `${((currentIndex + 1) / questions.length) * 100}%` }}
          />
        </div>

        {/* Emoji */}
        <div className="text-center text-7xl mb-6">{current.emoji}</div>

        {/* Question */}
        <div className="bg-blue-50 rounded-xl p-5 mb-6">
          <p className="text-lg font-semibold text-gray-800 text-center">{current.question}</p>
        </div>

        {/* Answer */}
        {revealed ? (
          <div className="bg-green-50 border border-green-200 rounded-xl p-5 mb-6 text-center">
            <p className="text-sm font-semibold text-green-500 uppercase tracking-wide mb-1">Answer</p>
            <p className="text-gray-700 font-medium">{current.answer}</p>
          </div>
        ) : (
          <div className="bg-gray-50 border border-dashed border-gray-300 rounded-xl p-5 mb-6 text-center">
            <p className="text-gray-400 italic">Think you know the answer? Reveal it when ready!</p>
          </div>
        )}

        {/* Buttons */}
        <div className="flex gap-3 justify-center">
          {!revealed ? (
            <button
              onClick={handleReveal}
              className="bg-blue-500 hover:bg-blue-600 text-white font-semibold py-3 px-8 rounded-xl transition-colors duration-200"
            >
              Reveal Answer
            </button>
          ) : (
            <button
              onClick={handleNext}
              className="bg-green-500 hover:bg-green-600 text-white font-semibold py-3 px-8 rounded-xl transition-colors duration-200"
            >
              {currentIndex + 1 >= questions.length ? "Finish Game 🎉" : "Next Question →"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
