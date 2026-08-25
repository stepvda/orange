import { useEffect, useRef, useState } from 'react'
import type { Topic } from '../types'
import { HelpButton } from './Help'

/** Visual stage-gate board and per-role assessment (FR-25, §4.10).
 *
 * §4.10 recommends "A + B + D": run the stage gate as the backbone because it
 * produces accountability, and add distributed assessment (model C) once there
 * are enough users for the ratings to mean anything.
 *
 * Two design rules carried from the document:
 *
 *  - Each role rates ONLY its own axis. A salesperson is authoritative about
 *    whether customers are asking, and is not being asked to re-judge evidence.
 *  - Ratings are 0-5 with WRITTEN ANCHORS, not a slider. §4.7.4: "People are
 *    unreliable at rating a topic 73 out of 100 and reliable at saying which of
 *    two topics they would rather take into a meeting."
 */

export interface WorkflowMeta {
  stages: { id: string; label: string; owner_role: string | null }[]
  terminal_stages: { id: string; label: string }[]
  role_axis: Record<string, string>
  axis_labels: Record<string, string>
  anchors: Record<string, Record<string, string>>
  divergence_threshold: number
  conviction_ranking_weight: number
}

/** A board card is a PROJECTION of a topic, not the whole thing: the endpoint
 *  sends what a card shows and nothing else, because shipping every topic's
 *  links and score components made the board a two-megabyte response. Selecting
 *  a card loads the full topic into the detail pane. */
export type BoardCard = Pick<Topic,
  'id' | 'statement' | 'labels' | 'triple' | 'horizon' | 'state' | 'portfolio_distance' |
  'evidence_gap_warning' | 'signal_count' | 'workflow' | 'divergence' | 'market_size_summary' |
  'has_brief' | 'competition'> & {
  attractiveness: { score: number } | null
  right_to_win: { score: number } | null
  conviction: { score: number | null; assessed: number } | null
}

export interface BoardData {
  stages: { id: string; label: string; owner_role: string | null; count: number; topics: BoardCard[] }[]
  axes: { id: string; label: string; role: string; anchors: Record<string, string> }[]
}

