import type {
  BriefMeta, CollateralItem, Competition, CompetitorAnalysis, Coverage, DeletionImpact,
  DeletionReport, PreSalesIndex,
  FilterState, GenerationConstraints, GenerationJob,
  Plan, PlannerMeta, PlanRequest, PlanReport, PlanReportStatus,
  GenerationMatch, GenerationOptions, MarketSize, Meta, RadarView, SessionInfo, Topic,
  TopicDescription, User,
  ChatMessage, GenerateAnywayRequest, HypothesisRequest, ScopingOpening, ScopingTurn,
} from './types'

const BASE = '/api'

/** Where a session that has ended gets reported.
 *
 * A session expires between page loads far more often than during one, but when
 * it does the symptom is every panel on screen showing "Your session has ended"
 * as a data error — which is both wrong (the radar is fine) and useless (there
 * is no way to act on it from a panel). One place decides, and it flips the
 * whole app back to the sign-in screen.
 *
 * Registered by App rather than imported by it, because this module must not
 * depend on React to know what to do about a 401.
 */
let onSessionEnded: (() => void) | null = null

export function setSessionEndedHandler(handler: (() => void) | null) {
  onSessionEnded = handler
}

/** True when the response is a signed-out 401, having told the app about it.
 *
 * Deliberately narrow: `/api/auth/login` answers 401 for a wrong password, and
 * treating THAT as a lost session would blank the login form the moment somebody
 * mistypes.
 */
function sessionEnded(res: Response, path: string): boolean {
  if (res.status !== 401 || path.startsWith('/auth/')) return false
  onSessionEnded?.()
  return true
}

async function get<T>(path: string, params?: Record<string, string | string[] | undefined>): Promise<T> {
  const url = new URL(BASE + path, window.location.origin)
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value === undefined || value === '') continue
    // Multi-select filters repeat the key — FastAPI reads them as a list (AC-04).
    if (Array.isArray(value)) value.forEach((v) => url.searchParams.append(key, v))
    else url.searchParams.set(key, value)
  }
  const res = await fetch(url.toString(), { credentials: 'same-origin' })
  if (!res.ok) { sessionEnded(res, path); throw await failure(res, path) }
  return parse<T>(res, path)
}

/** Turn a failed response into an error somebody can act on.
 *
 * The API puts the real reason in `detail` — a model failure, a missing key, a
 * run already in flight — and reporting the status line instead would leave the
 * user with "500" for every one of them.
 *
 * The case worth naming is a 500 with NO body at all. The API never produces
 * one: an unhandled exception in FastAPI still answers with text, and every
 * deliberate refusal here carries a `detail`. An empty-bodied 500 comes from
 * the Vite dev proxy when the backend it forwards to is not running — and its
 * symptom, `500 Internal Server Error — ` with nothing after the dash, appears
 * on every panel of the screen at once and says nothing about the cause. In dev
 * the cause is nearly always that the API process stopped, so that is what this
 * says.
 */
async function failure(res: Response, path: string): Promise<Error> {
  const body = (await res.text().catch(() => '')).trim()
  if (!body && res.status >= 500) {
    return new Error(
      `${res.status} from ${BASE}${path} with an empty body, which the API never sends — every `
      + 'refusal it makes carries a reason. In development this is the dev-server proxy answering '
      + 'for a backend that is not running: start it (radar serve, or uvicorn radar.api:app '
      + '--port 8000) and retry.',
    )
  }
  let detail = body.slice(0, 300)
  try { detail = JSON.parse(body).detail ?? detail } catch { /* not JSON */ }
  return new Error(detail || `${res.status} ${res.statusText}`)
}

/** Read a JSON body, or say what arrived instead.
 *
 * The API serves the built frontend from the same origin, and unknown paths
 * fall through to the app shell rather than 404ing — that is deliberate, so a
 * client-side route survives a reload. The cost is that an /api path the SERVER
 * does not know answers 200 with `<!doctype html>`, and the only symptom is
 * `SyntaxError: Unexpected token '<'` from JSON.parse, which says nothing about
 * the cause. In practice the cause is nearly always a server process older than
 * the bundle it is serving, so that is what this says.
 */
