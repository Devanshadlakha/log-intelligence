import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts"

// Format an ISO UTC timestamp into the user's local "HH:MM" — keeps the chart
// axis consistent with the LogTable, which also displays times in local TZ.
const formatHour = (iso) => {
  if (!iso) return ""
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false })
}

export default function ErrorFrequencyChart({ data }) {
  if (!data?.length) return null

  return (
    <div className="card-dark p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-white">Error Rate Over Time</h2>
        <span className="text-xs text-navy-400">{data.length} buckets</span>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={data} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}>
          <defs>
            <linearGradient id="errorGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#F87171" stopOpacity={0.35}/>
              <stop offset="95%" stopColor="#F87171" stopOpacity={0}/>
            </linearGradient>
            <linearGradient id="warnGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#FBBF24" stopOpacity={0.25}/>
              <stop offset="95%" stopColor="#FBBF24" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#2a2f3e" />
          <XAxis
            dataKey="timestamp"
            tickFormatter={formatHour}
            tick={{ fill: "#7889c1", fontSize: 11 }}
            axisLine={{ stroke: "#2a2f3e" }}
            tickLine={false}
            minTickGap={24}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fill: "#7889c1", fontSize: 11 }}
            axisLine={{ stroke: "#2a2f3e" }}
            tickLine={false}
          />
          <Tooltip
            labelFormatter={formatHour}
            contentStyle={{
              backgroundColor: "#0a0d16",
              border: "1px solid #2a2f3e",
              borderRadius: "8px",
              fontSize: "12px",
              color: "#d9e0f5",
            }}
            labelStyle={{ color: "#ffffff", fontWeight: 600 }}
          />
          <Legend
            wrapperStyle={{ fontSize: "12px", color: "#7889c1", paddingTop: "8px" }}
            iconType="circle"
            iconSize={8}
          />
          <Area
            type="monotone"
            dataKey="errors"
            stroke="#F87171"
            fill="url(#errorGrad)"
            strokeWidth={2}
            name="Errors"
            dot={false}
            activeDot={{ r: 4, strokeWidth: 0 }}
          />
          <Area
            type="monotone"
            dataKey="warnings"
            stroke="#FBBF24"
            fill="url(#warnGrad)"
            strokeWidth={2}
            name="Warnings"
            dot={false}
            activeDot={{ r: 4, strokeWidth: 0 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
