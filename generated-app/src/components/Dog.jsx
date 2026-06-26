import { forwardRef } from "react";

const Dog = forwardRef(function Dog({ onClick, barking }, ref) {
  return (
    <>
      <div className="dog" ref={ref} onClick={onClick} title="Click me!">
        🐶
      </div>
      {barking && (
        <div className="bark-bubble" style={{ left: "60%" }}>
          Woof! 🐾
        </div>
      )}
    </>
  );
});

export default Dog;
