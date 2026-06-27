import { useEffect, useMemo, useState } from "react";

const SUBJECTS = [
  {
    label: "Nature",
    category: "Nature",
    topic: "nature",
    prompt: "Which statement about nature is the lie?",
    accent: "from-emerald-500 to-lime-500",
    glow: "shadow-emerald-200",
  },
  {
    label: "Science",
    category: "Science",
    topic: "science",
    prompt: "Which statement about science is the lie?",
    accent: "from-cyan-500 to-blue-500",
    glow: "shadow-cyan-200",
  },
  {
    label: "Animals",
    category: "Animals",
    topic: "animals",
    prompt: "Which statement about animals is the lie?",
    accent: "from-rose-500 to-orange-500",
    glow: "shadow-rose-200",
  },
  {
    label: "Space",
    category: "Space",
    topic: "space",
    prompt: "Which statement about space is the lie?",
    accent: "from-violet-500 to-fuchsia-500",
    glow: "shadow-violet-200",
  },
];

const TRIVIA_API_URL = "https://opentdb.com/api.php?amount=5&type=multiple";
const THEME_STORAGE_KEY = "two-truths-theme";
const TRIVIA_FETCH_RETRY_COUNT = 3;
const TRIVIA_FETCH_RETRY_DELAY_MS = 800;

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

function delay(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
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
    Nature: [
      {
        statements: [
          "Trees absorb carbon dioxide from the air.",
          "Rainforests receive a lot of rainfall each year.",
          "All deserts are covered in snow year-round.",
        ],
        lieIndex: 2,
        explanation: "Deserts are typically dry, not covered in snow year-round.",
      },
      {
        statements: [
          "Bees help pollinate many plants.",
          "Oceans cover most of Earth's surface.",
          "Every plant needs saltwater to grow.",
        ],
        lieIndex: 2,
        explanation: "Most plants do not need saltwater to grow.",
      },
      {
        statements: [
          "Mountains can form when tectonic plates collide.",
          "Ferns reproduce using spores.",
          "All rivers flow uphill.",
        ],
        lieIndex: 2,
        explanation: "Rivers flow downhill, not uphill.",
      },
      {
        statements: [
          "Some flowers bloom only at night.",
          "Moss often grows in damp places.",
          "All rocks are alive.",
        ],
        lieIndex: 2,
        explanation: "Rocks are not alive.",
      },
      {
        statements: [
          "Leaves can change color in autumn.",
          "The water cycle includes evaporation and precipitation.",
          "All clouds are made of cotton.",
        ],
        lieIndex: 2,
        explanation: "Clouds are made of tiny water droplets or ice crystals, not cotton.",
      },
    ],
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
      {
        statements: [
          "Gravity pulls objects toward Earth.",
          "A magnet can attract some metals.",
          "All liquids are invisible.",
        ],
        lieIndex: 2,
        explanation: "Liquids are visible, even if some are clear.",
      },
      {
        statements: [
          "Electricity can power light bulbs.",
          "The human body has bones.",
          "All gases are heavier than rocks.",
        ],
        lieIndex: 2,
        explanation: "Gases are not heavier than rocks in general.",
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
      {
        statements: [
          "Elephants are the largest land animals.",
          "Some frogs can live both in water and on land.",
          "All insects have eight legs.",
        ],
        lieIndex: 2,
        explanation: "Insects have six legs, not eight.",
      },
      {
        statements: [
          "Whales breathe air.",
          "Honeybees live in colonies.",
          "All mammals lay eggs.",
        ],
        lieIndex: 2,
        explanation: "Most mammals give birth to live young; only a few lay eggs.",
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
      {
        statements: [
          "Saturn has rings.",
          "The Moon affects ocean tides.",
          "All planets are made of cheese.",
        ],
        lieIndex: 2,
        explanation: "Planets are not made of cheese.",
      },
      {
        statements: [
          "A year on Mercury is shorter than a year on Earth.",
          "Space is mostly empty.",
          "All comets are made of fire.",
        ],
        lieIndex: 2,
        explanation: "Comets are made mostly of ice, dust, and rock.",
      },
    ],
  };

  return templates[subject.category].map((round) => ({
    category: subject.category,
    prompt: subject.prompt,
    ...round,
  }));
}

