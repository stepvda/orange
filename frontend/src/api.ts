import type {
  BriefMeta, Competition, CompetitorAnalysis, Coverage, FilterState, GenerationConstraints, GenerationJob,
  Plan, PlannerMeta, PlanRequest, PlanReport, PlanReportStatus,
  GenerationMatch, GenerationOptions, MarketSize, Meta, RadarView, Topic, TopicDescription,
  ChatMessage, HypothesisRequest, ScopingOpening, ScopingTurn,
} from './types'

const BASE = '/api'

async function get<T>(path: string, params?: Record<string, string | string[] | undefined>): Promise<T> {
  const url = new URL(BASE + path, window.location.origin)
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value === undefined || value === '') continue
    // Multi-select filters repeat the key — FastAPI reads them as a list (AC-04).
    if (Array.isArray(value)) value.forEach((v) => url.searchParams.append(key, v))
    else url.searchParams.set(key, value)
  }
  const res = await fetch(url.toString())
  if (!res.ok) throw await failure(res, path)
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
    ...(body === undefined ? {} : {
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  })
  if (!res.ok) throw await failure(res, path)
  return parse<T>(res, path)
}

export const api = {
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
      horizon: filters.horizon,
      competition: filters.competition,
      has_brief: filters.has_brief ? 'true' : undefined,
      q: filters.q || undefined,
    }),

  topic: (id: string) => get<Topic>(`/topics/${id}`),

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

  whitespace: (filters?: FilterState) =>
    get<{ count: number; total_unfiltered: number; topics: Topic[] }>('/whitespace', {
      vertical: filters?.vertical,
      domain: filters?.domain,
      persona: filters?.persona,
      geography: filters?.geography,
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

  /** Build a space the corpus is silent about, on evidence you contribute.
   *
   *  Not a bypass of the evidence rule — the opposite. The rationale is recorded
   *  as a dated, attributable internal signal (FR-24, tier 3) and the ordinary
   *  run then cites it, so the space rests on a named person's assertion rather
   *  than on nothing, and scores like the hypothesis it is. */
  startGenerationFromHypothesis: (body: HypothesisRequest) =>
    post<GenerationJob & { internal_signal_id: string }>('/generate/hypothesis', body),

  /* --- the scoping conversation ---------------------------------------------
   * Stateless: the transcript lives here and is posted whole on every turn, so
   * there is no session to expire and a reload loses a conversation rather than
   * leaking one. The opening turn is a GET because it is written, not generated,
   * and costs no model call. */

  scopingOpening: () => get<ScopingOpening>('/generate/chat'),

  /** One turn. The reply carries the retrieval and the readiness verdict as
   *  well as the words, because the screen shows all three — a chat bubble on
   *  its own would hide the part that makes this different from a text box. */
  scopingTurn: (messages: ChatMessage[]) =>
    post<ScopingTurn>('/generate/chat', { messages }),

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
