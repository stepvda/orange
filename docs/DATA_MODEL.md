# Data model reference

29 tables in one SQLite file. This is the physical reference; the
diagrams in the Technical Architecture (Figures 7–10 and 12) show the same thing
with its relationships.

Row counts are from the working database at the time of writing and are there to
give a sense of scale, not as a contract.

## Why SQLite

The graph is thousands of nodes, not millions, so a relational store in one file
is the right size of solution. A single file also makes the historical replay
harness a file copy rather than a restore procedure, and the serving profile is
read-mostly with a single writer: discovery is a scheduled batch job, and the API
writes only feedback, assessments, stage moves and generated artefacts.

The deployed instance runs in `DELETE` journal mode rather than WAL, because
`/home` on Azure App Service is an SMB mount and WAL needs shared memory SMB
cannot provide. `bootstrap.py` converts the seeded copy once and the app is told
to keep using it.

## Migrations

`CREATE TABLE IF NOT EXISTS` leaves an existing table alone, so a column added to
`SCHEMA` never reaches a database that already exists. `db.MIGRATIONS` is an
additive, idempotent list applied on `init_schema()` — no rewrite, no data
movement — which is what makes it safe to run against the deployed file where the
feedback and assessments the pipeline never saw are the whole reason that file is
not simply recreated.

| Table | Column | Added for |
|---|---|---|
| `topic_briefs` | `brief_schema` | Distinguishing an INCOMPLETE brief (missing a section that current briefs carry) from a merely STALE one. |
| `plans` | `pdf_path` | Where the exported plan document was written. |
| `plans` | `pdf_bytes` | Size, so the interface can show it without opening the file. |
| `plans` | `pdf_hash` | Content hash — cache-busts the embedded viewer when a plan is re-exported. |
| `plans` | `pdf_generated_at` | When the export was rendered. |
| `plans` | `pdf_schema` | Which renderer version produced it, so an old export can be recognised as stale. |

## Tables

### Core

| Table | Rows | Purpose |
|---|---:|---|
| `opportunity_signals` | 11,181 | Evidence attachment, recording which refresh first attached each signal — what makes momentum honest. |
| `opportunity_spaces` | 418 | The canonical unit. Identity is the vertical × use case × technology triple (DR-02, DR-03). |
| `refreshes` | 37 | One row per run: reference date, replay flag, per-stage statistics, per-source errors. |
| `scores` | 1,844 | One row per topic per score kind per computation, with components AND the inputs that produced them (DR-05, SC-10). |

### Discovery

| Table | Rows | Purpose |
|---|---:|---|
| `clusters` | 325 | Theme clusters, recomputed each refresh; the seed for synthesis. |
| `raw_items` | 11,353 | Replay archive — the connector payload as returned, so a past date can be re-run without re-fetching (DR-14, FR-35). |
| `signals` | 11,354 | Dated, attributable evidence, stored by reference plus a bounded extract (DR-01, DR-08). |

### Business graph

| Table | Rows | Purpose |
|---|---:|---|
| `graph_edges` | 182 | Typed, dated, sourced edges. A partner's tier is an EDGE property, not a node one. |
| `graph_nodes` | 181 | Offers, references, partners, certifications, analyst positions, capability pools (DR-11). |
| `link_pattern_decisions` | 0 | Curator adjudications; later occurrences of a pattern inherit the decision (LK-06). |
| `opportunity_links` | 4,832 | Typed links topic → asset, with evidence, confidence and the confirming curator (DR-13, LK-04…LK-08). |

### Qualification

| Table | Rows | Purpose |
|---|---:|---|
| `market_sizes` | 701 | TAM/SAM/SOM by method, every factor with its source and basis, plus caveats (§4.3.4). |
| `reference_observations` | 56,385 | Statistical values by indicator, industry, geography, size class and period. Denominators, not signals. |
| `reference_series` | 5 | Eurostat dataset metadata including the publisher's own updated stamp and licence. |
| `topic_competition` | 181 | Competitive intensity level over a named competitor list, with the evidence for each (§4.3.3). |

### Competitor intel

| Table | Rows | Purpose |
|---|---:|---|
| `competitor_pages` | 1,745 | Crawled competitor pages — URL plus a bounded extract, never a mirror. |
| `competitor_profiles` | 65 | One structured profile per competitor, or a recorded reason why there is none. |
| `topic_competitor_analysis` | 177 | Per-topic join (always present) plus the written comparison (NULL until asked for). |

