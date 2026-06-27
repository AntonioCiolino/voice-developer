import { useState } from "react";

const ANIMALS = [
  { emoji: "🐱", name: "Cat" },
  { emoji: "🐶", name: "Dog" },
  { emoji: "🐰", name: "Bunny" },
  { emoji: "🦊", name: "Fox" },
  { emoji: "🐻", name: "Bear" },
  { emoji: "🐼", name: "Panda" },
  { emoji: "🦁", name: "Lion" },
  { emoji: "🐯", name: "Tiger" },
];

// Each animal is spaced evenly and offset in time so they march in a staggered line
const PARADE_DURATION = 14; // seconds for one full crossing

export default function ViewThree() {
  const [clickedAnimal, setClickedAnimal] = useState(null);

  const handleClick = (name) => {
    setClickedAnimal(name);
    setTimeout(() => setClickedAnimal(null), 1000);
  };

  return (
    <div className="flex flex-col h-full gap-4">
      <style>{`
        @keyframes march {
          0%   { left: 110%; }
          100% { left: -120px; }
        }

        @keyframes jauntyBob {
          0%   { transform: translateY(0px) rotate(-8deg) scaleX(-1); }
          25%  { transform: translateY(-18px) rotate(0deg) scaleX(-1); }
          50%  { transform: translateY(0px) rotate(8deg) scaleX(-1); }
          75%  { transform: translateY(-10px) rotate(0deg) scaleX(-1); }
          100% { transform: translateY(0px) rotate(-8deg) scaleX(-1); }
        }

        @keyframes jauntyBobClicked {
          0%   { transform: translateY(0px) rotate(-8deg) scaleX(-1) scale(1.4); }
          25%  { transform: translateY(-28px) rotate(0deg) scaleX(-1) scale(1.4); }
          50%  { transform: translateY(0px) rotate(8deg) scaleX(-1) scale(1.4); }
          75%  { transform: translateY(-14px) rotate(0deg) scaleX(-1) scale(1.4); }
          100% { transform: translateY(0px) rotate(-8deg) scaleX(-1) scale(1.4); }
        }

        .parade-animal {
          position: absolute;
          font-size: 3.5rem;
          cursor: pointer;
          user-select: none;
          bottom: 60px;
          animation:
            march var(--march-dur) linear infinite var(--march-delay),
            jauntyBob 0.55s ease-in-out infinite;
          will-change: transform, left;
        }

        .parade-animal.clicked {
          animation:
            march var(--march-dur) linear infinite var(--march-delay),
            jauntyBobClicked 0.55s ease-in-out infinite;
          filter: drop-shadow(0 0 10px gold);
        }

        @keyframes groundScroll {
          0%   { background-position: 0% 0%; }
          100% { background-position: -200px 0%; }
        }

        .parade-ground {
          position: absolute;
          bottom: 0;
          left: 0;
          right: 0;
          height: 60px;
          background: repeating-linear-gradient(
            90deg,
            #5a9e3a 0px,
            #5a9e3a 30px,
            #4a8e2a 30px,
            #4a8e2a 60px
          );
          background-size: 200px 100%;
          animation: groundScroll 2s linear infinite;
        }

        .parade-sky {
          position: absolute;
          top: 0; left: 0; right: 0; bottom: 0;
          background: linear-gradient(180deg, #87CEEB 0%, #b8e4f7 70%, #d4f1c0 100%);
        }

        @keyframes cloudFloat {
          0%   { left: 110%; }
          100% { left: -200px; }
        }

        .parade-cloud {
          position: absolute;
          font-size: 3rem;
          pointer-events: none;
          user-select: none;
          animation: cloudFloat var(--cloud-dur) linear infinite var(--cloud-delay);
        }

        .cheer-bubble {
          position: absolute;
          bottom: 130px;
          background: white;
          border: 2px solid #f59e0b;
          border-radius: 16px;
          padding: 4px 12px;
          font-size: 0.9rem;
          font-weight: bold;
          color: #92400e;
          white-space: nowrap;
          pointer-events: none;
          animation: march var(--march-dur) linear infinite var(--march-delay);
          z-index: 20;
        }
      `}</style>

      <div className="text-center flex-shrink-0">
        <h2 className="text-2xl font-bold text-gray-700 mb-1">Animal Parade 🎉</h2>
        <p className="text-gray-500 text-sm">Click an animal as it marches by!</p>
      </div>

      {/* Parade scene */}
      <div className="relative flex-1 rounded-2xl overflow-hidden shadow-xl">
        <div className="parade-sky" />

        {/* Clouds */}
        {[
          { dur: "20s", delay: "0s",   top: "10%" },
          { dur: "28s", delay: "-10s", top: "22%" },
          { dur: "24s", delay: "-5s",  top: "8%"  },
        ].map((cloud, i) => (
          <div
            key={i}
            className="parade-cloud"
            style={{
              "--cloud-dur": cloud.dur,
              "--cloud-delay": cloud.delay,
              top: cloud.top,
            }}
          >
            ☁️
          </div>
        ))}

        {/* Marching animals */}
        {ANIMALS.map((animal, i) => {
          const delay = `-${(i / ANIMALS.length) * PARADE_DURATION}s`;
          const dur = `${PARADE_DURATION}s`;
          const isClicked = clickedAnimal === animal.name;

          return (
            <div key={animal.name}>
              <div
                className={`parade-animal${isClicked ? " clicked" : ""}`}
                style={{
                  "--march-dur": dur,
                  "--march-delay": delay,
                  animationDelay: delay,
                  zIndex: 10,
                }}
                onClick={() => handleClick(animal.name)}
                title={`Click me! (${animal.name})`}
              >
                {animal.emoji}
              </div>
              {isClicked && (
                <div
                  className="cheer-bubble"
                  style={{
                    "--march-dur": dur,
                    "--march-delay": delay,
                  }}
                >
                  {animal.name}! 🎊
                </div>
              )}
            </div>
          );
        })}

        {/* Ground */}
        <div className="parade-ground" />
      </div>
    </div>
  );
}
