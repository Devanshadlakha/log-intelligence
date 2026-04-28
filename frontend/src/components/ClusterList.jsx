const CLUSTER_COLORS = ["#5171FF", "#FF97AD", "#34D399", "#FBBF24", "#A78BFA", "#F87171"]

export default function ClusterList({ clusters }) {
  if (!clusters?.length) return null

  return (
    <div className="card-dark p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-white">Error Clusters</h2>
        <span className="text-xs text-navy-400">{clusters.length} groups</span>
      </div>
      <div className="space-y-2">
        {clusters.map((cluster, i) => (
          <div
            key={cluster.cluster_id}
            className="flex items-center gap-3 px-3 py-2.5 rounded-md hover:bg-dark-50/40 transition-colors"
          >
            <span
              className="w-2.5 h-2.5 rounded-full flex-shrink-0"
              style={{ backgroundColor: CLUSTER_COLORS[i % CLUSTER_COLORS.length] }}
            />
            <span className="flex-1 text-navy-200 text-sm truncate">{cluster.label}</span>
            <span
              className="text-[11px] font-semibold whitespace-nowrap px-2 py-0.5 rounded-full bg-dark-50 text-navy-200 border border-dark-50"
            >
              {cluster.count} Events
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
