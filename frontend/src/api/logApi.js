import axios from "axios"

// In production (Docker), env vars are empty → uses relative URLs → nginx proxies
// In local dev, env vars point to localhost ports
const AI_SERVICE_URL = import.meta.env.VITE_AI_SERVICE_URL || ""
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || ""

// ─── Auth helpers ──────────────────────────────────────────────

function getAuthHeader() {
  const token = localStorage.getItem("token")
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/**
 * Returns the user's role from localStorage.
 */
export function getUserRole() {
  return localStorage.getItem("userRole") || "BASIC_USER"
}

/**
 * Returns the allowed source categories for the current user.
 */
export function getAllowedSources() {
  try {
    return JSON.parse(localStorage.getItem("allowedSources") || "[]")
  } catch {
    return []
  }
}

/**
 * Axios interceptor — redirect to login on 401, show error on 403.
 */
axios.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid — force re-login
      localStorage.removeItem("token")
      localStorage.removeItem("isAuthenticated")
      localStorage.removeItem("userRole")
      localStorage.removeItem("allowedSources")
      window.location.href = "/login"
    }
    return Promise.reject(error)
  }
)

/**
 * Register a new user with a role.
 * Returns: { token, email, name, role, allowedSources, message }
 */
export async function register(email, password, name = "", role = "BASIC_USER") {
  const response = await axios.post(`${BACKEND_URL}/api/auth/register`, {
    email, password, name, role,
  })
  return response.data
}

/**
 * Login with existing credentials.
 * Returns: { token, email, name, role, allowedSources, message }
 */
export async function login(email, password) {
  const response = await axios.post(`${BACKEND_URL}/api/auth/login`, {
    email, password,
  })
  return response.data
}

/**
 * Validate the current token.
 * Returns: { email, name, role, allowedSources }
 */
export async function getMe() {
  const response = await axios.get(`${BACKEND_URL}/api/auth/me`, {
    headers: getAuthHeader(),
    timeout: 5000,
  })
  return response.data
}

/**
 * Fetch available roles.
 * Returns: { roles: [{ role, allowedSources }, ...] }
 */
export async function fetchRoles() {
  const response = await axios.get(`${BACKEND_URL}/api/auth/roles`, {
    timeout: 5000,
  })
  return response.data
}

// ─── Log API ───────────────────────────────────────────────────

/**
 * Sends a natural language query to the Python AI service.
 * The JWT is forwarded so the AI service can pass it to the backend
 * for RBAC-filtered log retrieval.
 */
export async function analyzeQuery(query, timeRange = "24", source = null) {
  const payload = {
    query,
    timeRange,
  }
  if (source) {
    payload.source = source
  }
  const response = await axios.post(`${AI_SERVICE_URL}/analyze`, payload, {
    headers: getAuthHeader(),
  })
  return response.data
}

/**
 * Fetches log counts per service from the backend (RBAC-filtered).
 */
export async function fetchStats(hoursAgo = 168) {
  const response = await axios.get(`${BACKEND_URL}/api/logs/stats`, {
    params: { hoursAgo },
    headers: getAuthHeader(),
    timeout: 10000,
  })
  return response.data.stats || []
}

/**
 * Fetches distinct service names from the backend (RBAC-filtered).
 */
export async function fetchServices() {
  const response = await axios.get(`${BACKEND_URL}/api/logs/services`, {
    headers: getAuthHeader(),
    timeout: 10000,
  })
  return response.data.services || []
}
