/** Shapes served by radar.api. Mirrors radar/readmodel.py. */

export interface VocabItem {
  id: string
  label: string
  definition: string
}

export interface RoleMode {
  id: string
  label: string
  description: string
  primary_action: string
  link_types: string[]
  acceptance?: string
  ranking: Record<string, number>
}

export interface LinkTypeInfo {
  id: string
  meaning: string
  definition: string
  owner: string
  action: string
}

export interface Meta {
  verticals: VocabItem[]
  use_cases: VocabItem[]
  technologies: VocabItem[]
  domains: VocabItem[]
  personas: VocabItem[]
  signal_types: VocabItem[]
  horizons: string[]
  states: string[]
  link_types: LinkTypeInfo[]
  roles: RoleMode[]
  weight_set: string
  sorts?: { id: SortId; label: string }[]
  sizing_version?: string
  competitor_register_version?: string
  competition_levels?: { id: string; meaning: string }[]
  attractiveness_weights: Record<string, number>
  right_to_win_weights: Record<string, number>
  pipeline_version: string
  last_refresh: RefreshRow | null
  strategy: {
    plan: string
    period: string
    ambitions: { id: string; label: string; implication: string }[]
    privileged_verticals: Record<string, number>
  }
}

export interface RefreshRow {
  id: string
  started_at: string
  finished_at: string | null
  reference_date: string
  is_replay: number
  weight_set?: string
  pipeline_version?: string
}

export interface ScoreBlock {
  score: number
  components: Record<string, number>
  /** Present only on the detail endpoint — the raw inputs behind each component (DR-05). */
  inputs: Record<string, any> | null
  weight_set: string
  computed_at: string
}

export interface Claim {
  claim: string
  signals: string[]
}

export interface TopicLink {
  node_id: string
  node_type: string
  label: string
  link_type: string
  link_meaning: string
  owner: string
  action: string
  confidence: number
  evidence: Record<string, any>
  confirmed_by: string | null
}

export interface Signal {
  id: string
  title: string
  url: string
  publisher: string
  published_at: string
  signal_type: string | null
  tier: number
  extract: string
  language: string
  geographies: string[]
}

export interface WorkflowState {
  stage: string
  stage_label: string
  owner_role: string | null
  owner: string | null
  entered_stage_at: string | null
  age_in_stage_days: number
  stalled: boolean
  note: string | null
  next_stage: string | null
}

export interface ConvictionAxis {
  label: string
  score: number
  raw_mean: number
  n: number
  rater_spread: number
  contested: boolean
  voices: { role: string; rating: number; confidence: number; rationale: string | null; author: string; at: string }[]
}

export interface Conviction {
  assessed: number
  axes: Record<string, ConvictionAxis>
  score: number | null
  roles_responded: string[]
  roles_missing: string[]
  sufficient: boolean
}

export interface Divergence {
  review_trigger: boolean
  flags: {
    axis: string; axis_label: string; internal: number; external: number
    external_label: string; delta: number; direction: string; reading: string
  }[]
}

/** §4.3.4 market sizing. Every figure is computed; `factors` carries the
 *  working, so the UI can show where each number came from rather than asking
 *  the reader to trust it. */
export interface SizeFactor {
  name: string
  label: string
  value: number
  unit: string
  basis: 'observed' | 'proxy' | 'assumption'
  low: number | null
  high: number | null
  source: {
    publisher?: string; dataset?: string; indicator?: string
    url?: string; period?: string; updated?: string; licence?: string; owner?: string
  }
  detail: Record<string, any>
  note: string
}

export interface SizeBand { low: number | null; base: number | null; high: number | null }

export interface MarketSize {
  method: 'bottom_up_adoption' | 'procurement_observed'
  method_label: string
  currency: string
  tam: SizeBand
  sam: SizeBand
  som: SizeBand
  confidence: 'observed' | 'partial' | 'modelled'
  factors: SizeFactor[]
  coverage: Record<string, any>
  caveats: string[]
  sizing_version: string
  computed_at: string
}

export interface CompetitorMention {
  signal_id: string
  publisher: string
  published_at: string
  url: string
  title: string
  quote: string
}

export interface Competitor {
  id: string
  label: string
  type: string
  type_label: string
  relationship: 'competitor' | 'partner' | 'both'
  partner_id?: string | null
  basis: 'evidenced' | 'structural'
  why: string
  note?: string
  mentions: CompetitorMention[]
  contribution: number
}

