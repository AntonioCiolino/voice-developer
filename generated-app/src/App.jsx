import { useRef, useState } from "react";
import Ball from "./components/Ball.jsx";
import Cat from "./components/Cat.jsx";
import Dog from "./components/Dog.jsx";
import Crow from "./components/Crow.jsx";
import Ground from "./components/Ground.jsx";
import Sky from "./components/Sky.jsx";
import Title from "./components/Title.jsx";
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
      style={{
        minHeight: "100vh",
        // Fallback for iOS Safari where 100vh includes browser chrome
        minHeight: "-webkit-fill-available",
        backgroundColor: skyBg,
        transition: "background-color 0.3s ease",
        position: "relative",
        overflow: "hidden",
        // Prevent iOS double-tap zoom
        touchAction: "manipulation",
      }}
    >
      <style>{styles}</style>

      {/* Mute / Unmute button */}
      <button
        onClick={toggleMute}
        title={muted ? "Unmute music" : "Mute music"}
        style={{
          position: "absolute",
          top: "20px",
          right: "16px",
          zIndex: 100,
          background: "rgba(255,255,255,0.25)",
          border: "2px solid rgba(255,255,255,0.6)",
          borderRadius: "50%",
          width: "44px",
          height: "44px",
          fontSize: "1.4rem",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          // Both prefixed and unprefixed for Safari
          WebkitBackdropFilter: "blur(4px)",
          backdropFilter: "blur(4px)",
          boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
          transition: "background 0.2s",
          // Ensure tappable on iOS
          WebkitTapHighlightColor: "transparent",
          touchAction: "manipulation",
        }}
      >
        {muted ? "🔇" : "🎵"}
      </button>

      {/* Sky elements */}
      <Sky onSunClick={handleSunClick} />

      {/* Title */}
      <Title />

      {/* Crow */}
      <Crow ref={crowRef} visible={crowVisible} onClick={handleCrowClick} />

      {/* Paw prints */}
      {paws.map((paw) => (
        <div
          key={paw.id}
          style={{
            position: "absolute",
            bottom: "132px",
            left: `${paw.x}%`,
            fontSize: "1.2rem",
            animation: "pawPrint 1.8s ease forwards",
            zIndex: 5,
            pointerEvents: "none",
          }}
        >
          🐾
        </div>
      ))}

      {/* Ball */}
      <Ball />

      {/* Cat */}
      <Cat
        ref={catRef}
        catStyle={catStyle}
        catLeaping={catLeaping}
        onClick={handleCatClick}
      />

      {/* Dog */}
      <Dog ref={dogRef} onClick={handleDogClick} barking={barking} />

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

      {/* Ground (renders grass, ferns, flowers) */}
      <div style={{ position: "absolute", bottom: 0, width: "100%" }}>
        <Ground />
      </div>
    </div>
  );
}
