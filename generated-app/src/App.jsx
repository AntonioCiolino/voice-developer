import React, { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

function createBaseScene() {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x050816);
  scene.fog = new THREE.Fog(0x050816, 10, 30);
  return scene;
}

function createCamera() {
  const camera = new THREE.PerspectiveCamera(
    60,
    window.innerWidth / window.innerHeight,
    0.1,
    1000
  );
  camera.position.set(4, 3, 7);
  return camera;
}

function createRenderer() {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  renderer.setPixelRatio(window.devicePixelRatio || 1);
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  return renderer;
}

function createLighting(scene) {
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

  return {
    ambientLight,
    hemisphereLight,
    directionalLight,
    pointLight,
  };
}

function createEnvironment(scene) {
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

  const gridHelper = new THREE.GridHelper(30, 30, 0x334155, 0x1e293b);
  gridHelper.position.y = -1.49;
  scene.add(gridHelper);

  const clickPlaneGeometry = new THREE.PlaneGeometry(30, 30);
  const clickPlaneMaterial = new THREE.MeshBasicMaterial({
    visible: false,
    side: THREE.DoubleSide,
  });
  const clickPlane = new THREE.Mesh(clickPlaneGeometry, clickPlaneMaterial);
  clickPlane.rotation.x = -Math.PI / 2;
  clickPlane.position.y = -1.25;
  scene.add(clickPlane);

  return {
    floor,
    floorGeometry,
    floorMaterial,
    gridHelper,
    clickPlane,
    clickPlaneGeometry,
    clickPlaneMaterial,
  };
}

function createDemoObjects(scene) {
  const torusGeometry = new THREE.TorusKnotGeometry(1, 0.35, 160, 24);
  const torusMaterial = new THREE.MeshStandardMaterial({
    color: 0x22d3ee,
    metalness: 0.55,
    roughness: 0.2,
  });
  const torusKnot = new THREE.Mesh(torusGeometry, torusMaterial);
  torusKnot.position.y = 0.5;
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

  return {
    torusKnot,
    torusGeometry,
    torusMaterial,
    sphere,
    sphereGeometry,
    sphereMaterial,
    box,
    boxGeometry,
    boxMaterial,
  };
}

function createBall(scene, position) {
  const ballGeometry = new THREE.SphereGeometry(0.25, 24, 24);
  const ballMaterial = new THREE.MeshStandardMaterial({
    color: 0x38bdf8,
    metalness: 0.25,
    roughness: 0.35,
  });

  const ball = new THREE.Mesh(ballGeometry, ballMaterial);
  ball.position.copy(position);
  ball.position.y = Math.max(position.y, -1.25);
  scene.add(ball);

  return ball;
}

function disposeObject3D(object) {
  if (!object) return;

  object.traverse?.((child) => {
    if (child.geometry) {
      child.geometry.dispose();
    }

    if (child.material) {
      if (Array.isArray(child.material)) {
        child.material.forEach((material) => material.dispose());
      } else {
        child.material.dispose();
      }
    }
  });
}

