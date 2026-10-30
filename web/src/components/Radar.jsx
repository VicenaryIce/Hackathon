import { useMemo } from 'react'
import {
  Area, Bar, CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { DATES, PHASES, SIGNALS, alarmById, fmtDate, fmtDay, nf, products, replay, smart } from '../lib.js'
import { Intro, More } from './Ui.jsx'

export function PhaseBadge({ phase, big }) {
  const p = PHASES[phase] || PHASES.geen_data
  return <span className={`chip ${p.cls} ${big ? 'text-sm px-3 py-1' : ''}`}>{p.label}</span>
}

const STATUS = {
  afgekapt: { cls: 'bg-red-50 border-red-200 text-red-800', title: 'Verkoopdata onbetrouwbaar',
    text: 'De bron gaf vandaag afgekapte verkoopcijfers door (100% heeft 1 significant cijfer). De radar wacht en roept geen hype.' },
  bronwissel: { cls: 'bg-red-50 border-red-200 text-red-800', title: 'Bronwissel gedetecteerd: massale sprong genegeerd',
    text: 'Alle vergelijkbare producten veranderden tegelijk en 22 prijzen gingen ×1,30. Een naïef systeem ziet een mega-hype; de radar start een nieuwe meetreeks.' },
  opwarmen: { cls: 'bg-slate-100 border-slate-200 text-slate-700', title: 'Radar warmt op',
    text: 'Eerste betrouwbare verkoopmeting. Vanaf morgen ziet de radar trends per product.' },
  live: null,
}

function Slider({ day, setDay }) {
  const d = replay[day]
  return (
    <div className="card p-4 flex items-center gap-4">
      <div className="shrink-0">
        <div className="text-xs uppercase tracking-wide text-slate-500 font-semibold">Speel de dagen af</div>
        <div className="text-2xl font-extrabold text-navy">{fmtDay(d.date)}</div>
      </div>
      <button className="px-3 py-2 rounded-lg bg-slate-100 font-bold disabled:opacity-30" disabled={day === 0} onClick={() => setDay(day - 1)}>◀</button>
      <div className="flex-1">
        <input type="range" min={0} max={replay.length - 1} value={day} onChange={(e) => setDay(+e.target.value)} className="w-full" />
        <div className="flex justify-between text-[11px] text-slate-500 mt-1">
          {replay.map((r, i) => (
            <button key={r.date} onClick={() => setDay(i)} className={`flex flex-col items-center w-6 ${i === day ? 'text-navy font-bold' : ''}`}>
              <span>{new Date(r.date + 'T12:00').getDate()}</span>
              <span className="h-2 w-2 rounded-full mt-0.5" style={{ background:
                r.bursts_today.length ? '#FF6200' : r.status === 'afgekapt' || r.status === 'bronwissel' ? '#ef4444' : r.counts.opbouw ? '#f59e0b' : '#cbd5e1' }} />
            </button>
          ))}
        </div>
      </div>
      <button className="px-3 py-2 rounded-lg bg-oranje text-white font-bold disabled:opacity-30" disabled={day === replay.length - 1} onClick={() => setDay(day + 1)}>▶</button>
      <div className="text-xs text-slate-500 w-36 shrink-0 hidden lg:block"><span className="text-oranje">●</span> hype &nbsp;<span className="text-red-500">●</span> datafout</div>
    </div>
  )
}

function Watchlist({ d, selected, setSelected }) {
  return (
    <div className="card p-4">
      <h2 className="font-extrabold text-lg text-navy">Producten om in de gaten te houden</h2>
      <div className="text-xs text-slate-500 mb-2">Klik op een product voor de uitleg</div>
      {d.watchlist.length === 0 && <div className="text-slate-500 text-sm py-8 text-center">Op deze dag is de verkoopdata niet bruikbaar, dus de radar wacht. Ga een dag verder.</div>}
      <ol className="divide-y divide-slate-100">
        {d.watchlist.map((w, i) => {
          const p = products[w.id]
          const active = selected === w.id
          return (
            <li key={w.id}>
              <button onClick={() => setSelected(w.id)}
                className={`w-full text-left py-2.5 px-2 rounded-xl flex items-center gap-3 transition ${active ? 'bg-oranje-50 ring-2 ring-oranje' : 'hover:bg-slate-50'}`}>
                <span className="w-5 text-slate-400 font-bold text-sm">{i + 1}</span>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-sm truncate">{p.short}</div>
                  <div className="text-xs text-slate-500 truncate">{p.brand} · {smart(w.level)} per dag</div>
                </div>
                <PhaseBadge phase={w.phase} />
              </button>
            </li>
          )
        })}
      </ol>
    </div>
  )
}

function Detail({ id, day }) {
  const p = products[id]
  const t = p.timeline
  const data = useMemo(() => DATES.map((date, i) => {
    const known = t.known_from[i] != null && t.known_from[i] <= day
    return {
      date: fmtDate(date), i,
      sales: known ? t.sales_filled[i] : null,
      future: !known && i > day && t.sales_filled[i] != null ? t.sales_filled[i] : null,
      reviews: i <= day && t.reviews[i] != null && i > 0 && t.reviews[i - 1] != null ? Math.max(0, t.reviews[i] - t.reviews[i - 1]) : null,
      videos: i <= day ? t.video_cadence[i] : null,
      phase: i <= day ? t.phase[i] : null,
    }
  }), [id, day])
  // shade the phases (as the radar saw them, up to today)
  const bands = []
  data.forEach((row, i) => {
    if (!row.phase || !['opbouw', 'burst', 'afkoeling'].includes(row.phase)) return
    const last = bands[bands.length - 1]
    if (last && last.phase === row.phase && last.end === i - 1) last.end = i
    else bands.push({ phase: row.phase, start: i, end: i })
  })
  const sig = t.signals[day]
  const futureAny = data.some((r) => r.future != null)
  return (
    <div className="card p-5">
      <div className="flex items-start gap-4">
        <div className="flex-1 min-w-0">
          <div className="text-xs text-slate-500">{p.brand}</div>
          <h2 className="font-extrabold text-xl text-navy leading-tight">{p.short}</h2>
        </div>
        <PhaseBadge phase={t.phase[day]} big />
      </div>
      <div className="mt-3 rounded-xl bg-navy-50 p-3 text-sm">
        <span className="font-bold text-navy">Wat gebeurt er? </span>{t.why[day]}
        {t.prediction[day] && <div className="mt-1 font-semibold text-oranje-600">➜ {t.prediction[day]}</div>}
      </div>
      <div className="text-xs text-slate-500 mt-3">Verkocht per dag{futureAny ? ' · stippellijn = wat er daarna echt gebeurde' : ''}</div>
      <div className="h-56">
        <ResponsiveContainer>
          <ComposedChart data={data} margin={{ top: 22, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} interval={1} />
            <YAxis tick={{ fontSize: 11 }} width={48} />
            <Tooltip formatter={(v, n) => [smart(v), n]} />
            {bands.map((b, k) => (
              <ReferenceArea key={k} x1={data[b.start].date} x2={data[b.end].date} fill={PHASES[b.phase].dot} fillOpacity={0.15} ifOverflow="extendDomain" />
            ))}
            <ReferenceLine x={data[day].date} stroke="#001E82" strokeDasharray="4 2" label={{ value: 'vandaag', fontSize: 11, fill: '#001E82', position: 'top' }} />
            <Area type="linear" dataKey="sales" name="Verkocht per dag" stroke="#FF6200" fill="#FF6200" fillOpacity={0.25} strokeWidth={3} connectNulls />
            {futureAny && <Line type="linear" dataKey="future" name="Wat er daarna gebeurde" stroke="#94a3b8" strokeDasharray="5 4" dot={false} connectNulls />}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <More label="Meer details: hype score en signalen" className="mt-2">
        <div className="text-sm mb-2">Hype score: <b className="text-oranje">{t.score[day]}/100</b> <span className="text-slate-500">(55% verkoop, 20% reviews, 15% video's, 10% likes)</span></div>
        <div className="h-24">
          <ResponsiveContainer>
            <ComposedChart data={data} margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
              <XAxis dataKey="date" hide />
              <YAxis yAxisId="r" tick={{ fontSize: 10 }} width={48} allowDecimals={false} />
              <YAxis yAxisId="v" orientation="right" hide />
              <Tooltip formatter={(v, n) => [smart(v), n]} />
              <Bar yAxisId="r" dataKey="reviews" name="Nieuwe reviews" fill="#001E82" barSize={10} />
              <Line yAxisId="v" type="stepAfter" dataKey="videos" name="Merk-video's per dag" stroke="#10b981" strokeWidth={2} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <div className="flex gap-3 text-[11px] text-slate-500 mt-1">
          <span><b className="text-navy">■</b> nieuwe reviews</span><span><b className="text-emerald-500">—</b> merk-video's per dag</span>
        </div>
        <div className="flex flex-wrap gap-2 mt-3">
          {SIGNALS.map((s, k) => (
            <span key={s} className={`chip ${sig[k] ? 'bg-oranje-100 text-oranje-600' : 'bg-slate-100 text-slate-400'}`}>{sig[k] ? '✓' : '·'} {s}</span>
          ))}
        </div>
        <div className="text-xs text-slate-500 mt-2">{p.type_label} · {p.parcel_size}{p.price ? ` · $${nf(p.price, 2)}` : ''}</div>
      </More>
    </div>
  )
}

function Forecast({ d }) {
  const f = d.forecast
  const rows = f.days.map((date, k) => ({
    date: fmtDate(date), normaal: f.normal[k], extra: f.extra[k],
    werkelijk: f.actual[k],
  }))
  const peak = Math.max(...f.extra)
  const icon = (k) => ({ sorteren: '📦', bezorgers: '🚚', webshop: '🏪', brievenbus: '✉️', retour: '↩️', data: '🛡️', rust: '✅' }[k] || '•')
  return (
    <div className="card p-4">
      <h2 className="font-extrabold text-lg text-navy">Wat moet PostNL doen?</h2>
      <div className="flex items-baseline gap-2 mt-1">
        <div className="text-4xl font-black text-oranje">+{nf(peak)}</div>
        <div className="text-sm text-slate-600">extra pakketten per dag (piek)</div>
      </div>
      <div className="mt-3 space-y-2">
        {d.actions.slice(0, 3).map((a, k) => (
          <div key={k} className="flex gap-2 text-sm"><span>{icon(a.kind)}</span><span>{a.text}</span></div>
        ))}
      </div>
      <More label="Bekijk de pakketprognose" className="mt-3">
        <div className="text-xs text-slate-500 mb-1">Komende 7 dagen · normaal niveau {nf(f.normal[0])} · bezorging 1-3 dagen na bestelling</div>
        <div className="h-40">
          <ResponsiveContainer>
            <ComposedChart data={rows} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} width={48} />
              <Tooltip formatter={(v, n) => [nf(v), n]} />
              <Bar dataKey="normaal" stackId="a" fill="#D6DDF2" name="Normaal" />
              <Bar dataKey="extra" stackId="a" fill="#FF6200" name="Extra door hype" radius={[4, 4, 0, 0]} />
              <Line dataKey="werkelijk" stroke="#001E82" strokeDasharray="4 3" name="Werkelijk (achteraf)" dot={{ r: 3 }} connectNulls={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        {d.actions.length > 3 && (
          <div className="mt-2 space-y-1.5">
            {d.actions.slice(3).map((a, k) => (
              <div key={k} className="flex gap-2 text-sm"><span>{icon(a.kind)}</span><span>{a.text}</span></div>
            ))}
          </div>
        )}
      </More>
    </div>
  )
}

function Alarms({ day, setSelected }) {
  const upto = replay[day].date
  const items = Object.values(alarmById).filter((a) => a.date <= upto).reverse()
  const top = items.filter((a) => a.severity !== 'laag').slice(0, 4)
  const today = new Set(replay[day].alarms_today)
  return (
    <div className="card p-4">
      <h2 className="font-extrabold text-lg text-navy">🛡️ Nep-hypes weggefilterd</h2>
      <div className="text-sm text-slate-600 mt-1"><b className="text-navy text-2xl font-black">{items.length}</b> valse alarmen tot en met {fmtDate(upto)}, zoals datafouten en gekochte groei.</div>
      {top.length > 0 && (
        <More label="Bekijk voorbeelden" className="mt-2">
          <div className="space-y-2">
            {top.map((a) => (
              <div key={a.id} className={`rounded-xl border p-3 text-sm ${today.has(a.id) ? 'border-red-300 bg-red-50' : 'border-slate-200'}`}>
                <div className="flex justify-between gap-2"><b>{a.title}</b><span className="text-xs text-slate-500 shrink-0">{fmtDate(a.date)}</span></div>
                <div className="text-xs mt-1"><span className="font-semibold text-red-600">Lijkt: </span>{a.naive}</div>
                <div className="text-xs mt-0.5"><span className="font-semibold text-emerald-700">Echt: </span>{a.real}</div>
                {a.product_id && <button onClick={() => setSelected(a.product_id)} className="text-xs text-navy underline mt-1">bekijk product</button>}
              </div>
            ))}
          </div>
        </More>
      )}
    </div>
  )
}

export default function Radar({ day, setDay, selected, setSelected }) {
  const d = replay[day]
  const status = STATUS[d.status]
  const sel = selected || d.watchlist[0]?.id || 'p190'
  return (
    <div className="space-y-4">
      <Intro step="1" title="Welke producten gaan nu viraal?">De radar kijkt elke dag naar de verkoop en waarschuwt zodra een product hard gaat lopen. Speel de dagen af om het te zien gebeuren.</Intro>
      <Slider day={day} setDay={setDay} />
      {status && (
        <div className={`rounded-2xl border p-4 ${status.cls}`}>
          <div className="font-extrabold">{status.title}</div><div className="text-sm">{status.text}</div>
        </div>
      )}
      {d.bursts_today.length > 0 && (
        <div className="rounded-2xl p-4 bg-oranje text-white flex items-center gap-4">
          <span className="text-3xl">🔥</span>
          <div>
            <div className="font-extrabold text-lg">Burst gedetecteerd: {d.bursts_today.map((id) => products[id].short).join(' + ')}</div>
            <div className="text-sm text-white/90">Bestellingen van vandaag worden over 1-3 dagen bezorgd: PostNL ziet de pakketgolf aankomen voordat hij er is.</div>
          </div>
        </div>
      )}
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 lg:col-span-4"><Watchlist d={d} selected={sel} setSelected={setSelected} /></div>
        <div className="col-span-12 lg:col-span-8 space-y-4">
          <Detail id={sel} day={day} />
          <div className="grid md:grid-cols-2 gap-4">
            <Forecast d={d} />
            <Alarms day={day} setSelected={setSelected} />
          </div>
        </div>
      </div>
    </div>
  )
}
