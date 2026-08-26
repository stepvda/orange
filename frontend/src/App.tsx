import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import BriefView from './components/Brief'
import Filters from './components/Filters'
import RadarChart, { RadarLegend, rtwColor } from './components/RadarChart'
import TopicDetail from './components/TopicDetail'
import { Board, type BoardData, type WorkflowMeta } from './components/Workflow'
import { BarList, ChartCard, DivergenceChart, Heatmap, Kpi, StackedBar, StageFunnel } from './components/Charts'
import { HelpButton, HelpModal } from './components/Help'
import { countryNames } from './geo'
import GenerateScreen from './components/Generate'
import SpaceFullscreen from './components/Fullscreen'
import PlannerScreen from './components/Planner'
import ScoreExplainModal from './components/ScoreExplain'
import HowBuilt from './components/HowBuilt'
import { LoginScreen, PasswordDialog } from './components/Login'
import { useAnnounce } from './components/Announcer'
import {
  IconAutoTheme, IconBars, IconBoard, IconCalendar, IconClipboard, IconCompass,
  IconCoverageGrid, IconDoc, IconList, IconMoon, IconPanel, IconPerson, IconRadar,
  IconRoute, IconSignOut, IconSpark, IconSun, IconTag, IconWhitespace,
} from './components/Icons'
import { formatEur } from './components/MarketSize'
import { api, setSessionEndedHandler } from './api'
import type { Coverage, FilterState, Meta, RadarView, SessionInfo, SortId, Topic, User } from './types'
import { EMPTY_FILTERS } from './types'

type Tab = 'radar' | 'list' | 'brief' | 'detail' | 'workflow' | 'analytics' | 'whitespace' | 'coverage'

/** Radar and List are ONE view rendered two ways — the same ranked set, plotted
 *  against the two axes or laid out as rows — so they are boxed together the way
 *  the roles are. Which of the two you want is a rendering preference; the four
 *  after them are different questions about the corpus. */
const RANKED_TABS: readonly Tab[] = ['radar', 'list'] as const
const OTHER_TABS: readonly Tab[] = ['brief', 'analytics', 'whitespace', 'coverage'] as const

/* `workflow` is in neither: it is still a tab — it renders inside the reading
   layout like the rest — but it is READ beside Generate and Planner, because
   those three are what a team does TO the portfolio rather than ways of looking
   at it. It is rendered in that tray. */

const TAB_LABELS: Record<Tab, string> = {
  radar: 'Radar', list: 'List', brief: 'Brief', detail: 'Detail',
  workflow: 'Workflow', analytics: 'Analytics', whitespace: 'White space', coverage: 'Coverage',
}

const TAB_ICONS: Record<Tab, (props: { className?: string }) => JSX.Element> = {
  radar: IconRadar, list: IconList, brief: IconDoc, detail: IconPanel,
  workflow: IconBoard, analytics: IconBars, whitespace: IconWhitespace, coverage: IconCoverageGrid,
}

/** Role id -> mark. Keyed off the ids in `role_modes.yaml`; an id this does not
 *  know still gets a button, with the generic person mark, rather than a hole. */
const ROLE_ICONS: Record<string, (props: { className?: string }) => JSX.Element> = {
  strategist: IconCompass, sales: IconTag, presales: IconClipboard,
}

/** A top-bar label, set on up to two lines.
 *
 * The row has to hold fourteen controls on one line at 2560px, and its widest
 * labels are two halves of one thing — "White space", "Presales / Proposal".
 * Stacking those halves costs no height (every button in the row is one fixed
 * height, so the two-line ones were already paying for the space) and buys back
 * the width that was pushing Generate and the account onto a second row.
 *
 * The slash goes with the break. It was only ever there to separate the two
 * halves and the line break already does that. Nothing is lost to a screen
 * reader: the button carries the unbroken label as its accessible name.
 */
function TopLabel({ text }: { text: string }) {
  const parts = text.includes(' / ') ? text.split(' / ')
    : text.split(' ').length === 2 ? text.split(' ')
    : [text]
  return <span className="btn-label">{parts.map((part, i) => <span key={i}>{part}</span>)}</span>
}

/** Pane geometry (§4.9 is about what the screen says, not how wide it is — but
 *  a brief in the middle pane and a decomposition in the right one are both
 *  reading surfaces, and which one a user wants larger changes by task). */
const DETAIL_MIN = 300
const DETAIL_MAX = 900
const DETAIL_DEFAULT = 420
const FILTERS_WIDTH = 236
const FILTERS_COLLAPSED = 44
const STORE_KEY = 'radar.layout.v1'

interface Layout { detailWidth: number; filtersCollapsed: boolean; detailHidden: boolean }

/** Track a media query in React state, so layout decisions can follow it. */
function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches)
  useEffect(() => {
    const list = window.matchMedia(query)
    const onChange = (event: MediaQueryListEvent) => setMatches(event.matches)
    list.addEventListener('change', onChange)
    setMatches(list.matches)
    return () => list.removeEventListener('change', onChange)
  }, [query])
  return matches
}

function loadLayout(): Layout {
  try {
    const raw = window.localStorage.getItem(STORE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      return {
        detailWidth: Math.min(DETAIL_MAX, Math.max(DETAIL_MIN, Number(parsed.detailWidth) || DETAIL_DEFAULT)),
        filtersCollapsed: Boolean(parsed.filtersCollapsed),
        detailHidden: Boolean(parsed.detailHidden),
      }
    }
  } catch { /* a corrupt preference is not worth an error path */ }
  return { detailWidth: DETAIL_DEFAULT, filtersCollapsed: false, detailHidden: false }
}

/** Initial state from the URL, so a topic view is shareable.
 *
 * A salesperson finding a topic and sending it to a colleague is the normal way
 * this tool spreads inside an organisation, so ?topic=OS012 has to survive a
 * copy-paste. ?role and ?theme ride along for the same reason.
 */
const FILTER_KEYS = ['vertical', 'domain', 'persona', 'geography', 'market_cluster', 'horizon', 'competition'] as const

function initialFromUrl() {
  const params = new URLSearchParams(window.location.search)
  const theme = params.get('theme')
  // A prepared view — "CISO topics in manufacturing, least contested first" — is
  // the thing people actually want to send each other, and it was the one piece
  // of state that never reached the address bar.
  const filters: FilterState = { ...EMPTY_FILTERS }
  for (const key of FILTER_KEYS) {
    const value = params.get(key)
    if (value) filters[key] = value.split(',').filter(Boolean)
  }
  filters.q = params.get('q') ?? ''
  filters.has_brief = params.get('has_brief') === '1'
  return {
    topic: params.get('topic'),
    explain: params.get('explain'),
    role: params.get('role'),
    tab: params.get('tab') as Tab | null,
    // A whole screen rather than a tab, so it takes the address bar the same
    // way: "open the generator with manufacturing selected" has to survive
    // being sent to someone.
    generate: params.get('screen') === 'generate',
    // ?view=full rides along with ?topic, so "read this one properly" is as
    // shareable as the topic itself.
    fullscreen: params.get('view') === 'full',
    planner: params.get('view') === 'planner',
    sort: (params.get('sort') ?? 'rank') as SortId,
    filters,
    theme: (theme === 'dark' || theme === 'light' ? theme : 'auto') as 'auto' | 'light' | 'dark',
  }
}

/** AC-05's cap, with the way out AND the way back.
 *
 * Lifting the cap to 148 turns the radar into a blob, and there was no control
 * to undo it — the only route back to a readable view was a page reload.
 */
function ShowMore({ view, limit, setLimit }: {
  view: RadarView | null
  limit: number | null
  setLimit: (value: number | null) => void
}) {
  if (!view) return null
  const shownCount = view.topics.length + view.exploration.length
  if (view.total_matching <= shownCount && limit === null) return null
  return (
    <div className="show-more">
      {view.total_matching > shownCount ? (
        <>
          <span>
            {view.total_matching - shownCount} more match. The view shows {view.cap} at a time,
            so the list stays readable.
          </span>
          <button onClick={() => setLimit((limit ?? view.cap ?? 24) + (view.cap ?? 24))}>
            Show {Math.min(view.cap ?? 24, view.total_matching - shownCount)} more
          </button>
          <button onClick={() => setLimit(view.total_matching)}>
            Show all {view.total_matching}
          </button>
        </>
      ) : (
        <span>Showing all {view.total_matching} that match.</span>
      )}
      {limit !== null && (
        <button onClick={() => setLimit(null)}>Back to the top {view.cap}</button>
      )}
    </div>
  )
}

interface RadarProps {
  user: User
  minPasswordLength: number
  onSignedOut: () => void
  onUserChanged: (user: User) => void
}

