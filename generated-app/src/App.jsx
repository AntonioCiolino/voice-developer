import React from "react";

export default function App() {
  return (
    <div className="w-screen h-screen overflow-hidden bg-black">
      <div
        id="render-surface"
        className="w-full h-full"
        aria-label="3D rendering surface"
      />
    </div>
  );
}
