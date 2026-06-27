import { useState } from "react";
import { triviaQuestions } from "./trivia";

export default function App() {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [finished, setFinished] = useState(false);

  const current = triviaQuestions[currentIndex];

  const handleReveal = () => {
    setRevealed(true);
  };

  const handleNext = () => {
    if (currentIndex + 1 >= triviaQuestions.length) {
      setFinished(true);
    } else {
      setCurrentIndex(currentIndex + 1);
      setRevealed(false);
    }
  };

  const handleRestart = () => {
    setCurrentIndex(0);
    setRevealed(false);
    setFinished(false);
  };

  if (finished) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100">
        <div className="text-center bg-white rounded-2xl shadow-lg p-10 max-w-md w-full mx-4">
          <div className="text-6xl mb-4">🎉</div>
          <h1 className="text-3xl font-bold mb-2 text-green-600">Game Over!</h1>
          <p className="text-gray-600 mb-6">You've gone through all the animal trivia questions!</p>
          <button
            onClick={handleRestart}
            className="bg-green-500 hover:bg-green-600 text-white font-semibold py-3 px-8 rounded-xl transition-colors duration-200"
          >
            Play Again
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
            Question {currentIndex + 1} of {triviaQuestions.length}
          </p>
        </div>

        {/* Progress Bar */}
        <div className="w-full bg-gray-200 rounded-full h-2 mb-8">
          <div
            className="bg-blue-500 h-2 rounded-full transition-all duration-500"
            style={{ width: `${((currentIndex + 1) / triviaQuestions.length) * 100}%` }}
          />
        </div>

        {/* Animal Emoji */}
        <div className="text-center text-7xl mb-6">{current.emoji}</div>

        {/* Question */}
        <div className="bg-blue-50 rounded-xl p-5 mb-6">
          <p className="text-lg font-semibold text-gray-800 text-center">{current.question}</p>
        </div>

        {/* Answer (revealed on button click) */}
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
              {currentIndex + 1 >= triviaQuestions.length ? "Finish Game 🎉" : "Next Question →"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
