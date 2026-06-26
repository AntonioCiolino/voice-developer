import { useState, useEffect } from "react";

export function usePawPrints() {
  const [paws, setPaws] = useState([]);

  useEffect(() => {
    const interval = setInterval(() => {
      const id = Date.now();
      const x = Math.random() * 90 + 5;
      setPaws((prev) => [...prev.slice(-6), { id, x }]);
    }, 600);
    return () => clearInterval(interval);
  }, []);

  return paws;
}
