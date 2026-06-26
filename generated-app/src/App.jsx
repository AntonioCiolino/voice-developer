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

export default function App() {
  const catRef = useRef(null);
  const crowRef = useRef(null);
  const dogRef = useRef(null);

  const [crowVisible, setCrowVisible] = useState(true);
  const [particles, setParticles] = useState([]);
  const [skyRed, setSkyRed] = useState(false);
  const [barking, setBarking] = useState(false);

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

  return (
    <div
      className={skyRed ? "sky-red" : ""}
      style={{
        minHeight: "100vh",
        backgroundColor: skyRed ? undefined : "#87CEEB",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <style>{styles}</style>

      {/* Sky elements */}
      <Sky />

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
