import { useEffect, useMemo, useState } from "react";

const SUBJECTS = [
  {
    label: "Science",
    category: "Science",
    topic: "science",
    prompt: "Which statement about science is the lie?",
  },
  {
    label: "Animals",
    category: "Animals",
    topic: "animals",
    prompt: "Which statement about animals is the lie?",
  },
  {
    label: "Space",
    category: "Space",
    topic: "space",
    prompt: "Which statement about space is the lie?",
  },
  {
    label: "History",
    category: "History",
    topic: "history",
    prompt: "Which statement about history is the lie?",
  },
];

const TRIVIA_API_URL = "https://opentdb.com/api.php?amount=3&type=multiple";

function decodeHtmlEntities(text) {
  const textarea = document.createElement("textarea");
  textarea.innerHTML = text;
  return textarea.value;
}

function shuffle(array) {
  const copy = [...array];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

function buildRoundFromTrivia(triviaItem, subject) {
  const correctAnswer = decodeHtmlEntities(triviaItem.correct_answer);
  const incorrectAnswers = triviaItem.incorrect_answers.map(decodeHtmlEntities);
  const statements = shuffle([correctAnswer, ...incorrectAnswers]);

  const lieIndex = statements.findIndex((statement) => statement === correctAnswer);

  return {
    category: subject.category,
    prompt: subject.prompt,
    statements,
    lieIndex,
    explanation: `The correct answer from the trivia source was: ${correctAnswer}.`,
  };
}

function buildFallbackRounds(subject) {
  const templates = {
    Science: [
      {
        statements: [
          "Water boils at 100°C at sea level.",
          "Humans need oxygen to survive.",
          "The Sun is a planet.",
        ],
        lieIndex: 2,
        explanation: "The Sun is a star, not a planet.",
      },
      {
        statements: [
          "Plants use sunlight to make energy through photosynthesis.",
          "Lightning is hotter than the surface of the Sun.",
          "The Earth is flat.",
        ],
        lieIndex: 2,
        explanation: "The Earth is not flat.",
      },
      {
        statements: [
          "Atoms are made of smaller particles.",
          "Sound travels faster in water than in air.",
          "All metals are magnetic.",
        ],
        lieIndex: 2,
        explanation: "Not all metals are magnetic.",
      },
    ],
    Animals: [
      {
        statements: [
          "Dolphins are mammals.",
          "Bats are the only mammals that can truly fly.",
          "All birds can swim underwater.",
        ],
        lieIndex: 2,
        explanation: "Not all birds can swim underwater.",
      },
      {
        statements: [
          "Octopuses have three hearts.",
          "Dogs can learn to understand human gestures.",
          "All cats love water.",
        ],
        lieIndex: 2,
        explanation: "Not all cats love water.",
      },
      {
        statements: [
          "Penguins are birds.",
          "Some snakes lay eggs.",
          "Every fish lives in freshwater.",
        ],
        lieIndex: 2,
        explanation: "Many fish live in saltwater, not just freshwater.",
      },
    ],
    Space: [
      {
        statements: [
          "Mars is known as the Red Planet.",
          "A day on Venus is longer than a year on Venus.",
          "The Moon makes its own light.",
        ],
        lieIndex: 2,
        explanation: "The Moon reflects sunlight; it does not make its own light.",
      },
      {
        statements: [
          "Jupiter is the largest planet in our solar system.",
          "The Milky Way is a galaxy.",
          "The Sun orbits Earth.",
        ],
        lieIndex: 2,
        explanation: "Earth orbits the Sun, not the other way around.",
      },
      {
        statements: [
          "Astronauts can grow taller in space.",
          "Black holes can bend light.",
          "All stars are the same size.",
        ],
        lieIndex: 2,
        explanation: "Stars come in many different sizes.",
      },
    ],
    History: [
      {
        statements: [
          "The Great Wall of China is visible from space with the naked eye.",
          "Ancient Egyptians built pyramids.",
          "The Roman Empire existed.",
        ],
        lieIndex: 0,
        explanation:
          "The Great Wall of China is not generally visible from space with the naked eye.",
      },
      {
        statements: [
          "The printing press helped spread information.",
          "The Renaissance was a cultural movement.",
          "The first computers were invented in the Stone Age.",
        ],
        lieIndex: 2,
        explanation: "Computers were invented much later than the Stone Age.",
      },
      {
        statements: [
          "The Titanic sank in 1912.",
          "The United States declared independence in 1776.",
          "The first airplane flew before humans learned to write.",
        ],
        lieIndex: 2,
        explanation: "Humans learned to write long before the first airplane flew.",
      },
    ],
  };

  return templates[subject.category].map((round) => ({
    category: subject.category,
    prompt: subject.prompt,
    ...round,
  }));
}

async function fetchQuestionSet(subject) {
  const response = await fetch(TRIVIA_API_URL);

  if (!response.ok) {
    throw new Error("Failed to fetch trivia questions.");
  }

  const data = await response.json();

  if (!data?.results?.length) {
    throw new Error("No trivia questions were returned.");
  }

  return data.results.map((item) => buildRoundFromTrivia(item, subject));
}

export default function App() {
  const [subjectIndex, setSubjectIndex] = useState(0);
  const [rounds, setRounds] = useState([]);
  const [roundIndex, setRoundIndex] = useState(0);
  const [selected, setSelected] = useState(null);
  const [showResult, setShowResult] = useState(false);
  const [score, setScore] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const subject = SUBJECTS[subjectIndex];
  const round = rounds[roundIndex];

  const isCorrect = useMemo(() => {
    if (selected === null || !round) return false;
    return selected === round.lieIndex;
  }, [selected, round]);

  const loadQuestionSet = async (nextSubjectIndex = subjectIndex) => {
    const nextSubject = SUBJECTS[nextSubjectIndex];
    setLoading(true);
    setError("");

    try {
      const fetchedRounds = await fetchQuestionSet(nextSubject);
      setRounds(fetchedRounds);
      setRoundIndex(0);
      setSelected(null);
      setShowResult(false);
    } catch (fetchError) {
      setError(fetchError.message || "Something went wrong loading trivia.");
      const fallbackRounds = buildFallbackRounds(nextSubject);
      setRounds(fallbackRounds);
      setRoundIndex(0);
      setSelected(null);
      setShowResult(false);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadQuestionSet();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleGuess = (index) => {
    if (showResult || !round) return;
    setSelected(index);
    setShowResult(true);
    if (index === round.lieIndex) {
      setScore((current) => current + 1);
    }
  };

  const nextRound = () => {
    if (!rounds.length) return;

    const nextIndex = roundIndex + 1;

    if (nextIndex >= rounds.length) {
      const nextSubjectIndex = (subjectIndex + 1) % SUBJECTS.length;
      setSubjectIndex(nextSubjectIndex);
      loadQuestionSet(nextSubjectIndex);
      return;
    }

    setSelected(null);
    setShowResult(false);
    setRoundIndex(nextIndex);
  };

  const restart = () => {
    setRoundIndex(0);
    setSelected(null);
    setShowResult(false);
    setScore(0);
    loadQuestionSet(subjectIndex);
  };

  if (loading && !round) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-indigo-100 via-white to-emerald-100 flex items-center justify-center p-4">
        <div className="w-full max-w-2xl rounded-3xl bg-white shadow-xl border border-gray-200 p-6 md:p-8 text-center">
          <p className="text-lg font-semibold text-gray-900">Loading new trivia set...</p>
          <p className="text-gray-600 mt-2">Fetching fresh questions for you now.</p>
        </div>
      </div>
    );
  }

  if (!round) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-indigo-100 via-white to-emerald-100 flex items-center justify-center p-4">
        <div className="w-full max-w-2xl rounded-3xl bg-white shadow-xl border border-gray-200 p-6 md:p-8 text-center">
          <p className="text-lg font-semibold text-gray-900">No trivia available right now.</p>
          <button
            type="button"
            onClick={() => loadQuestionSet(subjectIndex)}
            className="mt-4 rounded-2xl bg-indigo-600 px-5 py-3 font-semibold text-white hover:bg-indigo-700 transition-colors"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-100 via-white to-emerald-100 flex items-center justify-center p-4">
      <div className="w-full max-w-2xl rounded-3xl bg-white shadow-xl border border-gray-200 p-6 md:p-8">
        <div className="text-center mb-6">
          <p className="text-sm font-semibold uppercase tracking-widest text-indigo-600">
            Two Truths and a Lie
          </p>
          <h1 className="text-3xl md:text-4xl font-bold text-gray-900 mt-2">
            Fresh trivia, one fake
          </h1>
          <p className="text-gray-600 mt-3">
            Read the three statements and guess which one is the lie.
          </p>
          <p className="text-sm text-gray-500 mt-2">
            Topic: {subject.label}
          </p>
        </div>

        <div className="flex items-center justify-between mb-5 text-sm text-gray-500">
          <span>
            Round {roundIndex + 1} of {rounds.length}
          </span>
          <span>Score: {score}</span>
        </div>

        {error && (
          <div className="mb-5 rounded-2xl border border-amber-200 bg-amber-50 p-4">
            <p className="font-semibold text-amber-900">Using fallback trivia</p>
            <p className="text-amber-800 text-sm mt-1">{error}</p>
          </div>
        )}

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
            New Question Set
          </button>
        </div>
      </div>
    </div>
  );
}
