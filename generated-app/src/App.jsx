import Ball from "./components/Ball.jsx";
import { styles } from "./styles.js";

export default function App() {
  return (
    <div
      style={{
        minHeight: "100vh",
        backgroundColor: "#87CEEB",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <style>{styles}</style>
      <Ball />
    </div>
  );
}
