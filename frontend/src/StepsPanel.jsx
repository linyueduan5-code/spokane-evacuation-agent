import { Check, ChevronDown, ChevronRight, ShieldAlert } from 'lucide-react'
import { useState } from 'react'

const pretty = (value) => JSON.stringify(value, null, 2)

export default function StepsPanel({ steps = [] }) {
  const [open, setOpen] = useState({ 0: true })
  if (!steps.length) return <div className="empty-steps">Run an analysis to see tool orchestration.</div>

  return (
    <div className="steps-list">
      {steps.map((step, index) => {
        const expanded = !!open[index]
        return (
          <article className={`step-card ${step.status}`} key={`${step.tool}-${index}`}>
            <button className="step-title" onClick={() => setOpen((old) => ({ ...old, [index]: !expanded }))}>
              <span className="step-index">{String(index + 1).padStart(2, '0')}</span>
              <span className="step-icon">{step.status === 'ok' ? <Check size={15} /> : <ShieldAlert size={15} />}</span>
              <span className="step-name">{step.tool}</span>
              <span className={`step-origin ${step.origin}`}>{step.origin?.replace('_', ' ')}</span>
              <span className="step-time">{step.elapsed_ms} ms</span>
              {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
            </button>
            {expanded && (
              <div className="step-detail">
                <label>INPUT</label><pre>{pretty(step.input)}</pre>
                <label>OUTPUT</label><pre>{pretty(step.output)}</pre>
              </div>
            )}
          </article>
        )
      })}
    </div>
  )
}
