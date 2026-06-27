import { useMemo, useState } from "react";

const rounds = [
  {
    category: "Mountain",
    prompt: "Which statement about Mount Everest is the lie?",
    statements: [
      "It is the highest mountain above sea level on Earth.",
      "It is located in the Himalayas.",
      "It is the tallest mountain in the world when measured from base to peak.",
    ],
    lieIndex: 2,
    explanation:
      "Mount Everest is the highest above sea level, but Mauna Kea is taller from base to peak.",
  },
  {
    category: "Dog",
    prompt: "Which statement about dogs is the lie?",
    statements: [
      "Dogs are descendants of wolves.",
      "Dogs can understand human gestures and tone.",
      "All dogs are naturally born knowing how to fetch.",
    ],
    lieIndex: 2,
    explanation:
      "Dogs learn many behaviors, but fetching is not something every dog is born knowing.",
  },
  {
    category: "Object",
    prompt: "Which statement about a compass is the lie?",
    statements: [
      "It can help you find direction.",
      "It uses Earth’s magnetic field.",
      "It works best when placed near a strong magnet.",
    ],
    lieIndex: 2,
    explanation:
      "A strong magnet can interfere with a compass and make it less accurate.",
  },
];

export default function App() {
  const [roundIndex, setRoundIndex] = useState(0);
  const [selected, setSelected] = useState(null);
  const [showResult, setShowResult] = useState(false);
  const [score, setScore] = useState(0);

  const round = rounds[roundIndex];

  const isCorrect = useMemo(() => {
    if (selected === null) return false;
    return selected === round.lieIndex;
  }, [selected, round.lieIndex]);

  const handleGuess = (index) => {
    if (showResult) return;
    setSelected(index);
    setShowResult(true);
    if (index === round.lieIndex) {
      setScore((current) => current + 1);
    }
  };

  const nextRound = () => {
    setSelected(null);
    setShowResult(false);
    setRoundIndex((current) => (current + 1) % rounds.length);
  };

  const restart = () => {
    setRoundIndex(0);
    setSelected(null);
    setShowResult(false);
    setScore(0);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-100 via-white to-emerald-100 flex items-center justify-center p-4">
      <div className="w-full max-w-2xl rounded-3xl bg-white shadow-xl border border-gray-200 p-6 md:p-8">
        <div className="text-center mb-6">
          <p className="text-sm font-semibold uppercase tracking-widest text-indigo-600">
            Two Truths and a Lie
          </p>
          <h1 className="text-3xl md:text-4xl font-bold text-gray-900 mt-2">
            Fun facts, one fake
          </h1>
          <p className="text-gray-600 mt-3">
            Read the three statements and guess which one is the lie.
          </p>
        </div>

        <div className="flex items-center justify-between mb-5 text-sm text-gray-500">
          <span>
            Round {roundIndex + 1} of {rounds.length}
          </span>
          <span>Score: {score}</span>
        </div>

        <div className="rounded-2xl bg-gray-50 p-5 mb-6">
          <p className="text-sm font-semibold text-emerald-700 mb-2">
            Category: {round.category}
          </p>
          <h2 className="text-xl md:text-2xl font-bold text-gray-900">
            {round.prompt}
          </h2>
        </div>

        <div className="space-y-3">
          {round.statements.map((statement, index) => {
            const isSelected = selected === index;
            const revealCorrect = showResult && index === round.lieIndex;
            const revealWrong = showResult && isSelected && index !== round.lieIndex;

            let buttonClass =
              "w-full text-left rounded-2xl border px-4 py-4 transition-all duration-200 ";

            if (!showResult) {
              buttonClass +=
                "border-gray-200 hover:border-indigo-400 hover:bg-indigo-50";
            } else if (revealCorrect) {
              buttonClass += "border-emerald-500 bg-emerald-50";
            } else if (revealWrong) {
              buttonClass += "border-red-500 bg-red-50";
            } else {
              buttonClass += "border-gray-200 bg-gray-100 opacity-70";
            }

            return (
              <button
                key={statement}
                type="button"
                onClick={() => handleGuess(index)}
                className={buttonClass}
              >
                <div className="flex items-start gap-3">
                  <div className="mt-1 h-6 w-6 rounded-full border border-current flex items-center justify-center text-xs font-bold">
                    {index + 1}
                  </div>
                  <div>
                    <p className="text-gray-900 font-medium">{statement}</p>
                    {showResult && revealCorrect && (
                      <p className="text-emerald-700 text-sm mt-2">
                        Correct! This is the lie.
                      </p>
                    )}
                    {showResult && revealWrong && (
                      <p className="text-red-700 text-sm mt-2">
                        Nope — this one is true.
                      </p>
                    )}
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        {showResult && (
          <div className="mt-6 rounded-2xl bg-indigo-50 border border-indigo-200 p-5">
            <p className="font-semibold text-indigo-900">
              {isCorrect ? "Nice job!" : "Good try!"}
            </p>
            <p className="text-indigo-800 mt-1">{round.explanation}</p>
          </div>
        )}

        <div className="mt-6 flex flex-col sm:flex-row gap-3">
          <button
            type="button"
            onClick={nextRound}
            className="flex-1 rounded-2xl bg-indigo-600 px-5 py-3 font-semibold text-white hover:bg-indigo-700 transition-colors"
          >
            Next Round
          </button>
          <button
            type="button"
            onClick={restart}
            className="flex-1 rounded-2xl border border-gray-300 px-5 py-3 font-semibold text-gray-700 hover:bg-gray-50 transition-colors"
          >
            Restart Game
          </button>
        </div>
      </div>
    </div>
  );
}
