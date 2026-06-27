import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls";

export default function App() {
  const mountRef = useRef(null);
  const controlsRef = useRef(null);
  const cameraRef = useRef(null);
  const torusKnotRef = useRef(null);
  const animationStateRef = useRef({
    autoRotate: true,
    torusSpeed: 1,
  });

  const [autoRotate, setAutoRotate] = useState(true);
  const [torusSpeed, setTorusSpeed] = useState(1);

  useEffect(() => {
    animationStateRef.current.autoRotate = autoRotate;
  }, [autoRotate]);

  useEffect(() => {
    animationStateRef.current.torusSpeed = torusSpeed;
  }, [torusSpeed]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x050816);
    scene.fog = new THREE.Fog(0x050816, 10, 30);

    const camera = new THREE.PerspectiveCamera(
      60,
      window.innerWidth / window.innerHeight,
      0.1,
      1000
    );
    camera.position.set(4, 3, 7);
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(window.devicePixelRatio || 1);
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    mount.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controlsRef.current = controls;
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.rotateSpeed = 0.6;
    controls.zoomSpeed = 0.8;
    controls.panSpeed = 0.8;
    controls.target.set(0, 0.5, 0);

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
    scene.add(ambientLight);

    const hemisphereLight = new THREE.HemisphereLight(0x8ec5ff, 0x1b1b2f, 1.2);
    scene.add(hemisphereLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 2.5);
    directionalLight.position.set(5, 8, 6);
    scene.add(directionalLight);

    const pointLight = new THREE.PointLight(0x22d3ee, 35, 20);
    pointLight.position.set(-3, 2, 4);
    scene.add(pointLight);

    const floorGeometry = new THREE.PlaneGeometry(30, 30);
    const floorMaterial = new THREE.MeshStandardMaterial({
      color: 0x0f172a,
      roughness: 1,
      metalness: 0,
    });
    const floor = new THREE.Mesh(floorGeometry, floorMaterial);
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -1.5;
    scene.add(floor);

    const torusGeometry = new THREE.TorusKnotGeometry(1, 0.35, 160, 24);
    const torusMaterial = new THREE.MeshStandardMaterial({
      color: 0x22d3ee,
      metalness: 0.55,
      roughness: 0.2,
    });
    const torusKnot = new THREE.Mesh(torusGeometry, torusMaterial);
    torusKnot.position.y = 0.5;
    torusKnotRef.current = torusKnot;
    scene.add(torusKnot);

    const sphereGeometry = new THREE.SphereGeometry(0.45, 32, 32);
    const sphereMaterial = new THREE.MeshStandardMaterial({
      color: 0xf97316,
      metalness: 0.2,
      roughness: 0.35,
    });
    const sphere = new THREE.Mesh(sphereGeometry, sphereMaterial);
    sphere.position.set(2.2, 0.2, 0.5);
    scene.add(sphere);

    const boxGeometry = new THREE.BoxGeometry(0.8, 0.8, 0.8);
    const boxMaterial = new THREE.MeshStandardMaterial({
      color: 0xa855f7,
      metalness: 0.35,
      roughness: 0.3,
    });
    const box = new THREE.Mesh(boxGeometry, boxMaterial);
    box.position.set(-2.2, 0.1, -0.5);
    scene.add(box);

    const gridHelper = new THREE.GridHelper(30, 30, 0x334155, 0x1e293b);
    gridHelper.position.y = -1.49;
    scene.add(gridHelper);

    const clock = new THREE.Clock();
    let animationFrameId = 0;

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);

      const elapsedTime = clock.getElapsedTime();
      const deltaTime = clock.getDelta();

      const currentSpeed = animationStateRef.current.torusSpeed;
      const isAutoRotate = animationStateRef.current.autoRotate;

      if (isAutoRotate) {
        torusKnot.rotation.x += 0.8 * deltaTime * currentSpeed;
        torusKnot.rotation.y += 1.2 * deltaTime * currentSpeed;
      }

      sphere.rotation.y += 0.9 * deltaTime;
      box.rotation.x += 0.9 * deltaTime;
      box.rotation.y += 0.8 * deltaTime;

      torusKnot.position.y = 0.5 + Math.sin(elapsedTime * 1.5) * 0.08;
      sphere.position.y = 0.2 + Math.sin(elapsedTime * 2.0) * 0.05;
      box.position.y = 0.1 + Math.cos(elapsedTime * 1.8) * 0.05;

      controls.update();
      renderer.render(scene, camera);
    };

    const handleResize = () => {
      const width = mount.clientWidth || window.innerWidth;
      const height = mount.clientHeight || window.innerHeight;

      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
      renderer.setPixelRatio(window.devicePixelRatio || 1);
    };

    handleResize();
    window.addEventListener("resize", handleResize);
    animate();

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener("resize", handleResize);

      controls.dispose();
      floorGeometry.dispose();
      floorMaterial.dispose();
      torusGeometry.dispose();
      torusMaterial.dispose();
      sphereGeometry.dispose();
      sphereMaterial.dispose();
      boxGeometry.dispose();
      boxMaterial.dispose();
      renderer.dispose();

      if (mount.contains(renderer.domElement)) {
        mount.removeChild(renderer.domElement);
      }

      controlsRef.current = null;
      cameraRef.current = null;
      torusKnotRef.current = null;
    };
  }, []);

  const handleResetCamera = () => {
    const camera = cameraRef.current;
    const controls = controlsRef.current;

    if (!camera || !controls) return;

    camera.position.set(4, 3, 7);
    controls.target.set(0, 0.5, 0);
    controls.update();
  };

  const handleToggleAutoRotate = () => {
    setAutoRotate((value) => !value);
  };

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-black">
      <div ref={mountRef} className="absolute inset-0" />

      <div className="absolute top-4 left-4 z-10 w-[280px] rounded-2xl border border-white/10 bg-slate-950/70 p-4 text-white shadow-2xl backdrop-blur-md">
        <div className="mb-3">
          <h1 className="text-lg font-semibold">3D Scene Controls</h1>
          <p className="mt-1 text-sm text-slate-300">
            Orbit the scene, tweak motion, and reset the camera.
          </p>
        </div>

        <div className="space-y-3">
          <button
            type="button"
            onClick={handleToggleAutoRotate}
            className="w-full rounded-lg bg-cyan-500 px-3 py-2 text-sm font-medium text-slate-950 transition hover:bg-cyan-400"
          >
            {autoRotate ? "Pause Rotation" : "Resume Rotation"}
          </button>

          <button
            type="button"
            onClick={handleResetCamera}
            className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm font-medium text-white transition hover:bg-white/10"
          >
            Reset Camera
          </button>

          <label className="block">
            <div className="mb-2 flex items-center justify-between text-sm text-slate-300">
              <span>Torus Speed</span>
              <span>{torusSpeed.toFixed(1)}x</span>
            </div>
            <input
              type="range"
              min="0"
              max="3"
              step="0.1"
              value={torusSpeed}
              onChange={(e) => setTorusSpeed(Number(e.target.value))}
              className="w-full accent-cyan-400"
            />
          </label>

          <div className="rounded-lg border border-white/10 bg-white/5 p-3 text-sm text-slate-300">
            <div className="flex items-center justify-between">
              <span>Auto Rotate</span>
              <span className={autoRotate ? "text-emerald-400" : "text-rose-400"}>
                {autoRotate ? "On" : "Off"}
              </span>
            </div>
            <div className="mt-2 flex items-center justify-between">
              <span>Interaction</span>
              <span>Drag / Scroll</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
