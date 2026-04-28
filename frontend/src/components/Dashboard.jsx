import { useState, useEffect, useRef } from "react"
import { Client } from "@stomp/stompjs"
import SockJS from "sockjs-client/dist/sockjs"
import SourceCard from "./SourceCard"
import ProportionChart from "./ProportionChart"
import { fetchStats, getAllowedSources, getUserRole } from "../api/logApi"

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || ""

// Log source categories — maps to service name patterns in Kafka
const LOG_SOURCES = [
  {
    id: "system",
    title: "System Logs",
    description: "Windows Event Viewer logs from System, Application, and Security channels",
    icon: "\uD83D\uDDA5\uFE0F",
    servicePatterns: ["windows-event"],
  },
  {
    id: "file",
    title: "File Logs",
    description: "Application log files monitored in real-time via file watcher",
    icon: "\uD83D\uDCC4",
    servicePatterns: ["test-app", "file-"],
  },
  {
    id: "database",
    title: "Database Logs",
    description: "MariaDB, MySQL, and PostgreSQL query and error logs",
    icon: "\uD83D\uDDC4\uFE0F",
    servicePatterns: ["mariadb", "mysql", "postgresql"],
  },
  {
    id: "docker",
    title: "Docker Logs",
    description: "Real-time container logs from Docker Desktop",
    icon: "\uD83D\uDC33",
    servicePatterns: ["docker"],
  },
  {
    id: "github",
    title: "GitHub Actions",
    description: "CI/CD workflow run results and job status logs",
    icon: "\u2699\uFE0F",
    servicePatterns: ["github-actions"],
  },
  {
    id: "webserver",
    title: "Web Server",
    description: "Nginx and Apache HTTP access logs with status analysis",
    icon: "\uD83C\uDF10",
    servicePatterns: ["nginx", "apache"],
  },
]

// Role display names
const ROLE_LABELS = {
  ADMIN: "Admin",
  DEVOPS: "DevOps Engineer",
  BACKEND_DEVELOPER: "Backend Developer",
  DATA_ANALYST: "Data Analyst",
  SECURITY_ENGINEER: "Security Engineer",
  BASIC_USER: "Basic User",
}

