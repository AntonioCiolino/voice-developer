import { useState, useEffect } from "react";
import { quotes } from "./quotes";
import { clintonQuotes } from "./clintonQuotes";

const GAMES = {
  trumpObama: {
    title: "🇺🇸 Trump or Obama?",
    gradient: "from-red-100 via-white to-blue-100",
    players: ["Trump", "Obama"],
    playerStyles: {
      Trump: {
        base: "bg-red-100 border-red-400 hover:bg-red-200 text-red-700",
        emoji: "🔴",
      },
      Obama: {
        base: "bg-blue-100 border-blue-400 hover:bg-blue-200 text-blue-700",
        emoji: "🔵",
      },
    },
    quotes,
  },
  billHillary: {
    title: "🌟 Bill or Hillary?",
    gradient: "from-purple-100 via-white to-yellow-100",
    players: ["Bill", "Hillary"],
    playerStyles: {
      Bill: {
        base: "bg-purple-100 border-purple-400 hover:bg-purple-200 text-purple-700",
        emoji: "🟣",
      },
      Hillary: {
        base: "bg-yellow-100 border-yellow-400 hover:bg-yellow-200 text-yellow-700",
        emoji: "🟡",
      },
    },
    quotes: clintonQuotes,
  },
};

function shuffleArray(arr) {
  return [...arr].sort(() => Math.random() - 0.5);
}

export default function App() {
  const [selectedGame, setSelectedGame] = useState(null);
  const [gameQuotes, setGameQuotes] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState(null);
  const [score, setScore] = useState(0);
  const [finished, setFinished] = useState(false);

  const startGame = (gameKey) => {
    const game = GAMES[gameKey];
    setSelectedGame(gameKey);
    setGameQuotes(shuffleArray(game.quotes).slice(0, 10));
    setCurrentIndex(0);
    setSelectedAnswer(null);
    setScore(0);
    setFinished(false);
  };

  const goHome = () => {
    setSelectedGame(null);
    setFinished(false);
  };

  const game = selectedGame ? GAMES[selectedGame] : null;
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
    const base =
      "flex-1 py-4 px-6 rounded-2xl text-xl font-bold transition-all duration-200 border-4 ";
    if (!revealed) {
      return base + game.playerStyles[person].base + " cursor-pointer";
    }
    if (person === current.answer) {
      return base + "bg-green-400 border-green-600 text-white scale-105";
    }
    if (person === selectedAnswer) {
      return base + "bg-red-400 border-red-600 text-white";
    }
    return base + "bg-gray-100 border-gray-200 text-gray-400 opacity-50";
  };

  // Home screen
  if (!selectedGame) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-gray-100 via-white to-gray-200">
        <div className="text-center bg-white rounded-3xl shadow-2xl p-12 max-w-md w-full mx-4">
          <h1 className="text-4xl font-extrabold mb-2 text-gray-800">🎮 Quote Quiz</h1>
          <p className="text-gray-500 mb-8 text-lg">Choose a game to play!</p>
          <div className="flex flex-col gap-4">
            <button
              onClick={() => startGame("trumpObama")}
              className="bg-gradient-to-r from-red-500 to-blue-500 hover:from-red-600 hover:to-blue-600 text-white font-bold py-4 px-10 rounded-2xl text-xl transition-all duration-200 shadow-lg"
            >
              🇺🇸 Trump or Obama?
            </button>
            <button
              onClick={() => startGame("billHillary")}
              className="bg-gradient-to-r from-purple-500 to-yellow-500 hover:from-purple-600 hover:to-yellow-600 text-white font-bold py-4 px-10 rounded-2xl text-xl transition-all duration-200 shadow-lg"
            >
              🌟 Bill or Hillary?
            </button>
          </div>
        </div>
      </div>
    );
  }

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
      <div
        className={`flex items-center justify-center min-h-screen bg-gradient-to-br ${game.gradient}`}
      >
        <div className="text-center bg-white rounded-3xl shadow-2xl p-12 max-w-md w-full mx-4">
          <div className="text-7xl mb-4">{medal}</div>
          <h1 className="text-4xl font-extrabold mb-2 text-gray-800">Game Over!</h1>
          <p className="text-gray-500 mb-2 text-lg">You scored</p>
          <p className="text-6xl font-bold text-blue-600 mb-1">
            {score} / {gameQuotes.length}
          </p>
          <p className="text-gray-400 mb-8 text-lg">{percentage}% correct</p>
          <div className="flex flex-col gap-3">
            <button
              onClick={() => startGame(selectedGame)}
              className="bg-gradient-to-r from-red-500 to-blue-500 hover:from-red-600 hover:to-blue-600 text-white font-bold py-4 px-10 rounded-2xl text-xl transition-all duration-200 shadow-lg"
            >
              Play Again 🎉
            </button>
            <button
              onClick={goHome}
              className="bg-gray-100 hover:bg-gray-200 text-gray-600 font-bold py-3 px-10 rounded-2xl text-lg transition-all duration-200"
            >
              ← Back to Games
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`flex items-center justify-center min-h-screen bg-gradient-to-br ${game.gradient}`}
    >
      <div className="bg-white rounded-3xl shadow-2xl p-8 max-w-2xl w-full mx-4">
        {/* Header */}
        <div className="text-center mb-6">
          <h1 className="text-4xl font-extrabold text-gray-800 mb-1">{game.title}</h1>
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
          {game.players.map((person) => (
            <button
              key={person}
              onClick={() => handleGuess(person)}
              className={getButtonStyle(person)}
            >
              {game.playerStyles[person].emoji} {person}
            </button>
          ))}
        </div>

        {/* Feedback */}
        {revealed && (
          <div
            className={`rounded-2xl p-5 mb-6 text-center border-2 ${
              isCorrect ? "bg-green-50 border-green-300" : "bg-red-50 border-red-300"
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
          <div className="flex justify-between items-center">
            <button
              onClick={goHome}
              className="text-gray-400 hover:text-gray-600 font-semibold text-sm transition-all duration-200"
            >
              ← Games
            </button>
            <button
              onClick={handleNext}
              className="bg-gradient-to-r from-red-500 to-blue-500 hover:from-red-600 hover:to-blue-600 text-white font-bold py-3 px-10 rounded-2xl