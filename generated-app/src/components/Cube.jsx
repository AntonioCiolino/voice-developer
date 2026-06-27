export default function Cube() {
  return (
    <div style={{ perspective: "400px", width: 100, height: 100 }}>
      <div className="cube">
        <div className="cube-face cube-front">🐾</div>
        <div className="cube-face cube-back">🐱</div>
        <div className="cube-face cube-left">🐶</div>
        <div className="cube-face cube-right">🌟</div>
        <div className="cube-face cube-top">☀️</div>
        <div className="cube-face cube-bottom">🌿</div>
      </div>
    </div>
  );
}
