import { useEffect, useRef } from "react";

export default function App() {
  const mountRef = useRef(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    mount.appendChild(canvas);

    let width = 0;
    let height = 0;
    let dpr = 1;
    let animationFrameId = 0;
    let time = 0;

    const resize = () => {
      width = mount.clientWidth;
      height = mount.clientHeight;
      dpr = Math.min(window.devicePixelRatio || 1, 2);

      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const project = (x, y, z, cameraDistance = 5.5, focalLength = 420) => {
      const scale = focalLength / (cameraDistance + z);
      return {
        x: width / 2 + x * scale,
        y: height / 2 + y * scale,
        scale,
      };
    };

    const drawBackground = () => {
      const bg = ctx.createLinearGradient(0, 0, 0, height);
      bg.addColorStop(0, "#020617");
      bg.addColorStop(1, "#0f172a");
      ctx.fillStyle = bg;
      ctx.fillRect(0, 0, width, height);

      const glow = ctx.createRadialGradient(
        width * 0.5,
        height * 0.25,
        20,
        width * 0.5,
        height * 0.25,
        Math.max(width, height) * 0.7
      );
      glow.addColorStop(0, "rgba(56, 189, 248, 0.18)");
      glow.addColorStop(1, "rgba(56, 189, 248, 0)");
      ctx.fillStyle = glow;
      ctx.fillRect(0, 0, width, height);
    };

    const rotatePoint = (point, rx, ry, rz) => {
      let { x, y, z } = point;

      const cosX = Math.cos(rx);
      const sinX = Math.sin(rx);
      const cosY = Math.cos(ry);
      const sinY = Math.sin(ry);
      const cosZ = Math.cos(rz);
      const sinZ = Math.sin(rz);

      let y1 = y * cosX - z * sinX;
      let z1 = y * sinX + z * cosX;
      y = y1;
      z = z1;

      let x2 = x * cosY + z * sinY;
      let z2 = -x * sinY + z * cosY;
      x = x2;
      z = z2;

      let x3 = x * cosZ - y * sinZ;
      let y3 = x * sinZ + y * cosZ;

      return { x: x3, y: y3, z };
    };

    const vertices = [
      { x: -1, y: -1, z: -1 },
      { x: 1, y: -1, z: -1 },
      { x: 1, y: 1, z: -1 },
      { x: -1, y: 1, z: -1 },
      { x: -1, y: -1, z: 1 },
      { x: 1, y: -1, z: 1 },
      { x: 1, y: 1, z: 1 },
      { x: -1, y: 1, z: 1 },
    ];

    const edges = [
      [0, 1],
      [1, 2],
      [2, 3],
      [3, 0],
      [4, 5],
      [5, 6],
      [6, 7],
      [7, 4],
      [0, 4],
      [1, 5],
      [2, 6],
      [3, 7],
    ];

    const animate = () => {
      time += 0.01;

      drawBackground();

      const rx = time * 0.8;
      const ry = time * 1.1;
      const rz = Math.sin(time * 0.5) * 0.2;

      const projected = vertices.map((v) => {
        const rotated = rotatePoint(v, rx, ry, rz);
        const bob = Math.sin(time * 2 + v.x + v.y + v.z) * 0.08;
        const p = project(rotated.x * 1.1, rotated.y * 1.1 + bob, rotated.z * 1.1);
        return { ...p, z: rotated.z };
      });

      const shadowScale = 1 + Math.sin(time) * 0.08;
      ctx.save();
      ctx.translate(width / 2, height * 0.72);
      ctx.scale(shadowScale * 1.2, shadowScale * 0.45);
      const shadow = ctx.createRadialGradient(0, 0, 10, 0, 0, 180);
      shadow.addColorStop(0, "rgba(0,0,0,0.35)");
      shadow.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = shadow;
      ctx.beginPath();
      ctx.arc(0, 0, 180, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();

      ctx.lineWidth = 2;
      ctx.strokeStyle = "rgba(147, 197, 253, 0.75)";
      ctx.fillStyle = "rgba(59, 130, 246, 0.9)";

      for (const [a, b] of edges) {
        const p1 = projected[a];
        const p2 = projected[b];
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
        ctx.stroke();
      }

      for (const p of projected) {
        ctx.beginPath();
        ctx.arc(p.x, p.y, 4.5, 0, Math.PI * 2);
        ctx.fill();
      }

      ctx.fillStyle = "rgba(255,255,255,0.08)";
      ctx.fillRect(0, 0, width, height);

      animationFrameId = window.requestAnimationFrame(animate);
    };

    resize();
    animate();

    window.addEventListener("resize", resize);

    return () => {
      window.removeEventListener("resize", resize);
      window.cancelAnimationFrame(animationFrameId);
      if (canvas.parentNode === mount) {
        mount.removeChild(canvas);
      }
    };
  }, []);

  return (
    <div className="relative min-h-screen overflow-hidden bg-slate-950 text-white">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.18),transparent_35%),radial-gradient(circle_at_bottom,rgba(59,130,246,0.12),transparent_30%)]" />
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-slate-900/20 via-transparent to-slate-950/60" />

      <div className="absolute left-0 top-0 z-10 p-6 md:p-8">
        <div className="max-w-md rounded-2xl border border-white/10 bg-slate-950/35 p-4 shadow-2xl backdrop-blur-md">
          <h1 className="mb-2 text-3xl font-bold tracking-tight md:text-4xl">
            3D Cube Demo
          </h1>
          <p className="text-sm leading-6 text-slate-300 md:text-base">
            Target platform: Web browser
            <br />
            Rendering technology: Canvas-based 3D-style animation
            <br />
            Controls: automatic rotation and motion
          </p>
        </div>
      </div>

      <div ref={mountRef} className="h-screen w-screen" />
    </div>
  );
}
