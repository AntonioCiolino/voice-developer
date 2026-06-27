import React, { useEffect, useRef } from "react";

export default function App() {
  const cubeRef = useRef(null);

  useEffect(() => {
    const cube = cubeRef.current;
    if (!cube) return;

    let animationFrameId;
    let startTime = performance.now();

    const animate = (time) => {
      const elapsed = (time - startTime) / 1000;
      const rotateX = elapsed * 25;
      const rotateY = elapsed * 35;

      cube.style.transform = `rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;

      animationFrameId = requestAnimationFrame(animate);
    };

    animationFrameId = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <div className="w-screen h-screen overflow-hidden bg-black flex items-center justify-center">
      <div className="perspective-[1000px] w-full h-full flex items-center justify-center">
        <div
          ref={cubeRef}
          className="relative w-40 h-40 transform-style-preserve-3d"
          aria-label="3D rotating cube"
        >
          <div className="absolute inset-0 bg-cyan-500/80 border border-cyan-300 shadow-[0_0_40px_rgba(34,211,238,0.35)] transform translate-z-20" />
          <div className="absolute inset-0 bg-blue-500/80 border border-blue-300 shadow-[0_0_40px_rgba(59,130,246,0.35)] transform rotateY(180deg) translate-z-20" />
          <div className="absolute inset-0 bg-emerald-500/80 border border-emerald-300 shadow-[0_0_40px_rgba(16,185,129,0.35)] transform rotateY(90deg) translate-z-20" />
          <div className="absolute inset-0 bg-violet-500/80 border border-violet-300 shadow-[0_0_40px_rgba(139,92,246,0.35)] transform rotateY(-90deg) translate-z-20" />
          <div className="absolute inset-0 bg-rose-500/80 border border-rose-300 shadow-[0_0_40px_rgba(244,63,94,0.35)] transform rotateX(90deg) translate-z-20" />
          <div className="absolute inset-0 bg-amber-500/80 border border-amber-300 shadow-[0_0_40px_rgba(245,158,11,0.35)] transform rotateX(-90deg) translate-z-20" />
        </div>
      </div>
    </div>
  );
}
