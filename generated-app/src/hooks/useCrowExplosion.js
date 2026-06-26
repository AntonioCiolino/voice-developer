import { useState } from "react";
import { EXPLODE_EMOJIS } from "../constants";

export function useCrowExplosion({ setCrowVisible, setParticles, setSkyRed }) {
  const handleCrowClick = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;

    const newParticles = EXPLODE_EMOJIS.map((emoji, i) => {
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

    setParticles((prev) => [...prev, ...newParticles]);
    setCrowVisible(false);
    setSkyRed(true);

    setTimeout(() => {
      setParticles((prev) => prev.filter((p) => !newParticles.find((np) => np.id === p.id)));
      setCrowVisible(true);
      setSkyRed(false);
    }, 3000);
  };

  return { handleCrowClick };
}
