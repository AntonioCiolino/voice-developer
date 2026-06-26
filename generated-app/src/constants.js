export const EXPLODE_EMOJIS = ["💥", "✨", "⭐", "🌟", "💫", "🔥", "🪶", "💨"];

export const GROUND_ITEMS = Array.from({ length: 30 }, (_, i) => ({
  id: i,
  isFlower: i % 7 === 0,
  swayDelay: `${(i * 0.1) % 1.5}s`,
}));

export const FERN_ITEMS = Array.from({ length: 18 }, (_, i) => ({
  id: i,
  left: `${(i / 18) * 100 + Math.sin(i) * 2}%`,
  size: 1.4 + (i % 3) * 0.4,
  swayDelay: `${(i * 0.17) % 2}s`,
  swayDuration: `${1.2 + (i % 4) * 0.3}s`,
  zIndex: i % 2 === 0 ? 4 : 2,
  bottom: i % 3 === 0 ? "108px" : i % 3 === 1 ? "112px" : "105px",
}));