/** One competitor on one opportunity space: what the register knows, what their
 *  own pages say, and how Orange differentiates against them specifically.
 *
 *  The split matters and is preserved all the way to the screen. `relevant_claims`
 *  and `register_overlap` are a join over stored data — reproducible, free, always
 *  present. `written` is a model comparing two companies, and it is absent until
 *  somebody asks for it. */
export interface CompetitorAnalysisEntry {
  id: string
  label: string
  type: string
  type_label: string
  relationship: 'competitor' | 'partner' | 'both'
  basis: 'evidenced' | 'structural'
  website?: string
  mentions: CompetitorMention[]
  profile_status: 'profiled' | 'blocked' | 'unreachable' | 'no_pages' | 'unread'
  profile_reason?: string | null
  positioning?: string | null
  pages_used: number
  named_offers: string[]
  register_overlap: { vertical: boolean; use_case: boolean; technology: boolean }
  profile_overlap?: { vertical?: boolean; use_case?: boolean; technology?: boolean }
  relevant_claims: { claim: string; pages: string[] }[]
  written?: {
    activity: { text: string; pages: string[] }
    /** How Orange differentiates against THIS competitor, for THIS opportunity. */
    differentiation: string
    orange_assets: string[]
    concession: string
  } | null
}

export interface CompetitorAnalysis {
  opportunity_id: string
  computed_at: string
  topic_version: number
  entries: CompetitorAnalysisEntry[]
  narrative: { per_competitor: Record<string, any>; field: string } | null
  has_narrative: boolean
  stripped: { competitor: string; reason: string }[]
  coverage: {
    on_topic?: number
    profiled?: number
    blocked?: number
    unread?: number
    register?: {
      register_total: number; profiled: number; blocked: number
      unreachable: number; no_pages: number; unread: number; register_version: string
    }
  }
  register_version: string
  prompt_version?: string | null
  model_version?: string | null
  /** False when competitive intensity was never computed — distinct from
   *  computed-and-matched-nobody, which is a claim about the register. */
  competition_assessed?: boolean
}

/** §4.3.3 — a FOURTH quantity beside attractiveness, right to win and
 *  conviction, never folded into any of them. */
export interface Competition {
  level: 'none' | 'low' | 'medium' | 'high'
  level_label: string
  meaning: string
  score: number
  competitors: Competitor[]
  counts: { listed: number; evidenced: number; partners_who_also_compete: number; total?: number }
  inputs: Record<string, any>
  register_version: string
  computed_at: string
}

export interface DiagramNode { label: string; provider: 'orange' | 'partner' | 'customer' | 'third_party' }
export interface DiagramLayer { label: string; nodes: DiagramNode[] }
export interface SolutionDiagram {
  title: string
  caption: string
  layers: DiagramLayer[]
  flows: { from: string; to: string; label: string }[]
}

export interface TopicDescription {
  sections: Record<string, { text: string; signals: string[] }>
  section_order: string[]
  section_titles: Record<string, string>
  qualifying_questions: string[]
  objection_handling: { objection: string; response: string }[]
  diagram: SolutionDiagram | null
  stripped: { section: string; reason: string }[]
  generated_at: string
  topic_version: number
  stale: boolean
  provenance: Record<string, string>
}

export interface BriefMeta {
  topic_id: string
  generated_at?: string
  topic_version?: number
  filename?: string
  bytes?: number
  content_hash?: string
  exists: boolean
  stale?: boolean
  /** Which kind of staleness — the topic, the narrative, the sizing or the file. */
  stale_reason?: string | null
  weight_set?: string
  sizing_version?: string
  prompt_version?: string
  model_version?: string
  url?: string
  description_available?: boolean
  /** The brief predates a section current briefs carry. Distinct from `stale`:
   *  stale means overtaken, incomplete means it never had the section. */
  brief_schema?: string | null
  incomplete?: boolean
  missing_sections?: string[]
}

