export default function Sky({ onSunClick }) {
  return (
    <>
      <div className="cloud1">☁️</div>
      <div className="cloud2">☁️</div>
      <div
        onClick={onSunClick}
        style={{
          position: "absolute",
          top: "30px",
          right: "60px",
          fontSize: "3.5rem",
          cursor: "pointer",
          zIndex: 10,
        }}
      >
        ☀️
      </div>
    </>
  );
}
