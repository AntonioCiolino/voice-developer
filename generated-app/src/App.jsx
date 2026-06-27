import { useRef, useState } from "react";
import Ball from "./components/Ball.jsx";
import Cat from "./components/Cat.jsx";
import Dog from "./components/Dog.jsx";
import Crow from "./components/Crow.jsx";
import Ground from "./components/Ground.jsx";
import Sky from "./components/Sky.jsx";
import Title from "./components/Title.jsx";
import Cube from "./components/Cube.jsx";
import { styles } from "./styles.js";
import { useCatLeap } from "./hooks/useCatLeap.js";
import { useCrowExplosion } from "./hooks/useCrowExplosion.js";
import { usePawPrints } from "./hooks/usePawPrints.js";
import { useBackgroundMusic } from "./hooks/useBackgroundMusic.js";

export default function App() {
  const catRef = useRef(null);
  const crowRef = useRef(null);
  const dogRef = useRef(null);

  const [crowVisible, setCrowVisible] = useState(true);
  const [particles, setParticles] = useState([]);
  const [skyRed, setSkyRed] = useState(false);
  const [skyGreen, setSkyGreen] = useState(false);
  const [barking, setBarking] = useState(false);

  const { muted, toggleMute } = useBackgroundMusic();

  const { catLeaping, catStyle, handleCatClick } = useCatLeap({
    catRef,
    crowRef,
    setCrowVisible,
    setParticles,
  });

  const { handleCrowClick } = useCrowExplosion({
    setCrowVisible,
    setParticles,
    setSkyRed,
  });

  const paws = usePawPrints();

  const handleDogClick = () => {
    if (barking) return;
    setBarking(true);
    setTimeout(() => setBarking(false), 2000);
  };

  const handleSunClick = () => {
    if (skyGreen || skyRed) return;
    setSkyGreen(true);
    setTimeout(() => setSkyGreen(false), 3000);
  };

  let skyBg = "#87CEEB";
  if (skyRed) skyBg = "#ff2200";
  if (skyGreen) skyBg = "#22cc44";

  return (
    <div
      className="app-root"
      style={{
        backgroundColor: skyBg,
        transition: "background-color 0.3s ease",
        position: "relative",
        overflow: "hidden",
        touchAction: "manipulation",
      }}
    >
      {/* Inject styles */}
      <style>{styles}</style>

      {/* Mute button */}
      <button
        onClick={toggleMute}
        title={muted ? "Unmute music" : "Mute music"}
        style={{
          position: "absolute",
          top: "20px",
          right: "20px",
          zIndex: 50,
          background: "rgba(255,255,255,0.25)",
          border: "2px solid rgba(255,255,255,0.6)",
          borderRadius: "50%",
          width: "48px",
          height: "48px",
          fontSize: "1.5rem",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          backdropFilter: "blur(4px)",
          WebkitBackdropFilter: "blur(4px)",
          boxShadow: "0 2px 8px rgba(0,0,0,0.2)",
          userSelect: "none",
          WebkitUserSelect: "none",
        }}
      >
        {muted ? "🔇" : "🎵"}
      </button>

      {/* Sky elements (clouds + sun) */}
      <Sky onSunClick={handleSunClick} />

      {/* Spinning cube */}
      <Cube />

      {/* Title */}
      <Title />

      {/* Crow */}
      <Crow ref={crowRef} visible={crowVisible} onClick={handleCrowClick} />

      {/* Paw prints on the ground */}
      {paws.map((paw) => (
        <div
          key={paw.id}
          style={{
            position: "absolute",
            bottom: "125px",
            left: `${paw.x}%`,
            fontSize: "1.2rem",
            zIndex: 5,
            pointerEvents: "none",
            animation: "pawPrint 1.8s ease-out forwards",
            WebkitAnimation: "pawPrint 1.8s ease-out forwards",
          }}
        >
          🐾
        </div>
      ))}

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

      {/* Animals */}
      <Cat
        ref={catRef}
        catStyle={catStyle}
        catLeaping={catLeaping}
        onClick={handleCatClick}
      />
      <Dog ref={dogRef} onClick={handleDogClick} barking={barking} />

      {/* Bouncing ball */}
      <Ball />

      {/* Ground (grass, flowers, ferns) */}
      <div style={{ position: "absolute", bottom: 0, width: "100%", zIndex: 3 }}>
        <Ground />
      </div>
    </div>
  );
}
