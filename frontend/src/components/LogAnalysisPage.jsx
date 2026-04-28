import { useState } from "react"
import { useParams, Link, Navigate } from "react-router-dom"
import SearchBar from "./SearchBar"
import TimeRangeDropdown from "./TimeRangeDropdown"
import LogTable from "./LogTable"
import RootCauseSummary from "./RootCauseSummary"
import ClusterList from "./ClusterList"
import ErrorFrequencyChart from "./ErrorFrequencyChart"
import AnomalyAlert from "./AnomalyAlert"
import { analyzeQuery, getAllowedSources } from "../api/logApi"

// Source metadata for display
const SOURCE_META = {
  system:    { title: "System Logs",    icon: "\uD83D\uDDA5\uFE0F" },
  file:      { title: "File Logs",      icon: "\uD83D\uDCC4" },
  database:  { title: "Database Logs",  icon: "\uD83D\uDDC4\uFE0F" },
  docker:    { title: "Docker Logs",    icon: "\uD83D\uDC33" },
  github:    { title: "GitHub Actions", icon: "\u2699\uFE0F" },
  webserver: { title: "Web Server",     icon: "\uD83C\uDF10" },
}

export default function LogAnalysisPage() {
  const { source } = useParams()
  const meta = SOURCE_META[source] || { title: source, icon: "\uD83D\uDCCB" }
  const allowedSources = getAllowedSources()

  const [query, setQuery] = useState("")
  const [timeRange, setTimeRange] = useState("24")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [results, setResults] = useState(null)

  // If the user navigates to a source they don't have access to, redirect to dashboard
  if (!allowedSources.includes(source)) {
    return <Navigate to="/" replace />
  }

  const handleSearch = async () => {
    if (!query.trim()) return

    setLoading(true)
    setError(null)
    setResults(null)

    try {
      const data = await analyzeQuery(query, timeRange, source)
      setResults(data)
    } catch (err) {
      if (err.response?.status === 403) {
        setError("Access denied. Your role does not have permission to view these logs.")
      } else {
        setError(err.message || "Something went wrong. Is the AI service running?")
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="animate-fade-in">
      {/* Back + Title */}
      <div className="mb-4 sm:mb-6">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-xs text-navy-400 hover:text-brand-blue transition-colors mb-3"
        >
          <span>&larr;</span> Back to Dashboard
        </Link>

        <div className="flex items-center gap-3">
          <span className="text-2xl sm:text-3xl">{meta.icon}</span>
          <div>
            <h1 className="text-lg sm:text-xl font-bold text-white">{meta.title}</h1>
            <p className="text-navy-400 text-xs">Search and analyze logs from this source</p>
          </div>
        </div>
      </div>

      {/* Search Section */}
      <div className="flex gap-3 flex-col sm:flex-row mb-6">
        <SearchBar
          value={query}
          onChange={setQuery}
          onSearch={handleSearch}
          loading={loading}
        />
        <TimeRangeDropdown value={timeRange} onChange={setTimeRange} />
        <button
          onClick={handleSearch}
          disabled={loading || !query.trim()}
          className="primary-button whitespace-nowrap"
        >
          {loading ? "Analyzing..." : "Search"}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center gap-3 text-navy-300 text-sm py-16 justify-center">
          <div className="w-5 h-5 border-2 border-brand-blue border-t-transparent rounded-full animate-spin" />
          Parsing query, fetching logs, clustering, generating summary...
        </div>
      )}

      {/* Results */}
      {results && !loading && (
        <div className="space-y-5">
          {/* Anomaly Alert — shown first if spike detected */}
          <AnomalyAlert anomaly={results.anomaly} />

          {/* Root Cause / AI Answer / Report */}
          {results.summary && (
            <RootCauseSummary summary={results.summary} intent={results.intent} />
          )}

          {/* Chart + Clusters side by side */}
          {(results.metrics?.time_series?.length > 0 || results.clusters?.length > 0) && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              {results.metrics?.time_series?.length > 0 && (
                <ErrorFrequencyChart data={results.metrics.time_series} />
              )}
              {results.clusters?.length > 0 && (
                <ClusterList clusters={results.clusters} />
              )}
            </div>
          )}

          {/* Log Table */}
          <LogTable logs={results.logs || []} />
        </div>
      )}

      {/* Empty state */}
      {!results && !loading && !error && (
        <div className="text-center py-20">
          <div className="text-5xl mb-4 opacity-40">{meta.icon}</div>
          <p className="text-sm text-navy-300">Enter a query to start analyzing {meta.title.toLowerCase()}</p>
          <p className="text-xs mt-2 text-navy-400">
            Try: "show all errors" | "what's causing issues?" | "generate a summary report"
          </p>
        </div>
      )}
    </div>
  )
}
