import { useEffect, useMemo, useState } from 'react'
import { Accessibility, AlertTriangle, ArrowUp, BarChart3, CheckCircle2, Clock3, Database, Flame, LocateFixed, PawPrint, Route, ShieldCheck, UserRoundSearch } from 'lucide-react'
import { api } from './api'
import EvalPanel from './EvalPanel'
import MapPanel from './MapPanel'
import StepsPanel from './StepsPanel'

const timelineLabels = ['Aug 1 · 8 PM', 'Aug 6 · Noon', 'Aug 7 · Noon', 'Aug 8 · 8 PM']

function NeedsToggle({ icon, label, active, onClick }) {
  return <button className={`need-toggle ${active ? 'active' : ''}`} onClick={onClick}>{icon}<span>{label}</span></button>
}

function SourceStrip({ response }) {
  const sources = useMemo(() => {
    const values = []
    for (const step of response?.steps || []) {
      const output = Array.isArray(step.output) ? step.output : [step.output]
      for (const item of output) {
        const id = item?.provenance?.source_id || item?.source_id
        if (id && !values.includes(id)) values.push(id)
      }
    }
    return values
  }, [response])
  return <div className="source-strip"><Database size={14} /> Sources this run: {sources.length ? sources.join(' · ') : 'waiting for analysis'}</div>
}

