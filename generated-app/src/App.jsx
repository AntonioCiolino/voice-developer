import { useState, useEffect } from "react";

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

  .cat {
    position: absolute;
    font-size: 4rem;
    animation: catRun 4s linear infinite, bounce 0.4s ease-in-out infinite;
    bottom: 130px;
    transform: scaleX(-1);
  }

  .dog {
    position: absolute;
    font-size: 4rem;
    animation: dogRun 4s linear infinite 0.7s, bounceDog 0.35s ease-in-out infinite;
    bottom: 125px;
    transform: scaleX(-1);
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

  .grass-blade {
    display: inline-block;
    animation: grassSway 1.5s ease-in-out infinite;
    transform-origin: bottom center;
    font-size: 2rem;
  }
`;

export default function App() {
  const [paws, setPaws] = useState([]);

  useEffect(() => {
    const interval = setInterval(() => {
      const id = Date.now();
      const x = Math.random() * 90 + 5;
      setPaws((prev) => [...prev.slice(-6), { id, x }]);
    }, 600);
    return () => clearInterval(interval);
  }, []);

  return (
    <>
      <style>{styles}</style>
      <div
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

        {/* Cat */}
        <div className="cat">🐱</div>

        {/* Dog */}
        <div className="dog">🐶</div>

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
              <span key={i} style={{ fontSize: "1.4rem" }}>{flower}</span>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
