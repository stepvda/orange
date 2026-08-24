import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { Plan, PlannerMeta, PlanRequest, PlanReport } from '../types'
import {
  CapacityChart, EntryTimelineChart, FunnelChart, MixChart,
  RevenueProfitChart, UncertaintyChart,
} from './PlannerCharts'

/** The Planner — full screen, because a plan is not a side panel.
 *
 * Everything else in this interface answers a question about ONE space. A plan
 * is a statement about the portfolio, and reading it beside a filter rail for
 * individual topics would be the same category error as reading the brief in a
 * 420px column.
 *
 * The screen keeps the product's standing division visible: what was COMPUTED
 * (selection, schedule, projection, capacity) sits above what was WRITTEN (the
 * narrative), and the written half is absent until somebody asks for it. Every
 * figure on the page came from the optimiser; the model is only allowed to
 * explain them, and it may not introduce one.
 *
 * TWO SOURCES, AND THE SIDEBAR IS THE CHOICE BETWEEN THEM. Under `parameters`
 * the caller states constraints and the optimiser picks the set — the
 * exploratory question, what SHOULD we do. Under `workflow` the set is already
 * decided: everything the stage gate has moved to Demand-tested or beyond, with
 * no constraint applied to it, because each would overrule a human decision
 * with an assumption band. The second mode answers what the business we have
 * already committed to earns, and when.
 *
 * The modes are not two views of one plan. They produce different plan ids and
 * are read differently, so the screen says which one it is looking at
 * everywhere the difference changes the reading — most of all where a
 * capability pool is over-committed, which is impossible under one mode and the
 * most useful number on the page under the other.
 */

const EUR = (v?: number | null) => {
  if (v === null || v === undefined) return '—'
  const m = v / 1e6
  if (Math.abs(m) >= 1000) return `€${(m / 1000).toFixed(2)}bn`
  return `€${Math.round(m).toLocaleString()}m`
}

type Tab = 'overview' | 'spaces' | 'narrative' | 'assumptions' | 'document'

const TABS: readonly Tab[] = ['overview', 'spaces', 'narrative', 'assumptions', 'document'] as const

const TAB_LABELS: Record<Tab, string> = {
  overview: 'Overview',
  spaces: 'Spaces',
  narrative: 'Business plan',
  assumptions: 'Assumptions',
  document: 'Document',
}

const SECTION_TITLES: Record<string, string> = {
  thesis: 'The thesis',
  why_these: 'Why this set',
  sequence: 'The sequence',
  capacity: 'Execution',
  risks: 'Risks',
  not_doing: 'What we are not doing',
}

/** The stage a plan started from, in the label the workflow board uses. Read
 *  from meta so one rename on the backend does not leave two spellings in the
 *  interface. */
const stageLabel = (id: string | undefined, meta: PlannerMeta | null) =>
  (meta?.workflow?.stages ?? []).find((s) => s.id === id)?.label ?? 'Demand-tested'

const workflowCount = (meta: PlannerMeta | null, stage: string) =>
  (meta?.workflow?.stages ?? []).find((s) => s.id === stage)?.cumulative ?? 0

function Stat({ label, value, sub, tone }: {
  label: string; value: string; sub?: string; tone?: 'accent' | 'warn'
}) {
  return (
    <div className={`pl-stat${tone ? ` ${tone}` : ''}`}>
      <span className="pl-stat-label">{label}</span>
      <span className="pl-stat-value">{value}</span>
      {sub && <span className="pl-stat-sub">{sub}</span>}
    </div>
  )
}

/** The two ways a portfolio gets into a plan.
 *
 * Presented as a choice rather than a checkbox because they are different
 * questions, not one question with an option. `parameters` asks what we SHOULD
 * do; `workflow` asks what the business has ALREADY DECIDED to do and what that
 * earns. Nothing in the second half of the form applies to the second question.
 */
