import { useState } from "react";
import { quotes } from "./quotes";
import { clintonQuotes } from "./clintonQuotes";
import { jesusOrBuddhaQuotes } from "./jesusOrBuddhaQuotes";
import { dwightOrJimQuotes } from "./dwightOrJimQuotes";
import { triviaQuestions } from "./trivia";

const GAMES = {
  trumpObama: {
    title: "Trump or Obama?",
    emoji: "🇺🇸",
    gradient: "from-red-200 via-white to-blue-200",
    cardBg: "bg-white",
    players: ["Trump", "Obama"],
    playerStyles: {
      Trump: {
        base: "bg-red-100 border-red-400 hover:bg-red-200 text-red-700",
        selected: "bg-red-400 border-red-600 text-white scale-105",
        correct: "bg-red-500 border-red-700 text-white",
        emoji: "🔴",
      },
      Obama: {
        base: "bg-blue-100 border-blue-400 hover:bg-blue-200 text-blue-700",
        selected: "bg-blue-400 border-blue-600 text-white scale-105",
        correct: "bg-blue-500 border-blue-700 text-white",
        emoji: "🔵",
      },
    },
    quotes,
  },
  billHillary: {
    title: "Bill or Hillary?",
    emoji: "🌟",
    gradient: "from-purple-200 via-white to-yellow-100",
    cardBg: "bg-white",
    players: ["Bill", "Hillary"],
    playerStyles: {
      Bill: {
        base: "bg-purple-100 border-purple-400 hover:bg-purple-200 text-purple-700",
        selected: "bg-purple-400 border-purple-600 text-white scale-105",
        correct: "bg-purple-500 border-purple-700 text-white",
        emoji: "🟣",
      },
      Hillary: {
        base: "bg-yellow-100 border-yellow-400 hover:bg-yellow-200 text-yellow-700",
        selected: "bg-yellow-400 border-yellow-600 text-white scale-105",
        correct: "bg-yellow-500 border-yellow-700 text-white",
        emoji: "🟡",
      },
    },
    quotes: clintonQuotes,
  },
  jesusOrBuddha: {
    title: "Jesus or Buddha?",
    emoji: "✝️",
    gradient: "from-amber-100 via-white to-sky-100",
    cardBg: "bg-white",
    players: ["Jesus", "Buddha"],
    playerStyles: {
      Jesus: {
        base: "bg-amber-100 border-amber-400 hover:bg-amber-200 text-amber-700",
        selected: "bg-amber-400 border-amber-600 text-white scale-105",
        correct: "bg-amber-500 border-amber-700 text-white",
        emoji: "✝️",
      },
      Buddha: {
        base: "bg-sky-100 border-sky-400 hover:bg-sky-200 text-sky-700",
        selected: "bg-sky-400 border-sky-600 text-white scale-105",
        correct: "bg-sky-500 border-sky-700 text-white",
        emoji: "☸️",
      },
    },
    quotes: jesusOrBuddhaQuotes,
  },
  dwightOrJim: {
    title: "Dwight or Jim?",
    emoji: "🌱",
    gradient: "from-green-100 via-white to-orange-100",
    cardBg: "bg-white",
    players: ["Dwight", "Jim"],
    playerStyles: {
      Dwight: {
        base: "bg-green-100 border-green-400 hover:bg-green-200 text-green-700",
        selected: "bg-green-400 border-green-600 text-white scale-105",
        correct: "bg-green-500 border-green-700 text-white",
        emoji: "🌱",
      },
      Jim: {
        base: "bg-orange-100 border-orange-400 hover:bg-orange-200 text-orange-700",
        selected: "bg-orange-400 border-orange-600 text-white scale-105",
        correct: "bg-orange-500 border-orange-700 text-white",
        emoji: "😏",
      },
    },
    quotes: dwightOrJimQuotes,
  },
};

function shuffleArray(arr) {
  return [...arr].sort(() => Math.random() - 0.5);
}

function getScoreMessage(score, total) {
  const pct = score / total;
  if (pct === 1) return "Perfect score! 🏆 You're a genius!";
  if (pct >= 0.8) return "Great job! 🎉 Almost perfect!";
  if (pct >= 0.6) return "Not bad! 👍 You know your stuff.";
  if (pct >= 0.4) return "Could be better. 🤔 Try again?";
  return "Yikes! 😅 Better luck next time!";
}

