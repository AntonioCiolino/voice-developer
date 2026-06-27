import { useEffect, useRef, useState } from "react";

const ANIMALS = [
  { emoji: "🐱", name: "Cat", speed: 4, bottom: 130, bounce: true },
  { emoji: "🐶", name: "Dog", speed: 5, bottom: 128, bounce: true },
  { emoji: "🐰", name: "Bunny", speed: 6, bottom: 130, bounce: true },
  { emoji: "🦊", name: "Fox", speed: 4.5, bottom: 130, bounce: true },
  { emoji: "🐻", name: "Bear", speed: 3.5, bottom: 128, bounce: false },
  { emoji: "🐼", name: "Panda", speed: 3, bottom: 128, bounce: false },
  { emoji: "🦁", name: "Lion", speed: 4.2, bottom: 130, bounce: true },
  { emoji: "🐯", name: "Tiger", speed: 4.8, bottom: 130, bounce: true },
];

const GROUND_ITEMS = Array.from({ length: 28 }, (_, i) => ({
  id: i,
  isFlower: i % 6 === 0,
  swayDelay: `${(i * 0.13) % 1.5}s`,
}));

export default function ViewThree() {
  const [clickedAnimal, setClickedAnimal] = useState(null);

  const handleAnimalClick = (name) => {
    setClickedAnimal(name);
    setTimeout(() => setClickedAnimal(null), 1000);
  };

  return (
    <div className="flex flex-col h-full min-h-[500px] gap-4">
      <div className="text-center">
        <h2 className="text-2xl font-bold text-gray-700 mb-1">Animal Parade 🎉</h2>
        <p className="text-gray-500 text-sm">Click the animals!</p>
      </div>

      {/* Scene */}
      <div
        className="relative flex-1 rounded-2xl overflow-hidden shadow-xl"
        style={{
          background: "linear-gradient(180deg, #87CEEB 0%, #b8e4f7 60%, #d4f1c0 100%)",
          minHeight: 320,
        }}
      >
        {/* Sun */}
        <div
          style={{
            position: "absolute",
            top: 24,
            right: 48,
            fontSize: "3rem",
            filter: "drop-shadow(0 0 8px rgba(255,220,0,0.7))",
            zIndex: 2,
            pointerEvents: "none",
          }}
        >
          ☀️
        </div>

        {/* Clouds */}
        <div className="cloud-scroll cloud-a" style={{ top: 30, fontSize: "3rem" }}>☁️</div>
        <div className="cloud-scroll cloud-b" style={{ top: 70, fontSize: "2rem" }}>☁️</div>

        {/* Animals */}
        {ANIMALS.map((animal, i) => (
          <AnimalRunner
            key={animal.name}
            animal={animal}
            delay={i * 0.7}
            onClick={() =>