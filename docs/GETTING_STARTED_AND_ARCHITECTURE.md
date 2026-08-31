# Getting started and architecture

## Quick start

```bash
# 1. Python deps
pip install -r requirements.txt

# 2. Configure the LLM provider and contact address
cp .env.example .env        # then fill in DEEPSEEK_API_KEY

# 3. Check the config and vocabularies load
PYTHONPATH=src python3 -m radar.cli check

# 4. Run the pipeline end to end. Collection is parallel; synthesis dominates
#    the rest. GDELT is the long pole when it is rate-limiting.
PYTHONPATH=src python3 -m radar.cli refresh --since-days 60

# 5. Serve the read API
PYTHONPATH=src python3 -m radar.cli serve            # → http://127.0.0.1:8000

# 6. Serve the React frontend (separate terminal)
npm --prefix frontend install
npm --prefix frontend run dev                        # → http://localhost:5173
```

Signing in: the first start of an empty database creates one account,
**`orange` / `orange`**, and the interface says so on every screen until the
password is changed. Change it in the app (click the account name in the top
bar) or from the command line:

```bash
PYTHONPATH=src python3 -m radar.cli user passwd orange   # prompts, twice
PYTHONPATH=src python3 -m radar.cli user add jo          # a second account
PYTHONPATH=src python3 -m radar.cli user list            # who exists, who is still on the default
```

The pipeline can also be run stage by stage, which is how you iterate:

```bash
PYTHONPATH=src python3 -m radar.cli refresh --stages collect,classify
PYTHONPATH=src python3 -m radar.cli refresh --stages themes
PYTHONPATH=src python3 -m radar.cli refresh --stages synthesise --max-clusters 8
PYTHONPATH=src python3 -m radar.cli refresh --stages graph,link,score,actions
PYTHONPATH=src python3 -m radar.cli refresh --stages reference,size,competition
PYTHONPATH=src python3 -m radar.cli refresh --stages describe
```

Useful commands:

| Command                                                         | What it does                                                                    |
| --------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| `radar check`                                                   | Validate config, print vocabulary sizes, flag unconfirmed source terms          |
| `radar topics --role sales`                                     | Role-ranked topic list (FR-13)                                                  |
| `radar show OS012`                                              | Full decomposition: claims, sources, links, score breakdown (NFR-01)            |
| `radar whitespace`                                              | High attractiveness, no portfolio path (FR-32)                                  |
| `radar orphan-offers`                                           | Offers with no live topic — portfolio decay (FR-33)                             |
| `radar coverage`                                                | Language / geography / tier coverage (NFR-08)                                   |
| `radar replay --date 2024-06-01`                                | Historical replay with leakage controls (FR-35)                                 |
| `radar confirm-link <pattern> --decision confirmed --curator x` | Curator link decision (LK-06)                                                   |
| `radar reference-data`                                          | Fetch the Eurostat denominators market sizing needs (§4.3.4)                    |
| `radar size`                                                    | Compute market size per opportunity space, both methods (§4.3.4)                |
| `radar competition`                                             | Assess competitive intensity per space (§4.3.3)                                 |
| `radar describe --limit 40`                                     | Write the long-form descriptions and solution diagrams (FR-14)                  |
| `radar brief OS012 --open`                                      | Render the sales/presales PDF brief (FR-18)                                     |
| `radar competitor-scrape`                                       | Crawl competitor sites into the profiling corpus, robots-aware                  |
| `radar competitor-profile`                                      | Build a structured profile per competitor from that corpus                      |
| `radar competitor-analysis`                                     | Per-topic competitor analysis and the differentiation angle                     |
| `radar plan --narrate --pdf`                                    | Build a five-year portfolio plan, write the business plan, export it as one PDF |
| `radar plans`                                                   | List stored plans with their headline figures                                   |
| `radar plan --source workflow --from-stage demand_tested`       | Plan the set the stage gate has already committed to, rather than choosing one  |
| `radar delete-space OS123`                                      | Remove a space — prints the impact first, and says what it does _not_ take      |
| `radar internal add \| moderate \| promote`                     | Internal signal intake — conversations, RFP themes, lost deals                  |

---

## Architecture

Thirteen pipeline stages with defined input/output contracts (§4.2, Table 16), so
stages can be developed, tested and replaced independently.

```
 1  collect      connectors/ + query_grid   source config       → raw items
 2  normalise    pipeline/ingest.py         raw items           → signal records
 3  classify     pipeline/ingest.py         signals             → typed, tiered signals
 4  themes       pipeline/themes.py         signals             → theme clusters
 5  synthesise   pipeline/synthesis.py      clusters + taxonomy → candidate spaces
 5b enrich       pipeline/enrich.py         topics + signals    → more evidence per topic
 6  graph        graph.py                   business_graph/*    → nodes + edges
 6b link         graph.py                   topics + nodes      → typed links, portfolio distance
 6c score        scoring.py                 topics + links      → two scores, horizon, state
 6d actions      pipeline/actions.py        scored topics       → next action per role
 6e reference    reference.py               Eurostat            → reference series
 6f size         sizing.py                  topics + reference  → TAM/SAM/SOM, two methods
 6g competition  competition.py             topics + register   → level + named list
 7  describe     pipeline/describe.py       topics + links      → narrative + diagram spec

    serve        readmodel.py, api.py, brief.py                 → radar, briefs, PDF, API

Two subsystems sit beside the pipeline rather than in it. Both read what the
pipeline produced; neither writes to it.

 p1 plan         planner.py, plan_report.py   read model + economics.yaml
                                              → a selected SET, an entry schedule,
                                                a five-year projection and a PDF
 p2 collateral   presales/                    one snapshot of a space
                                              → twelve artefacts in five formats

Competitor intelligence runs on its own cadence, outside `refresh`:

 c1 competitor-scrape    competitor_intel.py      register → crawled pages
 c2 competitor-profile   competitor_intel.py      pages    → structured profiles
 c3 competitor-analysis  competitor_analysis.py   profiles → per-topic join + comparison
```

