# Operations runbook

*How to run the pipeline, in what order, and what to do when a stage misbehaves.*

---

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env                 # then fill in the provider key
PYTHONPATH=src python3 -m radar.cli check
```

`check` validates every configuration file and cross-reference and prints the
vocabulary sizes. **A dangling identifier is a startup error, not a runtime
surprise** — that is the whole point of running it first.

The `radar` entry point is installed by `pip install -e .`; every example below
also works as `PYTHONPATH=src python3 -m radar.cli …`.

---

## The order things run in

Stages are independent and each reads what its predecessor wrote to the
database, so any subset can be re-run alone. That is how the system is
developed, tested and repaired.

```
radar refresh --since-days 60
```

runs all thirteen stages. The pieces, in dependency order:

| # | Stage | Needs | Model? | Notes |
|---|---|---|---|---|
| 1 | `collect` | network | no | Parallel, 8 hosts at a time |
| 2 | `normalise` | 1 | no | URL dedup is a read-modify-write, so writes stay serial |
| 3 | `classify` | 2 | **yes** | Batched 12 per request, temperature 0 |
| 4 | `themes` | 3 | no | Deterministic clustering — no randomised init (SC-11) |
| 5 | `synthesise` | 4 | **yes** | 3 lensed passes per cluster, 4 clusters concurrent |
| 5b | `enrich` | 5 | no | Embeddings + taxonomy corroboration |
| 6 | `graph` | config | no | Rebuilds the business graph from YAML |
| 6b | `link` | 5, 6 | no | Typing and portfolio distance — no model at all |
| 6c | `score` | 6b | **yes** | One rubric call per topic; the rest is arithmetic |
| 6d | `actions` | 6c | **yes** | One call per topic |
| 6e | `reference` | network | no | Eurostat; annual data, refetched on age |
| 6f | `size` | 6e | no | No model anywhere on this path |
| 6g | `competition` | register | no | Arithmetic over the competitor register |
| 7 | `describe` | 6f, 6g | **yes** | Capped at 40 per refresh |

Subsets:

```bash
radar refresh --stages collect,classify
radar refresh --stages score,actions
radar refresh --stages size,competition --no-llm
```

### Competitor intelligence

Runs on its own cadence, not inside `refresh` — the sites change slowly and the
crawl is slow.

```bash
radar competitor-scrape                    # ~15-20 min, robots-aware
radar competitor-profile                   # 1 model call per competitor
radar competitor-analysis --no-llm         # the join, free, every topic
radar competitor-analysis --limit 40       # comparisons, capped
```

`--force` on either of the last two rebuilds even when nothing moved. Both skip
work that is still current: profiles compare a `corpus_hash`, analyses compare
the topic version, the prompt version and the register version.

### Outputs

```bash
radar describe --limit 40
radar brief OS012 --open
radar brief --all
```

---

## Planning

The Planner is not a pipeline stage. It reads what the pipeline produced and
answers a different question: not which topic, but which **set**.

```bash
# Parameters — the optimiser chooses, under constraints you state
radar plan --budget 40 --slots 6 --min-confidence partial --max-distance 2 \
           --objective profit --narrate --pdf

# The committed set — the stage gate already chose; this only schedules and costs it
radar plan --source workflow --from-stage demand_tested --narrate --pdf

radar plans                       # stored plans with their headline figures
```

`--narrate` and `--pdf` are separate flags because only the first spends a model
call. The projection itself is arithmetic and is complete the moment the plan is
created.

**A plan id is a fingerprint of its inputs** plus `economics_version`,
`sizing_version`, `weight_set` and the plan schema. Running the same command
twice returns the same plan rather than a second copy of it, and a parameter plan
can never quietly overwrite the workflow plan it was built to be compared
against.

> **Two failure messages, and they mean different things.** *"No opportunity
> space survived the stated constraints"* means loosen something — the confidence
> floor, the distance cap, the exclusions. *"No opportunity space has reached
> Demand-tested"* means the workflow board is empty, and no constraint you can
> reach from the command line will change that; move a card forward, or plan from
> parameters instead.

Changing any band in `config/economics.yaml` requires a new `economics_version`.
Projections across a version boundary are not comparable, and every plan records
the version that produced it.

---

## Pre-sales collateral

Twelve artefacts per space. There is **no CLI command** — collateral is built
through the API, from the fourth tab of a space's full-screen view, because every
piece is bound to a snapshot of the space and the format is a choice the reader
makes at the moment of asking. A batch that pre-built all twelve in all their
formats would produce sixty files, most of them stale before anyone opened one.

```bash
# What exists for a space, built or not, with staleness per format
curl -b cookies.txt localhost:8000/api/topics/OS021/presales

