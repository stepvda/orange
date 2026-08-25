import sys; sys.path.insert(0, ".")
from docx_kit import *

import pathlib
HERE = pathlib.Path(__file__).resolve().parent.parent
D = str(HERE / "diagrams") + "/"
doc = Doc("Orange Business Innovation Radar — Technical Architecture", "")

doc.cover(
    "Technical Architecture",
    "Opportunity Spaces / Innovation Radar",
    "ORANGE BUSINESS  ·  INNOVATION RADAR",
    [("Document", "Technical Architecture (TA)"),
     ("Version", "1.2"),
     ("Status", "For review"),
     ("Date", "24 August 2026"),
     ("Applies to", "Innovation Radar MVP · pipeline version 0.1.0 · weight set w-2026-08-a"),
     ("Repository", "src/radar (Python) · frontend (React + Vite) · config (YAML + CSV)"),
     ("Companion", "Functional Design Document (FDD), same date"),
     ("Audience", "Architects, engineers, data engineers, security review, operations")],
    statement="Two runtimes over one SQLite file. A batch discovery pipeline of thirteen stages writes; a read-mostly "
              "FastAPI service serves the read model and the built React bundle from the same origin, behind a session "
              "guard applied to the whole application rather than route by route. Nothing in the serving path imports "
              "the pipeline's heavy dependencies, no language model writes to the database unvalidated, and every "
              "stored number carries the inputs and the configuration version that produced it. Two subsystems sit "
              "beside the pipeline and do not belong to it: a portfolio optimiser that reads the read model and a "
              "collateral renderer that emits one description into five document formats.")

doc.toc([
    (1, "1   Architecture overview and principles"),
    (1, "2   Technology stack"),
    (1, "3   Component architecture"),
    (1, "4   The refresh pipeline"),
    (2, "4.1  Stage contracts  ·  4.2  Connectors  ·  4.3  Concurrency  ·  4.4  Failure containment  ·  4.5  Replay"),
    (1, "5   Runtime sequences"),
    (1, "6   The scoring engine"),
    (1, "7   The market-sizing engine"),
    (1, "8   The business graph and the linker"),
    (1, "9   Language-model integration and guardrails"),
    (1, "9b  Competitor intelligence architecture"),
    (1, "9c  The Planner — optimiser, projection, report"),
    (1, "9d  Pre-sales collateral rendering"),
    (1, "10  Data architecture"),
    (2, "10.1  Storage choice  ·  10.2  Physical data model  ·  10.3  Table catalogue  ·  10.4  Keys, indexes and constraints"),
    (2, "10.5  JSON-valued columns  ·  10.6  Volumes and retention"),
    (1, "11  API surface"),
    (1, "12  Frontend architecture"),
    (1, "13  Configuration architecture"),
    (1, "14  Deployment"),
    (1, "15  Performance"),
    (1, "16  Security, privacy and compliance"),
    (2, "16.1  Access control  ·  16.2  Data protection  ·  16.3  Application security  ·  16.4  Deleting a space"),
    (1, "17  Testing strategy"),
    (1, "18  Observability and operations"),
    (1, "19  Risks and technical debt"),
    (1, "20  Appendix A — module reference"),
])

# ============================================================ 1
doc.h1("1   Architecture overview and principles")
doc.p("The system is two runtimes sharing one database file. A **batch discovery pipeline** collects, classifies, "
      "synthesises, links, scores, sizes and describes; a **read-mostly HTTP service** serves the resulting read model "
      "and the built single-page application from the same origin. The two never run in the same process, and the "
      "serving runtime does not import the pipeline's machine-learning dependencies at all.")
doc.figure(D + "ta-01-layers.png", "Figure 1 — Layered architecture",
           "Each layer depends only on the layer below it. The read model exists so that neither the API nor the "
           "frontend needs to know how a score was computed in order to show it.")
doc.h2("1.1  Architectural principles")
doc.table(
    ["Principle", "What it means in practice", "Where it is enforced"],
    [["Configuration, not code", "No vertical, weight, threshold or source is hard-coded. Every one lives in "
      "YAML or CSV and is validated when the process starts.", "`config.py` validates every cross-reference at load; "
      "a dangling identifier is a startup error"],
     ["Every number decomposes", "A component returns a value **and** the inputs that produced it, and both are "
      "persisted.", "`ComponentResult(value, inputs)`; `scores.components` and `scores.inputs`"],
     ["Arithmetic where arithmetic will do", "Counting, diversity, recency and momentum are never a model call — "
      "a model asked to count will occasionally be wrong and always be unverifiable.", "No model call exists on those paths"],
     ["Retrieval and rules over generation", "Link assertion and evidence enrichment are joins with corroboration "
      "rules, not inferences.", "`graph.py` contains no model call at all"],
     ["Publication time, never ingestion time", "Every temporal computation reads the publication date. Ingestion "
      "time exists only to measure connector lag.", "Connector-level `reference_date` gating; `signals.published_at`"],
     ["Fail soft, report loudly", "One sick source must not cost a refresh. What was skipped is named in the "
      "refresh statistics.", "Per-source exception capture plus a per-host circuit breaker"],
     ["Version everything that can drift", "Weight set, sizing version, register version, prompt version, model "
      "version and pipeline version travel on the rows they produced.", "Columns on `scores`, `market_sizes`, "
      "`topic_competition`, `topic_descriptions`, `topic_briefs`"]],
    widths=[3.4, 7.0, 6.2], size=8.5)

# ============================================================ 2
doc.h1("2   Technology stack")
doc.table(
    ["Layer", "Choice", "Version", "Why this one"],
    [["Language (backend)", "Python", "≥ 3.10, deployed on 3.13", "Ecosystem for the statistical and NLP work; one "
      "language across pipeline and API"],
     ["HTTP framework", "FastAPI", "≥ 0.110", "Typed request models, automatic schema, low ceremony for a read-mostly API"],
     ["ASGI server", "gunicorn + uvicorn worker", "≥ 21.2 / ≥ 0.29", "One process, threaded; matches a single-core "
      "instance and a single-writer database"],
     ["Storage", "SQLite (WAL)", "stdlib", "The graph is thousands of nodes, not millions; a single file makes the "
      "replay harness trivial to snapshot"],
     ["Numerics", "numpy", "≥ 1.26", "Entropy, slope fitting, vector arithmetic"],
     ["Optimisation", "scipy (`optimize.milp`, HiGHS)", "≥ 1.11", "Portfolio selection is a mixed-integer program. "
      "Optional: a greedy fill runs when scipy is absent, and names every constraint it relaxed"],
     ["Clustering", "scikit-learn", "≥ 1.4", "Deterministic agglomerative clustering — no randomised initialisation, "
      "because reproducibility is a requirement"],
     ["Embeddings", "sentence-transformers, local", "≥ 2.7", "Runs on the machine; keeps the sovereign deployment "
      "option open. TF-IDF fallback when unavailable"],
     ["Model access", "OpenAI-compatible client", "≥ 1.40", "One interface for DeepSeek, OpenAI and Ollama alike"],
     ["PDF rendering", "reportlab", "≥ 4.0", "No browser dependency, which matters for a sovereign deployment"],
     ["Office output", "python-pptx · python-docx · odfpy", "≥ 0.6 / ≥ 1.1 / ≥ 1.4", "Pre-sales collateral in the "
      "format its reader works in. PowerPoint charts are native shapes, not pictures"],
     ["Password hashing", "hashlib.pbkdf2_hmac", "stdlib", "Not the best KDF — the best one available with NO new "
      "dependency, which is what keeps the sovereign option cheap"],
     ["Configuration", "PyYAML + CSV", "≥ 6.0", "Reviewable by someone who is not reading the code"],
     ["Validation", "pydantic", "≥ 2.6", "Request models on the write endpoints"],
     ["Frontend", "React + Vite + TypeScript", "18.3 / 6.0 / 5.6", "No chart library — the radar encoding is specific "
      "to this product and is hand-drawn SVG"],
     ["Tests", "pytest", "≥ 8.0", "475 tests; the model provider has a mock implementation so no test needs a network"]],
    widths=[3.2, 3.8, 2.6, 7.0], size=8.5)

# ============================================================ 3
doc.h1("3   Component architecture")
doc.p("The backend is a single Python package, `radar`, with one module per bounded responsibility. The module "
      "boundaries are the same boundaries the pipeline stages use, which is what makes a stage independently "
      "runnable and independently testable.")
doc.table(
    ["Module", "Lines", "Responsibility"],
    [["`config.py`", "553", "Controlled vocabularies, crosswalks, business graph configuration, validation at load"],
     ["`db.py`", "659", "The complete SQL schema, additive migrations, connection management, deterministic JSON helpers"],
     ["`llm.py`", "200", "Provider-agnostic client — deepseek | openai | ollama | mock"],
     ["`embeddings.py`", "99", "Local sentence-transformers with a TF-IDF fallback"],
     ["`connectors/`", "—", "17 connector types behind one registry — procurement, regulation, research, news and "
      "demand-side leading indicators — plus a shared HTTP session with retry, pacing and a circuit breaker"],
     ["`pipeline/`", "—", "`ingest` · `themes` · `synthesis` · `enrich` · `actions` · `describe` · `prompts` · "
      "`query_grid` (taxonomy-derived collection parameters) · `run`"],
     ["`bootstrap.py`", "340", "Prepares a serving instance's storage without ever raising at import — see 14.2"],
     ["`internal.py`", "—", "Internal signal intake with a moderation gate; enters the corpus at tier 3"],
     ["`generation.py`", "636", "On-demand, constrained synthesis for the Generate screen, scoped to what it created"],
     ["`competitor_intel.py`", "833", "Robots-aware competitor crawling and structured profile generation"],
     ["`competitor_analysis.py`", "419", "Per-topic competitor join and the written comparison, including the differentiation angle"],
     ["`graph.py`", "466", "Business graph materialisation, link generation and typing, portfolio distance"],
     ["`scoring.py`", "772", "Attractiveness (5 components), right to win (7), horizon derivation, lifecycle transitions"],
     ["`reference.py`", "271", "Eurostat reference series retrieval and storage"],
     ["`sizing.py`", "956", "Bottom-up and procurement-observed market size, factor by factor"],
     ["`competition.py`", "298", "Competitor matching, evidence detection, intensity banding"],
     ["`workflow.py`", "420", "Stage gate, per-role assessment, conviction aggregation, divergence detection"],
     ["`describe` + `brief.py`", "961", "Long-form description and the six-page PDF, including the solution diagram"],
     ["`readmodel.py`", "790", "Role-specific ranking and filtering, facets, white space, coverage, the bulk-fetch view context"],
     ["`auth.py`", "484", "Sign-in, sessions, PBKDF2 verifiers, the application-level guard and account management"],
     ["`scoping.py`", "661", "The Generate screen's scoping conversation — retrieval per turn, and the gate that "
      "decides whether a proposed brief is runnable"],
     ["`planner.py`", "1,274", "Portfolio selection under constraints, the committed-set scheduler, the five-year "
      "projection, the flags and the narrative"],
     ["`plan_report.py`", "837", "The plan as a six-part PDF, charts drawn with exact geometry"],
     ["`presales/`", "5,315", "`catalogue` · `context` · `builder` · `research` · `content` · `blocks` · `documents` "
      "· `decks` · `emitters` · `charts` · `office` — twelve artefacts described once and emitted in five formats"],
     ["`deletion.py`", "299", "What a delete takes with it, reported before it is taken and again afterwards"],
     ["`api.py`", "1,937", "FastAPI application, 68 endpoints, static mount for the built frontend"],
     ["`cli.py`", "753", "Command line: check, refresh, serve, topics, show, whitespace, replay, brief, the three "
      "competitor commands, internal intake, `user`, `plan`/`plans`, `delete-space`, and the rest"]],
    widths=[3.6, 1.4, 11.6], size=8.5)
