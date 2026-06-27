import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

export default function App() {
  const mountRef = useRef(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x020617);
    scene.fog = new THREE.Fog(0x020617, 8, 18);

    const camera = new THREE.PerspectiveCamera(
      60,
      mount.clientWidth / mount.clientHeight,
      0.1,
      100
    );
    camera.position.set(2.8, 2.3, 4.8);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: "high-performance",
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    mount.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.enablePan = false;
    controls.minDistance = 2.5;
    controls.maxDistance = 10;
    controls.target.set(0, 0.1, 0);
    controls.update();

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.85);
    scene.add(ambientLight);

    const hemisphereLight = new THREE.HemisphereLight(0x93c5fd, 0x0f172a, 1.1);
    scene.add(hemisphereLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 2.2);
    directionalLight.position.set(4, 7, 5);
    directionalLight.castShadow = true;
    directionalLight.shadow.mapSize.width = 2048;
    directionalLight.shadow.mapSize.height = 2048;
    directionalLight.shadow.camera.near = 0.5;
    directionalLight.shadow.camera.far = 20;
    directionalLight.shadow.camera.left = -6;
    directionalLight.shadow.camera.right = 6;
    directionalLight.shadow.camera.top = 6;
    directionalLight.shadow.camera.bottom = -6;
    scene.add(directionalLight);

    const fillLight = new THREE.PointLight(0x60a5fa, 1.4, 20);
    fillLight.position.set(-3, 2, 3);
    scene.add(fillLight);

    const rimLight = new THREE.PointLight(0x38bdf8, 0.9, 18);
    rimLight.position.set(2.5, 1.5, -3);
    scene.add(rimLight);

    const cubeGeometry = new THREE.BoxGeometry(1.5, 1.5, 1.5);
    const cubeMaterial = new THREE.MeshStandardMaterial({
      color: 0x3b82f6,
      metalness: 0.35,
      roughness: 0.22,
      emissive: 0x0f172a,
      emissiveIntensity: 0.15,
    });
    const cube = new THREE.Mesh(cubeGeometry, cubeMaterial);
    cube.castShadow = true;
    cube.receiveShadow = true;
    scene.add(cube);

    const edgesGeometry = new THREE.EdgesGeometry(cubeGeometry);
    const edgesMaterial = new THREE.LineBasicMaterial({
      color: 0x93c5fd,
      transparent: true,
      opacity: 0.45,
    });
    const edges = new THREE.LineSegments(edgesGeometry, edgesMaterial);
    cube.add(edges);

    const floorGeometry = new THREE.PlaneGeometry(14, 14);
    const floorMaterial = new THREE.MeshStandardMaterial({
      color: 0x0f172a,
      roughness: 1,
      metalness: 0,
    });
    const floor = new THREE.Mesh(floorGeometry, floorMaterial);
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -1.25;
    floor.receiveShadow = true;
    scene.add(floor);

    const shadowGeometry = new THREE.CircleGeometry(1.35, 48);
    const shadowMaterial = new THREE.MeshBasicMaterial({
      color: 0x000000,
      transparent: true,
      opacity: 0.28,
    });
    const shadow = new THREE.Mesh(shadowGeometry, shadowMaterial);
    shadow.rotation.x = -Math.PI / 2;
    shadow.position.y = -1.19;
    scene.add(shadow);

    const handleResize = () => {
      const width = mount.clientWidth;
      const height = mount.clientHeight;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    };

    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(mount);
    window.addEventListener("resize", handleResize);

    let animationFrameId;
    let time = 0;

    const animate = () => {
      time += 0.01;

      cube.rotation.x += 0.008;
      cube.rotation.y += 0.011;
      cube.position.y = Math.sin(time) * 0.08;
      cube.position.x = Math.cos(time * 0.7) * 0.03;

      shadow.scale.setScalar(1 + Math.sin(time) * 0.08);
      shadow.material.opacity = 0.24 + (1 - Math.sin(time) * 0.5) * 0.05;

      controls.update();
      renderer.render(scene, camera);
      animationFrameId = window.requestAnimationFrame(animate);
    };

    animate();

    return () => {
      window.removeEventListener("resize", handleResize);
      resizeObserver.disconnect();
      window.cancelAnimationFrame(animationFrameId);
      controls.dispose();
      cubeGeometry.dispose();
      cubeMaterial.dispose();
      edgesGeometry.dispose();
      edgesMaterial.dispose();
      floorGeometry.dispose();
      floorMaterial.dispose();
      shadowGeometry.dispose();
      shadowMaterial.dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode === mount) {
        mount.removeChild(renderer.domElement);
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
            Rendering technology: Three.js / WebGL
            <br />
            Controls: drag to rotate, scroll/pinch to zoom
          </p>
        </div>
      </div>

      <div ref={mountRef} className="h-screen w-screen" />
    </div>
  );
}
