import { useState } from 'react'
import Radar from './components/Radar.jsx'
import Insights from './components/Insights.jsx'
import Predict from './components/Predict.jsx'
import { DATES, replay } from './lib.js'

// Tabs follow the story of the pitch: predict the parcels → spot the hype live → why we believe it.
const TABS = [
  { id: 'voorspelling', step: '1', label: 'Voorspelling', sub: 'pakketten als het viraal gaat' },
  { id: 'radar', step: '2', label: 'Hype Radar', sub: 'is er nu een hype?' },
  { id: 'inzichten', step: 'i', label: 'Inzichten', sub: 'wat de data zegt' },
]

export default function App() {
  const [tab, setTab] = useState('voorspelling')
  // start the replay on the first burst day: the key demo moment
  const firstBurst = replay.findIndex((d) => d.bursts_today.length > 0)
  const [day, setDay] = useState(firstBurst > 0 ? firstBurst : 0)
  const [selected, setSelected] = useState(null)

  return (
    <div className="min-h-screen">
      <header className="bg-navy text-white">
        <div className="max-w-[1400px] mx-auto px-6 py-3 flex items-center gap-6 flex-wrap">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-oranje grid place-items-center text-xl font-black">◎</div>
            <div>
              <div className="font-extrabold text-xl leading-tight">Hype Radar</div>
              <div className="text-xs text-navy-100">Zie de hype aankomen voordat de pakketten er zijn</div>
            </div>
          </div>
          <nav className="flex gap-1 ml-auto flex-wrap">
            {TABS.map((t) => (
              <button key={t.id} onClick={() => setTab(t.id)}
                className={`px-4 py-2 rounded-xl text-left transition flex items-center gap-2.5 ${tab === t.id ? 'bg-white text-navy' : 'hover:bg-white/10'}`}>
                <span className={`w-6 h-6 rounded-full grid place-items-center text-xs font-black ${tab === t.id ? 'bg-oranje text-white' : 'bg-white/15'}`}>{t.step}</span>
                <span>
                  <span className="block font-bold text-sm">{t.label}</span>
                  <span className={`block text-[11px] ${tab === t.id ? 'text-slate-500' : 'text-navy-100'}`}>{t.sub}</span>
                </span>
              </button>
            ))}
          </nav>
        </div>
      </header>
      <main className="max-w-[1400px] mx-auto px-6 py-6">
        {tab === 'radar' && <Radar day={day} setDay={setDay} selected={selected} setSelected={setSelected} />}
        {tab === 'voorspelling' && <Predict />}
        {tab === 'inzichten' && <Insights />}
      </main>
      <footer className="max-w-[1400px] mx-auto px-6 pb-6 text-xs text-slate-400">
        Hackathon-concept, geen officieel PostNL-product. Data: TikTok Shop VS, {DATES[0]} t/m {DATES[DATES.length - 1]} (Hackathon for Good dataset).
        Aantallen illustreren de methode; aanname 1 bestelling = 1 pakket.
      </footer>
    </div>
  )
}