export function AssessmentWidget({ topic, role, meta, onSubmitted, onHelp }: {
  topic: Topic
  role: string
  meta: WorkflowMeta
  onSubmitted: () => void
  onHelp?: (topic: string) => void
}) {
  const axis = meta.role_axis[role]
  const anchors = meta.anchors[axis] ?? {}
  const [rating, setRating] = useState<number | null>(null)
  const [hovered, setHovered] = useState<number | null>(null)
  const [confidence, setConfidence] = useState(3)
  const [rationale, setRationale] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => { setRating(null); setRationale(''); setSaved(false) }, [topic.id, role])

  const shown = hovered ?? rating
  const conviction = topic.conviction
  const mine = conviction?.axes?.[axis]

  const submit = async () => {
    if (rating === null) return
    setSaving(true)
    try {
      await fetch(`/api/topics/${topic.id}/assessment`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          role, rating, confidence,
          rationale: rationale.trim() || null,
          // A real deployment takes this from the session; the prototype is
          // explicit about it rather than pretending to know who you are.
          author: `${role}@demo`,
        }),
      })
      setSaved(true)
      onSubmitted()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="assess-box">
      <div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '.06em',
                    color: 'var(--text-muted)', marginBottom: 7 }}>
        Your assessment · {meta.axis_labels[axis]}
        {onHelp && <HelpButton topic="assessment" onOpen={onHelp} />}
      </div>

      <div className="rating" onMouseLeave={() => setHovered(null)}>
        {[0, 1, 2, 3, 4, 5].map((n) => (
          <button key={n}
                  aria-pressed={rating === n}
                  onMouseEnter={() => setHovered(n)}
                  onClick={() => { setRating(n); setSaved(false) }}>
            {n}
          </button>
        ))}
      </div>
      {/* The anchor for the level under the cursor — this is what makes a 0-5
          scale mean the same thing to two different people. */}
      <div className="anchor-note">
        {shown !== null ? anchors[String(shown)] : 'Hover a level to see what it means.'}
      </div>

      <label style={{ fontSize: 11, color: 'var(--text-muted)' }}>
        Confidence
        <select value={confidence} onChange={(e) => setConfidence(Number(e.target.value))}
                style={{ marginLeft: 6, fontSize: 11, padding: '2px 4px' }}>
          <option value={1}>1 — guessing</option>
          <option value={2}>2 — low</option>
          <option value={3}>3 — moderate</option>
          <option value={4}>4 — high</option>
          <option value={5}>5 — certain</option>
        </select>
      </label>

      <textarea
        placeholder="Why? (optional, but this is the most useful text in the system)"
        value={rationale}
        onChange={(e) => setRationale(e.target.value)}
        rows={2}
        style={{
          width: '100%', marginTop: 8, fontFamily: 'inherit', fontSize: 12,
          padding: 6, borderRadius: 'var(--radius-sm)',
          border: '1px solid var(--border-strong)',
          background: 'var(--surface-1)', color: 'var(--text-primary)', resize: 'vertical',
        }} />

      <button style={{ marginTop: 8 }} disabled={rating === null || saving} onClick={submit}>
        {saving ? 'Saving…' : saved ? 'Saved ✓' : 'Submit assessment'}
      </button>

      {mine && (
        <div style={{ marginTop: 10, fontSize: 11.5, color: 'var(--text-secondary)' }}>
          Team so far: <b style={{ fontFamily: 'var(--mono)' }}>{mine.score}</b>/100 from {mine.n} rating(s)
          {mine.contested && (
            <span style={{ color: 'var(--status-warning)' }}>
              {' '}· contested (spread {mine.rater_spread}) — the criterion may be ill-defined, not the topic
            </span>
          )}
          {mine.voices?.filter((v) => v.rationale).map((v, i) => (
            <div className="voice" key={i}>
              <div className="who">{v.author} · rated {v.rating}, confidence {v.confidence}</div>
              {v.rationale}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function ConvictionPanel({ topic }: { topic: Topic }) {
  const conviction = topic.conviction
  if (!conviction || !conviction.assessed) {
    return (
      <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: 0 }}>
        No role has assessed this topic yet. Conviction is a third quantity beside
        attractiveness and right-to-win — it never changes either of them, it only
        changes what surfaces first for each role.
      </p>
    )
  }
  return (
    <div>
      {Object.entries(conviction.axes).map(([axis, block]) => (
        <div className="component" key={axis}>
          <div>
            <div className="component-label">
              {block.label}
              <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--mono)', fontSize: 10 }}>
                {' '}n={block.n}{block.contested ? ' · contested' : ''}
              </span>
            </div>
            <div className="component-track">
              <div className="component-fill"
                   style={{ width: `${block.score}%`, background: 'var(--ord-3)' }} />
            </div>
          </div>
          <div className="component-num">{block.score.toFixed(0)}</div>
        </div>
      ))}
      {conviction.roles_missing.length > 0 && (
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>
          Not yet assessed by: {conviction.roles_missing.join(', ')}
        </div>
      )}
      {topic.divergence && (
        <div className="warning-box" style={{ marginTop: 10 }}>
          <span aria-hidden>⚠</span>
          <span>
            <b>Review trigger.</b>{' '}
            {topic.divergence.flags.map((f) => f.reading).join(' ')}
          </span>
        </div>
      )}
    </div>
  )
}

export function StageControl({ topic, role, meta, onMoved }: {
  topic: Topic; role: string; meta: WorkflowMeta; onMoved: () => void
}) {
  const [busy, setBusy] = useState(false)
  const wf = topic.workflow
  if (!wf) return null

  const move = async (to: string) => {
    setBusy(true)
    try {
      await fetch(`/api/topics/${topic.id}/stage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ to_stage: to, actor: `${role}@demo`, actor_role: role }),
      })
      onMoved()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <div style={{ fontSize: 12.5, marginBottom: 7 }}>
        Stage <b>{wf.stage_label}</b>
        <span style={{ color: 'var(--text-muted)' }}>
          {' '}· owned by {wf.owner_role ?? 'unassigned'} · {wf.age_in_stage_days}d in stage
        </span>
        {wf.stalled && (
          <span style={{ color: 'var(--status-warning)' }}> · stalled</span>
        )}
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {wf.next_stage && (
          <button disabled={busy} onClick={() => move(wf.next_stage!)}>
            Advance → {meta.stages.find((s) => s.id === wf.next_stage)?.label}
          </button>
        )}
        {meta.terminal_stages.map((t) => (
          <button key={t.id} disabled={busy} onClick={() => move(t.id)}
                  style={{ fontSize: 11.5 }}>
            {t.label}
          </button>
        ))}
      </div>
    </div>
  )
}

/** The MIME-ish key the board drags under.
 *
 * A custom type rather than `text/plain`: the drop zone can then ask, during
 * `dragover`, whether what is being dragged is one of its own cards — and say
 * no to a file, a selection of text, or a link from another window before the
 * user has committed to the drop. `text/plain` is set as well, so dragging a
 * card into an editor still yields its id rather than nothing. */
const DRAG_TYPE = 'application/x-radar-space'

export function Board({ board, selectedId, onSelect, onExplain, onMove }: {
  board: BoardData; selectedId: string | null; onSelect: (id: string) => void
  onExplain?: (id: string) => void
  /** Move a space to another stage. Absent for a read-only board — the cards
   *  then keep their click and lose their drag, rather than offering a gesture
   *  that quietly fails. */
  onMove?: (topicId: string, toStage: string) => void
}) {
  // Which column the pointer is currently over, so it can say so. Tracked with
  // a counter per column rather than a boolean: `dragleave` fires when the
  // pointer crosses onto a CHILD of the column, so a boolean flickers off every
  // time the cursor passes over a card inside the column it is already in.
  const [overStage, setOverStage] = useState<string | null>(null)
  const depth = useRef(0)
  const [dragging, setDragging] = useState<string | null>(null)

  const stages = board.stages.filter(
    (s) => !['parked', 'rejected'].includes(s.id) || s.count > 0)

  const endDrag = () => { depth.current = 0; setOverStage(null); setDragging(null) }

  /** Alt + arrow, for anyone not using a mouse.
   *
   * Drag and drop has no keyboard equivalent, and the stage gate is the one
   * place in this interface where the gesture CHANGES something rather than
   * rearranging a view. Alt is the modifier because the arrows alone belong to
   * the scroll container the cards sit in. */
  const onCardKey = (event: React.KeyboardEvent, topicId: string, index: number) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault(); onSelect(topicId); return
    }
    if (!onMove || !event.altKey) return
    const step = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
    if (!step) return
    const next = stages[index + step]
    if (!next) return
    event.preventDefault()
    onMove(topicId, next.id)
  }

  return (
    <div className="board" onDragEnd={endDrag}>
      {stages.map((stage, stageIndex) => (
        <div className={`board-col${overStage === stage.id ? ' drop-over' : ''}`} key={stage.id}
             onDragEnter={(e) => {
               if (!onMove || !e.dataTransfer.types.includes(DRAG_TYPE)) return
               depth.current += 1
               setOverStage(stage.id)
             }}
             onDragOver={(e) => {
               if (!onMove || !e.dataTransfer.types.includes(DRAG_TYPE)) return
               // Without this the browser refuses the drop: the default action
               // for dragover is "this is not a drop target".
               e.preventDefault()
               e.dataTransfer.dropEffect = 'move'
             }}
             onDragLeave={() => {
               depth.current -= 1
               if (depth.current <= 0) { depth.current = 0; setOverStage(null) }
             }}
             onDrop={(e) => {
               const id = e.dataTransfer.getData(DRAG_TYPE)
               endDrag()
               if (!onMove || !id) return
               e.preventDefault()
               // Dropping a card back where it started is not a transition, and
               // recording one would put a no-op in the audit trail the stage
               // gate exists to produce.
               if (stage.topics.some((t) => t.id === id)) return
               onMove(id, stage.id)
             }}>
          <div className="board-head">
            <h4>{stage.label} <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--mono)' }}>
              {stage.count}
            </span></h4>
            {stage.owner_role && <div className="owner">owner: {stage.owner_role}</div>}
          </div>
          <div className="board-body">
            {stage.topics.map((topic) => (
              <div key={topic.id}
                   className={`board-card${topic.workflow?.stalled ? ' stalled' : ''}`
                     + `${topic.divergence ? ' diverging' : ''}`
                     + `${dragging === topic.id ? ' dragging' : ''}`}
                   role="button" tabIndex={0}
                   aria-selected={selectedId === topic.id}
                   title={onMove
                     ? `${topic.id} — drag to another stage, or focus it and press Alt + ← / →`
                     : topic.id}
                   draggable={Boolean(onMove)}
                   onDragStart={(e) => {
                     e.dataTransfer.setData(DRAG_TYPE, topic.id)
                     e.dataTransfer.setData('text/plain', topic.id)
                     e.dataTransfer.effectAllowed = 'move'
                     setDragging(topic.id)
                   }}
                   onKeyDown={(e) => onCardKey(e, topic.id, stageIndex)}
                   onClick={() => onSelect(topic.id)}>
                <div className="bc-id">{topic.id}</div>
                <div>{topic.statement.slice(0, 96)}{topic.statement.length > 96 ? '…' : ''}</div>
                <div className="bc-meta">
                  <span className="badge">A {topic.attractiveness?.score?.toFixed(0) ?? '—'}</span>
                  <span className="badge">W {topic.right_to_win?.score?.toFixed(0) ?? '—'}</span>
                  {topic.conviction?.score != null && (
                    <span className="badge">C {topic.conviction.score.toFixed(0)}</span>
                  )}
                  {topic.divergence && <span className="badge gap">⚠ review</span>}
                  {topic.workflow?.stalled && <span className="badge">stalled</span>}
                  {onExplain && (
                    <button className="help-btn" title="How was this calculated?"
                            aria-label={`How ${topic.id}'s score was calculated`}
                            onClick={(e) => { e.stopPropagation(); onExplain(topic.id) }}>=</button>
                  )}
                </div>
              </div>
            ))}
            {stage.topics.length === 0 && (
              <div className="board-empty">{onMove ? 'Empty — drop a space here' : 'Empty'}</div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
