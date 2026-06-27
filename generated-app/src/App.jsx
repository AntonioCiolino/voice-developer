import { useState, useEffect } from "react";
import { triviaQuestions as fallbackQuestions } from "./trivia";

function decodeHTML(html) {
  const txt = document.createElement("textarea");
  txt.innerHTML = html;
  return txt.value;
}

const CATEGORY_EMOJIS = ["🐾", "🌍", "🔬", "🎨", "🏆", "🎭", "🍕", "🚀", "🎵", "💡"];

function shuffleArray(arr) {
  return [...arr].sort(() => Math.random() - 0.5);
}

async function fetchQuestions() {
  const res = await fetch(
    "https://opentdb.com/api.php?amount=10&type=multiple&difficulty=medium"
  );
  const data = await res.json();

  if (data.response_code !== 0 || !data.results?.length) {
    throw new Error("Bad response from API");
  }

  return data.results.map((item, i) => {
    const correct = decodeHTML(item.correct_answer);
    const options = shuffleArray([
      correct,
      ...item.incorrect_answers.map(decodeHTML),
    ]);
    return {
      question: decodeHTML(item.question),
      options,
      answer: correct,
      explanation: `The correct answer is: ${correct}`,
      emoji: CATEGORY_EMOJIS[i % CATEGORY_EMOJIS.length],
    };
  });
}

export default function App() {
  const [questions, setQuestions] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedOption, setSelectedOption] = useState(null);
  const [score, setScore] = useState(0);
  const [finished, setFinished] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadQuestions = async () => {
    setLoading(true);
    setError(null);
    setCurrentIndex(0);
    setSelectedOption(null);
    setScore(0);
    setFinished(false);
    try {
      const fetched = await fetchQuestions();
      setQuestions(fetched);
    } catch (err) {
      console.error("Failed to fetch questions, using fallback.", err);
      const shuffled = shuffleArray(fallbackQuestions).slice(0, 10);
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
  const revealed = selectedOption !== null;
  const isCorrect = selectedOption === current?.answer;

  const handleSelect = (option) => {
    if (revealed) return;
    setSelectedOption(option);
    if (option === current.answer) {
      setScore((s) => s + 1);
    }
  };

  const handleNext = () => {
    if (currentIndex + 1 >= questions.length) {
      setFinished(true);
    } else {
      setCurrentIndex(currentIndex + 1);
      setSelectedOption(null);
    }
  };

  const getOptionStyle = (option) => {
    if (!revealed) {
      return "bg-white border-2 border-gray-200 hover:border-blue-400 hover:bg-blue-50 text-gray-700 cursor-pointer";
    }
    if (option === current.answer) {
      return "bg-green-100 border-2 border-green-500 text-green-800 font-semibold";
    }
    if (option === selectedOption) {
      return "bg-red-100 border-2 border-red-400 text-red-700";
    }
    return "bg-gray-50 border-2 border-gray-200 text-gray-400";
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100">
        <div className="text-center bg-white rounded-2xl shadow-lg p-10 max-w-md w-full mx-4">
          <div className="text-6xl mb-4 animate-bounce">🐾</div>
          <h1 className="text-2xl font-bold text-gray-700 mb-2">Loading Questions...</h1>
          <p className="text-gray-400">Fetching fresh trivia from the internet!</p>
        </div>
      </div>
    );
  }

  if (finished) {
    const percentage = Math.round((score / questions.length) * 100);
    const medal = percentage === 100 ? "🏆" : percentage >= 70 ? "🥈" : percentage >= 40 ? "🥉" : "😅";
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100">
        <div className="text-center bg-white rounded-2xl shadow-lg p-10 max-w-md w-full mx-4">
          <div className="text-6xl mb-4">{medal}</div>
          <h1 className="text-3xl font-bold mb-2 text-green-600">Game Over!</h1>
          <p className="text-gray-600 mb-2">You scored</p>
          <p className="text-5xl font-bold text-blue-600 mb-1">{score} / {questions.length}</p>
          <p className="text-gray-400 mb-6">{percentage}% correct</p>
          <button
            onClick={loadQuestions}
            className="bg-green-500 hover:bg-green-600 text-white font-semibold py-3 px-8 rounded-xl transition-colors duration-200"
          >
            Play Again 🎉
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
          <h1 className="text-3xl font-bold text-gray-800">🐾 Animal Trivia</h1>
          <p className="text-sm text-gray-400 mt-1">
            Question {currentIndex + 1} of {questions.length} &nbsp;|&nbsp; Score: {score}
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

        {/* Options */}
        <div className="grid grid-cols-1 gap-3 mb-6">
          {current.options.map((option) => (
            <button
              key={option}
              onClick={() => handleSelect(option)}
              className={`w-full text-left px-5 py-3 rounded-xl transition-all duration-200 ${getOptionStyle(option)}`}
            >
              {option}
            </button>
          ))}
        </div>

        {/* Feedback */}
        {revealed && (
          <div className={`rounded-xl p-4 mb-6 text-center ${isCorrect ? "bg-green-50 border border-green-200" : "bg-red-50 border border-red-200"}`}>
            <p className={`font-bold text-lg mb-1 ${isCorrect ? "text-green-600" : "text-red-500"}`}>
              {isCorrect ? "✅ Correct!" : "❌ Wrong!"}
            </p>
            <p className="text-gray-600 text-sm">{current.explanation}</p>
          </div>
        )}

        {/* Next Button */}
        {revealed && (
          <div className="flex justify-center">
            <button
              onClick={handleNext}
              className="bg-blue-500 hover:bg-blue-600 text-white font-semibold py-3 px-8 rounded-xl transition-colors duration-200"
            >
              {currentIndex + 1 >= questions.length ? "See Results 🎉" : "Next Question →"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
