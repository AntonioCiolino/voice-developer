import { useEffect, useRef } from "react";

const FACES = [
  { indices: [0, 1, 2, 3], emoji: "🐾", color: [99, 179, 237] },   // front
  { indices: [4, 5, 6, 7], emoji: "🐱", color: [252, 129, 74] },   // back
  { indices: [0, 1, 5, 4], emoji: "🐶", color: [154, 230, 180] },  // bottom
  { indices: [2, 3, 7, 6], emoji: "🌟", color: [246, 173, 85] },   // top
  { indices: [0, 3, 7, 4], emoji: "☀️", color: [183, 148, 246] },  // left
  { indices: [1, 2, 6, 5], emoji: "🌿", color: [252, 129, 129] },  // right
];

// Unit cube vertices (centered at origin)
const BASE_VERTICES = [
  [-1, -1,  1], // 0 front-bottom-left
  [ 1, -1,  1], // 1 front-bottom-right
  [ 1,  1,  1], // 2 front-top-right
  [-1,  1,  1], // 3 front-top-left
  [-1, -1, -1], // 4 back-bottom-left
  [ 1, -1, -1], // 5 back-bottom-right
  [ 1,  1, -1], // 6 back-top-right
  [-1,  1, -1], // 7 back-top-left
];

function rotateX(v, a) {
  const [x, y, z] = v;
  return [x, y * Math.cos(a) - z * Math.sin(a), y * Math.sin(a) + z * Math.cos(a)];
}
function rotateY(v, a) {
  const [x, y, z] = v;
  return [x * Math.cos(a) + z * Math.sin(a), y, -x * Math.sin(a) + z * Math.cos(a)];
}
function rotateZ(v, a) {
  const [x, y, z] = v;
  return [x * Math.cos(a) - y * Math.sin(a), x * Math.sin(a) + y * Math.cos(a), z];
}

function project(v, fov, cx, cy) {
  const z = v[2] + 4; // push back so cube is in front of camera
  const scale = fov / z;
  return [v[0] * scale + cx, -v[1] * scale + cy];
}

function cross(a, b) {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ];
}
function sub(a, b) {
  return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
}
function dot(a, b) {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}
function normalize(v) {
  const len = Math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2);
  return len === 0 ? v : [v[0] / len, v[1] / len, v[2] / len];
}

const LIGHT_DIR = normalize([1, 2, 3]);
const AMBIENT = 0.35;

export default function Cube() {
  const canvasRef = useRef(null);
  const angleRef = useRef({ x: 0.4, y: 0, z: 0 });
  const rafRef = useRef(null);
  const lastTimeRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");

    const SIZE = 220;
    canvas.width = SIZE;
    canvas.height = SIZE;
    const cx = SIZE / 2;
    const cy = SIZE / 2;
    const FOV = 260;
    const HALF = 0.85; // cube half-size

    const draw = (timestamp) => {
      if (!lastTimeRef.current) lastTimeRef.current = timestamp;
      const dt = (timestamp - lastTimeRef.current) / 1000;
      lastTimeRef.current = timestamp;

      angleRef.current.x += 0.4 * dt;
      angleRef.current.y += 0.6 * dt;
      angleRef.current.z += 0.15 * dt;

      const { x: ax, y: ay, z: az } = angleRef.current;

      // Transform all vertices
      const verts = BASE_VERTICES.map((v) => {
        let p = [v[0] * HALF, v[1] * HALF, v[2] * HALF];
        p = rotateX(p, ax);
        p = rotateY(p, ay);
        p = rotateZ(p, az);
        return p;
      });

      // Project to 2D
      const projected = verts.map((v) => project(v, FOV, cx, cy));

      // Build face data with depth and normal
      const faceData = FACES.map((face) => {
        const [i0, i1, i2, i3] = face.indices;
        const v0 = verts[i0], v1 = verts[i1], v2 = verts[i2], v3 = verts[i3];

        // Average Z for depth sorting
        const avgZ = (v0[2] + v1[2] + v2[2] + v3[2]) / 4;

        // Face normal via cross product
        const edge1 = sub(v1, v0);
        const edge2 = sub(v3, v0);
        const normal = normalize(cross(edge1, edge2));

        // Back-face culling: skip faces pointing away from camera
        const toCamera = [0, 0, 1];
        const facing = dot(normal, toCamera);

        // Flat shading
        const diffuse = Math.max(0, dot(normal, LIGHT_DIR));
        const brightness = AMBIENT + (1 - AMBIENT) * diffuse;

        const [r, g, b] = face.color;
        const fr = Math.min(255, Math.round(r * brightness));
        const fg = Math.min(255, Math.round(g * brightness));
        const fb = Math.min(255, Math.round(b * brightness));

        return {
          face,
          avgZ,
          facing,
          fillColor: `rgb(${fr},${fg},${fb})`,
          pts: face.indices.map((i) => projected[i]),
          center3d: [
            (v0[0] + v1[0] + v2[0] + v3[0]) / 4,
            (v0[1] + v1[1] + v2[1] + v3[1]) / 4,
            (v0[2] + v1[2] + v2[2] + v3[2]) / 4,
          ],
        };
      });

      // Sort back-to-front (painter's algorithm)
      faceData.sort((a, b) => a.avgZ - b.avgZ);

      // Clear
      ctx.clearRect(0, 0, SIZE, SIZE);

      // Draw faces
      for (const fd of faceData) {
        if (fd.facing <= 0) continue; // back-face cull

        const [p0, p1, p2, p3] = fd.pts;

        // Fill polygon
        ctx.beginPath();
        ctx.moveTo(p0[0], p0[1]);
        ctx.lineTo(p1[0], p1[1]);
        ctx.lineTo(p2[0], p2[1]);
        ctx.lineTo(p3[0], p3[1]);
        ctx.closePath();

        ctx.fillStyle = fd.fillColor;
        ctx.fill();

        // Edge outline
        ctx.strokeStyle = "rgba(255,255,255,0.55)";
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Emoji label at face center projected to 2D
        const fc = fd.center3d;
        const fz = fc[2] + 4;
        const scale = FOV / fz;
        const ex = fc[0] * scale + cx;
        const ey = -fc[1] * scale + cy;

        const emojiSize = Math.max(14, Math.round(28 * (scale / (FOV / 4))));
        ctx.font = `${emojiSize}px serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(fd.face.emoji, ex, ey);
      }

      rafRef.current = requestAnimationFrame(draw);
    };

    rafRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(rafRef.current);
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        display: "block",
        borderRadius: "12px",
        boxShadow: "0 8px 32px rgba(0,0,0,0.25)",
        background: "transparent",
      }}
    />
  );
}
