import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { backtest, fmtDate, insights, meta, nf, products } from '../lib.js'

const VERDICT = {
  bevestigd: 'bg-emerald-100 text-emerald-800',
  deels: 'bg-amber-100 text-amber-800',
  'niet bevestigd': 'bg-red-100 text-red-700',
}
const COLORS = ['#FF6200', '#001E82', '#10b981', '#0ea5e9', '#a855f7', '#f59e0b', '#64748b']

function Chart({ chart }) {
  if (!chart) return null
  if (chart.type === 'brands') {
    return (
      <ResponsiveContainer height={220}>
        <BarChart data={chart.rows} layout="vertical" margin={{ left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis type="number" tick={{ fontSize: 10 }} />
          <YAxis type="category" dataKey="brand" width={110} tick={{ fontSize: 10 }} />
          <Tooltip />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="videos_per_day" name="Video's per dag" fill="#001E82" />
          <Bar dataKey="growth_pct_per_day" name="Verkoopgroei %/dag" fill="#FF6200" />
        </BarChart>
      </ResponsiveContainer>
    )
  }
  if (chart.type === 'event_study') {
    return (
      <ResponsiveContainer height={200}>
        <BarChart data={chart.rows.map((r) => ({ ...r, dag: r.day === 0 ? 'burst' : (r.day > 0 ? '+' : '') + r.day }))}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="dag" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 10 }} />
          <Tooltip />
          <Bar dataKey="reviews_per_day" name="Reviews per dag (gem.)">
            {chart.rows.map((r) => <Cell key={r.day} fill={r.day < 0 ? '#94a3b8' : '#001E82'} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    )
  }
  if (chart.type === 'bars') {
    return (
      <ResponsiveContainer height={180}>
        <BarChart data={chart.rows}>
          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 10 }} unit="%" />
          <Tooltip />
          <Bar dataKey="value" name={chart.unit} fill="#FF6200" radius={[6, 6, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    )
  }
  if (chart.type === 'decay') {
    const rows = [0, 1, 2, 3, 4].map((t) => {
      const r = { t: t === 0 ? 'piek' : `+${t} d` }
      chart.curves.forEach((c, k) => { const p = c.points.find((x) => x.t === t); r[`c${k}`] = p ? p.pct : null })
      return r
    })
    return (
      <ResponsiveContainer height={220}>
        <LineChart data={rows}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="t" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 10 }} unit="%" />
          <Tooltip />
          {chart.curves.map((c, k) => (
            <Line key={k} dataKey={`c${k}`} name={`${c.title.slice(0, 28)} (${fmtDate(c.peak_date)})`} stroke={COLORS[k % COLORS.length]} strokeWidth={2} connectNulls />
          ))}
        </LineChart>
      </ResponsiveContainer>
    )
  }
  if (chart.type === 'categories') {
    return (
      <ResponsiveContainer height={240}>
        <BarChart data={chart.rows} layout="vertical" margin={{ left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis type="number" tick={{ fontSize: 10 }} />
          <YAxis type="category" dataKey="label" width={150} tick={{ fontSize: 10 }} />
          <Tooltip />
          <Bar dataKey="units_per_day" name="Verkocht per dag" fill="#FF6200" />
        </BarChart>
      </ResponsiveContainer>
    )
  }
  return null
}

function Backtest() {
  const r = backtest.radar
  const lc = backtest.leakage_check
  const stat = (v, l, accent) => (
    <div className="text-center"><div className={`text-3xl font-black ${accent || 'text-navy'}`}>{v}</div><div className="text-xs text-slate-500">{l}</div></div>
  )
  return (
    <div className="card p-5">
      <h2 className="font-extrabold text-xl text-navy">Backtest: de radar terugspelen, dag voor dag</h2>
      <p className="text-sm text-slate-600 mt-1">
        Voor elke dag draaide de hele detector opnieuw met alleen de data tot en met die dag. Lekcheck:{' '}
        <b className={lc.passed ? 'text-emerald-700' : 'text-red-600'}>{lc.passed ? 'geslaagd' : 'MISLUKT'}</b>{' '}
        ({nf(lc.rows_compared)} product-dagen identiek aan de volledige run, dus niets kijkt in de toekomst).
      </p>
      <div className="grid grid-cols-3 md:grid-cols-6 gap-3 my-4">
        {stat(r.events, 'bursts in de data')}
        {stat(`${backtest.detection.events_detected_on_first_day}/${r.events}`, 'op dag 1 gedetecteerd', 'text-oranje')}
        {stat(`${backtest.detection.parcel_warning_days[0]}-${backtest.detection.parcel_warning_days[1]} d`, 'voorsprong op bezorging', 'text-oranje')}
        {stat(`${r.events_predicted}/${r.events}`, 'vooraf voorspeld (1-3 d)')}
        {stat(r.alerts, 'opbouw-alerts')}
        {stat(r.false_alarms, 'daarvan niet uitgekomen', 'text-red-600')}
      </div>
      <div className="rounded-xl bg-amber-50 border border-amber-200 p-3 text-sm">
        <b>Eerlijk:</b> in 13 dagen schone data ging aan geen enkele burst een signaal vooraf dat we betrouwbaar konden zien. De radar ziet
        elke burst op de eerste dag. Omdat bestellingen pas 1-3 dagen later bezorgd worden, is dat precies op tijd voor PostNL. Echt
        vooruit voorspellen vraagt meer data (maanden, niet 2 weken). De backtest-code staat klaar om dat te bewijzen.
        {' '}{backtest.model}
      </div>
      <div className="grid md:grid-cols-2 gap-4 mt-4">
        <div>
          <h3 className="font-bold text-sm mb-1">Bursts</h3>
          <table className="w-full text-sm">
            <tbody>
              {backtest.events.map((e, k) => (
                <tr key={k} className="border-t border-slate-100"><td className="py-1">{fmtDate(e.date)}</td><td>{products[e.id]?.short}</td>
                  <td className="text-right">{e.predicted ? `${e.lead_days} d vooraf` : 'op de dag zelf'}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
        <div>
          <h3 className="font-bold text-sm mb-1">Losse signalen als voorspeller (zelfde bursts)</h3>
          <table className="w-full text-sm">
            <thead><tr className="text-xs text-slate-500 text-left"><th>Regel</th><th className="text-right">alerts</th><th className="text-right">bursts vooraf</th><th className="text-right">trefkans</th></tr></thead>
            <tbody>
              {[{ ...r, rule: 'Hype Radar (combinatie)' }, ...backtest.comparisons].map((c) => (
                <tr key={c.rule} className="border-t border-slate-100">
                  <td className="py-1">{c.rule}</td><td className="text-right">{c.alerts}</td>
                  <td className="text-right">{c.events_predicted}/{c.events}</td>
                  <td className="text-right">{c.precision == null ? '–' : `${nf(100 * c.precision, 1)}%`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function DataQuality() {
  return (
    <div className="card p-5">
      <h2 className="font-extrabold text-xl text-navy">Datakwaliteit per dag</h2>
      <div className="flex gap-1 mt-3">
        {meta.day_quality.map((q) => (
          <div key={q.date} className="flex-1 text-center">
            <div className={`h-12 rounded-md grid place-items-center text-[10px] font-bold text-white ${q.sales_gated ? 'bg-red-500' : q.source_change ? 'bg-red-700' : q.partial_day ? 'bg-amber-400' : 'bg-emerald-500'}`}>
              {q.n_products}
            </div>
            <div className="text-[10px] text-slate-500 mt-1">{fmtDate(q.date)}</div>
          </div>
        ))}
      </div>
      <div className="flex gap-4 text-xs text-slate-500 mt-2">
        <span><b className="text-red-500">■</b> afgekapte verkoopcijfers</span><span><b className="text-red-700">■</b> bronwissel</span>
        <span><b className="text-amber-400">■</b> veel producten ontbreken</span><span><b className="text-emerald-500">■</b> bruikbaar (getal = aantal producten)</span>
      </div>
      <h3 className="font-bold text-sm mt-4 mb-1">Opschoonlog (alles staat in detector/output/exclusion_log.csv)</h3>
      <table className="w-full text-sm">
        <tbody>
          {meta.exclusions.map((e) => (
            <tr key={e.rule} className="border-t border-slate-100"><td className="py-1 font-mono text-xs">{e.rule}</td><td>{e.action}</td><td className="text-right">{e.entries}×</td></tr>
          ))}
        </tbody>
      </table>
      <h3 className="font-bold text-sm mt-4 mb-1">Aannames</h3>
      <ul className="text-sm list-disc pl-5 text-slate-700">{meta.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
    </div>
  )
}

export default function Insights() {
  return (
    <div className="space-y-4">
      <div className="card p-5 bg-navy text-white border-0">
        <div className="text-xs uppercase tracking-wide text-navy-100 font-semibold">Kerninzicht</div>
        <div className="text-xl font-bold mt-1">{insights.headline}</div>
      </div>
      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
        {insights.cards.map((c) => (
          <div key={c.id} className="card p-5 flex flex-col">
            <div className="flex items-start justify-between gap-2">
              <h3 className="font-extrabold text-navy text-lg leading-tight">{c.title}</h3>
              <span className={`chip ${VERDICT[c.verdict]} shrink-0`}>{c.verdict}</span>
            </div>
            <div className="text-xs text-slate-500 italic mt-1">Hypothese: {c.hypothesis}</div>
            <p className="text-sm mt-2">{c.summary}</p>
            <div className="grid grid-cols-2 gap-2 mt-3">
              {c.numbers.map((n) => (
                <div key={n.label} className="rounded-lg bg-slate-50 p-2"><div className="font-black text-navy">{n.value}</div><div className="text-[11px] text-slate-500">{n.label}</div></div>
              ))}
            </div>
            <div className="mt-3"><Chart chart={c.chart} /></div>
          </div>
        ))}
      </div>
      <Backtest />
      <DataQuality />
    </div>
  )
}
