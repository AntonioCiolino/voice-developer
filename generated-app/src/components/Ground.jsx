import { GROUND_ITEMS, FERN_ITEMS } from "../constants";

export default function Ground() {
  return (
    <>
      {/* Fern layer — behind animals */}
      <div style={{ position: "absolute", width: "100%", bottom: 0, zIndex: 2, pointerEvents: "none" }}>
        {FERN_ITEMS.filter((f) => f.zIndex === 2).map((fern) => (
          <span
            key={fern.id}
            className="fern"
            style={{
              position: "absolute",
              left: fern.left,
              bottom: fern.bottom,
              fontSize: `${fern.size}rem`,
              animationDelay: fern.swayDelay,
              animationDuration: fern.swayDuration,
            }}
          >
            🌿
          </span>
        ))}
      </div>

      {/* Main ground strip */}
      <div
        style={{
          width: "100%",
          height: "120px",
          backgroundColor: "#5a9e3a",
          position: "relative",
          zIndex: 3,
          display: "flex",
          alignItems: "flex-start",
          paddingTop: "4px",
          overflow: "hidden",
        }}
      >
        {GROUND_ITEMS.map((item) =>
          item.isFlower ? (
            <span
              key={item.id}
              className="flower"
              style={{
                fontSize: "1.5rem",
                animationDelay: item.swayDelay,
                marginRight: "8px",
              }}
            >
              🌸
            </span>
          ) : (
            <span
              key={item.id}
              className="grass-blade"
              style={{ animationDelay: item.swayDelay, marginRight: "4px" }}
            >
              🌱
            </span>
          )
        )}
      </div>

      {/* Fern layer — in front of animals */}
      <div style={{ position: "absolute", width: "100%", bottom: 0, zIndex: 7, pointerEvents: "none" }}>
        {FERN_ITEMS.filter((f) => f.zIndex === 4).map((fern) => (
          <span
            key={fern.id}
            className="fern"
            style={{
              position: "absolute",
              left: fern.left,
              bottom: fern.bottom,
              fontSize: `${fern.size}rem`,
              animationDelay: fern.swayDelay,
              animationDuration: fern.swayDuration,
            }}
          >
            🌿
          </span>
        ))}
      </div>
    </>
  );
}
