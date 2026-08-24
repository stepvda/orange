# Data model reference

{{TABLE_COUNT}} tables in one SQLite file. This is the physical reference; the
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

{{MIGRATIONS}}

## Tables
{{TABLES}}

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