export interface Topic {
  id: string
  version: number
  triple: { vertical: string; use_case: string; technology: string }
  labels: { vertical: string; use_case: string; technology: string }
  statement: string
  domains: string[]
  domain_labels: string[]
  personas: string[]
  persona_labels: string[]
  geographies: string[]
  state: string
  state_reason: string
  horizon: string | null
  horizon_basis: string | null
  why_hot: Claim[]
  next_actions: Record<string, string>
  attractiveness: ScoreBlock | null
  right_to_win: ScoreBlock | null
  portfolio_distance: number
  link_types: string[]
  links: TopicLink[]
  evidence_gap_warning: boolean
  reference_density: Record<string, any>
  critic_score: number | null
  first_seen: string
  last_refresh: string
  signal_count: number
  signals?: Signal[]
  /** Detail endpoint only. */
  market_size?: MarketSize[]
  description?: TopicDescription | null
  brief?: BriefMeta | null
  /** List rows carry the headline figure only. */
  market_size_summary?: {
    method: string; sam_base: number | null; tam_base: number | null; confidence: string
  } | null
  competition?: Competition | null
  /** List rows only — so a row can say whether the brief exists before you click. */
  has_description?: boolean
  has_brief?: boolean
  workflow?: WorkflowState | null
  conviction?: Conviction | null
  divergence?: Divergence | null
  provenance: Record<string, string | null>
  rank_score?: number
  rank_explanation?: Record<string, { value: number; weight: number; contribution: number }>
  exploration_slot?: boolean
  strategist_flag?: string
}

export interface RadarView {
  role: string
  role_label: string
  primary_action: string
  filters: Record<string, unknown>
  total_matching: number
  /** Server-computed counts per filter value, over the whole role-eligible set. */
  facets: Record<string, Record<string, number>>
  sort: SortId
  cap: number
  topics: Topic[]
  exploration: Topic[]
  last_refresh: RefreshRow | null
  weight_set: string
}

export interface Coverage {
  languages: Record<string, number>
  tiers: Record<string, number>
  signal_types: Record<string, number>
  sources: Record<string, number>
  geographies: Record<string, number>
  topics_per_vertical: Record<string, number>
  /** What the competitive picture is missing, reported rather than inferred
   *  from an empty panel. Three separate gaps that compound. */
  competitors?: {
    register_total: number
    register_version: string
    by_status: Record<string, number>
    unread_named: Record<string, string[]>
    pages_read: number
    topics_total: number
    topics_assessed: number
    topics_analysed: number
    topics_written: number
  }
}

export type FilterState = {
  vertical: string[]
  domain: string[]
  persona: string[]
  geography: string[]
  horizon: string[]
  /** §4.3.3 — filter on how crowded the field is. */
  competition: string[]
  /** FR-18 — "what can I actually take to a meeting tomorrow". */
  has_brief: boolean
  q: string
}

export const EMPTY_FILTERS: FilterState = {
  vertical: [], domain: [], persona: [], geography: [], horizon: [],
  competition: [], has_brief: false, q: '',
}

/** Orderings the API offers beyond the role's own ranking function (FR-13). */
export type SortId = 'rank' | 'market_size' | 'attractiveness' | 'right_to_win'
  | 'competition' | 'signals' | 'recent'

/* -------------------------------------------------------------------------
 * Generation (the Generate screen).
 *
 * Mirrors radar.generation. The one shape worth reading twice is
 * GenerationConstraints: three of its four fields are ENFORCED server-side and
 * `horizons` is not — §4.8 derives Now/Next/Later from the evidence after
 * scoring, so a horizon filter steers which clusters are read and what the
 * prompt looks for, and where the spaces actually land is reported afterwards.
 * ---------------------------------------------------------------------- */

export interface GenerationConstraints {
  geographies: string[]
  verticals: string[]
  horizons: string[]
  domains: string[]
}

export const EMPTY_CONSTRAINTS: GenerationConstraints = {
  geographies: [], verticals: [], horizons: [], domains: [],
}

export function constraintCount(c: GenerationConstraints): number {
  return c.geographies.length + c.verticals.length + c.horizons.length + c.domains.length
}

export interface GenerationOptions {
  /** Read from the corpus, not from config — geography rides on signals (§2.6). */
  geographies: { id: string; signals: number; spaces: number }[]
  total_live: number
  clusters: number
  clustered_signals: number
  ready: boolean
  reason: string | null
  max_per_run: number
  min_brief_chars: number
  max_brief_chars: number
  /** Id of a run already in flight, if any — only one may proceed at a time. */
  busy: string | null
}

export interface GenerationMatch {
  filters: Record<string, string[]>
  count: number
  total_live: number
  facets: Record<string, Record<string, number>>
  truncated: boolean
  topics: Topic[]
}

export interface GenerationStage {
  id: string
  label: string
  done: boolean
}

