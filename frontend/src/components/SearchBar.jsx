export default function SearchBar({ value, onChange, onSearch, loading }) {
  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !loading) onSearch()
  }

  return (
    <div className="relative flex-1">
      <svg
        className="absolute left-3.5 top-1/2 -translate-y-1/2 text-navy-400"
        width="16" height="16" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      >
        <circle cx="11" cy="11" r="8"/>
        <line x1="21" y1="21" x2="16.65" y2="16.65"/>
      </svg>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder='e.g. "show errors last 6 hours" or "what is causing failures?" or "generate a summary report"'
        disabled={loading}
        className="w-full bg-[#2a3040] border border-[#3a4055] rounded-lg pl-10 pr-4 py-3
                   text-white placeholder-[#8090b0] text-sm
                   focus:outline-none focus:border-brand-blue focus:ring-1 focus:ring-brand-blue/30
                   disabled:opacity-50 transition-all"
      />
    </div>
  )
}
