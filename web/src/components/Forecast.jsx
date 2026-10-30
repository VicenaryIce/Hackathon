import { useState } from 'react'
import {
  Area, Bar, BarChart, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from 'recharts'
import { DATES, fmtDate, fmtDay, nf, products, smart } from '../lib.js'
import momentum from '../data/momentum.json'
import { Intro, More } from './Ui.jsx'

// Momentum model (see detector/momentum.py): next week's orders/day = ratio x this week's.
export const MPHASE = {
  groeiend: { label: 'Groeiend', cls: 'bg-oranje text-white' },
  stabiel: { label: 'Stabiel', cls: 'bg-emerald-50 text-emerald-700' },
  afkoelend: { label: 'Afkoelend', cls: 'bg-sky-50 text-sky-700' },
  te_weinig: { label: 'Te weinig data', cls: 'bg-slate-100 text-slate-500' },
}
export const MBadge = ({ phase }) => <span className={`chip ${MPHASE[phase].cls}`}>{MPHASE[phase].label}</span>

export function momentumPhase(id, date) {
  const d = momentum.days.find((x) => x.date === date) || momentum.days[momentum.days.length - 1]
  return d.products.find((p) => p.id === id)
}

function sentence(p) {
  const base = `Verwacht: ongeveer ${smart(p.mid)} bestellingen per dag volgende week.`
  if (p.phase === 'afkoelend') return `${base} De hype koelt af, dus let op retouren.`
  if (p.phase === 'groeiend') return `${base} De verkoop groeit: waarschuw de webshop voor de voorraad.`
  if (p.phase === 'stabiel') return `${base} Stabiel, normale capaciteit is genoeg.`
  return `${base} Te weinig verkoop om een trend te zien.`
}

function Detail({ id, dayIdx }) {
  const day = momentum.days[dayIdx]
  const p = day.products.find((x) => x.id === id)
  const t = products[id].timeline
  const di = DATES.indexOf(day.date)
  const rows = DATES.map((date, i) => ({
    date: fmtDate(date),
    verkocht: t.known_from[i] != null && t.known_from[i] <= di ? t.sales_filled[i] : null,
    achteraf: i > di && t.sales_filled[i] != null ? t.sales_filled[i] : null,
  }))
  for (let k = 1; k <= 7; k++) {
    const d = new Date(day.date + 'T12:00'); d.setDate(d.getDate() + k)
    const s = d.toISOString().slice(0, 10)
    let row = rows.find((r) => r.date === fmtDate(s))
    if (!row) { row = { date: fmtDate(s) }; rows.push(row) }
    row.band = [p.low, p.high]; row.verwacht = p.mid
  }
  return (
    <div className="card p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs text-slate-500">{products[id].brand}</div>
          <h2 className="font-extrabold text-xl text-navy">{products[id].short}</h2>
        </div>
        <MBadge phase={p.phase} />
      </div>
      <div className="mt-3 rounded-xl bg-navy-50 p-3 text-base font-semibold text-navy">{sentence(p)}</div>
      <div className="flex gap-4 text-xs text-slate-600 mt-3">
        <span><b className="text-navy">━</b> verkocht</span><span><b className="text-oranje">┅</b> verwacht</span><span><span className="inline-block w-3 h-3 align-middle rounded-sm bg-oranje/20" /> kan ook tussen</span>
      </div>
      <div className="h-64 mt-3">
        <ResponsiveContainer>
          <ComposedChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} interval={2} />
            <YAxis tick={{ fontSize: 11 }} width={48} />
            <Tooltip formatter={(v, n) => [Array.isArray(v) ? `${smart(v[0])}–${smart(v[1])}` : smart(v), n]} />
            <Area dataKey="band" name="Verwachte bandbreedte" fill="#FF6200" fillOpacity={0.18} stroke="none" />
            <Line dataKey="verwacht" name="Verwacht (midden)" stroke="#FF6200" strokeDasharray="6 3" dot={false} strokeWidth={2} />
            <Line dataKey="verkocht" name="Verkocht per dag" stroke="#001E82" strokeWidth={3} dot={false} connectNulls />
            <Line dataKey="achteraf" name="Wat er echt gebeurde (achteraf)" stroke="#94a3b8" strokeDasharray="4 3" dot={false} connectNulls />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <More label="Meer details" className="mt-1">
        <div className="text-sm space-y-1 text-slate-700">
          <div>Bandbreedte: <b>{smart(p.low)}–{smart(p.high)}</b> per dag (de middelste helft van wat echt gebeurde bij vergelijkbare producten).</div>
          <div>Afgelopen week: <b>{smart(p.this_week)}</b> per dag{p.ratio != null ? <> · groei week-op-week: <b>×{nf(p.ratio, 2)}</b></> : ''}</div>
          <div>{products[id].type_label} · pakketsoort: <b>{p.parcel_size}</b></div>
          <div className="text-xs text-slate-500">Grijze stippellijn = wat er achteraf echt gebeurde.</div>
        </div>
      </More>
    </div>
  )
}

