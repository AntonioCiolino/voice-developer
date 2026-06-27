import { useState, useEffect } from "react";

const CONFETTI_COLORS = ["#f59e0b", "#ef4444", "#3b82f6", "#10b981", "#8b5cf6", "#ec4899"];
const CONFETTI_COUNT = 40;

function randomBetween(a, b) {
  return a + Math.random() * (b - a);
}

function generateConfetti() {
  return Array.from({ length: CONFETTI_COUNT }, (_, i) => ({
    id: i,
    left: `${randomBetween(0, 100)}%`,
    color: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
    size: randomBetween(8, 16),
    delay: `${randomBetween(0, 3)}s`,
    duration: `${randomBetween(2.5, 5)}s`,
    rotation: randomBetween(0, 360),
  }));
}

const FACTS = [
  "🐱 Cats sleep 12–16 hours a day.",
  "🐶 Dogs have a sense of smell 40× stronger than humans.",
  "🦋 Butterflies taste with their feet.",
  "🐘 Elephants are the only animals that can't jump.",
  "🦈 Sharks are older than trees.",
  "🐙 Octopuses have three hearts.",
  "🦜 Parrots can live for over 80 years.",
  "🐝 Honey never spoils — 3000-year-old honey is still edible.",
];

export default function ViewSpecial() {
  const [confetti] = useState(generateConfetti);
  const [factIndex, setFactIndex] = useState(0);
  const [animating, setAnimating] = useState(false);
  const [stars, setStars] = useState([]);

  useEffect(() => {
    setStars(
      Array.from({ length: 20 }, (_, i) => ({
        id: i,
        top: `${randomBetween(5, 90)}%`,
        left: `${randomBetween(2, 98)}%`,
        delay: `${randomBetween(0, 2)}s`,
        duration: `${randomBetween(1.5, 3)}s`,
      }))
    );
  }, []);

  const nextFact = () => {
    if (animating) return;
    setAnimating(true);
    setTimeout(() => {
      setFactIndex((i) => (i + 1) % FACTS.length);
      setAnimating(false);
    }, 300);
  };

  return (
    <div className="max-w-3xl mx-auto flex flex-col gap-6">
      <style>{`
        @keyframes confettiFall {
          0%   { transform: translateY(-40px) rotate(0deg); opacity: 1; }
          100% { transform: translateY(100vh) rotate(720deg); opacity: 0; }
        }
        @keyframes twinkle {
          0%, 100% { opacity: 0.2; transform: scale(0.8); }
          50%       { opacity: 1;   transform: scale(1.3); }
        }
        @keyframes fadeSlideIn {
          0%   { opacity: 0; transform: translateY(10px); }
          100% { opacity: 1; transform: translateY(0); }
        }
        @keyframes fadeSlideOut {
          0%   { opacity: 1; transform: translateY(0); }
          100% { opacity: 0; transform: translateY(-10px); }
        }
        @keyframes pulse-glow {
          0%, 100% { box-shadow: 0 0 10px 2px rgba(139,92,246,0.4); }
          50%       { box-shadow: 0 0 24px 8px rgba(139,92,246,0.8); }
        }
        .confetti-piece {
          position: fixed;
          top: -20px;
          pointer-events: none;
          z-index: 0;
          border-radius: 2px;
          animation: confettiFall var(--dur) linear var(--delay) infinite;
        }
        .star-twinkle {
          position: absolute;
          font-size: 1.1rem;
          pointer-events: none;
          animation: twinkle var(--dur) ease-in-out var(--delay) infinite;
        }
        .fact-text-in {
          animation: fadeSlideIn 0.3s ease forwards;
        }
        .fact-text-out {
          animation: fadeSlideOut 0.3s ease forwards;
        }
        .glow-card {
          animation: pulse-glow 2.5s ease-in-out infinite;
        }
      `}</style>

      {/* Confetti */}
      {confetti.map((c) => (
        <div
          key={c.id}
          className="confetti-piece"
          style={{
            left: c.left,
            width: c.size,
            height: c.size,
            backgroundColor: c.color,
            "--dur": c.duration,
            "--delay": c.delay,
            transform: `rotate(${c.rotation}deg)`,
          }}
        />
      ))}

      {/* Hero banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-violet-600 via-purple-500 to-pink-500 text-white px-10 py-12 shadow-xl glow-card">
        {stars.map((s) => (
          <span
            key={s.id}
            className="star-twinkle"
            style={{
              top: s.top,
              left: s.left,
              "--dur": s.duration,
              "--delay": s.delay,
            }}
          >
            ✨
          </span>
        ))}
        <div className="relative z-10 text-center">
          <div className="text-6xl mb-4">🎉</div>
          <h1 className="text-4xl font-extrabold tracking-tight mb-2 drop-shadow-lg">
            Welcome to Special!
          </h1>
          <p className="text-purple-100 text-lg max-w-md mx-auto">
            You found the secret page. Enjoy the confetti and fun facts below!
          </p>
        </div>
      </div>

      {/* Fun fact card */}
      <div className="bg-white rounded-2xl shadow-lg p-8 flex flex-col items-center gap-5">
        <h2 className="text-xl font-bold text-gray-700">🧠 Fun Fact of the Moment</h2>
        <div className="min-h-[3rem] flex items-center justify-center">
          <p
            className={`text-gray-600 text-center text-lg leading-relaxed ${
              animating ? "fact-text-out" : "fact-text-in"
            }`}
          >
            {FACTS[factIndex]}
          </p>
        </div>
        <button
          onClick={nextFact}
          className="bg-violet-500 hover:bg-violet-400 active:bg-violet-600 active:scale-95 text-white font-bold px-6 py-2 rounded-full shadow transition-all duration-150 select-none"
        >
          Next Fact →
        </button>
      </div>

      {/* Emoji grid */}
      <div className="bg-white rounded-2xl shadow-lg p-8">
        <h2 className="text-xl font-bold text-gray-700 mb-4 text-center">🎨 Emoji Gallery</h2>
        <div className="grid grid-cols-6 gap-4 text-center">
          {[
            "🦄","🌈","🎸","🚀","🍕","🎩",
            "🦋","🌺","🎯","🏆","🎪","🌙",
            "🦊","🍦","🎲","💎","🌊","🎠",
          ].map((emoji, i) => (
            <div
              key={i}
              className="text-3xl hover:scale-125 transition-transform duration-150 cursor-default select-none"
              title={emoji}
            >
              {emoji}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