export default function App() {
  const mountRef = useRef(null);
  const controlsRef = useRef(null);
  const cameraRef = useRef(null);
  const sceneRef = useRef(null);
  const rendererRef = useRef(null);
  const assetsRef = useRef({
    currentSceneId: "demo",
    scenes: {},
    loadedAssets: {},
  });
  const animationStateRef = useRef({
    autoRotate: true,
    torusSpeed: 1,
  });

  const [autoRotate, setAutoRotate] = useState(true);
  const [torusSpeed, setTorusSpeed] = useState(1);
  const [activeSceneId] = useState("demo");
  const [ballCount, setBallCount] = useState(0);

  useEffect(() => {
    animationStateRef.current.autoRotate = autoRotate;
  }, [autoRotate]);

  useEffect(() => {
    animationStateRef.current.torusSpeed = torusSpeed;
  }, [torusSpeed]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const scene = createBaseScene();
    sceneRef.current = scene;

    const camera = createCamera();
    cameraRef.current = camera;

    const renderer = createRenderer();
    rendererRef.current = renderer;
    mount.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controlsRef.current = controls;
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.rotateSpeed = 0.6;
    controls.zoomSpeed = 0.8;
    controls.panSpeed = 0.8;
    controls.target.set(0, 0.5, 0);

    createLighting(scene);
    const environment = createEnvironment(scene);
    const demoObjects = createDemoObjects(scene);

    assetsRef.current.scenes.demo = {
      id: "demo",
      name: "Demo Scene",
      objects: demoObjects,
      environment,
      balls: [],
    };
    assetsRef.current.currentSceneId = "demo";

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();

    const getPointerWorldPosition = (event) => {
      const rect = renderer.domElement.getBoundingClientRect();
      const x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      const y = -(((event.clientY - rect.top) / rect.height) * 2 - 1);

      pointer.set(x, y);
      raycaster.setFromCamera(pointer, camera);

      const intersections = raycaster.intersectObject(environment.clickPlane, false);
      return intersections[0]?.point || null;
    };

    const handlePointerDown = (event) => {
      const worldPosition = getPointerWorldPosition(event);
      if (!worldPosition) return;

      const currentScene = assetsRef.current.scenes[assetsRef.current.currentSceneId];
      if (!currentScene) return;

      const ball = createBall(scene, worldPosition);
      currentScene.balls = currentScene.balls || [];
      currentScene.balls.push(ball);
      setBallCount(currentScene.balls.length);
    };

    renderer.domElement.addEventListener("pointerdown", handlePointerDown);

    const clock = new THREE.Clock();
    let animationFrameId = 0;

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);

      const elapsedTime = clock.getElapsedTime();
      const deltaTime = clock.getDelta();

      const currentSpeed = animationStateRef.current.torusSpeed;
      const isAutoRotate = animationStateRef.current.autoRotate;
      const currentScene = assetsRef.current.scenes[assetsRef.current.currentSceneId];

      if (currentScene?.objects) {
        const { torusKnot, sphere, box } = currentScene.objects;

        if (isAutoRotate && torusKnot) {
          torusKnot.rotation.x += 0.8 * deltaTime * currentSpeed;
          torusKnot.rotation.y += 1.2 * deltaTime * currentSpeed;
        }

        if (sphere) {
          sphere.rotation.y += 0.9 * deltaTime;
          sphere.position.y = 0.2 + Math.sin(elapsedTime * 2.0) * 0.05;
        }

        if (box) {
          box.rotation.x += 0.9 * deltaTime;
          box.rotation.y += 0.8 * deltaTime;
          box.position.y = 0.1 + Math.cos(elapsedTime * 1.8) * 0.05;
        }

        if (torusKnot) {
          torusKnot.position.y = 0.5 + Math.sin(elapsedTime * 1.5) * 0.08;
        }
      }

      if (currentScene?.balls?.length) {
        currentScene.balls.forEach((ball, index) => {
          ball.position.y =
            Math.max(ball.position.y, -1.25) + Math.sin(elapsedTime * 3 + index) * 0.0005;
          ball.rotation.x += 0.4 * deltaTime;
          ball.rotation.y += 0.6 * deltaTime;
        });
      }

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
      renderer.domElement.removeEventListener("pointerdown", handlePointerDown);

      controls.dispose();

      disposeObject3D(environment.floor);
      disposeObject3D(environment.gridHelper);
      disposeObject3D(environment.clickPlane);
      disposeObject3D(demoObjects.torusKnot);
      disposeObject3D(demoObjects.sphere);
      disposeObject3D(demoObjects.box);
      currentScene?.balls?.forEach((ball) => disposeObject3D(ball));

      renderer.dispose();

      if (mount.contains(renderer.domElement)) {
        mount.removeChild(renderer.domElement);
      }

      controlsRef.current = null;
      cameraRef.current = null;
      sceneRef.current = null;
      rendererRef.current = null;
      assetsRef.current = {
        currentSceneId: "demo",
        scenes: {},
        loadedAssets: {},
      };
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

  const sceneLabel = useMemo(() => {
    return activeSceneId === "demo" ? "Demo Scene" : activeSceneId;
  }, [activeSceneId]);

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

        <div className="mb-3 rounded-lg border border-white/10 bg-white/5 p-3 text-xs text-slate-300">
          <div className="flex items-center justify-between">
            <span>Active Scene</span>
            <span className="text-white">{sceneLabel}</span>
          </div>
          <div className="mt-2 flex items-center justify-between">
            <span>Asset Pipeline</span>
            <span>Ready</span>
          </div>
          <div className="mt-2 flex items-center justify-between">
            <span>Balls</span>
            <span>{ballCount}</span>
          </div>
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
              <span>Drag / Scroll / Click</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
