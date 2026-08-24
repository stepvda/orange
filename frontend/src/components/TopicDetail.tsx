import { useEffect, useState } from 'react'
import { api } from '../api'
import ConfirmDelete from './ConfirmDelete'
import type { Meta, Topic } from '../types'
import ScoreBreakdown from './ScoreBreakdown'
import { EvidenceTimeline } from './Charts'
import { AssessmentWidget, ConvictionPanel, StageControl, type WorkflowMeta } from './Workflow'
import { HelpButton } from './Help'
import {
  IconBoard, IconChat, IconClock, IconCube, IconDoc, IconFlame, IconGauge, IconLink, IconMoney, IconPeople, IconTarget, IconThumb, IconTrend, IconVenn, IconVoices,
  SECTION_ICONS,
} from './Icons'
import { rtwColor } from './RadarChart'
import MarketSizePanel, { formatEur } from './MarketSize'
import CompetitionPanel from './Competition'
import DescriptionPanel from './Description'

/** §4.9 Topic detail — "one page, in the order the user's questions arrive":
 *   the opportunity statement;
 *   why it is hot now, with each claim linked to its dated source;
 *   where it can deliver value and for whom;
 *   can we play and can we win, itemised against named Orange assets;
 *   proof points;
 *   the score breakdown, expanded rather than hidden behind a tooltip;
 *   the recommended next action for the current role.
 */

interface Props {
  topicId: string | null
  /** Set when the brief tab is open, so the pane can offer to jump to it. */
  onOpenBrief?: (topicId: string) => void
  role: string
  meta: Meta
  rank?: number
  workflowMeta?: WorkflowMeta | null
  onChanged?: () => void
  refreshKey?: number
  onHelp?: (topic: string) => void
  onExplain?: (topic: Topic) => void
  /** Set by the surfaces that can survive the space disappearing — they have to
   *  clear the selection and re-read the view. Omitted, the remove control does
   *  not render at all: a delete button whose caller cannot handle the delete
   *  leaves the reader looking at a space that is no longer there. */
  onDeleted?: (topicId: string) => void
}

/** The pane answers the user's questions in the order §4.9 puts them, which is
 *  correct and long. These jump to a section rather than reordering it: a
 *  presales engineer wants the assets, a strategist wants the sizing, and both
 *  should still meet the evidence on the way past. */
/** Claims shown before the fold. Four is what fits above the market figures. */
const CLAIM_PREVIEW = 4

/** The nearest ancestor that actually scrolls, or null for the document.
 *
 * Asking the DOM beats naming the container: which element scrolls depends on
 * which surface this pane is rendered into, and a name that is right in one
 * place fails silently in the others.
 */
function scrollParent(element: HTMLElement): HTMLElement | null {
  let node = element.parentElement
  while (node && node !== document.body) {
    const overflow = window.getComputedStyle(node).overflowY
    if ((overflow === 'auto' || overflow === 'scroll') && node.scrollHeight > node.clientHeight) {
      return node
    }
    node = node.parentElement
  }
  return null
}

/** Collapse near-identical claims, keeping every citation.
 *
 * Two claims that differ only in wording are one fact to a reader and two rows
 * on screen. The comparison is deliberately crude — lower-cased, punctuation
 * stripped, first eight words — because what it fixes is near-verbatim
 * repetition from multi-pass synthesis, not paraphrase, and a cleverer rule
 * would start merging things that are genuinely different.
 */
function dedupeClaims(claims: { claim: string; signals: string[] }[]) {
  const byKey = new Map<string, { claim: string; signals: string[] }>()
  for (const entry of claims) {
    const key = entry.claim.toLowerCase().replace(/[^a-z0-9 ]/g, '').split(/\s+/).slice(0, 8).join(' ')
    const existing = byKey.get(key)
    if (existing) {
      existing.signals = [...new Set([...existing.signals, ...entry.signals])]
      if (entry.claim.length > existing.claim.length) existing.claim = entry.claim
    } else {
      byKey.set(key, { claim: entry.claim, signals: [...entry.signals] })
    }
  }
  return [...byKey.values()]
}

