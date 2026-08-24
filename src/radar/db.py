"""SQLite storage for the radar.

Carries the data requirements of §3.6 directly:

  DR-01  signal record fields incl. source tier
  DR-02  opportunity space fields
  DR-03  stable identifiers across refreshes — a recurring topic is UPDATED
  DR-05  every score component stored with the inputs used to compute it
  DR-08  source content stored by reference (URL + short extract), never mirrored
  DR-09  no personal data beyond the strictly necessary
  DR-10  every artefact records pipeline / prompt / model version
  DR-11  business graph with typed, dated, sourced edges
  DR-13  every link stores type, confidence, evidence and confirming curator
  DR-15  feedback events stored with their exposure context

SQLite is used because the graph is small — thousands of nodes, not millions
(§4.5.1) — and because a single file makes the historical-replay harness
(FR-35) trivial to snapshot.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

log = logging.getLogger(__name__)

#: SQLite's journal mode, overridable per deployment.
#:
#: WAL is right everywhere the database sits on a local disk: readers never block
#: the writer, which is what makes a refresh and a live UI coexist. It is wrong
#: on a network share. Azure App Service mounts /home over SMB, and WAL needs
#: shared memory the protocol does not provide, so opening a WAL database there
#: fails outright — which, because `init_schema()` runs at import, takes the
#: whole process down and turns a deployment into a restart loop.
#:
#: DELETE (the classic rollback journal) works on SMB. It is slower and it locks
#: the file for the duration of a write, which is acceptable for a read-mostly
#: serving instance running one worker.
JOURNAL_MODE = os.getenv("RADAR_SQLITE_JOURNAL_MODE", "WAL").upper()

SCHEMA = """
PRAGMA journal_mode = __JOURNAL_MODE__;
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Raw items, retained so the pipeline can be replayed as of a past date
-- without re-fetching (DR-14, FR-35).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw_items (
    id              TEXT PRIMARY KEY,          -- sha256 of source_id + url
    source_id       TEXT NOT NULL,
    url             TEXT,
    fetched_at      TEXT NOT NULL,
    payload         TEXT NOT NULL,             -- JSON as returned by the connector
    content_hash    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_raw_source ON raw_items(source_id, fetched_at);

-- ---------------------------------------------------------------------------
-- Signals (DR-01). `published_at` is the field every temporal computation must
-- use: §4.7.3 warns that leakage through late-arriving documents is the standard
-- way a forecasting model produces excellent offline results and useless live
-- ones. `ingested_at` exists only to measure connector lag.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS signals (
    id              TEXT PRIMARY KEY,          -- SIG-xxxxxxxx, stable
    source_id       TEXT NOT NULL,
    publisher       TEXT NOT NULL,
    title           TEXT NOT NULL,
    url             TEXT,
    published_at    TEXT NOT NULL,             -- ISO date. DR-04: undated evidence is dated by inference or rejected
    published_at_inferred INTEGER NOT NULL DEFAULT 0,
    ingested_at     TEXT NOT NULL,
    language        TEXT,
    geographies     TEXT NOT NULL DEFAULT '[]',-- JSON array of ISO codes. §2.6: geography attaches to SIGNALS, not only topics
    signal_type     TEXT,                      -- one of the six (FR-03)
    signal_type_confidence REAL,
    tier            INTEGER NOT NULL,          -- 1..4 (§4.3.7)
    extract         TEXT NOT NULL,             -- short extract only (DR-08)
    relevance       REAL,                      -- relevance gate score (stage 3)
    relevance_reason TEXT,
    cluster_id      INTEGER,
    embedding       BLOB,
    raw_item_id     TEXT REFERENCES raw_items(id),
    -- Structured extras a connector may attach: CPV codes, tender value,
    -- regulatory dates, patent codes.
    attributes      TEXT NOT NULL DEFAULT '{}',
    pipeline_version TEXT NOT NULL,
    prompt_version  TEXT,                      -- DR-10
    model_version   TEXT
);
CREATE INDEX IF NOT EXISTS idx_signals_published ON signals(published_at);
CREATE INDEX IF NOT EXISTS idx_signals_cluster ON signals(cluster_id);
CREATE INDEX IF NOT EXISTS idx_signals_type ON signals(signal_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_signals_url ON signals(url) WHERE url IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Theme clusters (stage 4), tracked across refreshes.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS clusters (
    id              INTEGER PRIMARY KEY,
    label           TEXT,
    keyphrases      TEXT NOT NULL DEFAULT '[]',
    size            INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    refresh_id      TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- Opportunity spaces (DR-02).
-- DR-03: `id` is stable across refreshes. Canonical identity is the taxonomy
-- triple (§4.4.5), enforced by the unique index below — this is what makes
-- momentum measurable and is the requirement most often missed in a first build.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS opportunity_spaces (
    id              TEXT PRIMARY KEY,          -- OS001, stable
    version         INTEGER NOT NULL DEFAULT 1,
    vertical        TEXT NOT NULL,
    use_case        TEXT NOT NULL,
    technology      TEXT NOT NULL,
    statement       TEXT NOT NULL,
    domains         TEXT NOT NULL DEFAULT '[]',
    personas        TEXT NOT NULL DEFAULT '[]',
    geographies     TEXT NOT NULL DEFAULT '[]',
    state           TEXT NOT NULL,             -- candidate|watchlist|active|fading|dormant|rejected (§4.8)
    state_reason    TEXT,
    state_changed_at TEXT,
    horizon         TEXT,                      -- now|next|later (FR-08)
    horizon_basis   TEXT,                      -- which derivation test was applied
    horizon_anchor_date TEXT,
    why_hot         TEXT NOT NULL DEFAULT '[]',-- JSON [{claim, signals:[SIG-...]}] — every claim cited (FR-14)
    next_actions    TEXT NOT NULL DEFAULT '{}',-- JSON {role: text} (FR-17)
    critic_score    INTEGER,
    critic_notes    TEXT,
    first_seen      TEXT NOT NULL,
    last_refresh    TEXT NOT NULL,
    pipeline_version TEXT NOT NULL,
    prompt_version  TEXT,
    model_version   TEXT,
    merged_into     TEXT REFERENCES opportunity_spaces(id)
);
-- Canonical identity: two candidates with the same triple are the same topic.
CREATE UNIQUE INDEX IF NOT EXISTS idx_os_triple
    ON opportunity_spaces(vertical, use_case, technology) WHERE merged_into IS NULL;
CREATE INDEX IF NOT EXISTS idx_os_state ON opportunity_spaces(state);

-- Signal attachment. On refresh, new signals attach to the existing topic
-- (§4.4.5); the row records which refresh first attached each signal, so
-- momentum is the honest trajectory of signal accretion.
CREATE TABLE IF NOT EXISTS opportunity_signals (
    opportunity_id  TEXT NOT NULL REFERENCES opportunity_spaces(id) ON DELETE CASCADE,
    signal_id       TEXT NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
    attached_at     TEXT NOT NULL,
    refresh_id      TEXT NOT NULL,
    PRIMARY KEY (opportunity_id, signal_id)
);

-- ---------------------------------------------------------------------------
-- Scores. SC-10: every published score records the weight set used.
-- DR-05: every component is stored with the inputs used to compute it, so any
-- number can be reproduced. §4.6: the UI must never plot a trajectory across a
-- weight-set boundary without saying so — hence weight_set on every row.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id  TEXT NOT NULL REFERENCES opportunity_spaces(id) ON DELETE CASCADE,
    computed_at     TEXT NOT NULL,
    refresh_id      TEXT NOT NULL,
    kind            TEXT NOT NULL,             -- 'attractiveness' | 'right_to_win'
    score           REAL NOT NULL,
    components      TEXT NOT NULL,             -- JSON {component: value}
    inputs          TEXT NOT NULL,             -- JSON {component: {...raw inputs...}} (DR-05)
    weight_set      TEXT NOT NULL,             -- SC-10
    pipeline_version TEXT NOT NULL,
    model_version   TEXT
);
CREATE INDEX IF NOT EXISTS idx_scores_topic ON scores(opportunity_id, kind, computed_at);

-- ---------------------------------------------------------------------------
-- Orange Business Graph (DR-11). Nodes and typed, dated, sourced edges.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS graph_nodes (
    id              TEXT PRIMARY KEY,
    node_type       TEXT NOT NULL,             -- offer|reference|partner|certification|analyst_position|capability_pool|research_asset
    label           TEXT NOT NULL,
    attributes      TEXT NOT NULL DEFAULT '{}',
    source          TEXT NOT NULL,             -- NFR-02: the graph is auditable to the same standard as the signals
    as_of           TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_nodes_type ON graph_nodes(node_type);

CREATE TABLE IF NOT EXISTS graph_edges (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    src             TEXT NOT NULL,
    dst             TEXT NOT NULL,
    edge_type       TEXT NOT NULL,             -- ADDRESSES|DEMONSTRATES|PROVIDES|REQUIRED_BY|STAFFS|COVERS
    strength        REAL NOT NULL DEFAULT 1.0,
    as_of           TEXT NOT NULL,
    source          TEXT NOT NULL,
    attributes      TEXT NOT NULL DEFAULT '{}' -- e.g. partner tier lives here, as an EDGE property (§4.5.1)
);
CREATE INDEX IF NOT EXISTS idx_edges_src ON graph_edges(src, edge_type);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON graph_edges(dst, edge_type);

-- ---------------------------------------------------------------------------
-- Opportunity space -> business asset links (DR-13, LK-04..LK-08).
-- §4.5.4: "A link nobody can explain is worse than no link, because it will
-- eventually appear in front of a customer." Hence evidence and curator on
-- every row.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS opportunity_links (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id  TEXT NOT NULL REFERENCES opportunity_spaces(id) ON DELETE CASCADE,
    node_id         TEXT NOT NULL REFERENCES graph_nodes(id),
    link_type       TEXT NOT NULL,             -- L0|L1|L2|L3|L4 (FR-30)
    confidence      REAL NOT NULL,
    evidence        TEXT NOT NULL,             -- JSON: what justified this link
    confirmed_by    TEXT,                      -- curator id, NULL = unconfirmed (LK-06)
    confirmed_at    TEXT,
    rejected        INTEGER NOT NULL DEFAULT 0,
    rejection_reason TEXT,
    created_at      TEXT NOT NULL,
    revalidated_at  TEXT,                      -- LK-07
    UNIQUE (opportunity_id, node_id)
);
CREATE INDEX IF NOT EXISTS idx_links_topic ON opportunity_links(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_links_node ON opportunity_links(node_id);

-- Link patterns already adjudicated by a curator. LK-06: the FIRST occurrence
-- of each pattern needs confirmation; later occurrences inherit the decision,
-- and both confirmations and rejections become training data (§4.7).
CREATE TABLE IF NOT EXISTS link_pattern_decisions (
    pattern         TEXT PRIMARY KEY,          -- e.g. "offer:live_objects|use_case:asset_tracking"
    decision        TEXT NOT NULL,             -- confirmed|rejected
    curator         TEXT NOT NULL,
    reason          TEXT,
    decided_at      TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- Refresh log. FR-19: display the last refresh date per topic and globally.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS refreshes (
    id              TEXT PRIMARY KEY,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    reference_date  TEXT NOT NULL,             -- FR-35: replay uses a past reference date
    is_replay       INTEGER NOT NULL DEFAULT 0,
    pipeline_version TEXT NOT NULL,
    weight_set      TEXT NOT NULL,
    stats           TEXT NOT NULL DEFAULT '{}',
    notes           TEXT
);

-- ---------------------------------------------------------------------------
-- Feedback (FR-23, FR-34, DR-15).
-- §4.7.6: engagement must be weighted by the inverse of the probability that
-- the topic was shown, so exposure context is stored, not just the click.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS feedback (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      TEXT NOT NULL,
    role            TEXT NOT NULL,
    kind            TEXT NOT NULL,             -- rating|comparison|override|engagement
    opportunity_id  TEXT REFERENCES opportunity_spaces(id) ON DELETE CASCADE,
    other_opportunity_id TEXT REFERENCES opportunity_spaces(id) ON DELETE CASCADE,
    verdict         TEXT,                      -- useful|not_useful|wrong|left|right
    reason          TEXT,                      -- §4.7.7: the most valuable free text in the system
    exposure_context TEXT NOT NULL DEFAULT '{}' -- rank shown, view, filters, exploration slot (DR-15)
);
CREATE INDEX IF NOT EXISTS idx_feedback_topic ON feedback(opportunity_id);


-- ---------------------------------------------------------------------------
-- Collaboration workflow (FR-25, §4.10).
--
-- §4.10 recommends "A + B + D, with C as a fast follower": run the sequential
-- stage-gate as the backbone because it produces accountability, open the front
-- of the pipeline to bottom-up injection, and anchor it with a review board.
--
-- Model A — the stage gate. A topic moves Shortlisted -> Demand-tested ->
-- Packaged -> Live, with an owner per stage. The weakness §4.10 names is
-- latency ("a topic can die waiting for a stage owner"), so every transition is
-- timestamped and the age-in-stage is queryable.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workflow_state (
    opportunity_id  TEXT PRIMARY KEY REFERENCES opportunity_spaces(id) ON DELETE CASCADE,
    stage           TEXT NOT NULL DEFAULT 'shortlisted',
    owner_role      TEXT,
    owner           TEXT,
    entered_stage_at TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    note            TEXT
);

CREATE TABLE IF NOT EXISTS workflow_transitions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id  TEXT NOT NULL REFERENCES opportunity_spaces(id) ON DELETE CASCADE,
    from_stage      TEXT,
    to_stage        TEXT NOT NULL,
    actor           TEXT NOT NULL,
    actor_role      TEXT NOT NULL,
    reason          TEXT,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_transitions_topic ON workflow_transitions(opportunity_id, created_at);

-- Model C — distributed assessment. "All three roles rate topics on their own
-- axis (strategy: attractiveness; sales: demand; presales: deliverability).
-- Divergence between the external score and internal ratings is surfaced as a
-- review trigger."
--
-- Each role rates only its OWN axis. That is the whole point: a salesperson is
-- authoritative about whether customers are asking, and is not being asked to
-- second-guess the evidence base. Ratings are 0-5 discrete with anchors, for
-- the same score-compression reason as the strategic-relevance rubric (§4.6),
-- and §4.7.4's finding that people are unreliable at fine-grained absolute
-- scores.
CREATE TABLE IF NOT EXISTS assessments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id  TEXT NOT NULL REFERENCES opportunity_spaces(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,            -- strategist | sales | presales
    axis            TEXT NOT NULL,            -- strategic_fit | customer_demand | deliverability
    rating          INTEGER NOT NULL,         -- 0..5
    confidence      INTEGER NOT NULL DEFAULT 3,  -- 1..5, weights the aggregate
    rationale       TEXT,                     -- §4.7.7: the most valuable free text in the system
    author          TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    weight_set      TEXT NOT NULL,            -- the config the topic was scored under when rated
    superseded      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_assessments_topic ON assessments(opportunity_id, role, superseded);

-- ---------------------------------------------------------------------------
-- Reference data for market sizing (§4.3.4, Table 19).
--
-- Deliberately NOT the signals table. Eurostat enterprise counts and adoption
-- rates are denominators, not dated events: they carry no publisher diversity,
-- no momentum and no relevance, and storing them as signals would inflate every
-- component that counts attached signals. They are reference series, refreshed
-- on their own annual-ish cadence, and read only by the sizing engine.
--
-- DR-08 still applies: the value plus its coordinates and the dataset's own
-- `updated` stamp are stored, never a mirror of the publication.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reference_series (
    id              TEXT PRIMARY KEY,          -- config key: sbs | ict_cloud | ...
    dataset         TEXT NOT NULL,             -- Eurostat dataset code
    publisher       TEXT NOT NULL,
    label           TEXT NOT NULL,
    url             TEXT NOT NULL,
    licence         TEXT NOT NULL,
    source_updated  TEXT,                      -- the dataset's own `updated` stamp
    fetched_at      TEXT NOT NULL,
    rows            INTEGER NOT NULL DEFAULT 0,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS reference_observations (
    series_id       TEXT NOT NULL REFERENCES reference_series(id) ON DELETE CASCADE,
    indicator       TEXT NOT NULL,             -- ENT_NR | E_CC | E_AI_TML | ...
    nace            TEXT NOT NULL,
    geo             TEXT NOT NULL,
    size_class      TEXT NOT NULL,             -- SBS size class, or GE10 for the ICT survey
    period          TEXT NOT NULL,             -- year
    value           REAL NOT NULL,
    unit            TEXT NOT NULL,             -- ENT | PC_ENT | MEUR
    PRIMARY KEY (series_id, indicator, nace, geo, size_class, period)
);
CREATE INDEX IF NOT EXISTS idx_refobs_lookup
    ON reference_observations(series_id, indicator, nace, geo);

-- ---------------------------------------------------------------------------
-- Market size per opportunity space (§4.3.4).
--
-- Same discipline as `scores`: the components AND the inputs that produced them
-- are stored (DR-05), so any figure can be re-derived, and the sizing config
-- version travels with the row for the same reason `weight_set` does (SC-10) —
-- sizes computed under different assumptions are not comparable.
--
-- No figure in this table was produced by a language model (§4.4.4 defence 3).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_sizes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id  TEXT NOT NULL REFERENCES opportunity_spaces(id) ON DELETE CASCADE,
    computed_at     TEXT NOT NULL,
    method          TEXT NOT NULL,             -- bottom_up_adoption | procurement_observed
    currency        TEXT NOT NULL DEFAULT 'EUR',
    tam_low         REAL, tam_base REAL, tam_high REAL,
    sam_low         REAL, sam_base REAL, sam_high REAL,
    som_low         REAL, som_base REAL, som_high REAL,
    confidence      TEXT NOT NULL,             -- observed | partial | modelled
    factors         TEXT NOT NULL,             -- JSON: every factor with its source and date
    coverage        TEXT NOT NULL,             -- JSON: geographies covered vs requested (NFR-08)
    caveats         TEXT NOT NULL DEFAULT '[]',-- JSON: the proxies and assumptions, spelled out
    sizing_version  TEXT NOT NULL,
    pipeline_version TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sizes_topic ON market_sizes(opportunity_id, method, computed_at);

-- ---------------------------------------------------------------------------
-- Long-form topic description (FR-14, FR-18) and the sales/presales brief.
--
-- The description is generated under the same four hallucination defences as
-- synthesis (§4.4.4): every narrative section carries the signal ids it was
-- written from, uncited sections are stripped, and generated numbers are
-- rejected — the figures in a brief come from `market_sizes` and `scores`,
-- never from the model.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS topic_descriptions (
    opportunity_id  TEXT PRIMARY KEY REFERENCES opportunity_spaces(id) ON DELETE CASCADE,
    generated_at    TEXT NOT NULL,
    topic_version   INTEGER NOT NULL,          -- the version described, so staleness is detectable
    sections        TEXT NOT NULL,             -- JSON {section: {text, signals:[...]}}
    stripped        TEXT NOT NULL DEFAULT '[]',-- JSON: what evidence binding removed, and why
    prompt_version  TEXT NOT NULL,
    model_version   TEXT NOT NULL,
    pipeline_version TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- Competitive intensity per topic (§4.3.3, Table 27).
--
-- A FOURTH quantity beside attractiveness, right to win and conviction, and
-- kept as separate from them as they are from each other (SC-12): a crowded
-- field and a weak Orange position are two different facts, and averaging them
-- would hide both. `competitors` stores the named list with the evidence that
-- justified each entry, so any level can be re-derived (NFR-01, LK-08).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS topic_competition (
    opportunity_id  TEXT PRIMARY KEY REFERENCES opportunity_spaces(id) ON DELETE CASCADE,
    computed_at     TEXT NOT NULL,
    level           TEXT NOT NULL,             -- none | low | medium | high
    score           REAL NOT NULL,
    competitors     TEXT NOT NULL,             -- JSON [{id,label,type,basis,mentions:[...]}]
    inputs          TEXT NOT NULL,             -- JSON: the weights and bands that produced the level
    register_version TEXT NOT NULL,
    pipeline_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS topic_briefs (
    opportunity_id  TEXT PRIMARY KEY REFERENCES opportunity_spaces(id) ON DELETE CASCADE,
    generated_at    TEXT NOT NULL,
    topic_version   INTEGER NOT NULL,
    path            TEXT NOT NULL,             -- PDF on disk; DR-08 keeps blobs out of the row
    filename        TEXT NOT NULL,
    bytes           INTEGER NOT NULL,
    content_hash    TEXT NOT NULL,
    description_at  TEXT,                      -- which description generation it rendered
    market_size_at  TEXT,                      -- which sizing run it rendered
    weight_set      TEXT NOT NULL,
    sizing_version  TEXT,
    prompt_version  TEXT,
    model_version   TEXT,
    pipeline_version TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- Internal signal injection (FR-24). Collaboration model B (§4.10): captures
-- the most valuable signal in the company, which currently lives only in
-- people's heads. Weighted carefully so one loud account cannot distort the
-- radar.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS internal_signals (
    id              TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    author          TEXT NOT NULL,
    kind            TEXT NOT NULL,             -- customer_conversation|rfp_theme|lost_deal
    title           TEXT NOT NULL,
    body            TEXT NOT NULL,
    vertical        TEXT,
    geographies     TEXT NOT NULL DEFAULT '[]',
    account_hint    TEXT,
    moderated       INTEGER NOT NULL DEFAULT 0,
    signal_id       TEXT REFERENCES signals(id)
);

-- ---------------------------------------------------------------------------
-- Competitor profiling (§4.3.3 extension).
--
-- The curated register in config/business_graph/competitors.yaml says what a
-- competitor sells, as a Sprint 0 curation deliverable. These tables hold what
-- the competitor SAYS it sells, taken from its own published pages.
--
-- That is a weaker kind of evidence and is treated as such everywhere: a
-- vendor's own site is TIER 4, it is capped in evidence quality like any other
-- interested party, and SC-09's guarantee -- vendor-only evidence scores low --
-- is untouched by any of this. What a profile is allowed to do is SEED
-- generation (the competitor-move lens in synthesis) and EXPLAIN a competitor
-- already matched to a topic. It may not lift a score.
--
-- DR-08 applies exactly as it does to signals: URL plus a bounded extract,
-- never a mirror of the page.
-- ---------------------------------------------------------------------------
-- ---------------------------------------------------------------------------
-- Planner (strategy engine).
--
-- A PLAN is a selection of opportunity spaces, an entry year for each, and a
-- five-year revenue and profit projection under a stated set of assumptions.
-- Three things are kept apart in the schema because they are different kinds of
-- claim, exactly as elsewhere in this codebase:
--
--   inputs      what the caller asked for. Reproducible: the same inputs and
--               the same versions give the same plan, and a test asserts it.
--   projection  arithmetic over stored sizes and configured bands. No model.
--   narrative   a model writing prose ABOUT the projection. Absent until asked
--               for, and it may not introduce a number.
--
-- Every plan records economics_version, sizing_version and weight_set. A plan
-- built under different assumptions is not comparable with another, and the
-- interface will not chart them together silently.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS plans (
    id              TEXT PRIMARY KEY,          -- PLAN-xxxxxxxx
    created_at      TEXT NOT NULL,
    label           TEXT,
    inputs          TEXT NOT NULL,             -- JSON: the full parameter set
    status          TEXT NOT NULL,             -- draft | computed | narrated
    objective       TEXT NOT NULL,
    plan_years      INTEGER NOT NULL,
    selected_count  INTEGER NOT NULL DEFAULT 0,
    considered_count INTEGER NOT NULL DEFAULT 0,
    projection      TEXT NOT NULL DEFAULT '{}',-- JSON: per-year revenue/profit, bands, mix
    capacity_usage  TEXT NOT NULL DEFAULT '{}',-- JSON: per pool per year, and what bound
    exclusions      TEXT NOT NULL DEFAULT '[]',-- JSON: why each near-miss was left out
    flags           TEXT NOT NULL DEFAULT '[]',-- JSON: plausibility and concentration warnings
    narrative       TEXT,                      -- JSON {section: text} or NULL
    stripped        TEXT NOT NULL DEFAULT '[]',
    economics_version TEXT NOT NULL,
    sizing_version  TEXT,
    weight_set      TEXT,
    prompt_version  TEXT,
    model_version   TEXT,
    pipeline_version TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_plans_created ON plans(created_at);

-- One row per space selected into a plan, with its entry year and the economics
-- that were applied to it. Denormalised on purpose: a plan has to stay
-- reproducible after the topic beneath it has moved on.
CREATE TABLE IF NOT EXISTS plan_selections (
    plan_id         TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    opportunity_id  TEXT NOT NULL REFERENCES opportunity_spaces(id) ON DELETE CASCADE,
    entry_year      INTEGER NOT NULL,          -- 1-based, within the plan window
    horizon         TEXT,
    portfolio_distance INTEGER,
    margin_applied  REAL NOT NULL,
    entry_effort    REAL NOT NULL,             -- person-years, after any shared-build discount
    pool            TEXT,                      -- capability pool it draws on
    som_base        REAL,
    revenue_by_year TEXT NOT NULL DEFAULT '[]',-- JSON, after overlap adjustment
    profit_by_year  TEXT NOT NULL DEFAULT '[]',
    overlap_factor  REAL NOT NULL DEFAULT 1.0,
    rationale       TEXT,                      -- why it was selected, computed not written
    PRIMARY KEY (plan_id, opportunity_id)
);
CREATE INDEX IF NOT EXISTS idx_plansel_topic ON plan_selections(opportunity_id);

CREATE TABLE IF NOT EXISTS competitor_pages (
    id              TEXT PRIMARY KEY,          -- sha256 of competitor_id + url
    competitor_id   TEXT NOT NULL,             -- register id; not an FK, the register is config
    url             TEXT NOT NULL,
    kind            TEXT NOT NULL,             -- home | solution | industry | product | customer_story | other
    title           TEXT,
    extract         TEXT NOT NULL,             -- bounded text (DR-08)
    lang            TEXT,
    content_hash    TEXT NOT NULL,
    fetched_at      TEXT NOT NULL,
    http_status     INTEGER,
    pipeline_version TEXT NOT NULL,
    UNIQUE (competitor_id, url)
);
CREATE INDEX IF NOT EXISTS idx_cpages_competitor ON competitor_pages(competitor_id, kind);

-- One profile per competitor, regenerated when its page corpus moves.
-- `claims` carries every statement with the page ids that support it, on the
-- same evidence-binding rule as synthesis: an uncited claim is stripped.
CREATE TABLE IF NOT EXISTS competitor_profiles (
    competitor_id   TEXT PRIMARY KEY,
    generated_at    TEXT NOT NULL,
    status          TEXT NOT NULL,             -- profiled | blocked | unreachable | no_pages
    status_reason   TEXT,
    positioning     TEXT,                      -- what they say they are, in one paragraph
    claims          TEXT NOT NULL DEFAULT '[]',-- JSON [{claim, pages:[page ids]}]
    verticals       TEXT NOT NULL DEFAULT '[]',-- JSON, closed vocabulary
    technologies    TEXT NOT NULL DEFAULT '[]',-- JSON, closed vocabulary
    use_cases       TEXT NOT NULL DEFAULT '[]',-- JSON, closed vocabulary
    named_offers    TEXT NOT NULL DEFAULT '[]',-- JSON [{name, pages:[...]}] -- their product names
    stripped        TEXT NOT NULL DEFAULT '[]',-- JSON: what evidence binding removed, and why
    pages_used      INTEGER NOT NULL DEFAULT 0,
    corpus_hash     TEXT,                      -- staleness: changes when the page set changes
    register_version TEXT NOT NULL,
    prompt_version  TEXT,
    model_version   TEXT,
    pipeline_version TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cprofiles_status ON competitor_profiles(status);

-- Per-topic competitive analysis: the structural join between a topic and the
-- profiles of the competitors already matched to it by competition.py, plus an
-- optional written comparison. The join is arithmetic and always present; only
-- the narrative costs a model call, so it is capped and generated on demand in
-- the same way descriptions are.
CREATE TABLE IF NOT EXISTS topic_competitor_analysis (
    opportunity_id  TEXT PRIMARY KEY REFERENCES opportunity_spaces(id) ON DELETE CASCADE,
    computed_at     TEXT NOT NULL,
    topic_version   INTEGER NOT NULL,          -- staleness, as for descriptions and briefs
    entries         TEXT NOT NULL DEFAULT '[]',-- JSON: per competitor, what their own pages say about this cell
    narrative       TEXT,                      -- JSON {section: {text, pages:[...]}} or NULL when ungenerated
    stripped        TEXT NOT NULL DEFAULT '[]',
    coverage        TEXT NOT NULL DEFAULT '{}',-- JSON: profiled / blocked / unprofiled counts behind this view
    register_version TEXT NOT NULL,
    prompt_version  TEXT,
    model_version   TEXT,
    pipeline_version TEXT NOT NULL
);
"""

#: Columns added after the first release. SQLite's CREATE TABLE IF NOT EXISTS
#: silently leaves an existing table alone, so a new column in SCHEMA above
#: never reaches a database that already exists. Each entry is applied only when
#: the column is absent, which makes `init_schema` safe to run repeatedly and
#: safe to run against the deployed copy.
MIGRATIONS: list[tuple[str, str, str]] = [
    # (table, column, DDL fragment)
    ("topic_briefs", "brief_schema", "TEXT"),
    # The Planner's exported PDF. Kept on the plan row rather than in its own
    # table because a plan is immutable once computed — its id is a fingerprint
    # of its inputs — so there is only ever one report per plan.
    ("plans", "pdf_path", "TEXT"),
    ("plans", "pdf_bytes", "INTEGER"),
    ("plans", "pdf_hash", "TEXT"),
    ("plans", "pdf_generated_at", "TEXT"),
    ("plans", "pdf_schema", "TEXT"),
]


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        if JOURNAL_MODE != "WAL":
            # Every connection, not just the one that ran the schema: SQLite
            # stores the mode in the file header, but a connection that assumes
            # WAL on a share it cannot use there fails on first write.
            conn.execute(f"PRAGMA journal_mode = {JOURNAL_MODE}")
        return conn

    @contextmanager
    def cursor(self) -> Iterator[sqlite3.Cursor]:
        conn = self.connect()
        try:
            cur = conn.cursor()
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        conn = self.connect()
        try:
            # Substituted rather than interpolated: the DDL below is full of
            # '{}' JSON defaults, so an f-string schema does not survive
            # contact with it.
            conn.executescript(SCHEMA.replace("__JOURNAL_MODE__", JOURNAL_MODE))
            self._apply_migrations(conn)
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _apply_migrations(conn: sqlite3.Connection) -> None:
        """Add columns that post-date a database's creation.

        `CREATE TABLE IF NOT EXISTS` silently leaves an existing table alone, so
        a column added to SCHEMA never reaches a database that already exists.
        This is additive and idempotent — no rewrite, no data movement — which
        is what makes it safe to run against the deployed file, where the
        feedback, assessments and briefs the pipeline never saw are the entire
        reason that file is not simply recreated.
        """
        for table, column, ddl in MIGRATIONS:
            if not conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone():
                continue
            cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
            if column not in cols:
                log.info("Migration: adding %s.%s", table, column)
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    # -- helpers -----------------------------------------------------------

    def query(self, sql: str, params: tuple | dict = ()) -> list[sqlite3.Row]:
        conn = self.connect()
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def query_one(self, sql: str, params: tuple | dict = ()) -> sqlite3.Row | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None


def js(value: Any) -> str:
    """Serialise a JSON column value deterministically (SC-11 reproducibility)."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def unjs(value: str | None, default: Any = None) -> Any:
    if not value:
        return default if default is not None else None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default
