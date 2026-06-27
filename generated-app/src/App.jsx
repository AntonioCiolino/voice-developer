import { useState } from "react";
import { quotes } from "./quotes";
import { clintonQuotes } from "./clintonQuotes";
import { jesusOrBuddhaQuotes } from "./jesusOrBuddhaQuotes";
import { dwightOrJimQuotes } from "./dwightOrJimQuotes";

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
  jesusOrBuddha: {
    title: "✝️ Jesus or Buddha?",
    gradient: "from-amber-100 via-white to-sky-100",
    players: ["Jesus", "Buddha"],
    playerStyles: {
      Jesus: {
        base: "bg-amber-100 border-amber-400 hover:bg-amber-200 text-amber-700",
        emoji: "✝️",
      },
      Buddha: {
        base: "bg-sky-100 border-sky-400 hover:bg-sky-200 text-sky-700",
        emoji: "☸️",
      },
    },
    quotes: jesusOrBuddhaQuotes,
  },
  dwightOrJim: {
    title: "🌱 Dwight or Jim?",
    gradient: "from-green-100 via-white to-orange-100",
    players: ["Dwight", "Jim"],
    playerStyles: {
      Dwight: {
        base: "bg-green-100 border-green-400 hover:bg-green-200 text-green-700",
        emoji: "🌱",
      },
      Jim: {
        base: "bg-orange-100 border-orange-400 hover:bg-orange-200 text-orange-700",
        emoji: "😏",
      },
    },
    quotes: dwightOrJimQuotes,
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
      "flex-1 py-4 px-6 rounded-2xl text-xl font-bold transition-all duration-200 border-4