# Build one piece; ?fmt= picks the format, ?force=true rebuilds a current one
curl -b cookies.txt -X POST 'localhost:8000/api/topics/OS021/presales/battlecards?fmt=docx'
```

Formats coexist — asking for Word after you have the PDF gives you both. An
unsupported format is a `400` naming the alternatives, never a silent fallback.

Set `RADAR_PRESALES_RESEARCH=0` to disable the live research pass. Needed for CI,
for air-gapped builds, and for any deployment where outbound calls are the thing
being prevented.

---

## Accounts

```bash
radar user list                  # who exists, who is still on the shipped password
radar user add jo                # prompts twice
radar user passwd orange         # also ends every session that account holds
radar user signout jo            # end that account's sessions, keep the account
radar user remove jo
```

An empty database seeds `orange` / `orange`, flagged **must change password**;
the interface warns on every screen until it is cleared. Accounts cannot be
created from the running application — this is the only route in, so a hijacked
session cannot mint itself a permanent login.

---

## Removing an opportunity space

```bash
radar delete-space OS123          # prints the impact, then asks
radar delete-space OS123 --yes    # skips the prompt
```

The same impact report the interface reads out before showing its button.
**Signals survive** — only the attachment rows go, because a signal is evidence
several spaces may cite. **Duplicates folded into this space go with it.** **A
plan that selected the space is named, not blocked** — its stored projection was
computed once and is immutable by design.

> **Deletion is not suppression.** Identity is the vertical × use case ×
> technology triple, so a later refresh that meets the same triple in the
> evidence will synthesise the space again, with a new id. Removing a space is a
> statement about the corpus as it stands, not a permanent veto.

---

## Serving

```bash
radar serve                                # 127.0.0.1:8000
npm --prefix frontend run dev              # 5173, proxying to 8000
```

For production the API also serves the built bundle from the same origin:

```bash
npm --prefix frontend run build
radar serve --host 0.0.0.0 --port 8000
```

**Signing in.** Every `/api` path needs a session except the three under
`/api/auth`. The first start of an empty database seeds `orange` / `orange`. From
a script:

```bash
curl -c cookies.txt -X POST localhost:8000/api/auth/login \
     -H 'Content-Type: application/json' \
     -d '{"username":"orange","password":"orange"}'
curl -b cookies.txt localhost:8000/api/meta          # now answers 200
```

`/healthz` and the built bundle stay open deliberately: the login screen has to
load before anyone can sign in, and a liveness probe that answers `401` makes
every deployment look unhealthy.

> **A `401` from `/api/auth/login` is deliberately ambiguous.** An unknown
> account and a wrong password give the same message and cost the same time, so
> the response cannot be used to enumerate accounts. Repeated failures on one
> account rate-limit to `429` and reopen by themselves.

> **The failure you will hit at least once.** `radar serve` does not reload. If
> you add an endpoint and the frontend calls it, the running server answers
> `200 text/html` (the app shell, via the SPA catch-all) rather than 404. The
> frontend detects this and says *"the running server is older than the bundle
> it is serving"* — restart it, or use `--reload` while developing.

---

## Inspecting without the UI

```bash
radar topics --role sales --limit 20
radar show OS012                    # full decomposition: claims, links, score inputs
radar whitespace                    # high attractiveness, no portfolio path
radar orphan-offers                 # offers with no live topic
radar coverage                      # language / geography / tier / competitor coverage
```

---

## Curation

```bash
radar confirm-link "offer:live_objects|use_case:asset_tracking" \
      --decision confirmed --curator alice
radar internal add --author bob --kind customer_conversation \
      --title "Airport asked about counter-drone" --vertical transport_logistics
