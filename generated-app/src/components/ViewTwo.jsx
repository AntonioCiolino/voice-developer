export default function ViewTwo() {
  const size = 120;

  const faceStyle = {
    position: "absolute",
    width: `${size}px`,
    height: `${size}px`,
    border: "2px solid rgba(255,255,255,0.6)",
    borderRadius: "10px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "2.5rem",
    backdropFilter: "blur(4px)",
    WebkitBackdropFilter: "blur(4px)",
    boxShadow: "inset 0 0 20px rgba(255,255,255,0.2), 0 0 10px rgba(0,0,0,0.15)",
  };

  const faces = [
    {
      label: "Front",
      emoji: "🐾",
      color: "rgba(99,179,237,0.7)",
      transform: `translateZ(${size / 2}px)`,
    },
    {
      label: "Back",
      emoji: "🐱",
      color: "rgba(252,129,74,0.7)",
      transform: `rotateY(180deg) translateZ(${size / 2}px)`,
    },
    {
      label: "Left",
      emoji: "🐶",
      color: "rgba(154,230,180,0.7)",
      transform: `rotateY(-90deg) translateZ(${size / 2}px)`,
    },
    {
      label: "Right",
      emoji: "🌟",
      color: "rgba(246,173,85,0.7)",
      transform: `rotateY(90deg) translateZ(${size / 2}px)`,
    },
    {
      label: "Top",
      emoji: "☀️",
      color: "rgba(183,148,246,0.7)",
      transform: `rotateX(90deg) translateZ(${size / 2}px)`,
    },
    {
      label: "Bottom",
      emoji: "🌿",
      color: "rgba(252,129,129,0.7)",
      transform: `rotateX(-90deg) translateZ(${size / 2}px)`,
    },
  ];

  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[500px] gap-10">
      <style>{`
        @keyframes spin {
          0%   { transform: rotateX(0deg)   rotateY(0deg); }
          25%  { transform: rotateX(20deg)  rotateY(90deg); }
          50%  { transform: rotateX(0deg)   rotateY(180deg); }
          75%  { transform: rotateX(-20deg) rotateY(270deg); }
          100% { transform: rotateX(0deg)   rotateY(360deg); }
        }
      `}</style>

      <div className="text-center">
        <h2 className="text-2xl font-bold text-gray-700 mb-1">3D Cube</h2>
        <p className="text-gray-500 text-sm">CSS-powered · hardware accelerated</p>
      </div>

      {/* Perspective wrapper */}
      <div
        style={{
          perspective: "600px",
          perspectiveOrigin: "50% 50%",
          width: `${size}px`,
          height: `${size}px`,
        }}
      >
        {/* Cube — transform-style: preserve-3d + spin animation */}
        <div
          style={{
            width: `${size}px`,
            height: `${size}px`,
            position: "relative",
            transformStyle: "preserve-3d",
            animation: "spin 6s linear infinite",
          }}
        >
          {faces.map((face) => (
            <div
              key={face.label}
              style={{
                ...faceStyle,
                background: face.color,
                transform: face.transform,
              }}
            >
              {face.emoji}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
