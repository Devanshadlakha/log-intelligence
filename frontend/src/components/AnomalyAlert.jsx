export default function AnomalyAlert({ anomaly }) {
  if (!anomaly || !anomaly.detected) return null

  const severity = anomaly.severity || "warning"
  const severityClasses =
    severity === "critical"
      ? "border-red-500/40 bg-red-500/10 text-red-300"
      : "border-yellow-500/40 bg-yellow-500/10 text-yellow-300"

  return (
    <div className={`rounded border ${severityClasses} px-4 py-3 mb-4`}>
      <div className="flex items-start gap-3">
        <span className="mt-0.5 inline-block h-2 w-2 rounded-full bg-current animate-pulse" />
        <div className="flex-1">
          <p className="text-sm font-semibold capitalize">
            {severity} anomaly detected
          </p>
          {anomaly.message && (
            <p className="text-xs mt-1 opacity-90">{anomaly.message}</p>
          )}
          {typeof anomaly.score === "number" && (
            <p className="text-[11px] mt-1 opacity-70">
              Score: {anomaly.score.toFixed(2)}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
