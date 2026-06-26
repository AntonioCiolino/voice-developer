import { useEffect, useRef, useState } from "react";

const BALL_SIZE = 40;
const GROUND_Y = 130; // bottom offset where ball rests (matches CSS ground height)
const GRAVITY = 0.5;
const BOUNCE_DAMPING = 0.72;
const INITIAL_VX = 3.5;
const INITIAL_VY = -12;

export default function Ball() {
  const containerRef = useRef(null);
  const stateRef = useRef({
    x: 60,
    vx: INITIAL_VX,
    vy: INITIAL_VY,
    // y measured from bottom of viewport upward, matching `bottom` CSS
    y: GROUND_Y,
  });
  const rafRef = useRef(null);
  const [pos, setPos] = useState({ x: 60, y: GROUND_Y });

  useEffect(() => {
    const getContainerWidth = () => {
      return window.innerWidth;
    };

    const tick = () => {
      const s = stateRef.current;
      const width = getContainerWidth();

      // Apply gravity (vy is upward positive, so gravity subtracts)
      s.vy -= GRAVITY;

      s.x += s.vx;
      s.y += s.vy;

      // Bounce off ground
      if (s.y <= GROUND_Y) {
        s.y = GROUND_Y;
        s.vy = Math.abs(s.vy) * BOUNCE_DAMPING;
        // If bounce is too small, reset to keep it lively
        if (s.vy < 3) {
          s.vy = 8 + Math.random() * 5;
        }
      }

      // Bounce off left edge
      if (s.x <= 0) {
        s.x = 0;
        s.vx = Math.abs(s.vx);
      }

      // Bounce off right edge
      if (s.x >= width - BALL_SIZE) {
        s.x = width - BALL_SIZE;
        s.vx = -Math.abs(s.vx);
      }

      setPos({ x: s.x, y: s.y });
      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, []);

  return (
    <div
      style={{
        position: "absolute",
        left: pos.x,
        bottom: pos.y,
        width: BALL_SIZE,
        height: BALL_SIZE,
        borderRadius: "50%",
        background: "radial-gradient(circle at 35% 35%, #a8ff78, #2ecc40)",
        boxShadow: "2px 4px 8px rgba(0,0,0,0.3), inset -3px -3px 6px rgba(0,0,0,0.15)",
        zIndex: 6,
        pointerEvents: "none",
      }}
    />
  );
}
