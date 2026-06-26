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

  @keyframes fernSway {
    0%   { transform: rotate(-4deg) scaleX(1); }
    50%  { transform: rotate(4deg) scaleX(1); }
    100% { transform: rotate(-4deg) scaleX(1); }
  }

  @keyframes pawPrint {
    0%   { opacity: 0; transform: scale(0.5); }
    20%  { opacity: 1; transform: scale(1.1); }
    80%  { opacity: 1; transform: scale(1); }
    100% { opacity: 0; transform: scale(0.8); }
  }

  @keyframes explode {
    0%   { opacity: 1; transform: translate(0, 0) scale(1); }
    100% { opacity: 0; transform: translate(var(--tx), var(--ty)) scale(0.3); }
  }

  @keyframes barkBounce {
    0%, 100% { transform: translateY(0); }
    50%       { transform: translateY(-6px); }
  }

  @keyframes cloudDrift1 {
    0%   { left: -120px; }
    100% { left: 110%; }
  }

  @keyframes cloudDrift2 {
    0%   { left: -120px; }
    100% { left: 110%; }
  }

  .cat {
    position: absolute;
    bottom: 130px;
    font-size: 4rem;
    cursor: pointer;
    z-index: 10;
    user-select: none;
    animation: catRun 4s linear infinite, bounce 0.4s ease-in-out infinite;
    -webkit-animation: catRun 4s linear infinite, bounce 0.4s ease-in-out infinite;
    will-change: transform, left;
    -webkit-tap-highlight-color: transparent;
    touch-action: manipulation;
  }

  .dog {
    position: absolute;
    bottom: 128px;
    font-size: 4rem;
    cursor: pointer;
    z-index: 9;
    user-select: none;
    animation: dogRun 5s linear infinite, bounceDog 0.45s ease-in-out infinite;
    -webkit-animation: dogRun 5s linear infinite, bounceDog 0.45s ease-in-out infinite;
    will-change: transform, left;
    -webkit-tap-highlight-color: transparent;
    touch-action: manipulation;
  }

  .crow {
    position: absolute;
    top: 120px;
    left: 55%;
    font-size: 3rem;
    cursor: pointer;
    z-index: 10;
    user-select: none;
    -webkit-tap-highlight-color: transparent;
    touch-action: manipulation;
  }

  .grass-blade {
    display: inline-block;
    font-size: 1.5rem;
    animation: grassSway 1.2s ease-in-out infinite;
    -webkit-animation: grassSway 1.2s ease-in-out infinite;
    transform-origin: bottom center;
    will-change: transform;
  }

  .flower {
    display: inline-block;
    font-size: 1.5rem;
    animation: flowerSway 1.5s ease-in-out infinite;
    -webkit-animation: flowerSway 1.5s ease-in-out infinite;
    transform-origin: bottom center;
    will-change: transform;
  }

  .fern {
    display: inline-block;
    animation: fernSway 1.8s ease-in-out infinite;
    -webkit-animation: fernSway 1.8s ease-in-out infinite;
    transform-origin: bottom center;
    will-change: transform;
  }

  .explode-particle {
    position: fixed;
    font-size: 1.8rem;
    pointer-events: none;
    z-index: 999;
    animation: explode 0.8s ease-out forwards;
    -webkit-animation: explode 0.8s ease-out forwards;
    will-change: transform, opacity;
  }

  .bark-bubble {
    position: absolute;
    bottom: 175px;
    background: white;
    border: 2px solid #333;
    border-radius: 16px;
    padding: 4px 12px;
    font-size: 1rem;
    font-weight: bold;
    z-index: 20;
    animation: barkBounce 0.4s ease-in-out infinite;
    -webkit-animation: barkBounce 0.4s ease-in-out infinite;
    white-space: nowrap;
    pointer-events: none;
  }

  .bark-bubble::after {
    content: '';
    position: absolute;
    bottom: -10px;
    left: 16px;
    border-width: 10px 8px 0;
    border-style: solid;
    border-color: white transparent transparent;
  }

  .cloud1 {
    position: absolute;
    top: 40px;
    font-size: 4rem;
    z-index: 1;
    pointer-events: none;
    animation: cloudDrift1 18s linear infinite;
    -webkit-animation: cloudDrift1 18s linear infinite;
    will-change: left;
  }

  .cloud2 {
    position: absolute;
    top: 80px;
    font-size: 3rem;
    z-index: 1;
    pointer-events: none;
    animation: cloudDrift2 26s linear infinite 6s;
    -webkit-animation: cloudDrift2 26s linear infinite 6s;
    will-change: left;
  }
`;
