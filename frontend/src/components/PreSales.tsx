import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'
import { useAnnounce } from './Announcer'
import type { CollateralItem, Topic } from '../types'

/** Pre-sales collateral for one opportunity space — the fourth full-screen tab.
 *
 * The brief is a leave-behind for a first meeting. This is what the team needs
 * BETWEEN that meeting and a proposal: qualification, a solution outline,
 * battlecards, a business case, a PoC scope, tender blocks, a risk register and
 * a partner ask. Twelve pieces, each built from the same snapshot of the same
 * space, so nothing in the pack can disagree with anything else in it.
 *
 * Three decisions this screen makes, each of which the obvious alternative gets
 * wrong:
 *
 * 1. THE WHOLE CATALOGUE IS ALWAYS LISTED, built or not. A screen that shows
 *    only what exists starts empty, and an empty screen is one nobody presses a
 *    button on. What could be produced is as much of the answer as what has
 *    been, so every row says what it is, who it is for, and which diagrams it
 *    carries — before anyone spends a model call finding out.
 *
 * 2. THE FORMAT IS PICKED PER ROW, not once for the tab. A battlecard is a PDF
 *    in a car park and a Word file on a bid manager's desk, and those are the
 *    same person on different days. The default is the format the artefact
 *    wants to be; the alternatives sit next to it and each remembers whether it
 *    has been built.
 *
 * 3. STALENESS IS PER PIECE AND PER CAUSE. "Out of date" alone tells a reader
 *    nothing they can act on. A battlecard overtaken by a new competitor
 *    register and a value case overtaken by a re-run sizing need different
 *    fixes, so the row says which happened.
 */

const GROUPS: { label: string; note: string; kinds: string[] }[] = [
  {
    label: 'Before the meeting',
    note: 'Qualify it, and know who is in the room.',
    kinds: ['discovery-pack', 'outreach-sequence'],
  },
  {
    label: 'In the meeting',
    note: 'What you present, and what you leave behind.',
    kinds: ['first-meeting-deck', 'value-hypothesis', 'reference-pack'],
  },
  {
    label: 'Against the competition',
    note: 'Who else is here, and what you say when the customer names them.',
    kinds: ['battlecards'],
  },
  {
    label: 'Designing the work',
    note: 'What gets built, what gets proved, and who has to supply the gaps.',
    kinds: ['solution-outline', 'demo-scope', 'partner-brief'],
  },
  {
    label: 'Winning it',
    note: 'The commercial shape, the response, and what could still go wrong.',
    kinds: ['pricing-options', 'rfp-boilerplate', 'risk-register'],
  },
]

function kilobytes(bytes: number | null | undefined): string {
  if (!bytes) return ''
  return bytes < 1024 ? `${bytes} B` : `${Math.round(bytes / 1024)} kB`
}

/** One catalogue row: what it is, which formats exist, and the two buttons. */
function CollateralRow({ item, topicId, busy, elapsed, onGenerate }: {
  item: CollateralItem
  topicId: string
  busy: string | null
  elapsed: number
  onGenerate: (kind: string, fmt: string, force: boolean) => void
}) {
  // The format the reader last looked at, not the one that happens to exist:
  // somebody who picked ODF once is telling you something about their estate.
  const [fmt, setFmt] = useState(item.format)
  const build = item.builds[fmt]
  const built = Boolean(build?.exists)
  const working = busy === `${item.kind}:${fmt}`

  return (
    <div className={`ps-row${built ? ' built' : ''}`}>
      <div className="ps-row-main">
        <div className="ps-row-head">
          <h4>{item.title}</h4>
          {built && build?.stale && (
            <span className="badge gap" title={build.stale_reason ?? undefined}>out of date</span>
          )}
          {built && !build?.stale && <span className="badge now">built</span>}
          {/* Worth saying before the click, not after: a piece with no model
              call is instant and free, and one with a model call is neither. */}
          {item.model_calls > 0 && !built && (
            <span className="ps-cost" title="This piece needs one model call, and looks for
              recent public items first. It takes a few seconds.">1 model call</span>
          )}
        </div>

        <p className="ps-summary">{item.summary}</p>
        <p className="ps-audience"><span>For</span> {item.audience}</p>

        {item.charts.length > 0 && (
          <ul className="ps-charts" aria-label="Diagrams this carries">
            {item.charts.map((chart) => <li key={chart}>{chart}</li>)}
          </ul>
        )}

        {built && build?.stale && build.stale_reason && (
          <p className="ps-stale">
            <b>Out of date:</b> {build.stale_reason}. Rebuild before sending it to anyone.
          </p>
        )}
        {built && build && !build.has_narrative && item.model_calls > 0 && (
          <p className="ps-stale">
            Built from computed and curated data only — the written sections are absent.
            The document says so on its first page.
          </p>
        )}
      </div>

      <div className="ps-row-side">
        <div className="ps-formats" role="group" aria-label={`Format for ${item.title}`}>
          {item.formats.map((option) => (
            <button key={option.fmt} type="button"
                    aria-pressed={option.fmt === fmt}
                    onClick={() => setFmt(option.fmt)}
                    title={option.built
                      ? `${option.label} — built${option.stale ? ', out of date' : ''}`
                      : `${option.label} — not built yet`}>
              {option.label.replace(/ \(.*\)/, '')}
              {option.built && <span aria-hidden className="ps-dot">●</span>}
            </button>
          ))}
        </div>

        <div className="ps-actions">
          {built ? (
            <>
              {/* A real anchor, not a scripted click: the browser's own download
                  path is more reliable and keeps the right-click menu working. */}
              <a className="btn-link" href={api.collateralDownloadUrl(topicId, item.kind, fmt)}>
                Download
              </a>
              <button type="button" disabled={Boolean(busy)}
                      onClick={() => onGenerate(item.kind, fmt, true)}>
                {working ? <><span className="spinner" /> {elapsed}s</> : 'Rebuild'}
              </button>
            </>
          ) : (
            <button type="button" className="ps-generate" disabled={Boolean(busy)}
                    onClick={() => onGenerate(item.kind, fmt, false)}>
              {working ? <><span className="spinner" /> Generating… {elapsed}s</> : 'Generate'}
            </button>
          )}
        </div>

        {built && build && (
          <p className="ps-meta">
            {kilobytes(build.bytes)} · {build.generated_at?.slice(0, 16).replace('T', ' ')}
          </p>
        )}
      </div>
    </div>
  )
}