export default function Forecast() {
  const [dayIdx, setDayIdx] = useState(momentum.days.length - 1)
  const day = momentum.days[dayIdx]
  const list = day.products.filter((p) => p.phase !== 'te_weinig').slice(0, 10)
  const [sel, setSel] = useState(null)
  const id = sel && day.products.some((p) => p.id === sel) ? sel : list[0].id
  const growing = day.products.filter((p) => p.phase === 'groeiend' && p.mid >= 20).slice(0, 2)
  const cooling = day.products.filter((p) => p.phase === 'afkoelend').slice(0, 2)
  const t = day.totals
  const sizeIcon = { brievenbus: '✉️', pakket: '📦', 'groot pakket': '🗃️' }
  return (
    <div className="space-y-4">
      <Intro step="2" title="Hoeveel pakketten komen er volgende week?">Het model kijkt naar de verkoop van deze week en voorspelt de volgende. Simpele regel: volgende week ≈ {nf(day.fit.ratio, 1)}× deze week.</Intro>

      <div className="card p-5 grid md:grid-cols-12 gap-5 items-center">
        <div className="md:col-span-4">
          <div className="text-xs uppercase tracking-wide text-slate-500 font-semibold">Verwacht per dag, volgende week</div>
          <div className="text-5xl font-black text-oranje">{nf(t.mid)}</div>
          <div className="text-sm text-slate-600">pakketten <span className="text-slate-400">(tussen {nf(t.low)} en {nf(t.high)})</span></div>
          {day.actual_total != null && <div className="text-xs mt-1 text-slate-500">Achteraf echt: <b>{nf(day.actual_total)}</b> per dag</div>}
        </div>
        <div className="md:col-span-4 space-y-1.5">
          {Object.entries(day.by_size).map(([k, v]) => (
            <div key={k} className="flex items-center gap-2 text-sm"><span className="w-6">{sizeIcon[k]}</span><span className="w-28 text-slate-600">{k}</span><b className="text-navy">{nf(v)}</b></div>
          ))}
          <div className="flex items-center gap-2 text-sm"><span className="w-6">🚚</span><span className="w-28 text-slate-600">bezorgers</span><b className="text-navy">~{Math.ceil(t.mid / 150)}</b></div>
        </div>
        <div className="md:col-span-4 space-y-1.5 text-sm">
          <div className="font-bold text-navy">Actie</div>
          <div>📦 Plan sorteercapaciteit voor ~{nf(t.high)} per dag.</div>
          {growing.slice(0, 1).map((p) => <div key={p.id}>🏪 Waarschuw {products[p.id].store}: voorraad '{products[p.id].short}' checken.</div>)}
          {cooling.slice(0, 1).map((p) => <div key={p.id}>↩️ '{products[p.id].short}' koelt af: retourrisico.</div>)}
        </div>
      </div>

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 lg:col-span-4 card p-4">
          <h2 className="font-extrabold text-lg text-navy">Grootste producten</h2>
          <div className="text-xs text-slate-500 mb-2">verwachte bestellingen per dag</div>
          <ol className="divide-y divide-slate-100">
            {list.map((p, i) => (
              <li key={p.id}>
                <button onClick={() => setSel(p.id)} className={`w-full text-left py-2.5 px-2 rounded-xl flex items-center gap-3 ${p.id === id ? 'bg-oranje-50 ring-2 ring-oranje' : 'hover:bg-slate-50'}`}>
                  <span className="w-5 text-slate-400 font-bold text-sm">{i + 1}</span>
                  <div className="flex-1 min-w-0"><div className="font-semibold text-sm truncate">{products[p.id].short}</div><div className="text-xs text-slate-500 truncate">{products[p.id].brand}</div></div>
                  <div className="text-lg font-black text-navy w-14 text-right">{smart(p.mid)}</div>
                  <MBadge phase={p.phase} />
                </button>
              </li>
            ))}
          </ol>
        </div>
        <div className="col-span-12 lg:col-span-8"><Detail id={id} dayIdx={dayIdx} /></div>
      </div>

      <div className="card p-4">
        <More label="Terugspelen: wat voorspelde het model op eerdere dagen?">
          <div className="flex gap-1 flex-wrap">
            {momentum.days.map((d, i) => (
              <button key={d.date} onClick={() => setDayIdx(i)}
                className={`px-3 py-2 rounded-lg text-sm font-semibold border ${i === dayIdx ? 'bg-oranje text-white border-oranje' : 'border-slate-200 hover:bg-slate-50'}`}>
                {fmtDay(d.date)}
              </button>
            ))}
          </div>
          <div className="text-xs text-slate-500 mt-2">
            Elke voorspelling gebruikt alleen data tot en met die dag. Nu gekozen: <b>{fmtDay(day.date)}</b>, model volgende week ≈ {nf(day.fit.ratio, 2)}× deze week
            (bandbreedte {nf(day.fit.ratio_low, 2)}–{nf(day.fit.ratio_high, 2)}×), geschat op {day.fit_note}. Bezorgers: aanname ~150 pakketten per bezorger per dag. VS-data, dus dit laat de methode zien, geen NL-volumes.
          </div>
        </More>
      </div>
    </div>
  )
}

