import { Navigate } from "react-router-dom"

export default function ProtectedRoute({ children }) {
  const token = localStorage.getItem("token")
  const isAuthenticated = localStorage.getItem("isAuthenticated") === "true"
  const role = localStorage.getItem("userRole")

  // Require token, auth flag, and role
  if (!token || !isAuthenticated || !role) {
    return <Navigate to="/login" replace />
  }

  return children
}
