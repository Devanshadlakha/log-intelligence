import { Link, useLocation } from "react-router-dom"

const NAV = [
  { to: "/", label: "Dashboard" },
  { to: "/settings", label: "Settings" },
]

export default function Sidebar() {
  const { pathname } = useLocation()

  return (
    <aside className="hidden md:flex fixed left-0 top-0 h-screen w-52 bg-dark-400 border-r border-dark-50 flex-col">
      <div className="px-5 py-4 border-b border-dark-50">
        <h1 className="text-base font-bold text-white">Log Intelligence</h1>
        <p className="text-[11px] text-gray-400 mt-0.5">AI-powered log analysis</p>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV.map((item) => {
          const active = pathname === item.to
          return (
            <Link
              key={item.to}
              to={item.to}
              className={`block px-3 py-2 rounded text-sm transition-colors ${
                active
                  ? "bg-dark-50 text-white"
                  : "text-gray-300 hover:bg-dark-50 hover:text-white"
              }`}
            >
              {item.label}
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}