doc.callout("The dependency rule that makes the deployment work",
            ["`radar.api` imports scikit-learn, sentence-transformers and the model client **only inside the functions "
             "that need them**. A serving instance therefore never loads torch, and the deployment package is 28 MB "
             "instead of multiple gigabytes. On a Free-tier App Service instance that is the difference between "
             "starting and not."], SH_BLUE, BLUE)

# ============================================================ 4
doc.h1("4   The refresh pipeline")
doc.p("Discovery runs as thirteen named stages with declared input and output contracts. Any subset can be run alone "
      "— `radar refresh --stages score,actions` — which is how the system is developed, tested and repaired. A stage "
      "reads what the previous stage wrote to the database; there is no in-memory hand-off between stages, so a stage "
      "can be re-run against yesterday's output without re-running its predecessors.")
doc.figure(D + "ta-02-pipeline.png", "Figure 2 — The refresh pipeline",
           "Stage contracts, concurrency, failure containment and the leakage control, in one view.")

doc.h2("4.1  Stage contracts")
doc.table(
    ["#", "Stage", "Module", "Input", "Output"],
    [["1", "collect", "`connectors/`", "source catalogue + reference date", "raw items"],
     ["2", "normalise", "`pipeline/ingest.py`", "raw items", "signal records, URL-deduplicated"],
     ["3", "classify", "`pipeline/ingest.py`", "signals", "signal type, relevance gate, tier, geography, language"],
     ["4", "themes", "`pipeline/themes.py`", "signals + embeddings", "theme clusters"],
     ["5", "synthesise", "`pipeline/synthesis.py`", "clusters + taxonomy", "candidate opportunity spaces"],
     ["5b", "enrich", "`pipeline/enrich.py`", "topics + unattached signals", "additional evidence per topic"],
     ["6", "graph", "`graph.py`", "business graph configuration", "graph nodes and typed edges"],
     ["6b", "link", "`graph.py`", "topics + graph nodes", "typed links L0–L4/SUP, portfolio distance"],
     ["6c", "score", "`scoring.py`", "topics + signals + links", "two scores, horizon, lifecycle state"],
     ["6d", "actions", "`pipeline/actions.py`", "scored topics", "next action per role"],
     ["6e", "reference", "`reference.py`", "Eurostat API", "reference series and observations"],
     ["6f", "size", "`sizing.py`", "topics + reference data + tenders", "TAM/SAM/SOM by two methods"],
     ["6g", "competition", "`competition.py`", "topics + competitor register", "intensity level + named list"],
     ["7", "describe", "`pipeline/describe.py`", "topics + links + competitors", "narrative sections + diagram structure"]],
    widths=[0.9, 2.2, 3.4, 4.6, 5.5], size=8.5)

doc.h2("4.2  Connectors")
doc.p("Thirteen connector classes are registered behind one name-keyed registry and driven from the source catalogue, "
      "so wiring a new source is a configuration entry plus a class. Every connector inherits a shared HTTP session "
      "with a declared user agent, a 45-second timeout, three retries with backoff, optional per-host pacing, and the "
      "circuit breaker described in 4.4.")
doc.table(
    ["Registry name", "Sources it serves"],
    [["`ted`, `boamp`, `uk_contracts`", "Procurement — above-threshold EU tenders, French below-threshold notices"],
     ["`eurlex`, `have_your_say`", "Regulation — dated legal instruments and open consultations with their deadlines"],
     ["`openalex`, `arxiv`, `cordis`, `crossref`", "Research and funded programmes"],
     ["`gdelt`, `rss_search`, `rss_feed`, `hackernews`", "News and practitioner attention, English and French"]],
    widths=[5.0, 11.6])
doc.callout("Three sampling defects worth knowing about", [
    "Each produced a plausible-looking corpus that was quietly wrong, and all three were found by inspecting what "
    "actually landed in the database rather than by reading the connector.",
    "**TED returned 40 of 14,485 matching notices, all from one day.** The API accepts no sort parameter and returns "
    "publication-date ascending, so a single capped request samples only the oldest day in the window. Momentum is the "
    "slope of signal volume over trailing periods, so that corpus made every procurement-driven momentum figure "
    "meaningless. Fixed by slicing the window into 14-day chunks and querying each: 827 notices across 35 distinct dates.",
    "**CORDIS returned nothing at all.** It leaks its own localisation template and emits dates such as "
    "`1 {{month_11}} 2023`, which failed date parsing, so every project was rejected as undated — silently, with no error.",
    "**EUR-Lex yielded 20 distinct acts from 120 rows.** The endpoint returns one row per expression title and several "
    "titles share a work, so rows collapsed on URL dedup. The limit was raised to compensate; a concept-based query is "
    "the proper fix.",
], SH_RED, RED)

doc.h2("4.3  Concurrency")
doc.p("Sources are independent and network-bound, so collection runs in a thread pool of eight. Twelve sources "
      "complete in about 45 seconds. **Database writes stay serial**, because deduplication is a read-modify-write "
      "over the whole signal table. Synthesis runs four clusters concurrently, and each cluster issues three "
      "generation calls plus a critic and an entailment call per candidate, so the concurrency multiplies against the "
      "provider and is raised with care. Description generation runs four topics in parallel and is capped at forty "
      "per refresh; what was left ungenerated is logged rather than silently dropped.")

doc.h2("4.4  Failure containment")
doc.bullets([
    "**Graceful degradation.** A failing source is recorded in the refresh statistics and never aborts the run. A "
    "refresh with eleven of thirteen sources is a usable refresh with a known gap.",
    "**Circuit breaker.** After two exhausted requests to a host, the remainder of that host's requests are skipped "
    "and the host is named in the collection errors. Without it, ten blocked GDELT queries cost eleven minutes for "
    "zero data. GDELT is the long pole in every refresh: everything else finishes in 45 seconds while it alone can "
    "take up to eleven minutes.",
    "**Undated evidence is rejected, not defaulted.** A signal whose publication date cannot be parsed or inferred is "
    "dropped, because defaulting it to the fetch date would silently corrupt momentum, recency and replay.",
])

doc.h2("4.5  Replay and leakage control")
doc.p("Every connector takes a `reference_date` and rejects anything published after it, filtering on the "
      "**publication** date and never the ingestion date. Leakage through late-arriving documents is the standard way "
      "a forecasting model produces excellent offline results and useless live ones. Raw archives are retained, so "
      "`radar replay --date 2024-06-01` reconstructs the state of the world as of that date without re-fetching "
      "anything.")

# ============================================================ 5
doc.h1("5   Runtime sequences")
doc.figure(D + "ta-03-sequence-refresh.png", "Figure 3 — Sequence: one refresh run",
           "Only two things on the scoring path call the model: the strategic-relevance rubric and the next action per role.")
doc.figure(D + "ta-04-sequence-read.png", "Figure 4 — Sequence: serving a view, and the N+1 that was removed",
           "The fix was not caching. It was fetching each table once for the whole set and indexing it in memory.")
doc.p("Assembling a view previously issued eleven database queries **per topic** — scores, links, node labels, "
      "competition, size, workflow state, assessments twice, signal count and two artefact checks. Across 167 topics "
      "that was roughly 1,670 round trips and 1.6 seconds of dead air on every filter change, role switch and tab "
      "change, and it was invisible in any frontend profile.")
doc.p("The read model is a read model, so the fix was the obvious one. `_assemble()` reads from a pre-built view "
      "context when it is given one and queries when it is not, so the single-topic detail path is untouched — and a "
      "test asserts the two paths produce byte-identical topics, because two code paths for one object is how two "
      "surfaces start disagreeing. A second test guards the query count against growing **with the number of topics**, "
      "which is the regression that would make a list feel broken at 150 rows.")

# ============================================================ 6
doc.h1("6   The scoring engine")
doc.figure(D + "ta-06-scoring.png", "Figure 6 — How a score is computed, and how it is explained",
           "Four of the five attractiveness components are arithmetic. Right to win is a structured lookup with no model call at all.")
doc.h2("6.1  Implementation notes that are easy to get wrong")
doc.bullets([
    "**Entropy is scale-invariant.** A uniform tier-4 discount applied inside the Shannon entropy computation cancels "
    "out entirely, and six vendor blogs then score identically to six independent outlets. The discount is applied to "
    "the **effective publisher count** instead. This was caught by a test, not by review.",
    "**Momentum is fitted on publication dates.** Using ingestion dates would make a backfill look like a surge.",
    "**Normalisation is cross-topic.** Market signal strength is normalised against the distribution across all live "
    "topics, so the component answers \"how visible is this relative to everything else on the radar\" rather than "
    "\"how many articles exist\".",
    "**The rubric is discrete.** Strategic relevance is scored 0–5 against written anchors and mapped through a "
    "configured table onto 0–100. A free 0–100 request compresses every answer into the middle of the scale.",
])
doc.h2("6.2  Lifecycle and horizon")
doc.p("Both are computed in the same module and stored on the topic with the reason that produced them. State "
      "transitions read the promotion gate from configuration — four signals, three distinct publishers, evidence "
      "quality of 45, at least one non-tier-4 source — and a topic discovered on the current refresh can never be "
      "classified dormant, because dormancy means observed silence rather than absence of history.")

# ============================================================ 7
doc.h1("7   The market-sizing engine")
doc.p("`sizing.py` is the largest single module in the backend, and almost all of it is bookkeeping about provenance "
      "rather than arithmetic. Every factor carries its source, its year and its basis; the row carries the "
      "geographies covered against those requested, the caveats spelled out, and the sizing configuration version.")
