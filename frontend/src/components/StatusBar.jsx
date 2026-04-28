import { useEffect, useState } from "react"

export default function StatusBar() {
  const [online, setOnline] = useState(true)

  useEffect(() => {
    let cancelled = false
    const ping = async () => {
      try {
        const res = await fetch("/api/logs/health", { cache: "no-store" })
        if (!cancelled) setOnline(res.ok)
      } catch {
        if (!cancelled) setOnline(false)
      }
    }
    ping()
    const id = setInterval(ping, 15000)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  return (
    <div className="flex items-center gap-2 text-xs text-gray-300">
      <span
        className={`inline-block h-2 w-2 rounded-full ${
          online ? "bg-green-500" : "bg-red-500"
        }`}
      />
      <span>{online ? "Connected" : "Offline"}</span>
    </div>
  )
}
