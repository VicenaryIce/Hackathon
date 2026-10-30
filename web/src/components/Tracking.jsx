import { useEffect, useState } from 'react'
import { DATES, fmtDay, products } from '../lib.js'
import { PhaseBadge } from './Radar.jsx'
import { MBadge, momentumPhase } from './Forecast.jsx'
import { Intro, More } from './Ui.jsx'

// Demo product: the e.l.f. Glow Reviver Lip Oil Stick, the one real hype in the data.
const PID = Object.values(products).find((p) => p.title === 'e.l.f. Glow Reviver Lip Oil Stick').id
const STOPS = ['Besteld', 'Bij de webshop', 'Sorteercentrum', 'Onderweg', 'Bezorgd']

// Placeholder content per hype phase (no real videos, articles or creator names).
const CONTENT = {
  burst: {
    tone: 'bg-oranje text-white', head: '🔥 Je hebt de hype te pakken!',
    sub: 'Dit product gaat nu viraal: duizenden mensen bestelden het deze week.',
    cards: [
      { icon: '▶', kind: 'Unboxing', title: 'Unboxing: zo ziet je pakketje eruit', meta: 'video · 0:45' },
      { icon: '★', kind: 'Waarom iedereen het wil', title: 'Waarom deze lip oil stick overal op je For You staat', meta: 'artikel · 2 min' },
      { icon: '♥', kind: 'Reviews', title: '“Glanzend zonder plakkerig gevoel” en meer reacties', meta: 'reviews' },
      { icon: '?', kind: 'Quiz', title: 'Welke tint past bij jou? Doe de quiz tijdens het wachten', meta: '1 min' },
    ],
  },
  opbouw: {
    tone: 'bg-amber-400 text-navy-900', head: '⚡ Je bent er vroeg bij!',
    sub: 'Dit product is in opkomst. Jij hebt hem straks als een van de eersten.',
    cards: [
      { icon: '▶', kind: 'Eerste indruk', title: 'Eerste indruk: wat maakt dit product anders?', meta: 'video · 1:10' },
      { icon: '?', kind: 'Quiz', title: 'Welke tint past bij jou?', meta: '1 min' },
      { icon: '★', kind: 'Trend', title: 'Waarom iedereen het hierover heeft', meta: 'artikel · 2 min' },
    ],
  },
  afkoeling: {
    tone: 'bg-sky-600 text-white', head: '✨ Haal er alles uit',
    sub: 'De hype is voorbij, het product blijft goed. Zo gebruik je het optimaal (en hoef je niets terug te sturen).',
    cards: [
      { icon: '1', kind: 'Gebruikstip', title: 'Breng aan op schone, droge lippen en laat 30 seconden intrekken', meta: 'tip' },
      { icon: '2', kind: 'Tint te licht of te donker?', title: 'Combineer met een lipliner: zo past elke tint bij je huidskleur', meta: 'video · 0:50' },
      { icon: '3', kind: 'Langer plezier', title: 'Bewaar op kamertemperatuur, niet in de zon of een warme auto', meta: 'tip' },
      { icon: '4', kind: '3 looks', title: '3 manieren om hem te dragen: naturel, glossy en als blush', meta: 'artikel · 2 min' },
    ],
  },
  stabiel: {
    tone: 'bg-navy text-white', head: '📦 Je pakket is onderweg',
    sub: 'Alvast inspiratie voor als het er is.',
    cards: [
      { icon: '1', kind: 'Gebruikstip', title: 'Zo haal je het meeste uit je product', meta: 'tip' },
      { icon: '▶', kind: 'Unboxing', title: 'Unboxing van dit product', meta: 'video · 0:45' },
    ],
  },
}

