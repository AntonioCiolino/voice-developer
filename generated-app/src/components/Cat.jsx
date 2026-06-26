import { forwardRef } from "react";

const Cat = forwardRef(function Cat({ catStyle, catLeaping, onClick }, ref) {
  if (catStyle) {
    return (
      <div ref={ref} style={catStyle} onClick={onClick}>
        {catLeaping ? "😸" : "🐱"}
      </div>
    );
  }

  return (
    <div className="cat" ref={ref} onClick={onClick} title="Click me!">
      🐱
    </div>
  );
});

export default Cat;
