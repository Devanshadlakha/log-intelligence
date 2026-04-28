export default function TimeRangeDropdown({ value, onChange }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="bg-dark-300 border border-dark-50 rounded-lg px-4 py-3
                 text-navy-200 text-sm focus:outline-none focus:border-brand-blue
                 focus:ring-1 focus:ring-brand-blue/30 cursor-pointer transition-all"
    >
      <option value="0.25">Last 15 Minutes</option>
      <option value="0.5">Last 30 Minutes</option>
      <option value="1">Last 1 Hour</option>
      <option value="3">Last 3 Hours</option>
      <option value="6">Last 6 Hours</option>
      <option value="12">Last 12 Hours</option>
      <option value="24">Last 24 Hours</option>
      <option value="72">Last 3 Days</option>
      <option value="168">Last 7 Days</option>
    </select>
  )
}
