import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'
import { HelpButton } from './Help'
import BriefChat from './BriefChat'
import { countryNames } from '../geo'
import type {
  GenerateAnywayRequest, GenerationConstraints, GenerationJob, GenerationMatch,
  GenerationOptions, HypothesisRequest, Meta, Topic,
} from '../types'
import { EMPTY_CONSTRAINTS, constraintCount } from '../types'

/** Ask the radar for more opportunity spaces (FR-06, §4.4).
 *
 * `radar refresh` runs synthesis on a cadence (FR-19). This screen runs the
 * same stage on request, for a stated number of spaces, optionally bounded to a
 * slice of the taxonomy. Three things it is careful about, because each is a
 * place where a generation UI usually lies to its user:
 *
 * 1. IT SHOWS WHAT ALREADY EXISTS THERE. Every filter change refetches the
 *    spaces that already meet the criteria. Asking for five more in a cell that
 *    already holds eleven is a decision someone should get to make with the
 *    eleven on screen, and under DR-03 a run landing on an existing taxonomy
 *    triple refreshes it rather than creating anything.
 *
 * 2. IT DISTINGUISHES THE FILTERS IT CAN ENFORCE FROM THE ONE IT CANNOT.
 *    Vertical, domain and geography are checked against every candidate
 *    server-side. Horizon is DERIVED from the evidence after scoring (§4.8:
 *    "derived rather than judged, because derived classifications are
 *    explainable and consistent"), so it steers the run and is reported
 *    afterwards, and the screen says exactly that rather than implying a
 *    guarantee it has no power to keep.
 *
 * 3. IT EXPLAINS A SHORTFALL. §4.12: what was not produced is logged, never
 *    silently dropped. "Asked for eight, created three" arrives with the gate
 *    the other five died at, so "the evidence in this slice does not support
 *    eight" is distinguishable from a bug.
 *
 * There are two ways in, and they are TABS rather than two halves of one form,
 * because they are different questions. "Cover more of the grid" is asked with
 * filters and a count and answers "where is the radar thin?". "Describe a
 * space" is one specific idea somebody arrived with, and it used to be a
 * textarea whose only feedback was a character count — the one failure that did
 * not matter. It is now a conversation that can see the corpus (see BriefChat).
 * Stacking them meant the second was always below the fold of the first.
 */

interface Props {
  meta: Meta
  onClose: () => void
  /** Open a space in the radar — both for what already exists and for what the
   *  run just produced, since a result you cannot open is a receipt, not a result. */
  onOpenTopic: (id: string) => void
  /** A finished run changed the corpus; the radar behind this screen is stale. */
  onGenerated: () => void
  onHelp: (topic: string) => void
}

const POLL_MS = 2000
const DEFAULT_COUNT = 5

/** A filter block. Deliberately the same shape as the radar's filter rail —
 *  this screen asks the same four questions, and answering them in a control
 *  that looks different suggests it means something different. */
function ConstraintGroup({ title, note, items, selected, onToggle, counts }: {
  title: string
  note?: string
  items: { id: string; label: string; hint?: string }[]
  selected: string[]
  onToggle: (id: string) => void
  /** How many spaces ALREADY carry this value under the current selection. */
  counts?: Record<string, number>
}) {
  return (
    <div className="gen-group">
      <h4>
        {title}
        {selected.length > 0 && <span className="gen-group-count">{selected.length}</span>}
      </h4>
      {note && <p className="gen-note">{note}</p>}
      <div className="gen-options">
        {items.map((item) => {
          const active = selected.includes(item.id)
          const count = counts?.[item.id]
          return (
            <button
              key={item.id}
              type="button"
              className={`gen-chip${active ? ' is-on' : ''}`}
              aria-pressed={active}
              title={item.hint ?? item.label}
              onClick={() => onToggle(item.id)}
            >
              <span>{item.label}</span>
              {count !== undefined && <span className="gen-chip-count">{count}</span>}
            </button>
          )
        })}
      </div>
    </div>
  )
}