doc.table(
    ["Concern", "Implementation"],
    [["Two independent methods", "`bottom_up_adoption` — enterprise count × adoption rate × annual engagement value. "
      "`procurement_observed` — contracts that exist, annualised. Both stored, both published, never averaged."],
     ["Size-base consistency", "The enterprise count is restricted to the same size base as the adoption series "
      "(10+ employees). A test asserts the two share a base."],
     ["Contract eligibility", "A tender may price an engagement only if its **main object** resolves to an IT contract, "
      "not merely one of its lots. A test asserts this using the €188m turbine-retrofit case."],
     ["Size-class weighting", "Engagement value is scaled per size class, anchored on the class the observed contracts "
      "came from. The weights are configuration with a named owner and are printed in the brief."],
     ["Proxy handling", "A substituted series widens the band from ±15% to ±40% and lowers the confidence grade; it "
      "never moves the base. A test asserts a proxy widens the range without moving it."],
     ["Confidence grading", "The **worst** basis among the factors, never an average. A test asserts this."],
     ["Refusal to publish", "Where no attributable enterprise count exists — public administration, for example — no "
      "bottom-up figure is published and the space is sized from observed procurement only."],
     ["Crosswalk confidence", "Each crosswalk row carries a per-row confidence, and a test asserts that it reaches the "
      "arithmetic rather than sitting unused in the CSV."]],
    widths=[3.6, 13.0], size=8.5)
doc.p("Reference data is fetched by its own stage on its own cadence and refetched only when older than the configured "
      "age — these are annual statistics, not a feed. Five Eurostat series across 30 geographies and the last three "
      "published periods each produce 56,385 observations.")

# ============================================================ 8
doc.h1("8   The business graph and the linker")
doc.p("`graph.py` materialises the curated business graph from configuration into nodes and typed, dated, sourced "
      "edges, then generates, filters, types and scores links from each opportunity space onto those nodes. **No "
      "language model is used in this module at all**: matching against the asset catalogue is a join, not an inference.")
doc.h2("8.1  Edge semantics")
doc.p("Edges carry the semantics that matter rather than a generic \"relates to\": an offer ADDRESSES a use case; a "
      "reference DEMONSTRATES an offer in a vertical; a partner PROVIDES a technology at a tier; a certification is "
      "REQUIRED_BY a vertical; a capability pool STAFFS a domain. The partner's tier lives on the **edge**, not the "
      "node, because the same partner can be Gold for one technology and unlisted for another.")
doc.h2("8.2  Portfolio distance")
doc.p("Portfolio distance is the minimum ordinal distance over the topic's **delivery** links, or 4 when none exists. "
      "Supporting-evidence links are excluded from the computation, for the reason given in the FDD, section 7.1.")
doc.h2("8.3  Rebuild semantics")
doc.p("An early implementation truncated `graph_nodes` on rebuild while `opportunity_links` held a foreign key onto "
      "it, so a second rebuild failed. Nodes are now **upserted** and disappeared nodes are retired rather than "
      "deleted — which is also where the requirement that a withdrawn asset propagates to the topics that leaned on "
      "it now lives.")

# ============================================================ 9
doc.h1("9   Language-model integration and guardrails")
doc.figure(D + "ta-11-llm.png", "Figure 11 — Language-model integration and the guardrail chain",
           "The provider is an abstraction with a mock implementation, so no test needs a network. Nothing a model produces reaches the database unvalidated.")
doc.h2("9.1  Provider abstraction")
doc.p("One OpenAI-compatible interface serves DeepSeek, OpenAI and a locally hosted Ollama alike, selected by an "
      "environment variable. The `mock` implementation returns deterministic canned structures, which is what allows "
      "167 tests to run without a network and without a key.")
doc.h2("9.2  Call sites and their settings")
doc.table(
    ["Call site", "Temperature", "Batching / concurrency", "Purpose"],
    [["classify", "0.0", "12 items per request", "Signal type and relevance gate"],
     ["synthesise", "0.85", "4 clusters concurrent × 3 lensed passes", "Deliberate over-production of candidates"],
     ["critic", "0.10", "one call per candidate", "Adversarial review; score is the minimum across five tests"],
     ["entailment", "0.10", "one call per claim set", "Verify each claim is entailed by the span it cites"],
     ["rubric", "0.0", "one call per topic", "Strategic relevance 0–5 against written anchors"],
     ["actions", "0.0", "one call per topic", "Next action per role"],
     ["describe", "0.85", "4 topics concurrent, ≤ 40 per refresh", "Long-form narrative and diagram structure"]],
    widths=[2.6, 2.2, 5.0, 6.8], size=8.5)
doc.h2("9.3  The diagram is not drawn by the model")
doc.p("For the solution diagram in the PDF brief the model emits a **structure** — layers, boxes, who provides each "
      "one, what flows where — which the renderer draws to the same geometry every time. A model asked for SVG or "
      "drawing code produces something that looks plausible and overlaps its own labels; a model asked for structure "
      "produces something a renderer can guarantee. The closed-vocabulary rule applies to it too: a box claiming to be "
      "an Orange asset that is not in the linked graph is **demoted to third party rather than deleted** — the "
      "architecture still needs that component — and the demotion is recorded in the brief.")


# ============================================================ 9b
doc.h1("9b   Competitor intelligence architecture")
doc.p("Two modules, three tables and one hard constraint. `competitor_intel.py` reads competitor websites and turns "
      "them into structured profiles; `competitor_analysis.py` joins those profiles onto an opportunity space and, "
      "on request, writes the comparison. The functional case is in the Functional Design Document, section 9; what "
      "follows is how it is built and where it is bounded.")
doc.figure(D + "ta-12-erd-competitor.png",
           "Figure 12 — Physical data model, part 5: competitor intelligence",
           "The join and the comparison are separate columns because they are separate kinds of thing — one is "
           "arithmetic and always current, the other costs a model call and is absent until asked for.")

doc.h2("9b.1  The crawler")
doc.table(
    ["Concern", "Implementation"],
    [["robots.txt", "Checked **per URL, not per host**, and cached per host. A host whose robots.txt cannot be read "
      "fails CLOSED — the entry point only. The conservative reading costs a handful of competitors; the "
      "alternative is crawling somebody who may have said no in a file we failed to parse."],
     ["URL selection", "Sitemap first, following one level of index, with child sitemaps ranked by whether their own "
      "name suggests the part of the site we want. URLs are partitioned **as they arrive** into those whose path "
      "names a solution, industry, product or customer story and everything else; the second group tops up at most "
      "a quarter of the budget. Homepage links are the fallback when no sitemap is readable."],
     ["Locale collapsing", "Path identity with the leading locale segment removed, preferring the English variant. "
      "The locale list is an **allowlist** — `ai`, `it`, `id`, `is` and `no` are ISO codes and ordinary path "
      "segments both, and treating `/ai/platform` as a locale silently merges two different pages into one."],
     ["Pacing", "One request per host every 2 s by default, 8 competitors concurrent. The shared `HttpSession` "
      "supplies retry, backoff and the circuit breaker."],
     ["Storage", "DR-08 unchanged: URL plus an extract capped at 6,000 characters. A page yielding under 200 "
      "characters after tag-stripping is discarded rather than stored — it is a nav bar and a cookie banner."],
     ["Failure recording", "A crawl that stores nothing records **why**. Without that a refusal is indistinguishable "
      "from never having been attempted, and the coverage line would count a permanent gap as a pending one."]],
    widths=[3.2, 13.4], size=8.5)
doc.callout("The circuit breaker is tuned for the wrong job here",
            ["`HttpSession` trips after two exhausted requests to a host, which is right for a refresh that must "
             "finish inside its cadence window — ten blocked GDELT queries otherwise cost eleven minutes for zero "
             "data. For a profiler that runs rarely it is far too twitchy: eight competitors were lost to transient "
             "429s and 500s on the first full crawl.",
             "Re-running those eight with a six-failure budget and 6 s spacing recovered four. The default is "
             "unchanged; the patient settings are applied per run."], SH_GOLD, RGBColor(0x8A, 0x6D, 0x1F))

doc.h2("9b.2  Profile validation")
doc.p("The four synthesis defences apply, plus a fifth that had to be added after a defect:")
doc.numbers([
    "**Evidence binding** — every claim carries page ids validated against the pages actually supplied.",
    "**Closed vocabulary** — taxonomy values validated against the enumerations.",
    "**No generated numbers** — the shared numeric-claim regex, applied to claims and to the positioning paragraph.",
    "**Named-offer corroboration** — an offer name must appear in the corpus, not merely cite a page.",
    "**Vocabulary corroboration** — a valid id is kept only if its label, a synonym or the id itself appears in the "
    "pages, matched on word boundaries with a four-character minimum.",
])
doc.callout("Why the fifth defence exists",
            ["Asked for OVHcloud's technologies, the model returned the **first eight ids of the technology "
             "vocabulary, in vocabulary order** — private 5G, O-RAN, network slicing, SD-WAN, SASE, satellite NTN, "
             "LPWAN, Wi-Fi 6E. Every id is real, so closed-vocabulary validation passed all eight. OVHcloud's pages "
             "mention 5G exactly zero times.",
             "A list-echo is the characteristic failure of handing a model an enumeration, and the enumeration is "
             "precisely what makes it survive validation. Those tags feed competitor-seeded generation, so this was "
             "load-bearing. The remedy is the rule `enrichment` already applies to signal attachment — similarity "
             "alone is not evidence — applied to the same problem in a different place.",
             "Word boundaries matter: \u201cPrivate 5G / LTE\u201d splits to \u201clte\u201d, and substring-matching a "
             "three-letter token corroborates almost anything. `competition.py` learned the same lesson with its "
             "alias matcher."], SH_RED, RED)

doc.h2("9b.3  The join and the comparison")
doc.table(
    ["", "The join (`entries`)", "The comparison (`narrative`)"],
    [["Produced by", "Arithmetic over stored data", "One model call per topic"],
     ["Cost", "None", "One call, capped per run like descriptions"],
     ["Presence", "Always, on every analysed topic", "NULL until requested"],
     ["Freshness", "Recomputed whenever the topic or a profile moves", "Stamped with the topic version, prompt "
      "version and register version; stale when any moves"],
     ["Contains", "Relevant claims, register overlap, profiling status, competitor mentions",
      "Activity cited to their pages, the differentiation angle, the concession, the field paragraph"]],
    widths=[2.6, 6.6, 7.4], size=8.5)
doc.p("Re-running the cheap join must never discard an expensive comparison that still holds, so `_store` carries a "
      "`keep_narrative` flag and the join path preserves what the writing path produced. A test asserts it.")

doc.h2("9b.4  The differentiation guard")
doc.p("The differentiation paragraph may only name Orange assets **linked to the topic** in the business graph. The "
      "validator collects the linked asset labels, tolerates a dropped link-type suffix — a paragraph naming "
      "\u201cLive Objects\u201d rather than \u201cLive Objects (L0)\u201d is still naming a supplied asset — and strips the "
      "paragraph when anything else appears. The activity half is validated independently, so one failing does not "
      "discard the other.")
doc.p("This is the strictest guard in the codebase, and deliberately so: it is the one paragraph in the product a "
      "salesperson will repeat verbatim in front of a customer.")