async function fetchQuestionSetOnce(subject) {
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

async function fetchQuestionSetWithRetry(subject, retryCount = TRIVIA_FETCH_RETRY_COUNT) {
  let lastError = null;

  for (let attempt = 0; attempt <= retryCount; attempt += 1) {
    try {
      return await fetchQuestionSetOnce(subject);
    } catch (error) {
      lastError = error;

      if (attempt < retryCount) {
        await delay(TRIVIA_FETCH_RETRY_DELAY_MS);
      }
    }
  }

  throw lastError || new Error("Failed to fetch trivia questions.");
}

function DecorativeOrbs({ theme }) {
  const isDark = theme === "dark";

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      <div
        className={`absolute -top-24 left-[-5rem] h-72 w-72 rounded-full blur-3xl animate-pulse ${
          isDark ? "bg-indigo-500/20" : "bg-indigo-300/30"
        }`}
      />
      <div
        className={`absolute top-1/3 right-[-4rem] h-80 w-80 rounded-full blur-3xl animate-pulse [animation-delay:1.5s] ${
          isDark ? "bg-emerald-500/15" : "bg-emerald-300/25"
        }`}
      />
      <div
        className={`absolute bottom-[-6rem] left-1/3 h-72 w-72 rounded-full blur-3xl animate-pulse [animation-delay:3s] ${
          isDark ? "bg-fuchsia-500/15" : "bg-fuchsia-300/20"
        }`}
      />
    </div>
  );
}