async function parse<T>(res: Response, path: string): Promise<T> {
  const type = res.headers.get('content-type') ?? ''
  if (!type.includes('json')) {
    const body = (await res.text().catch(() => '')).trimStart()
    if (body.startsWith('<')) {
      throw new Error(
        `The API served the app shell for ${BASE}${path} instead of data, which means the running `
        + 'server does not have that route. It is almost certainly running an older build than the '
        + 'frontend — restart it (radar serve, or with --reload while developing).',
      )
    }
    throw new Error(`${BASE}${path} answered with ${type || 'no content type'}, not JSON.`)
  }
  return res.json() as Promise<T>
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method: 'POST',
    credentials: 'same-origin',
    ...(body === undefined ? {} : {
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  })
  if (!res.ok) { sessionEnded(res, path); throw await failure(res, path) }
  return parse<T>(res, path)
}

/** The one destructive verb in this client, and the only caller is a dialog
 *  that has already shown the user what it is about to remove. */
async function del<T>(path: string): Promise<T> {
  const res = await fetch(BASE + path, { method: 'DELETE', credentials: 'same-origin' })
  if (!res.ok) { sessionEnded(res, path); throw await failure(res, path) }
  return parse<T>(res, path)
}

export const api = {
  /* --- signing in ----------------------------------------------------------
   * The session is an HttpOnly cookie, so none of these return a token and
   * nothing here stores one: the browser attaches it and script cannot read it.
   * That is the point — a token this module could hold is a token an injected
   * script could steal. */

  /** Who is signed in. Always 200, so a signed-out visitor is not reported as a
   *  broken server. */
  session: () => get<SessionInfo>('/auth/session'),

  login: (username: string, password: string) =>
    post<{ user: User }>('/auth/login', { username, password }),

  logout: () => post<{ signed_out: boolean }>('/auth/logout'),

  /** Ends every other session for the account; this one is reissued. */
  changePassword: (currentPassword: string, newPassword: string) =>
    post<{ user: User }>('/auth/password', {
      current_password: currentPassword, new_password: newPassword,
    }),

  meta: () => get<Meta>('/meta'),

  view: (role: string, filters: FilterState, limit?: number | null, sort?: string) =>
    get<RadarView>('/view', {
      role,
      limit: limit ? String(limit) : undefined,
      sort: sort && sort !== 'rank' ? sort : undefined,
      vertical: filters.vertical,
      domain: filters.domain,
      persona: filters.persona,
      geography: filters.geography,
      market_cluster: filters.market_cluster,
      horizon: filters.horizon,
      competition: filters.competition,
      has_brief: filters.has_brief ? 'true' : undefined,
      q: filters.q || undefined,
    }),

  topic: (id: string) => get<Topic>(`/topics/${id}`),

  /** What a delete would take, without taking any of it. Read by the
   *  confirmation dialog: thirteen tables point at a space, and "are you sure?"
   *  over a number nobody was shown is not a confirmation. */
  deletionImpact: (id: string) => get<DeletionImpact>(`/topics/${id}/deletion-impact`),

  /** Removes the space and everything attached to it. Returns the impact as it
   *  stood a moment before, so the caller can say what actually went. */
  deleteTopic: (id: string) => del<DeletionReport>(`/topics/${id}`),

  marketSize: (id: string) => get<{ topic_id: string; estimates: MarketSize[] }>(`/topics/${id}/market-size`),

  competition: (id: string) => get<Competition>(`/topics/${id}/competition`),

  /** The structural join is computed server-side on first read; only the written
   *  comparison needs the POST below. */
  competitorAnalysis: (id: string) => get<CompetitorAnalysis>(`/topics/${id}/competitor-analysis`),

  recomputeCompetition: (id: string) => post<Competition>(`/topics/${id}/competition`),

  /** The Planner. Selection and projection are arithmetic and fast; only the
   *  written business plan costs a model call. */
  plannerMeta: () => get<PlannerMeta>('/planner/meta'),
  plans: () => get<{ plans: any[] }>('/planner/plans'),
  plan: (id: string) => get<Plan>(`/planner/plans/${id}`),
  createPlan: (body: PlanRequest) => post<Plan>('/planner/plans', body),
  narratePlan: (id: string) => post<Plan>(`/planner/plans/${id}/narrative`),

  planReportStatus: (id: string) => get<PlanReportStatus>(`/planner/plans/${id}/report`),

  /** Renders the document. Always a rebuild, because the narrative can be
      written after the plan was computed and a cached export would be missing
      exactly the section the reader opened it for. */
  buildPlanReport: (id: string) => post<PlanReport>(`/planner/plans/${id}/report`),

  /** Cache-busted on the content hash so a rebuilt document is never served
      from the embed's cache at the same URL. */
  planReportUrl: (id: string, version?: string) =>
    `${BASE}/planner/plans/${id}/report.pdf${version ? `?v=${encodeURIComponent(version)}` : ''}`,

  planReportDownloadUrl: (id: string) => `${BASE}/planner/plans/${id}/report.pdf?download=1`,

  generateCompetitorAnalysis: (id: string, force = false) =>
    post<CompetitorAnalysis>(`/topics/${id}/competitor-analysis${force ? '?force=true' : ''}`),

  /** §4.3.4 reference data vintage — the UI shows how old the denominators are. */
  referenceData: () => get<{ count: number; series: Record<string, any>[] }>('/reference-data'),

  /** Generation is a POST because it writes a derived artefact. Both calls are
   *  slow enough (one model call) that callers show a pending state. */
  generateDescription: (id: string, force = false) =>
    post<TopicDescription>(`/topics/${id}/description${force ? '?force=true' : ''}`),

  brief: (id: string) => get<BriefMeta>(`/topics/${id}/brief`),

  generateBrief: (id: string, force = false) =>
    post<BriefMeta>(`/topics/${id}/brief${force ? '?force=true' : ''}`),

  /** Cache-busted so a regenerated brief is never served from the iframe cache. */
  briefUrl: (id: string, version?: string) =>
    `${BASE}/topics/${id}/brief.pdf${version ? `?v=${encodeURIComponent(version)}` : ''}`,

  briefDownloadUrl: (id: string) => `${BASE}/topics/${id}/brief.pdf?download=1`,

  /** The whole pre-sales catalogue for one space, each entry with its state. */
  presales: (id: string) => get<PreSalesIndex>(`/topics/${id}/presales`),

  /** Build one piece in one format. `force` rebuilds a piece that is current. */
  generateCollateral: (id: string, kind: string, fmt: string, force = false) =>
    post<CollateralItem>(
      `/topics/${id}/presales/${kind}?fmt=${encodeURIComponent(fmt)}${force ? '&force=true' : ''}`),

  /** Always the attachment form. PowerPoint, Word and ODF have no inline viewer
   *  worth the name, and a PDF that opens in a tab is one the reader has to
   *  save by hand anyway — the one button that always does what it says beats
   *  two that sometimes do. */
  collateralDownloadUrl: (id: string, kind: string, fmt: string) =>
    `${BASE}/topics/${id}/presales/${kind}/file?fmt=${encodeURIComponent(fmt)}&download=1`,

  /** Cache-busted, so a rebuilt document is never served from the viewer cache. */
  collateralViewUrl: (id: string, kind: string, fmt: string, version?: string) =>
    `${BASE}/topics/${id}/presales/${kind}/file?fmt=${encodeURIComponent(fmt)}`
    + (version ? `&v=${encodeURIComponent(version)}` : ''),

  whitespace: (filters?: FilterState) =>
    get<{ count: number; total_unfiltered: number; topics: Topic[] }>('/whitespace', {
      vertical: filters?.vertical,
      domain: filters?.domain,
      persona: filters?.persona,
      geography: filters?.geography,
      market_cluster: filters?.market_cluster,
      horizon: filters?.horizon,
      competition: filters?.competition,
      q: filters?.q || undefined,
    }),

  coverage: () => get<Coverage>('/coverage'),

  orphanOffers: () => get<{ count: number; offers: { id: string; label: string }[] }>('/orphan-offers'),

  /* --- generation (the Generate screen) ------------------------------------
   * A run takes minutes, so it is started and then polled: an HTTP request held
   * open for that long dies to a proxy timeout with the work half-done and no
   * way to find out what happened. */

  generationOptions: () => get<GenerationOptions>('/generate/options'),

  /** What ALREADY exists inside the selected criteria. Not /view: that filters
   *  by role first, and generation writes to the whole corpus. */
  generationMatching: (c: GenerationConstraints) =>
    get<GenerationMatch>('/generate/matching', {
      vertical: c.verticals,
      domain: c.domains,
      geography: c.geographies,
      market_cluster: c.market_clusters,
      horizon: c.horizons,
    }),

  startGeneration: (count: number, c: GenerationConstraints) =>
    post<GenerationJob>('/generate', { count, ...c }),

  /** One space from a written description. The text is a SEARCH BRIEF, not
   *  evidence — the server retrieves the closest corroborated signals and those
   *  become the only facts the model may cite. */
  startGenerationFromBrief: (description: string) =>
    post<GenerationJob>('/generate/brief', { description }),

  /** One space per brief, in a single run. The scoping conversation can land on
   *  several distinct taxonomy triples, and synthesis holds the only write lock
   *  on that identity — separate requests would just collect 409s. */
  startGenerationFromBriefs: (descriptions: string[]) =>
    post<GenerationJob>('/generate/briefs', { descriptions }),

  /* --- the scoping conversation ---------------------------------------------
   * Stateless: the transcript lives here and is posted whole on every turn, so
   * there is no session to expire and a reload loses a conversation rather than
   * leaking one. The opening turn is a GET because it is written, not generated,
   * and costs no model call. */

  /** Build a space the corpus is silent about, on evidence you contribute.
   *
   *  Not a bypass of the evidence rule — the opposite. The rationale is recorded
   *  as a dated, attributable internal signal (FR-24, tier 3) and the ordinary
   *  run then cites it, so the space rests on a named person's assertion rather
   *  than on nothing, and scores like the hypothesis it is. */
  startGenerationFromHypothesis: (body: HypothesisRequest) =>
    post<GenerationJob & { internal_signal_id: string }>('/generate/hypothesis', body),

  /** Generate regardless of what the corpus holds today: the run searches for
   *  evidence on the brief first, and cites the person's own account where they
   *  gave one. Synthesis is unchanged — claims still have to cite something. */
  startGenerationAnyway: (body: GenerateAnywayRequest) =>
    post<GenerationJob & { internal_signal_id: string | null }>('/generate/anyway', body),

  scopingOpening: () => get<ScopingOpening>('/generate/chat'),

  /** One turn. The reply carries the retrieval and the readiness verdict as
   *  well as the words, because the screen shows all three — a chat bubble on
   *  its own would hide the part that makes this different from a text box. */
  /** `understood` is the rest of the conversation's state. The transcript is
   *  not enough on its own: the model's own cumulative slots are not reliably
   *  cumulative, so what earlier turns settled is echoed back and merged
   *  server-side. It is re-validated there, so this is a hint, not a bypass. */
  scopingTurn: (messages: ChatMessage[], understood?: ScopingTurn['understood']) =>
    post<ScopingTurn>('/generate/chat', { messages, understood }),

  generationJob: (id: string) => get<GenerationJob>(`/generate/${id}`),

  generationJobs: () =>
    get<{ active: string | null; jobs: GenerationJob[] }>('/generate/jobs'),

  cancelGeneration: (id: string) => post<GenerationJob>(`/generate/${id}/cancel`),

  /** FR-23 / FR-34 / DR-15 — exposure context travels with every event. */
  feedback: (payload: {
    role: string
    kind: 'rating' | 'comparison' | 'override' | 'engagement'
    opportunity_id?: string
    other_opportunity_id?: string
    verdict?: string
    reason?: string
    exposure_context?: Record<string, unknown>
  }) =>
    fetch(`${BASE}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }).then((r) => r.json()),
}