doc.h2("9b.5  Seeding generation")
doc.p("`Synthesiser._competitor_targets` reads the profiled competitors' closed-vocabulary tags and returns cells "
      "where **two or more** competitors sell and the radar has no topic. Those cells move to the front of the "
      "coverage target list, and a fifth evidence lens asks the model to reason from competitive movement — while "
      "telling it plainly that a competitor's marketing is not a market and an unsupported candidate will be "
      "rejected downstream anyway.")
doc.p("Two competitors rather than one, because the cross-product of a single profile's tags is large and mostly "
      "spurious: a competitor tagged with 6 verticals, 8 use cases and 6 technologies implies 288 cells, almost "
      "none of which they actually sell. Requiring two independent competitors and then taking the top slice is "
      "what turns that cross-product back into a signal.")
doc.callout("A latent bug this uncovered",
            ["The lens rotation was `GENERATION_LENSES[index % len(LENSES)]`, where `index` runs over "
             "`candidates_per_cluster` (3) against 4 lenses. Lenses 0, 1 and 2 fired on every cluster and lens 3 "
             "fired on none — the cross-vertical lens was **unreachable for the entire life of the pipeline**, and "
             "the new competitor lens would have been dead on arrival.",
             "The window is now offset by the cluster, so each cluster still gets three different lenses while the "
             "corpus as a whole gets all five."], SH_BLUE, BLUE)


# ============================================================ 9c
doc.h1("9c   The Planner — optimiser, projection, report")
doc.p("The Planner sits beside the pipeline rather than in it. It reads the read model, writes two tables of its own, "
      "and is the only subsystem in the codebase that solves a mathematical program. It makes exactly **one** model "
      "call, and that call happens after every number in the plan is already fixed.")
doc.figure(D + "ta-13-planner.png", "Figure 13 — The Planner: a mixed-integer program, a fallback, and arithmetic",
           "Resolve once, select or schedule, project, flag, narrate. The plan id is a fingerprint of the inputs and "
           "the assumption versions, so the same request returns the same plan rather than a second copy of it.")
doc.h2("9c.1  Resolve")
doc.p("One pass builds a `Candidate` per admissible space, carrying everything the selection needs: the statement and "
      "triple, the horizon, the portfolio distance (which fixes the margin band), the stored bottom-up SOM with its "
      "low and high, the confidence grade, both scores, the competitive band, the capability pool the space would "
      "draw on and that pool's headcount, and the legal entry years with the revenue vector each would produce. "
      "Nothing downstream re-reads the database, so a plan is computed from one consistent view.")
doc.h2("9c.2  Select, or schedule")
doc.p("Under `source: parameters` the problem is a **multi-dimensional knapsack**, expressed as one binary variable "
      "per (space, legal entry year) pair and solved by `scipy.optimize.milp`. The constraints are the ones an "
      "executive would state out loud:")
doc.bullets([
    "Each space enters at most once.",
    "Entry slots per year — how many new spaces the organisation can actually start in one year.",
    "Capability pool load, **per pool per year**: entry effort in a space's entry year, plus sustain effort "
    "proportional to the revenue of everything already live in that pool. This is the constraint that makes shared "
    "build visible; without the per-year decomposition a plan can look affordable in total and be unstaffable in "
    "year two.",
    "Total budget in person-years, concentration caps per vertical and per technology, and a horizon mix within a "
    "stated tolerance.",
])
doc.p("Where scipy is unavailable or the program is infeasible, a **greedy fill** runs instead: rank by objective "
      "density, fill under the hard constraints, and relax the soft constraints in a fixed order — naming each one it "
      "relaxed. Returning a set that quietly ignores a constraint the caller stated would be worse than returning "
      "nothing.")
doc.p("Under `source: workflow` there is no program at all. The set arrives decided by the stage gate, and what "
      "remains is scheduling: `HORIZON_EARLIEST` fixes the earliest year a space may start, `STAGE_ENTRY_FLOOR` pulls "
      "a Packaged or Live space forward to year one regardless of horizon, and a cohort larger than the year's entry "
      "slots cascades into the next year — largest commitments first, so an over-subscribed year defers the smallest "
      "rather than an arbitrary set. `selected_count == considered_count` is asserted by a test.")
doc.h2("9c.3  Project")
doc.p("Arithmetic over stored sizes and configured bands, with no model call anywhere in it. Three operations are "
      "worth naming because each is a correction to a naive sum:")
doc.table(
    ["Operation", "What it does", "The failure it prevents"],
    [["Overlap discount", "A second space in a vertical is discounted; a third sharing its use case more so, "
      "compounding to a floor at three.",
      "SOM is not additive. Obtainable share is computed per topic against the same customers' same budgets, and the "
      "naive sum over all 418 spaces reaches 90% of the segment's entire revenue. Coverage makes it worse rather "
      "than better, which is what proves the problem is the aggregation and not the sizing."],
     ["Margin by distance", "L0 14% … L4 0%, rather than the filed 7.9% applied flat.",
      "The filed margin is fully loaded. Applied flat to incremental revenue it understates L0 (existing offer, "
      "existing overhead) and overstates L3 (a build carried in opex inside the window). The correction moves "
      "five-year profit by about 1.66×."],
     ["Ramp by own entry year", "Share of obtainable market reached in each year AFTER a space's own entry.",
      "It is what makes staggered entry cost something. A space entering in year three is in the first year of its "
      "own ramp, not the third of the plan's."]],
    widths=[3.0, 5.2, 8.4], size=8.5)
doc.p("The band is carried through rather than recomputed: the low and high profit series scale the base series by "
      "`som_low / som_base` and `som_high / som_base`, so the interval on the plan is the interval on the sizes that "
      "produced it. NPV discounts the profit stream at the post-tax rate quoted from Orange's own filed accounts.")
doc.h2("9c.4  Flag, exclude, narrate")
doc.p("`_flags()` says what is not credible rather than returning it with a straight face: a year-five revenue that "
      "is an implausible share of the filed segment revenue, a set more than half concentrated in one vertical or "
      "technology, and any selected space resting on a `modelled` size. Under the workflow source a further set of "
      "flags reports pool over-commitment, since nothing was dropped to prevent it.")
doc.p("`explain_exclusions()` names, per excluded space, the constraint that bound — and under the workflow source it "
      "names a **stage** instead, because nothing there was excluded by the Planner. The narrative prompt splits on "
      "the source for the same reason: prose written for a committed set may not describe alternatives being weighed, "
      "because none were.")
doc.callout("Reproducibility is structural, not a convention", [
    "`PlanInputs.fingerprint()` is a SHA-256 over the canonical JSON of every stated input. The plan id is that "
    "fingerprint plus the plan schema, the economics version, the sizing version and the weight set.",
    "So the same request returns the SAME plan rather than a second copy of it, a plan cannot be silently recomputed "
    "under changed assumptions, and a parameter plan and a workflow plan built from the same portfolio can never "
    "overwrite one another — the source is part of the fingerprint.",
    "A test asserts that identical inputs give an identical plan id.",
], SH_BLUE, BLUE)

# ============================================================ 9d
doc.h1("9d   Pre-sales collateral rendering")
doc.p("Twelve artefacts, five output formats, thirty-three (piece, format) pairs that must all say the same thing. "
      "The architecture exists to make that a property of the code rather than a discipline somebody maintains.")
doc.figure(D + "ta-14-collateral.png", "Figure 14 — Building one piece of pre-sales collateral, in one format",
           "One snapshot, one model call, one block description, one emitter. Everything else is shared.")
doc.h2("9d.1  Describe once, emit many times")
doc.p("`documents.py` and `decks.py` describe a piece as a list of **blocks** — headings, prose, tables, chart "
      "specifications, citations, the missing-input banner. `emitters.py` holds one emitter per format, and each "
      "emitter walks the same blocks. Seven documents by three formats plus four decks by three would otherwise be "
      "thirty-three places for the same battlecard to say something slightly different, and within a month two of "
      "them disagree. Adding a format is one emitter; adding a document is one description.")
doc.table(
    ["Format", "Library", "Charts", "What it is for"],
    [["`pdf`", "reportlab", "Vector, exact geometry", "The format to send. No browser (NFR-05)."],
     ["`pptx`", "python-pptx", "**Native shapes**", "The format to edit. An architect moves a box rather than "
      "redrawing the slide."],
     ["`docx`", "python-docx", "Rasterised at high DPI", "Native styles and tables; Word has no drawing model this "
      "code can target."],
     ["`odt` / `odp`", "odfpy", "Rasterised at high DPI", "The same, for an estate that standardised on LibreOffice."],
     ["`md`", "plain text", "—", "Six emails. Nobody has ever wanted a PDF of them."]],
    widths=[2.0, 2.8, 3.4, 8.4], size=8.5)
doc.p("The raster fallback is the right way round: the format people **send** and the format people **edit** both get "
      "true vector output, and the fallback applies only where a chart is being read rather than worked on.")
doc.h2("9d.2  One snapshot")
doc.p("`context.load()` reads the space once — sizing, competition, description, links, scores, evidence and the "
      "named graph assets — and every renderer works from that reading. Two documents in the same pack quoting "
      "different SAM figures, because one was built before a sizing run and one after, is the failure this makes "
      "impossible rather than merely unlikely.")
doc.h2("9d.3  The live research pass")
doc.p("`research.py` runs targeted queries through the connectors the pipeline already trusts — the same "
      "`HttpSession`, the same throttling, the same robots discipline, content held by reference only (DR-08). It "
      "exists because the corpus is refreshed on a cadence and a battlecard is written the morning of a meeting; a "
      "regulator's deadline or a competitor's announcement lives in that gap. Anything drawn from a retrieved item "
      "names its publisher inline and appears in a list at the back of the document, marked as **not** having been "
      "through the radar's evidence validation.")
doc.p("`RADAR_PRESALES_RESEARCH=0` disables the pass. That switch is needed for CI, for air-gapped builds, and for "
      "any deployment where outbound calls are the thing being prevented.")
doc.h2("9d.4  Storage and staleness")
doc.p("The row key is **(space, kind, format)**, not (space, kind). Somebody who has the battlecard as a PDF and then "
      "asks for Word wants both, and overwriting the first would be a surprising way to answer the second. Each row "
      "records the renderer schema, the space version, and the timestamps of the description and the sizing it was "
      "built from — so staleness is reported per input rather than per space, and a piece built before a section "
      "existed reads as INCOMPLETE rather than merely old.")
doc.p("A piece whose declared inputs are missing **still builds**, with a banner naming the gap. Nothing in this "
      "subsystem refuses to produce a document: an engineer who asked for a solution outline and got an error has "
      "nothing, while one who got the outline with \"built without the written description\" across the top has the "
      "component map, the portfolio path and a clear instruction.")
