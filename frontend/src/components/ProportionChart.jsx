import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts"

const COLORS = [
  "#5171FF",
  "#FF97AD",
  "#34D399",
  "#FBBF24",
  "#A78BFA",
  "#F87171",
  "#60A5FA",
  "#FB923C",
]

export default function ProportionChart({ data, stretch = false }) {
  if (!data || data.length === 0) {
    return (
      <div className={`card-dark p-6 ${stretch ? "h-full flex flex-col justify-center" : ""}`}>
        <h2 className="text-sm font-semibold text-white mb-4">Log Distribution</h2>
        <p className="text-xs text-navy-400 text-center py-8">
          No log data available yet. Start your collectors to see distribution.
        </p>
      </div>
    )
  }

  const total = data.reduce((sum, d) => sum + d.count, 0)

  const chartData = data
    .map((d, i) => ({
      name: d.category,
      value: d.count,
      percentage: total > 0 ? (d.count / total) * 100 : 0,
      color: COLORS[i % COLORS.length],
    }))
    .sort((a, b) => b.value - a.value)

  return (
    <div className={`card-dark p-6 ${stretch ? "h-full flex flex-col" : ""}`}>
      <h2 className="text-sm font-semibold text-white mb-1">Log Distribution</h2>
      <p className="text-xs text-navy-400 mb-4">Proportion by source (last 7 days)</p>

      <div className={`relative ${stretch ? "flex-1 min-h-0" : ""}`}>
        <ResponsiveContainer width="100%" height={stretch ? "100%" : 240}>
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius={68}
              outerRadius={108}
              paddingAngle={2}
              dataKey="value"
              isAnimationActive={false}
            >
              {chartData.map((entry, i) => (
                <Cell
                  key={i}
                  fill={entry.color}
                  stroke="#1e2230"
                  strokeWidth={2}
                />
              ))}
            </Pie>
            <Tooltip
              formatter={(value, name) => [
                `${value.toLocaleString()} logs (${total > 0 ? ((value / total) * 100).toFixed(1) : 0}%)`,
                name,
              ]}
              contentStyle={{
                backgroundColor: "#0a0d16",
                border: "1px solid #5171FF",
                borderRadius: "8px",
                fontSize: "12px",
                color: "#ffffff",
                boxShadow: "0 4px 20px rgba(81, 113, 255, 0.25)",
              }}
              itemStyle={{ color: "#d9e0f5" }}
              labelStyle={{ color: "#ffffff", fontWeight: 600 }}
            />
          </PieChart>
        </ResponsiveContainer>

        {/* Center total — absolutely positioned over the donut hole */}
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-bold text-gradient leading-none">
            {total.toLocaleString()}
          </span>
          <span className="text-[11px] uppercase tracking-wider text-navy-400 mt-1">
            total logs
          </span>
        </div>
      </div>

      {/* Custom legend below — colored dot, name, percentage */}
      <ul className="mt-5 grid grid-cols-2 gap-x-4 gap-y-2">
        {chartData.map((entry) => (
          <li
            key={entry.name}
            className="flex items-center justify-between gap-2 text-xs"
          >
            <span className="flex items-center gap-2 min-w-0">
              <span
                className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                style={{ backgroundColor: entry.color }}
              />
              <span className="text-navy-200 truncate">{entry.name}</span>
            </span>
            <span className="text-navy-400 font-mono tabular-nums flex-shrink-0">
              {entry.percentage.toFixed(1)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
