import { Routes, Route, Navigate, useLocation } from "react-router-dom"
import AuthPage from "./components/AuthPage"
import Dashboard from "./components/Dashboard"
import LogAnalysisPage from "./components/LogAnalysisPage"
import SettingsPanel from "./components/SettingsPanel"
import ProtectedRoute from "./components/ProtectedRoute"
import Sidebar from "./components/Sidebar"
import StatusBar from "./components/StatusBar"

function AppLayout({ children }) {
  return (
    <div className="min-h-screen bg-dark-500">
      <Sidebar />
      {/* Main content area — offset by sidebar on md+ */}
      <div className="md:ml-52">
        {/* Top status bar */}
        <header className="h-12 bg-dark-400 border-b border-dark-50 flex items-center justify-between px-4 sm:px-6">
          <h2 className="text-xs sm:text-sm font-semibold text-white truncate mr-4 pl-10 md:pl-0">
            AI-Powered Log Intelligence Dashboard
          </h2>
          <StatusBar />
        </header>
        <main className="p-3 sm:p-4 md:p-6">{children}</main>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<AuthPage />} />

      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AppLayout>
              <Dashboard />
            </AppLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/logs/:source"
        element={
          <ProtectedRoute>
            <AppLayout>
              <LogAnalysisPage />
            </AppLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <AppLayout>
              <SettingsPanel />
            </AppLayout>
          </ProtectedRoute>
        }
      />

      {/* Catch-all redirect */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
