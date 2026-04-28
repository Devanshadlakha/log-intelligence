import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { login, register } from "../api/logApi"

const ROLES = [
  { value: "ADMIN", label: "Admin", desc: "Full access to all log sources" },
  { value: "DEVOPS", label: "DevOps Engineer", desc: "System, Docker, CI/CD, Web Server" },
  { value: "BACKEND_DEVELOPER", label: "Backend Developer", desc: "File Logs, Database Logs" },
  { value: "DATA_ANALYST", label: "Data Analyst", desc: "Database Logs" },
  { value: "SECURITY_ENGINEER", label: "Security Engineer", desc: "System, Web Server" },
  { value: "BASIC_USER", label: "Basic User", desc: "File Logs only" },
]

export default function AuthPage() {
  const [isLogin, setIsLogin] = useState(true)
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [name, setName] = useState("")
  const [role, setRole] = useState("BASIC_USER")
  const [error, setError] = useState("")
  const [success, setSuccess] = useState("")
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError("")

    if (!email.trim() || !password.trim()) {
      setError("Please fill in all fields")
      return
    }

    if (!isLogin) {
      if (password !== confirmPassword) {
        setError("Passwords do not match")
        return
      }
      if (password.length < 8) {
        setError("Password must be at least 8 characters long")
        return
      }
      if (!/[A-Z]/.test(password) || !/[a-z]/.test(password) || !/\d/.test(password)) {
        setError("Password must contain uppercase, lowercase, and a number")
        return
      }
    }

    setLoading(true)
    try {
      if (isLogin) {
        const data = await login(email, password)
        // Store JWT token, user info, role, and allowed sources
        localStorage.setItem("token", data.token)
        localStorage.setItem("isAuthenticated", "true")
        localStorage.setItem("userEmail", data.email)
        localStorage.setItem("userName", data.name || "")
        localStorage.setItem("userRole", data.role)
        localStorage.setItem("allowedSources", JSON.stringify(data.allowedSources || []))
        navigate("/")
      } else {
        await register(email, password, name, role)
        // After signup, switch to login tab so user logs in
        setSuccess("Account created successfully! Please log in.")
        setIsLogin(true)
        setPassword("")
        setConfirmPassword("")
        setName("")
        setRole("BASIC_USER")
      }
    } catch (err) {
      const message = err.response?.data?.error || "Something went wrong. Is the backend running?"
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-dark-500">
      <div className="w-full max-w-md mx-4">
        <div className="card-dark p-10">
          {/* Logo */}
          <div className="text-center mb-8">
            <div className="flex items-center justify-center mb-3">
              <img src="/logo.png" alt="Log Intelligence" className="w-14 h-14 rounded-lg" />
            </div>
            <h1 className="text-gradient text-2xl font-bold tracking-tight mb-1">
              Log Intelligence
            </h1>
            <p className="text-navy-400 text-sm">
              AI-Powered Real-Time Log Analysis
            </p>
          </div>

          {/* Toggle */}
          <div className="flex bg-dark-400 rounded-lg p-1 mb-8">
            <button
              onClick={() => { setIsLogin(true); setError(""); setSuccess("") }}
              className={`flex-1 py-2 text-sm font-medium rounded-md transition-all ${
                isLogin
                  ? "bg-dark-200 text-white shadow-sm"
                  : "text-navy-400 hover:text-navy-200"
              }`}
            >
              Log In
            </button>
            <button
              onClick={() => { setIsLogin(false); setError(""); setSuccess("") }}
              className={`flex-1 py-2 text-sm font-medium rounded-md transition-all ${
                !isLogin
                  ? "bg-dark-200 text-white shadow-sm"
                  : "text-navy-400 hover:text-navy-200"
              }`}
            >
              Sign Up
            </button>
          </div>

          {/* Success */}
          {success && (
            <div className="mb-4 p-3 bg-green-500/10 border border-green-500/30 rounded-lg text-green-400 text-sm">
              {success}
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
              {error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {!isLogin && (
              <div>
                <label className="block text-sm font-medium text-navy-200 mb-1">
                  Full Name
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Your name"
                  className="w-full px-4 py-3 rounded-lg text-sm text-white bg-[#2a3040] border border-[#3a4055]
                             focus:outline-none focus:ring-1 focus:ring-brand-blue/30 focus:border-brand-blue
                             placeholder-[#8090b0]"
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-navy-200 mb-1">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full px-4 py-3 rounded-lg text-sm text-white bg-[#2a3040] border border-[#3a4055]
                           focus:outline-none focus:ring-1 focus:ring-brand-blue/30 focus:border-brand-blue
                           placeholder-[#8090b0]"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-navy-200 mb-1">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                className="w-full px-4 py-3 rounded-lg text-sm text-white bg-[#2a3040] border border-[#3a4055]
                           focus:outline-none focus:ring-1 focus:ring-brand-blue/30 focus:border-brand-blue
                           placeholder-[#8090b0]"
              />
              {!isLogin && (
                <p className="text-xs text-navy-500 mt-1">
                  Min 8 characters, with uppercase, lowercase, and a number
                </p>
              )}
            </div>

            {!isLogin && (
              <>
                <div>
                  <label className="block text-sm font-medium text-navy-200 mb-1">
                    Confirm Password
                  </label>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Confirm your password"
                    className="w-full px-4 py-3 rounded-lg text-sm text-white bg-[#2a3040] border border-[#3a4055]
                               focus:outline-none focus:ring-1 focus:ring-brand-blue/30 focus:border-brand-blue
                               placeholder-[#8090b0]"
                  />
                </div>

                {/* Role selector */}
                <div>
                  <label className="block text-sm font-medium text-navy-200 mb-1">
                    Role
                  </label>
                  <select
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    className="w-full px-4 py-3 rounded-lg text-sm text-white bg-[#2a3040] border border-[#3a4055]
                               focus:outline-none focus:ring-1 focus:ring-brand-blue/30 focus:border-brand-blue
                               appearance-none cursor-pointer"
                  >
                    {ROLES.map((r) => (
                      <option key={r.value} value={r.value}>
                        {r.label}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-navy-500 mt-1">
                    {ROLES.find(r => r.value === role)?.desc}
                  </p>
                </div>
              </>
            )}

            <button type="submit" disabled={loading} className="auth-button mt-2">
              {loading
                ? "Please wait..."
                : isLogin ? "Log In" : "Create Account"
              }
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