const SECTIONS: { id: string; label: string }[] = [
  { id: 'why-hot', label: 'Why now' },
  { id: 'market', label: 'Market' },
  { id: 'competition', label: 'Competition' },
  { id: 'questions', label: 'Ask & answer' },
  { id: 'description', label: 'Description' },
  { id: 'value', label: 'Buyers' },
  { id: 'assets', label: 'Assets' },
  { id: 'score', label: 'Score' },
  { id: 'action', label: 'Next action' },
  { id: 'workflow', label: 'Workflow' },
  { id: 'timeline', label: 'Momentum' },
  { id: 'sources', label: 'Sources' },
]

export default function TopicDetail({ topicId, role, meta, rank, workflowMeta, onChanged, refreshKey, onHelp, onExplain, onOpenBrief, onDeleted }: Props) {
  const [topic, setTopic] = useState<Topic | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [rated, setRated] = useState<string | null>(null)
  const [timeline, setTimeline] = useState<{ month: string; n: number }[]>([])
  const [localKey, setLocalKey] = useState(0)
  const [showAllClaims, setShowAllClaims] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  useEffect(() => {
    setTopic(null)
    setError(null)
    setRated(null)
    setTimeline([])
    setConfirmingDelete(false)
    if (!topicId) return
    api.topic(topicId).then(setTopic).catch((e) => setError(String(e)))
    fetch(`/api/topics/${topicId}/evidence-timeline`)
      .then((r) => r.json())
      .then((d) => setTimeline(d.months ?? []))
      .catch(() => {})
  }, [topicId, refreshKey, localKey])

  const reload = () => { setLocalKey((k) => k + 1); onChanged?.() }

  /** Scroll the pane to a section, and take the reading cursor with it.
   *
   * Two bugs lived in the original four lines. `offsetTop` is measured from the
   * nearest positioned ancestor, which in the side pane IS the pane, so
   * subtracting the pane's own offset overshot every jump by the height of the
   * header. And scrolling alone leaves a keyboard or screen-reader user exactly
   * where they were: the jump has to move focus, or it only works for people
   * who can see the page move.
   *
   * The container is FOUND rather than named. This component now renders on
   * three surfaces — the side pane, the narrow-window detail tab, and full
   * screen — and each scrolls a different element; hardcoding `.detail-pane`
   * meant the jump bar silently did nothing on the other two.
   */
  const jumpTo = (sectionId: string) => {
    const target = document.getElementById(`section-${sectionId}`)
    if (!target) return
    const pane = scrollParent(target)
    // The jump bar is sticky, so the target has to clear it or the heading lands
    // underneath the thing that sent you there.
    const nav = (pane ?? document).querySelector('.detail-nav') as HTMLElement | null
    const clearance = (nav?.offsetHeight ?? 0) + 10
    if (pane) {
      pane.scrollTop += target.getBoundingClientRect().top - pane.getBoundingClientRect().top - clearance
    } else {
      window.scrollBy({ top: target.getBoundingClientRect().top - clearance })
    }
    const heading = target.querySelector('h4')
    if (heading) {
      heading.setAttribute('tabindex', '-1')
      ;(heading as HTMLElement).focus({ preventScroll: true })
    }
  }

  if (!topicId) return <div className="empty">Select a topic on the radar or in the list.</div>
  if (error) return <div className="empty">Could not load {topicId}: {error}</div>
  if (!topic) return <div className="empty">Loading {topicId}…</div>

  // §4.3.4 publishes two methods; the bottom-up estimate is the one the
  // requirements ask for, so it is the one the headline carries.
  const headlineSize = (topic.market_size ?? []).find((m) => m.method === 'bottom_up_adoption')
    ?? (topic.market_size ?? [])[0]
  const signalById = new Map((topic.signals ?? []).map((s) => [s.id, s]))
  const mergedClaims = dedupeClaims(topic.why_hot)
  const visibleClaims = showAllClaims ? mergedClaims : mergedClaims.slice(0, CLAIM_PREVIEW)
  const byType = (types: string[]) => topic.links.filter((l) => types.includes(l.node_type))

  const rate = (verdict: 'useful' | 'not_useful' | 'wrong') => {
    setRated(verdict)
    // DR-15: exposure context travels with the event so engagement can be
    // inverse-propensity weighted against exposure bias (§4.7.6).
    api.feedback({
      role,
      kind: 'rating',
      opportunity_id: topic.id,
      verdict,
      exposure_context: {
        view: 'topic_detail',
        rank_shown: rank ?? null,
        exploration_slot: Boolean(topic.exploration_slot),
        weight_set: topic.attractiveness?.weight_set ?? null,
      },
    }).catch(() => setRated(null))
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'baseline', marginBottom: 8, flexWrap: 'wrap' }}>
        <span className="badge">{topic.id}</span>
        <span className="badge">{topic.state}</span>
        {onHelp && <HelpButton topic="lifecycle" onOpen={onHelp} />}
        {topic.horizon && <span className={`badge ${topic.horizon === 'now' ? 'now' : ''}`}>{topic.horizon.toUpperCase()}</span>}
        <span className="badge" title="Portfolio distance — shortest path to a deliverable configuration (§4.5.3)">
          L{topic.portfolio_distance}
        </span>
        {onHelp && <HelpButton topic="portfolio_distance" onOpen={onHelp} />}
        {topic.exploration_slot && <span className="badge explore">exploration</span>}
      </div>

      <p className="detail-statement">{topic.statement}</p>
      <div className="topic-triple">
        {topic.labels.vertical} × {topic.labels.use_case} × {topic.labels.technology}
      </div>

      {/* The four quantities, above the fold.
          §4.9 asks the pane to answer questions in the order they arrive, and it
          does — but the answers to "how big", "can we win" and "who else is
          here" were at screens 4, 6 and 5 of 10. This is a summary, not a
          substitute: every figure links to the section that derives it, and
          SC-12 still holds — four numbers side by side, never combined. */}
      <dl className="headline-strip">
        <div>
          <dt>Attractiveness</dt>
          <dd><button className="headline-link" onClick={() => jumpTo('score')}>
            {topic.attractiveness?.score?.toFixed(0) ?? '—'}
          </button></dd>
          <dd className="headline-sub">is the world moving</dd>
        </div>
        <div>
          <dt>Right to win</dt>
          <dd><button className="headline-link" onClick={() => jumpTo('assets')}
                      style={{ color: rtwColor(topic.right_to_win?.score) }}>
            {topic.right_to_win?.score?.toFixed(0) ?? '—'}
          </button></dd>
          <dd className="headline-sub">{topic.links.length} named asset{topic.links.length === 1 ? '' : 's'}</dd>
        </div>
        <div>
          <dt>Serviceable market</dt>
          <dd><button className="headline-link" onClick={() => jumpTo('market')}>
            {headlineSize ? formatEur(headlineSize.sam.base) : '—'}
          </button></dd>
          <dd className="headline-sub">
            {headlineSize ? `per year · ${headlineSize.confidence} evidence` : 'not sized'}
          </dd>
        </div>
        <div>
          <dt>Competition</dt>
          <dd>
            <button className="headline-link intensity" data-level={topic.competition?.level ?? 'none'}
                    onClick={() => jumpTo('competition')}>
              {topic.competition?.level_label?.toUpperCase() ?? '—'}
            </button>
          </dd>
          <dd className="headline-sub">
            {topic.competition
              ? `${topic.competition.counts.evidenced} of ${topic.competition.counts.listed} seen in evidence`
              : 'not assessed'}
          </dd>
        </div>
      </dl>

      {topic.next_actions[role] && (
        <div className="action-card action-lead">
          <div className="action-role">
            Do this next — {meta.roles.find((r) => r.id === role)?.label ?? role}
          </div>
          {topic.next_actions[role]}
        </div>
      )}

      <nav className="detail-nav" aria-label="Jump to a section">
        {/* The same mark on the jump entry and on the heading it lands on. A
            jump bar whose entries look nothing like their destinations is a
            second vocabulary to learn. */}
        {SECTIONS.map((section) => {
          const Icon = SECTION_ICONS[section.id]
          return (
            <button key={section.id} onClick={() => jumpTo(section.id)}>
              {Icon && <Icon className="nav-icon" />}{section.label}
            </button>
          )
        })}
      </nav>

      {topic.evidence_gap_warning && (
        <div className="warning-box">
          <span aria-hidden>⚠</span>
          <span>
            <b>Evidence gap.</b>{onHelp && <HelpButton topic="evidence_gap" onOpen={onHelp} />}{' '}
            {topic.reference_density?.published_story_count ?? 0} published reference
            {topic.reference_density?.published_story_count === 1 ? '' : 's'} in{' '}
            {topic.labels.vertical}, below the threshold of {topic.reference_density?.threshold ?? '?'}.
            A customer conversation here has no proof point behind it.
          </span>
        </div>
      )}

      {/* --- why hot: every claim traceable to a signal (FR-14, AC-01) --- */}
      <div className="detail-section" id="section-why-hot">
        <h4><IconFlame />Why it is hot now{onHelp && <HelpButton topic="why_hot" onOpen={onHelp} />}</h4>
        {topic.why_hot.length === 0 && <div style={{ color: 'var(--text-muted)' }}>No evidence-bound claims.</div>}
        {/* Synthesis passes over each cluster several times, so near-identical
            sentences accumulate on a topic and filled the pane's best screenful
            with one fact three times. Merged for display only: the stored claims
            and every citation stay exactly as the pipeline wrote them. */}
        {visibleClaims.map((claim, i) => (
          <div className="claim" key={i}>
            <div>{claim.claim}</div>
            <div className="claim-signals">
              {claim.signals.map((sid) => {
                const signal = signalById.get(sid)
                return (
                  <a className="sig-chip" key={sid} href={signal?.url ?? '#'}
                     target="_blank" rel="noreferrer"
                     title={signal ? `${signal.title}\nTier ${signal.tier} · ${signal.id}` : sid}>
                    {signal
                      ? <>{signal.publisher.replace(/^www\./, '').slice(0, 22)}
                          <span className="sig-date"> {signal.published_at.slice(0, 7)}</span>
                          <span className="sig-tier" data-tier={signal.tier}>t{signal.tier}</span></>
                      : sid}
                  </a>
                )
              })}
            </div>
          </div>
        ))}
        {mergedClaims.length > CLAIM_PREVIEW && (
          <button className="link-button" onClick={() => setShowAllClaims((v) => !v)}>
            {showAllClaims
              ? 'Show fewer'
              : `Show ${mergedClaims.length - CLAIM_PREVIEW} more claim${
                  mergedClaims.length - CLAIM_PREVIEW === 1 ? '' : 's'}`}
          </button>
        )}
      </div>

      {/* --- market size (§4.3.4): the working, not just the number --- */}
      <div className="detail-section" id="section-market">
        <h4><IconMoney />Market opportunity{onHelp && <HelpButton topic="market_size" onOpen={onHelp} />}</h4>
        <MarketSizePanel sizes={topic.market_size ?? []} onHelp={onHelp} />
      </div>

      {/* --- competitive landscape (§4.3.3) --- */}
      <div className="detail-section" id="section-competition">
        <h4><IconVenn />Competition{onHelp && <HelpButton topic="competition" onOpen={onHelp} />}</h4>
        <CompetitionPanel competition={topic.competition} onHelp={onHelp} />
      </div>

      {/* --- what to ask, and what you will be asked back (FR-17, AC-03) ---
              Generated with the description, surfaced separately: a question you
              can ask on Thursday is a different artefact from a page you read. */}
      {(topic.description?.qualifying_questions?.length || topic.description?.objection_handling?.length) ? (
        <div className="detail-section" id="section-questions">
          <h4><IconChat />Questions to ask, objections to expect</h4>
          {topic.description?.qualifying_questions?.length ? (
            <ol className="qa-list">
              {topic.description.qualifying_questions.map((question, index) => (
                <li key={index}>{question}</li>
              ))}
            </ol>
          ) : null}
          {topic.description?.objection_handling?.map((entry, index) => (
            <div key={index} style={{ marginTop: 6 }}>
              <div style={{ fontSize: 12.5, fontWeight: 550 }}>“{entry.objection}”</div>
              <div style={{ fontSize: 12.3, color: 'var(--text-secondary)' }}>{entry.response}</div>
            </div>
          ))}
        </div>
      ) : null}

      {/* --- the generated long-form description (FR-14, FR-18) --- */}
      <div className="detail-section" id="section-description">
        <h4><IconDoc />Detailed description{onHelp && <HelpButton topic="description" onOpen={onHelp} />}</h4>
        <DescriptionPanel topicId={topic.id} description={topic.description}
                          signals={topic.signals} onHelp={onHelp}
                          onRegenerated={reload} />
        {onOpenBrief && (
          <button style={{ marginTop: 8, width: '100%' }} onClick={() => onOpenBrief(topic.id)}>
            {topic.brief?.exists
              ? (topic.brief.stale ? 'Open the PDF brief — out of date' : 'Open the PDF brief')
              : 'Build the PDF brief'}
          </button>
        )}
      </div>

      {/* --- where it delivers value and for whom --- */}
      <div className="detail-section" id="section-value">
        <h4><IconPeople />Where it delivers value, and for whom</h4>
        {/* Three different dimensions were rendered as one undifferentiated
            strip of pills: a reader could not tell a business domain from a
            buyer from a country code. */}
        {([
          ['Business domain', topic.domain_labels],
          ['Who signs', topic.persona_labels],
          ['Where', topic.geographies],
        ] as [string, string[]][]).map(([label, values]) => (
          <div className="labelled-badges" key={label}>
            <span className="labelled-badges-key">{label}</span>
            <span className="labelled-badges-values">
              {values.length === 0
                ? <span style={{ color: 'var(--text-muted)', fontSize: 11.5 }}>none recorded</span>
                : values.map((value) => <span className="badge" key={value}>{value}</span>)}
            </span>
          </div>
        ))}
      </div>

      {/* --- can we play / can we win (FR-15, FR-29, LK-08) --- */}
      <div className="detail-section" id="section-assets">
        <h4><IconCube />Can we play, can we win{onHelp && <HelpButton topic="links" onOpen={onHelp} />}</h4>
        {topic.links.length === 0 && (
          <div style={{ color: 'var(--text-muted)' }}>No linked assets — white space.</div>
        )}
        {['offer', 'partner', 'certification', 'analyst_position', 'capability_pool', 'technology', 'reference']
          .map((type) => {
            const all = byType([type])
            // Ten near-identical "published reference in this vertical, different
            // use case" rows pushed the partners and certifications off screen.
            // The PDF already caps them; the pane now agrees.
            const rows = type === 'reference' ? all.slice(0, 4) : all
            if (all.length === 0) {
              // An absent OFFER group used to render as nothing at all, so
              // "Orange has no offer here" and "we did not check" looked the same.
              return type === 'offer' ? (
                <div key={type} style={{ marginBottom: 10, fontSize: 11.5, color: 'var(--text-muted)' }}>
                  <b>No Orange offer is linked to this space.</b> Whatever is sold here has to be
                  assembled from partners and capability, or built.
                </div>
              ) : null
            }
            return (
              <div key={type} style={{ marginBottom: 10 }}>
                <div style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '.06em', color: 'var(--text-muted)', marginBottom: 3 }}>
                  {type.replace('_', ' ')}
                </div>
                {rows.map((link) => (
                  <div className="link-row" key={link.node_id}>
                    <span className="link-type" title={`${link.link_meaning} — owner: ${link.owner}`}>{link.link_type}</span>
                    <span>
                      {link.label}
                      {!link.confirmed_by && (
                        <span className="unconfirmed"
                              title="LK-06: a named curator has not yet adjudicated this link pattern. That is true of every link today — it is the review queue, not a fault in this one.">
                          {' '}· awaiting curator
                        </span>
                      )}
                      {/* This sentence is what decides whether a reference is a
                          proof point or a coincidence — "same vertical, different
                          use case" is not something to skim past. */}
                      <div className="link-rule">{link.evidence?.rule}</div>
                    </span>
                  </div>
                ))}
                {all.length > rows.length && (
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    + {all.length - rows.length} more published reference
                    {all.length - rows.length === 1 ? '' : 's'} in this vertical, listed in the brief.
                  </div>
                )}
              </div>
            )
          })}
      </div>

      {/* --- score breakdown, expanded (NFR-01, §4.9) --- */}
      <div className="detail-section" id="section-score">
        <h4><IconGauge />Score breakdown{onHelp && <HelpButton topic="attractiveness" onOpen={onHelp} />}</h4>
        <ScoreBreakdown title="Attractiveness" block={topic.attractiveness} weights={meta.attractiveness_weights} />
        <ScoreBreakdown title="Right to win" block={topic.right_to_win} weights={meta.right_to_win_weights} />
        {onExplain && (
          <button style={{ marginTop: 10, width: '100%' }} onClick={() => onExplain(topic)}>
            How was this calculated?
          </button>
        )}
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>
          Attractiveness and right to win answer different questions, so they are never combined
          into a single number.
        </div>
      </div>

      {/* --- horizon derivation (FR-08) --- */}
      <div className="detail-section">
        <h4><IconClock />Time horizon{onHelp && <HelpButton topic="horizon" onOpen={onHelp} />}</h4>
        <div style={{ fontSize: 12.5 }}>
          <b>{topic.horizon?.toUpperCase() ?? '—'}</b>{' '}
          <span style={{ color: 'var(--text-muted)' }}>derived, not judged — basis: {topic.horizon_basis}</span>
        </div>
        <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 4 }}>
          Lifecycle: {topic.state} — {topic.state_reason}
        </div>
      </div>

      {/* --- next action for the current role (FR-17, AC-03) --- */}
      <div className="detail-section" id="section-action">
        <h4><IconTarget />Next action, by role</h4>
        {!topic.next_actions[role] && (
          <div style={{ color: 'var(--text-muted)' }}>No action generated for this role yet.</div>
        )}
        {Object.entries(topic.next_actions).map(([roleId, action]) => (
          <div className={`action-card${roleId === role ? ' own' : ''}`} key={roleId}>
            <div className="action-role">
              {meta.roles.find((r) => r.id === roleId)?.label ?? roleId}
              {roleId === role && ' · yours, repeated from the top'}
            </div>
            {action}
          </div>
        ))}
      </div>

      {/* --- collaboration workflow (FR-25, §4.10) --- */}
      {workflowMeta && (
        <>
          <div className="detail-section" id="section-workflow">
            <h4><IconBoard />Workflow{onHelp && <HelpButton topic="workflow" onOpen={onHelp} />}</h4>
            <StageControl topic={topic} role={role} meta={workflowMeta} onMoved={reload} />
          </div>

          <div className="detail-section">
            <h4><IconVoices />Team conviction{onHelp && <HelpButton topic="conviction" onOpen={onHelp} />}</h4>
            <ConvictionPanel topic={topic} />
            <div style={{ marginTop: 10 }}>
              <AssessmentWidget topic={topic} role={role} meta={workflowMeta} onSubmitted={reload} onHelp={onHelp} />
            </div>
          </div>
        </>
      )}

      {/* --- momentum made visible (§4.6, §4.4.5) --- */}
      <div className="detail-section" id="section-timeline">
        <h4><IconTrend />Evidence over time{onHelp && <HelpButton topic="evidence_timeline" onOpen={onHelp} />}</h4>
        <EvidenceTimeline months={timeline} />
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>
          Momentum is the slope of this series, so the shape is what the number was computed from.
        </div>
      </div>

      {/* --- feedback (FR-23) --- */}
      <div className="detail-section">
        <h4><IconThumb />Is this useful?</h4>
        <div style={{ display: 'flex', gap: 6 }}>
          {(['useful', 'not_useful', 'wrong'] as const).map((verdict) => (
            <button key={verdict} aria-pressed={rated === verdict} onClick={() => rate(verdict)}>
              {verdict.replace('_', ' ')}
            </button>
          ))}
        </div>
        {rated && <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 6 }}>Recorded — thank you.</div>}
      </div>

      {/* --- sources (NFR-02 lineage) --- */}
      <div className="detail-section" id="section-sources">
        <h4><IconLink />Sources ({topic.signals?.length ?? 0}){onHelp && <HelpButton topic="source_tier" onOpen={onHelp} />}</h4>
        <div className="scroll-x">
          <table className="data">
            <thead>
              <tr><th>Signal</th><th>Publisher</th><th>Date</th><th>Type</th><th className="num">Tier</th></tr>
            </thead>
            <tbody>
              {(topic.signals ?? []).slice(0, 25).map((signal) => (
                <tr key={signal.id}>
                  <td><a href={signal.url} target="_blank" rel="noreferrer" title={signal.title}>{signal.title.slice(0, 46)}…</a></td>
                  <td>{signal.publisher}</td>
                  <td style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{signal.published_at}</td>
                  <td style={{ fontSize: 11 }}>{signal.signal_type ?? '—'}</td>
                  <td className="num">{signal.tier}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div style={{ fontSize: 10.5, color: 'var(--text-muted)', fontFamily: 'var(--mono)', marginTop: 14 }}>
        v{topic.version} · first seen {topic.first_seen} · refreshed {topic.last_refresh}<br />
        pipeline {topic.provenance.pipeline_version} · prompt {topic.provenance.prompt_version} · model {topic.provenance.model_version}
      </div>

      {/* --- removing the space ---
          Last, and behind its own rule. Every other control on this pane is
          reversible — regenerate a description, move a stage, rate a topic — and
          this one is not, so it does not sit among them where a mis-click lands
          on it. The dialog behind the button is where the consequence is
          actually spelled out. */}
      {onDeleted && (
        <div className="danger-zone">
          <div>
            <h4>Remove this space</h4>
            <p>
              Deletes {topic.id} and everything attached to it — evidence links, scores, asset
              links, assessments, stage history, sizing, the description and the brief. The
              signals themselves are shared, and stay. You will be shown the full list before
              anything happens.
            </p>
          </div>
          <button className="danger-btn" onClick={() => setConfirmingDelete(true)}>
            Delete space…
          </button>
        </div>
      )}

      {confirmingDelete && onDeleted && (
        <ConfirmDelete
          topicId={topic.id}
          statement={topic.statement}
          onCancel={() => setConfirmingDelete(false)}
          onDeleted={(id) => { setConfirmingDelete(false); onDeleted(id) }} />
      )}
    </div>
  )
}
