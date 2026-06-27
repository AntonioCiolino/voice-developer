import React, { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

const COLLISION_CATEGORY = {
  BALL: 1 << 0,
  TORSO: 1 << 1,
  SPHERE: 1 << 2,
  BOX: 1 << 3,
};

function createBaseScene() {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x050816);
  scene.fog = new THREE.Fog(0x050816, 10, 30);

  // Enable gravity in the scene configuration so physics objects can use it.
  scene.userData.gravity = new THREE.Vector3(0, -9.8, 0);

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
  const greenPlaneGeometry = new THREE.PlaneGeometry(30, 30);
  const greenPlaneMaterial = new THREE.MeshStandardMaterial({
    color: 0x16a34a,
    roughness: 1,
    metalness: 0,
  });
  const greenPlane = new THREE.Mesh(greenPlaneGeometry, greenPlaneMaterial);
  greenPlane.rotation.x = -Math.PI / 2;
  greenPlane.position.y = -1.51;
  scene.add(greenPlane);

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
    greenPlane,
    greenPlaneGeometry,
    greenPlaneMaterial,
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
  const subjectPivot = new THREE.Group();
  subjectPivot.position.set(0, 0.5, 0);
  scene.add(subjectPivot);

  const torusGeometry = new THREE.TorusKnotGeometry(1, 0.35, 160, 24);
  const torusMaterial = new THREE.MeshStandardMaterial({
    color: 0x22d3ee,
    metalness: 0.55,
    roughness: 0.2,
  });
  const torusKnot = new THREE.Mesh(torusGeometry, torusMaterial);
  torusKnot.position.set(0, 0, 0);
  torusKnot.userData.collision = {
    type: "torus",
    category: COLLISION_CATEGORY.TORSO,
    mask: COLLISION_CATEGORY.BALL,
    majorRadius: 1.0,
    minorRadius: 0.45,
  };
  subjectPivot.add(torusKnot);

  const sphereGeometry = new THREE.SphereGeometry(0.45, 32, 32);
  const sphereMaterial = new THREE.MeshStandardMaterial({
    color: 0xf97316,
    metalness: 0.2,
    roughness: 0.35,
  });
  const sphere = new THREE.Mesh(sphereGeometry, sphereMaterial);
  sphere.position.set(2.2, -0.3, 0.5);
  sphere.userData.collision = {
    type: "sphere",
    category: COLLISION_CATEGORY.SPHERE,
    mask: COLLISION_CATEGORY.BALL,
    radius: 0.45,
  };
  subjectPivot.add(sphere);

  const boxGeometry = new THREE.BoxGeometry(0.8, 0.8, 0.8);
  const boxMaterial = new THREE.MeshStandardMaterial({
    color: 0xa855f7,
    metalness: 0.35,
    roughness: 0.3,
  });
  const box = new THREE.Mesh(boxGeometry, boxMaterial);
  box.position.set(-2.2, -0.4, -0.5);
  box.userData.collision = {
    type: "box",
    category: COLLISION_CATEGORY.BOX,
    mask: COLLISION_CATEGORY.BALL,
    halfExtents: new THREE.Vector3(0.4, 0.4, 0.4),
  };
  subjectPivot.add(box);

  return {
    subjectPivot,
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

  // Physics state
  ball.userData.velocity = new THREE.Vector3(0, 0, 0);
  ball.userData.acceleration = new THREE.Vector3(0, 0, 0);
  ball.userData.radius = 0.25;
  ball.userData.mass = 1;
  ball.userData.restitution = 0.45;
  ball.userData.linearDamping = 0.995;
  ball.userData.forces = new THREE.Vector3(0, 0, 0);
  ball.userData.collision = {
    type: "ball",
    category: COLLISION_CATEGORY.BALL,
    mask:
      COLLISION_CATEGORY.BALL |
      COLLISION_CATEGORY.TORSO |
      COLLISION_CATEGORY.SPHERE |
      COLLISION_CATEGORY.BOX,
  };

  scene.add(ball);

  return ball;
}

function applyForce(ball, force) {
  if (!ball?.userData) return;

  if (!ball.userData.forces) {
    ball.userData.forces = new THREE.Vector3(0, 0, 0);
  }

  ball.userData.forces.add(force);
}

function applyImpulse(ball, impulse) {
  if (!ball?.userData?.velocity) return;

  const mass = ball.userData.mass ?? 1;
  ball.userData.velocity.addScaledVector(impulse, 1 / mass);
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

function canCollide(a, b) {
  const aCollision = a?.userData?.collision;
  const bCollision = b?.userData?.collision;

  if (!aCollision || !bCollision) return false;

  return Boolean(
    (aCollision.mask & bCollision.category) &&
      (bCollision.mask & aCollision.category)
  );
}

function resolveBallTorusCollision(ball, torusKnot) {
  if (!ball || !torusKnot) return false;

  const radius = ball.userData.radius ?? 0.25;

  torusKnot.updateWorldMatrix(true, false);

  const torusWorldPosition = new THREE.Vector3();
  const torusWorldQuaternion = new THREE.Quaternion();
  const torusWorldScale = new THREE.Vector3();

  torusKnot.getWorldPosition(torusWorldPosition);
  torusKnot.getWorldQuaternion(torusWorldQuaternion);
  torusKnot.getWorldScale(torusWorldScale);

  const inverseQuaternion = torusWorldQuaternion.clone().invert();

  const ballWorldPosition = ball.getWorldPosition(new THREE.Vector3());
  const localBallPosition = ballWorldPosition
    .clone()
    .sub(torusWorldPosition)
    .applyQuaternion(inverseQuaternion);

  const majorRadius = 1.0 * Math.max(torusWorldScale.x, torusWorldScale.z);
  const minorRadius =
    0.45 * Math.max(torusWorldScale.x, torusWorldScale.y, torusWorldScale.z);

  const xzLength = Math.sqrt(
    localBallPosition.x * localBallPosition.x +
      localBallPosition.z * localBallPosition.z
  );

  const radialOffset = xzLength - majorRadius;
  const distanceToSurface = Math.sqrt(
    radialOffset * radialOffset + localBallPosition.y * localBallPosition.y
  );

  const combinedRadius = minorRadius + radius;

  if (distanceToSurface >= combinedRadius) {
    return false;
  }

  const velocity = ball.userData.velocity;
  const penetrationDepth = combinedRadius - distanceToSurface;

  let localNormal;

  if (distanceToSurface > 1e-6) {
    const radialDirection =
      xzLength > 1e-6
        ? new THREE.Vector3(
            localBallPosition.x / xzLength,
            0,
            localBallPosition.z / xzLength
          )
        : new THREE.Vector3(1, 0, 0);

    localNormal = new THREE.Vector3(
      radialDirection.x * radialOffset,
      localBallPosition.y,
      radialDirection.z * radialOffset
    ).normalize();
  } else {
    localNormal = new THREE.Vector3(0, 1, 0);
  }

  const worldNormal = localNormal
    .clone()
    .applyQuaternion(torusWorldQuaternion)
    .normalize();

  ball.position.addScaledVector(worldNormal, penetrationDepth + 0.001);

  const velocityAlongNormal = velocity.dot(worldNormal);
  if (velocityAlongNormal < 0) {
    const restitution = ball.userData.restitution ?? 0.45;
    velocity.addScaledVector(worldNormal, -(1 + restitution) * velocityAlongNormal);
    velocity.multiplyScalar(0.985);
  }

  if (Math.abs(velocity.y) < 0.08) {
    velocity.y = 0;
  }

  return true;
}

function resolveBallSphereCollision(ball, sphere) {
  if (!ball || !sphere) return false;

  const ballRadius = ball.userData.radius ?? 0.25;
  const sphereRadius = sphere.userData.collision?.radius ?? 0.45;

  sphere.updateWorldMatrix(true, false);

  const sphereWorldPosition = sphere.getWorldPosition(new THREE.Vector3());
  const ballWorldPosition = ball.getWorldPosition(new THREE.Vector3());
  const delta = ballWorldPosition.clone().sub(sphereWorldPosition);
  const distance = delta.length();
  const combinedRadius = ballRadius + sphereRadius;

  if (distance >= combinedRadius) {
    return false;
  }

  const velocity = ball.userData.velocity;
  const normal =
    distance > 1e-6 ? delta.multiplyScalar(1 / distance) : new THREE.Vector3(0, 1, 0);
  const penetrationDepth = combinedRadius - distance;

  ball.position.addScaledVector(normal, penetrationDepth + 0.001);

  const velocityAlongNormal = velocity.dot(normal);
  if (velocityAlongNormal < 0) {
    const restitution = ball.userData.restitution ?? 0.45;
    velocity.addScaledVector(normal, -(1 + restitution) * velocityAlongNormal);
    velocity.multiplyScalar(0.985);
  }

  return true;
}

function resolveBallBoxCollision(ball, box) {
  if (!ball || !box) return false;

  const ballRadius = ball.userData.radius ?? 0.25;
  const halfExtents = box.userData.collision?.halfExtents;
  if (!halfExtents) return false;

  box.updateWorldMatrix(true, false);

  const boxWorldPosition = box.getWorldPosition(new THREE.Vector3());
  const boxWorldQuaternion = box.getWorldQuaternion(new THREE.Quaternion());
  const inverseQuaternion = boxWorldQuaternion.clone().invert();

  const ballWorldPosition = ball.getWorldPosition(new THREE.Vector3());
  const localBallPosition = ballWorldPosition
    .clone()
    .sub(boxWorldPosition)
    .applyQuaternion(inverseQuaternion);

  const clampedPoint = new THREE.Vector3(
    THREE.MathUtils.clamp(localBallPosition.x, -halfExtents.x, halfExtents.x),
    THREE.MathUtils.clamp(localBallPosition.y, -halfExtents.y, halfExtents.y),
    THREE.MathUtils.clamp(localBallPosition.z, -halfExtents.z, halfExtents.z)
  );

  const delta = localBallPosition.clone().sub(clampedPoint);
  const distance = delta.length();

  if (distance >= ballRadius) {
    return false;
  }

  const velocity = ball.userData.velocity;
  const localNormal =
    distance > 1e-6
      ? delta.multiplyScalar(1 / distance)
      : new THREE.Vector3(0, 1, 0);

  const worldNormal = localNormal.clone().applyQuaternion(boxWorldQuaternion).normalize();
  const penetrationDepth = ballRadius - distance;

  ball.position.addScaledVector(worldNormal, penetrationDepth + 0.001);

  const velocityAlongNormal = velocity.dot(worldNormal);
  if (velocityAlongNormal < 0) {
    const restitution = ball.userData.restitution ?? 0.45;
    velocity.addScaledVector(worldNormal, -(1 + restitution) * velocityAlongNormal);
    velocity.multiplyScalar(0.985);
  }

  return true;
}

function resolveBallBallCollision(ballA, ballB) {
  if (!ballA || !ballB) return false;

  const radiusA = ballA.userData.radius ?? 0.25;
  const radiusB = ballB.userData.radius ?? 0.25;
  const combinedRadius = radiusA + radiusB;

  const positionA = ballA.position;
  const positionB = ballB.position;
  const delta = positionA.clone().sub(positionB);
  const distance = delta.length();

  if (distance >= combinedRadius) {
    return false;
  }

  const normal =
    distance > 1e-6 ? delta.multiplyScalar(1 / distance) : new THREE.Vector3(1, 0, 0);
  const penetrationDepth = combinedRadius - distance;

  positionA.addScaledVector(normal, penetrationDepth * 0.5 + 0.001);
  positionB.addScaledVector(normal, -(penetrationDepth * 0.5 + 0.001));

  const velocityA = ballA.userData.velocity;
  const velocityB = ballB.userData.velocity;
  const relativeVelocity = velocityA.clone().sub(velocityB);
  const velocityAlongNormal = relativeVelocity.dot(normal);

  if (velocityAlongNormal < 0) {
    const restitution = Math.min(
      ballA.userData.restitution ?? 0.45,
      ballB.userData.restitution ?? 0.45
    );
    const impulseMagnitude = (-(1 + restitution) * velocityAlongNormal) / 2;

    velocityA.addScaledVector(normal, impulseMagnitude);
    velocityB.addScaledVector(normal, -impulseMagnitude);
    velocityA.multiplyScalar(0.995);
    velocityB.multiplyScalar(0.995);
  }

  return true;
}

function resolveBallGenericCollision(ball, collider) {
  if (!ball || !collider?.userData?.collision) return false;

  if (!canCollide(ball, collider)) return false;

  const collisionType = collider.userData.collision.type;

  if (collisionType === "torus") {
    return resolveBallTorusCollision(ball, collider);
  }

  if (collisionType === "sphere") {
    return resolveBallSphereCollision(ball, collider);
  }

  if (collisionType === "box") {
    return resolveBallBoxCollision(ball, collider);
  }

  return false;
}

function stepBallPhysics(ball, deltaTime, gravity, colliders, balls) {
  if (!ball) return;

  const velocity = ball.userData.velocity;
  const radius = ball.userData.radius ?? 0.25;
  const floorY = -1.5 + radius;
  const restitution = ball.userData.restitution ?? 0.45;
  const linearDamping = ball.userData.linearDamping ?? 0.995;
  const mass = ball.userData.mass ?? 1;

  if (!ball.userData.forces) {
    ball.userData.forces = new THREE.Vector3(0, 0, 0);
  }

  const forceAcceleration = ball.userData.forces.clone().multiplyScalar(1 / mass);
  const totalAcceleration = gravity.clone().add(forceAcceleration);

  velocity.addScaledVector(totalAcceleration, deltaTime);
  ball.position.addScaledVector(velocity, deltaTime);

  ball.userData.forces.set(0, 0, 0);

  if (Array.isArray(colliders)) {
    colliders.forEach((collider) => {
      resolveBallGenericCollision(ball, collider);
    });
  }

  if (Array.isArray(balls)) {
    balls.forEach((otherBall) => {
      if (otherBall !== ball) {
        resolveBallBallCollision(ball, otherBall);
      }
    });
  }

  if (ball.position.y <= floorY) {
    ball.position.y = floorY;

    if (Math.abs(velocity.y) > 0.15) {
      velocity.y *= -restitution;
      velocity.x *= 0.98;
      velocity.z *= 0.98;
    } else {
      velocity.y = 0;
      velocity.x *= 0.9;
      velocity.z *= 0.9;
    }
  }

  velocity.multiplyScalar(linearDamping);

  ball.rotation.x += 0.4 * deltaTime;
  ball.rotation.y += 0.6 * deltaTime;
}

function resolveStaticObjectCollision(object, ball) {
  if (!object || !ball) return false;

  const collisionType = object.userData?.collision?.type;
  if (collisionType === "torus") return resolveBallTorusCollision(ball, object);
  if (collisionType === "sphere") return resolveBallSphereCollision(ball, object);
  if (collisionType === "box") return resolveBallBoxCollision(ball, object);
  return false;
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
    gravity: new THREE.Vector3(0, -9.8, 0),
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
    controls.dampingFactor = 0.06;
    controls.rotateSpeed = 0.5;
    controls.zoomSpeed = 0.9;
    controls.panSpeed = 0.7;
    controls.enablePan = true;
    controls.enableRotate = true;
    controls.enableZoom = true;
    controls.screenSpacePanning = false;
    controls.touches.ONE = THREE.TOUCH.ROTATE;
    controls.touches.TWO = THREE.TOUCH.DOLLY_PAN;
    controls.target.set(0, 0.5, 0);
    controls.minDistance = 2.2;
    controls.maxDistance = 20;
    controls.maxPolarAngle = Math.PI - 0.02;
    controls.minPolarAngle = 0.02;
    controls.maxAzimuthAngle = Infinity;
    controls.minAzimuthAngle = -Infinity;
    controls.update();

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

      const ballSpawnPosition = worldPosition.clone();
      ballSpawnPosition.y = 6;

      const ball = createBall(scene, ballSpawnPosition);

      ball.userData.velocity.set(0, 0, 0);
      applyImpulse(
        ball,
        new THREE.Vector3(
          (Math.random() - 0.5) * 2.5,
          4.5,
          (Math.random() - 0.5) * 2.5
        )
      );

      applyForce(ball, new THREE.Vector3(0, -1, 0));

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
      let deltaTime = clock.getDelta();
      if (deltaTime === 0) deltaTime = 1 / 60;

      const currentSpeed = animationStateRef.current.torusSpeed;
      const isAutoRotate = animationStateRef.current.autoRotate;
      const gravity =
        scene.userData.gravity || animationStateRef.current.gravity;
      const currentScene = assetsRef.current.scenes[assetsRef.current.currentSceneId];

      if (currentScene?.objects) {
        const { subjectPivot, torusKnot, sphere, box } = currentScene.objects;

        if (subjectPivot && isAutoRotate) {
          subjectPivot.rotation.y += 0.35 * deltaTime * currentSpeed;
        }

        if (isAutoRotate && torusKnot) {
          torusKnot.rotation.x += 0.8 * deltaTime * currentSpeed;
          torusKnot.rotation.y += 1.2 * deltaTime * currentSpeed;
        }

        if (sphere) {
          sphere.rotation.y += 0.9 * deltaTime;
        }

        if (box) {
          box.rotation.x += 0.9 * deltaTime;
          box.rotation.y += 0.8 * deltaTime;
        }

        if (torusKnot) {
          torusKnot.position.y = Math.sin(elapsedTime * 1.5) * 0.08;
        }
      }

      if (currentScene?.balls?.length) {
        const colliders = [
          currentScene.objects?.torusKnot,
          currentScene.objects?.sphere,
          currentScene.objects?.box,
        ].filter(Boolean);

        currentScene.balls.forEach((ball) => {
          stepBallPhysics(ball, deltaTime, gravity, colliders, currentScene.balls);
        });

        currentScene.balls.forEach((ball) => {
          colliders.forEach((collider) => {
            resolveStaticObjectCollision(collider, ball);
          });
        });

        setBallCount(currentScene.balls.length);
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

      if (controlsRef.current) {
        controlsRef.current.target.set(0, 0.5, 0);
        controlsRef.current.update();
      }
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
      disposeObject3D(environment.greenPlane);
      disposeObject3D(demoObjects.subjectPivot);
      disposeObject3D(demoObjects.torusKnot);
      disposeObject3D(demoObjects.sphere);
      disposeObject3D(demoObjects.box);

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
          <div className="mt-2 flex items-center justify-between">
            <span>Gravity</span>
            <span>Enabled</span>
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
            <div className="mt-2 flex items-center justify-between">
              <span>Orbit Control</span>
              <span>Enabled</span>
            </div>
            <div className="mt-2 flex items-center justify-between">
              <span>Spawn Balls</span>
              <span>Click the scene</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
