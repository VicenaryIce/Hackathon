import { useState } from 'react'
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fmtDate, fmtDay, nf, products, smart } from '../lib.js'
import scenario from '../data/scenario.json'
import { Intro, More } from './Ui.jsx'

// Product-first forecast: normal orders → parcels if it goes viral → chance and timing.
// All numbers come from detector/scenario.py (python3 -m detector).

const STATUS = {
  burst: { label: '🔥 Nu viraal', cls: 'bg-oranje text-white', text: 'De radar ziet nu een hype. De pakketten komen over 1-3 dagen: plan nu.' },
  opbouw: { label: '⚡ Signaal', cls: 'bg-amber-100 text-amber-800', text: 'De verkoop begint te stijgen. Mogelijk viraal binnen 1-3 dagen.' },
  afkoeling: { label: 'Koelt af', cls: 'bg-sky-50 text-sky-700', text: 'Was net viraal en koelt nu af. Kan opnieuw opleven (gebeurde al eerder).' },
  rustig: { label: 'Rustig', cls: 'bg-slate-100 text-slate-600', text: 'Nu geen signaal. Gaat het viraal, dan ziet de radar dat op dag 1.' },
}
const SIZE_ICON = { brievenbus: '✉️', pakket: '📦', 'groot pakket': '🗃️' }
const [D_LO, D_HI] = scenario.delivery_days
const SHIFT = Math.round((D_LO + D_HI) / 2) // orders reach PostNL ~2 days later

function chanceCls(pct) {
  if (pct >= 20) return 'bg-oranje text-white'
  if (pct >= 5) return 'bg-amber-100 text-amber-800'
  return 'bg-slate-100 text-slate-600'
}
const pct = (x) => `${x >= 10 ? nf(x) : nf(x, 1)}%`
const addDays = (date, k) => { const d = new Date(date + 'T12:00'); d.setDate(d.getDate() + k); return d.toISOString().slice(0, 10) }

