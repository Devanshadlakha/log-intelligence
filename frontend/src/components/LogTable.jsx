import { useState, useEffect } from "react"

const LEVEL_STYLES = {
  ERROR: "bg-red-500/20 text-red-400 border border-red-500/30",
  WARN:  "bg-amber-500/20 text-amber-400 border border-amber-500/30",
  INFO:  "bg-blue-500/20 text-blue-400 border border-blue-500/30",
}

export default function LogTable({ logs }) {
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(() => parseInt(localStorage.getItem("logsPerPage") || "20", 10))

  useEffect(() => {
    const onSettingsChanged = () => {
      const newSize = parseInt(localStorage.getItem("logsPerPage") || "20", 10)
      setPageSize(newSize)
      setPage(0)
    }
    window.addEventListener("settingsChanged", onSettingsChanged)
    return () => window.removeEventListener("settingsChanged", onSettingsChanged)
  }, [])

  const totalPages = Math.ceil(logs.length / pageSize)
  const paginated = logs.slice(page * pageSize, (page + 1) * pageSize)

  if (!logs.length) return null

  const formatTime = (ts) => {
    if (!ts) return "-"
    return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
  }

  return (
    <div className="card-dark overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 sm:px-5 py-3 border-b border-dark-50">
        <h2 className="text-sm font-semibold text-white">Log Results</h2>
        <div className="flex items-center gap-3">
          <span className="text-xs text-navy-400">{logs.length} entries</span>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[600px]">
          <thead>
            <tr className="border-b border-dark-50 bg-dark-300">
              <th className="text-left px-5 py-3 text-navy-400 font-medium text-xs uppercase tracking-wider">
                Timestamp
              </th>
              <th className="text-left px-5 py-3 text-navy-400 font-medium text-xs uppercase tracking-wider">
                Service
              </th>
              <th className="text-left px-5 py-3 text-navy-400 font-medium text-xs uppercase tracking-wider">
                Level
              </th>
              <th className="text-left px-5 py-3 text-navy-400 font-medium text-xs uppercase tracking-wider">
                Message
              </th>
            </tr>
          </thead>
          <tbody>
            {paginated.map((log, i) => (
              <tr
                key={log.id || i}
                className="border-b border-dark-50/50 hover:bg-dark-50/30 transition-colors"
              >
                <td className="px-5 py-3 text-navy-300 text-xs whitespace-nowrap font-mono">
                  {formatTime(log.timestamp)}
                </td>
                <td className="px-5 py-3 text-navy-200 text-xs whitespace-nowrap">
                  {log.service}
                </td>
                <td className="px-5 py-3">
                  <span
                    className={`text-xs px-2.5 py-1 rounded font-bold uppercase ${
                      LEVEL_STYLES[log.level] || LEVEL_STYLES.INFO
                    }`}
                  >
                    {log.level}
                  </span>
                </td>
                <td className="px-5 py-3 text-navy-300 text-xs max-w-xl truncate">
                  {log.message}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-end gap-1 px-3 sm:px-5 py-3 border-t border-dark-50">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="px-2 py-1 text-xs text-navy-300 hover:text-white disabled:opacity-30 transition-colors"
          >
            &lt;
          </button>
          {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
            const pageNum = page < 3 ? i : page - 2 + i
            if (pageNum >= totalPages) return null
            return (
              <button
                key={pageNum}
                onClick={() => setPage(pageNum)}
                className={`w-7 h-7 rounded text-xs font-medium transition-colors ${
                  pageNum === page
                    ? "bg-brand-blue text-white"
                    : "text-navy-300 hover:text-white hover:bg-dark-50"
                }`}
              >
                {pageNum + 1}
              </button>
            )
          })}
          <button
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page === totalPages - 1}
            className="px-2 py-1 text-xs text-navy-300 hover:text-white disabled:opacity-30 transition-colors"
          >
            Next &gt;
          </button>
        </div>
      )}
    </div>
  )
}