// ─── Trivia Game ────────────────────────────────────────────────────────────

function TriviaGame({ onHome }) {
  const [questions] = useState(() => shuffleArray(triviaQuestions).slice(0, 10));
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState(null);
  const [score, setScore] = useState(0);
  const [finished, setFinished] = useState(false);

  const current = questions[currentIndex];
  const revealed = selectedAnswer !== null;
  const isCorrect = selectedAnswer === current?.answer;

  const handleGuess = (option) => {
    if (revealed) return;
    setSelectedAnswer(option);
    if (option === current.answer) setScore((s) => s + 1);
  };

  const handleNext = () => {
    if (currentIndex + 1 >= questions.length) {
      setFinished(true);
    } else {
      setCurrentIndex(currentIndex + 1);
      setSelectedAnswer(null);
    }
  };

  if (finished) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-teal-100 via-white to-cyan-100 flex flex-col items-center justify-center p-6">
        <div className="bg-white rounded-3xl shadow-2xl p-10 max-w-md w-full text-center">
          <div className="text-6xl mb-4">🧠</div>
          <h2 className="text-3xl font-extrabold text-gray-800 mb-2">Quiz Complete!</h2>
          <p className="text-xl text-gray-500 mb-6">{getScoreMessage(score, questions.length)}</p>
          <div className="text-6xl font-black text-teal-600 mb-2">
            {score} / {questions.length}
          </div>
          <p className="text-gray-400 mb-8">correct answers</p>
          <div className="flex gap-3">
            <button
              onClick={onHome}
              className="flex-1 py-3 rounded-2xl bg-gray-100 hover:bg-gray-200 text-gray-700 font-bold text-lg transition"
            >
              🏠 Home
            </button>
            <button
              onClick={() => {
                setCurrentIndex(0);
                setSelectedAnswer(null);
                setScore(0);
                setFinished(false);
              }}
              className="flex-1 py-3 rounded-2xl bg-teal-500 hover:bg-teal-600 text-white font-bold text-lg transition"
            >
              🔄 Play Again
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-teal-100 via-white to-cyan-100 flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-xl">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <button
            onClick={onHome}
            className="text-sm font-semibold text-gray-500 hover:text-gray-800 bg-white px-4 py-2 rounded-xl shadow transition"
          >
            ← Home
          </button>
          <span className="text-sm font-bold text-gray-500">
            {currentIndex + 1} / {questions.length}
          </span>
          <span className="text-sm font-bold text-teal-600 bg-white px-4 py-2 rounded-xl shadow">
            Score: {score}
          </span>
        </div>

        {/* Progress Bar */}
        <div className="w-full bg-gray-200 rounded-full h-2 mb-6">
          <div
            className="bg-teal-500 h-2 rounded-full transition-all duration-500"
            style={{ width: `${((currentIndex + 1) / questions.length) * 100}%` }}
          />
        </div>

        {/* Card */}
        <div className="bg-white rounded-3xl shadow-2xl p-8 mb-6">
          <div className="text-5xl text-center mb-4">{current.emoji}</div>
          <p className="text-xl font-bold text-gray-800 text-center mb-6">{current.question}</p>

          <div className="grid grid-cols-1 gap-3">
            {current.options.map((option) => {
              let style =
                "w-full py-3 px-5 rounded-2xl border-2 font-semibold text-left transition-all duration-200 ";
              if (!revealed) {
                style +=
                  "bg-gray-50 border-gray-200 hover:bg-teal-50 hover:border-teal-400 text-gray-700 cursor-pointer";
              } else if (option === current.answer) {
                style += "bg-green-100 border-green-500 text-green-800";
              } else if (option === selectedAnswer) {
                style += "bg-red-100 border-red-400 text-red-700";
              } else {
                style += "bg-gray-50 border-gray-200 text-gray-400 opacity-60";
              }

              return (
                <button key={option} className={style} onClick={() => handleGuess(option)}>
                  {revealed && option === current.answer && "✅ "}
                  {revealed && option === selectedAnswer && option !== current.answer && "❌ "}
                  {option}
                </button>
              );
            })}
          </div>

          {revealed && (
            <div
              className={`mt-5 p-4 rounded-2xl text-sm font-medium ${
                isCorrect ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"
              }`}
            >
              {isCorrect ? "🎉 Correct! " : `❌ The answer was "${current.answer}". `}
              {current.explanation}
            </div>
          )}
        </div>

        {revealed && (
          <button
            onClick={handleNext}
            className="w-full py-4 rounded-2xl bg-teal-500 hover:bg-teal-600 text-white font-bold text-xl shadow-lg transition"
          >
            {currentIndex + 1 >= questions.length ? "See Results 🏁" : "Next Question →"}
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Quote Game ──────────────────────────────────────────────────────────────

function QuoteGame({ gameKey, onHome }) {
  const game = GAMES[gameKey];
  const [gameQuotes] = useState(() => shuffleArray(game.quotes).slice(0, 10));
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState(null);
  const [score, setScore] = useState(0);
  const [finished, setFinished] = useState(false);

  const current = gameQuotes[currentIndex];
  const revealed = selectedAnswer !== null;
  const isCorrect = selectedAnswer === current?.answer;

  const handleGuess = (person) => {
    if (revealed) return;
    setSelectedAnswer(person);
    if (person === current.answer) setScore((s) => s + 1);
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
    const styles = game.playerStyles[person];
    if (!revealed) {
      return `flex-1 py-4 px-6 rounded-2xl text-lg font-bold transition-all duration-200 border-4 cursor-pointer ${styles.base}`;
    }
    if (person === current.answer) {
      return `flex-1 py-4 px-6 rounded-2xl text-lg font-bold transition-all duration-200 border-4 ${styles.correct}`;
    }
    if (person === selectedAnswer) {
      return "flex-1 py-4 px-6 rounded-2xl text-lg font-bold transition-all duration-200 border-4 bg-gray-200 border-gray-400 text-gray-500 line-through";
    }
    return `flex-1 py-4 px-6 rounded-2xl text-lg font-bold transition-all duration-200 border-4 opacity-40 ${styles.base}`;
  };

  if (finished) {
    return (
      <div className={`min-h-screen bg-gradient-to-br ${game.gradient} flex flex-col items-center justify-center p-6`}>
        <div className="bg-white rounded-3xl shadow-2xl p-10 max-w-md w-full text-center">
          <div className="text-6xl mb-4">{game.emoji}</div>
          <h2 className="text-3xl font-extrabold text-gray-800 mb-2">Game Over!</h2>
          <p className="text-xl text-gray-500 mb-6">{getScoreMessage(score, gameQuotes.length)}</p>
          <div className="text-6xl font-black text-indigo-600 mb-2">
            {score} / {gameQuotes.length}
          </div>
          <p className="text-gray-400 mb-8">correct answers</p>
          <div className="flex gap-3">
            <button
              onClick={onHome}
              className="flex-1 py-3 rounded-2xl bg-gray-100 hover:bg-gray-200 text-gray-700 font-bold text-lg transition"
            >
              🏠 Home
            </button>
            <button
              onClick={() => {
                setCurrentIndex(0);
                setSelectedAnswer(null);
                setScore(0);
                setFinished(false);
              }}
              className="flex-1 py-3 rounded-2xl bg-indigo-500 hover:bg-indigo-600 text-white font-bold text-lg transition"
            >
              🔄 Play Again
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`min-h-screen bg-gradient-to-br ${game.gradient} flex flex-col items-center justify-center p-4`}>
      <div className="w-full max-w-xl">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <button
            onClick={onHome}
            className="text-sm font-semibold text-gray-500 hover:text-gray-800 bg-white px-4 py-2 rounded-xl shadow transition"
          >
            ← Home
          </button>
          <span className="text-sm font-bold text-gray-500">
            {currentIndex + 1} / {gameQuotes.length}
          </span>
          <span className="text-sm font-bold text-indigo-600 bg-white px-4 py-2 rounded-xl shadow">
            Score: {score}
          </span>
        </div>

        {/* Progress Bar */}
        <div className="w-full bg-gray-200 rounded-full h-2 mb-6">
          <div
            className="bg-indigo-500 h-2 rounded-full transition-all duration-500"
            style={{ width: `${((currentIndex + 1) / gameQuotes.length) * 100}%` }}
          />
        </div>

        {/* Card */}
        <div className="bg-white rounded-3xl shadow-2xl p-8 mb-6">
          <div className="text-5xl text-center mb-4">{game.emoji}</div>
          <p className="text-xl font-bold text-gray-800 text-center mb-6">{current.quote}</p>

          <div className="flex flex-col sm:flex-row gap-3">
            {game.players.map((person) => {
              const styles = game.playerStyles[person];
              return (
                <button key={person} className={getButtonStyle(person)} onClick={() => handleGuess(person)}>
                  <span className="mr-2">{styles.emoji}</span>
                  {person}
                </button>
              );
            })}
          </div>

          {revealed && (
            <div
              className={`mt-5 p-4 rounded-2xl text-sm font-medium ${
                isCorrect ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"
              }`}
            >
              {isCorrect ? "🎉 Correct! " : `❌ The answer was "${current.answer}". `}
              {current.explanation}
            </div>
          )}
        </div>

        {revealed && (
          <button
            onClick={handleNext}
            className="w-full py-4 rounded-2xl bg-indigo-500 hover:bg-indigo-600 text-white font-bold text-xl shadow-lg transition"
          >
            {currentIndex + 1 >= gameQuotes.length ? "See Results 🏁" : "Next Quote →"}
          </button>
        )}
      </div>
    </div>
  );
}

function HomeScreen({ onSelectGame }) {
  const cards = [
    {
      key: "trumpObama",
      title: GAMES.trumpObama.title,
      emoji: GAMES.trumpObama.emoji,
      gradient: "from-red-100 to-blue-100",
      description: "Guess whether each quote was said by Trump or Obama.",
    },
    {
      key: "billHillary",
      title: GAMES.billHillary.title,
      emoji: GAMES.billHillary.emoji,
      gradient: "from-purple-100 to-yellow-100",
      description: "Can you tell Bill and Hillary Clinton apart?",
    },
    {
      key: "jesusOrBuddha",
      title: GAMES.jesusOrBuddha.title,
      emoji: GAMES.jesusOrBuddha.emoji,
      gradient: "from-amber-100 to-sky-100",
      description: "Match the quote to Jesus or Buddha.",
    },
    {
      key: "dwightOrJim",
      title: GAMES.dwightOrJim.title,
      emoji: GAMES.dwightOrJim.emoji,
      gradient: "from-green-100 to-orange-100",
      description: "Identify whether the quote came from Dwight or Jim.",
    },
    {
      key: "trivia",
      title: "Animal Trivia",
      emoji: "🧠",
      gradient: "from-teal-100 to-cyan-100",
      description: "Test your knowledge with fun animal facts.",
    },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-100 via-white to-slate-200 flex items-center justify-center p-6">
      <div className="w-full max-w-5xl">
        <div className="text-center mb-10">
          <div className="text-6xl mb-4">🎮</div>
          <h1 className="text-4xl md:text-5xl font-black text-gray-800 mb-3">Quote & Trivia Games</h1>
          <p className="text-lg text-gray-500">Pick a game and see how well you know your quotes and facts.</p>
        </div>

        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {cards.map((card) => (
            <button
              key={card.key}
              onClick={() => onSelectGame(card.key)}
              className={`text-left rounded-3xl p-6 shadow-lg hover:shadow-2xl transition transform hover:-translate-y-1 bg-gradient-to-br ${card.gradient}`}
            >
              <div className="text-4xl mb-4">{card.emoji}</div>
              <h2 className="text-2xl font-extrabold text-gray-800 mb-2">{card.title}</h2>
              <p className="text-gray-600">{card.description}</p>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [screen, setScreen] = useState("home");

  if (screen === "trivia") return <TriviaGame onHome={() => setScreen("home")} />;
  if (screen === "trumpObama") return <QuoteGame gameKey="trumpObama" onHome={() => setScreen("home")} />;
  if (screen === "billHillary") return <QuoteGame gameKey="billHillary" onHome={() => setScreen("home")} />;
  if (screen === "jesusOrBuddha") return <QuoteGame gameKey="jesusOrBuddha" onHome={() => setScreen("home")} />;
  if (screen === "dwightOrJim") return <QuoteGame gameKey="dwightOrJim" onHome={() => setScreen("home")} />;

  return <HomeScreen onSelectGame={setScreen} />;
}