function ScenarioChart({ r }) {
  // Example: the hype starts 2 days from now. Parcels reach PostNL ~2 days after the orders.
  // average day-by-day shape of a hype, scaled so its top matches the peak shown in step 2
  const raw = scenario.model.shape
  const top = Math.max(...raw)
  const shape = raw.map((m) => 1 + (m - 1) * (scenario.model.peak_mult.mid - 1) / (top - 1))
  const start = 2
  const rows = Array.from({ length: 11 }, (_, k) => {
    const date = addDays(scenario.as_of, k + 1)
    const ok = k - start - SHIFT
    const mult = ok >= 0 && ok < shape.length ? shape[ok] : 1
    return { date: fmtDate(date), normaal: r.normal, hype: Math.round(r.normal * mult) }
  })
  const hypeDay = rows[start].date
  const parcelDay = rows[start + SHIFT].date
  return (
    <div>
      <div className="text-sm font-semibold text-navy">Pakketten per dag bij PostNL, als de hype op {hypeDay} start (voorbeeld)</div>
      <div className="h-56">
        <ResponsiveContainer>
          <ComposedChart data={rows} margin={{ top: 22, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} width={48} />
            <Tooltip formatter={(v, n) => [nf(v), n]} />
            <ReferenceLine x={hypeDay} stroke="#f59e0b" strokeDasharray="4 2" label={{ value: 'radar ziet hype', fontSize: 11, fill: '#b45309', position: 'top' }} />
            <ReferenceLine x={parcelDay} stroke="#FF6200" strokeDasharray="4 2" label={{ value: 'pakketten komen', fontSize: 11, fill: '#E55800', position: 'top' }} />
            <Area type="monotone" dataKey="hype" name="Als het viraal gaat" stroke="#FF6200" fill="#FF6200" fillOpacity={0.2} strokeWidth={3} />
            <Line type="monotone" dataKey="normaal" name="Normaal" stroke="#001E82" strokeDasharray="6 4" dot={false} strokeWidth={2} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="flex gap-4 text-xs text-slate-600">
        <span><b className="text-navy">┅</b> normaal</span><span><b className="text-oranje">━</b> als het viraal gaat</span>
        <span>Tussen de twee lijnen: {D_LO}-{D_HI} dagen om je voor te bereiden.</span>
      </div>
    </div>
  )
}

function Step({ n, title, children, accent }) {
  return (
    <div className={`rounded-2xl p-4 flex-1 ${accent ? 'bg-oranje-50 ring-1 ring-oranje/30' : 'bg-slate-50'}`}>
      <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-slate-500">
        <span className={`w-5 h-5 rounded-full grid place-items-center text-[11px] ${accent ? 'bg-oranje text-white' : 'bg-navy text-white'}`}>{n}</span>{title}
      </div>
      <div className="mt-2">{children}</div>
    </div>
  )
}

function ProductCard({ r }) {
  const p = products[r.id]
  const v = r.viral
  const st = STATUS[r.status]
  const extraDrivers = Math.ceil((v.peak - r.normal) / scenario.parcels_per_driver)
  return (
    <div className="card p-5 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs text-slate-500">{p.brand} · {SIZE_ICON[r.parcel_size]} {r.parcel_size}</div>
          <h2 className="font-extrabold text-xl text-navy leading-tight">{p.short}</h2>
        </div>
        <span className={`chip ${st.cls} text-sm px-3 py-1`}>{st.label}</span>
      </div>

      <div className="flex flex-col md:flex-row gap-2 items-stretch">
        <Step n="1" title="Normaal">
          <div className="text-3xl font-black text-navy">{smart(r.normal)}</div>
          <div className="text-sm text-slate-600">pakketten per dag volgende week</div>
        </Step>
        <div className="hidden md:grid place-items-center text-2xl text-slate-300">→</div>
        <Step n="2" title="Als het viraal gaat" accent>
          <div className="text-3xl font-black text-oranje">{smart(v.peak)}</div>
          <div className="text-sm text-slate-700">per dag op de piek <span className="text-slate-400">({smart(v.peak_low)}-{smart(v.peak_high)})</span></div>
          <div className="text-sm text-slate-700 mt-1"><b>+{nf(v.extra)}</b> extra pakketten in ~{nf(v.days)} dagen</div>
        </Step>
        <div className="hidden md:grid place-items-center text-2xl text-slate-300">→</div>
        <Step n="3" title="Wanneer?">
          <div className="flex items-baseline gap-2"><span className={`chip ${chanceCls(r.chance_week_pct)} text-lg px-3 py-0.5`}>{pct(r.chance_week_pct)}</span><span className="text-sm text-slate-600">kans deze week</span></div>
          <div className="text-sm text-slate-700 mt-1.5">{st.text}</div>
        </Step>
      </div>

      <ScenarioChart r={r} />

      <div className="rounded-xl bg-navy-50 p-3 text-sm space-y-1">
        <div className="font-bold text-navy">Wat PostNL kan doen</div>
        <div>📦 Sorteercapaciteit klaarzetten voor tot <b>{nf(v.peak_high)}</b> {r.parcel_size === 'brievenbus' ? 'brievenbuspakjes' : 'pakketten'} per dag.</div>
        {extraDrivers > 0 && <div>🚚 ~{extraDrivers} extra bezorger{extraDrivers > 1 ? 's' : ''} achter de hand houden.</div>}
        <div>🏪 {p.store}: voorraad voor ~{nf(v.extra_high)} extra bestellingen, zodat de hype niet stokt.</div>
      </div>

      <More label="Hoe komen we aan deze getallen?">
        <div className="text-sm text-slate-700 space-y-1.5">
          <div><b>Normaal</b> = het voorspellingsmodel: volgende week ≈ 0,8× deze week (zie Inzichten).</div>
          <div><b>Als het viraal gaat</b> = wat er gebeurde bij de {scenario.model.n_big} grote hypes in de data: bestellingen stegen naar
            {' '}{nf(scenario.model.peak_mult.low, 1)}-{nf(scenario.model.peak_mult.high, 1)}× normaal, {scenario.model.days.low}-{scenario.model.days.high} dagen lang.</div>
          <div><b>Kans</b> = hoe vaak dit soort product ({p.type_label.toLowerCase()}: {pct(r.type_chance_week_pct)} per week)
            {r.went_viral_before ? <> en dit product zelf ({r.went_viral_before}× viraal in 12 dagen)</> : ''} viraal ging.</div>
          <div className="text-xs text-slate-500">Een exacte datum is niet te voorspellen: in de data ging geen enkel signaal betrouwbaar vooraf aan een hype. Wat wel kan: de radar ziet de hype op dag 1, en de pakketten komen pas 1-3 dagen later.</div>
        </div>
      </More>
    </div>
  )
}

export default function Predict() {
  const list = scenario.products.slice(0, 12)
  const [sel, setSel] = useState(list[0].id)
  const r = scenario.products.find((x) => x.id === sel) || list[0]
  const t = scenario.totals
  const top = scenario.products[0]
  return (
    <div className="space-y-4">
      <Intro step="1" title="Hoeveel pakketten als een product viraal gaat?">Per product: wat is normaal, hoeveel wordt het als het viraal gaat, en hoe groot is de kans. Voorspelling vanaf {fmtDay(scenario.as_of)}.</Intro>

      <div className="grid md:grid-cols-3 gap-4">
        <div className="card p-4">
          <div className="text-xs uppercase tracking-wide text-slate-500 font-semibold">Normaal, volgende week</div>
          <div className="text-4xl font-black text-navy">{nf(t.normal)}</div>
          <div className="text-sm text-slate-600">pakketten per dag</div>
        </div>
        <div className="card p-4">
          <div className="text-xs uppercase tracking-wide text-slate-500 font-semibold">Extra door hypes, verwacht</div>
          <div className="text-4xl font-black text-oranje">+{nf(t.expected_extra_week)}</div>
          <div className="text-sm text-slate-600">pakketten deze week (kans × omvang)</div>
        </div>
        <div className="card p-4">
          <div className="text-xs uppercase tracking-wide text-slate-500 font-semibold">Grootste risico</div>
          <div className="text-lg font-extrabold text-navy truncate">{products[top.id].short}</div>
          <div className="text-sm text-slate-600">tot <b>{nf(top.viral.peak)}</b> per dag als het viraal gaat · {pct(top.chance_week_pct)} kans</div>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 lg:col-span-4 card p-4 self-start">
          <h2 className="font-extrabold text-lg text-navy">Hoogste hype-risico</h2>
          <div className="text-xs text-slate-500 mb-2">gesorteerd op kans × aantal pakketten</div>
          <ol className="divide-y divide-slate-100">
            {list.map((x, i) => (
              <li key={x.id}>
                <button onClick={() => setSel(x.id)}
                  className={`w-full text-left py-2.5 px-2 rounded-xl flex items-center gap-3 ${x.id === r.id ? 'bg-oranje-50 ring-2 ring-oranje' : 'hover:bg-slate-50'}`}>
                  <span className="w-5 text-slate-400 font-bold text-sm">{i + 1}</span>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-sm truncate">{products[x.id].short}</div>
                    <div className="text-xs text-slate-500 truncate">{smart(x.normal)} → <b className="text-oranje-600">{smart(x.viral.peak)}</b> per dag als viraal</div>
                  </div>
                  <span className={`chip ${chanceCls(x.chance_week_pct)}`}>{pct(x.chance_week_pct)}</span>
                </button>
              </li>
            ))}
          </ol>
        </div>
        <div className="col-span-12 lg:col-span-8"><ProductCard r={r} /></div>
      </div>

      <div className="card p-4">
        <More label="Hype-kans per soort product">
          <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-2">
            {scenario.types.map((ty) => (
              <div key={ty.type} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
                <span>{ty.label} <span className="text-xs text-slate-400">({ty.bursts} hype{ty.bursts === 1 ? '' : 's'})</span></span>
                <span className={`chip ${chanceCls(ty.week_pct)}`}>{pct(ty.week_pct)}</span>
              </div>
            ))}
          </div>
          <div className="text-xs text-slate-500 mt-2">Per week, op basis van {scenario.model.n_all} hypes in de schone dagen vanaf {fmtDate(scenario.model.clean_from)}. Soorten zonder hype krijgen het gemiddelde ({pct(scenario.model.overall_week_pct)}) als startpunt, niet 0%. Eerste schatting: weinig data.</div>
        </More>
      </div>
    </div>
  )
}
