export default function Title() {
  return (
    <div
      style={{
        position: "absolute",
        top: "20px",
        width: "100%",
        textAlign: "center",
        zIndex: 10,
      }}
    >
      <h1
        style={{
          fontSize: "2.5rem",
          color: "#fff",
          textShadow: "2px 2px 6px rgba(0,0,0,0.3)",
          margin: 0,
          letterSpacing: "2px",
        }}
      >
        🐾 The Chase 🐾
      </h1>
      <p
        style={{
          color: "#f0f8ff",
          fontSize: "1rem",
          marginTop: "6px",
          textShadow: "1px 1px 3px rgba(0,0,0,0.2)",
        }}
      >
        A dog chasing a cat...
      </p>
    </div>
  );
}
