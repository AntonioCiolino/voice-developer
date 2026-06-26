import { useState } from "react";
import { EXPLODE_EMOJIS } from "../constants";

export function useCatLeap({ catRef, crowRef, setCrowVisible, setParticles }) {
  const [catLeaping, setCatLeaping] = useState(false);
  const [catStyle, setCatStyle] = useState(null);

  const buildParticles = (crowRect) => {
    const cx = crowRect.left + crowRect.width / 2;
    const cy = crowRect.top + crowRect.height / 2;
    return EXPLODE_EMOJIS.map((emoji, i) => {
      const angle = (i / EXPLODE_EMOJIS.length) * 2 * Math.PI;
      const dist = 60 + Math.random() * 60;
      return {
        id: Date.now() + i,
        emoji,
        x: cx,
        y: cy,
        tx: `${Math.cos(angle) * dist}px`,
        ty: `${Math.sin(angle) * dist}px`,
      };
    });
  };

  const handleCatClick = () => {
    if (catLeaping) return;

    const crowEl = crowRef.current;
    const catEl = catRef.current;
    if (!crowEl || !catEl) return;

    const crowRect = crowEl.getBoundingClientRect();
    const catRect = catEl.getBoundingClientRect();
    const containerRect = catEl.parentElement.getBoundingClientRect();

    const catStartLeft = catRect.left - containerRect.left;
    const catStartBottom = containerRect.bottom - catRect.bottom;
    const crowTargetLeft = crowRect.left - containerRect.left + crowRect.width / 2 - catRect.width / 2;
    const crowTargetBottom = containerRect.bottom - crowRect.bottom + crowRect.height / 2;

    setCatLeaping(true);
    setCrowVisible(false);

    setCatStyle({
      position: "absolute",
      fontSize: "4rem",
      transform: "scaleX(-1)",
      cursor: "pointer",
      zIndex: 10,
      left: catStartLeft,
      bottom: catStartBottom,
      transition: "none",
    });

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        setCatStyle((prev) => ({
          ...prev,
          left: crowTargetLeft,
          bottom: crowTargetBottom,
          transition: "left 0.5s ease-in-out, bottom 0.4s ease-in",
        }));

        setTimeout(() => {
          setCatStyle((prev) => ({ ...prev, transition: "none" }));

          const newParticles = buildParticles(crowRect);
          setParticles((prev) => [...prev, ...newParticles]);

          setTimeout(() => {
            setCatStyle((prev) => ({
              ...prev,
              bottom: catStartBottom,
              transition: "bottom 0.4s ease-in",
            }));

            setTimeout(() => {
              setCatStyle(null);
              setCatLeaping(false);
              setCrowVisible(true);
              setParticles((prev) =>
                prev.filter((p) => !newParticles.find((np) => np.id === p.id))
              );
            }, 500);
          }, 800);
        }, 550);
      });
    });
  };

  return { catLeaping, catStyle, handleCatClick };
}
