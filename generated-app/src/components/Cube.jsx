export default function Cube() {
  return (
    <div
      style={{
        perspective: "600px",
        width: "100px",
        height: "100px",
      }}
    >
      <div className="cube">
        <div className="cube-face cube-front">🐾</div>
        <div className="cube-face cube-back">⭐</div>
        <div className="cube-face cube-left">🔥</div>
        <div className="cube-face cube-right">💫</div>
        <div className="cube-face cube-top">✨</div>
        <div className="cube-face cube-bottom">🌟</div>
      </div>
    </div>
  );
}
