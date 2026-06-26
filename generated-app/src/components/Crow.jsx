import { forwardRef } from "react";

const Crow = forwardRef(function Crow({ visible, onClick }, ref) {
  if (!visible) return null;
  return (
    <div className="crow" ref={ref} onClick={onClick} title="Click me!">
      🐦
    </div>
  );
});

export default Crow;
