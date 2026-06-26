export default function App() {
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        background: "#0f0f0f",
        color: "#fff",
        gap: "1rem",
        textAlign: "center",
        padding: "2rem",
      }}
    >
      <div style={{ fontSize: "3rem" }}>🎙️</div>
      <h1 style={{ fontSize: "1.75rem", fontWeight: 700, letterSpacing: "-0.02em" }}>
        voice-developer
      </h1>
      <p style={{ color: "#888", fontSize: "1rem", maxWidth: "320px" }}>
        Send a prompt to <code style={{ color: "#aaa" }}>POST /generate</code> and watch this page transform.
      </p>
    </div>
  );
}