doc.callout("A defect worth keeping in the record: labels are not bullets", [
    "The model supplies a paragraph where the prompt asked for a name. A commercial-model driver called \"Pricing is "
    "tied to achieving specific outcomes, such as regulatory compliance for a defined product portfolio…\" is one it "
    "actually produced.",
    "A bullet can be given more room when it needs it. A chart label sits under a bar in a slot the geometry fixed, "
    "and there is no outside to move it to — a 10pt label needing 1.25in in a 0.55in box wrapped over the legend and "
    "off the slide.",
    "Truncating is right HERE specifically, against the usual rule of never clipping a label: the full string is "
    "already on the slide as a bullet or in the speaker notes, so an ellipsis says \"there is more of this\" while an "
    "untrimmed label destroys the chart it was meant to annotate. The test now walks EVERY text frame on every "
    "slide, which is what should have been asserted the first time — the earlier test passed while four labels on one "
    "slide were overflowing.",
], SH_GOLD, ORANGE_DARK)

# ============================================================ 10
doc.h1("10   Data architecture")
doc.h2("10.1  Storage choice")
doc.p("SQLite with write-ahead logging. Three reasons, in order of weight:")
doc.bullets([
    "The graph is **thousands of nodes, not millions**. A relational store on one file is the correct size of "
    "solution, and a graph database would add an operational dependency to serve a join that fits in memory.",
    "A single file makes the **historical replay harness** trivial to snapshot: replaying as of a past date is a file "
    "copy plus a reference date, not a restore procedure.",
    "The serving profile is **read-mostly with a single writer**. Discovery is a scheduled batch job; the API writes "
    "only feedback, assessments, stage moves and generated artefacts.",
])
doc.p("The choice is a considered constraint rather than a permanent one. Section 19 records what would force a move "
      "to a server-based store, and the schema contains nothing that would prevent it.")

doc.h2("10.2  Physical data model")
doc.p("Twenty-five tables, presented over five figures by subject area. Crow's-foot notation throughout; the notation "
      "key is on Figure 7.")
doc.figure(D + "ta-07-erd-core.png", "Figure 7 — Physical data model, part 1: discovery, opportunity spaces and scores",
           "The two identity rules at the foot of the figure explain most of the system's refresh behaviour.")
doc.figure(D + "ta-08-erd-graph.png", "Figure 8 — Physical data model, part 2: the Orange Business Graph and link typing",
           "Every link row carries the evidence, the confidence and the curator, because a link nobody can explain is "
           "worse than no link.")
doc.figure(D + "ta-09-erd-outputs.png", "Figure 9 — Physical data model, part 3: market sizing, competition and generated outputs",
           "Reference data sits outside the signal store on purpose. No figure in market_sizes was produced by a language model.")
doc.figure(D + "ta-10-erd-collab.png", "Figure 10 — Physical data model, part 4: collaboration, conviction and feedback",
           "What the organisation contributes, recorded so that it adjusts the ordering of a list and nothing else.")

doc.h2("10.3  Table catalogue")
doc.table(
    ["Table", "Rows", "Purpose", "Retention"],
    [["`raw_items`", "11,353", "Replay archive — the connector payload as returned", "Kept locally; dropped from the "
      "serving package"],
     ["`signals`", "11,354", "Dated, attributable evidence, stored by reference plus a short extract", "Indefinite"],
     ["`clusters`", "325", "Theme clusters, recomputed each refresh", "Current + history"],
     ["`opportunity_spaces`", "418", "The canonical unit; identity is the taxonomy triple", "Indefinite; merged rows "
      "point at their survivor"],
     ["`opportunity_signals`", "11,181", "Evidence attachment, with the refresh that first attached each signal", "Indefinite"],
     ["`scores`", "1,844", "One row per topic per score kind per computation, with components and inputs", "Full history — "
      "this is the trajectory"],
     ["`graph_nodes`", "181", "Offers, references, partners, certifications, analyst positions, capability pools", "Upserted; "
      "disappeared nodes retired"],
     ["`graph_edges`", "182", "Typed, dated, sourced edges between graph nodes", "Rebuilt per refresh"],
     ["`opportunity_links`", "4,832", "Typed links from a topic to a business asset, with evidence and curator", "Indefinite"],
     ["`link_pattern_decisions`", "0", "Curator adjudications, inherited by later occurrences of the same pattern", "Indefinite"],
     ["`refreshes`", "40", "One row per run, with reference date, replay flag and per-stage statistics", "Indefinite"],
     ["`feedback`", "1", "Ratings, comparisons, overrides and engagement, with exposure context", "Indefinite"],
     ["`workflow_state`", "418", "Current stage and owner per topic", "Current"],
     ["`workflow_transitions`", "2", "Full stage history with actor and reason", "Indefinite"],
     ["`assessments`", "9", "Per-role ratings on that role's own axis, superseded rather than deleted", "Indefinite"],
     ["`reference_series`", "5", "Eurostat dataset metadata including its own updated stamp and licence", "Refetched on age"],
     ["`reference_observations`", "56,385", "Statistical values by indicator, industry, geography, size class, period", "Last three periods"],
     ["`market_sizes`", "701", "TAM/SAM/SOM by method, with every factor and its source", "Full history"],
     ["`topic_competition`", "181", "Level plus the named competitor list with its evidence", "Current"],
     ["`topic_descriptions`", "174", "Narrative sections with the signal ids each was written from", "Current per topic version"],
     ["`topic_briefs`", "174", "Generated PDF metadata; the file itself lives on disk", "Current per topic version"],
     ["`internal_signals`", "1", "Bottom-up injection, moderated before it becomes a signal", "Indefinite"],
     ["`competitor_pages`", "1,745", "Crawled competitor pages — URL plus a bounded extract, never a mirror",
      "Replaced on re-crawl"],
     ["`competitor_profiles`", "65", "One profile per competitor, or a recorded reason why there is none",
      "Current per corpus hash"],
     ["`topic_competitor_analysis`", "177", "Per-topic join, plus the written comparison when generated",
      "Current per topic version"],
     ["`plans`", "7", "One portfolio plan: inputs, projection, capacity usage, exclusions, flags, narrative and the "
      "exported PDF's metadata", "Indefinite; immutable once computed"],
     ["`plan_selections`", "294", "One selected space per plan, with entry year, margin band, overlap factor and "
      "capability pool", "Cascades with its plan"],
     ["`topic_collateral`", "15", "One built pre-sales piece per space per FORMAT, with the versions of everything it "
      "printed", "Current per (space, kind, format)"],
     ["`users`", "1", "Who may sign in — a username and a PBKDF2 verifier, never a password", "Indefinite"],
     ["`sessions`", "23", "Live sign-ins, keyed by the SHA-256 of the cookie value", "Expired rows swept on use"]],
    widths=[3.6, 1.5, 7.5, 4.0], size=8)

doc.h2("10.4  Keys, indexes and constraints")
doc.p("Two identity rules do most of the work, and both are enforced by the database rather than by application code.")
doc.h3("10.3b  Migrations")
doc.p("`CREATE TABLE IF NOT EXISTS` leaves an existing table alone, so a column added to the schema never reaches a "
      "database that already exists. `db.MIGRATIONS` is an additive, idempotent list applied on every "
      "`init_schema()` — no rewrite, no data movement — which is what makes it safe to run against the deployed "
      "file, where the feedback, assessments and briefs the pipeline never saw are the entire reason that file is "
      "not simply recreated.")
doc.table(
    ["Table", "Column", "Added for"],
    [["`topic_briefs`", "`brief_schema`", "Distinguishing an INCOMPLETE brief — one missing a section that current "
      "briefs carry — from a merely STALE one. A stale brief was correct when built and has been overtaken; an "
      "incomplete brief never had the section, so waiting does not fix it."],
     ["`plans`", "`pdf_path`, `pdf_bytes`, `pdf_hash`, `pdf_generated_at`, `pdf_schema`",
      "Exporting a plan as a document, added after plans already existed. The hash cache-busts the embedded viewer "
      "when a plan is re-exported; the schema lets an old export be recognised as stale."]],
    widths=[3.0, 3.2, 10.4])

doc.code("-- Syndication collapses to one item: five outlets carrying the same wire\n"
         "-- story cannot inflate publisher diversity.\nCREATE UNIQUE INDEX idx_signals_url\n"
         "    ON signals(url) WHERE url IS NOT NULL;\n\n"
         "-- Canonical identity. A recurring topic is UPDATED, never recreated:\n"
         "-- new signals attach, the score is recomputed, the previous score is kept.\n"
         "CREATE UNIQUE INDEX idx_os_triple\n"
         "    ON opportunity_spaces(vertical, use_case, technology)\n"
         "    WHERE merged_into IS NULL;")
doc.table(
    ["Index", "On", "Serves"],
    [["`idx_raw_source`", "`raw_items(source_id, fetched_at)`", "Replay retrieval by source and date"],
     ["`idx_signals_published`", "`signals(published_at)`", "Trailing-window queries for volume and momentum"],
     ["`idx_signals_cluster`", "`signals(cluster_id)`", "Cluster assembly during synthesis"],
     ["`idx_signals_type`", "`signals(signal_type)`", "Signal-type mix analytics"],
     ["`idx_os_state`", "`opportunity_spaces(state)`", "Lifecycle filtering in the read model"],
     ["`idx_scores_topic`", "`scores(opportunity_id, kind, computed_at)`", "Latest score and score trajectory"],
     ["`idx_nodes_type` / `idx_edges_src` / `idx_edges_dst`", "graph tables", "Link generation traversal"],
     ["`idx_links_topic` / `idx_links_node`", "`opportunity_links`", "Topic assembly and orphan-offer reporting"],
     ["`idx_refobs_lookup`", "`reference_observations(series_id, indicator, nace, geo)`", "Sizing factor lookup"],
     ["`idx_sizes_topic`", "`market_sizes(opportunity_id, method, computed_at)`", "Latest size per method"],
     ["`idx_assessments_topic`", "`assessments(opportunity_id, role, superseded)`", "Live assessments only"],
     ["`idx_transitions_topic`", "`workflow_transitions(opportunity_id, created_at)`", "Stage history and age-in-stage"]],
    widths=[5.0, 6.4, 5.2], size=8.5)
doc.p("Foreign keys are enabled on every connection. Cascading deletes are declared from `opportunity_spaces` onto the "
      "tables that exist only to describe a topic — signals attachment, scores, links, sizes, competition, "
      "descriptions, briefs, workflow state, assessments and feedback — so a topic can be removed without leaving "
      "orphans. `opportunity_links.node_id` deliberately does **not** cascade, which is what forces the retire-rather-"
      "than-delete behaviour described in 8.3.")

doc.h2("10.5  JSON-valued columns")
doc.p("A number of columns hold JSON. This is a deliberate choice with a boundary: JSON is used where the shape is "
      "**evidence about a computation** that is read as a whole and never joined on. Anything that is filtered, "
      "counted or ranked is a real column.")
