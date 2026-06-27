import { useEffect, useRef } from "react";
import * as THREE from "three";

const FACE_COLORS = [
  0x63b3ed, // right  - blue
  0xfc814a, // left   - orange
  0x9ae6b4, // top    - green
  0xf6ad55, // bottom - yellow
  0xb794f6, // front  - purple
  0xfc8181, // back   - red
];

const FACE_EMOJIS = ["🐾", "🐱", "🐶", "🌟", "☀️", "🌿"];

export default function Cube() {
  const mountRef = useRef(null);

  useEffect(() => {
    const SIZE = 220;
    const mount = mountRef.current;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(SIZE, SIZE);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setClearColor(0x000000, 0);
    mount.appendChild(renderer.domElement);

    // Scene & Camera
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
    camera.position.set(0, 0, 4);

    // Lights
    const ambient = new THREE.AmbientLight(0xffffff, 0.4);
    scene.add(ambient);

    const dirLight = new THREE.DirectionalLight(0xffffff, 0.9);
    dirLight.position.set(1, 2, 3);
    scene.add(dirLight);

    // Cube with per-face materials
    const geometry = new THREE.BoxGeometry(1.7, 1.7, 1.7);
    const materials = FACE_COLORS.map(
      (color) =>
        new THREE.MeshLambertMaterial({
          color,
          transparent: true,
          opacity: 0.85,
        })
    );
    const cube = new THREE.Mesh(geometry, materials);
    scene.add(cube);

    // Emoji sprites — one per face
    const emojiSize = 64;
    const spriteScale = 0.7;

    const faceOffsets = [
      new THREE.Vector3( 0.85,  0,     0),   // right
      new THREE.Vector3(-0.85,  0,     0),   // left
      new THREE.Vector3( 0,     0.85,  0),   // top
      new THREE.Vector3( 0,    -0.85,  0),   // bottom
      new THREE.Vector3( 0,     0,     0.85),// front
      new THREE.Vector3( 0,     0,    -0.85),// back
    ];

    const sprites = FACE_EMOJIS.map((emoji, i) => {
      const canvas = document.createElement("canvas");
      canvas.width = emojiSize;
      canvas.height = emojiSize;
      const ctx = canvas.getContext("2d");
      ctx.font = `${emojiSize * 0.7}px serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(emoji, emojiSize / 2, emojiSize / 2);

      const texture = new THREE.CanvasTexture(canvas);
      const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
      const sprite = new THREE.Sprite(material);
      sprite.scale.set(spriteScale, spriteScale, spriteScale);
      sprite.position.copy(faceOffsets[i]);
      cube.add(sprite);
      return sprite;
    });

    // Animation loop
    let rafId;
    const clock = new THREE.Clock();

    const animate = () => {
      rafId = requestAnimationFrame(animate);
      const dt = clock.getDelta();
      cube.rotation.x += 0.4 * dt;
      cube.rotation.y += 0.6 * dt;
      cube.rotation.z += 0.15 * dt;
      renderer.render(scene, camera);
    };

    animate();

    return () => {
      cancelAnimationFrame(rafId);
      renderer.dispose();
      geometry.dispose();
      materials.forEach((m) => m.dispose());
      sprites.forEach((s) => s.material.map.dispose());
      mount.removeChild(renderer.domElement);
    };
  }, []);

  return (
    <div
      ref={mountRef}
      style={{
        width: 220,
        height: 220,
        borderRadius: "12px",
        overflow: "hidden",
        boxShadow: "0 8px 32px rgba(0,0,0,0.25)",
      }}
    />
  );
}