radar internal pending
radar internal moderate INT-0001
radar internal promote
```

Internal signals are **inert until moderated**. External evidence arrives with a
publisher and a date a reviewer can check; an internal note arrives with neither,
so the moderation step is what keeps NFR-02 true for a class of evidence whose
attribution is a colleague rather than a publication. They enter at **tier 3**.

---

## Replay

```bash
radar replay --date 2024-06-01 --since-days 90
```

Every connector rejects anything published after the reference date, filtering on
the **publication** date and never the ingestion date. `raw_items` is retained so
a replay needs no re-fetch.

---

## Troubleshooting

### A source returned nothing

Check the refresh row first, not the logs:

```bash
radar coverage
sqlite3 data/radar.db "select id, stats from refreshes order by started_at desc limit 1"
```

`stats.collect.errors` names the hosts that failed and the ones whose circuit
breaker tripped. A failing source is recorded and never aborts the run.

**The circuit breaker is deliberately twitchy** — two exhausted requests to a
host and the rest of that host's requests are skipped, because ten blocked GDELT
queries otherwise cost eleven minutes for zero data. For a rarely-run job like
the competitor crawl that is too aggressive; raise `failure_budget` and
`min_interval` and re-run the affected ids.

### A model call failed on invalid JSON

Almost always truncation, not malformed output — the response hit the completion
budget mid-string. The symptom is `Unterminated string starting at:` and the loss
of the whole artefact rather than its tail. Raise `max_tokens` on that call site.
Both the profile call (6000) and the analysis call (8000) were raised for exactly
this reason after failing on the largest inputs.

### The competitor tab is empty

Three different causes, and the interface distinguishes them:

| What you see | Cause | Fix |
|---|---|---|
| "could not be loaded" + an error | The request failed | Usually a stale server — restart it |
| "Competitive intensity has not been computed" | No `topic_competition` row | Press the button, or `radar competition --topics OS123` |
| "No competitor from the register is matched" | Assessed, matched nobody | A statement about the register, not a bug |

### A brief is marked incomplete

It was rendered before a section that current briefs carry existed. That is
different from **stale**, which means it was correct when built and has been
overtaken. Only a rebuild fixes incomplete:

```bash
radar brief OS012          # or the Regenerate button in the Brief tab
```

### A plan will not build

Read which message it is. *"No opportunity space survived the stated
constraints"* is a parameter problem — loosen the confidence floor, the distance
cap or the exclusions. *"No opportunity space has reached Demand-tested"* is a
workflow problem, and nothing on the command line fixes it. *"N spaces have
reached Demand-tested but none has a bottom-up market size"* means run `radar
size` first: the plan is arithmetic over those sizes, and there is nothing to do
arithmetic on.

If a plan builds but the capability figures look impossible, check
`pool_availability` — it is the share of headcount free for **new** work, and the
default is deliberately conservative.

### A pre-sales piece built with a banner across the top

That is the design, not a failure. A piece whose declared inputs are missing
still builds, with the gap named — an engineer who asked for a solution outline
and got an error has nothing, while one who got the outline marked *"built
without the written description"* has the component map, the portfolio path and a
clear instruction. Generate the missing input (`radar describe`, `radar size`,
`radar competition`) and rebuild with `?force=true`.

### Everything answers 401

The session expired, or the cookie was not sent. Sessions refresh on use up to
the idle window and cannot outlive the ceiling however often they are used. If
sign-in appears to succeed and the next request still answers `401`, the cookie
is being discarded — check `RADAR_COOKIE_SECURE`. Marking the cookie `Secure`
over plain HTTP means the browser drops it and nobody can sign in; unset, it
follows the scheme the browser used, reading `x-forwarded-proto` first because
App Service terminates TLS at the front end.

### Scores look wrong after a config change

Changing any weight requires a **new `weight_set` id**. Scores across a version
boundary are not comparable, every score records the set that produced it, and
the interface refuses to plot a trajectory across the boundary silently.

---

## Regenerating the documentation

```bash
# diagrams (matplotlib, no external tooling)
python3 docs/build_diagrams.py

# API and data-model references, generated from the running code
python3 docs/build_reference.py

# the two design documents, which embed the diagrams
python3 docs/build_docs.py

# the screenshots both decks put on their slides — needs the app running
python3 docs/build_shots.py

# the decks
python3 docs/build_deck.py                 # Orange_Innovation_Radar.pptx
python3 docs/build_walkthrough_deck.py     # ..._Walkthrough.pptx

# the narrated films — these need the app running on :8000 and :5173
python3 docs/build_video.py                # the concept film
python3 docs/build_demo.py                 # the narrated product demo
```

The references are regenerated from the code and the live schema, so they cannot
drift. The narrative documents are hand-written in `docs/_build/*_content.py` and
need judgement to update — `build_docs.py` only assembles them.

**The two film builds drive a real browser against the running application.**
Nothing in either is mocked, and the demo runs the browser **headed** rather than
headless — a headless Chromium will not display an embedded PDF, and half of what
the demo shows is a document rendered on the page. Do not "fix" that back to
headless.

---

## Deployment

```bash
./scripts/deploy-azure.sh
```

Three constraints that will otherwise be rediscovered:

* **The Free App Service tier allows one plan per subscription, not per region.**
  A second plan is created without complaint and then sits at `QuotaExceeded`
  forever, in any region.
* **`/home` is the only path that survives a redeploy**, and it is an SMB mount.
  SQLite's WAL needs shared memory SMB cannot provide, so the seeded database is
  converted to `DELETE` journal mode once at boot.
* **A crash loop destroys its own evidence.** Fifteen restarts exhaust the plan's
  quota, which disables the log endpoints that would explain the first failure.
  `startup.sh` therefore never uses `set -e`, tees its output to `/home/LogFiles`,
  and falls back to a diagnostic server rather than exiting.

Before anything real: the deployed app is **public and unauthenticated**, and the
two generation endpoints spend the deployed model key. See the Technical
Architecture, section 16.
