import Cube from "./components/Cube";

export default function App() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-100">
      <div className="text-center">
        <h1 className="text-4xl font-bold mb-4">New App</h1>
        <p className="text-gray-600">Ready to build...</p>
        <div style={{ display: "flex", justifyContent: "center", marginTop: "60px" }}>
          <Cube />
        </div>
      </div>
    </div>
  );
}