export default function App() {
  const [bootstrap, setBootstrap] = useState(null)
  const [status, setStatus] = useState('connecting')
  const [health, setHealth] = useState(null)
  const [timeline, setTimeline] = useState(0)
  const [context, setContext] = useState({
    address: 'Rifle Club Road, Spokane, WA', lat: 47.753, lon: -117.512,
    at: '2026-08-01T20:00:00-07:00',
    needs: { pets: true, mobility: true, medical: false, service_animal: false },
    contact: 'demo@example.invalid', consent_to_search: false,
  })
  const [response, setResponse] = useState(null)
  const [message, setMessage] = useState('Analyze my situation and find a safe shelter.')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [missingOpen, setMissingOpen] = useState(false)
  const [missing, setMissing] = useState({ name: 'Avery Chen', last_known_location: 'Rifle Club Road', consent: false })
  const [evalOpen, setEvalOpen] = useState(false)
  const [evalBusy, setEvalBusy] = useState(false)
  const [evalReport, setEvalReport] = useState(null)

  useEffect(() => {
    Promise.all([api.bootstrap(), api.health()])
      .then(([data, healthData]) => { setBootstrap(data); setHealth(healthData); setStatus('ready') })
      .catch(() => setStatus('offline'))
  }, [])

  const updateTimeline = (index) => {
    const next = Number(index)
    setTimeline(next)
    if (bootstrap) setContext((old) => ({ ...old, at: bootstrap.scenario.timeline[next] }))
  }

  const runAnalysis = async () => {
    setBusy(true); setError('')
    try {
      const data = await api.chat({ session_id: 'live-demo', message, context })
      setResponse(data)
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  const runMissing = async () => {
    setBusy(true); setError('')
    try {
      const data = await api.missingPerson({
        session_id: 'live-demo', name: missing.name, last_known_location: missing.last_known_location,
        contact: context.contact, consent: missing.consent, context,
      })
      setResponse(data); setMissingOpen(false)
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  const runEvaluation = async () => {
    setEvalOpen(true); setEvalBusy(true); setError('')
    try { setEvalReport(await api.runEvaluation()) }
    catch (err) { setError(err.message) }
    finally { setEvalBusy(false) }
  }

  const evacLevel = response?.map_state?.evacuation?.level

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand"><span className="brand-mark"><Flame size={19} /></span><span>EMBER</span><small>EVACUATION INTELLIGENCE</small></div>
        <div className="top-actions">
          <button className="eval-trigger" aria-label="Run 40-case evaluation" onClick={runEvaluation}><BarChart3 size={15} /><span>RUN 40-CASE EVALUATION</span></button>
          <div className="system-status"><i className={status} /> Agent: {status === 'ready' ? 'READY' : status.toUpperCase()} <span>{health?.provider === 'deepseek' ? 'DEEPSEEK V4 FLASH' : 'DETERMINISTIC'} · 7 TOOLS</span></div>
        </div>
      </header>

      <section className="workspace">
        <aside className="control-panel">
          <div className="eyebrow">SCENARIO CONTROL</div>
          <h1>Spokane<br /><em>Complex</em></h1>
          <p className="subtitle">A time-aware evacuation replay grounded in public data.</p>

          <div className="control-block">
            <label><LocateFixed size={15} /> LOCATION</label>
            <input value={context.address} onChange={(e) => setContext({ ...context, address: e.target.value })} />
            <div className="coordinates">47.7530° N · 117.5120° W</div>
          </div>

          <div className="control-block">
            <label><Clock3 size={15} /> REPLAY TIME</label>
            <div className="timeline-value">{timelineLabels[timeline]}</div>
            <input className="timeline" type="range" min="0" max="3" step="1" value={timeline} onChange={(e) => updateTimeline(e.target.value)} />
            <div className="timeline-ticks">
              {['AUG 1', 'AUG 6', 'AUG 7', 'AUG 8'].map((label, index) => (
                <button
                  key={label}
                  aria-label={`Set replay time to ${timelineLabels[index]}`}
                  className={timeline === index ? 'active' : ''}
                  onClick={() => updateTimeline(index)}
                >{label}</button>
              ))}
            </div>
          </div>

          <div className="control-block">
            <label>HOUSEHOLD NEEDS</label>
            <div className="needs-grid">
              <NeedsToggle icon={<PawPrint size={17} />} label="Pets" active={context.needs.pets} onClick={() => setContext({ ...context, needs: { ...context.needs, pets: !context.needs.pets } })} />
              <NeedsToggle icon={<Accessibility size={17} />} label="Mobility" active={context.needs.mobility} onClick={() => setContext({ ...context, needs: { ...context.needs, mobility: !context.needs.mobility } })} />
              <NeedsToggle icon={<ShieldCheck size={17} />} label="Medical" active={context.needs.medical} onClick={() => setContext({ ...context, needs: { ...context.needs, medical: !context.needs.medical } })} />
            </div>
          </div>

          <button className="primary-action" disabled={busy || status !== 'ready'} onClick={runAnalysis}>
            {busy ? 'AGENT WORKING…' : <><Route size={18} /> RUN EVACUATION PLAN</>}
          </button>
          <button className="secondary-action" onClick={() => setMissingOpen(!missingOpen)}><UserRoundSearch size={17} /> Synthetic reunification demo</button>

          {missingOpen && <div className="missing-form">
            <input value={missing.name} onChange={(e) => setMissing({ ...missing, name: e.target.value })} placeholder="Synthetic name" />
            <input value={missing.last_known_location} onChange={(e) => setMissing({ ...missing, last_known_location: e.target.value })} placeholder="Last known location" />
            <label className="consent"><input type="checkbox" checked={missing.consent} onChange={(e) => setMissing({ ...missing, consent: e.target.checked })} /> I consent to this synthetic demo search.</label>
            <button disabled={busy} onClick={runMissing}>Run synthetic search</button>
          </div>}

          <div className="privacy-note"><ShieldCheck size={16} /><span><strong>Privacy by design</strong>Personal and check-in records are synthetic and memory-only.</span></div>
        </aside>

        <section className="main-panel">
          <MapPanel bootstrap={bootstrap} response={response} context={context} />

          <div className="results-grid">
            <section className="briefing">
              <div className="section-heading"><span>01</span><div><small>RESIDENT BRIEFING</small><h2>Recommended action</h2></div></div>
              {!response ? (
                <div className="empty-state"><div className="radar"><span /></div><h3>Ready to analyze</h3><p>Run the preset to query evacuation, incident, shelter, route and hazmat data.</p></div>
              ) : (
                <div className={`answer-card ${response.severity}`}>
                  <div className="severity-row">
                    {response.severity === 'danger' ? <AlertTriangle /> : <CheckCircle2 />}
                    <span>{evacLevel ? `EVACUATION LEVEL ${evacLevel}` : response.intent.toUpperCase()}</span>
                  </div>
                  {response.orchestration?.provider === 'deepseek' && <div className="model-badge">MODEL-DRIVEN · {response.orchestration.model_tool_calls} MODEL CALLS · {response.orchestration.guard_tool_calls} GUARD CALLS</div>}
                  {response.answer.split('\n\n').map((paragraph, index) => <p key={index}>{paragraph}</p>)}
                  {response.notices.map((notice, index) => <div className="notice" key={index}>{notice}</div>)}
                </div>
              )}
              {error && <div className="error-box">{error}</div>}
              <div className="message-row"><input value={message} onChange={(e) => setMessage(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && runAnalysis()} /><button onClick={runAnalysis} disabled={busy}><ArrowUp size={18} /></button></div>
              <SourceStrip response={response} />
            </section>

            <section className="reasoning">
              <div className="section-heading"><span>02</span><div><small>ORCHESTRATION TRACE</small><h2>Agent steps</h2></div></div>
              <StepsPanel steps={response?.steps} />
            </section>
          </div>
        </section>
      </section>
      {evalOpen && <EvalPanel report={evalReport} loading={evalBusy} onRun={runEvaluation} onClose={() => setEvalOpen(false)} />}
    </main>
  )
}
