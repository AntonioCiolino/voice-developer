import { useState, useEffect } from "react";
import { quotes } from "./quotes";

function shuffleArray(arr) {
  return [...arr].sort(() => Math.random() - 0.5);
}

export default function App() {
  const [gameQuotes, setGameQuotes] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState(null);
  const [score, setScore] = useState(0);
  const [finished, setFinished] = useState(false);

  const startGame = () => {
    setGameQuotes(shuffleArray(quotes).slice(0, 10));
    setCurrentIndex(0);
    setSelectedAnswer(null);
    setScore(0);
    setFinished(false);
  };

  useEffect(() => {
    startGame();
  }, []);

  const current = gameQuotes[currentIndex];
  const revealed = selectedAnswer !== null;
  const isCorrect = selectedAnswer === current?.answer;

  const handleGuess = (person) => {
    if (revealed) return;
    setSelectedAnswer(person);
    if (person === current.answer) {
      setScore((s) => s + 1);
    }
  };

  const handleNext = () => {
    if (currentIndex + 1 >= gameQuotes.length) {
      setFinished(true);
    } else {
      setCurrentIndex(currentIndex + 1);
      setSelectedAnswer(null);
    }
  };

  const getButtonStyle = (person) => {
    const base = "flex-1 py-4 px-6 rounded-2xl text-xl font-bold transition-all duration-200 border-4 ";
    if (!revealed) {
      if (person === "Trump") {
        return base + "bg-red-100 border-red-400 hover:bg-red-200 text-red-700 cursor-pointer";
      } else {
        return base + "bg-blue-100 border-blue-400 hover:bg-blue-200 text-blue-700 cursor-pointer";
      }
    }
    if (person === current.answer) {
      return base + "bg-green-400 border-green-600 text-white scale-105";
    }
    if (person === selectedAnswer) {
      return base + "bg-red-400 border-red-600 text-white";
    }
    return base + "bg-gray-100 border-gray-200 text-gray-400 opacity-50";
  };

  if (!gameQuotes.length) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100">
        <div className="text-center text-gray-500 text-xl">Loading...</div>
      </div>
    );
  }

  if (finished) {
    const percentage = Math.round((score / gameQuotes.length) * 100);
    const medal =
      percentage === 100 ? "🏆" : percentage >= 70 ? "🥈" : percentage >= 40 ? "🥉" : "😅";

    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-red-100 via-white to-blue-100">
        <div className="text-center bg-white rounded-3xl shadow-2xl p-12 max-w-md w-full mx-4">
          <div className="text-7xl mb-4">{medal}</div>
          <h1 className="text-4xl font-extrabold mb-2 text-gray-800">Game Over!</h1>
          <p className="text-gray-500 mb-2 text-lg">You scored</p>
          <p className="text-6xl font-bold text-blue-600 mb-1">
            {score} / {gameQuotes.length}
          </p>
          <p className="text-gray-400 mb-8 text-lg">{percentage}% correct</p>
          <button
            onClick={startGame}
            className="bg-gradient-to-r from-red-500 to-blue-500 hover:from-red-600 hover:to-blue-600 text-white font-bold py-4 px-10 rounded-2xl text-xl transition-all duration-200 shadow-lg"
          >
            Play Again 🎉
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-red-100 via-white to-blue-100">
      <div className="bg-white rounded-3xl shadow-2xl p-8 max-w-2xl w-full mx-4">
        {/* Header */}
        <div className="text-center mb-6">
          <h1 className="text-4xl font-extrabold text-gray-800 mb-1">
            🇺🇸 Trump or Obama?
          </h1>
          <p className="text-gray-400 text-sm">
            Question {currentIndex + 1} of {gameQuotes.length} &nbsp;|&nbsp; Score: {score}
          </p>
        </div>

        {/* Progress Bar */}
        <div className="w-full bg-gray-200 rounded-full h-2 mb-8">
          <div
            className="bg-gradient-to-r from-red-400 to-blue-400 h-2 rounded-full transition-all duration-500"
            style={{ width: `${((currentIndex + 1) / gameQuotes.length) * 100}%` }}
          />
        </div>

        {/* Quote */}
        <div className="bg-gray-50 border-l-4 border-gray-300 rounded-2xl p-6 mb-8 shadow-inner">
          <p className="text-2xl font-semibold text-gray-800 text-center italic leading-relaxed">
            "{current.quote}"
          </p>
        </div>

        {/* Guess Buttons */}
        <div className="flex gap-4 mb-6">
          <button
            onClick={() => handleGuess("Trump")}
            className={getButtonStyle("Trump")}
          >
            🔴 Trump
          </button>
          <button
            onClick={() => handleGuess("Obama")}
            className={getButtonStyle("Obama")}
          >
            🔵 Obama
          </button>
        </div>

        {/* Feedback */}
        {revealed && (
          <div
            className={`rounded-2xl p-5 mb-6 text-center border-2 ${
              isCorrect
                ? "bg-green-50 border-green-300"
                : "bg-red-50 border-red-300"
            }`}
          >
            <p
              className={`font-extrabold text-2xl mb-2 ${
                isCorrect ? "text-green-600" : "text-red-500"
              }`}
            >
              {isCorrect ? "✅ Correct!" : `❌ It was ${current.answer}!`}
            </p>
            <p className="text-gray-600 text-sm">{current.explanation}</p>
          </div>
        )}

        {/* Next Button */}
        {revealed && (
          <div className="flex justify-center">
            <button
              onClick={handleNext}
              className="bg-gradient-to-r from-red-500 to-blue-500 hover:from-red-600 hover:to-blue-600 text-white font-bold py-3 px-10 rounded-2xl text-lg transition-all duration-200 shadow-md"
            >
              {currentIndex + 1 >= gameQuotes.length ? "See Results 🎉" : "Next Quote →"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
