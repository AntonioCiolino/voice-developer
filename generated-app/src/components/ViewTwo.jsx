export default function ViewTwo() {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[500px] gap-8">
      <div className="text-center">
        <h2 className="text-2xl font-bold text-gray-700 mb-1">3D Cube</h2>
        <p className="text-gray-500 text-sm">CSS-powered · hardware accelerated</p>
      </div>

      <div
        style={{
          perspective: "600px",
          width: 140,
          height: 140,
        }}
      >
        <div className="cube-3d">
          <div className="face face-front">🐾</div>
          <div className="face face-back">🐱</div>
          <div className="face face-left">🐶</div>
          <div className="face face-right">🌟</div>
          <div className="face face-top">☀️</div>
          <div className="face face-bottom">🌿</div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 mt-4">
        {[
          { face: "Front", emoji: "🐾", color: "bg-blue-100 text-blue-700" },
          { face: "Back", emoji: "🐱", color: "bg-orange-100 text-orange-700" },
          { face: "Left", emoji: "🐶", color: "bg-green-100 text-green-700" },
          { face: "Right", emoji: "🌟", color: "bg-yellow-100 text-yellow-700" },
          { face: "Top", emoji: "☀️", color: "bg-purple-100 text-purple-700" },
          { face: "Bottom", emoji: "🌿", color: "bg-red-100 text-red-700" },
        ].map(({ face, emoji, color }) => (
          <div
            key={face}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold ${color}`}
          >
            <span>{emoji}</span>
            <span>{face}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