const SOURCES = [
  { id: 'parameters' as const, label: 'Parameters' },
  { id: 'workflow' as const, label: 'Workflow selected' },
]

/** Only the stages that can start a plan. Nobody plans from Shortlisted: the
 *  stage means "worth looking at", and a plan built on it would be projecting
 *  revenue from a decision nobody has taken. */
const PLANNABLE_FROM = ['demand_tested', 'packaged', 'live']

function Form({ meta, busy, source, onSource, onRun }: {
  meta: PlannerMeta
  busy: boolean
  source: 'parameters' | 'workflow'
  onSource: (s: 'parameters' | 'workflow') => void
  onRun: (req: PlanRequest) => void
}) {
  const d = meta.defaults ?? {}
  const cap = meta.capacity ?? {}
  const [req, setReq] = useState<PlanRequest>({
    label: 'Five-year portfolio plan',
    objective: 'profit',
    plan_years: 5,
    from_stage: meta.workflow?.default_from_stage ?? 'demand_tested',
    min_confidence: 'partial',
    max_portfolio_distance: 3,
    entry_slots_per_year: cap.entry_slots_per_year ?? 12,
    pool_availability: cap.pool_availability ?? 0.15,
    max_share_per_vertical: d.max_share_per_vertical ?? 0.4,
    prefer_verticals: [],
    exclude_verticals: [],
    geographies: [],
  })
  const set = <K extends keyof PlanRequest>(k: K, v: PlanRequest[K]) =>
    setReq((r) => ({ ...r, [k]: v }))

  const stages = (meta.workflow?.stages ?? []).filter((s) => PLANNABLE_FROM.includes(s.id))
  const chosen = stages.find((s) => s.id === req.from_stage)
  const committed = chosen?.cumulative ?? 0
  const projectable = chosen?.cumulative_sized ?? 0
  const unsized = committed - projectable

  return (
    <form className="pl-form" onSubmit={(e) => { e.preventDefault(); onRun({ ...req, source }) }}>
      <div className="pl-source" role="group" aria-label="Where the portfolio comes from">
        {SOURCES.map((s) => (
          <button key={s.id} type="button" aria-pressed={source === s.id}
                  onClick={() => onSource(s.id)}>{s.label}</button>
        ))}
      </div>

      <label>
        <span>Plan name</span>
        <input value={req.label} onChange={(e) => set('label', e.target.value)} />
      </label>

      {source === 'workflow' ? (
        <>
          <label>
            <span>Include everything from</span>
            <select value={req.from_stage}
                    onChange={(e) => set('from_stage', e.target.value)}>
              {stages.map((s) => (
                <option key={s.id} value={s.id}>{s.label} or further</option>
              ))}
            </select>
            <em>
              {committed} space{committed === 1 ? '' : 's'} have reached this stage
              {projectable !== committed && <> · <strong>{projectable}</strong> can be projected</>}
              {unsized > 0 && <> · {unsized} carry no market size and will be listed as a gap</>}
            </em>
          </label>

          <label>
            <span>Plan horizon (years)</span>
            <input type="number" min={1} max={10} value={req.plan_years}
                   onChange={(e) => set('plan_years', Number(e.target.value))} />
            <em>Commitments whose market arrives after the window still appear, in the
              final year, earning what their first ramp year earns.</em>
          </label>

          <label>
            <span>New spaces started per year</span>
            <input type="number" min={1} max={60} value={req.entry_slots_per_year ?? 12}
                   onChange={(e) => set('entry_slots_per_year', Number(e.target.value))} />
            <em>Spreads the schedule; it never removes anything. A cohort bigger than
              this cascades into the next year.</em>
          </label>

          <label>
            <span>Capability headcount available for new work</span>
            <input type="range" min={0.05} max={0.5} step={0.01}
                   value={req.pool_availability ?? 0.15}
                   onChange={(e) => set('pool_availability', Number(e.target.value))} />
            <em>{Math.round((req.pool_availability ?? 0.15) * 100)}% of each pool. Here this
              measures the commitment rather than limiting it — a pool over 100% is
              reported, not resolved by dropping a space.</em>
          </label>

          <button className="pl-run" disabled={busy || projectable === 0}>
            {busy ? 'Computing…' : 'Generate the business plan'}
          </button>
          {projectable === 0 && (
            <p className="pl-form-note">
              Nothing at this stage carries a bottom-up market size, so there is nothing to
              project. Size the spaces first, or move one further along the workflow board.
            </p>
          )}
          <p className="pl-form-note">
            The workflow chose this set — no evidence floor, distance cap or concentration
            limit is applied, because each would overrule a decision somebody already took.
            What is computed here is the schedule and the arithmetic.
          </p>
        </>
      ) : (
        <>
          <label>
            <span>Objective</span>
            <select value={req.objective} onChange={(e) => set('objective', e.target.value)}>
              <option value="profit">Maximise 5-year profit</option>
              <option value="revenue">Maximise 5-year revenue</option>
              <option value="npv">Maximise NPV of profit</option>
              <option value="strategic_coverage">Maximise strategic coverage</option>
            </select>
            <em>Different objectives give materially different portfolios. This is a decision.</em>
          </label>

          <label>
            <span>New spaces started per year</span>
            <input type="number" min={1} max={60} value={req.entry_slots_per_year ?? 12}
                   onChange={(e) => set('entry_slots_per_year', Number(e.target.value))} />
            <em>Governance, bid capacity and sales enablement — not headcount.</em>
          </label>

          <label>
            <span>Capability headcount available for new work</span>
            <input type="range" min={0.05} max={0.5} step={0.01}
                   value={req.pool_availability ?? 0.15}
                   onChange={(e) => set('pool_availability', Number(e.target.value))} />
            <em>{Math.round((req.pool_availability ?? 0.15) * 100)}% of each pool. The rest runs
              the existing business.</em>
          </label>

          <label>
            <span>Evidence floor</span>
            <select value={req.min_confidence}
                    onChange={(e) => set('min_confidence', e.target.value)}>
              <option value="observed">Observed sizes only — strictest</option>
              <option value="partial">Observed and partial</option>
              <option value="modelled">Everything, including modelled</option>
            </select>
            <em>
              {meta.sizes_by_confidence?.observed ?? 0} observed ·{' '}
              {meta.sizes_by_confidence?.partial ?? 0} partial ·{' '}
              {meta.sizes_by_confidence?.modelled ?? 0} modelled
            </em>
          </label>

          <label>
            <span>Furthest portfolio distance</span>
            <select value={req.max_portfolio_distance}
                    onChange={(e) => set('max_portfolio_distance', Number(e.target.value))}>
              <option value={0}>L0 — existing offer only</option>
              <option value={1}>L0–L1 — bundles allowed</option>
              <option value={2}>L0–L2 — partner-dependent allowed</option>
              <option value={3}>L0–L3 — one capability build allowed</option>
              <option value={4}>L0–L4 — including white space</option>
            </select>
          </label>

          <label>
            <span>Maximum share in any one vertical</span>
            <input type="range" min={0.15} max={1} step={0.05}
                   value={req.max_share_per_vertical ?? 0.4}
                   onChange={(e) => set('max_share_per_vertical', Number(e.target.value))} />
            <em>{Math.round((req.max_share_per_vertical ?? 0.4) * 100)}%. Without a cap the
              optimiser returns a single-vertical plan and calls it a portfolio.</em>
          </label>

          <label>
            <span>Prefer verticals</span>
            <select multiple size={5} value={req.prefer_verticals ?? []}
                    onChange={(e) => set('prefer_verticals',
                      Array.from(e.target.selectedOptions).map((o) => o.value))}>
              {meta.verticals?.map((v) => <option key={v.id} value={v.id}>{v.label}</option>)}
            </select>
            <em>A tilt, not a filter.</em>
          </label>

          <button className="pl-run" disabled={busy}>
            {busy ? 'Optimising…' : 'Build the plan'}
          </button>
          <p className="pl-form-note">
            Selection and projection are arithmetic — no model call, so this is fast. The written
            business plan is a separate step.
          </p>
        </>
      )}
    </form>
  )
}

