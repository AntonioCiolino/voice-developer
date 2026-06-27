const NAV_ITEMS = [
  { id: "one", label: "One", icon: "📄", description: "Text Document" },
  { id: "two", label: "Two", icon: "🎲", description: "3D Cube" },
  { id: "three", label: "Three", icon: "🐾", description: "Animal Parade" },
  { id: "special", label: "Special", icon: "🎉", description: "Secret Page" },
];

export default function Sidebar({ activeView, setActiveView }) {
  return (
    <aside className="w-56 bg-gray-900 text-white flex flex-col shadow-xl z-10 flex-shrink-0">
      <div className="px-4 py-5 border-b border-gray-700">
        <p className="text-xs font-semibold uppercase tracking-widest text-gray-400">Navigation</p>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV_ITEMS.map((item) => {
          const isActive = activeView === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveView(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-3 rounded-lg text-left transition-all duration-150 group
                ${isActive
                  ? "bg-blue-600 text-white shadow-md"
                  : "text-gray-300 hover:bg-gray-700 hover:text-white"
                }`}
            >
              <span className="text-xl">{item.icon}</span>
              <div>
                <div className={`font-semibold text-sm ${isActive ? "text-white" : "text-gray-200"}`}>
                  {item.label}
                </div>
                <div className={`text-xs ${isActive ? "text-blue-200" : "text-gray-500"}`}>
                  {item.description}
                </div>
              </div>
              {isActive && (
                <div className="ml-auto w-1.5 h-1.5 rounded-full bg-white opacity-80" />
              )}
            </button>
          );
        })}
      </nav>

      <div className="px-4 py-4 border-t border-gray-700">
        <p className="text-xs text-gray-500 text-center">v1.0.0</p>
      </div>
    </aside>
  );
}