/** The radar itself, mounted only once there is a session behind it.
 *
 * Splitting this out of the sign-in gate is not tidiness. Every screen in here
 * opens by fetching — meta, the view, the workflow board — and mounting it for a
 * signed-out visitor would fire a dozen requests that all answer 401, painting
 * the error state of eight panels behind a login form. Not rendering it until
 * there is a session means the first request it makes is one that can succeed,
 * and signing out unmounts it, which discards the data with the session rather
 * than leaving it on screen.
 */
function RadarApp({ user, minPasswordLength, onSignedOut, onUserChanged }: RadarProps) {
  const initial = useMemo(initialFromUrl, [])
  const [meta, setMeta] = useState<Meta | null>(null)
  const [role, setRole] = useState(initial.role ?? 'strategist')
  const [filters, setFilters] = useState<FilterState>(initial.filters)
  const [sort, setSort] = useState<SortId>(initial.sort)
  const [view, setView] = useState<RadarView | null>(null)
  // "Nothing matched" and "nothing has arrived yet" look identical if you
  // only track the data. They are opposite messages to a user, so the
  // in-flight state is tracked separately.
  const [viewLoading, setViewLoading] = useState(true)
  const [selected, setSelected] = useState<string | null>(initial.topic)
  const [tab, setTab] = useState<Tab>(initial.tab ?? 'radar')
  // The generator is a SCREEN, not a tab: it writes to the corpus rather than
  // reading a view of it, and the filter rail beside the tabs means something
  // different there (what to constrain generation to, not what to display), so
  // showing them together would be two controls with one appearance.
  const [generating, setGenerating] = useState(initial.generate)
  // Reading one space with nothing else on screen. Distinct from the `detail`
  // TAB, which is the responsive fallback below 1080px and still sits inside
  // the layout: this replaces the layout, and it carries the brief with it.
  const [fullscreen, setFullscreen] = useState(initial.fullscreen)
  // The Planner is a screen, not a tab: it is a statement about the portfolio
  // rather than about any one space, so it takes the whole window.
  const [planner, setPlanner] = useState(initial.planner)
  const [whitespace, setWhitespace] = useState<Topic[]>([])
  const [whitespaceTotal, setWhitespaceTotal] = useState(0)
  const [coverage, setCoverage] = useState<Coverage | null>(null)
  const [board, setBoard] = useState<BoardData | null>(null)
  const [wfMeta, setWfMeta] = useState<WorkflowMeta | null>(null)
  // A failed stage move, said where the move was made. The `error` state above
  // is the cannot-reach-the-API screen and is only rendered before `meta`
  // arrives, so routing this through it would have failed silently.
  const [moveError, setMoveError] = useState<string | null>(null)
  const [summary, setSummary] = useState<any | null>(null)
  const [gridData, setGridData] = useState<any | null>(null)
  const [divergent, setDivergent] = useState<any[]>([])
  const [sizing, setSizing] = useState<any | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)
  // AC-05 caps the DEFAULT view for signal-to-noise. It does not require
  // hiding the rest with no way to ask — without this, adding 99 topics to
  // the corpus changed nothing a user could see.
  const [limit, setLimit] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [theme, setTheme] = useState<'auto' | 'light' | 'dark'>(initial.theme)
  const [help, setHelp] = useState<string | null>(null)
  // The method explainer. Separate from `help`, which is a lookup keyed by
  // topic: this one is a single long-form page about the pipeline as a whole,
  // and it is reached from the radar rather than from a heading.
  const [howBuilt, setHowBuilt] = useState(false)
  const [explaining, setExplaining] = useState<Topic | null>(null)
  const [selectedTopic, setSelectedTopic] = useState<Topic | null>(null)
  const [layout, setLayout] = useState(loadLayout)
  const [dragging, setDragging] = useState(false)
  const [changingPassword, setChangingPassword] = useState(false)
  // Named rather than counted: after a delete the space is gone from every pane
  // at once, and "OS041 deleted" is the only thing left that says which one.
  const [deleted, setDeleted] = useState<string | null>(null)
  const announce = useAnnounce()
  const detailHidden = layout.detailHidden ?? false
  const layoutRef = useRef<HTMLDivElement | null>(null)
  // The detail pane is hidden by the responsive rules below 1080px — which is
  // also what 200% browser zoom looks like to CSS. Everything in it would be
  // unreachable, so the middle pane takes it over instead of it disappearing.
  const compact = useMediaQuery('(max-width: 1080px)')
  // Collapsing a pane destroys the control that did it. Without moving focus to
  // the control that undoes it, a keyboard user is dropped on <body> and has to
  // tab from the top of the document to get back.
  const filterToggleRef = useRef<HTMLButtonElement | null>(null)
  const detailRestoreRef = useRef<HTMLButtonElement | null>(null)
  const fullscreenRef = useRef<HTMLButtonElement | null>(null)
  const pendingFocus = useRef<'filters' | 'detail' | 'fullscreen' | null>(null)

  useEffect(() => {
    if (pendingFocus.current === 'filters') filterToggleRef.current?.focus()
    if (pendingFocus.current === 'detail') detailRestoreRef.current?.focus()
    if (pendingFocus.current === 'fullscreen') fullscreenRef.current?.focus()
    pendingFocus.current = null
  }, [layout.filtersCollapsed, layout.detailHidden, fullscreen])
  // The list view carries only summary scores; the explanation needs the
  // stored per-component inputs, which live on the detail endpoint.
  const openExplain = useCallback((id: string) => {
    api.topic(id).then(setExplaining).catch(() => {})
  }, [])

  useEffect(() => {
    try { window.localStorage.setItem(STORE_KEY, JSON.stringify(layout)) } catch { /* private mode */ }
  }, [layout])

  // The brief tab and the list rows both need the full topic, so it is fetched
  // once here rather than twice in two panes.
  useEffect(() => {
    if (!selected) { setSelectedTopic(null); return }
    let cancelled = false
    api.topic(selected)
      .then((t) => { if (!cancelled) setSelectedTopic(t) })
      .catch(() => { if (!cancelled) setSelectedTopic(null) })
    return () => { cancelled = true }
  }, [selected, refreshKey])

  /** Drag the boundary between the middle and right panes.
   *
   * Pointer events rather than mouse events, so a trackpad, a touchscreen and a
   * pen all work; capture on the handle, so the drag survives the pointer
   * leaving it; and the width is clamped, because a 40px detail pane is not a
   * choice anyone meant to make.
   */
  const onSplitterDown = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    event.preventDefault()
    const handle = event.currentTarget
    handle.setPointerCapture(event.pointerId)
    setDragging(true)
    document.body.dataset.resizing = 'true'
    const move = (moveEvent: PointerEvent) => {
      const container = layoutRef.current
      if (!container) return
      const right = container.getBoundingClientRect().right
      const width = Math.min(DETAIL_MAX, Math.max(DETAIL_MIN, right - moveEvent.clientX))
      setLayout((current) => ({ ...current, detailWidth: width }))
    }
    const up = () => {
      setDragging(false)
      delete document.body.dataset.resizing
      handle.removeEventListener('pointermove', move)
      handle.removeEventListener('pointerup', up)
      handle.removeEventListener('pointercancel', up)
    }
    handle.addEventListener('pointermove', move)
    handle.addEventListener('pointerup', up)
    handle.addEventListener('pointercancel', up)
  }, [])

  const onSplitterKey = useCallback((event: React.KeyboardEvent<HTMLDivElement>) => {
    const step = event.shiftKey ? 64 : 16
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault()
      setLayout((current) => ({
        ...current,
        detailWidth: Math.min(DETAIL_MAX, Math.max(DETAIL_MIN,
          current.detailWidth + (event.key === 'ArrowLeft' ? step : -step))),
      }))
    }
    if (event.key === 'Home' || event.key === 'Enter') {
      event.preventDefault()
      setLayout((current) => ({ ...current, detailWidth: DETAIL_DEFAULT }))
    }
  }, [])

  // "?explain=OS001" makes a score explanation shareable — "here is exactly why
  // this scored what it did" is the message people actually forward.
  useEffect(() => {
    if (initial.explain) openExplain(initial.explain)
  }, [initial.explain, openExplain])

  // Keep the address bar in step without adding history entries.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    selected ? params.set('topic', selected) : params.delete('topic')
    role === 'strategist' ? params.delete('role') : params.set('role', role)
    tab === 'radar' ? params.delete('tab') : params.set('tab', tab)
    generating ? params.set('screen', 'generate') : params.delete('screen')
    if (planner) params.set('view', 'planner')
    else if (fullscreen && selected) params.set('view', 'full')
    else params.delete('view')
    theme === 'auto' ? params.delete('theme') : params.set('theme', theme)
    sort === 'rank' ? params.delete('sort') : params.set('sort', sort)
    for (const key of FILTER_KEYS) {
      filters[key].length ? params.set(key, filters[key].join(',')) : params.delete(key)
    }
    filters.q ? params.set('q', filters.q) : params.delete('q')
    filters.has_brief ? params.set('has_brief', '1') : params.delete('has_brief')
    const query = params.toString()
    window.history.replaceState(null, '', query ? `?${query}` : window.location.pathname)
  }, [selected, role, tab, theme, sort, filters, generating, fullscreen, planner])

  useEffect(() => {
    api.meta().then(setMeta).catch((e) => setError(String(e)))
    fetch('/api/workflow/meta').then((r) => r.json()).then(setWfMeta).catch(() => {})
  }, [])

  useEffect(() => {
    if (theme === 'auto') document.documentElement.removeAttribute('data-theme')
    else document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  useEffect(() => {
    let cancelled = false
    setViewLoading(true)
    api.view(role, filters, limit, sort)
      .then((v) => { if (!cancelled) { setView(v); setError(null) } })
      .catch((e) => { if (!cancelled) setError(String(e)) })
      .finally(() => { if (!cancelled) setViewLoading(false) })
    return () => { cancelled = true }
    // refreshKey is in here so a generation run that added spaces is reflected
    // without a reload: the radar behind the generator is stale the moment it
    // finishes.
  }, [role, filters, limit, sort, refreshKey])

  useEffect(() => { setLimit(null) }, [role, filters, sort])

  useEffect(() => {
    if (tab === 'whitespace') {
      // Refetched on every filter change: the rail is visible on this tab, so
      // it has to mean something here too.
      api.whitespace(filters).then((w) => {
        setWhitespace(w.topics)
        setWhitespaceTotal(w.total_unfiltered)
      }).catch(() => {})
    }
    if (tab === 'coverage' && !coverage) {
      api.coverage().then(setCoverage).catch(() => {})
    }
    if (tab === 'workflow') {
      fetch(`/api/workflow/board?role=${role}`).then((r) => r.json()).then(setBoard).catch(() => {})
    }
    if (tab === 'analytics') {
      fetch('/api/analytics/summary').then((r) => r.json()).then(setSummary).catch(() => {})
      fetch('/api/analytics/grid').then((r) => r.json()).then(setGridData).catch(() => {})
      fetch('/api/divergence').then((r) => r.json()).then((d) => setDivergent(d.topics ?? [])).catch(() => {})
      fetch('/api/analytics/market-size').then((r) => r.json()).then(setSizing).catch(() => {})
    }
  }, [tab, coverage, role, refreshKey, filters])

  // The exploration slot is shown INSIDE the list, marked, so the randomised
  // sample actually gets seen — that is the point of the remedy (§4.7.6).
  const shown = useMemo(
    () => (view ? [...view.topics, ...view.exploration] : []),
    [view],
  )

  // Shown on the collapsed rail: a filter you cannot see is a filter you forget
  // you set, and then the radar looks empty for no visible reason.
  // Which tabs the rail actually drives. Analytics and Coverage are corpus-level
  // by construction, and a live control that changes nothing is worse than an
  // absent one — the strategist lens read the unchanged analytics as filtered.
  /* The filter rail, the splitter and the detail pane are sticky under the top
     bar, and they used to start at a hardcoded 58px. The bar is no longer that
     height — and it was never really a constant: it wraps on a narrow window,
     and its small-print line has no refresh stamp on it until the first refresh
     lands. So it is measured. The CSS carries a default for the first paint. */
  // A CALLBACK ref, not an effect over a ref object. The header is not in the
  // tree on the first render — this component returns a loading state until
  // `meta` arrives — so a mount effect ran against a null ref, returned, and
  // never fired again, leaving every pane below aligned to the CSS fallback
  // rather than to the bar. A callback ref runs when the node itself attaches.
  const headerObserver = useRef<ResizeObserver | null>(null)
  const headerRef = useCallback((el: HTMLElement | null) => {
    headerObserver.current?.disconnect()
    headerObserver.current = null
    if (!el || typeof ResizeObserver === 'undefined') return
    const apply = () => document.documentElement.style
      .setProperty('--topbar-h', `${Math.round(el.getBoundingClientRect().height)}px`)
    apply()
    headerObserver.current = new ResizeObserver(apply)
    headerObserver.current.observe(el)
  }, [])

  /** Move a space to another stage from the board itself.
   *
   * The card moves before the server answers. A stage gate is used by dragging
   * eight or nine cards in a sitting, and a board that snaps back for a
   * round-trip after every one of them cannot be dragged at speed. The refetch
   * behind it is what makes it true — the stage owner, the age-in-stage clock
   * and the column counts are all computed server-side, so the optimistic card
   * is right about where it is and stale about everything else for one tick.
   *
   * A rejected move is not patched up locally: the board is refetched, which
   * puts the card back where the server says it belongs. Guessing at the undo
   * is how two versions of "where is OS-103" end up on one screen.
   */
  const moveStage = useCallback(async (topicId: string, toStage: string) => {
    setBoard((current) => {
      if (!current) return current
      const card = current.stages.flatMap((s) => s.topics).find((t) => t.id === topicId)
      if (!card) return current
      return {
        ...current,
        stages: current.stages.map((s) => {
          if (s.id === toStage) return { ...s, count: s.count + 1, topics: [card, ...s.topics] }
          if (!s.topics.some((t) => t.id === topicId)) return s
          return { ...s, count: Math.max(0, s.count - 1), topics: s.topics.filter((t) => t.id !== topicId) }
        }),
      }
    })
    const label = wfMeta?.stages.find((s) => s.id === toStage)?.label
      ?? wfMeta?.terminal_stages.find((s) => s.id === toStage)?.label ?? toStage
    try {
      const res = await fetch(`/api/topics/${topicId}/stage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ to_stage: toStage, actor: `${role}@demo`, actor_role: role }),
      })
      if (!res.ok) throw new Error(`${res.status}`)
      announce(`${topicId} moved to ${label}`)
      setMoveError(null)
      // The move changes the topic's own workflow block, which the detail pane
      // and the planner both read, so it is a corpus change and not a board one.
      setRefreshKey((k) => k + 1)
    } catch {
      setMoveError(`${topicId} could not be moved to ${label} — it is back where it was.`)
    } finally {
      fetch(`/api/workflow/board?role=${role}`).then((r) => r.json()).then(setBoard).catch(() => {})
    }
  }, [role, wfMeta, announce])

  /** Open a view tab, leaving whatever full screen is over it.
   *
   * Generate, the Planner and the fullscreen reader all hide `.layout` rather
   * than unmount it, so a tab click that only set `tab` used to look pressed
   * while the screen in front of it did not move. Every one of these is "show
   * me this view", so every one of them closes what is covering the view. */
  const openTab = useCallback((next: Tab) => {
    setTab(next); setGenerating(false); setFullscreen(false); setPlanner(false)
  }, [])

  /** One view tab. A factory rather than a repeated block: the tabs are drawn
   *  in three places in the row now — the compact-only reading pane, the boxed
   *  Radar/List pair, and the four loose ones after it — and three copies of
   *  the same button is three places for them to drift apart. */
  const tabButton = useCallback((t: Tab) => {
    const Icon = TAB_ICONS[t]
    return (
      <button key={t} className="topbtn"
              aria-pressed={tab === t && !generating && !fullscreen && !planner}
              aria-label={TAB_LABELS[t]}
              onClick={() => openTab(t)}>
        <Icon className="btn-icon" />
        <TopLabel text={TAB_LABELS[t]} />
      </button>
    )
  }, [tab, generating, fullscreen, planner, openTab])

  const filtersApply = tab === 'radar' || tab === 'list' || tab === 'whitespace'

  const activeFilterCount = useMemo(
    () => filters.vertical.length + filters.domain.length + filters.persona.length
      + filters.geography.length + filters.market_cluster.length
      + filters.horizon.length + (filters.q ? 1 : 0),
    [filters],
  )

  const activeFilterSummary = useMemo(() => {
    const parts = [
      ...filters.vertical.map((v) => meta?.verticals.find((x) => x.id === v)?.label ?? v),
      ...filters.domain.map((d) => meta?.domains.find((x) => x.id === d)?.label ?? d),
      ...filters.persona.map((p) => meta?.personas.find((x) => x.id === p)?.label ?? p),
      ...filters.geography,
      ...filters.market_cluster.map((c) => meta?.market_clusters.find((m) => m.id === c)?.label ?? c),
      ...filters.horizon,
    ]
    if (filters.q) parts.push(`“${filters.q}”`)
    return parts.length ? `Active filters: ${parts.join(', ')}` : 'No filters set'
  }, [filters, meta])

  // Countries on screen, plus whatever is selected. The second half matters
  // because selecting a market cluster ticks its members: a code the current
  // result set does not carry would otherwise be filtering invisibly, with no
  // row to untick. It also fixes the older version of the same problem — pick a
  // country, narrow until nothing carries it, and the control vanished.
  const geographies = useMemo(() => {
    const set = new Set<string>(filters.geography)
    for (const topic of shown) topic.geographies.forEach((g) => set.add(g))
    return [...set].sort()
  }, [shown, filters.geography])

  // The whole vocabulary, in the order Orange gave it — not the subset that
  // happens to appear in the current page of results.
  //
  // This previously filtered to clusters present in `shown`, which is the capped
  // list, so Benelux, DACH, Nordics, Eastern Europe and Africa simply vanished
  // from the rail. Every other dimension passes its full vocabulary straight
  // through and lets MultiSelect grey out the zeroes — "there are none of these"
  // is information, and a control that disappears cannot be used to look for
  // what is missing.
  const marketClusters = useMemo(() => meta?.market_clusters ?? [], [meta])

  // Selecting a topic when there is no side pane has to go somewhere; silently
  // updating a pane the reader cannot see is how the content went missing.
  const selectAndShow = useCallback((id: string) => {
    setSelected(id)
    if (compact) setTab('detail')
  }, [compact])

  /** A space has just been removed.
   *
   * Everything on screen that referenced it is now referencing something that
   * does not exist — the selection, the detail pane, full screen, and the view
   * the row was drawn from. All four are cleared here rather than left to
   * discover the 404 separately, which is what produced "Could not load OS041"
   * in three panes at once.
   */
  const onTopicDeleted = useCallback((id: string) => {
    setSelected((current) => (current === id ? null : current))
    setSelectedTopic(null)
    setFullscreen(false)
    setExplaining((current) => (current?.id === id ? null : current))
    setDeleted(id)
    setRefreshKey((k) => k + 1)
    announce(`Opportunity space ${id} deleted.`)
  }, [announce])

  /** Order control.
   *
   * The blocker it fixes: the five largest sized opportunities in the radar were
   * unreachable from the default view, because the only ordering was the role's
   * ranking function and the view is capped at 24 (AC-05). Sorting re-orders
   * what the role may see; it never widens it — a salesperson sorting by market
   * size still cannot reach white space (§4.5.3), and the label says so.
   */
  const sortControl = meta && (
    <label className="sort-control">
      <span>Order</span>
      <select value={sort} onChange={(e) => setSort(e.target.value as SortId)}
              title="Re-orders the topics this role can see. It does not change which topics that is.">
        {(meta.sorts ?? [{ id: 'rank' as SortId, label: 'Ranked for this role' }]).map((option) => (
          <option key={option.id} value={option.id}>{option.label}</option>
        ))}
      </select>
    </label>
  )

  if (error && !meta) {
    return (
      <div className="empty">
        <p>Cannot reach the radar API.</p>
        <p style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{error}</p>
        <p>Start it with <code>radar serve</code> (or <code>python -m radar.cli serve</code>).</p>
      </div>
    )
  }
  if (!meta) return <div className="empty">Loading…</div>

  const activeRole = meta.roles.find((r) => r.id === role)
  const selectedRank = shown.findIndex((t) => t.id === selected)

  return (
    <div className="app">
      {/* The target is inside the reading layout, which the generator hides —
          a skip link that lands on a hidden element is worse than none. */}
      {!generating && !fullscreen && <a className="skip-link" href="#main-pane">Skip to the topics</a>}
      <header className="topbar" ref={headerRef}>
        {/* One row of controls, one line of small print underneath it.
            The freshness stamp and the weight-set id were sitting between the
            tabs and the actions, and on a 2560px screen they were enough to
            push Generate and the account onto a second row — they are things
            the bar STATES, not things it offers, so they read below where a
            caption belongs and the row is left to the buttons. */}
        <div className="topbar-row">
          <div className="brand">
            <span className="brand-mark" />
            <h1>Innovation Radar</h1>
          </div>

          <HelpButton topic="role_modes" onOpen={setHelp} />

          {/* The three roles are one choice, so they are drawn as one control:
              a box makes "pick exactly one of these" visible without a label
              spending a line saying it. */}
          <div className="btn-group roles" role="group" aria-label="Role mode">
            {meta.roles.map((mode) => {
              const Icon = ROLE_ICONS[mode.id] ?? IconPerson
              return (
                <button key={mode.id} className="topbtn" aria-pressed={role === mode.id}
                        aria-label={mode.label}
                        title={`${mode.description} Sees link types ${mode.link_types.join(', ')}.`}
                        onClick={() => setRole(mode.id)}>
                  <Icon className="btn-icon" />
                  <TopLabel text={mode.label} />
                </button>
              )
            })}
          </div>

          <div className="tabs" role="group" aria-label="View">
            {compact && tabButton('detail')}
            <div className="btn-group" role="group" aria-label="The ranked set">
              {RANKED_TABS.map(tabButton)}
            </div>
            {OTHER_TABS.map(tabButton)}
          </div>

          <div className="spacer" />

          {/* The three that act on the portfolio rather than look at it, boxed
              for the same reason the roles are: Generate synthesises new spaces
              into it, Workflow moves them through its gate, Planner commits a
              set of them to years. Workflow is still a TAB — it renders in the
              reading layout like the others — but it is read here, because what
              a stage owner does on that board is the same kind of act. */}
          <div className="btn-group actions" role="group" aria-label="Portfolio">
            <button className="topbtn generate-btn"
                    onClick={() => { setGenerating(true); setFullscreen(false); setPlanner(false) }}
                    aria-pressed={generating} aria-label="Generate"
                    title="Synthesise more opportunity spaces from the evidence already collected">
              <IconSpark className="btn-icon" />
              <TopLabel text="Generate" />
            </button>
            <button className="topbtn workflow-btn"
                    onClick={() => openTab('workflow')}
                    aria-pressed={tab === 'workflow' && !generating && !fullscreen && !planner}
                    aria-label="Workflow"
                    title="The stage gate: drag a space from one stage to the next, or park it">
              <IconBoard className="btn-icon" />
              <TopLabel text="Workflow" />
            </button>
            <button className="topbtn planner-btn"
                    onClick={() => { setPlanner(true); setGenerating(false); setFullscreen(false) }}
                    aria-pressed={planner} aria-label="Planner"
                    title="Build a five-year portfolio plan: which spaces to enter, in what order, and what they earn">
              <IconCalendar className="btn-icon" />
              <TopLabel text="Planner" />
            </button>
          </div>

          <button className="topbtn icon-only"
                  onClick={() => setTheme(theme === 'dark' ? 'light' : theme === 'light' ? 'auto' : 'dark')}
                  aria-label={`Theme: ${theme}`}
                  title={`Theme: ${theme} — click to change`}>
            {theme === 'auto' ? <IconAutoTheme className="btn-icon" />
              : theme === 'dark' ? <IconMoon className="btn-icon" />
              : <IconSun className="btn-icon" />}
          </button>

          {/* Two controls rather than a menu. A dropdown here would need
              outside-click handling, focus return and an escape key for two
              items, and one of those two is the one people look for when they are
              already annoyed. Sign out keeps the door and drops the word: it is
              the one control in the row whose icon nobody has to learn. */}
          <button className="topbtn account-btn" onClick={() => setChangingPassword(true)}
                  aria-label={`Signed in as ${user.username} — change password`}
                  title={`Signed in as ${user.username} — change password`}>
            <IconPerson className="btn-icon" />
            <span className="btn-label"><span>{user.display_name}</span></span>
            {user.must_change_password && <span className="account-warn" aria-hidden>!</span>}
          </button>
          <button className="topbtn icon-only signout-btn" onClick={onSignedOut}
                  aria-label="Sign out" title="Sign out — end this session">
            <IconSignOut className="btn-icon" />
          </button>
        </div>

        <div className="topbar-info">
          <span className="ti-sub">Orange Business · opportunity spaces</span>
          <span className="spacer" />
          {view?.last_refresh && (
            <span className="meta-chip" title="AC-02 freshness: the radar shows its last refresh date">
              refreshed {(view.last_refresh.finished_at ?? view.last_refresh.started_at).slice(0, 10)}
            </span>
          )}
          <button className="meta-chip" title="SC-10: every published score records its weight set"
                  onClick={() => setHelp('weight_set')}>
            {meta.weight_set}
          </button>
        </div>
      </header>

      {user.must_change_password && (
        <div className="default-password-banner" role="status">
          <span aria-hidden>⚠</span>
          <span>
            <b>This account still has the password the radar shipped with.</b> Anyone who knows
            the default can read every space, every competitor assessment and every plan in here.
          </span>
          <button onClick={() => setChangingPassword(true)}>Change it now</button>
        </div>
      )}

      {deleted && (
        <div className="deleted-banner" role="status">
          <span><b>{deleted}</b> and everything attached to it has been deleted.</span>
          <button onClick={() => setDeleted(null)} aria-label="Dismiss">Dismiss</button>
        </div>
      )}

      {generating && (
        <GenerateScreen
          meta={meta}
          onClose={() => setGenerating(false)}
          onHelp={setHelp}
          // Opening a space from the generator means leaving it — the point of
          // the link is to read the space in the radar, not beside the form.
          onOpenTopic={(id) => {
            setSelected(id)
            setGenerating(false)
            if (compact) setTab('detail')
          }}
          onGenerated={() => setRefreshKey((k) => k + 1)}
        />
      )}

      {planner && (
        <PlannerScreen
          onClose={() => setPlanner(false)}
          onOpenTopic={(id) => { setPlanner(false); setSelected(id); setTab('list') }} />
      )}

      {fullscreen && selected && (
        <SpaceFullscreen
          topicId={selected}
          topic={selectedTopic}
          role={role}
          meta={meta}
          workflowMeta={wfMeta}
          refreshKey={refreshKey}
          rank={selectedRank >= 0 ? selectedRank + 1 : undefined}
          onChanged={() => setRefreshKey((k) => k + 1)}
          onHelp={setHelp}
          onExplain={setExplaining}
          onDeleted={onTopicDeleted}
          onClose={() => {
            // Leaving destroys the control that was focused, so focus goes back
            // to the button that opened it rather than to <body>.
            pendingFocus.current = 'fullscreen'
            setFullscreen(false)
          }} />
      )}

      <div className="layout" ref={layoutRef}
           hidden={generating || planner || (fullscreen && Boolean(selected))}
           data-detail={detailHidden ? 'hidden' : undefined}
           style={{
             ['--filters-w' as any]: `${layout.filtersCollapsed ? FILTERS_COLLAPSED : FILTERS_WIDTH}px`,
             ['--detail-w' as any]: `${layout.detailWidth}px`,
           }}>
        <aside className={`filters-pane${layout.filtersCollapsed ? ' collapsed' : ''}`}>
          {layout.filtersCollapsed ? (
            <>
              <button className="pane-toggle" title="Show filters" aria-label="Show filters"
                      aria-expanded={false} ref={filterToggleRef}
                      onClick={() => setLayout((c) => ({ ...c, filtersCollapsed: false }))}>»</button>
              <button className="rail" onClick={() => setLayout((c) => ({ ...c, filtersCollapsed: false }))}>
                Filters
              </button>
              {activeFilterCount > 0 && (
                <span className="filter-badge" title={activeFilterSummary}>{activeFilterCount}</span>
              )}
            </>
          ) : (
            <>
              <div className="filters-head">
                <span className="label">Filters</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <HelpButton topic="filters" onOpen={setHelp} />
                  <HelpButton topic="market_clusters" onOpen={setHelp} label="C" />
                  <button className="pane-toggle" title="Collapse the filter pane"
                          aria-label="Collapse the filter pane" aria-expanded
                          onClick={() => {
                            pendingFocus.current = 'filters'
                            setLayout((c) => ({ ...c, filtersCollapsed: true }))
                          }}>«</button>
                </span>
              </div>
              <div className="filters-body">
                {!filtersApply && (
                  <p className="filters-inert">
                    This view is portfolio-wide — it answers “where is the radar as a whole”, so it
                    ignores the filters below on purpose. Switch to Radar, List or White space to
                    apply them.
                  </p>
                )}
                <Filters meta={meta} filters={filters} onChange={setFilters}
                         geographies={geographies} marketClusters={marketClusters}
                         facets={view?.facets ?? {}}
                         totalMatching={view?.total_matching ?? 0}
                         loading={viewLoading && !view} />
              </div>
            </>
          )}
        </aside>

        <main className="main-pane" id="main-pane" tabIndex={-1}>
          {activeRole && (
            <div style={{ marginBottom: 14, fontSize: 12.5, color: 'var(--text-secondary)' }}>
              <b>{activeRole.label}.</b> {activeRole.description}{' '}
              <span style={{ color: 'var(--text-muted)' }}>
                {/* The old wording ("showing link types L1, L2…") read as a filter
                    on the links inside a topic, which is not what it does: it
                    decides which spaces appear at all. */}
                Only spaces Orange could deliver at {
                  activeRole.link_types.length > 2
                    ? `${activeRole.link_types[0]}–${activeRole.link_types[activeRole.link_types.length - 1]}`
                    : activeRole.link_types.join(' or ')
                } appear here, ordered for this role.
                <HelpButton topic="role_modes" onOpen={setHelp} />
              </span>
            </div>
          )}

          {tab === 'radar' && (
            <div className="panel">
              <div className="panel-head">
                <h2>Radar</h2>
                <HelpButton topic="radar" onOpen={setHelp} />
                <span className="sub">
                  {view ? view.total_matching : '…'} match this role and filter · showing {shown.length}
                  {sort !== 'rank' && ' · the cap now takes the top of your chosen order'}
                </span>
                <span className="spacer" />
                {sortControl}
              </div>
              <div className="panel-body">
                <RadarLegend />
                <RadarChart topics={shown} domains={meta.domains}
                            selectedId={selected} onSelect={selectAndShow} />
                {/* The plot is the product's one claim to authority, and a
                    reader's first question about it is where the dots came
                    from. The answer sits under the picture that raised the
                    question rather than behind a "?" in the heading, because
                    it is a page, not a definition. */}
                <div className="hb-trigger-row">
                  <button type="button" className="hb-trigger"
                          onClick={() => setHowBuilt(true)}>
                    <IconRoute />
                    How was the radar created?
                  </button>
                </div>
              </div>
              <ShowMore view={view} limit={limit} setLimit={setLimit} />
            </div>
          )}

          {tab === 'list' && (
            <div className="panel">
              <div className="panel-head">
                <h2>Topics</h2>
                <HelpButton topic="role_modes" onOpen={setHelp} />
                <span className="sub">
                  {view ? view.total_matching : '…'} match this role and filter · showing {shown.length}
                  {sort === 'rank'
                    ? ` · ranked by the ${activeRole?.label} ranking function`
                    : ` · ordered by ${(meta.sorts ?? []).find((s2) => s2.id === sort)?.label?.toLowerCase()},`
                      + ` within what ${activeRole?.label} may see`}
                </span>
                <span className="spacer" />
                {sortControl}
              </div>
              <div className="panel-body" style={{ padding: 8 }}>
                {shown.length === 0 && (
                  <div className="empty" aria-live="polite">
                    {viewLoading ? 'Loading…' : 'No topics match these filters.'}
                  </div>
                )}
                {shown.map((topic, i) => (
                  <div className="topic-row" key={topic.id}
                       data-selected={selected === topic.id || undefined}
                       onClick={() => selectAndShow(topic.id)}>
                    <div className="topic-rank">{topic.exploration_slot ? '★' : i + 1}</div>
                    <div>
                      {/* The row stays clickable for a mouse; the statement is a
                          real button so a keyboard reaches it too. */}
                      <button className="topic-open" onClick={(e) => { e.stopPropagation(); setSelected(topic.id) }}
                              aria-pressed={selected === topic.id}>
                        <p className="topic-statement">{topic.statement}</p>
                      </button>
                      <div className="topic-triple">
                        {topic.labels.vertical} × {topic.labels.use_case} × {topic.labels.technology}
                        {' · '}{topic.signal_count} signals
                        {/* The cluster, not the country codes: three ISO pairs on a
                            list row is noise, and the grouping is what the reader
                            is scanning for. Silent when the evidence is EU-wide
                            and belongs to no single cluster. */}
                        {topic.market_cluster_labels.length > 0
                          && ` · ${topic.market_cluster_labels.join(', ')}`}
                      </div>
                      <div style={{ display: 'flex', gap: 5, marginTop: 5, flexWrap: 'wrap',
                                    alignItems: 'center' }}>
                        {topic.horizon && <span className={`badge ${topic.horizon === 'now' ? 'now' : ''}`}>{topic.horizon}</span>}
                        <span className="badge">L{topic.portfolio_distance}</span>
                        <span className="badge">{topic.state}</span>
                        {topic.market_size_summary && (
                          /* Two methods produce these figures and they are not the
                             same quantity: a bottom-up estimate and an observed
                             procurement floor sat in identical badges. The method
                             marker and the confidence grade travel with the number. */
                          <span className={`badge size-badge ${topic.market_size_summary.confidence}`}
                                title={topic.market_size_summary.method === 'bottom_up_adoption'
                                  ? `Serviceable market, per year. Bottom-up: enterprises × adoption × contract value. `
                                    + `${topic.market_size_summary.confidence} evidence — open the topic for the range and the factors.`
                                  : `Observed public tenders, annualised — a floor, not a market estimate. `
                                    + `No bottom-up estimate exists for this space.`}>
                            {formatEur(topic.market_size_summary.sam_base)}/yr
                            <span className="size-badge-method">
                              {topic.market_size_summary.method === 'bottom_up_adoption'
                                ? 'serviceable' : 'tendered'}
                            </span>
                          </span>
                        )}
                        {topic.competition && (
                          <span className="intensity" data-level={topic.competition.level}
                                style={{ fontSize: 11 }} title={topic.competition.meaning}>
                            {topic.competition.level_label.toUpperCase()}
                            <span style={{ fontSize: 10, fontWeight: 400, color: 'var(--text-muted)' }}>
                              competition
                            </span>
                          </span>
                        )}
                        {topic.evidence_gap_warning && <span className="badge gap">⚠ evidence gap</span>}
                        {topic.exploration_slot && <span className="badge explore">exploration slot</span>}
                        {topic.divergence && <span className="badge gap">⚠ review</span>}
                      </div>
                    </div>
                    <div className="topic-scores">
                      <span className="score-pill" title="Attractiveness">A {topic.attractiveness?.score?.toFixed(0) ?? '—'}</span>
                      <span className="score-pill" title="Right to win"
                            style={{ borderColor: rtwColor(topic.right_to_win?.score) }}>
                        W {topic.right_to_win?.score?.toFixed(0) ?? '—'}
                      </span>
                      <button className="help-btn"
                              aria-label={`How ${topic.id}'s score was calculated`}
                              title="How was this calculated?"
                              onClick={(e) => { e.stopPropagation(); openExplain(topic.id) }}>=</button>
                      {/* Two glyphs, not one glyph in two colours: "a brief exists"
                          is a fact a colourblind reader needs too. */}
                      <button className={`help-btn${topic.has_brief ? ' ready' : ''}`}
                              aria-label={topic.has_brief
                                ? `Open the brief for ${topic.id}`
                                : `Build the brief for ${topic.id}`}
                              title={topic.has_brief
                                ? 'Brief ready — open it'
                                : (topic.has_description
                                    ? 'Description written, no brief yet — opens the tab where you can build one'
                                    : 'Nothing written yet — opens the tab where you can build it')}
                              onClick={(e) => { e.stopPropagation(); setSelected(topic.id); setTab('brief') }}>
                        {topic.has_brief ? '▤' : '▢'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
              <ShowMore view={view} limit={limit} setLimit={setLimit} />
            </div>
          )}

          {tab === 'detail' && (
            <div className="panel">
              <div className="panel-head">
                <h2>Topic detail</h2>
                <span className="sub">
                  The window is too narrow for a side pane, so the detail is here instead.
                </span>
                <span className="spacer" />
                {selected && (
                  <button className="fs-enter" onClick={() => setFullscreen(true)}
                          title="Read this space with the other panes out of the way, with its brief alongside">
                    <span aria-hidden>⤢</span> Display in full screen
                  </button>
                )}
              </div>
              <div className="panel-body">
                <TopicDetail topicId={selected} role={role} meta={meta}
                             workflowMeta={wfMeta}
                             onChanged={() => setRefreshKey((k) => k + 1)}
                             refreshKey={refreshKey}
                             onHelp={setHelp}
                             onExplain={setExplaining}
                             onDeleted={onTopicDeleted}
                             onOpenBrief={(id) => { setSelected(id); setTab('brief') }}
                             rank={selectedRank >= 0 ? selectedRank + 1 : undefined} />
              </div>
            </div>
          )}

          {tab === 'brief' && (
            <BriefView topic={selectedTopic} onHelp={setHelp}
                       recent={shown.filter((t) => t.has_brief)
                         .slice(0, 8).map((t) => ({ id: t.id, statement: t.statement }))}
                       onSelectTopic={(id) => setSelected(id)} />
          )}

          {tab === 'whitespace' && (
            <div className="panel">
              <div className="panel-head">
                <h2>White space</h2>
                <HelpButton topic="whitespace" onOpen={setHelp} />
                <span className="sub">
                  High attractiveness, no path from the current portfolio (FR-32). The strategist's
                  innovation agenda — and precisely what a salesperson should never be shown.
                  {' '}Showing {whitespace.length} of {whitespaceTotal}
                  {whitespace.length !== whitespaceTotal && ' — your filters apply here'}.
                </span>
              </div>
              <div className="panel-body" style={{ padding: 8 }}>
                {whitespace.length === 0 && <div className="empty">No white-space topics at the current threshold.</div>}
                {whitespace.map((topic) => (
                  <div className="topic-row" key={topic.id}
                       data-selected={selected === topic.id || undefined}
                       onClick={() => setSelected(topic.id)}>
                    <div className="topic-rank">L{topic.portfolio_distance}</div>
                    <div>
                      <button className="topic-open" aria-pressed={selected === topic.id}
                              onClick={(e) => { e.stopPropagation(); setSelected(topic.id) }}>
                        <p className="topic-statement">{topic.statement}</p>
                      </button>
                      <div className="topic-triple">
                        {topic.labels.vertical} × {topic.labels.use_case} × {topic.labels.technology}
                        {topic.market_cluster_labels.length > 0
                          && ` · ${topic.market_cluster_labels.join(', ')}`}
                      </div>
                      {/* White space is where the strategist decides what to fund,
                          so the two facts that drive that decision travel with it —
                          they were being dropped here while the list showed them. */}
                      <div style={{ display: 'flex', gap: 5, marginTop: 5, flexWrap: 'wrap',
                                    alignItems: 'center' }}>
                        {topic.horizon && <span className="badge">{topic.horizon}</span>}
                        {topic.market_size_summary && (
                          <span className="badge" title="Serviceable market, per year">
                            {formatEur(topic.market_size_summary.sam_base)} SAM
                          </span>
                        )}
                        {topic.competition && (
                          <span className="intensity" data-level={topic.competition.level}
                                style={{ fontSize: 11 }} title={topic.competition.meaning}>
                            {topic.competition.level_label.toUpperCase()}
                            <span style={{ fontSize: 10, fontWeight: 400, color: 'var(--text-muted)' }}>
                              competition
                            </span>
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="topic-scores">
                      <span className="score-pill" title="Attractiveness">
                        A {topic.attractiveness?.score?.toFixed(0) ?? '—'}
                      </span>
                      <span className="score-pill" title="Right to win"
                            style={{ borderColor: rtwColor(topic.right_to_win?.score) }}>
                        W {topic.right_to_win?.score?.toFixed(0) ?? '—'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {tab === 'workflow' && board && wfMeta && (
            <div className="panel">
              <div className="panel-head">
                <h2>Stage gate</h2>
                <HelpButton topic="workflow" onOpen={setHelp} />
                <span className="sub">
                  A space moves Shortlisted → Demand-tested → Packaged → Live, with an owner at
                  each stage. Cards flag when they stall, and when the team and the evidence disagree.
                </span>
              </div>
              <div className="panel-body">
                {moveError && (
                  <div className="board-error" role="alert">
                    <span aria-hidden>⚠</span>
                    <span>{moveError}</span>
                    <button onClick={() => setMoveError(null)} aria-label="Dismiss">Dismiss</button>
                  </div>
                )}
                <Board board={board} selectedId={selected} onSelect={setSelected}
                       onExplain={openExplain} onMove={moveStage} />
                <p style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 14, marginBottom: 0 }}>
                  <b>Drag a card into another column to move it a stage</b>, or focus one and
                  press Alt + ← / →. Every move is recorded against your role, with the stage it
                  came from. Open a space to assess it. Each role rates only its own axis — strategy rates
                  strategic fit, sales rates customer demand, presales rates deliverability. Those
                  ratings form a third quantity, <b>conviction</b>, which changes what surfaces first
                  for each role but never alters attractiveness or right to win.
                </p>
              </div>
            </div>
          )}

          {tab === 'analytics' && summary && (
            <>
              <p style={{ fontSize: 11.5, color: 'var(--text-muted)', margin: '0 0 8px' }}>
                Portfolio-wide and role-blind: these count the whole corpus, not the
                {' '}{view?.total_matching ?? 0} spaces your current role and filters show.
              </p>
              <div className="kpi-row">
                <Kpi value={summary.topics} label="Opportunity spaces"
                     sub={`${summary.topics_assessed} assessed by a role`} />
                <Kpi value={summary.signals.toLocaleString()} label="Signals"
                     sub={`${summary.relevant_signals.toLocaleString()} passed the gate`} />
                <Kpi value={summary.sources} label="Sources" />
                <Kpi value={summary.links.toLocaleString()} label="Asset links" />
                <Kpi value={summary.by_horizon?.now ?? 0} label="Now-horizon"
                     sub="dated buying window" />
              </div>

              <div className="chart-grid">
                <ChartCard help="heatmap" onHelp={setHelp} wide title="Where the topics are"
                           note="Vertical × domain. Magnitude on a grid, so a sequential single-hue ramp — blue, because orange already encodes right-to-win elsewhere and reusing it would imply the same quantity. Outlined cells carry an evidence gap. Empty cells are the white space.">
                  {gridData && <Heatmap grid={gridData} onSelect={(vertical, domain) => {
                    // Both coordinates, not one: clicking "Manufacturing ×
                    // Cybersecurity" and landing on all 33 manufacturing topics
                    // is a drill-down that loses the thing you drilled into.
                    setFilters({ ...filters, vertical: [vertical], domain: domain ? [domain] : [] })
                    setTab('list')
                  }} />}
                </ChartCard>

                <ChartCard help="market_size" onHelp={setHelp}
                           title="Where sized opportunity concentrates (€ per year)"
                           note={sizing?.note ?? 'Serviceable market per vertical, summed across the topics sized bottom-up. Magnitude on a single hue — the length is the quantity, so colour has no second job to do.'}>
                  {sizing && (
                    <BarList format={formatEur}
                             data={(sizing.by_vertical ?? []).slice(0, 8).map((row: any) => ({
                               label: row.label,
                               value: Math.round(row.sam_base),
                               hint: `${row.topics} space(s) sized in ${row.label}, `
                                 + `serviceable market per year, summed`,
                             }))} />
                  )}
                </ChartCard>

                <ChartCard help="market_clusters" onHelp={setHelp}
                           title="Where the radar has evidence, by market cluster"
                           note="Opportunity spaces attributed to each cluster from the country codes their evidence carries. Magnitude on a single hue. Counts sum to more than the radar holds — a space with evidence in three clusters is counted in three — and EU-wide spaces appear in none of them, which is why the totals here are smaller than the corpus. Coverage reports what falls outside.">
                  <BarList
                    data={(meta?.market_clusters ?? [])
                      .map((c) => ({
                        label: c.source === 'extension' ? `${c.label} *` : c.label,
                        value: view?.facets?.market_cluster?.[c.id] ?? 0,
                        hint: `${countryNames(c.countries, 99).full}`
                          + (c.source === 'email'
                            ? ' — grouping supplied by Orange Business'
                            : c.source === 'confirmed'
                              ? ' — not in the supplied grouping; confirmed separately'
                              : ' — grouping inferred from the corpus, not supplied'),
                      }))
                      .filter((row) => row.value > 0)
                      .sort((a, b) => b.value - a.value)} />
                </ChartCard>

                <ChartCard help="competition" onHelp={setHelp} title="Competitive intensity"
                           note="How crowded the field is across the radar. Ordered bands, so an ordinal ramp — the reader sees the order in the colour. A radar that is all HIGH is telling you where Orange is late, not that the method is broken.">
                  {sizing && (
                    <BarList ordinal
                             data={['none', 'low', 'medium', 'high'].map((level) => ({
                               label: level[0].toUpperCase() + level.slice(1),
                               value: sizing.competition_by_level?.[level] ?? 0,
                             }))} />
                  )}
                </ChartCard>

                <ChartCard help="divergence" onHelp={setHelp} title="Team conviction vs the evidence"
                           note="Disagreement becomes information rather than friction. Polarity, so a diverging scale with a neutral grey midpoint — agreement reads as nothing at all. Click a row to open the space.">
                  <DivergenceChart rows={divergent} onSelect={(id) => { setSelected(id); setTab('list') }} />
                </ChartCard>

                <ChartCard help="workflow" onHelp={setHelp} title="Stage gate"
                           note="Stages are an ordered sequence, so the ramp is ordinal — the reader sees the order in the colour.">
                  <StageFunnel stages={(wfMeta?.stages ?? []).map((st) => ({
                    id: st.id, label: st.label, count: summary.by_stage?.[st.id] ?? 0,
                  }))} />
                </ChartCard>

                <ChartCard help="source_tier" onHelp={setHelp} title="Evidence mix"
                           note="Signal types across the gated corpus. The series ARE the subject here, so this is the one categorical chart — with a legend and a table, because identity must never rest on colour alone.">
                  <StackedBar data={Object.entries(summary.by_signal_type ?? {})
                    .sort((a, b) => (b[1] as number) - (a[1] as number))
                    .slice(0, 6)
                    .map(([label, value]) => ({ label, value: value as number }))} />
                </ChartCard>

                <ChartCard help="portfolio_distance" onHelp={setHelp} title="Portfolio distance"
                           note="How far each topic sits from something Orange could deliver today. L0 is a direct offer; L4 is white space.">
                  <BarList ordinal data={['L0', 'L1', 'L2', 'L3', 'L4'].map((k) => ({
                    label: k, value: summary.by_distance?.[k] ?? 0,
                  }))} />
                </ChartCard>

                <ChartCard help="source_tier" onHelp={setHelp} title="Source tiers"
                           note="§4.3.7 tiering. A corpus that is all tier 1 is not automatically better — it means the independent trade press and practitioner voices are missing.">
                  <BarList data={Object.entries(summary.by_tier ?? {}).sort()
                    .map(([k, v]) => ({ label: `Tier ${k}`, value: v as number }))} />
                </ChartCard>

                <ChartCard help="coverage" onHelp={setHelp} title="Language coverage"
                           note="Measured, not assumed: anglophone bias is a known risk, and the pipeline ingests English and French.">
                  <BarList data={Object.entries(summary.by_language ?? {})
                    .sort((a, b) => (b[1] as number) - (a[1] as number))
                    .map(([k, v]) => ({ label: k, value: v as number }))} />
                </ChartCard>

                <ChartCard help="coverage" onHelp={setHelp} title="Signals per source"
                           note="Concentration matters: if one source dominates, source diversity is thinner than the headline count suggests.">
                  <BarList data={Object.entries(summary.by_source ?? {})
                    .sort((a, b) => (b[1] as number) - (a[1] as number))
                    .slice(0, 10)
                    .map(([k, v]) => ({ label: k, value: v as number }))} />
                </ChartCard>
              </div>
            </>
          )}

          {tab === 'coverage' && coverage && (
            <div className="panel">
              <div className="panel-head">
                <h2>Coverage</h2>
                <HelpButton topic="coverage" onOpen={setHelp} />
                <HelpButton topic="market_clusters" onOpen={setHelp} label="C" />
                <span className="sub">
                  Language, geography and competitor coverage, measured rather than assumed —
                  anglophone and EU bias is a known risk in a corpus like this.
                </span>
              </div>
              <div className="panel-body">
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 20 }}>
                  {([
                    ['Source tier', coverage.tiers],
                    ['Language', coverage.languages],
                    ['Signal type', coverage.signal_types],
                    ['Source', coverage.sources],
                    ['Market cluster', coverage.market_clusters],
                    ['Geography', coverage.geographies],
                    ['Topics per vertical', coverage.topics_per_vertical],
                  ] as [string, Record<string, number>][]).map(([title, data]) => (
                    <div key={title}>
                      <h4 style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '.07em', color: 'var(--text-muted)', margin: '0 0 8px' }}>
                        {title}
                      </h4>
                      <table className="data">
                        <tbody>
                          {Object.entries(data).slice(0, 12).map(([key, value]) => (
                            <tr key={key}><td>{key}</td><td className="num">{value}</td></tr>
                          ))}
                  {/* NFR-08 applied to the new dimension: the cluster rollup does
                      not cover everything, and the part it does not cover is
                      stated rather than left to be inferred from a total that
                      does not add up. */}
                  <div>
                    <h4 style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '.07em', color: 'var(--text-muted)', margin: '0 0 8px' }}>
                      Outside the cluster map
                    </h4>
                    <table className="data">
                      <tbody>
                        <tr>
                          <td title="Tagged EU or UN — real evidence, but not attributable to one cluster. Counted towards every European cluster when filtering.">
                            EU / UN-wide
                          </td>
                          <td className="num">{coverage.market_cluster_gaps.supranational}</td>
                        </tr>
                        {Object.entries(coverage.market_cluster_gaps.unmapped).map(([code, n]) => (
                          <tr key={code}>
                            <td title="A country code no cluster claims — usually a malformed code from extraction. Shown rather than absorbed.">
                              {code} (unmapped)
                            </td>
                            <td className="num">{n}</td>
                          </tr>
                        ))}
                        {Object.keys(coverage.market_cluster_gaps.unmapped).length === 0 && (
                          <tr><td colSpan={2} style={{ color: 'var(--text-muted)' }}>every country code maps</td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                        </tbody>
                      </table>
                    </div>
                  ))}
                </div>

                {coverage.competitors && (() => {
                  const c = coverage.competitors!
                  const profiled = c.by_status.profiled ?? 0
                  const pct = (n: number, of: number) => (of ? Math.round((n / of) * 100) : 0)
                  return (
                    <div className="cov-competitors">
                      <h3>Competitive picture</h3>
                      <p className="cov-sub">
                        Three separate gaps, reported together because they compound: a written
                        comparison over a space whose competitors are mostly unread is thinner
                        than the same comparison elsewhere.
                      </p>

                      <div className="cov-bars">
                        <div>
                          <div className="cov-bar-head">
                            <span>Register read from their own sites</span>
                            <strong>{profiled} / {c.register_total}</strong>
                          </div>
                          <div className="cov-bar">
                            <span style={{ width: `${pct(profiled, c.register_total)}%` }} />
                          </div>
                          <p className="cov-note">{c.pages_read.toLocaleString()} pages · register {c.register_version}</p>
                        </div>
                        <div>
                          <div className="cov-bar-head">
                            <span>Spaces with a competitive intensity</span>
                            <strong>{c.topics_assessed} / {c.topics_total}</strong>
                          </div>
                          <div className="cov-bar">
                            <span style={{ width: `${pct(c.topics_assessed, c.topics_total)}%` }} />
                          </div>
                          <p className="cov-note">
                            {c.topics_total - c.topics_assessed} spaces show an empty competitor tab —
                            a processing gap, not a finding
                          </p>
                        </div>
                        <div>
                          <div className="cov-bar-head">
                            <span>Spaces with a written comparison</span>
                            <strong>{c.topics_written} / {c.topics_analysed}</strong>
                          </div>
                          <div className="cov-bar">
                            <span style={{ width: `${pct(c.topics_written, c.topics_analysed || 1)}%` }} />
                          </div>
                          <p className="cov-note">costs one model call each, so it is never universal</p>
                        </div>
                      </div>

                      {Object.keys(c.unread_named).length > 0 && (
                        <div className="cov-unread">
                          <h4>Competitors whose published position is unread</h4>
                          {Object.entries(c.unread_named).map(([status, names]) => (
                            <p key={status}>
                              <span className="tag">{status.replace('_', ' ')}</span>
                              {' '}{names.join(' · ')}
                              {status === 'blocked' && (
                                <span className="cov-note">
                                  {' '}— these sites refuse automated clients. Recorded rather than
                                  worked around, so their absence is visible instead of silent.
                                </span>
                              )}
                              {status === 'no_pages' && (
                                <span className="cov-note">
                                  {' '}— fetched successfully but render their content client-side,
                                  so nothing readable was returned.
                                </span>
                              )}
                            </p>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })()}
              </div>
            </div>
          )}
        </main>

        {detailHidden && (
          <button className="detail-restore" ref={detailRestoreRef}
                  onClick={() => setLayout((c) => ({ ...c, detailHidden: false }))}
                  title="Show the detail pane" aria-label="Show the detail pane" aria-expanded={false}>
            «<span>Detail</span>
          </button>
        )}

        <div className="pane-splitter" role="separator" tabIndex={0}
             aria-orientation="vertical"
             aria-label="Resize the detail pane"
             aria-valuenow={Math.round(layout.detailWidth)}
             aria-valuemin={DETAIL_MIN} aria-valuemax={DETAIL_MAX}
             data-dragging={dragging || undefined}
             title="Drag to resize · arrow keys to nudge · double-click to reset"
             onPointerDown={onSplitterDown}
             onKeyDown={onSplitterKey}
             onDoubleClick={() => setLayout((c) => ({ ...c, detailWidth: DETAIL_DEFAULT }))} />

        <aside className="detail-pane">
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 4, marginBottom: 6,
                        alignItems: 'center' }}>
            <button className="pane-toggle" title="Hide the detail pane"
                    aria-label="Hide the detail pane" aria-expanded
                    onClick={() => {
                      pendingFocus.current = 'detail'
                      setLayout((c) => ({ ...c, detailHidden: true }))
                    }}>»</button>
            {selected && (
              <button className="fs-enter" ref={fullscreenRef}
                      onClick={() => setFullscreen(true)}
                      title="Read this space with the other panes out of the way, with its brief alongside">
                <span aria-hidden>⤢</span> Display in full screen
              </button>
            )}
            <span className="spacer" />
            <span style={{ fontSize: 10.5, color: 'var(--text-muted)' }}>Help</span>
            <HelpButton topic="attractiveness" onOpen={setHelp} label="A" />
            <HelpButton topic="right_to_win" onOpen={setHelp} label="W" />
            <HelpButton topic="conviction" onOpen={setHelp} label="C" />
            <HelpButton topic="portfolio_distance" onOpen={setHelp} label="L" />
          </div>
          <TopicDetail topicId={selected} role={role} meta={meta}
                       workflowMeta={wfMeta}
                       onChanged={() => setRefreshKey((k) => k + 1)}
                       refreshKey={refreshKey}
                       onHelp={setHelp}
                       onExplain={setExplaining}
                       onDeleted={onTopicDeleted}
                       onOpenBrief={(id) => { setSelected(id); setTab('brief') }}
                       rank={selectedRank >= 0 ? selectedRank + 1 : undefined} />
        </aside>
      </div>

      {changingPassword && (
        <PasswordDialog user={user} minLength={minPasswordLength}
                        onClose={() => setChangingPassword(false)}
                        onChanged={onUserChanged} />
      )}

      <HelpModal topic={help} onClose={() => setHelp(null)} />
      <HowBuilt open={howBuilt} onClose={() => setHowBuilt(false)} meta={meta} />
      <ScoreExplainModal
        topic={explaining}
        weights={{ attractiveness: meta.attractiveness_weights, right_to_win: meta.right_to_win_weights }}
        onClose={() => setExplaining(null)} />
    </div>
  )
}


/** The sign-in gate, and the only thing rendered before there is a session.
 *
 * Three states, and they are genuinely different messages: still asking,
 * cannot ask at all, and asked and got "nobody". The middle one used to be
 * folded into the third — a backend that was down showed a login form, and the
 * password that would not work looked like the user's fault.
 */
export default function App() {
  const [session, setSession] = useState<SessionInfo | null>(null)
  const [checking, setChecking] = useState(true)
  const [unreachable, setUnreachable] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api.session()
      .then((info) => { if (!cancelled) { setSession(info); setUnreachable(null) } })
      .catch((exc) => { if (!cancelled) setUnreachable(String(exc.message ?? exc)) })
      .finally(() => { if (!cancelled) setChecking(false) })
    return () => { cancelled = true }
  }, [])

  // A 401 from anywhere in the app means the session ended underneath it —
  // expired, or signed out in another tab. Handled once, here, rather than by
  // each panel rendering "your session has ended" as if it were a data error.
  useEffect(() => {
    setSessionEndedHandler(() => {
      setSession((current) => (current ? { ...current, authenticated: false, user: null } : current))
    })
    return () => setSessionEndedHandler(null)
  }, [])

  if (checking) return <div className="empty">Loading…</div>

  if (unreachable) {
    return (
      <div className="empty">
        <p>Cannot reach the radar API.</p>
        <p style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{unreachable}</p>
        <p>Start it with <code>radar serve</code> (or <code>python -m radar.cli serve</code>).</p>
      </div>
    )
  }

  if (!session?.authenticated || !session.user) {
    return (
      <LoginScreen
        onSignedIn={(user) => setSession((current) => ({
          authenticated: true,
          user,
          password_policy: current?.password_policy ?? { min_length: 8 },
        }))} />
    )
  }

  return (
    <RadarApp
      user={session.user}
      minPasswordLength={session.password_policy?.min_length ?? 8}
      onUserChanged={(user) => setSession((current) => (current ? { ...current, user } : current))}
      onSignedOut={() => {
        // Cleared locally whatever the server says. A network failure on the way
        // out must not leave somebody looking at a radar they asked to leave —
        // and the cookie is HttpOnly, so the only thing this can do is stop
        // rendering the data it already has.
        api.logout().catch(() => {})
        setSession((current) => (current ? { ...current, authenticated: false, user: null } : current))
      }} />
  )
}