export default function PlannerScreen({ onClose, onOpenTopic }: {
  onClose: () => void
  onOpenTopic?: (id: string) => void
}) {
  const [meta, setMeta] = useState<PlannerMeta | null>(null)
  const [plan, setPlan] = useState<Plan | null>(null)
  const [busy, setBusy] = useState(false)
  const [writing, setWriting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>('overview')
  const [source, setSource] = useState<'parameters' | 'workflow'>('parameters')
  const [report, setReport] = useState<PlanReport | null>(null)
  const [exporting, setExporting] = useState(false)
  const closeRef = useRef<HTMLButtonElement | null>(null)

  useEffect(() => { closeRef.current?.focus() }, [])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !document.querySelector('.help-backdrop')) onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  useEffect(() => { api.plannerMeta().then(setMeta).catch((e) => setError(String(e.message ?? e))) }, [])

  const run = useCallback(async (req: PlanRequest) => {
    setBusy(true); setError(null)
    try { setPlan(await api.createPlan(req)); setReport(null); setTab('overview') }
    catch (e: any) { setError(String(e.message ?? e)) }
    finally { setBusy(false) }
  }, [])

  const narrate = useCallback(async () => {
    if (!plan) return
    setWriting(true); setError(null)
    try { setPlan(await api.narratePlan(plan.id)); setTab('narrative') }
    catch (e: any) { setError(String(e.message ?? e)) }
    finally { setWriting(false) }
  }, [plan])

  // Rebuilt rather than fetched: the narrative can be written after the plan
  // was computed, and a reader who exported before that would otherwise get a
  // document quietly missing the section they opened it for.
  const exportPdf = useCallback(async () => {
    if (!plan) return
    setExporting(true); setError(null)
    try { setReport(await api.buildPlanReport(plan.id)); setTab('document') }
    catch (e: any) { setError(String(e.message ?? e)) }
    finally { setExporting(false) }
  }, [plan])

  useEffect(() => {
    if (tab === 'document' && plan && !report && !exporting) void exportPdf()
  }, [tab, plan, report, exporting, exportPdf])

  const p = plan?.projection
  // Which question this plan answered. Read off the plan rather than the
  // sidebar, so a plan stays labelled correctly after the toggle has moved on.
  const fromWorkflow = plan?.inputs?.source === 'workflow'
  const fromStage = plan?.capacity_usage?.from_stage
  const stageMix = plan?.capacity_usage?.stage_mix ?? []

  return (
    <div className="fs-screen pl-screen">
      <div className="fs-head">
        <div className="fs-title">
          <div className="fs-badges">
            <span className="badge">PLANNER</span>
            {fromWorkflow && (
              <span className="badge explore"
                    title="The set came from the workflow board, not from the optimiser">
                FROM WORKFLOW
              </span>
            )}
            {plan && <span className="badge">{plan.id}</span>}
            {meta && <span className="badge" title="The assumption set this plan rests on">
              {meta.economics_version}
            </span>}
          </div>
          <h2>{plan ? plan.label : 'Five-year portfolio plan'}</h2>
          <p className="fs-triple">
            {plan
              ? fromWorkflow
                ? `${plan.selected_count} committed spaces, scheduled across ${plan.plan_years} years`
                  + ` — everything at ${stageLabel(fromStage, meta)} or further`
                : `${plan.selected_count} spaces selected from ${plan.considered_count} admissible candidates`
              : source === 'workflow'
                ? `${workflowCount(meta, 'demand_tested')} spaces are Demand-tested or further`
                : `${meta?.plannable_spaces ?? '…'} sized spaces available to plan over`}
          </p>
          {/* Said here rather than buried in the assumptions tab: the two figures
              that turn a market size into money are Orange's own filed numbers,
              and a reader deciding how much to trust this page needs that first. */}
          <p className="pl-provenance-head">
            Margin and discount rate are taken from{' '}
            <strong>Orange&apos;s own published financial filings</strong>
            {meta?.source_filing ? ` — ${meta.source_filing}` : ''}
            {meta?.filed ? ` · segment EBITDAaL margin ${(meta.filed.segment_ebitdaal_margin * 100).toFixed(1)}%`
                         + ` · post-tax discount rate ${(meta.filed.discount_rate_post_tax * 100).toFixed(1)}%` : ''}
          </p>
        </div>
        <span className="spacer" />
        {plan && (
          <div className="fs-panes" role="group" aria-label="View">
            {TABS.map((t) => (
              <button key={t} aria-pressed={tab === t} onClick={() => setTab(t)}>
                {TAB_LABELS[t]}
                {t === 'narrative' && !plan.narrative && <span className="fs-stale-dot">●</span>}
              </button>
            ))}
          </div>
        )}
        <button className="fs-exit" ref={closeRef} onClick={onClose} title="Back to the radar (Esc)">
          <span aria-hidden>↙</span> Exit planner
        </button>
      </div>

      <div className="fs-body pl-body">
        <aside className="pl-side">
          <h3>Parameters</h3>
          {meta ? <Form meta={meta} busy={busy} source={source} onSource={setSource} onRun={run} />
                : <p className="ca-muted">Loading…</p>}
          {plan && (
            <button className="pl-export" onClick={exportPdf} disabled={exporting}
                    title="Inputs, projection, spaces, business plan and assumptions in one PDF">
              {exporting ? 'Rendering…' : '↓ Export to PDF'}
            </button>
          )}
        </aside>

        <main className="pl-main">
          {error && <p className="ca-error">{error}</p>}
          {!plan && !busy && (
            <div className="pl-empty">
              <h3>No plan yet</h3>
              <p className="pl-filings">
                <strong>Grounded in Orange&apos;s filed accounts.</strong> The margin applied to
                revenue and the rate used to discount it are quoted from{' '}
                {meta?.source_filing ?? "Orange's Universal Registration Document"} — not chosen
                here. Every projection is also checked against the segment revenue Orange filed,
                so a plan that implies implausible growth says so.
              </p>
              {source === 'workflow' ? (
                <>
                  <p>
                    <strong>The portfolio is already chosen.</strong> Every opportunity space the
                    workflow board has moved to {stageLabel(meta?.workflow?.default_from_stage, meta)}{' '}
                    or beyond is in this plan — {workflowCount(meta, 'demand_tested')} of them
                    today. No evidence floor, distance cap or concentration limit is applied,
                    because each of those would overrule a decision a strategist, a salesperson or
                    a presales engineer has already taken.
                  </p>
                  <p>
                    What is computed is the rest of it: each space enters when its horizon says the
                    market arrives, cohorts bigger than a year&apos;s capacity cascade forward, and
                    the revenue, margin, ramp, overlap discount and capability load follow from
                    there. A space already Live starts in year one whatever its horizon says.
                  </p>
                  <p className="ca-muted">
                    Nothing is dropped to make the numbers work. Where the committed set needs more
                    than the capability pools can staff, the plan says so and by how much — that
                    gap is the finding, not a reason to edit the portfolio.
                  </p>
                </>
              ) : (
                <>
                  <p>
                    Set the constraints on the left and build one. The optimiser selects a set of
                    opportunity spaces, schedules when each is entered, and projects revenue and
                    profit across the plan window.
                  </p>
                  <p className="ca-muted">
                    It is a scenario under stated assumptions, not a forecast. Every projection
                    carries its interval and is checked against Orange's own filed segment revenue.
                  </p>
                  <p className="ca-muted">
                    Nothing has been decided yet at this point — that is what this mode is for. To
                    plan the business already committed on the workflow board instead, switch to{' '}
                    <strong>Workflow selected</strong>.
                  </p>
                </>
              )}
            </div>
          )}

          {plan && p && tab === 'overview' && (
            <>
              {/* Said before the first figure. Everything below reads differently
                  depending on who chose the set — most of all a pool over 100%,
                  which cannot happen under the optimiser and is the whole point
                  of the page under the workflow. */}
              {fromWorkflow && (
                <p className="pl-committed">
                  <strong>Nothing here was selected by the Planner.</strong> This is every
                  opportunity space the workflow board has moved to {stageLabel(fromStage, meta)}{' '}
                  or beyond, scheduled across the window and costed. The optimiser chose nothing
                  and rejected nothing.
                  {stageMix.length > 0 && (
                    <span className="pl-stage-mix">
                      {stageMix.map((m) => (
                        <span key={m.key}><strong>{m.count}</strong> {m.label}</span>
                      ))}
                    </span>
                  )}
                </p>
              )}

              <div className="pl-stats">
                <Stat label={`${plan.plan_years}-year revenue`} value={EUR(p.revenue_total)} />
                <Stat label={`${plan.plan_years}-year profit`} value={EUR(p.profit_total)} tone="accent"
                      sub={`band ${EUR(p.profit_total_low)} – ${EUR(p.profit_total_high)}`} />
                <Stat label={`NPV @ ${(p.discount_rate * 100).toFixed(1)}%`} value={EUR(p.npv_profit)}
                      sub="Orange's filed discount rate" />
                <Stat label={fromWorkflow ? 'Committed spaces' : 'Spaces'}
                      value={String(plan.selected_count)}
                      sub={fromWorkflow ? `at ${stageLabel(fromStage, meta)} or further`
                                        : `of ${plan.considered_count} admissible`} />
                <Stat label={`Year-${plan.plan_years} vs segment`}
                      value={`${((p.year5_share_of_segment ?? 0) * 100).toFixed(1)}%`}
                      tone={(p.year5_share_of_segment ?? 0) > 0.15 ? 'warn' : undefined}
                      sub="of filed Orange Business revenue" />
              </div>

              {plan.flags?.map((f, i) => (
                <div key={i} className={`pl-flag ${f.severity}`}>
                  <strong>{f.kind}</strong> {f.message}
                </div>
              ))}

              <div className="pl-grid">
                <RevenueProfitChart plan={plan} />
                <UncertaintyChart plan={plan} />
                <EntryTimelineChart plan={plan} />
                <CapacityChart plan={plan} />
                <MixChart plan={plan} dimension="vertical" />
                <FunnelChart plan={plan} />
              </div>

              {(plan.capacity_usage?.binding ?? []).length > 0 && (
                <div className="pl-binding">
                  <h4>{fromWorkflow ? 'What the schedule ran into' : 'What bound this plan'}</h4>
                  <p className="ca-muted">
                    {fromWorkflow
                      ? 'The committed set was scheduled, not selected, so these are limits the '
                        + 'schedule met rather than constraints that removed anything. Nothing was '
                        + 'dropped to satisfy them.'
                      : 'These are the constraints the optimiser hit. Relaxing one is what would '
                        + 'change the answer.'}
                  </p>
                  <ul>{plan.capacity_usage!.binding!.map((b) => <li key={b}>{b}</li>)}</ul>
                </div>
              )}
            </>
          )}

          {plan && tab === 'spaces' && (
            <>
              <h3>{fromWorkflow ? 'Committed spaces, in entry order' : 'Selected spaces, in entry order'}</h3>
              <table className="data pl-table">
                <thead>
                  <tr>
                    <th>Year</th><th>Space</th><th>Vertical</th><th>L</th>
                    <th>Pool</th><th className="num">5y revenue</th><th className="num">5y profit</th>
                  </tr>
                </thead>
                <tbody>
                  {plan.selections.map((s) => (
                    <tr key={s.opportunity_id}>
                      <td><span className="badge">Y{s.entry_year}</span></td>
                      <td>
                        <button className="pl-link" onClick={() => onOpenTopic?.(s.opportunity_id)}>
                          {s.opportunity_id}
                        </button>
                        <div className="pl-stmt">{s.statement}</div>
                      </td>
                      <td>{s.vertical.replace(/_/g, ' ')}</td>
                      <td>L{s.portfolio_distance}</td>
                      <td className="pl-pool">{s.pool ?? '—'}</td>
                      <td className="num">{EUR(s.revenue_by_year.reduce((a, b) => a + b, 0))}</td>
                      <td className="num">{EUR(s.profit_by_year.reduce((a, b) => a + b, 0))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {(plan.exclusions ?? []).length > 0 && (
                <details className="pl-exclusions">
                  <summary>
                    {fromWorkflow
                      ? `${plan.exclusions.length} space(s) not in this plan, and why — none of `
                        + 'them excluded here'
                      : `${plan.exclusions.length} near-miss space(s), and why each was left out`}
                  </summary>
                  <table className="data">
                    <tbody>
                      {plan.exclusions.map((e) => (
                        <tr key={e.opportunity_id}>
                          <td>{e.opportunity_id}</td>
                          <td>{e.statement}</td>
                          <td className="pl-reason">{e.reason}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </details>
              )}
            </>
          )}

          {plan && tab === 'narrative' && (
            <div className="pl-narrative">
              {!plan.narrative && (
                <div className="pl-empty">
                  <h3>The business plan has not been written yet</h3>
                  <p>
                    Everything on the Overview tab was computed. This step asks a model to
                    explain it — the thesis, the sequence, the execution story, the risks and
                    what was deliberately left out.
                  </p>
                  <p className="ca-muted">
                    It may not introduce a number. Every figure already sits in the projection,
                    and a sentence that disagreed with it would be a defect the reader has to
                    adjudicate — so a section containing a quantity is stripped and shown as such.
                  </p>
                  <button className="pl-run" disabled={writing} onClick={narrate}>
                    {writing ? 'Writing…' : 'Write the business plan'}
                  </button>
                </div>
              )}
              {plan.narrative && (
                <>
                  <blockquote className="pl-headline">{plan.narrative.headline}</blockquote>
                  {Object.entries(SECTION_TITLES).map(([key, title]) =>
                    plan.narrative!.sections?.[key] ? (
                      <section key={key}>
                        <h4>{title}</h4>
                        <p>{plan.narrative!.sections[key]}</p>
                      </section>
                    ) : null,
                  )}
                  {(plan.stripped ?? []).length > 0 && (
                    <details className="ca-stripped">
                      <summary>{plan.stripped.length} section(s) removed by the guardrails</summary>
                      <ul>
                        {plan.stripped.map((s, i) => (
                          <li key={i}><strong>{s.section}</strong> — {s.reason}</li>
                        ))}
                      </ul>
                    </details>
                  )}
                  <button className="pl-rewrite" disabled={writing} onClick={narrate}>
                    {writing ? 'Rewriting…' : 'Rewrite'}
                  </button>
                </>
              )}
            </div>
          )}

          {plan && tab === 'assumptions' && (
            <div className="pl-assumptions">
              <h3>What this plan rests on</h3>
              <p className="ca-muted">
                Two figures are quoted from Orange's own filed accounts. Everything else is a
                planning band with an owner — and a plan built under one version of these
                assumptions is not comparable with a plan built under another.
              </p>
              <h4>Filed — {plan.assumptions?.source_filing}</h4>
              <table className="data">
                <tbody>
                  <tr><td>Discount rate (post-tax)</td>
                      <td className="num">{((plan.assumptions?.filed?.discount_rate_post_tax ?? 0) * 100).toFixed(1)}%</td></tr>
                  <tr><td>Segment EBITDAaL margin</td>
                      <td className="num">{((plan.assumptions?.filed?.segment_ebitdaal_margin ?? 0) * 100).toFixed(1)}%</td></tr>
                  <tr><td>Segment revenue</td>
                      <td className="num">€{(plan.assumptions?.filed?.segment_revenue_eur_m ?? 0).toLocaleString()}m</td></tr>
                </tbody>
              </table>
              <h4>Planning bands — owner: {plan.assumptions?.owner}</h4>
              <table className="data">
                <tbody>
                  {Object.entries(plan.assumptions?.margin_by_distance ?? {}).map(([k, v]) => (
                    <tr key={k}><td>Margin at {k}</td>
                        <td className="num">{((v as number) * 100).toFixed(1)}%</td></tr>
                  ))}
                  {Object.entries(plan.assumptions?.ramp_by_horizon ?? {}).map(([k, v]) => (
                    <tr key={k}><td>Ramp — {k}</td>
                        <td className="num">{(v as number[]).map((x) => `${Math.round(x * 100)}%`).join(' · ')}</td></tr>
                  ))}
                </tbody>
              </table>
              <p className="pl-provenance">
                economics {plan.economics_version} · sizing {plan.sizing_version} ·
                weights {plan.weight_set}
                {plan.prompt_version && ` · prompt ${plan.prompt_version}`}
              </p>
            </div>
          )}

          {/* The whole plan as one document, read in the browser rather than
              downloaded. A plan that has to leave the tool to be read is a plan
              that gets read in a stale copy — so the export is a view here, and
              the download is what you do after you have seen it. */}
          {plan && tab === 'document' && (
            <div className="pl-doc">
              <div className="pl-doc-bar">
                <div>
                  <strong>Everything on this screen, in one document.</strong>{' '}
                  Inputs, projection, every selected space with its own description, the
                  business plan and the assumptions it rests on.
                  {!plan.narrative && (
                    <span className="pl-doc-warn">
                      {' '}The business plan has not been written yet — generate it first and the
                      document will include it.
                    </span>
                  )}
                </div>
                <span className="spacer" />
                {report && (
                  <>
                    <a className="pl-doc-btn" href={api.planReportUrl(plan.id, report.content_hash)}
                       target="_blank" rel="noreferrer">Open in a new tab</a>
                    <a className="pl-doc-btn" href={api.planReportDownloadUrl(plan.id)}
                       download={report.filename}>Download</a>
                    <button className="pl-doc-btn" onClick={exportPdf} disabled={exporting}>
                      {exporting ? 'Rebuilding…' : 'Rebuild'}
                    </button>
                  </>
                )}
              </div>

              {exporting && !report && (
                <div className="pl-doc-empty"><p>Rendering the document…</p></div>
              )}
              {!exporting && !report && (
                <div className="pl-doc-empty">
                  <p>The document has not been rendered yet.</p>
                  <button className="primary" onClick={exportPdf}>Export to PDF</button>
                </div>
              )}
              {report && (
                <>
                  <object className="pl-doc-frame" data={api.planReportUrl(plan.id, report.content_hash)}
                          type="application/pdf" aria-label="Plan document">
                    {/* Browsers without an inline PDF viewer get the file rather
                        than an empty grey rectangle. */}
                    <p>
                      This browser cannot display PDFs inline.{' '}
                      <a href={api.planReportDownloadUrl(plan.id)}>Download the document</a>.
                    </p>
                  </object>
                  <p className="pl-provenance">
                    {report.filename} · {(report.bytes / 1024).toFixed(0)} KB ·
                    rendered {report.generated_at} · {report.schema}
                  </p>
                </>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
