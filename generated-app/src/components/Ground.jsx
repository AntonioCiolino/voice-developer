import { GROUND_ITEMS } from "../constants";

export default function Ground() {
  return (
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