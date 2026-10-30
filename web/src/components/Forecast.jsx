import { useState } from 'react'
import {
  Area, Bar, BarChart, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from 'recharts'
import { DATES, fmtDate, fmtDay, nf, products, smart } from '../lib.js'
import momentum from '../data/momentum.json'

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
  const base = `Verwacht ${smart(p.low)}–${smart(p.high)} bestellingen per dag volgende week (midden ${smart(p.mid)}).`
  if (p.phase === 'afkoelend') return `${base} Dit product koelt af, dus houd rekening met retouren.`
  if (p.phase === 'groeiend') return `${base} De verkoop groeit: waarschuw de webshop voor de voorraad.`
  if (p.phase === 'stabiel') return `${base} Stabiel: normale capaciteit.`
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
          <div className="text-xs text-slate-500">{products[id].brand} · {products[id].type_label} · {p.parcel_size}</div>
          <h2 className="font-extrabold text-xl text-navy">{products[id].short}</h2>
        </div>
        <MBadge phase={p.phase} />
      </div>
      <div className="mt-3 rounded-xl bg-navy-50 p-3 text-sm">{sentence(p)}
        <div className="text-xs text-slate-500 mt-1">Afgelopen week {smart(p.this_week)} per dag{p.ratio != null ? ` · week-op-week ×${nf(p.ratio, 2)}` : ''}</div>
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
      <div className="text-[11px] text-slate-500">Blauw = verkocht · oranje vlak = verwachte bandbreedte (25-75% van de echte uitkomsten) · grijs = achteraf</div>
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
  return (
    <div className="space-y-4">
      <div className="card p-4 flex items-center gap-4 flex-wrap">
        <div>
          <div className="text-xs uppercase tracking-wide text-slate-500 font-semibold">Voorspelling gemaakt op</div>
          <div className="text-2xl font-extrabold text-navy">{fmtDay(day.date)}</div>
        </div>
        <div className="flex gap-1">
          {momentum.days.map((d, i) => (
            <button key={d.date} onClick={() => setDayIdx(i)}
              className={`px-3 py-2 rounded-lg text-sm font-semibold border ${i === dayIdx ? 'bg-oranje text-white border-oranje' : 'border-slate-200 hover:bg-slate-50'}`}>
              {fmtDate(d.date)}
            </button>
          ))}
        </div>
        <div className="text-xs text-slate-500 flex-1 min-w-[260px]">
          Alleen data t/m die dag. Model: volgende week ≈ <b>{nf(day.fit.ratio, 2)}×</b> deze week (bandbreedte {nf(day.fit.ratio_low, 2)}–{nf(day.fit.ratio_high, 2)}×), geschat op {day.fit_note}.
        </div>
      </div>
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 xl:col-span-4 card p-4">
          <h2 className="font-extrabold text-lg text-navy">Watchlist: verwachte bestellingen</h2>
          <div className="text-xs text-slate-500 mb-2">per dag, komende week</div>
          <ol className="divide-y divide-slate-100">
            {list.map((p, i) => (
              <li key={p.id}>
                <button onClick={() => setSel(p.id)} className={`w-full text-left py-2 px-2 rounded-xl flex items-center gap-3 ${p.id === id ? 'bg-oranje-50 ring-2 ring-oranje' : 'hover:bg-slate-50'}`}>
                  <span className="w-5 text-slate-400 font-bold text-sm">{i + 1}</span>
                  <div className="w-20 text-right"><div className="text-xl font-black text-navy">{smart(p.mid)}</div><div className="text-[10px] text-slate-400">{smart(p.low)}–{smart(p.high)}</div></div>
                  <div className="flex-1 min-w-0"><div className="font-semibold text-sm truncate">{products[p.id].short}</div><div className="text-xs text-slate-500 truncate">{products[p.id].brand} · nu {smart(p.this_week)}/dag</div></div>
                  <MBadge phase={p.phase} />
                </button>
              </li>
            ))}
          </ol>
        </div>
        <div className="col-span-12 xl:col-span-5"><Detail id={id} dayIdx={dayIdx} /></div>
        <div className="col-span-12 xl:col-span-3 card p-4">
          <h2 className="font-extrabold text-lg text-navy">Pakketten komende week</h2>
          <div className="text-xs text-slate-500">alle producten · 1 bestelling = 1 pakket · VS-data (methode, geen NL-volumes)</div>
          <div className="text-4xl font-black text-oranje mt-2">{nf(t.mid)}</div>
          <div className="text-xs text-slate-500">pakketten per dag verwacht ({nf(t.low)}–{nf(t.high)})</div>
          {day.actual_total != null && (
            <div className="text-xs mt-1">Achteraf: <b>{nf(day.actual_total)}</b> per dag (over {day.actual_window_days} dagen)</div>
          )}
          <div className="h-36 mt-2">
            <ResponsiveContainer>
              <BarChart data={Object.entries(day.by_size).map(([k, v]) => ({ k, v }))} layout="vertical">
                <XAxis type="number" hide /><YAxis type="category" dataKey="k" width={90} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => nf(v)} /><Bar dataKey="v" name="Pakketten/dag" fill="#001E82" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="space-y-1.5 text-sm mt-2">
            <div>📦 Plan sorteercapaciteit voor ~{nf(t.high)} pakketten per dag (bovenkant bandbreedte).</div>
            <div>🚚 Dat is ~{Math.ceil(t.mid / 150)} bezorgers (aanname ~150 pakketten per bezorger per dag).</div>
            {growing.map((p) => <div key={p.id}>🏪 Waarschuw {products[p.id].store}: '{products[p.id].short}' groeit, check de voorraad.</div>)}
            {cooling.map((p) => <div key={p.id}>↩️ '{products[p.id].short}' koelt af: retourrisico (schatting), track & trace toont gebruikstips.</div>)}
          </div>
        </div>
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
      <p className="text-sm mt-1">
        Volgers, likes, merkvideo's, kortingen en reviews voorspelden niets. De eigen verkoop van vorige week wel:
        log(1 + volgende week) = <b>{nf(m.a, 2)}</b> × log(1 + deze week) + <b>{nf(m.b, 2)}</b> (R² = <b>{nf(m.r2, 2)}</b>, {m.n} producten).
        Voor pakketten gebruiken we de simpele versie: <b>volgende week ≈ {nf(momentum.ratio_model.mid, 2)}× deze week</b>, want de log-versie
        onderschat grote verkopers (totaal {nf(vl.total_predicted)} voorspeld tegen {nf(v.total_actual)} echt). Hype koelt dus ~{nf(100 * (1 - momentum.ratio_model.mid))}% per week af.
        Waarom social media niet meetelt: de echte TikTok Shop-hype komt van creator-video's, en die zitten niet in de data. <b>Met creator-data kan de radar verder vooruit kijken.</b>
      </p>
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
        <div className="grid grid-cols-2 gap-2 content-start">
          {[
            [nf(v.r2, 2), 'R² (14-20 → 20-27 okt)'],
            [`${nf(100 * v.within_2x)}%`, `binnen 2× van echt (${v.n_active} producten ≥1/dag)`],
            [`${v.top10_overlap}/10`, 'top-10 voorspeld = top-10 echt'],
            [`${nf(v.total_predicted)} / ${nf(v.total_actual)}`, 'totaal voorspeld / echt per dag'],
            [`${nf(100 * c.within_2x)}%`, `binnen 2×, voorspeld op ${fmtDate(c.date)} met alleen data tot die dag`],
            [`${nf(100 * (1 - momentum.ratio_model.mid))}%`, 'afkoeling per week (mediaan)'],
          ].map(([a, b]) => <div key={b} className="rounded-lg bg-slate-50 p-2"><div className="font-black text-navy text-lg">{a}</div><div className="text-[11px] text-slate-500">{b}</div></div>)}
        </div>
      </div>
      <div className="text-xs text-slate-500 mt-2">Let op: maar 13 schone dagen, dus één week-op-week test. Een eerste schatting, geen bewezen model.</div>
    </div>
  )
}