export function MomentumInsight() {
  const m = momentum.model, v = momentum.validation, vl = momentum.validation_log, c = momentum.causal_check
  const pts = momentum.scatter.filter((s) => s.x > 0 && s.y > 0).map((s) => ({ x: s.x, y: s.y, name: products[s.id].short }))
  return (
    <div className="card p-5">
      <div className="flex items-start justify-between gap-2">
        <h2 className="font-extrabold text-xl text-navy">Wat wél voorspelt: de verkoop van vorige week</h2>
        <span className="chip bg-emerald-100 text-emerald-800">bevestigd</span>
      </div>
      <p className="mt-1">
        Volgers, likes, merkvideo's, kortingen en reviews voorspelden <b>niets</b>. De verkoop van vorige week wel:
        <b> volgende week ≈ {nf(momentum.ratio_model.mid, 1)}× deze week</b>. Een hype koelt dus zo'n {nf(100 * (1 - momentum.ratio_model.mid))}% per week af.
      </p>
      <p className="text-sm text-slate-600 mt-1">Waarom social media niet meetelt: de echte TikTok Shop-hype komt van creator-video's, en die zitten niet in de data. <b>Met creator-data kan de radar verder vooruit kijken.</b></p>
      <div className="grid md:grid-cols-2 gap-4 mt-3">
        <div className="h-64">
          <ResponsiveContainer>
            <ScatterChart margin={{ top: 5, right: 10, bottom: 20, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis type="number" dataKey="x" scale="log" domain={[0.1, 2000]} name="14-20 okt" tick={{ fontSize: 10 }} label={{ value: 'bestellingen/dag 14-20 okt (log)', position: 'bottom', fontSize: 11 }} allowDataOverflow />
              <YAxis type="number" dataKey="y" scale="log" domain={[0.1, 2000]} name="20-27 okt" tick={{ fontSize: 10 }} allowDataOverflow />
              <ZAxis range={[30, 30]} />
              <Tooltip formatter={(val) => smart(val)} cursor={{ strokeDasharray: '3 3' }} />
              <Scatter data={pts} fill="#FF6200" fillOpacity={0.6} />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
        <div className="space-y-2 content-start">
          <div className="text-xs text-slate-500">Elke stip is een product. Op een rechte lijn = vorige week voorspelt volgende week.</div>
          <div className="grid grid-cols-2 gap-2">
            {[
              [`${nf(100 * v.within_2x)}%`, 'van de producten goed voorspeld (binnen 2×)'],
              [`${v.top10_overlap}/10`, 'top-10 goed voorspeld'],
            ].map(([a, b]) => <div key={b} className="rounded-lg bg-slate-50 p-3"><div className="font-black text-navy text-2xl">{a}</div><div className="text-xs text-slate-500">{b}</div></div>)}
          </div>
          <More label="Alle cijfers en de formule">
            <div className="text-sm text-slate-700 space-y-1">
              <div>Formule: log(1 + volgende week) = <b>{nf(m.a, 2)}</b> × log(1 + deze week) + <b>{nf(m.b, 2)}</b>, R² = <b>{nf(m.r2, 2)}</b> ({m.n} producten).</div>
              <div>Voor pakketten gebruiken we de simpele versie ({nf(momentum.ratio_model.mid, 2)}×), want de log-versie onderschat grote verkopers (totaal {nf(vl.total_predicted)} voorspeld tegen {nf(v.total_actual)} echt).</div>
              <div>Totaal voorspeld / echt: <b>{nf(v.total_predicted)} / {nf(v.total_actual)}</b> per dag.</div>
              <div>Eerlijke test, voorspeld op {fmtDate(c.date)} met alleen data tot die dag: <b>{nf(100 * c.within_2x)}%</b> binnen 2×.</div>
            </div>
          </More>
        </div>
      </div>
      <div className="text-xs text-slate-500 mt-2">Let op: maar 13 schone dagen, dus één week-op-week test. Een eerste schatting, geen bewezen model.</div>
    </div>
  )
}