function StatPill({ label, value, tone = "indigo", theme = "light" }) {
  const tones = {
    light: {
      indigo: "bg-indigo-50 text-indigo-700 border-indigo-200",
      emerald: "bg-emerald-50 text-emerald-700 border-emerald-200",
      rose: "bg-rose-50 text-rose-700 border-rose-200",
      amber: "bg-amber-50 text-amber-700 border-amber-200",
    },
    dark: {
      indigo: "bg-slate-800 text-indigo-200 border-slate-700",
      emerald: "bg-slate-800 text-emerald-200 border-slate-700",
      rose: "bg-slate-800 text-rose-200 border-slate-700",
      amber: "bg-slate-800 text-amber-200 border-slate-700",
    },
  };

  return (
    <div className={`rounded-2xl border px-4 py-3 ${tones[theme][tone]}`}>
      <p className="text-[11px] uppercase tracking-[0.2em] font-bold opacity-80">{label}</p>
      <p className="text-lg font-extrabold leading-none mt-1">{value}</p>
    </div>
  );
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
  const [theme, setTheme] = useState(() => {
    if (typeof window === "undefined") return "light";
    return localStorage.getItem(THEME_STORAGE_KEY) || "light";
  });

  const subject = SUBJECTS[subjectIndex];
  const round = rounds[roundIndex];
  const isDark = theme === "dark";

  const isCorrect = useMemo(() => {
    if (selected === null || !round) return false;
    return selected === round.lieIndex;
  }, [selected, round]);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDark);
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [isDark, theme]);

  const loadQuestionSet = async (nextSubjectIndex = subjectIndex) => {
    const nextSubject = SUBJECTS[nextSubjectIndex];
    setLoading(true);
    setError("");

    try {
      const fetchedRounds = await fetchQuestionSetWithRetry(nextSubject);
      setRounds(fetchedRounds);
      setRoundIndex(0);
      setSelected(null);
      setShowResult(false);
    } catch (fetchError) {
      setError(
        `${fetchError.message || "Something went wrong loading trivia."} Retried ${TRIVIA_FETCH_RETRY_COUNT} times, then switched to fallback questions.`
      );
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

  const fullRefresh = () => {
    window.location.reload();
  };

  const pageBg = isDark
    ? "bg-[radial-gradient(circle_at_top,_#0f172a,_#111827_45%,_#020617_100%)]"
    : "bg-[radial-gradient(circle_at_top,_#eef2ff,_#ffffff_45%,_#ecfeff_100%)]";

  const cardBg = isDark
    ? "bg-slate-900/80 border-slate-700/70"
    : "bg-white/80 border-white/70";

  const textPrimary = isDark ? "text-slate-100" : "text-gray-900";
  const textSecondary = isDark ? "text-slate-300" : "text-gray-600";

  if (loading && !round) {
    return (
      <div className={`relative min-h-screen overflow-hidden ${pageBg} flex items-center justify-center p-4`}>
        <DecorativeOrbs theme={theme} />
        <div className={`relative w-full max-w-2xl rounded-[2rem] backdrop-blur-xl shadow-2xl border p-6 md:p-8 text-center ${cardBg}`}>
          <div className="mx-auto mb-4 h-14 w-14 rounded-2xl bg-gradient-to-br from-indigo-500 to-fuchsia-500 shadow-lg shadow-indigo-200 animate-pulse" />
          <p className={`text-lg font-semibold ${textPrimary}`}>Loading a new Two Truths and a Lie set...</p>
          <p className={`${textSecondary} mt-2`}>Fetching fresh statements for you now.</p>
          <div className="mt-6 flex justify-center">
            <button
              type="button"
              onClick={fullRefresh}
              className={`rounded-2xl border px-5 py-3 font-semibold transition-colors shadow-sm ${
                isDark
                  ? "border-slate-700 bg-slate-900 text-slate-100 hover:bg-slate-800"
                  : "border-gray-300 bg-white text-gray-700 hover:bg-gray-50 hover:border-gray-400"
              }`}
            >
              Full Refresh
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!round) {
    return (
      <div className={`relative min-h-screen overflow-hidden ${pageBg} flex items-center justify-center p-4`}>
        <DecorativeOrbs theme={theme} />
        <div className={`relative w-full max-w-2xl rounded-[2rem] backdrop-blur-xl shadow-2xl border p-6 md:p-8 text-center ${cardBg}`}>
          <div className="mx-auto mb-4 h-14 w-14 rounded-2xl bg-gradient-to-br from-rose-500 to-orange-500 shadow-lg shadow-rose-200" />
          <p className={`text-lg font-semibold ${textPrimary}`}>No statements available right now.</p>
          <p className={`${textSecondary} mt-2`}>
            Try reconnecting and loading a fresh question set.
          </p>
          <button
            type="button"
            onClick={() => loadQuestionSet(subjectIndex)}
            className="mt-4 rounded-2xl bg-gradient-to-r from-indigo-600 to-fuchsia-600 px-5 py-3 font-semibold text-white shadow-lg shadow-indigo-200 hover:scale-[1.02] hover:shadow-xl transition-all"
          >
            Try Again
          </button>
          <button
            type="button"
            onClick={fullRefresh}
            className={`mt-3 rounded-2xl border px-5 py-3 font-semibold transition-colors shadow-sm ${
              isDark
                ? "border-slate-700 bg-slate-900 text-slate-100 hover:bg-slate-800"
                : "border-gray-300 bg-white text-gray-700 hover:bg-gray-50 hover:border-gray-400"
            }`}
          >
            Full Refresh
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`relative min-h-screen overflow-hidden ${pageBg} flex items-center justify-center p-4`}>
      <DecorativeOrbs theme={theme} />

      <div className={`relative w-full max-w-3xl rounded-[2rem] backdrop-blur-xl shadow-2xl border p-6 md:p-8 ${cardBg}`}>
        <div className="absolute inset-x-0 top-0 h-2 rounded-t-[2rem] bg-gradient-to-r from-indigo-500 via-fuchsia-500 to-emerald-500" />

        <div className="flex items-start justify-between gap-4 mb-6 md:mb-8">
          <div className="text-center flex-1">
            <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50 px-4 py-2 text-sm font-semibold text-indigo-700 shadow-sm">
              <span className="h-2 w-2 rounded-full bg-indigo-500 animate-pulse" />
              Two Truths and a Lie
            </div>

            <h1 className={`text-4xl md:text-5xl font-black mt-4 tracking-tight ${textPrimary}`}>
              One’s a fib — can you spot it?
            </h1>

            <p className={`mt-3 text-base md:text-lg max-w-2xl mx-auto ${textSecondary}`}>
              Read the statements, trust your instincts, and spot the lie before it slips away.
            </p>

            <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
              <div
                className={`rounded-full bg-gradient-to-r ${subject.accent} px-4 py-2 text-white font-semibold shadow-lg ${subject.glow}`}
              >
                Topic: {subject.label}
              </div>
              <div
                className={`rounded-full border px-4 py-2 text-sm font-medium shadow-sm ${
                  isDark
                    ? "border-slate-700 bg-slate-800 text-slate-300"
                    : "border-gray-200 bg-white text-gray-600"
                }`}
              >
                {rounds.length} rounds of deception
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={() => setTheme(isDark ? "light" : "dark")}
            className={`shrink-0 rounded-2xl border px-4 py-3 font-semibold shadow-sm transition-colors ${
              isDark
                ? "border-slate-700 bg-slate-800 text-slate-100 hover:bg-slate-700"
                : "border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
            }`}
            aria-label={`Switch to ${isDark ? "light" : "dark"} mode`}
          >
            {isDark ? "☀️ Light" : "🌙 Dark"}
          </button>
        </div>

        <div className="grid gap-3 md:grid-cols-3 mb-6">
          <StatPill label="Round" value={`${roundIndex + 1}/${rounds.length}`} tone="indigo" theme={theme} />
          <StatPill label="Score" value={score} tone="emerald" theme={theme} />
          <StatPill label="Mood" value={showResult ? "Revealed" : "Guessing"} tone="amber" theme={theme} />
        </div>

        {error && (
          <div
            className={`mb-5 rounded-3xl border p-4 shadow-sm ${
              isDark ? "border-amber-900/60 bg-amber-950/40" : "border-amber-200 bg-amber-50/90"
            }`}
          >
            <p className={`font-semibold ${isDark ? "text-amber-200" : "text-amber-900"}`}>
              Using fallback statements
            </p>
            <p className={`text-sm mt-1 ${isDark ? "text-amber-300" : "text-amber-800"}`}>{error}</p>
            <p className={`text-sm mt-2 ${isDark ? "text-amber-300/90" : "text-amber-700"}`}>
              You can keep playing with the fallback set, or use Full Refresh to reconnect and try again.
            </p>
          </div>
        )}

        <div
          className={`rounded-[1.75rem] border p-5 md:p-6 mb-6 shadow-sm ${
            isDark
              ? "bg-gradient-to-br from-slate-800 to-slate-900 border-slate-700"
              : "bg-gradient-to-br from-gray-50 to-white border-gray-200"
          }`}
        >
          <p className="text-sm font-bold uppercase tracking-[0.2em] text-emerald-700 mb-2">
            Category: {round.category}
          </p>
          <h2 className={`text-2xl md:text-3xl font-black leading-tight ${textPrimary}`}>
            {round.prompt}
          </h2>
        </div>

        <div className="space-y-3">
          {round.statements.map((statement, index) => {
            const isSelected = selected === index;
            const revealCorrect = showResult && index === round.lieIndex;
            const revealWrong = showResult && isSelected && index !== round.lieIndex;

            let buttonClass =
              "group w-full text-left rounded-[1.5rem] border px-4 py-4 md:px-5 md:py-5 transition-all duration-200 shadow-sm ";

            if (!showResult) {
              buttonClass += isDark
                ? "border-slate-700 bg-slate-900 hover:border-indigo-500 hover:bg-slate-800 hover:-translate-y-0.5 hover:shadow-md"
                : "border-gray-200 bg-white hover:border-indigo-300 hover:bg-indigo-50/70 hover:-translate-y-0.5 hover:shadow-md";
            } else if (revealCorrect) {
              buttonClass += isDark
                ? "border-emerald-500 bg-emerald-950/40 shadow-emerald-900/20 ring-2 ring-emerald-700"
                : "border-emerald-400 bg-emerald-50 shadow-emerald-100 ring-2 ring-emerald-200";
            } else if (revealWrong) {
              buttonClass += isDark
                ? "border-rose-500 bg-rose-950/40 shadow-rose-900/20 ring-2 ring-rose-700"
                : "border-rose-400 bg-rose-50 shadow-rose-100 ring-2 ring-rose-200";
            } else {
              buttonClass += isDark ? "border-slate-800 bg-slate-950 opacity-70" : "border-gray-200 bg-gray-100 opacity-70";
            }

            return (
              <button
                key={statement}
                type="button"
                onClick={() => handleGuess(index)}
                className={buttonClass}
              >
                <div className="flex items-start gap-3 md:gap-4">
                  <div
                    className={`mt-0.5 h-7 w-7 rounded-full border flex items-center justify-center text-xs font-black transition-colors ${
                      showResult
                        ? "border-current"
                        : isDark
                          ? "border-slate-700 bg-slate-800 text-slate-100 group-hover:bg-slate-700"
                          : "border-indigo-200 bg-indigo-50 text-indigo-700 group-hover:bg-indigo-100"
                    }`}
                  >
                    {index + 1}
                  </div>
                  <div className="flex-1">
                    <p className={`font-semibold text-base md:text-lg leading-snug ${textPrimary}`}>
                      {statement}
                    </p>
                    {showResult && revealCorrect && (
                      <p className={`text-sm mt-2 font-medium ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>
                        Correct! This is the lie.
                      </p>
                    )}
                    {showResult && revealWrong && (
                      <p className={`text-sm mt-2 font-medium ${isDark ? "text-rose-300" : "text-rose-700"}`}>
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
          <div
            className={`mt-6 rounded-[1.75rem] border p-5 shadow-sm ${
              isDark
                ? "bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 border-slate-700"
                : "bg-gradient-to-r from-indigo-50 via-white to-fuchsia-50 border-indigo-200"
            }`}
          >
            <p className={`font-black text-lg ${isDark ? "text-indigo-200" : "text-indigo-900"}`}>
              {isCorrect ? "Nice job!" : "Good try!"}
            </p>
            <p className={`mt-1 ${isDark ? "text-slate-300" : "text-indigo-800"}`}>{round.explanation}</p>
          </div>
        )}

        <div className="mt-6 flex flex-col sm:flex-row gap-3">
          <button
            type="button"
            onClick={nextRound}
            className="flex-1 rounded-2xl bg-gradient-to-r from-indigo-600 to-fuchsia-600 px-5 py-3 font-semibold text-white shadow-lg shadow-indigo-200 hover:scale-[1.01] hover:shadow-xl transition-all"
          >
            Next Round
          </button>
          <button
            type="button"
            onClick={restart}
            className={`flex-1 rounded-2xl border px-5 py-3 font-semibold transition-colors shadow-sm ${
              isDark
                ? "border-slate-700 bg-slate-900 text-slate-100 hover:bg-slate-800"
                : "border-gray-300 bg-white text-gray-700 hover:bg-gray-50 hover:border-gray-400"
            }`}
          >
            New Question Set
          </button>
          <button
            type="button"
            onClick={fullRefresh}
            className={`flex-1 rounded-2xl border px-5 py-3 font-semibold transition-colors shadow-sm ${
              isDark
                ? "border-slate-700 bg-slate-900 text-slate-100 hover:bg-slate-800"
                : "border-gray-300 bg-white text-gray-700 hover:bg-gray-50 hover:border-gray-400"
            }`}
          >
            Full Refresh
          </button>
        </div>
      </div>
    </div>
  );
}