A parallel, slower path maintains the **Orange Business Graph** (offers,
references, partners, certifications, analyst positions, capabilities). It joins
at stage 6, so right-to-win can be improved without re-running discovery.

```
src/radar/
  config.py       controlled vocabularies, crosswalks, validation-at-load
  db.py           SQLite schema — carries DR-01…DR-15 directly
  llm.py          provider-agnostic client (deepseek | openai | ollama | mock)
  embeddings.py   local sentence-transformers, TF-IDF fallback
  graph.py        business graph + L0–L4 linking + portfolio distance
  reference.py    Eurostat reference series (enterprise counts, adoption rates)
  sizing.py       bottom-up and procurement-observed market size, factor by factor
  competition.py  named competitors, evidence matching, NONE/LOW/MEDIUM/HIGH
  brief.py        the sales/presales PDF, including the solution diagram
  competitor_intel.py     robots-aware competitor crawling and profile generation
  competitor_analysis.py  per-topic competitor join, comparison and differentiation
  generation.py   on-demand constrained synthesis (the Generate screen)
  scoping.py      the Generate screen's assistant — a corpus-grounded interview
                  that composes search briefs and refuses the ones the evidence
                  cannot answer
  planner.py      portfolio selection under constraints (a mixed-integer
                  program), the committed-set scheduler, the five-year
                  projection, the flags and the narrative
  plan_report.py  the plan as a six-part PDF — inputs, projection, spaces,
                  business plan, assumptions
  presales/       twelve pre-sales artefacts described once and emitted in five
                  formats: catalogue, context, builder, research, content,
                  blocks, documents, decks, emitters, charts, office
  auth.py         sign-in, sessions, PBKDF2 verifiers, the application-level
                  guard, and account management
  deletion.py     what a delete takes with it, reported before it is taken
  internal.py     internal signal intake with a moderation gate (tier 3)
  bootstrap.py    serving-instance storage prep that never raises at import
  scoring.py      5 attractiveness components, right-to-win, horizon, lifecycle
  workflow.py     stage gate, per-role assessment, conviction, divergence
  readmodel.py    role-specific ranking, filtering, white space, coverage
  api.py          FastAPI read API
  cli.py          command line
  connectors/     13 sources: ted, boamp, eurlex, have-your-say, gdelt, news RSS
                  (EN/FR), hacker news, openalex, arxiv, cordis, nist, cert-fr
  pipeline/       ingest, themes, prompts, synthesis, actions, run
frontend/         React + Vite + TypeScript; polar radar, workflow board,
                  analytics charts, topic detail, filters
config/           taxonomies, weights, sources, business graph, crosswalks
```

### Configuration, not code (NFR-11)

Nothing in the package hard-codes a vertical, a weight or a threshold. All of it
lives in `config/` and is validated at load time — a dangling id is a startup
error, not a runtime surprise, because §4.5.2 warns that crosswalk errors
propagate silently into every downstream number.

| File                                        | Contents                                                                                                                                                                                                    |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `config/taxonomy/*.yaml`                    | 15 verticals, 59 use cases, 38 technologies, 6 domains, 9 personas, 6 signal types                                                                                                                          |
| `config/settings.yaml` → `competitor_intel` | Crawl depth, pacing, URL filters and the per-run caps for competitor profiling                                                                                                                              |
| `config/settings.yaml`                      | Weight set, thresholds, lifecycle, horizon, curation                                                                                                                                                        |
| `config/strategy.yaml`                      | _Trust the future_ ambitions — the strategic-relevance rubric                                                                                                                                               |
| `config/sources.yaml`                       | Source catalogue (42 catalogued, 33 wired) with terms-of-use position                                                                                                                                       |
| `config/source_tiers.yaml`                  | Four-tier scheme + publisher overrides                                                                                                                                                                      |
| `config/business_graph/*.yaml`              | Offers, references, partners, certifications, capabilities                                                                                                                                                  |
| `config/crosswalks/*.csv`                   | CPV → vertical / use case, vertical → NACE, technology → adoption series; versioned, confidence per row                                                                                                     |
| `config/sizing.yaml`                        | Sizing scope, datasets, contract-value rules, uncertainty bands, share assumptions                                                                                                                          |
| `config/business_graph/competitors.yaml`    | 65 named competitors with type, aliases, partner relationship, website and scrape status                                                                                                                    |
| `config/role_modes.yaml`                    | Per-role ranking functions and link-type filters                                                                                                                                                            |
| `config/economics.yaml`                     | Everything the Planner turns a market size into money with: margin by portfolio distance, ramp by horizon, capacity and effort, overlap discounts, and four figures quoted from Orange's own filed accounts |

**Changing any weight requires a new `weight_set` id.** Scores across a version
boundary are not comparable, every score records the set that produced it
(SC-10), and the UI refuses to plot a trajectory across the boundary silently
(§4.6 calibration-drift guard). The same rule extends to `sizing_version` on
every market size, `register_version` on every competitive assessment, and
`economics_version` on every plan — a plan's id carries the version, so two plans
built under different bands can never be confused for one another.

---


