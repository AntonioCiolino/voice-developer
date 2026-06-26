import { useState, useEffect, useRef } from "react";

const styles = `
  @keyframes catRun {
    0%   { left: 110%; }
    100% { left: -150px; }
  }

  @keyframes dogRun {
    0%   { left: 110%; }
    100% { left: -150px; }
  }

  @keyframes bounce {
    0%, 100% { transform: translateY(0) scaleX(-1); }
    50%       { transform: translateY(-18px) scaleX(-1); }
  }

  @keyframes bounceDog {
    0%, 100% { transform: translateY(0) scaleX(-1); }
    50%       { transform: translateY(-14px) scaleX(-1); }
  }

  @keyframes grassSway {
    0%, 100% { transform: rotate(-3deg); }
    50%       { transform: rotate(3deg); }
  }

  @keyframes flowerSway {
    0%, 100% { transform: rotate(-4deg); }
    50%       { transform: rotate(4deg); }
  }

  @keyframes cloudDrift {
    0%   { left: 110%; }
    100% { left: -200px; }
  }

  @keyframes pawPrint {
    0%   { opacity: 0; transform: scale(0.5); }
    20%  { opacity: 1; transform: scale(1); }
    80%  { opacity: 1; }
    100% { opacity: 0; }
  }

  @keyframes crowFly {
    0%   { left: -100px; }
    100% { left: 110%; }
  }

  @keyframes flapWings {
    0%, 100% { transform: scaleY(1); }
    50%       { transform: scaleY(0.6); }
  }

  @keyframes explodeParticle {
    0%   { opacity: 1; transform: translate(0, 0) scale(1); }
    100% { opacity: 0; transform: translate(var(--tx), var(--ty)) scale(0.3); }
  }

  @keyframes catJumpEat {
    0%   { bottom: 130px; left: 50%; transform: scaleX(-1); }
    30%  { bottom: 300px; left: 50%; transform: scaleX(-1); }
    60%  { bottom: 300px; left: 50%; transform: scaleX(-1); }
    100% { bottom: 130px; left: 50%; transform: scaleX(-1); }
  }

  @keyframes barkBubble {
    0%   { opacity: 0; transform: scale(0.5); }
    15%  { opacity: 1; transform: scale(1.1); }
    25%  { transform: scale(1); }
    80%  { opacity: 1; }
    100% { opacity: 0; }
  }

  @keyframes skyFlash {
    0%   { background-color: #87CEEB; }
    20%  { background-color: #ff2200; }
    80%  { background-color: #ff2200; }
    100% { background-color: #87CEEB; }
  }

  .cat {
    position: absolute;
    font-size: 4rem;
    animation: catRun 7s linear infinite, bounce 0.4s ease-in-out infinite;
    bottom: 130px;
    transform: scaleX(-1);
    cursor: pointer;
    z-index: 6;
  }

  .cat-eating {
    position: absolute;
    font-size: 4rem;
    bottom: 130px;
    transform: scaleX(-1);
    cursor: pointer;
    z-index: 10;
    animation: catJumpEat 3s ease-in-out forwards;
  }

  .dog {
    position: absolute;
    font-size: 4rem;
    animation: dogRun 7s linear infinite 0.7s, bounceDog 0.35s ease-in-out infinite;
    bottom: 130px;
    transform: scaleX(-1);
    cursor: pointer;
    z-index: 6;
  }

  .cloud1 {
    position: absolute;
    font-size: 3rem;
    top: 60px;
    animation: cloudDrift 18s linear infinite;
    opacity: 0.85;
  }

  .cloud2 {
    position: absolute;
    font-size: 2rem;
    top: 100px;
    animation: cloudDrift 25s linear infinite 6s;
    opacity: 0.7;
  }

  .crow {
    position: absolute;
    font-size: 2.2rem;
    top: 140px;
    animation: crowFly 9s linear infinite 2s, flapWings 0.3s ease-in-out infinite;
    z-index: 5;
    filter: grayscale(100%) brightness(0.2);
    cursor: pointer;
  }

  .grass-blade {
    display: inline-block;
    animation: grassSway 1.5s ease-in-out infinite;
    transform-origin: bottom center;
    font-size: 2rem;
  }

  .flower {
    display: inline-block;
    animation: flowerSway 2s ease-in-out infinite;
    transform-origin: bottom center;
  }

  .explode-particle {
    position: fixed;
    font-size: 1.8rem;
    pointer-events: none;
    animation: explodeParticle 0.8s ease-out forwards;
    z-index: 999;
  }

  .bark-bubble {
    position: absolute;
    bottom: 175px;
    font-size: 1.2rem;
    background: white;
    border: 2px solid #333;
    border-radius: 12px;
    padding: 4px 10px;
    white-space: nowrap;
    animation: barkBubble 2s ease forwards;
    z-index: 20;
    pointer-events: none;
  }

  .bark-bubble::after {
    content: '';
    position: absolute;
    bottom: -10px;
    left: 14px;
    border-width: 10px 8px 0;
    border-style: solid;
    border-color: white transparent transparent;
  }

  .bark-bubble::before {
    content: '';
    position: absolute;
    bottom: -13px;
    left: 12px;
    border-width: 12px 10px 0;
    border-style: solid;
    border-color: #333 transparent transparent;
  }

  .sky-red {
    animation: skyFlash 3s ease forwards !important;
  }
`;

const EXPLODE_EMOJIS = ["💥", "✨", "⭐", "🌟", "💫", "🔥", "🪶", "💨"];

