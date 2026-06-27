import { useEffect, useRef } from "react";
import * as THREE from "three";

export default function Cube() {
  const mountRef = useRef(null);

  useEffect(() => {
    const mount = mountRef.current;
    const width = mount.clientWidth;
    const height = mount.clientHeight;

    // --- Renderer ---
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio);
    mount.appendChild(renderer.domElement);

    // --- Scene & Camera ---
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    camera.position.set(0, 0, 4);

    // --- Cube ---
    const geometry = new THREE.BoxGeometry(1.5, 1.5, 1.5);

    // Six face colors matching the original CSS faces
    const materials = [
      new THREE.MeshPhongMaterial({ color: 0xfc814a, transparent: true, opacity: 0.85 }), // right  (orange)
      new THREE.MeshPhongMaterial({ color: 0x63b3ed, transparent: true, opacity: 0.85 }), // left   (blue)
      new THREE.MeshPhongMaterial({ color: 0xb794f6, transparent: true, opacity: 0.85 }), // top    (purple)
      new THREE.MeshPhongMaterial({ color: 0xfc8181, transparent: true, opacity: 0.85 }), // bottom (pink)
      new THREE.MeshPhongMaterial({ color: 0x9ae6b4, transparent: true, opacity: 0.85 }), // front  (green)
      new THREE.MeshPhongMaterial({ color: 0xf6ad55, transparent: true, opacity: 0.85 }), // back   (amber)
    ];

    const cube = new THREE.Mesh(geometry, materials);
    scene.add(cube);

    // Wireframe overlay for a glassy edge effect
    const wireframe = new THREE.LineSegments(
      new THREE.EdgesGeometry(geometry),
      new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.6 })
    );
    cube.add(wireframe);

    // --- Lights ---
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
    scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0xffffff, 1.2);
    dirLight1.position.set(5, 5, 5);
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0x8888ff, 0.4);
    dirLight2.position.set(-5, -3, -5);
    scene.add(dirLight2);

    // --- Animation loop ---
    let animId;
    const animate = () => {
      animId = requestAnimationFrame(animate);
      cube.rotation.x += 0.008;
      cube.rotation.y += 0.013;
      cube.rotation.z += 0.005;
      renderer.render(scene, camera);
    };
    animate();

    // --- Handle resize ---
    const handleResize = () => {
      const w = mount.clientWidth;
      const h = mount.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener("resize", handleResize);

    // --- Cleanup ---
    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", handleResize);
      mount.removeChild(renderer.domElement);
      renderer.dispose();
      geometry.dispose();
      materials.forEach((m) => m.dispose());
    };
  }, []);

  return (
    <div
      ref={mountRef}
      style={{
        width: "220px",
        height: "220px",
        borderRadius: "16px",
        overflow: "hidden",
        boxShadow: "0 8px 32px rgba(0,0,0,0.25)",
      }}
    />
  );
}
