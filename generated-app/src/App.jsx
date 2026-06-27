import { useState } from "react";
import Sidebar from "./components/Sidebar";
import TopBar from "./components/TopBar";
import ViewOne from "./components/ViewOne";
import ViewTwo from "./components/ViewTwo";
import ViewThree from "./components/ViewThree";
import ViewSpecial from "./components/ViewSpecial";
import { useClickCount } from "./hooks/useClickCount";

export default function App() {
  const [activeView, setActiveView] = useState("one");
  const { count, increment } = useClickCount();

  const viewTitles = {
    one: "Text Document",
    two: "3D Cube",
    three: "Animal Parade",
    special: "Special Page",
  };

  return (
    <div className="flex flex-col h-screen bg-gray-100 font-sans overflow-hidden">
      {/* Top Bar */}
      <TopBar title={viewTitles[activeView]} count={count} onCountClick={increment} />

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <Sidebar activeView={activeView} setActiveView={setActiveView} />

        {/* Main Content */}
        <main className="flex-1 overflow-auto bg-gray-200 p-6">
          <div className="h-full">
            {activeView === "one" && <ViewOne />}
            {activeView === "two" && <ViewTwo />}
            {activeView === "three" && <ViewThree />}
            {activeView === "special" && <ViewSpecial />}
          </div>
        </main>
      </div>
    </div>
  );
}
