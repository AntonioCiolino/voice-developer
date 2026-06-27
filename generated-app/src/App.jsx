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