export default function Sky({ onSunClick }) {
  return (
    <>
      <div className="cloud1">☁️</div>
      <div className="cloud2">☁️</div>
      <div
        onClick={onSunClick}
        title="Click me!"
        style={{
          position: "absolute",
          top: "30px",
          right: "60px",
          fontSize: "3.5rem",
          cursor: "pointer",
          zIndex: 10,
          userSelect: "none",
          filter: "drop-shadow(0 0 6px rgba(255,220,0,0.7))",
          lineHeight: 1,
        }}
      >
        ☀️
      </div>
    </>
  );
}
