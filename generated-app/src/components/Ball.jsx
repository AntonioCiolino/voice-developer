import { useEffect, useRef, useState } from "react";

const BALL_SIZE = 40;
const GROUND_Y = 130; // bottom offset where ball rests (matches CSS ground height)
const GRAVITY = 0.5;
const BOUNCE_DAMPING = 0.85;
const INITIAL_VX = 5;
const INITIAL_VY = -20;
const MIN_BOUNCE_VY = 18;
const MAX_BOUNCE_VY = 22;

export default function Ball() {
  const stateRef = useRef({
    x: 60,
    vx: INITIAL_VX,
    vy: INITIAL_VY,
    y: GROUND_Y,
  });
  const rafRef = useRef(null);
  const [pos, setPos] = useState({ x: 60, y: GROUND_Y });

  useEffect(() => {
    const tick = () => {
      const s = stateRef.current;
      const width = window.innerWidth;

      // Apply gravity (vy is upward positive, so gravity subtracts)
      s.vy -= GRAVITY;

      s.x += s.vx;
      s.y += s.vy;

      // Bounce off ground
      if (s.y <= GROUND_Y) {
        s.y = GROUND_Y;
        s.vy = Math.abs(s.vy) * BOUNCE_DAMPING;
        // Keep bounce height lively
        if (s.vy < MIN_BOUNCE_VY) {
          s.vy = MIN_BOUNCE_VY + Math.random() * (MAX_BOUNCE_VY - MIN_BOUNCE_VY);
        }
        // Keep horizontal speed consistent
        const speed = Math.abs(s.vx);
        if (speed < INITIAL_VX) {
          s.vx = s.vx < 0 ? -INITIAL_VX : INITIAL_VX;
        }
      }

      // Bounce off left edge
      if (s.x <= 0) {
        s.x = 0;
        s.vx = INITIAL_VX;
      }

      // Bounce off right edge
      if (s.x >= width - BALL_SIZE) {
        s.x = width - BALL_SIZE;
        s.vx = -INITIAL_VX;
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
