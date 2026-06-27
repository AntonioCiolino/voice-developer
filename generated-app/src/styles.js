export const styles = `
  /* Full-height fix for iOS Safari — avoids the 100vh browser-chrome bug */
  html, body, #root {
    height: 100%;
    margin: 0;
    padding: 0;
  }

  .app-root {
    min-height: 100%;
    min-height: -webkit-fill-available;
  }

  @keyframes catRun {
    0%   { left: 110%; }
    100% { left: -150px; }
  }
  @-webkit-keyframes catRun {
    0%   { left: 110%; }
    100% { left: -150px; }
  }

  @keyframes dogRun {
    0%   { left: 110%; }
    100% { left: -150px; }
  }
  @-webkit-keyframes dogRun {
    0%   { left: 110%; }
    100% { left: -150px; }
  }

  @keyframes bounce {
    0%, 100% { transform: translateY(0) scaleX(-1); }
    50%       { transform: translateY(-18px) scaleX(-1); }
  }
  @-webkit-keyframes bounce {
    0%, 100% { -webkit-transform: translateY(0) scaleX(-1); }
    50%       { -webkit-transform: translateY(-18px) scaleX(-1); }
  }

  @keyframes bounceDog {
    0%, 100% { transform: translateY(0) scaleX(-1); }
    50%       { transform: translateY(-14px) scaleX(-1); }
  }
  @-webkit-keyframes bounceDog {
    0%, 100% { -webkit-transform: translateY(0) scaleX(-1); }
    50%       { -webkit-transform: translateY(-14px) scaleX(-1); }
  }

  @keyframes grassSway {
    0%, 100% { transform: rotate(-3deg); }
    50%       { transform: rotate(3deg); }
  }
  @-webkit-keyframes grassSway {
    0%, 100% { -webkit-transform: rotate(-3deg); }
    50%       { -webkit-transform: rotate(3deg); }
  }

  @keyframes flowerSway {
    0%, 100% { transform: rotate(-3deg); }
    50%       { transform: rotate(3deg); }
  }
  @-webkit-keyframes flowerSway {
    0%, 100% { -webkit-transform: rotate(-3deg); }
    50%       { -webkit-transform: rotate(3deg); }
  }

  @keyframes fernSway {
    0%   { transform: rotate(-4deg) scaleX(1); }
    50%  { transform: rotate(4deg) scaleX(1); }
    100% { transform: rotate(-4deg) scaleX(1); }
  }
  @-webkit-keyframes fernSway {
    0%   { -webkit-transform: rotate(-4deg) scaleX(1); }
    50%  { -webkit-transform: rotate(4deg) scaleX(1); }
    100% { -webkit-transform: rotate(-4deg) scaleX(1); }
  }

  @keyframes pawPrint {
    0%   { opacity: 0; transform: scale(0.5); }
    20%  { opacity: 1; transform: scale(1.1); }
    80%  { opacity: 1; transform: scale(1); }
    100% { opacity: 0; transform: scale(0.8); }
  }
  @-webkit-keyframes pawPrint {
    0%   { opacity: 0; -webkit-transform: scale(0.5); }
    20%  { opacity: 1; -webkit-transform: scale(1.1); }
    80%  { opacity: 1; -webkit-transform: scale(1); }
    100% { opacity: 0; -webkit-transform: scale(0.8); }
  }

  @keyframes explode {
    0%   { opacity: 1; transform: translate(0, 0) scale(1); }
    100% { opacity: 0; transform: translate(var(--tx), var(--ty)) scale(0.3); }
  }
  @-webkit-keyframes explode {
    0%   { opacity: 1; -webkit-transform: translate(0, 0) scale(1); }
    100% { opacity: 0; -webkit-transform: translate(var(--tx), var(--ty)) scale(0.3); }
  }

  @keyframes barkBounce {
    0%, 100% { transform: translateY(0); }
    50%       { transform: translateY(-6px); }
  }
  @-webkit-keyframes barkBounce {
    0%, 100% { -webkit-transform: translateY(0); }
    50%       { -webkit-transform: translateY(-6px); }
  }

  @keyframes cloudDrift1 {
    0%   { left: -120px; }
    100% { left: 110%; }
  }
  @-webkit-keyframes cloudDrift1 {
    0%   { left: -120px; }
    100% { left: 110%; }
  }

  @keyframes cloudDrift2 {
    0%   { left: -120px; }
    100% { left: 110%; }
  }
  @-webkit-keyframes cloudDrift2 {
    0%   { left: -120px; }
    100% { left: 110%; }
  }

  @keyframes cubeRotate {
    0%   { transform: rotateX(0deg)   rotateY(0deg)   rotateZ(0deg); }
    25%  { transform: rotateX(90deg)  rotateY(180deg) rotateZ(45deg); }
    50%  { transform: rotateX(180deg) rotateY(360deg) rotateZ(90deg); }
    75%  { transform: rotateX(270deg) rotateY(180deg) rotateZ(135deg); }
    100% { transform: rotateX(360deg) rotateY(360deg) rotateZ(180deg); }
  }
  @-webkit-keyframes cubeRotate {
    0%   { -webkit-transform: rotateX(0deg)   rotateY(0deg)   rotateZ(0deg); }
    25%  { -webkit-transform: rotateX(90deg)  rotateY(180deg) rotateZ(45deg); }
    50%  { -webkit-transform: rotateX(180deg) rotateY(360deg) rotateZ(90deg); }
    75%  { -webkit-transform: rotateX(270deg) rotateY(180deg) rotateZ(135deg); }
    100% { -webkit-transform: rotateX(360deg) rotateY(360deg) rotateZ(180deg); }
  }

  .cube {
    width: 100px;
    height: 100px;
    position: relative;
    transform-style: preserve-3d;
    -webkit-transform-style: preserve-3d;
    animation: cubeRotate 5s cubic-bezier(0.45, 0.05, 0.55, 0.95) infinite;
    -webkit-animation: cubeRotate 5s cubic-bezier(0.45, 0.05, 0.55, 0.95) infinite;
  }

  .cube-face {
    position: absolute;
    width: 100px;
    height: 100px;
    border: 2px solid rgba(255, 255, 255, 0.9);
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2.2rem;
    backdrop-filter: blur(4px);
    -webkit-backdrop-filter: blur(4px);
    box-shadow:
      inset 0 0 20px rgba(255, 255, 255, 0.25),
      0 0 10px rgba(0, 0, 0, 0.2);
  }

  .cube-front  {
    transform: translateZ(50px);
    background: rgba(99, 179, 237, 0.55);
  }
  .cube-back   {
    transform: rotateY(180deg) translateZ(50px);
    background: rgba(252, 129, 74, 0.55);
  }
  .cube-left   {
    transform: rotateY(-90deg) translateZ(50px);
    background: rgba(154, 230, 180, 0.55);
  }
  .cube-right  {
    transform: rotateY(90deg) translateZ(50px);
    background: rgba(246, 173, 85, 0.55);
  }
  .cube-top    {
    transform: rotateX(90deg) translateZ(50px);
    background: rgba(183, 148, 246, 0.55);
  }
  .cube-bottom {
    transform: rotateX(-90deg) translateZ(50px);
    background: rgba(252, 129, 129, 0.55);
  }

  .cat {
    position: absolute;
    bottom: 130px;
    font-size: 4rem;
    cursor: pointer;
    z-index: 10;
    user-select: none;
    -webkit-user-select: none;
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
    -webkit-user-select: none;
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
    -webkit-user-select: none;
    -webkit-tap-highlight-color: transparent;
    touch-action: manipulation;
  }

  .grass-blade {
    display: inline-block;
    font-size: 1.5rem;
    animation: grassSway 1.2s ease-in-out infinite;
    -webkit-animation: grassSway 1.2s ease-in-out infinite;
    transform-origin: bottom center;
    -webkit-transform-origin: bottom center;
    will-change: transform;
  }

  .flower {
    display: inline-block;
    font-size: 1.5rem;
    animation: flowerSway 1.5s ease-in-out infinite;
    -webkit-animation: flowerSway 1.5s ease-in-out infinite;
    transform-origin: bottom center;
    -webkit-transform-origin: bottom center;
    will-change: transform;
  }

  .fern {
    display: inline-block;
    animation: fernSway 1.8s ease-in-out infinite;
    -webkit-animation: fernSway 1.8s ease-in-out infinite;
    transform-origin: bottom center;
    -webkit-transform-origin: bottom center;
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
  }

  .cloud1 {
    position: absolute;
    font-size: 3.5rem;
    top: 40px;
    animation: cloudDrift1 18s linear infinite;
    -webkit-animation: cloudDrift1 18s linear infinite;
    z-index: 1;
    pointer-events: none;
    user-select: none;
  }

  .cloud2 {
    position: absolute;
    font-size: 2.5rem;
    top: 80px;
    animation: cloudDrift2 26s linear infinite 6s;
    -webkit-animation: cloudDrift2 26s linear infinite 6s;
    z-index: 1;
    pointer-events: none;
    user-select: none;
  }
`;