doc.table(
    ["Column", "Holds", "Read by"],
    [["`scores.components` / `.inputs`", "Per-component value and the raw inputs that produced it", "The score-explanation surface"],
     ["`opportunity_spaces.why_hot`", "Claims, each with the signal ids that support it", "Topic detail and the brief"],
     ["`opportunity_spaces.next_actions`", "One action per role", "The role's own view"],
     ["`opportunity_links.evidence`", "What justified the link", "Link explanation and curator review"],
     ["`market_sizes.factors` / `.coverage` / `.caveats`", "Every factor with source and date; geographies covered "
      "vs requested; the assumptions spelled out", "Market-size panel and the brief"],
     ["`topic_competition.competitors` / `.inputs`", "The named list with basis and mentions; the weights and bands", "Competition panel"],
     ["`topic_descriptions.sections` / `.stripped`", "Narrative sections with their citations; what evidence binding "
      "removed and why", "Description panel and the brief"],
     ["`feedback.exposure_context`", "Rank shown, view, active filters, exploration-slot flag", "Inverse-propensity weighting"],
     ["`signals.attributes`", "Connector-specific extras — procurement codes, tender value, regulatory dates", "Sizing and crosswalks"]],
    widths=[4.4, 7.6, 4.6], size=8.5)
doc.p("JSON is serialised with sorted keys and no ASCII escaping, so a byte-comparison of two rows is a meaningful "
      "reproducibility check.")

doc.h2("10.6  Volumes and growth")
doc.p("The working database is approximately 60 MB, of which the replay archive and the reference observations are "
      "the two largest contributors. Growth is dominated by `signals` and `reference_observations`; both are bounded "
      "by configuration — the collection window per source, and the last three published periods per series. At a "
      "14-day cadence the corpus grows by roughly 1,700 signals per refresh before deduplication. The serving copy "
      "drops `raw_items`, which is about half the file, and every citation still resolves because signals store the "
      "URL and the extract independently of the archive.")

# ============================================================ 11
doc.h1("11   API surface")
doc.p("Sixty-eight endpoints on one FastAPI application. The read endpoints are the product; the write "
      "endpoints exist for curation, collaboration, planning, collateral and on-demand generation. The complete "
      "generated list, with each endpoint's own docstring, is `docs/API.md` — regenerated from the running "
      "application so it cannot drift. The table below is the shape rather than the inventory.")
doc.table(
    ["Method and path", "Purpose"],
    [["`GET /api/meta`", "Vocabularies, weight set, role modes, link-type meanings — everything the frontend needs to render labels"],
     ["`GET /api/view`", "The main read: role-ranked, filtered, faceted, capped at 24 with an exploration slot"],
     ["`GET /api/topics/{id}`", "Full topic assembly — evidence, links, scores, size, competition, description, brief metadata"],
     ["`GET /api/topics/{id}/history`", "Score trajectory, annotated where it crosses a weight-set boundary"],
     ["`GET /api/topics/{id}/evidence-timeline`", "Signal accretion over time — the series momentum is the slope of"],
     ["`GET /api/topics/{id}/market-size`", "Both methods with every factor, source, band and caveat"],
     ["`GET /api/topics/{id}/competition`", "Level plus the named list with per-competitor evidence"],
     ["`GET /api/topics/{id}/description`", "Narrative sections with citations and the stripped list"],
     ["`GET /api/topics/{id}/brief` · `/brief.pdf`", "Brief metadata and the rendered file"],
     ["`GET /api/whitespace`", "High attractiveness with no portfolio path"],
     ["`GET /api/orphan-offers`", "Offers with no live topic — portfolio decay"],
     ["`GET /api/coverage`", "Language, geography and tier coverage across the corpus"],
     ["`GET /api/analytics/grid` · `/summary` · `/market-size`", "Vertical × domain heatmap, KPI row, funnel, size distribution"],
     ["`GET /api/workflow/board` · `/meta`", "Stage board with owners and stalled flags; stage and axis definitions"],
     ["`GET /api/divergence`", "Topics where conviction and the evidence-derived score disagree beyond the threshold"],
     ["`GET /api/graph/node/{id}`", "One business-graph node with its edges and the topics that link to it"],
     ["`GET /api/refreshes`", "Refresh log with per-stage statistics and per-source errors"],
     ["`GET /api/health` · `GET /healthz`", "Liveness plus a schema and corpus summary"],
     ["`POST /api/feedback`", "Rating, comparison, override or engagement, with the exposure context"],
     ["`POST /api/links/decision`", "Curator confirmation or rejection of a link pattern"],
     ["`POST /api/topics/{id}/assessment`", "One role's rating on its own axis, superseding that author's previous one"],
     ["`POST /api/topics/{id}/stage`", "Stage transition with actor, role and reason"],
     ["`POST /api/topics/{id}/description` · `/brief`", "On-demand generation; these are the two endpoints that spend model budget"],
     ["`POST /api/topics/{id}/market-size` · `/competition`", "Recompute from stored data; no model call"],
     ["`POST /api/reference-data/refresh`", "Refetch the Eurostat series when older than the configured age"],
     ["`POST /api/auth/login` · `/logout` · `GET /api/auth/session`", "The only three paths outside the session guard"],
     ["`POST /api/auth/password`", "Change the current account's password; clears the must-change flag"],
     ["`GET /api/topics/{id}/deletion-impact` · `DELETE /api/topics/{id}`", "What a delete would take, then the delete"],
     ["`GET /api/planner/meta`", "What a plan could be built from right now — sized spaces, stage counts, capability "
      "pools, the economics version — so a control can be disabled with a reason"],
     ["`POST /api/planner/plans`", "Build a plan. `source` selects parameters or the committed set"],
     ["`POST /api/planner/plans/{id}/narrative` · `/report`", "The two calls that cost something, kept separate from "
      "the projection, which is already complete"],
     ["`GET /api/planner/plans/{id}/report.pdf`", "The exported plan document"],
     ["`GET /api/topics/{id}/presales`", "The FULL collateral catalogue, built or not, with state per format"],
     ["`POST /api/topics/{id}/presales/{kind}?fmt=`", "Build one piece in one format; formats coexist"],
     ["`GET /api/generate/chat` · `POST /api/generate/chat`", "The scoping conversation. Stateless — the transcript "
      "arrives with every request"]],
    widths=[6.0, 10.6], size=8.5)
doc.p("The built frontend is mounted on the same origin, which is what the CORS list was always scoped for. A "
      "catch-all route serves the single-page application so that deep links resolve on a hard refresh.")

# ============================================================ 12
doc.h1("12   Frontend architecture")
doc.p("React 18 with Vite and TypeScript, and **no chart library**. The radar is hand-drawn SVG because the encoding "
      "is specific to this product: angular sector is the business domain, radial distance is the time horizon with "
      "Now at the centre, marker size is attractiveness and marker colour is right to win.")
doc.table(
    ["Concern", "Approach"],
    [["State", "`App.tsx` owns view state — role, tab, filters, sort, selection, theme, pane widths — and mirrors it "
      "into the URL, so any view is a link"],
     ["Data access", "One typed client module; the API's shapes are mirrored in `types.ts` and nothing is parsed twice"],
     ["Charts", "Each chart picks its colour by the **job the data does**, not by taste: sequential for magnitude, "
      "diverging for polarity with a neutral midpoint, ordinal for a sequence, categorical only where the series "
      "themselves are the subject"],
     ["Colour discipline", "Orange means right to win, so the vertical × domain heatmap uses blue — reusing orange "
      "would imply the same quantity. Status colours are theme-aware tokens named for the judgement they carry"],
     ["Accessibility", "Topic rows are real buttons, so the detail pane is reachable by keyboard from the primary "
      "browsing surface. One polite live region announces long generations with elapsed time. Contrast is computed "
      "against both surfaces of each theme"],
     ["Layout", "Three panes with a real draggable separator — drag, focus and arrow-key, or double-click to reset — "
      "and the width persists. Below 1080px the middle pane takes over the detail pane rather than hiding it"],
     ["Help", "One registry of contextual explanations rather than copy scattered through components, so the "
      "explanation and the behaviour cannot drift apart"],
     ["Screens vs tabs", "The Generate screen and the Planner are SCREENS, not tabs: one writes to the corpus and the "
      "other makes a statement about the whole portfolio, so neither is a way of looking at the current filter. Both "
      "take the address bar the same way a tab does, so a plan is still a link"],
     ["Full screen", "One space with nothing else on screen, in four panes — the space, the competitors, the brief, "
      "the pre-sales pack. That is the order the questions arrive: what is this, who else is here, what do I send, "
      "and what comes after the meeting"],
     ["Embedded documents", "The brief, the plan report and every built PDF render in an `<object>` on the page. "
      "Focus legitimately travels into the viewer, which is why Escape is bound on the document rather than on a "
      "wrapper — a keydown scoped to a div stops working exactly there"],
     ["The scoping conversation", "`BriefChat` holds the whole transcript client-side and posts it with every turn. "
      "There is no session table, nothing to expire, and a reload loses a conversation rather than leaking one"]],
    widths=[3.2, 13.4], size=8.5)
doc.p("Two encoding defects are worth recording because both are easy to reintroduce. Marker area spanned 17.8 to "
      "19.9 pixels and 17 of 26 marks shared one fill, because the scales mapped the nominal 0–100 range while the "
      "scores actually occupy 23–84 and 10–88. Both scales now map the band the data uses, with breaks at the measured "
      "quartiles, and the legend prints them. Separately, the filter rail computed its counts from the 24 topics on "
      "screen, so \"CISO: 0\" meant \"none on this page\" while 37 matched; counts are now server-computed facets over "
      "the whole role-eligible set.")

# ============================================================ 13
doc.h1("13   Configuration architecture")
doc.p("Everything that could reasonably be argued about lives in configuration and is validated when the process "
      "starts. A crosswalk entry pointing at a vocabulary value that does not exist is a startup error, because "
      "crosswalk errors otherwise propagate silently into every downstream number.")
doc.table(
    ["File", "Contents"],
    [["`config/taxonomy/*.yaml`", "15 verticals, 59 use cases, 38 technologies, 6 domains, 9 personas, 6 signal types"],
     ["`config/settings.yaml`", "Weight sets, thresholds, lifecycle, horizon, curation, clustering, enrichment, "
      "workflow, competition, serving, ingestion and model settings"],
     ["`config/strategy.yaml`", "The strategic-relevance rubric, anchored on published Orange ambitions"],
     ["`config/sources.yaml`", "Source catalogue — 25 entries, 19 enabled — each with its connector, tier, cadence, "
      "parameters and terms-of-use position"],
     ["`config/source_tiers.yaml`", "The four-tier scheme, the tier-4 cap and diversity discount, and publisher-level overrides"],
     ["`config/business_graph/*.yaml`", "Offers, references, partners, certifications, capability pools and the 65-entry "
      "competitor register"],
     ["`config/crosswalks/*.csv`", "Procurement code → vertical and use case; vertical → industry classification; "
      "technology → adoption series. Versioned, with a confidence per row"],
     ["`config/sizing.yaml`", "Sizing scope, datasets, contract-value rules, uncertainty bands and share assumptions"],
     ["`config/role_modes.yaml`", "Per-role ranking functions, link-type filters and default filters"],
     ["`config/economics.yaml`", "Everything the Planner turns a market size into money with: margin by portfolio "
      "distance, ramp by horizon, capacity and effort, overlap discounts, and the four figures quoted from Orange's "
      "own filed accounts — discount rate, segment margin, segment revenue and its trend"]],
    widths=[4.4, 12.2], size=8.5)
