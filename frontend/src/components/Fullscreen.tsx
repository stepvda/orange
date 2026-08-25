import { useCallback, useEffect, useRef, useState } from 'react'
import BriefView from './Brief'
import CompetitorAnalysisPanel from './CompetitorAnalysis'
import PreSalesPanel from './PreSales'
import TopicDetail from './TopicDetail'
import type { WorkflowMeta } from './Workflow'
import { HelpButton } from './Help'
import type { Meta, Topic } from '../types'

/** One opportunity space, with nothing else on screen.
 *
 * The three-pane layout is right for working THROUGH the radar — filter, scan,
 * open, compare, move on. It is wrong for the moment somebody actually reads a
 * space: §4.9 gives the detail pane ten sections, and reading them in a 420px
 * column beside a chart they are no longer looking at is the narrowest possible
 * view of the longest content in the interface. This is the same content with
 * the panes out of the way.
 *
 * The brief sits here as a TAB rather than a link because it is the same
 * subject seen twice: the space is what the radar computed, the brief is what
 * gets sent to a customer, and the reason to put them one click apart is that
 * the second is generated from the first and goes stale when it moves. Reading
 * them in the same frame is how anyone notices.
 *
 * The competitor tab is the third view of the same subject: what everyone else
 * is doing in it. It sits between the two because that is the order the
 * questions arrive — what is this, who else is here, what do I send.
 *
 * Pre-sales collateral is last because it is what happens AFTER the brief has
 * been sent and the meeting has happened. The brief is one document for one
 * conversation; that tab is twelve, for the work between that conversation and
 * a proposal, and putting it before the brief would suggest a team should build
 * a tender response before they have had the first meeting.
 */

type Pane = 'space' | 'competitors' | 'brief' | 'presales'

interface Props {
  topic: Topic | null
  topicId: string
  role: string
  meta: Meta
  workflowMeta?: WorkflowMeta | null
  refreshKey?: number
  rank?: number
  onChanged?: () => void
  onHelp: (topic: string) => void
  onExplain: (topic: Topic) => void
  onClose: () => void
  /** Passed through to the detail pane. Full screen shows ONE space, so when it
   *  is deleted this screen has nothing left to display — App closes it. */
  onDeleted?: (topicId: string) => void
}

export default function SpaceFullscreen({
  topic, topicId, role, meta, workflowMeta, refreshKey, rank, onChanged, onHelp, onExplain, onClose,
  onDeleted,
}: Props) {
  const [pane, setPane] = useState<Pane>('space')
  const closeRef = useRef<HTMLButtonElement | null>(null)

  // Escape is what people press. Bound on the document rather than a wrapper,
  // because focus legitimately travels into the PDF object, and a keydown that
  // only fires while a div holds focus would stop working exactly there.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      // The help and score-explanation dialogs bind Escape on the document too.
      // Without this, one press closes the dialog AND the screen behind it, and
      // the reader loses the space they were reading about.
      if (document.querySelector('.help-backdrop')) return
      onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  // Entering full screen removes everything the keyboard user was navigating,
  // so focus goes to the control that brings it back rather than to <body>.
  useEffect(() => { closeRef.current?.focus() }, [])

  const select = useCallback((next: Pane) => () => setPane(next), [])
  const briefStale = topic?.brief?.exists && topic.brief.stale

  return (
    <div className="fs-screen">
      <div className="fs-head">
        <div className="fs-title">
          <div className="fs-badges">
            <span className="badge">{topicId}</span>
            {topic && <span className="badge">{topic.state}</span>}
            {topic?.horizon && (
              <span className={`badge ${topic.horizon === 'now' ? 'now' : ''}`}>
                {topic.horizon.toUpperCase()}
              </span>
            )}
            {topic && (
              <span className="badge" title="Portfolio distance — shortest path to a deliverable configuration (§4.5.3)">
                L{topic.portfolio_distance}
              </span>
            )}
          </div>
          <h2>{topic?.statement ?? 'Loading…'}</h2>
          {topic && (
            <p className="fs-triple">
              {topic.labels.vertical} × {topic.labels.use_case} × {topic.labels.technology}
            </p>
          )}
        </div>

        <span className="spacer" />

        <div className="fs-panes" role="group" aria-label="View">
          <button aria-pressed={pane === 'space'} onClick={select('space')}>Opportunity space</button>
          <button aria-pressed={pane === 'competitors'} onClick={select('competitors')}
                  title="What each competitor on this space is doing, and how Orange differentiates against each of them">
            Competitors
          </button>
          <button aria-pressed={pane === 'brief'} onClick={select('brief')}>
            Sales brief
            {/* The one fact worth carrying onto the tab itself: a brief built
                against an older version of the space is worse than none, and
                the whole point of having both here is to catch that. */}
            {briefStale && <span className="fs-stale-dot" title="This brief is out of date">●</span>}
          </button>
          <button aria-pressed={pane === 'presales'} onClick={select('presales')}
                  title="Discovery, battlecards, solution outline, business case, PoC scope, tender blocks — in PDF, Office or OpenDocument">
            Pre-sales
          </button>
        </div>

        <div className="fs-help">
          <span>Help</span>
          <HelpButton topic="attractiveness" onOpen={onHelp} label="A" />
          <HelpButton topic="right_to_win" onOpen={onHelp} label="W" />
          <HelpButton topic="conviction" onOpen={onHelp} label="C" />
          <HelpButton topic="portfolio_distance" onOpen={onHelp} label="L" />
        </div>

        <button className="fs-exit" ref={closeRef} onClick={onClose}
                title="Back to the radar (Esc)">
          <span aria-hidden>↙</span> Exit full screen
        </button>
      </div>

      <div className="fs-body">
        {pane === 'space' && (
          <div className="fs-space">
            <TopicDetail topicId={topicId} role={role} meta={meta}
                         workflowMeta={workflowMeta}
                         onChanged={onChanged}
                         refreshKey={refreshKey}
                         onHelp={onHelp}
                         onExplain={onExplain}
                         onDeleted={onDeleted}
                         onOpenBrief={() => setPane('brief')}
                         rank={rank} />
          </div>
        )}
        {pane === 'competitors' && (
          <div className="fs-space">
            <CompetitorAnalysisPanel topicId={topicId} refreshKey={refreshKey} onHelp={onHelp} />
          </div>
        )}
        {pane === 'brief' && <BriefView topic={topic} onHelp={onHelp} />}
        {pane === 'presales' && (
          <div className="fs-space">
            <PreSalesPanel topic={topic} topicId={topicId} refreshKey={refreshKey}
                           onHelp={onHelp} />
          </div>
        )}
      </div>
    </div>
  )
}
