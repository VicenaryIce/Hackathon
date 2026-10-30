import { useState } from 'react'
import Radar from './components/Radar.jsx'
import Insights from './components/Insights.jsx'
import Tracking from './components/Tracking.jsx'
import Forecast from './components/Forecast.jsx'
import { DATES, replay } from './lib.js'

const TABS = [
  { id: 'radar', label: 'Hype Radar', sub: 'voor PostNL operations' },
  { id: 'voorspelling', label: 'Voorspelling', sub: 'bestellingen volgende week' },
  { id: 'inzichten', label: 'Inzichten', sub: 'hypotheses & backtest' },
  { id: 'tt', label: 'Track & Trace', sub: 'voor de klant' },
]

export default function App() {
  const [tab, setTab] = useState('radar')
  // start the replay on the first burst day: the key demo moment
  const firstBurst = replay.findIndex((d) => d.bursts_today.length > 0)
  const [day, setDay] = useState(firstBurst > 0 ? firstBurst : 0)
  const [selected, setSelected] = useState(null)

  return (
    <div className="min-h-screen">
      <header className="bg-navy text-white">
        <div className="max-w-[1500px] mx-auto px-6 py-3 flex items-center gap-6 flex-wrap">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-oranje grid place-items-center text-xl font-black">◎</div>
            <div>
              <div className="font-extrabold text-xl leading-tight">Hype Radar</div>
              <div className="text-xs text-navy-100">Kun je een hype voorspellen voordat die bij je wordt bezorgd?</div>
            </div>
          </div>
          <nav className="flex gap-1 ml-auto">
            {TABS.map((t) => (
              <button key={t.id} onClick={() => setTab(t.id)}
                className={`px-4 py-2 rounded-xl text-left transition ${tab === t.id ? 'bg-white text-navy' : 'hover:bg-white/10'}`}>
                <div className="font-bold text-sm">{t.label}</div>
                <div className={`text-[11px] ${tab === t.id ? 'text-slate-500' : 'text-navy-100'}`}>{t.sub}</div>
              </button>
            ))}
          </nav>
          <span className="chip bg-white/10 text-white">Hackathon-concept · geen officieel PostNL-product</span>
        </div>
      </header>
      <main className="max-w-[1500px] mx-auto px-6 py-5">
        {tab === 'radar' && <Radar day={day} setDay={setDay} selected={selected} setSelected={setSelected} />}
        {tab === 'voorspelling' && <Forecast />}
        {tab === 'inzichten' && <Insights />}
        {tab === 'tt' && <Tracking />}
      </main>
      <footer className="max-w-[1500px] mx-auto px-6 pb-6 text-xs text-slate-400">
        Data: TikTok Shop VS, {DATES[0]} t/m {DATES[DATES.length - 1]} (Hackathon for Good dataset). Aantallen illustreren de
        methode; aanname 1 bestelling = 1 pakket.
      </footer>
    </div>
  )
}
