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

export default function ViewThree() {
  const [selectedAnimal, setSelectedAnimal] = useState(null);

  return (
    <div className="flex flex-col h-full gap-4">
      <div className="text-center">
        <h2 className="text-2xl font-bold text-gray-700 mb-1">Animal Parade 🎉</h2>
        <p className="text-gray-500 text-sm">Click any animal!</p>
      </div>

      {/* Scene */}
      <div
        className="relative flex-1 rounded-2xl overflow-y-auto shadow-xl p-8"
        style={{
          background: "linear-gradient(180deg, #87CEEB 0%, #b8e4f7 60%, #d4f1c0 100%)",
        }}
      >
        {/* Animals Grid */}
        <div className="grid grid-cols-4 gap-6 justify-items-center">
          {ANIMALS.map((animal) => (
            <button
              key={animal.name}
              onClick={() => setSelectedAnimal(animal.name)}
              className={`text-6xl transition-transform duration-200 ${
                selectedAnimal === animal.name ? "scale-125" : "hover:scale-110"
              }`}
            >
              {animal.emoji}
            </button>
          ))}
        </div>

        {/* Selected Animal Message */}
        {selectedAnimal && (
          <div className="text-center mt-8 text-2xl font-bold text-gray-700 animate-bounce">
            You clicked the {selectedAnimal}! 🎊
          </div>
        )}
      </div>
    </div>
  );
}
