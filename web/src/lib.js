// Shared data + helpers. All data is produced by the Python detector (python3 -m detector).
import meta from './data/meta.json'
import products from './data/products.json'
import replay from './data/replay.json'
import backtest from './data/backtest.json'
import alarms from './data/alarms.json'
import insights from './data/insights.json'

export { meta, products, replay, backtest, alarms, insights }

export const DATES = meta.dates
const MONTHS = ['jan', 'feb', 'mrt', 'apr', 'mei', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec']
export const fmtDate = (s) => { const d = new Date(s + 'T12:00:00'); return `${d.getDate()} ${MONTHS[d.getMonth()]}` }
export const fmtDay = (s) => new Date(s + 'T12:00:00').toLocaleDateString('nl-NL', { weekday: 'short', day: 'numeric', month: 'short' })
export const nf = (x, d = 0) => (x == null || Number.isNaN(x) ? '–' : Number(x).toLocaleString('nl-NL', { maximumFractionDigits: d, minimumFractionDigits: 0 }))
export const smart = (x) => (x == null ? '–' : Math.abs(x) >= 10 ? nf(Math.round(x)) : nf(x, 1))

export const PHASES = {
  geen_data: { label: 'Geen data', cls: 'bg-slate-100 text-slate-500', dot: '#94a3b8' },
  opwarmen: { label: 'Opwarmen', cls: 'bg-slate-100 text-slate-600', dot: '#94a3b8' },
  stabiel: { label: 'Stabiel', cls: 'bg-emerald-50 text-emerald-700', dot: '#10b981' },
  opbouw: { label: 'Opbouw', cls: 'bg-amber-50 text-amber-700', dot: '#f59e0b' },
  burst: { label: 'Burst', cls: 'bg-oranje text-white', dot: '#FF6200' },
  afkoeling: { label: 'Afkoeling', cls: 'bg-sky-50 text-sky-700', dot: '#0ea5e9' },
}

export const SIGNALS = ['Verkoop stijgt', 'Reviewsprong', 'Merk post ≥1 video/dag', 'Likes stijgen']
export const alarmById = Object.fromEntries(alarms.map((a) => [a.id, a]))
