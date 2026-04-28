import { useNavigate, Link } from "react-router-dom"

export default function Navbar() {
  const navigate = useNavigate()

  const handleLogout = () => {
    localStorage.removeItem("isAuthenticated")
    localStorage.removeItem("userEmail")
    navigate("/login")
  }

  const email = localStorage.getItem("userEmail") || ""

  return (
    <nav className="w-full bg-beige-100 rounded-full px-8 py-3 flex items-center justify-between card-shadow">
      <Link to="/" className="text-gradient text-xl font-bold tracking-tight">
        LOG INTELLIGENCE
      </Link>

      <div className="flex items-center gap-6">
        <Link
          to="/"
          className="text-sm text-navy-400 hover:text-navy-700 transition-colors font-medium"
        >
          Dashboard
        </Link>

        <div className="flex items-center gap-3">
          <span className="text-xs text-navy-300">{email}</span>
          <button
            onClick={handleLogout}
            className="text-sm text-navy-400 hover:text-red-500 transition-colors font-medium"
          >
            Logout
          </button>
        </div>
      </div>
    </nav>
  )
}
