import { useState } from "react";

export default function App() {
  const [ballColor, setBallColor] = useState("orange");

  const getRandomColor = () => {
    const colors = [
      "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7",
      "#DDA0DD", "#98D8C8", "#F7DC6F", "#BB8FCE", "#85C1E9",
      "#F0B27A", "#82E0AA", "#F1948A", "#AED6F1", "#A9DFBF",
      "#FAD7A0", "#D2B4DE", "#A3E4D7", "#FDFEFE", "#2ECC71",
    ];
    let newColor;
    do {
      newColor = colors[Math.floor(Math.random() * colors.length)];
    } while (newColor === ballColor);
    return newColor;
  };

  const handleClick = () => {
    setBallColor(getRandomColor());
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "#1a1a2e",
        fontFamily: "Arial, sans-serif",
      }}
    >
      <h1
        style={{
          color: "#ffffff",
          fontSize: "2rem",
          marginBottom: "10px",
          letterSpacing: "2px",
          textTransform: "uppercase",
        }}
      >
        Color Ball
      </h1>
      <p
        style={{
          color: "#aaaaaa",
          marginBottom: "40px",
          fontSize: "1rem",
        }}
      >
        Click the ball to change its color
      </p>
      <div
        onClick={handleClick}
        style={{
          width: "200px",
          height: "200px",
          borderRadius: "50%",
          backgroundColor: ballColor,
          cursor: "pointer",
          boxShadow: `0 0 40px ${ballColor}, 0 10px 30px rgba(0,0,0,0.5)`,
          transition: "background-color 0.4s ease, box-shadow 0.4s ease, transform 0.1s ease",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
        onMouseDown={(e) => {
          e.currentTarget.style.transform = "scale(0.93)";
        }}
        onMouseUp={(e) => {
          e.currentTarget.style.transform = "scale(1)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = "scale(1)";
        }}
      />
      <p
        style={{
          color: "#ffffff",
          marginTop: "30px",
          fontSize: "1.1rem",
          letterSpacing: "1px",
        }}
      >
        Current Color:{" "}
        <span style={{ color: ballColor, fontWeight: "bold" }}>
          {ballColor.toUpperCase()}
        </span>
      </p>
    </div>
  );
}