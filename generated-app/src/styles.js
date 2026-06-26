export const styles = `
  @keyframes catRun {
    0%   { left: 110%; }
    100% { left: -150px; }
  }

  @keyframes dogRun {
    0%   { left: 110%; }
    100% { left: -150px; }
  }

  @keyframes bounce {
    0%, 100% { transform: translateY(0) scaleX(-1); }
    50%       { transform: translateY(-18px) scaleX(-1); }
  }

  @keyframes bounceDog {
    0%, 100% { transform: translateY(0) scaleX(-1); }
    50%       { transform: translateY(-14px) scaleX(-1); }
  }

  @keyframes grassSway {
    0%, 100% { transform: rotate(-3deg); }
    50%       { transform: rotate(3deg); }
  }

  @keyframes flowerSway {
    0%, 100% { transform: rotate(-3deg); }
    50%       { transform: rotate(3deg); }
  }

  @keyframes cloudDrift {
    0%   { left: 110%; }
    100% { left: -200px; }
  }

  @keyframes pawPrint {
    0%   { opacity: 0; transform: scale(0.5); }
    20%  { opacity: 1; transform: scale(1); }
    80%  { opacity: 1; }
    100% { opacity: 0; }
  }

  @keyframes crowFly {
    0%   { left: -100px; }
    100% { left: 110%; }
  }

  @keyframes flapWings {
    0%, 100% { transform: scaleY(1); }
    50%       { transform: scaleY(0.6); }
  }

  @keyframes explodeParticle {
    0%   { opacity: 1; transform: translate(0, 0) scale(1); }
    100% { opacity: 0; transform: translate(var(--tx), var(--ty)) scale(0.3); }
  }

  @keyframes barkBubble {
    0%   { opacity: 0; transform: scale(0.5); }
    15%  { opacity: 1; transform: scale(1.1); }
    25%  { transform: scale(1); }
    80%  { opacity: 1; }
    100% { opacity: 0; }
  }

  @keyframes skyFlash {
    0%   { background-color: #87CEEB; }
    20%  { background-color: #ff2200; }
    80%  { background-color: #ff2200; }
    100% { background-color: #87CEEB; }
  }

  .cat {
    position: absolute;
    font-size: 4rem;
    animation: catRun 7s linear infinite, bounce 0.4s ease-in-out infinite;
    bottom: 130px;
    transform: scaleX(-1);
    cursor: pointer;
    z-index: 6;
  }

  .dog {
    position: absolute;
    font-size: 4rem;
    animation: dogRun 7s linear infinite 0.7s, bounceDog 0.35s ease-in-out infinite;
    bottom: 130px;
    transform: scaleX(-1);
    cursor: pointer;
    z-index: 6;
  }

  .cloud1 {
    position: absolute;
    font-size: 3rem;
    top: 60px;
    animation: cloudDrift 18s linear infinite;
    opacity: 0.85;
  }

  .cloud2 {
    position: absolute;
    font-size: 2rem;
    top: 100px;
    animation: cloudDrift 25s linear infinite 6s;
    opacity: 0.7;
  }

  .crow {
    position: absolute;
    font-size: 2.2rem;
    top: 140px;
    animation: crowFly 9s linear infinite 2s, flapWings 0.3s ease-in-out infinite;
    z-index: 5;
    filter: grayscale(100%) brightness(0.2);
    cursor: pointer;
  }

  .grass-blade {
    display: inline-block;
    animation: grassSway 1.5s ease-in-out infinite;
    transform-origin: bottom center;
    font-size: 2rem;
  }

  .flower {
    display: inline-block;
    animation: flowerSway 1.5s ease-in-out infinite;
    transform-origin: bottom center;
  }

  .explode-particle {
    position: fixed;
    font-size: 1.8rem;
    pointer-events: none;
    animation: explodeParticle 0.8s ease-out forwards;
    z-index: 999;
  }

  .bark-bubble {
    position: absolute;
    bottom: 175px;
    font-size: 1.2rem;
    background: white;
    border: 2px solid #333;
    border-radius: 12px;
    padding: 4px 10px;
    white-space: nowrap;
    animation: barkBubble 2s ease forwards;
    z-index: 20;
    pointer-events: none;
  }

  .bark-bubble::after {
    content: '';
    position: absolute;
    bottom: -10px;
    left: 14px;
    border-width: 10px 8px 0;
    border-style: solid;
    border-color: white transparent transparent;
  }

  .bark-bubble::before {
    content: '';
    position: absolute;
    bottom: -13px;
    left: 12px;
    border-width: 12px 10px 0;
    border-style: solid;
    border-color: #333 transparent transparent;
  }

  .sky-red {
    animation: skyFlash 3s ease forwards !important;
  }
`;