export default function Tracking() {
  const p = products[PID]
  const t = p.timeline
  const orderable = DATES.map((d, i) => i).filter((i) => ['burst', 'afkoeling', 'opbouw', 'stabiel'].includes(t.phase[i]))
  const [order, setOrder] = useState(orderable.find((i) => t.phase[i] === 'burst') ?? orderable[0])
  const [step, setStep] = useState(1)
  useEffect(() => { setStep(1) }, [order])
  useEffect(() => {
    if (step >= STOPS.length - 1) return
    const id = setTimeout(() => setStep((s) => s + 1), 2600)
    return () => clearTimeout(id)
  }, [step])
  const mp = DATES[order] >= '2026-10-21' ? momentumPhase(PID, DATES[order]) : null
  const phase = mp && mp.phase === 'afkoelend' && t.phase[order] !== 'burst' ? 'afkoeling' : t.phase[order]
  const c = CONTENT[phase] || CONTENT.stabiel
  const delivered = step === STOPS.length - 1
  const deliveryDate = DATES[Math.min(order + 2, DATES.length - 1)]

  return (
    <div className="space-y-4">
    <Intro step="3" title="Blije klant, minder retouren">Zo ziet de klant zijn pakket. Tijdens de hype: hype-content. Als de hype afkoelt: tips om het product te houden.</Intro>
    <div className="grid grid-cols-12 gap-5">
      <div className="col-span-12 lg:col-span-4 space-y-4">
        <div className="card p-4">
          <div className="font-bold text-navy">Wanneer bestelde de klant?</div>
          <div className="text-sm text-slate-600 mb-2">De pagina past zich aan de hype aan.</div>
          <div className="flex flex-wrap gap-1.5">
            {orderable.map((i) => (
              <button key={i} onClick={() => setOrder(i)}
                className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold border ${i === order ? 'bg-navy text-white border-navy' : 'border-slate-200 hover:bg-slate-50'}`}>
                {fmtDay(DATES[i])}
              </button>
            ))}
          </div>
          <div className="mt-3 flex items-center gap-2 text-sm">Hype op die dag: <PhaseBadge phase={phase} /></div>
          <More label="Meer details" className="mt-2">
            {mp && <div className="flex items-center gap-2 text-sm">Weektrend: <MBadge phase={mp.phase} /></div>}
            <div className="text-xs text-slate-500 mt-1">{t.why[order]}</div>
          </More>
        </div>
        <div className="card p-4 text-sm text-slate-700 space-y-2">
          <div className="font-bold text-navy">Waarom dit werkt</div>
          <div>🔥 <b>Tijdens de hype:</b> leuke content maakt het wachten deel van de aankoop.</div>
          <div>↩️ <b>Als de hype afkoelt:</b> gebruikstips, zodat de klant het product houdt.</div>
        </div>
      </div>

      <div className="col-span-12 lg:col-span-8">
        <div className="card overflow-hidden max-w-3xl mx-auto">
          <div className="bg-navy text-white p-5">
            <div className="text-xs text-navy-100">Track & Trace · 3S-DEMO-{String(order + 1).padStart(4, '0')}</div>
            <div className="text-2xl font-extrabold mt-1">{delivered ? 'Bezorgd! 🎉' : `Verwacht: ${fmtDay(deliveryDate)}, 14:00-16:00`}</div>
            <div className="text-sm text-navy-100">{p.short} · {p.brand}</div>
            <div className="mt-4 flex items-center">
              {STOPS.map((s, i) => (
                <div key={s} className="flex-1 flex items-center">
                  <div className={`w-8 h-8 rounded-full grid place-items-center text-sm font-bold shrink-0 transition ${i <= step ? 'bg-oranje text-white' : 'bg-white/15 text-white/60'} ${i === step && !delivered ? 'ring-4 ring-oranje/40 animate-pulse' : ''}`}>
                    {i < step || delivered ? '✓' : i + 1}
                  </div>
                  {i < STOPS.length - 1 && <div className={`h-1 flex-1 mx-1 rounded ${i < step ? 'bg-oranje' : 'bg-white/15'}`} />}
                </div>
              ))}
            </div>
            <div className="flex mt-1 text-[11px] text-navy-100">{STOPS.map((s) => <div key={s} className="flex-1">{s}</div>)}</div>
          </div>

          {delivered ? (
            <div className="p-8 text-center">
              <div className="text-6xl">🎉📦</div>
              <div className="text-3xl font-black text-navy mt-2">Bezorgd!</div>
              <div className="text-slate-600 mt-1">Veel plezier met je {p.short}.</div>
              {phase === 'afkoeling' || phase === 'stabiel' ? (
                <div className="mt-4 rounded-xl bg-sky-50 p-4 text-left text-sm"><b>Eerste keer gebruiken?</b> Bekijk de 30-seconden-uitleg. Tint valt anders uit? Probeer eerst de lipliner-tip voordat je retourneert.</div>
              ) : (
                <div className="mt-4 rounded-xl bg-oranje-50 p-4 text-left text-sm"><b>Deel je unboxing!</b> Je hoort bij de eersten met dit virale product.</div>
              )}
              <button onClick={() => setStep(1)} className="mt-4 px-4 py-2 rounded-xl bg-navy text-white font-semibold">Opnieuw afspelen</button>
            </div>
          ) : (
            <div className="p-5">
              <div className={`rounded-2xl p-4 ${c.tone}`}>
                <div className="text-xl font-extrabold">{c.head}</div><div className="text-sm opacity-90">{c.sub}</div>
              </div>
              <div className="grid sm:grid-cols-2 gap-3 mt-4">
                {c.cards.map((card) => (
                  <div key={card.title} className="rounded-2xl border border-slate-200 p-3 flex gap-3 hover:shadow-md transition">
                    <div className="w-20 h-20 rounded-xl bg-gradient-to-br from-oranje-100 to-navy-100 grid place-items-center text-2xl font-black text-navy shrink-0">{card.icon}</div>
                    <div>
                      <div className="text-[11px] uppercase font-bold text-oranje-600">{card.kind}</div>
                      <div className="font-semibold text-sm leading-snug">{card.title}</div>
                      <div className="text-xs text-slate-400 mt-1">{card.meta} · voorbeeldcontent</div>
                    </div>
                  </div>
                ))}
              </div>
              <button onClick={() => setStep(STOPS.length - 1)} className="mt-4 text-xs text-slate-400 underline">sla over naar bezorging</button>
            </div>
          )}
        </div>
      </div>
    </div>
    </div>
  )
}