doc.callout("Changing any weight requires a new weight-set identifier",
            ["Scores across a version boundary are not comparable. Every score records the set that produced it, and "
             "the interface refuses to plot a trajectory across the boundary silently. The same rule extends to "
             "`sizing_version` on every market size, `register_version` on every competitive assessment, and "
             "`economics_version` on every plan — a plan built under one set of bands is not comparable with a plan "
             "built under another, and its id carries the version so the two cannot be confused."],
            SH_RED, RED)

# ============================================================ 14
doc.h1("14   Deployment")
doc.figure(D + "ta-05-deployment.png", "Figure 5 — Deployment topology",
           "Discovery is a local or CI batch job. Deploying is the publish step, not the compute step.")
doc.h2("14.1  Three constraints someone will otherwise rediscover")
doc.bullets([
    "**The Free App Service tier allows one plan per subscription, not per region.** A second plan is created without "
    "complaint and then sits at `QuotaExceeded` forever, in any region; stopping the other application does not "
    "release it, because the allowance is held by the plan. A Free plan does host several applications, so the radar "
    "joins the existing plan and the two share its 60 CPU-minutes a day. A dedicated Basic plan is about USD 13 a month.",
    "**`/home` is the only path that survives a restart or a redeploy** on Linux App Service, so the database and the "
    "generated briefs live in `/home/data`. The startup script seeds it on first boot and then leaves it alone: "
    "feedback, assessments, descriptions and briefs created in production are not thrown away by the next push.",
    "**Secrets are application settings, read from the local environment file at deploy time and never written into "
    "the package.** The environment file itself is excluded from the package and from version control.",
])
doc.h2("14.2  Diagnosing a 403")
doc.p("If the site answers 403 and the portal reports `QuotaExceeded`, check **which** quota before assuming it is "
      "CPU. During this deployment the answer was `WP stop requests: 37 / 15` — an hourly cap on worker restarts, "
      "tripped by repeated deploys while searching for an allowed region, with CPU at 0% of its daily allowance. It "
      "clears on the hour, and redeploying to fix it makes it worse.")
doc.h2("14.3  Region policy")
doc.p("The subscription carries an allowed-regions policy covering Italy North, France Central, Germany West Central, "
      "Poland Central and Spain Central — all in the EU, which suits a product whose strategic frame is sovereignty. "
      "France Central is used.")

# ============================================================ 15
doc.h1("15   Performance")
doc.table(
    ["Path", "Before", "After", "What changed"],
    [["`GET /api/view`", "1.69 s · 343 kB · ~1,670 queries", "**0.05 s · 84 kB · 11 queries**",
      "One bulk fetch per table into a view context; the response drops the fields only the detail page renders"],
     ["`GET /api/workflow/board`", "1.24 s · 2,151 kB", "**0.04 s · 181 kB**",
      "The board was shipping every topic's links, score components and rank explanation to render forty-word cards; "
      "it now sends what a card shows"]],
    widths=[3.4, 4.4, 3.6, 5.2], size=8.5)
doc.p("Pipeline timings, on the reference corpus: collection of twelve sources completes in about 45 seconds, plus up "
      "to eleven minutes when GDELT is rate-limiting — it is the long pole in every refresh. Synthesis dominates the "
      "remainder and scales with the number of clusters times the number of lensed passes. Scoring, linking, sizing "
      "and competition are arithmetic over a small corpus and are not measurable against the model calls.")
doc.p("Two performance regressions are guarded by tests rather than by convention: that the list and detail assembly "
      "paths return byte-identical topics, and that the query count for a view does not grow with the number of "
      "topics. The second is the regression that would make a list feel broken at 150 rows without anyone noticing "
      "the cause.")

# ============================================================ 16
doc.h1("16   Security, privacy and compliance")
doc.h2("16.1  Access control")
doc.p("Until `auth.py` existed the deployed application answered every request it received, on a public hostname, "
      "and everything it serves is internal: competitive analysis of named companies, Orange's own asset graph, "
      "market estimates with the workings attached, and the stage-gate opinions of people who work here. It also "
      "spent the deployed model key for anyone who asked. Both are now behind a session.")
doc.figure(D + "ta-15-access-deletion.png", "Figure 15 — Who may read it, and what a delete takes with it",
           "Two features that were the same gap: the app answered everyone, and a wrong result could only be "
           "retracted by editing the database by hand.")
doc.p("The shape is deliberately the boring one, because the interesting alternatives all cost something this "
      "deployment cannot pay:")
doc.table(
    ["Decision", "Reason", "What was rejected, and why"],
    [["Session cookie, not a bearer token in JavaScript",
      "`HttpOnly`, so a script injected into the page cannot read it. `SameSite=Lax` stands in for a CSRF token: it "
      "stops another origin's form posting to this API with the user's cookie attached, which is the only cross-site "
      "write that matters here.",
      "A token in `localStorage` is readable by definition."],
     ["Sessions in the database, not signed and stateless",
      "The table is tiny and the lookup is a primary-key hit. Revocation is one `DELETE`.",
      "A JWT cannot be revoked without server state, which puts the state back anyway — and the thing an operator "
      "actually wants (\"sign that account out everywhere, now\") is impossible."],
     ["The token is stored as a hash",
      "What is stored is the SHA-256 of the cookie value; the value itself exists only in the browser. The database "
      "is a file on a share, so a copy of it must not be a set of live sessions.",
      "Storing the token itself. The same argument one level up is why passwords are PBKDF2 verifiers."],
     ["PBKDF2-HMAC-SHA256 from the standard library",
      "The best KDF available with **no new dependency**, which is what keeps NFR-05's sovereign-deployment option "
      "cheap. The iteration count follows OWASP's current figure and is stamped into every stored hash, so raising it "
      "later re-hashes each password on its next successful sign-in rather than forcing a reset.",
      "scrypt and argon2 are better KDFs and each adds a dependency to the auth path."],
     ["The guard is an application-level dependency, not a decorator per route",
      "Every `/api` path needs a session except the three under `/api/auth`, so a route cannot be added without "
      "inheriting the guard. `tests/test_api_auth.py` WALKS THE ROUTER rather than naming endpoints, for the same "
      "reason.",
      "A per-route decorator. Its failure mode is the route somebody forgot."]],
    widths=[3.6, 7.2, 5.8], size=8.5)
doc.p("An unknown account and a wrong password give the same message and cost the same time, so the response is not "
      "an account oracle; repeated failures on one account rate-limit and reopen by themselves. The built bundle and "
      "`/healthz` are deliberately open — the login screen has to load before anyone can sign in, and a liveness probe "
      "that answers `401` makes every deployment look unhealthy. An empty user table seeds `orange` / `orange` flagged "
      "`must_change_password`, and the interface warns on every screen until it is cleared. Accounts are managed by "
      "`radar user`, because letting the running application mint logins would turn a session hijack into a permanent "
      "one.")
doc.callout("Still not present, and still required before production", [
    "Per-role authorisation on the write endpoints. Sign-in answers *who*; it does not yet answer *may they*.",
    "Rate limiting on the endpoints that spend model budget — sign-in bounds who can reach them, not how often.",
    "An audit log distinct from the workflow transition history, and a documented key-rotation procedure. The "
    "development key was shared in plaintext and should be rotated regardless, with a separate key issued for CI.",
], SH_RED, RED)
doc.h2("16.2  Data protection")
doc.table(
    ["Concern", "Position"],
    [["Personal data", "No personal data is collected beyond what is strictly necessary. Feedback and assessments "
      "record an author identifier supplied by the caller; no profile, contact detail or behavioural history is stored."],
     ["Source content", "Stored **by reference** — the URL plus an extract capped at 1,200 characters — never as a "
      "mirror of the publication. The raw archive holds the connector's own response payload for replay and is "
      "excluded from the serving package."],
     ["Licence position", "Every source carries an explicit terms-of-use field. Several currently read `pending`, "
      "which is a Sprint 0 action and not an assertion that the terms permit use."],
     ["Attribution", "Every signal carries its publisher, its URL and its publication date, and every claim carries "
      "the signal identifiers behind it."],
     ["Egress to the model provider", "Signal extracts and taxonomy values are sent to the configured provider during "
      "classification, synthesis and description. The provider abstraction supports a locally hosted model, which is "
      "the mitigation if that egress is unacceptable."],
     ["Secrets", "Held as application settings; never in the package, never in version control."]],
    widths=[3.6, 13.0], size=8.5)
doc.h2("16.3  Application security")
doc.bullets([
    "All database access uses parameterised statements; no query is assembled from request input by string concatenation.",
    "Write endpoints validate their payloads through typed request models, and the enumerated fields — role, axis, "
    "stage, verdict, decision — are checked against the same vocabularies the pipeline uses.",
    "Model output never reaches the database unvalidated. The guardrail chain in section 9 runs on every generated "
    "artefact, and closed-vocabulary validation means a model cannot introduce a taxonomy value that does not exist.",
    "The generated PDF is rendered server-side by a library with no browser and no JavaScript engine, which removes an "
    "entire class of HTML-to-PDF exposure.",
    "The static mount serves only the built frontend bundle; the brief endpoint serves a file resolved from a "
    "database row rather than from a path supplied by the caller.",
])
doc.bullets([
    "Passwords are never stored, never logged and never returned. The session cookie is `HttpOnly` and `SameSite=Lax`, "
    "and is marked `Secure` following `x-forwarded-proto` — set explicitly only where the headers are known to be "
    "wrong, because marking it `Secure` over plain HTTP means the browser discards it and nobody can sign in.",
    "A collateral or brief file is served from a path resolved through a database row, never from a path supplied by "
    "the caller, and the delete refuses to touch anything outside the database directory it was given.",
])
doc.h2("16.4  Deleting a space")
doc.p("Thirteen tables point at an opportunity space and the foreign keys already cascade, so the `DELETE` was never "
      "the hard part. `deletion.py` exists to make the delete **legible** — before and after. The dialog asks the "
      "server for the impact and reads it out before showing the button; the result names again what went.")