### Output

| Table | Rows | Purpose |
|---|---:|---|
| `topic_briefs` | 174 | Generated PDF metadata, stamped with every version it printed — including `brief_schema` (FR-18). |
| `topic_descriptions` | 174 | Long-form narrative, each section carrying the signal ids it was written from (FR-14). |

### Planner

| Table | Rows | Purpose |
|---|---:|---|
| `plan_selections` | 292 | One row per selected space per plan: entry year, the margin band applied, the overlap discount and the capability pool it draws on. |
| `plans` | 6 | One portfolio plan: the stated inputs, the projection, the flags and the narrative. The id is a fingerprint of the inputs, so a plan is immutable once computed. |

### Collaboration

| Table | Rows | Purpose |
|---|---:|---|
| `assessments` | 9 | One role's rating of its own axis, superseded rather than deleted (§4.10 model C). |
| `feedback` | 1 | Ratings, comparisons, overrides and engagement, with the exposure context (DR-15, §4.7.6). |
| `internal_signals` | 1 | Customer conversations, RFP themes and lost deals — inert until moderated (FR-24, §2.5). |
| `workflow_state` | 418 | Current stage and owner per topic (FR-25, §4.10 model A). |
| `workflow_transitions` | 2 | Full stage history with actor, role and reason. |

### Access

| Table | Rows | Purpose |
|---|---:|---|
| `sessions` | 0 | Live sign-ins, keyed by the SHA-256 of the cookie value. A copy of the database file therefore grants no logins. |
| `users` | 1 | Who may sign in. A username and a PBKDF2 verifier — never a password, and no personal data beyond what deciding access needs (DR-09). |

## The two identity rules

Everything about refresh behaviour follows from these, and both are enforced by
the database rather than by application code.

```sql
-- Syndication collapses to one item, so five outlets carrying the same wire
-- story cannot inflate publisher diversity.
CREATE UNIQUE INDEX idx_signals_url ON signals(url) WHERE url IS NOT NULL;

-- Canonical identity (§4.4.5). A recurring topic is UPDATED, never recreated:
-- new signals attach, the score is recomputed, the previous score is retained.
-- This is what makes momentum measurable.
CREATE UNIQUE INDEX idx_os_triple
    ON opportunity_spaces(vertical, use_case, technology)
    WHERE merged_into IS NULL;
```

## JSON-valued columns

JSON is used where the shape is **evidence about a computation** that is read
whole and never joined on. Anything filtered, counted or ranked is a real column.

| Column | Holds |
|---|---|
| `scores.components` / `.inputs` | Per-component value and the raw inputs behind it — what the score-explanation surface prints. |
| `opportunity_spaces.why_hot` | Claims, each with the signal ids supporting it. |
| `opportunity_links.evidence` | What justified the link. |
| `market_sizes.factors` / `.coverage` / `.caveats` | Every factor with source and date; geographies covered vs requested; the assumptions spelled out. |
| `topic_competition.competitors` / `.inputs` | The named list with basis and mentions; the weights and bands that produced the level. |
| `competitor_profiles.claims` / `.named_offers` / `.stripped` | Claims with their page ids; their own product names; what validation removed and why. |
| `topic_competitor_analysis.entries` / `.narrative` / `.coverage` | The join, the comparison, and how much of the field was actually readable. |
| `topic_descriptions.sections` / `.stripped` | Narrative sections with citations; what evidence binding removed. |
| `feedback.exposure_context` | Rank shown, view, active filters, exploration-slot flag — without which the feedback loop trains the radar to agree with itself. |
| `signals.attributes` | Connector-specific extras: procurement codes, tender value, regulatory dates. |

JSON is serialised with sorted keys and no ASCII escaping, so a byte comparison
of two rows is a meaningful reproducibility check (SC-11).

## Retention

| Data | Retention |
|---|---|
| `raw_items` | Kept locally for replay; **dropped from the serving package** — it is roughly half the file and the API never replays. Every citation still resolves because signals store the URL and extract independently. |
| `scores` | Full history. This is the trajectory momentum is measured from. |
| `market_sizes` | Full history, because each row carries the sizing version it was computed under. |
| `reference_observations` | Last three published periods per series. |
| `competitor_pages` | Replaced on re-crawl; `corpus_hash` on the profile detects when the page set moved. |
| Lifecycle states | Faded and dormant topics are retained, never deleted — a topic that goes quiet and returns is itself a signal. |
