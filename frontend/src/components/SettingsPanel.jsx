import { useEffect, useState } from "react"
import { getMe } from "../api/logApi"

export default function SettingsPanel() {
  const [user, setUser] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    getMe()
      .then(setUser)
      .catch((e) => setError(e?.response?.data?.message || "Failed to load user"))
  }, [])

  return (
    <div className="max-w-2xl">
      <h2 className="text-xl font-semibold text-white">Settings</h2>
      <p className="text-sm text-gray-400 mt-1">
        Account details and access summary.
      </p>

      <div className="mt-6 rounded border border-dark-50 bg-dark-400 p-5">
        {error && <p className="text-sm text-red-400">{error}</p>}

        {!error && !user && (
          <p className="text-sm text-gray-400">Loading...</p>
        )}

        {user && (
          <dl className="space-y-3 text-sm">
            <Row label="Name" value={user.name || "—"} />
            <Row label="Email" value={user.email} />
            <Row label="Role" value={user.role} />
            <Row
              label="Allowed sources"
              value={(user.allowedSources || []).join(", ") || "all"}
            />
          </dl>
        )}
      </div>
    </div>
  )
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between gap-6">
      <dt className="text-gray-400">{label}</dt>
      <dd className="text-white text-right break-all">{value}</dd>
    </div>
  )
}
