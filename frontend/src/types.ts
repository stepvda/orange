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

export interface MarketCluster {
  id: string
  label: string
  countries: string[]
  /** 'email' = named by Orange; 'confirmed' = settled by the project owner but
   *  not in Orange's own mail; 'extension' = still our reading of the corpus.
   *  Only 'extension' is marked with an asterisk in the UI. */
  source: 'email' | 'confirmed' | 'extension'
  scope: string
}

export interface Meta {
  verticals: VocabItem[]
  use_cases: VocabItem[]
  technologies: VocabItem[]
  domains: VocabItem[]
  personas: VocabItem[]
  signal_types: VocabItem[]
  /** Orange Business go-to-market grouping. `source` says whether Orange
   *  named the cluster or we inferred it, so the UI can mark the difference. */
  market_clusters: MarketCluster[]
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

/** One output format a piece of collateral can be produced in. */
export interface CollateralFormat {
  fmt: string
  label: string
  built: boolean
  stale: boolean
  bytes: number | null
  url: string
}

/** What has actually been built for one (space, kind, format). */
export interface CollateralBuild {
  fmt: string
  format_label: string
  exists: boolean
  generated_at?: string
  topic_version?: number
  filename?: string
  bytes?: number
  content_hash?: string
  media_type?: string
  stale?: boolean
  /** Which kind of staleness — the space, the narrative, the sizing or the file. */
  stale_reason?: string | null
  incomplete?: boolean
  /** Whether a model wrote any of it, or it is computed and curated data only. */
  has_narrative?: boolean
  weight_set?: string
  sizing_version?: string
  prompt_version?: string
  model_version?: string
  url: string
}

/** One row of the pre-sales catalogue, with whatever exists for it.
 *
 * The catalogue is always returned in full, never only what has been built:
 * the tab's job is to say what COULD be produced as much as what has been.
 */
export interface CollateralItem {
  kind: string
  title: string
  audience: string
  summary: string
  charts: string[]
  model_calls: number
  /** The default format — the one the artefact wants to be. */
  format: string
  formats: CollateralFormat[]
  builds: Record<string, CollateralBuild>
  exists: boolean
  stale: boolean
  stale_reason: string | null
  incomplete: boolean
  has_narrative: boolean
  generated_at: string | null
  bytes: number | null
  content_hash: string | null
  filename: string | null
  url: string
}

export interface PreSalesIndex {
  topic_id: string
  items: CollateralItem[]
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
  /** Clusters this topic is ABOUT, from its own country codes. Drives chips. */
  market_clusters: string[]
  market_cluster_labels: string[]
  /** Clusters this topic REACHES, adding what a supranational code spans.
   *  Wider than the above for EU-wide evidence; drives filtering. */
  market_cluster_reach: string[]
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
  market_clusters: Record<string, number>
  market_cluster_gaps: { supranational: number; unmapped: Record<string, number> }
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
  market_cluster: string[]
  horizon: string[]
  /** §4.3.3 — filter on how crowded the field is. */
  competition: string[]
  /** FR-18 — "what can I actually take to a meeting tomorrow". */
  has_brief: boolean
  q: string
}

export const EMPTY_FILTERS: FilterState = {
  vertical: [], domain: [], persona: [], geography: [], market_cluster: [], horizon: [],
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
  /** Expanded server-side into member ISO codes and unioned with `geographies`,
   *  so scoping a run by cluster is exactly scoping it by the countries in it. */
  market_clusters: string[]
  verticals: string[]
  horizons: string[]
  domains: string[]
}

export const EMPTY_CONSTRAINTS: GenerationConstraints = {
  geographies: [], market_clusters: [], verticals: [], horizons: [], domains: [],
}

export function constraintCount(c: GenerationConstraints): number {
  return c.geographies.length + c.market_clusters.length + c.verticals.length
    + c.horizons.length + c.domains.length
}

export interface GenerationOptions {
  /** Read from the corpus, not from config — geography rides on signals (§2.6). */
  geographies: { id: string; signals: number; spaces: number }[]
  market_clusters: { id: string; label: string; countries: string[]
                     source: string; signals: number; spaces: number }[]
  unmapped_geographies: string[]
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

/* -------------------------------------------------------------------------
 * The scoping conversation (the Generate screen's assistant tab).
 *
 * Mirrors radar.scoping. The field worth reading twice is `ready`: it is the
 * SERVER's verdict, not the model's. Every brief the assistant proposes is put
 * back through the same retrieval the generation job will run, and a brief the
 * corpus cannot answer disables the button it would otherwise enable. The
 * model's own opinion arrives separately as `model_ready`, which is only ever
 * interesting when the two disagree.
 * ---------------------------------------------------------------------- */

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

/** One retrieved signal, with everything needed to disagree with it. */
export interface ScopingSignal {
  id: string
  title: string
  publisher: string
  published_at: string
  signal_type: string | null
  tier: number
  url: string | null
  geographies?: string[]
  similarity: number
  /** Why this signal independently supports the brief — a vocabulary term in its
   *  text or a CPV crosswalk hit — or null when it is merely close. Similarity
   *  alone is not support: a brief retrieves same-sector, same-country documents
   *  at a high score whether or not any of them is about its subject. */
  corroborates?: string | null
}

export interface ScopingBrief {
  title: string
  /** The search brief itself. Editable before it is run — the job re-checks the
   *  corpus for whatever text is actually submitted. */
  description: string
  vertical: string | null
  use_case: string | null
  technology: string | null
  geographies: string[]
  rationale: string
  /** What YOU asserted in the conversation that the corpus does not carry.
   *  Pre-fills the contributed-evidence box — you have just spent six turns
   *  saying this, and being asked to type it all again is the refusal with an
   *  extra step. Empty when the corpus carries the brief on its own. */
  hypothesis_rationale: string
  /** `count` is what was retrieved; `corroborated` is what actually supports the
   *  brief. The gap between them is the whole reason a run can cost model calls
   *  and create nothing. */
  evidence: {
    count: number
    best: number | null
    corroborated: number
    /** Which test answered: `vocabulary` when the free one sufficed, `model`
     *  when it came up short and a cheap second opinion was bought. */
    support_method?: 'vocabulary' | 'model'
    signals: ScopingSignal[]
  }
  /** The space already sitting on this taxonomy triple, if any. Not a problem —
   *  the run is legal — but it means DR-03 refreshes rather than creates. */
  existing: { id: string; statement: string; state: string } | null
  /** Why this brief cannot be run as evidence-backed, if it cannot. Empty when
   *  it can. */
  problems: string[]
  runnable: boolean
  /** The corpus is silent, but the brief itself is sound — so the other route is
   *  open: contribute what you know as an attributable internal signal (FR-24)
   *  and build on that. False when the brief is malformed or outside the
   *  vocabulary, which no route can fix. */
  hypothesis: boolean
}

/** The three internal evidence kinds (§2.5), and what each becomes. */
export const HYPOTHESIS_KINDS = [
  { id: 'customer_conversation', label: 'A customer conversation', becomes: 'trend' },
  { id: 'rfp_theme', label: 'An RFP or tender theme', becomes: 'buying signal' },
  { id: 'lost_deal', label: 'A deal we lost', becomes: 'market move' },
] as const

/** Build the space whatever the corpus says: search for evidence first, and
 *  carry the person's own account if they have one. */
export interface GenerateAnywayRequest {
  description: string
  rationale?: string | null
  kind?: string
  vertical?: string | null
  geographies?: string[]
  research?: boolean
}

export interface HypothesisRequest {
  description: string
  rationale: string
  kind: string
  vertical?: string | null
  geographies?: string[]
}

export interface ScopingSlot {
  id: string
  label: string
  required: boolean
}

export interface ScopingCorpus {
  signals: number
  clusters: number
  spaces: number
  by_signal_type: [string, number][]
  by_geography: [string, number][]
  clusters_sample: { id: number; label: string; size: number; keyphrases: string }[]
  date_range: [string, string] | null
}

/** The first turn — written rather than generated, so it costs no model call. */
export interface ScopingOpening {
  message: string
  suggestions: string[]
  corpus: ScopingCorpus
  slots: ScopingSlot[]
  min_brief_chars: number
  max_brief_chars: number
  max_briefs: number
  prompt_version: string
}

export interface ScopingTurn {
  reply: string
  /** Cumulative across the conversation, resolved to taxonomy ids server-side. */
  understood: {
    vertical: string | null
    use_case: string | null
    technology: string | null
    buyer_problem: string | null
    geographies: string[]
    personas: string[]
    deployment: string | null
    horizon: string | null
  }
  /** What was said but could not be mapped onto a controlled vocabulary. */
  unresolved: Record<string, string>
  missing: string[]
  asking_for: string | null
  suggestions: string[]
  evidence_note: string | null
  ready: boolean
  model_ready: boolean
  briefs: ScopingBrief[]
  evidence: { floor: number; count: number; signals: ScopingSignal[] }
  /** Spaces already built on the evidence this conversation retrieved (DR-03). */
  occupied: string[]
  turns: number
  soft_turn_limit: number
  prompt_version: string
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
  /** Set only when the run answers exactly one brief; a run answering three has
   *  no single brief to name. `briefs` is the truth. */
  brief: string | null
  briefs: string[]
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
  /** Where the SET comes from. `parameters` lets the optimiser choose under the
   *  constraints below; `workflow` takes what the stage gate already decided and
   *  applies none of them. */
  source?: 'parameters' | 'workflow'
  from_stage?: string
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
    /* Present only on a plan built from the workflow. */
    source?: string
    from_stage?: string
    stage_mix?: { key: string; label: string; count: number; share: number }[]
    over_subscribed?: string[]
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
  /** What the stage gate has committed. `cumulative_sized` is the number the
   *  form must quote: a committed space with no market size contributes nothing
   *  to any figure, so counting it would promise a bigger plan than comes back. */
  workflow: {
    stages: {
      id: string; label: string; count: number; sized: number
      cumulative: number; cumulative_sized: number
    }[]
    default_from_stage: string
    parked: number
  }
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

/* --- accounts and sessions (radar/auth.py) -------------------------------- */

/** No hash, no token: `radar.auth.public_user` decides what leaves the server,
 *  and this mirrors that shape rather than the row behind it. */
export interface User {
  username: string
  display_name: string
  /** True while the account still holds the credential the radar shipped with.
   *  The interface says so on every screen until it is false. */
  must_change_password: boolean
  last_login_at: string | null
  password_changed_at: string | null
}

export interface SessionInfo {
  authenticated: boolean
  user: User | null
  /** Shown beside the field that enforces it, rather than discovered from a
   *  rejection after the user has typed something twice. */
  password_policy: { min_length: number }
}

/* --- deleting an opportunity space (radar/deletion.py) -------------------- */

/** One group of rows a delete would take, already worded for a reader:
 *  "3 asset links", not "opportunity_links: 3". */
export interface DeletionRemoval {
  table: string
  label: string
  count: number
}

export interface DeletionImpact {
  topic_id: string
  statement: string
  triple: { vertical: string; use_case: string; technology: string }
  state: string
  removes: DeletionRemoval[]
  /** Spaces folded into this one under the identity rule. They are the same
   *  space, so they leave with it. */
  merged_duplicates: string[]
  /** Portfolio plans that selected this space. Their stored projection still
   *  counts it, so deleting the space stops the plan adding up — reported
   *  rather than blocked. */
  plans: { id: string; label: string | null; created_at: string; entry_year: number }[]
  briefs: string[]
  /** Evidence is shared and stays; only the attachment goes. Named so the
   *  dialog can say what is NOT lost. */
  signals_kept: number
}

export interface DeletionReport extends DeletionImpact {
  deleted: true
  brief_files_removed: number
  deleted_by: string | null
}
