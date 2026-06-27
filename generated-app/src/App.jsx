import Cube from "./components/Cube";

export default function App() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-100">
      <div className="text-center">
        <h1 className="text-4xl font-bold mb-4">3D Cube Renderer</h1>
        <p className="text-gray-600 mb-8">Software-rendered — projection, depth sorting &amp; flat shading</p>
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            marginTop: "40px",
            padding: "40px",
            background: "linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)",
            borderRadius: "24px",
            boxShadow: "0 16px 48px rgba(0,0,0,0.3)",
          }}
        >
          <Cube />
        </div>
      </div>
    </div>
  );
}
