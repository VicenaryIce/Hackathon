// Small shared UI pieces that keep the screens calm: extra info goes under "Meer details".
export function More({ label = 'Meer details', children, className = '' }) {
  return (
    <details className={`more group ${className}`}>
      <summary className="cursor-pointer select-none list-none inline-flex items-center gap-1.5 text-sm font-semibold text-navy hover:text-oranje-600">
        <span className="inline-block transition-transform group-open:rotate-90">▸</span>{label}
      </summary>
      <div className="mt-3">{children}</div>
    </details>
  )
}

// One line at the top of every tab: what is this screen for?
export function Intro({ step, title, children }) {
  return (
    <div className="flex items-start gap-3">
      {step && <div className="w-9 h-9 rounded-full bg-oranje text-white grid place-items-center font-black shrink-0">{step}</div>}
      <div>
        <h1 className="text-2xl font-extrabold text-navy leading-tight">{title}</h1>
        <p className="text-slate-600">{children}</p>
      </div>
    </div>
  )
}
