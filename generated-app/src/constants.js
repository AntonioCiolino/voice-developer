export const EXPLODE_EMOJIS = ["💥", "✨", "⭐", "🌟", "💫", "🔥", "🪶", "💨"];

export const GROUND_ITEMS = Array.from({ length: 30 }, (_, i) => ({
  id: i,
  isFlower: i % 7 === 0,
  swayDelay: `${(i * 0.1) % 1.5}s`,
}));
