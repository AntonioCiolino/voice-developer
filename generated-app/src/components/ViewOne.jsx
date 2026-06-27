export default function ViewOne() {
  return (
    <div className="max-w-3xl mx-auto">
      <div className="bg-white rounded-2xl shadow-lg overflow-hidden">
        {/* Document toolbar */}
        <div className="flex items-center gap-2 px-6 py-3 bg-gray-50 border-b border-gray-200">
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-400" />
            <div className="w-3 h-3 rounded-full bg-yellow-400" />
            <div className="w-3 h-3 rounded-full bg-green-400" />
          </div>
          <span className="ml-3 text-xs text-gray-400 font-medium">document.txt</span>
        </div>

        {/* Document content */}
        <div className="px-10 py-10 font-serif">
          <h1 className="text-3xl font-bold text-gray-800 mb-2 tracking-tight">
            Welcome to MyApp
          </h1>
          <p className="text-xs text-gray-400 mb-8 uppercase tracking-widest">
            Created: January 2025 · 3 min read
          </p>

          <p className="text-gray-700 leading-relaxed mb-5 text-base">
            This is a polished React application featuring a sidebar navigation, a top menu bar,
            and three distinct views. Each view demonstrates a different capability of the app —
            from rich text documents to interactive 3D graphics and delightful animations.
          </p>

          <h2 className="text-xl font-bold text-gray-800 mt-8 mb-3">Features</h2>
          <ul className="space-y-2 mb-6">
            {[
              "📄 View One — A clean, readable text document layout",
              "🎲 View Two — A spinning 3D CSS cube with colourful faces",
              "🐾 View Three — Cute scrolling animals with animations",
              "🔴 Click counter — Persisted to localStorage automatically",
              "🎨 Tailwind CSS — Fully responsive and polished UI",
            ].map((item) => (
              <li key={item} className="flex items-start gap-2 text-gray-700 text-sm leading-relaxed">
                <span className="mt-0.5">{item.split(" — ")[0].slice(-2)}</span>
                <span>
                  <strong>{item.split(" — ")[0].slice(2).trim()}</strong>
                  {" — "}
                  {item.split(" — ")[1]}
                </span>
              </li>
            ))}
          </ul>

          <h2 className="text-xl font-bold text-gray-800 mt-8 mb-3">Getting Started</h2>
          <p className="text-gray-700 leading-relaxed mb-4 text-base">
            Use the sidebar on the left to switch between views. The red button in the top bar
            counts your clicks and saves the total automatically — even if you refresh the page,
            your count will be right where you left it.
          </p>

          <blockquote className="border-l-4 border-blue-400 pl-5 py-2 my-6 bg-blue-50 rounded-r-lg">
            <p className="text-blue-800 italic text-sm leading-relaxed">
              "Good software is a joy to use — clean, fast, and delightful in the details."
            </p>
          </blockquote>

          <p className="text-gray-700 leading-relaxed text-base">
            Navigate to <strong>View Two</strong> to see a hardware-accelerated 3D cube, or jump
            to <strong>View Three</strong> for a fun animated animal parade. Enjoy exploring!
          </p>

          <div className="mt-10 pt-6 border-t border-gray-100 flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white text-sm font-bold">
              A
            </div>
            <div>
              <p className="text-sm font-semibold text-gray-700">Author</p>
              <p className="text-xs text-gray-400">MyApp Team</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