export default function PreSalesPanel({ topic, topicId, refreshKey, onHelp }: {
  topic: Topic | null
  topicId: string
  refreshKey?: number
  onHelp?: (topic: string) => void
}) {
  const [items, setItems] = useState<CollateralItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  // A model call plus a research pass takes tens of seconds. A spinner alone
  // reads as "hung" after about ten of them, so the wait is counted out loud.
  const [elapsed, setElapsed] = useState(0)
  const announce = useAnnounce()
  const cancelled = useRef(false)

  useEffect(() => {
    if (!busy) { setElapsed(0); return }
    const started = Date.now()
    const timer = window.setInterval(() => setElapsed(Math.round((Date.now() - started) / 1000)), 1000)
    return () => window.clearInterval(timer)
  }, [busy])

  useEffect(() => {
    cancelled.current = false
    setItems(null)
    setError(null)
    api.presales(topicId)
      .then((index) => { if (!cancelled.current) setItems(index.items) })
      .catch((e) => { if (!cancelled.current) setError(String(e.message ?? e)) })
    return () => { cancelled.current = true }
  }, [topicId, refreshKey])

  const generate = useCallback((kind: string, fmt: string, force: boolean) => {
    setBusy(`${kind}:${fmt}`)
    setError(null)
    announce(`Building ${kind} as ${fmt}. This can take up to a minute.`)
    api.generateCollateral(topicId, kind, fmt, force)
      .then((updated) => {
        // Only the row that changed is replaced. Re-fetching the index would
        // also work and would throw away every format choice on the screen.
        setItems((current) =>
          (current ?? []).map((item) => (item.kind === updated.kind ? updated : item)))
        const bytes = updated.builds[fmt]?.bytes ?? 0
        announce(`${updated.title} ready as ${fmt}, ${Math.round(bytes / 1024)} kilobytes. `
                 + 'It can be downloaded from its row.')
      })
      .catch((e) => {
        setError(String(e.message ?? e))
        announce(`Generation failed: ${String(e.message ?? e)}`)
      })
      .finally(() => setBusy(null))
  }, [topicId, announce])

  const byKind = useMemo(
    () => Object.fromEntries((items ?? []).map((item) => [item.kind, item])),
    [items])
  const builtCount = (items ?? []).filter((item) => item.exists).length

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Pre-sales collateral</h2>
        {onHelp && (
          <button className="help-btn" aria-label="About pre-sales collateral"
                  onClick={() => onHelp('presales')}>?</button>
        )}
        <span className="sub">
          {topic
            ? `${topic.id} · ${builtCount} of ${items?.length ?? 0} built`
            : 'Loading…'}
        </span>
      </div>

      <div className="ps-intro">
        <p>
          The brief is what you take into the first meeting. These are what the team needs
          between that meeting and a proposal. Every piece is built from one snapshot of this
          space, so nothing in the pack can disagree with anything else in it — and each one
          carries the versions that produced it on its last page.
        </p>
        <p className="ps-intro-note">
          Pieces that need a written narrative make one model call and look for recent public
          items first, so the material is current. Anything drawn from those is attributed
          inline and listed at the back. Figures are never generated: they come from this
          space's own sizing.
        </p>
      </div>

      {error && <div className="ps-error">{error}</div>}

      {items === null && !error && <div className="brief-empty">Loading the catalogue…</div>}

      {items !== null && GROUPS.map((group) => {
        const rows = group.kinds.map((kind) => byKind[kind]).filter(Boolean)
        if (rows.length === 0) return null
        return (
          <section key={group.label} className="ps-group">
            <div className="ps-group-head">
              <h3>{group.label}</h3>
              <span>{group.note}</span>
            </div>
            {rows.map((item) => (
              <CollateralRow key={item.kind} item={item} topicId={topicId} busy={busy}
                             elapsed={elapsed} onGenerate={generate} />
            ))}
          </section>
        )
      })}
    </div>
  )
}
