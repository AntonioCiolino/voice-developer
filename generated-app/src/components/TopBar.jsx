export default function TopBar({ title, count, onCountClick }) {
  return (
    <header className="flex items-center justify-between bg-gray-900 text-white px-6 py-3 shadow-lg z-20 flex-shrink-0">
      <div className="flex items-center gap-3">
        <span className="text-2xl">🐾</span>
        <span className="text-lg font-bold tracking-wide text-gray-100">MyApp</span>
        <span className="text-gray-500 mx-2">|</span>
        <span className="text-sm text-gray-300 font-medium">{title}</span>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 bg-gray-800 rounded-full px-4 py-1.5">
          <span className="text-xs text-gray-400 font-medium uppercase tracking-wider">Clicks</span>
          <span className="text-white font-bold text-sm min-w-[2rem] text-center">{count}</span>
        </div>
        <button
          onClick={onCountClick}
          className="bg-red-500 hover:bg-red-400 active:bg-red-600 active:scale-95 text-white font-bold px-5 py-1.5 rounded-full shadow-md transition-all duration-150 text-sm select-none"
        >
          Click Me!
        </button>
      </div>
    </header>
  );
}
