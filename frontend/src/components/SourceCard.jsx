import { Link } from "react-router-dom"

export default function SourceCard({ source }) {
  const { id, title, description, icon, count } = source

  return (
    <Link to={`/logs/${id}`} className="block h-full">
      <div className="card-dark p-5 transition-all duration-300 hover:-translate-y-1 hover:border-brand-blue/40 h-full flex flex-col">
        <div className="text-3xl mb-3">{icon}</div>
        <h3 className="text-sm font-semibold text-white mb-1">{title}</h3>
        <p className="text-xs text-navy-300 mb-4 leading-relaxed flex-1">{description}</p>
        <div className="flex items-center justify-between mt-auto">
          <span className="text-xs text-navy-400">Last 24h</span>
          <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold bg-brand-blue/10 text-brand-blue">
            {count != null ? `${count} logs` : "..."}
          </span>
        </div>
      </div>
    </Link>
  )
}