export interface GenerationJob {
  id: string
  /** 0..1. Synthesis owns the first ~72%; inside it the value is the larger of
   *  spaces-created-over-asked and evidence-read-over-budget, the second capped
   *  below the full segment so reading clusters cannot render as a result. */
  progress: number
  round: number
  /** What a "unit" counts differs by path — theme clusters read on the grid
   *  path, generation passes on the free-text one — so the payload names it. */
  units_total: number
  units_done: number
  unit_label: string
  requested: number
  /** `grid` covers the evidenced taxonomy grid; `brief` answers one written
   *  description. They differ in what steers the model, not in what validates it. */
  kind: 'grid' | 'brief'
  brief: string | null
  constraints: GenerationConstraints
  constrained: boolean
  status: 'queued' | 'running' | 'done' | 'error' | 'cancelled'
  stage: string | null
  stage_label: string | null
  stages: GenerationStage[]
  started_at: string
  finished_at: string | null
  refresh_id: string | null
  created: number
  created_ids: string[]
  /** The spaces themselves, not just their ids — "what did it make" is the
   *  question somebody who just generated five is actually asking. */
  created_topics: Topic[]
  updated: number
  updated_ids: string[]
  error: string | null
  log: { at: string; message: string }[]
  stats: Record<string, any>
}


/** The Planner (strategy engine). Three registers kept apart, as everywhere else:
 *  `inputs` is what was asked for, `projection` is arithmetic, `narrative` is a
 *  model explaining the arithmetic and is absent until requested. */
export interface PlanRequest {
  label: string
  objective: string
  plan_years: number
  budget_person_years?: number | null
  entry_slots_per_year?: number | null
  pool_availability?: number | null
  min_confidence: string
  max_portfolio_distance: number
  geographies?: string[]
  exclude_verticals?: string[]
  exclude_technologies?: string[]
  prefer_verticals?: string[]
  prefer_domains?: string[]
  max_share_per_vertical?: number | null
  max_share_per_technology?: number | null
  max_competition?: string | null
}

export interface PlanSelection {
  opportunity_id: string
  statement: string
  vertical: string
  use_case: string
  technology: string
  entry_year: number
  horizon: string | null
  portfolio_distance: number
  margin_applied: number
  entry_effort: number
  pool: string | null
  som_base: number
  revenue_by_year: number[]
  profit_by_year: number[]
  overlap_factor: number
  rationale: string
}

export interface PlanProjection {
  years: number
  revenue_by_year: number[]
  profit_by_year: number[]
  profit_low_by_year: number[]
  profit_high_by_year: number[]
  revenue_total: number
  profit_total: number
  profit_total_low: number
  profit_total_high: number
  npv_profit: number
  discount_rate: number
  year5_share_of_segment: number | null
  segment_revenue: number
  mix: Record<string, { key: string; count: number; share: number }[]>
}

export interface Plan {
  id: string
  created_at: string
  label: string
  status: string
  objective: string
  plan_years: number
  selected_count: number
  considered_count: number
  inputs: Record<string, any>
  projection: PlanProjection
  capacity_usage: {
    pools?: Record<string, { capacity: number; used_by_year: number[]; peak_utilisation: number | null }>
    slots?: Record<string, { used: number; available: number }>
    binding?: string[]
  }
  exclusions: { opportunity_id: string; statement: string; vertical: string; reason: string }[]
  flags: { kind: string; severity: string; message: string }[]
  selections: PlanSelection[]
  narrative: { headline: string; sections: Record<string, string> } | null
  stripped: { section: string; reason: string }[]
  assumptions?: Record<string, any>
  economics_version: string
  sizing_version?: string | null
  weight_set?: string | null
  prompt_version?: string | null
  model_version?: string | null
}

export interface PlannerMeta {
  economics_version: string
  owner: string
  source_filing: string
  filed: Record<string, number>
  defaults: Record<string, any>
  margin_by_distance: Record<string, number>
  ramp_by_horizon: Record<string, number[]>
  capacity: Record<string, any>
  aggregation: Record<string, any>
  pools: { label: string; headcount: number }[]
  plannable_spaces: number
  sizes_by_confidence: Record<string, number>
  verticals: { id: string; label: string }[]
  domains: { id: string; label: string }[]
}

export interface PlanReport {
  plan_id: string
  filename: string
  bytes: number
  content_hash: string
  generated_at: string
  schema: string
  exists: boolean
  stale: boolean
  has_narrative: boolean
  url: string
}

export interface PlanReportStatus {
  plan_id: string
  generated: boolean
  report: PlanReport | null
  narrative_available: boolean
}
