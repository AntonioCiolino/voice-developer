import React, { useEffect, useRef } from "react";

export default function App() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationFrameId;
    let startTime = performance.now();

    const resizeCanvas = () => {
      const dpr = window.devicePixelRatio || 1;
      const width = window.innerWidth;
      const height = window.innerHeight;

      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const project = (x, y, z, width, height, fov, viewerDistance) => {
      const scale = fov / (viewerDistance + z);
      return {
        x: x * scale + width / 2,
        y: -y * scale + height / 2,
      };
    };

    const rotateX = (point, angle) => {
      const cos = Math.cos(angle);
      const sin = Math.sin(angle);
      return {
        x: point.x,
        y: point.y * cos - point.z * sin,
        z: point.y * sin + point.z * cos,
      };
    };

    const rotateY = (point, angle) => {
      const cos = Math.cos(angle);
      const sin = Math.sin(angle);
      return {
        x: point.x * cos + point.z * sin,
        y: point.y,
        z: -point.x * sin + point.z * cos,
      };
    };

    const rotateZ = (point, angle) => {
      const cos = Math.cos(angle);
      const sin = Math.sin(angle);
      return {
        x: point.x * cos - point.y * sin,
        y: point.x * sin + point.y * cos,
        z: point.z,
      };
    };

    const drawLine = (a, b, color, width = 2) => {
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.stroke();
    };

    const animate = (time) => {
      const width = window.innerWidth;
      const height = window.innerHeight;
      const elapsed = (time - startTime) / 1000;

      ctx.clearRect(0, 0, width, height);

      // Background
      const gradient = ctx.createRadialGradient(
        width / 2,
        height / 2,
        20,
        width / 2,
        height / 2,
        Math.max(width, height) / 1.2
      );
      gradient.addColorStop(0, "#050816");
      gradient.addColorStop(1, "#000000");
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, width, height);

      const cubeSize = Math.min(width, height) * 0.18;
      const half = cubeSize / 2;

      const vertices = [
        { x: -half, y: -half, z: -half },
        { x: half, y: -half, z: -half },
        { x: half, y: half, z: -half },
        { x: -half, y: half, z: -half },
        { x: -half, y: -half, z: half },
        { x: half, y: -half, z: half },
        { x: half, y: half, z: half },
        { x: -half, y: half, z: half },
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

      const ax = elapsed * 0.9;
      const ay = elapsed * 1.3;
      const az = elapsed * 0.4;

      const rotated = vertices.map((v) => {
        let p = rotateX(v, ax);
        p = rotateY(p, ay);
        p = rotateZ(p, az);
        return p;
      });

      const projected = rotated.map((p) =>
        project(p.x, p.y, p.z, width, height, 700, 700)
      );

      // Glow
      ctx.save();
      ctx.shadowColor = "rgba(34, 211, 238, 0.35)";
      ctx.shadowBlur = 24;
      edges.forEach(([start, end]) => {
        drawLine(projected[start], projected[end], "rgba(34, 211, 238, 0.9)", 3);
      });
      ctx.restore();

      // Accent edges
      edges.forEach(([start, end], index) => {
        const colors = [
          "rgba(34, 211, 238, 0.95)",
          "rgba(59, 130, 246, 0.95)",
          "rgba(16, 185, 129, 0.95)",
          "rgba(139, 92, 246, 0.95)",
          "rgba(244, 63, 94, 0.95)",
          "rgba(245, 158, 11, 0.95)",
        ];
        drawLine(projected[start], projected[end], colors[index % colors.length], 2);
      });

      // Vertices
      projected.forEach((p) => {
        ctx.beginPath();
        ctx.arc(p.x, p.y, 3, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(255, 255, 255, 0.9)";
        ctx.fill();
      });

      animationFrameId = requestAnimationFrame(animate);
    };

    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);
    animationFrameId = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener("resize", resizeCanvas);
    };
  }, []);

  return (
    <div className="w-screen h-screen overflow-hidden bg-black">
      <canvas
        ref={canvasRef}
        className="block w-full h-full"
        aria-label="3D rotating cube drawn frame by frame"
      />
    </div>
  );
}