/** One row of the "already exists here" list. */
function MatchRow({ topic, onOpen }: { topic: Topic; onOpen: () => void }) {
  const attractiveness = topic.attractiveness?.score
  return (
    <button type="button" className="gen-match" onClick={onOpen}>
      <span className="gen-match-id">{topic.id}</span>
      <span className="gen-match-body">
        <span className="gen-match-statement">{topic.statement}</span>
        <span className="gen-match-meta">
          {topic.labels.vertical} · {topic.labels.use_case} · {topic.labels.technology}
          {topic.horizon && ` · ${topic.horizon.toUpperCase()}`}
          {topic.geographies.length > 0 && ` · ${topic.geographies.join(' ')}`}
          {' · '}{topic.state}
        </span>
      </span>
      {attractiveness !== undefined && (
        <span className="gen-match-score" title="Attractiveness (SC-01)">
          {Math.round(attractiveness)}
        </span>
      )}
    </button>
  )
}

/** What a run actually produced.
 *
 * A row of ids answers "did it work" and not "what did it make". A newly
 * synthesised space is the one case where the cited evidence belongs on the
 * same screen as the statement: nobody has looked at this before, and "why does
 * the radar think this is a thing" is the first question — answerable here only
 * because §4.4.4 requires every claim to carry the signal ids behind it.
 *
 * The long-form description (FR-14) is deliberately NOT generated by a run —
 * one more model call per space, and the detail pane makes it on demand — so
 * the card says where to get it rather than leaving a blank where it would be.
 */
function CreatedSpace({ topic, onOpen }: { topic: Topic; onOpen: () => void }) {
  const attractiveness = topic.attractiveness?.score
  const rightToWin = topic.right_to_win?.score
  return (
    <div className="gen-space">
      <div className="gen-space-head">
        <button type="button" className="gen-space-open" onClick={onOpen}>
          {topic.statement}
        </button>
        <span className="gen-space-id">{topic.id}</span>
      </div>
      <p className="gen-space-meta">
        {topic.labels.vertical} · {topic.labels.use_case} · {topic.labels.technology}
        {topic.horizon && <> · <b>{topic.horizon.toUpperCase()}</b></>}
        {topic.geographies.length > 0 && ` · ${topic.geographies.join(' ')}`}
        {' · '}{topic.state}
        {attractiveness !== undefined && ` · attractiveness ${Math.round(attractiveness)}`}
        {rightToWin !== undefined && ` · right to win ${Math.round(rightToWin)}`}
        {' · '}{topic.signal_count} signal{topic.signal_count === 1 ? '' : 's'}
      </p>
      {topic.why_hot.length > 0 && (
        <ul className="gen-space-why">
          {topic.why_hot.slice(0, 3).map((claim, index) => (
            <li key={index}>
              {claim.claim}
              <span className="gen-space-cite">
                {' '}{claim.signals.length} cited signal{claim.signals.length === 1 ? '' : 's'}
              </span>
            </li>
          ))}
        </ul>
      )}
      <p className="gen-quiet">
        No long-form description was generated — that is one more model call per space, so it is
        made on demand. Open the space to write one.
      </p>
    </div>
  )
}

