const INTENT_CONFIG = {
  question: { label: "AI Answer", icon: "💡", border: "border-brand-blue/30", bg: "bg-brand-blue/5" },
  report:   { label: "Summary Report", icon: "📊", border: "border-emerald-500/30", bg: "bg-emerald-500/5" },
  search:   { label: "Root Cause Identified", icon: "⚠️", border: "border-amber-500/30", bg: "bg-amber-500/5" },
}

export default function RootCauseSummary({ summary, intent }) {
  if (!summary) return null

  const config = INTENT_CONFIG[intent] || INTENT_CONFIG.search

  return (
    <div className={`rounded-lg p-5 ${config.bg} border ${config.border}`}>
      <div className="flex items-center gap-2 mb-3">
        <span className="text-lg">{config.icon}</span>
        <h2 className="text-sm font-bold text-white">{config.label}</h2>
        <span className="text-xs text-navy-400 ml-auto">Powered by AI</span>
      </div>
      <p className="text-navy-200 text-sm leading-relaxed whitespace-pre-line">{summary}</p>
    </div>
  )
}