export default function Dashboard() {
  const [stats, setStats] = useState([])
  const [sourceCounts, setSourceCounts] = useState({})
  const [chartData, setChartData] = useState([])
  const [liveLogs, setLiveLogs] = useState([])
  const [wsConnected, setWsConnected] = useState(false)
  const stompClient = useRef(null)

  const role = getUserRole()
  const allowedSources = getAllowedSources()

  // Filter before rendering — unauthorized cards never enter the DOM
  const visibleSources = LOG_SOURCES.filter((s) => allowedSources.includes(s.id))
  const cardCount = visibleSources.length

  // WebSocket connection for real-time log streaming
  useEffect(() => {
    const client = new Client({
      webSocketFactory: () => new SockJS(`${BACKEND_URL}/ws`),
      reconnectDelay: 5000,
      onConnect: () => {
        setWsConnected(true)
        client.subscribe("/topic/logs", (message) => {
          const log = JSON.parse(message.body)
          const isAllowed = visibleSources.some((source) =>
            source.servicePatterns.some(
              (pattern) => log.service?.startsWith(pattern) || log.service === pattern
            )
          )
          if (isAllowed) {
            setLiveLogs((prev) => [log, ...prev].slice(0, 50))
          }
        })
      },
      onDisconnect: () => setWsConnected(false),
      onStompError: () => setWsConnected(false),
    })

    client.activate()
    stompClient.current = client

    return () => {
      if (stompClient.current) {
        stompClient.current.deactivate()
      }
    }
  }, [])

  useEffect(() => {
    const getInterval = () => parseInt(localStorage.getItem("refreshInterval") || "30", 10) * 1000

    loadStats()
    let interval = setInterval(loadStats, getInterval())

    const onSettingsChanged = () => {
      clearInterval(interval)
      interval = setInterval(loadStats, getInterval())
    }

    window.addEventListener("settingsChanged", onSettingsChanged)
    return () => {
      clearInterval(interval)
      window.removeEventListener("settingsChanged", onSettingsChanged)
    }
  }, [])

  const loadStats = async () => {
    try {
      const data = await fetchStats(168)
      setStats(data)

      const counts = {}
      const chartEntries = []

      for (const source of visibleSources) {
        const matchingStats = data.filter((s) =>
          source.servicePatterns.some((pattern) =>
            s.service.startsWith(pattern) || s.service === pattern
          )
        )
        const total = matchingStats.reduce((sum, s) => sum + s.count, 0)
        counts[source.id] = total

        if (total > 0) {
          chartEntries.push({ category: source.title, count: total })
        }
      }

      const knownPatterns = visibleSources.flatMap((s) => s.servicePatterns)
      const otherStats = data.filter(
        (s) => !knownPatterns.some((p) => s.service.startsWith(p) || s.service === p)
      )
      const otherTotal = otherStats.reduce((sum, s) => sum + s.count, 0)
      if (otherTotal > 0) {
        chartEntries.push({ category: "Other Services", count: otherTotal })
      }

      setSourceCounts(counts)
      setChartData(chartEntries)
    } catch (err) {
      console.error("Failed to fetch stats:", err)
    }
  }

  // Build the card elements once (reused across layout branches)
  const cardElements = visibleSources.map((source, i) => (
    <div
      key={source.id}
      className="animate-fade-in"
      style={{ animationDelay: `${i * 80}ms` }}
    >
      <SourceCard
        source={{
          ...source,
          count: sourceCounts[source.id] ?? null,
        }}
      />
    </div>
  ))

  // ── Layout strategy based on card count ─────────────────────
  //
  // 4 cards (DEVOPS):
  //   Chart pinned left spanning 2 rows, 4 cards in 2×2 grid beside it.
  //   On mobile: stacks to single column.
  //
  //   [ Chart (row-span-2) ] [ Card 1 ] [ Card 2 ]
  //   [ Chart (continued)  ] [ Card 3 ] [ Card 4 ]
  //
  // 5–6 cards (ADMIN):
  //   Chart pinned left spanning 2 rows, 3 cards top-right, 3 cards bottom-right.
  //
  //   [ Chart (row-span-2) ] [ Card 1 ] [ Card 2 ] [ Card 3 ]
  //   [ Chart (continued)  ] [ Card 4 ] [ Card 5 ] [ Card 6 ]
  //
  // 4 cards (DEVOPS):
  //   Chart pinned left spanning 2 rows, 2×2 cards right.
  //
  //   [ Chart (row-span-2) ] [ Card 1 ] [ Card 2 ]
  //   [ Chart (continued)  ] [ Card 3 ] [ Card 4 ]
  //
  // 3 cards:
  //   Chart left row-span-2, 2 cards right + 1 spanning below.
  //
  // 1–2 cards (BASIC_USER, DATA_ANALYST, BACKEND_DEV, SECURITY_ENG):
  //   Chart full width, cards expand below.

  const renderGrid = () => {
    if (cardCount >= 5) {
      // ── ADMIN: chart left, 3+3 cards right ──────────
      return (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 mb-6 sm:mb-8">
          <div className="lg:row-span-2 h-full">
            <ProportionChart data={chartData} stretch />
          </div>
          {cardElements.slice(0, 3)}
          {cardElements.slice(3)}
        </div>
      )
    }

    if (cardCount === 4) {
      // ── DEVOPS: chart left, 2×2 cards right ──────────
      return (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6 sm:mb-8">
          <div className="lg:row-span-2 h-full">
            <ProportionChart data={chartData} stretch />
          </div>
          {cardElements}
        </div>
      )
    }

    if (cardCount === 3) {
      return (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6 sm:mb-8">
          <div className="lg:row-span-2 h-full">
            <ProportionChart data={chartData} stretch />
          </div>
          {cardElements[0]}
          {cardElements[1]}
          <div className="lg:col-span-2">
            {cardElements[2]}
          </div>
        </div>
      )
    }

    // ── Default: chart full-width, cards below ──
    return (
      <div className="mb-6 sm:mb-8 space-y-4">
        <ProportionChart data={chartData} />
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
            gap: "16px",
          }}
        >
          {cardElements}
        </div>
      </div>
    )
  }

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-6 sm:mb-8">
        <h1 className="text-xl sm:text-2xl font-bold text-white">Your Log Sources</h1>
        <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-brand-blue/10 text-brand-blue border border-brand-blue/20">
          {ROLE_LABELS[role] || role}
        </span>
      </div>

      {/* Role-adaptive grid */}
      {renderGrid()}

      {/* Live Log Feed */}
      <div className="card-dark p-4 sm:p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-white">Live Log Stream</h2>
            <span className={`w-2 h-2 rounded-full ${wsConnected ? "bg-green-400 animate-pulse" : "bg-red-400"}`} />
            <span className="text-xs text-navy-400">{wsConnected ? "Connected" : "Disconnected"}</span>
          </div>
          {liveLogs.length > 0 && (
            <button
              onClick={() => setLiveLogs([])}
              className="text-xs text-navy-400 hover:text-white transition-colors"
            >
              Clear
            </button>
          )}
        </div>

        {liveLogs.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-sm text-navy-400">
              {wsConnected
                ? "Waiting for new logs..."
                : "Connecting to log stream..."}
            </p>
            <p className="text-xs text-navy-500 mt-1">
              Logs will appear here in real-time as they are ingested
            </p>
          </div>
        ) : (
          <div className="space-y-1 max-h-72 overflow-y-auto custom-scrollbar">
            {liveLogs.map((log, i) => (
              <div
                key={log.id || i}
                className="flex items-start gap-2 px-3 py-1.5 rounded text-xs font-mono bg-dark-400/50 animate-fade-in"
              >
                <span className="text-navy-500 flex-shrink-0 w-14">
                  {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : "--:--"}
                </span>
                <span className={`flex-shrink-0 w-12 font-semibold ${
                  log.level === "ERROR" ? "text-red-400"
                  : log.level === "WARN" ? "text-amber-400"
                  : "text-blue-400"
                }`}>
                  {log.level}
                </span>
                <span className="text-navy-300 flex-shrink-0 w-28 truncate">
                  {log.service}
                </span>
                <span className="text-navy-200 truncate">
                  {log.message}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