doc.bullets([
    "**Signals survive.** Only the attachment rows go. A signal is evidence about the world that several spaces may "
    "cite, collected under DR-01 and retained for replay under DR-14; deleting a synthesis result must not delete the "
    "reading it was synthesised from.",
    "**Duplicates folded into this space go with it.** A row with `merged_into` set is a tombstone saying \"this "
    "triple is the same topic as that one\". Clearing the pointer instead would resurrect duplicates against the "
    "identity rule — and `idx_os_triple` would refuse the second one anyway.",
    "**Plans are reported, not blocked.** `plan_selections` cascades, while the plan's stored `projection` and "
    "`selected_count` — computed once and immutable by design — still count the removed space. Refusing the delete "
    "would make any space that ever appeared in a plan permanent; silently breaking the plan would be worse.",
])
doc.callout("Deletion is not suppression", [
    "Identity is the vertical × use case × technology triple (DR-03), so a later refresh that meets the same triple "
    "in the evidence will synthesise the space again — with a new id and none of the history removed here.",
    "Removing a space is a statement about the corpus as it stands, not a permanent veto. Anything that must be "
    "permanent belongs in the taxonomy or the source catalogue.",
], SH_ORANGE, ORANGE_DARK)

# ============================================================ 17
doc.h1("17   Testing strategy")
doc.p("475 tests across twenty-two modules. They cover the invariants that would be expensive to discover late rather "
      "than aiming at a coverage percentage, and the model provider's mock implementation means none of them touches "
      "a network.")
doc.table(
    ["Suite", "What it holds"],
    [["`test_config.py`", "Vocabulary loading, cross-reference validation, crosswalk parsing with per-row confidence"],
     ["`test_connectors.py`", "Date parsing, publisher extraction, geography normalisation, publication-date gating"],
     ["`test_pipeline.py`", "Deduplication, syndication collapse, relevance gating, cluster assembly"],
     ["`test_scoring.py`", "Component decomposition, reproducibility, tier-4 discounting on the effective count, "
      "vendor-only evidence scoring low, horizon derivation, the lifecycle state machine, evidence-gap warnings"],
     ["`test_enrich.py`", "Similarity plus corroboration; similarity alone must not attach"],
     ["`test_sizing.py`", "Shared size base, main-object eligibility, proxy widening without base movement, "
      "worst-basis confidence, SAM never exceeding TAM"],
     ["`test_competition.py`", "Match weighting, evidenced doubling, banding over listed competitors only"],
     ["`test_describe.py`", "Uncited sections stripped, generated figures killing their section, unsupplied "
      "organisations rejected, a diagram box unable to claim an Orange asset the graph does not hold"],
     ["`test_readmodel.py`", "Role filtering, ranking, facet counts over the whole eligible set, exploration slot "
      "drawing from role-eligible topics, list and detail parity, query count independent of topic count"],
     ["`test_workflow.py`", "Stage transitions, ownership, age-in-stage, assessment supersession, conviction "
      "aggregation, divergence threshold"],
     ["`test_planner.py`", "Identical inputs give an identical plan id; a capability pool is never over-committed "
      "under the optimiser and IS reported when the committed set over-commits it; horizon fixes the earliest entry "
      "year and a stage pulls it forward; `selected_count == considered_count` under the workflow source; a committed "
      "space with no size is declared rather than dropped"],
     ["`test_api_planner.py`", "Both sources over the HTTP surface, the immutability of a stored plan, and the two "
      "failure messages — each phrased in the terms of the mode that produced it"],
     ["`test_presales.py`", "Every text frame on every generated slide fits its box; a piece builds with its inputs "
      "missing and says so; the palette rule that orange is never a competitor's colour"],
     ["`test_api_presales.py`", "The catalogue is returned whole whether or not anything is built; a second format "
      "coexists with the first; an unsupported format is a 400 naming the alternatives"],
     ["`test_auth.py` + `test_api_auth.py`", "Verifier round-trip and iteration upgrade on sign-in; identical answers "
      "for an unknown account and a wrong password. The API suite WALKS THE ROUTER rather than naming endpoints, so a "
      "route added without the guard fails the test that exists for exactly that"],
     ["`test_scoping.py`", "`ready` is the corpus's verdict rather than the model's; a brief corroborated only on its "
      "vertical is refused; the transcript is re-retrieved per turn"],
     ["`test_deletion.py`", "Signals survive and attachments do not; a folded duplicate leaves with its survivor; a "
      "plan that selected the space is named rather than blocking the delete; a path outside the database directory "
      "is refused"]],
    widths=[3.4, 13.2], size=8.5)
doc.p("Four defects found by these tests are worth recording, because each was a real failure rather than a style "
      "preference: the scale-invariant entropy discount described in 6.1; certifications typed L0, which made "
      "portfolio distance meaningless for every topic in a regulated vertical; a graph rebuild that truncated a table "
      "another table held a foreign key onto; and an exploration slot drawing from all filtered topics rather than "
      "role-eligible ones, which could show a salesperson a topic with no proof point and thereby bypass the very "
      "filter the role mode exists to enforce.")

# ============================================================ 18
doc.h1("18   Observability and operations")
doc.table(
    ["Signal", "Where it is"],
    [["Per-refresh statistics", "`refreshes.stats` — counts per stage, per-source item counts, and the hosts that "
      "tripped the circuit breaker"],
     ["Per-source errors", "`collect.errors` inside the refresh statistics, named by host"],
     ["Generation accounting", "Candidate counts at each guardrail gate; what the description cap left ungenerated"],
     ["Corpus health", "The coverage endpoint — language, geography and tier distribution"],
     ["Curation backlog", "Unconfirmed link count; currently 173 links await a named curator"],
     ["Workflow health", "Age-in-stage per topic, with cards stalled beyond 30 days flagged"],
     ["Liveness", "`GET /healthz` and `GET /api/health`, the latter returning a schema and corpus summary"],
     ["Request logging", "gunicorn access and error logs to stdout, collected by the platform"]],
    widths=[4.4, 12.2], size=8.5)
doc.p("**Operational runbook, in short.** Discovery is a scheduled batch job run locally or from CI against the same "
      "database file; publishing is a separate step. A failed refresh is safe to re-run — stages are idempotent "
      "against the canonical identity rules, and a repeated signal collapses on its URL. A partial refresh is "
      "diagnosed from the refresh row, not from the logs.")

# ============================================================ 19
doc.h1("19   Risks and technical debt")
doc.table(
    ["Risk", "Impact", "Current mitigation", "What would resolve it"],
    [["No authentication on the deployed instance", "High — internal material and model spend exposed",
      "Demonstration scope only", "IP restriction or Entra sign-in; rate limits on the generation endpoints"],
     ["SQLite single writer", "Medium — concurrent writes serialise", "Read-mostly profile; one worker with threads",
      "Move to a server-based store if concurrent curation becomes real. Nothing in the schema prevents it"],
     ["173 unconfirmed links", "Medium — quality drifts without a named adjudicator",
      "Confidence and evidence recorded on every link; unconfirmed links are visible as such",
      "A named curator, which is an open question rather than an engineering task"],
     ["Placeholder owners on sizing and competitor assumptions", "Medium — both appear in front of customers",
      "The assumptions are printed in the brief rather than hidden", "Named owners for `sizing.yaml` and the competitor register"],
     ["Six catalogued sources not wired", "Low — a known coverage gap",
      "Catalogued with the reason; coverage reported rather than assumed", "Registration where required; a rewritten "
      "connector where the feed path changed"],
     ["Model provider dependency", "Medium — sovereignty and cost", "Provider abstraction with a local implementation",
      "Exercise the local model path in a real refresh and measure the quality difference"],
     ["Prompt versioning is manual", "Low — a regression could be hard to attribute",
      "`prompt_version` stamped on every generated row", "Prompt assets in version control with a computed hash"],
     ["No backtest metrics", "Low for the MVP", "The replay path exists and is tested",
      "Implement the forecasting-quality metrics that consume it"],
     ["12 competitors unprofiled", "Medium — thins the competitive picture on security spaces in particular",
      "Each is recorded with its reason and named in the Coverage view; per-topic counts show how much of a field "
      "was readable", "A decision on the user agent (six sites), and a headless renderer for the three that are "
      "client-side only"],
     ["Competitor profiles go stale silently", "Low — sites change slowly",
      "`corpus_hash` detects a moved page set; profiles carry their register and prompt versions",
      "A scheduled re-crawl on the same cadence discipline as the reference data"],
     ["237 spaces have no competitive assessment", "Medium — their competitor tab is empty",
      "The interface says so explicitly and offers to compute it inline",
      "`radar competition` across all spaces; arithmetic, no model calls"]],
    widths=[3.8, 3.2, 5.0, 4.6], size=8)

# ============================================================ 20
doc.h1("20   Appendix A — module reference")
doc.p("Command-line entry points, for orientation:")
doc.code("radar check                              # validate config, print vocabulary sizes\n"
         "radar refresh --since-days 60            # full pipeline\n"
         "radar refresh --stages collect,classify  # any subset of the thirteen stages\n"
         "radar serve                              # FastAPI read API on 127.0.0.1:8000\n"
         "radar topics --role sales                # role-ranked topic list\n"
         "radar show OS012                         # full decomposition of one topic\n"
         "radar whitespace                         # high attractiveness, no portfolio path\n"
         "radar orphan-offers                      # offers with no live topic\n"
         "radar coverage                           # language / geography / tier coverage\n"
         "radar replay --date 2024-06-01           # historical replay with leakage controls\n"
         "radar confirm-link <pattern> --decision confirmed --curator <id>\n"
         "radar reference-data                     # fetch the Eurostat denominators\n"
         "radar size                               # market size per topic, both methods\n"
         "radar competition                        # competitive intensity per topic\n"
         "radar describe --limit 40                # long-form descriptions\n"
         "radar brief OS012 --open                 # render the sales/presales PDF\n"
         "\n"
         "radar plan --narrate --pdf               # five-year portfolio plan, prose and one PDF\n"
         "radar plan --source workflow --from-stage demand_tested   # plan the committed set\n"
         "radar plans                              # stored plans with their headline figures\n"
         "radar user list | add | passwd | remove | signout          # accounts and sessions\n"
         "radar delete-space OS123                 # prints the impact, then asks")
doc.p("Two commands have no CLI equivalent on purpose. **Pre-sales collateral** is built through the API only, "
      "because every piece is bound to a snapshot of the space and the format is a choice a reader makes at the "
      "moment of asking; a batch that pre-built all twelve in all their formats would produce sixty files, most of "
      "them stale before anyone opened one. And **accounts cannot be created by the running application** — `radar "
      "user` is the only route in, so a hijacked session cannot mint itself a permanent login.")
doc.p("Environment variables are read from a local `.env` file, which is excluded from version control and from the "
      "deployment package. The provider is selected by `RADAR_LLM_PROVIDER`; the corresponding key and the contact "
      "address used in the ingestion user agent are the only other required values.")

doc.save(str(HERE / "Orange_Innovation_Radar_Technical_Architecture.docx"))
