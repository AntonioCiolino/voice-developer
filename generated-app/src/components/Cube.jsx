export default function Cube() {
  return (
    <div
      style={{
        position: "absolute",
        top: "80px",
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 15,
        perspective: "400px",
        width: "80px",
        height: "80px",
        pointerEvents: "none",
      }}
    >
      <div className="cube">
        <div className="cube-face cube-front">🐾</div>
        <div className="cube-face cube-back">🐾</div>
        <div className="cube-face cube-left">🐾</div>
        <div className="cube-face cube-right">🐾</div>
        <div className="cube-face cube-top">🐾</div>
        <div className="cube-face cube-bottom">🐾</div>
      </div>
    </div>
  );
}