export default function App() {
  const [paws, setPaws] = useState([]);
  const [particles, setParticles] = useState([]);
  const [crowVisible, setCrowVisible] = useState(true);
  const [dogBarking, setDogBarking] = useState(false);
  const [catEating, setCatEating] = useState(false);
  const [skyRed, setSkyRed] = useState(false);
  const dogRef = useRef(null);

  useEffect(() => {
    const interval = setInterval(() => {
      const id = Date.now();
      const x = Math.random() * 90 + 5;
      setPaws((prev) => [...prev.slice(-6), { id, x }]);
    }, 600);
    return () => clearInterval(interval);
  }, []);

  const handleCrowClick = (e) => {
    if (!crowVisible) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;

    const newParticles = EXPLODE_EMOJIS.map((emoji, i) => {
      const angle = (i / EXPLODE_EMOJIS.length) * 2 * Math.PI;
      const dist = 60 + Math.random() * 60;
      return {
        id: Date.now() + i,
        emoji,
        x: cx,
        y: cy,
        tx: `${Math.cos(angle) * dist}px`,
        ty: `${Math.sin(angle) * dist}px`,
      };
    });

    setParticles((prev) => [...prev, ...newParticles]);
    setCrowVisible(false);
    setSkyRed(true);

    setTimeout(() => {
      setParticles((prev) => prev.filter((p) => !newParticles.find((np) => np.id === p.id)));
      setCrowVisible(true);
      setSkyRed(false);
    }, 3000);
  };

  const handleDogClick = () => {
    if (dogBarking) return;
    setDogBarking(true);
    setTimeout(() => setDogBarking(false), 2000);
  };

  const handleCatClick = () => {
    if (catEating || !crowVisible) return;
    setCatEating(true);
    setCrowVisible(false);
    setTimeout(() => {
      setCatEating(false);
      setCrowVisible(true);
    }, 3000);
  };

  return (
    <>
      <style>{styles}</style>
      <div
        className={skyRed ? "sky-red" : ""}
        style={{
          minHeight: "100vh",
          backgroundColor: "#87CEEB",
          overflow: "hidden",
          position: "relative",
          fontFamily: "Arial, sans-serif",
          display: "flex",
          flexDirection: "column",
          justifyContent: "flex-end",
        }}
      >
        {/* Title */}
        <div
          style={{
            position: "absolute",
            top: "20px",
            width: "100%",
            textAlign: "center",
            zIndex: 10,
          }}
        >
          <h1
            style={{
              fontSize: "2.5rem",
              color: "#fff",
              textShadow: "2px 2px 6px rgba(0,0,0,0.3)",
              margin: 0,
              letterSpacing: "2px",
            }}
          >
            🐾 The Chase 🐾
          </h1>
          <p style={{ color: "#f0f8ff", fontSize: "1rem", marginTop: "6px", textShadow: "1px 1px 3px rgba(0,0,0,0.2)" }}>
            A dog chasing a cat...
          </p>
        </div>

        {/* Clouds */}
        <div className="cloud1">☁️</div>
        <div className="cloud2">☁️</div>

        {/* Sun */}
        <div style={{ position: "absolute", top: "30px", right: "60px", fontSize: "3.5rem" }}>
          ☀️
        </div>

        {/* Crow */}
        {crowVisible && (
          <div className="crow" onClick={handleCrowClick} title="Click me!">
            🐦
          </div>
        )}

        {/* Explosion particles */}
        {particles.map((p) => (
          <div
            key={p.id}
            className="explode-particle"
            style={{
              left: p.x,
              top: p.y,
              "--tx": p.tx,
              "--ty": p.ty,
            }}
          >
            {p.emoji}
          </div>
        ))}

        {/* Paw prints */}
        {paws.map((paw) => (
          <div
            key={paw.id}
            style={{
              position: "absolute",
              bottom: "118px",
              left: `${paw.x}%`,
              fontSize: "1.2rem",
              animation: "pawPrint 2s ease forwards",
              zIndex: 2,
            }}
          >
            🐾
          </div>
        ))}

        {/* Cat - normal running or eating */}
        {catEating ? (
          <div className="cat-eating" onClick={handleCatClick}>
            😸
          </div>
        ) : (
          <div className="cat" onClick={handleCatClick} title="Click me!">
            🐱
          </div>
        )}

        {/* Dog + bark bubble */}
        <div style={{ position: "relative" }} ref={dogRef}>
          {dogBarking && (
            <div
              className="bark-bubble"
              style={{
                left: "48%",
              }}
            >
              Woof! 🗣️
            </div>
          )}
          <div className="dog" onClick={handleDogClick} title="Click me!">
            🐶
          </div>
        </div>

        {/* Ground */}
        <div
          style={{
            width: "100%",
            height: "130px",
            backgroundColor: "#5DBB63",
            position: "relative",
            borderTop: "6px solid #4a9e50",
            zIndex: 3,
          }}
        >
          {/* Grass blades */}
          <div style={{ display: "flex", justifyContent: "space-around", marginTop: "-10px" }}>
            {Array.from({ length: 30 }).map((_, i) => (
              <span
                key={i}
                className="grass-blade"
                style={{
                  animationDelay: `${(i * 0.15) % 1.5}s`,
                  fontSize: `${1.5 + (i % 3) * 0.4}rem`,
                }}
              >
                🌿
              </span>
            ))}
          </div>

          {/* Flowers */}
          <div style={{ display: "flex", justifyContent: "space-around", marginTop: "10px", paddingLeft: "20px" }}>
            {["🌸", "🌼", "🌺", "🌻", "🌸", "🌼", "🌺", "🌻", "🌸", "🌼"].map((flower, i) => (
              <span
                key={i}
                className="flower"
                style={{
                  fontSize: "1.4rem",
                  animationDelay: `${(i * 0.2) % 2}s`,
                }}
              >
                {flower}
              </span>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