/** Progress and outcome for one run. */
function RunReport({ job, onCancel, onOpenTopic }: {
  job: GenerationJob
  onCancel: () => void
  onOpenTopic: (id: string) => void
}) {
  const running = job.status === 'queued' || job.status === 'running'
  const logRef = useRef<HTMLDivElement | null>(null)
  // Follow the tail while it runs. A log that has to be scrolled to see the
  // current step is a log nobody watches.
  useEffect(() => {
    if (running && logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [job.log.length, running])

  const pct = Math.round(Math.max(0, Math.min(1, job.progress)) * 100)
  const landed = (job.stats?.horizon_landed ?? null) as Record<string, number> | null
  const synthesis = job.stats?.synthesis as Record<string, any> | undefined
  const usage = job.stats?.llm_usage as Record<string, any> | undefined

  return (
    <div className={`gen-run gen-run-${job.status}`}>
      <div className="gen-run-head">
        <span className={`gen-status gen-status-${job.status}`}>
          {running && <span className="spinner" />}
          {running ? (job.stage_label ?? 'Starting…') : job.status === 'done' ? 'Finished'
            : job.status === 'cancelled' ? 'Cancelled' : 'Failed'}
        </span>
        <span className="gen-run-id">
          {job.kind === 'brief' ? 'from a written brief' : 'grid'} · {job.id}
        </span>
        <span className="spacer" />
        {running && <button onClick={onCancel}>Stop</button>}
      </div>

      {/* The count is the headline, because it is what was asked for. The bar
          behind it moves on evidence read as well, so a run that has produced
          nothing yet still shows that it is working rather than reading as a
          hang — but it can never fill on evidence alone. */}
      <div className="gen-progress">
        <div className="gen-progress-line">
          <b>{job.created}</b>
          <span> of {job.requested} space{job.requested === 1 ? '' : 's'} created</span>
          {running && job.units_total > 0 && (
            <span className="gen-quiet">
              {job.kind === 'grid' ? ` · round ${job.round}, ` : ' · '}
              {job.units_done} of {job.units_total} {job.unit_label}
              {job.units_total === 1 ? '' : 's'}
              {job.kind === 'grid' ? ' read' : ''}
            </span>
          )}
          <span className="spacer" />
          <span className="gen-progress-pct">{pct}%</span>
        </div>
        <div className="gen-progress-track"
             role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}
             aria-label={`Generation progress: ${job.created} of ${job.requested} spaces created`}>
          <div className={`gen-progress-fill${running ? ' is-live' : ''}`}
               style={{ width: `${pct}%` }} />
        </div>
      </div>

      <ol className="gen-stages">
        {job.stages.map((stage) => (
          <li key={stage.id}
              className={stage.done ? 'is-done' : job.stage === stage.id ? 'is-active' : ''}>
            {stage.label}
          </li>
        ))}
      </ol>

      {job.error && <p className="gen-error">{job.error}</p>}

      {!running && (
        <div className="gen-outcome">
          <p>
            <b>{job.created}</b> new space{job.created === 1 ? '' : 's'} created
            {job.updated > 0 && (
              <>
                {' · '}<b>{job.updated}</b> existing space{job.updated === 1 ? '' : 's'} refreshed
                {' '}
                <span className="gen-quiet">
                  (a candidate landing on an existing vertical × use case × technology updates it
                  rather than creating a duplicate — DR-03)
                </span>
              </>
            )}
            {' · asked for '}{job.requested}.
          </p>
          {job.updated_ids.length > 0 && (
            <div className="gen-created-ids">
              <span className="gen-quiet">
                {job.created === 0
                  ? 'Nothing new was created because what the run produced already exists here. '
                    + 'Your evidence was added to it — open it and see:'
                  : 'Also refreshed with this run\'s evidence:'}
              </span>
              {job.updated_ids.map((id) => (
                <button key={id} type="button" className="gen-created-chip"
                        onClick={() => onOpenTopic(id)}>{id}</button>
              ))}
            </div>
          )}
          {job.created_topics.length > 0 && (
            <div className="gen-created">
              {job.created_topics.map((topic) => (
                <CreatedSpace key={topic.id} topic={topic}
                              onOpen={() => onOpenTopic(topic.id)} />
              ))}
            </div>
          )}
          {/* Ids without rows: the space exists but the read model has not been
              asked for it yet, or a finishing stage failed before it was
              assembled. Showing the id is better than showing nothing. */}
          {job.created_topics.length < job.created_ids.length && (
            <div className="gen-created-ids">
              {job.created_ids
                .filter((id) => !job.created_topics.some((t) => t.id === id))
                .map((id) => (
                  <button key={id} type="button" className="gen-created-chip"
                          onClick={() => onOpenTopic(id)}>{id}</button>
                ))}
            </div>
          )}
          {landed && Object.keys(landed).length > 0 && (
            <p className="gen-quiet">
              Derived horizon: {Object.entries(landed).map(([k, v]) => `${v} ${k}`).join(', ')}.
              §4.8 derives this from the evidence attached to each space — a horizon filter
              steers the run, it does not set the answer.
            </p>
          )}
          {synthesis && (
            <p className="gen-quiet">
              {synthesis.raw_candidates ?? 0} raw candidate{synthesis.raw_candidates === 1 ? '' : 's'} over{' '}
              {synthesis.rounds ?? 1} round{synthesis.rounds === 1 ? '' : 's'} from{' '}
              {synthesis.clusters_consumed ?? 0} theme cluster
              {synthesis.clusters_consumed === 1 ? '' : 's'}
              {typeof usage?.calls === 'number' && ` · ${usage.calls} model calls (${usage.provider})`}.
              {/* The usual reason a run falls short, so it gets said rather than
                  left for the reader to infer from "asked for 5, created 3". */}
              {(synthesis.duplicate_of_existing ?? 0) > 0 && (
                <>
                  {' '}{synthesis.duplicate_of_existing} landed on taxonomy cells the radar already
                  holds; the run named those back to the model and asked again
                  {(synthesis.duplicate_retries ?? 0) > 0
                    && ` (${synthesis.duplicate_retries} extra pass${synthesis.duplicate_retries === 1 ? '' : 'es'})`}.
                </>
              )}
            </p>
          )}
        </div>
      )}

      <details className="gen-log-wrap" open={running}>
        <summary>Run log ({job.log.length} entries)</summary>
        <div className="gen-log" ref={logRef}>
          {job.log.map((entry, index) => (
            <div key={`${entry.at}-${index}`}>
              <span className="gen-log-at">{entry.at.slice(11, 19)}</span> {entry.message}
            </div>
          ))}
        </div>
      </details>
      <p className="gen-quiet gen-run-foot">
        Recorded in the refresh log as <code>{job.id}</code>, kind <code>generation</code> — it
        synthesised over the corpus that was already collected and clustered; it collected nothing
        new (NFR-04).
      </p>
      <span className="visually-hidden" aria-live="polite">
        {running
          ? `Generation running: ${job.stage_label ?? ''}. ${job.created} of ${job.requested} spaces created.`
          : `Generation ${job.status}. ${job.created} spaces created.`}
      </span>
    </div>
  )
}

export default function GenerateScreen({ meta, onClose, onOpenTopic, onGenerated, onHelp }: Props) {
  const [count, setCount] = useState(DEFAULT_COUNT)
  const [constraints, setConstraints] = useState<GenerationConstraints>({ ...EMPTY_CONSTRAINTS })
  const [options, setOptions] = useState<GenerationOptions | null>(null)
  const [match, setMatch] = useState<GenerationMatch | null>(null)
  const [matchLoading, setMatchLoading] = useState(true)
  const [job, setJob] = useState<GenerationJob | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)
  /** Which way in. Tabs rather than a stacked form: they are different
   *  questions, and the second used to live below the fold of the first. */
  const [mode, setMode] = useState<'grid' | 'chat'>('grid')
  const notified = useRef<string | null>(null)

  const active = job?.status === 'queued' || job?.status === 'running'
  const selected = constraintCount(constraints)

  const toggle = useCallback((key: keyof GenerationConstraints) => (id: string) => {
    setConstraints((current) => {
      const list = current[key]
      return { ...current, [key]: list.includes(id) ? list.filter((v) => v !== id) : [...list, id] }
    })
  }, [])

  useEffect(() => {
    api.generationOptions().then(setOptions).catch((e) => setError(String(e)))
    // A run started before this screen was opened — or before a page reload —
    // is still running on the server. Reattach to it rather than showing an
    // idle screen that would let someone start a second one and get a 409.
    api.generationJobs()
      .then(({ active: activeId, jobs }) => {
        const found = activeId ? jobs.find((j) => j.id === activeId) : jobs[0]
        if (found) {
          setJob(found)
          notified.current = found.status === 'done' ? found.id : null
        }
      })
      .catch(() => { /* no history is not an error */ })
  }, [])

  // What already exists inside the criteria, refetched as they change.
  useEffect(() => {
    let cancelled = false
    setMatchLoading(true)
    api.generationMatching(constraints)
      .then((m) => { if (!cancelled) { setMatch(m); setError(null) } })
      .catch((e) => { if (!cancelled) setError(String(e)) })
      .finally(() => { if (!cancelled) setMatchLoading(false) })
    return () => { cancelled = true }
  }, [constraints])

  // Poll while a run is in flight, and once more after it ends so the final
  // stats land.
  useEffect(() => {
    if (!job || !active) return
    const id = window.setInterval(() => {
      api.generationJob(job.id).then(setJob).catch((e: Error) => {
        // A network blip is transient and the next tick recovers. A 404 is not:
        // the run's record lives in the server process, so a restart or a worker
        // recycle loses it — and swallowing that leaves the screen polling a job
        // that no longer exists, with every control disabled, until a reload.
        if (!/^404\b/.test(e.message)) return
        setJob((current) => (current && current.id === job.id
          ? { ...current, status: 'error', stage: null, progress: 1,
              error: 'The server no longer has a record of this run — it was most likely '
                + 'restarted. Any spaces it had already written are in the radar; reload to see them.' }
          : current))
      })
    }, POLL_MS)
    return () => window.clearInterval(id)
  }, [job, active])

  // A finished run changed the corpus, so the radar behind this screen and the
  // "already exists" list on it are both stale.
  useEffect(() => {
    if (!job || active || notified.current === job.id) return
    notified.current = job.id
    if (job.created > 0 || job.updated > 0) {
      onGenerated()
      api.generationMatching(constraints).then(setMatch).catch(() => {})
      api.generationOptions().then(setOptions).catch(() => {})
    }
  }, [job, active, onGenerated, constraints])

  const start = useCallback(() => {
    setStarting(true)
    setError(null)
    api.startGeneration(count, constraints)
      .then((started) => { setJob(started); notified.current = null })
      .catch((e) => setError(String(e).replace(/^Error:\s*/, '')))
      .finally(() => setStarting(false))
  }, [count, constraints])

  /** Run what the conversation composed. One job for however many briefs it
   *  landed on — synthesis holds the only write lock on the taxonomy triple, so
   *  three separate requests would just collect 409s. */
  const startFromBriefs = useCallback((descriptions: string[]) => {
    if (descriptions.length === 0) return
    setStarting(true)
    setError(null)
    api.startGenerationFromBriefs(descriptions)
      .then((started) => { setJob(started); notified.current = null })
      .catch((e) => setError(String(e).replace(/^Error:\s*/, '')))
      .finally(() => setStarting(false))
  }, [])

  /** Build a space the corpus is silent about, on contributed evidence. Same
   *  run, same curation — what differs is that the evidence was written down by
   *  the person asking rather than fetched, and is attributed to them. */
  const startFromHypothesis = useCallback((body: HypothesisRequest) => {
    setStarting(true)
    setError(null)
    api.startGenerationFromHypothesis(body)
      .then((started) => { setJob(started); notified.current = null })
      .catch((e) => setError(String(e).replace(/^Error:\s*/, '')))
      .finally(() => setStarting(false))
  }, [])

  /** Build it regardless. The run goes and looks for evidence on the brief and
   *  carries the person's own account where they gave one — so the space still
   *  cites something, it is just no longer limited to what the crawl happened
   *  to have fetched before today. */
  const startAnyway = useCallback((body: GenerateAnywayRequest) => {
    setStarting(true)
    setError(null)
    api.startGenerationAnyway(body)
      .then((started) => { setJob(started); notified.current = null })
      .catch((e) => setError(String(e).replace(/^Error:\s*/, '')))
      .finally(() => setStarting(false))
  }, [])

  const cancel = useCallback(() => {
    if (!job) return
    api.cancelGeneration(job.id).then(setJob).catch((e) => setError(String(e)))
  }, [job])

  const geographies = useMemo(
    () => (options?.geographies ?? []).map((g) => ({
      id: g.id,
      label: g.id,
      hint: `${g.id} — ${g.signals} signal${g.signals === 1 ? '' : 's'} in the corpus, `
        + `${g.spaces} existing space${g.spaces === 1 ? '' : 's'}`,
    })),
    [options],
  )

  // Cluster counts come from the server already rolled up over member codes, so
  // the hint says how much evidence a cluster actually has rather than implying
  // that ticking it is the same as ticking one country.
  const marketClusters = useMemo(
    () => (options?.market_clusters ?? [])
      .filter((c) => c.signals > 0 || c.spaces > 0)
      .map((c) => ({
        id: c.id,
        label: c.source === 'extension' ? `${c.label} *` : c.label,
        hint: `${countryNames(c.countries, 99).full || 'no codes in the corpus'} — ${c.signals} signal`
          + `${c.signals === 1 ? '' : 's'}, ${c.spaces} existing space${c.spaces === 1 ? '' : 's'}`
          + `${c.source === 'extension' ? ' · grouping inferred, not supplied by Orange' : ''}`,
      })),
    [options],
  )

  const blocked = options ? !options.ready : false

  return (
    <div className="gen-screen">
      <div className="gen-head">
        <div>
          <h2>Generate opportunity spaces</h2>
          <p className="gen-sub">
            Runs the synthesis stage over the evidence the pipeline has already collected and
            clustered. It does not fetch anything new — which is what makes “the evidence does not
            support that many” a real answer rather than a timeout.
            <HelpButton topic="generation" onOpen={onHelp} />
          </p>
        </div>
        <span className="spacer" />
        <button onClick={onClose}>← Back to the radar</button>
      </div>

      {blocked && (
        <p className="gen-blocked">{options?.reason}</p>
      )}
      {error && <p className="gen-error">{error}</p>}

      {/* The two ways in. Same pipeline, same curation, same validation — what
          differs is only what steers the model, and which question you arrived
          with. */}
      <div className="gen-tabs" role="tablist" aria-label="How to generate">
        <button
          role="tab"
          id="gen-tab-grid"
          aria-selected={mode === 'grid'}
          aria-controls="gen-panel-grid"
          className={`gen-tab${mode === 'grid' ? ' is-on' : ''}`}
          onClick={() => setMode('grid')}
        >
          Cover more of the grid
          <span className="gen-tab-sub">filters and a count — where is the radar thin?</span>
        </button>
        <button
          role="tab"
          id="gen-tab-chat"
          aria-selected={mode === 'chat'}
          aria-controls="gen-panel-chat"
          className={`gen-tab${mode === 'chat' ? ' is-on' : ''}`}
          onClick={() => setMode('chat')}
        >
          Describe a space
          <span className="gen-tab-sub">talk it through with the corpus in front of you</span>
        </button>
      </div>

      {/* One body in both modes, so the run report and "already in the radar"
          stay put when the tab changes. The chat takes the whole width because
          it carries its own evidence column; the grid form does not need it. */}
      <div className={`gen-body${mode === 'chat' ? ' is-chat' : ''}`}>
        {mode === 'chat' && (
          <section className="gen-panel gen-chat-panel" id="gen-panel-chat"
                   role="tabpanel" aria-labelledby="gen-tab-chat">
            <h3>Describe one opportunity space — and be asked about it</h3>
            <p className="gen-note gen-note-lead">
              Tell the radar what you are looking for and it will interview you until the idea is
              specific enough to retrieve real evidence with. What you say is a{' '}
              <b>search brief, not evidence</b>: it retrieves the closest corroborated signals
              already collected, and those become the only facts a space may rest on. The
              difference from a text box is that the assistant can see that corpus while you are
              still talking — so “the radar has nothing close to that” arrives as a question now
              rather than as an empty run in ten minutes.
              <HelpButton topic="generation" onOpen={onHelp} />
            </p>
            <BriefChat
              meta={meta}
              options={options}
              active={active}
              starting={starting}
              blocked={blocked}
              onGenerate={startFromBriefs}
              onHypothesis={startFromHypothesis}
              onAnyway={startAnyway}
              onOpenTopic={onOpenTopic}
            />
          </section>
        )}

        {mode === 'grid' && (
        <section className="gen-panel gen-form" id="gen-panel-grid"
                 role="tabpanel" aria-labelledby="gen-tab-grid">
          <h3>Cover more of the grid</h3>
          <p className="gen-note gen-note-lead">
            Synthesise across the evidence as a whole, optionally bounded to a slice of it.
          </p>

          <div className="gen-count">
            <label htmlFor="gen-count-input">How many new spaces</label>
            <input
              id="gen-count-input"
              type="number"
              min={1}
              max={options?.max_per_run ?? 25}
              value={count}
              onChange={(e) => {
                const next = Number(e.target.value)
                if (Number.isFinite(next)) {
                  setCount(Math.max(1, Math.min(options?.max_per_run ?? 25, Math.round(next))))
                }
              }}
            />
            <span className="gen-quiet">
              Up to {options?.max_per_run ?? 25} per run. This counts spaces the run <b>creates</b>;
              a candidate that lands on an existing vertical × use case × technology refreshes that
              space instead and does not count (DR-03).
            </span>
          </div>

          <div className="gen-filters-head">
            <h3>Constrain the run</h3>
            {selected > 0 && (
              <button className="gen-clear" onClick={() => setConstraints({ ...EMPTY_CONSTRAINTS })}>
                Clear {selected}
              </button>
            )}
          </div>
          <p className="gen-note gen-note-lead">
            {selected === 0
              ? 'Nothing selected — the run covers the whole evidenced grid, exactly as a scheduled '
                + 'refresh does.'
              : 'The run is bounded to what you have selected. Candidates outside it are discarded '
                + 'rather than corrected, so a narrow scope can legitimately return fewer spaces '
                + 'than you asked for.'}
          </p>

          <ConstraintGroup
            title="Market cluster"
            note="Orange Business go-to-market grouping. Expanded server-side into its member ISO codes and unioned with anything picked under Country, so scoping by cluster is exactly scoping by the countries in it — the preview count below already reflects that expansion. A cluster marked * is our reading of the corpus rather than a grouping Orange supplied."
            items={marketClusters}
            selected={constraints.market_clusters}
            onToggle={toggle('market_clusters')}
          />
          <ConstraintGroup
            title="Country"
            note="Read from the corpus, not the taxonomy: geography rides on signals (§2.6). Selecting some restricts the run to theme clusters that carry evidence actually tagged with those codes — deliberately strict, since a model asked for Germany and handed French tenders invents rather than declines. It can leave the run much less evidence than the whole corpus; the run log says how much."
            items={geographies}
            selected={constraints.geographies}
            onToggle={toggle('geographies')}
            counts={match?.facets?.geography}
          />
          <ConstraintGroup
            title="Vertical"
            items={meta.verticals}
            selected={constraints.verticals}
            onToggle={toggle('verticals')}
            counts={match?.facets?.vertical}
          />
          <ConstraintGroup
            title="Horizon"
            note="Steers the run; it cannot set the answer. §4.8 derives Now / Next / Later from the signal types attached to a space after scoring, so this picks clusters carrying that kind of evidence and reports where the new spaces actually landed."
            items={meta.horizons.map((h) => ({ id: h, label: h.toUpperCase() }))}
            selected={constraints.horizons}
            onToggle={toggle('horizons')}
            counts={match?.facets?.horizon}
          />
          <ConstraintGroup
            title="Domain"
            items={meta.domains}
            selected={constraints.domains}
            onToggle={toggle('domains')}
            counts={match?.facets?.domain}
          />

          <div className="gen-actions">
            <button className="gen-go" onClick={start} disabled={active || starting || blocked}>
              {active ? <><span className="spinner" /> Generating…</>
                : starting ? 'Starting…'
                : `Generate ${count} space${count === 1 ? '' : 's'}`}
            </button>
            {active && (
              <span className="gen-quiet">
                One run at a time — synthesis writes opportunity spaces, and the identity rule
                (DR-03) is enforced by a unique index on the taxonomy triple.
              </span>
            )}
          </div>
        </section>
        )}

        <section className="gen-panel gen-matches" aria-labelledby="gen-matches-head">
          <div className="gen-matches-head">
            <h3 id="gen-matches-head">Already in the radar</h3>
            <span className="gen-quiet" aria-live="polite">
              {matchLoading ? 'Counting…'
                : `${match?.count ?? 0} of ${match?.total_live ?? 0} live space${match?.total_live === 1 ? '' : 's'}`}
            </span>
          </div>
          <p className="gen-note">
            {mode === 'chat'
              ? 'Every live space. The assistant checks this list as you talk and will name the '
                + 'space by id if the conversation converges on a taxonomy triple one of them '
                + 'already holds.'
              : selected === 0
                ? 'Every live space, since nothing is selected. Narrow the filters to see what is '
                  + 'already covered before adding to it.'
                : 'These already meet the criteria you selected. A run that lands on one of their '
                  + 'taxonomy triples refreshes it rather than creating a new space.'}
            {' '}Counted across the whole corpus, not through a role filter — generation writes to
            all of it.
          </p>

          {job && (
            <RunReport job={job} onCancel={cancel} onOpenTopic={onOpenTopic} />
          )}

          <div className="gen-match-list">
            {!matchLoading && (match?.count ?? 0) === 0 && (
              <p className="gen-empty">
                Nothing in the radar meets these criteria yet. That is the case where generating is
                most likely to add something — assuming the corpus carries evidence there.
              </p>
            )}
            {match?.topics.map((topic) => (
              <MatchRow key={topic.id} topic={topic} onOpen={() => onOpenTopic(topic.id)} />
            ))}
            {match?.truncated && (
              <p className="gen-quiet">
                Showing the {match.topics.length} most attractive of {match.count}. The count above
                is the whole matching set.
              </p>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
