# Implementation guide

## How the requirements are met

### Evidence before generation (§4.1)

The model never invents an opportunity space from its own knowledge. Four
hallucination defences, in the document's order of effectiveness (§4.4.4):

1. **Evidence binding** — every claim cites signal ids, validated to exist _in
   the cluster that produced the candidate_. Uncited claims are **stripped, not
   rewritten**.
2. **Closed-vocabulary output** — taxonomy values validated against the
   enumerations; a recognised synonym is repaired once, anything else is dropped.
3. **No model-generated numbers** — enforced in every system prompt and
   backstopped by a regex over generated claims.
4. **Entailment check** — a cheap second pass verifies each "why hot" claim is
   entailed by its cited span.

Plus an **adversarial critic pass** with a different system prompt (§4.4.3),
which in the live run rejected 119 of 254 candidates with specific reasons.

### Prolonged brainstorming, made systematic (§4.4.3)

All three mechanisms the document asks for are implemented:

- **Coverage-driven prompting.** The pipeline computes which taxonomy cells have
  evidence but no candidate yet and targets generation at exactly those. "This
  converts brainstorming from 'produce more ideas' into 'cover the evidenced
  grid', which terminates and is measurable."
- **Diversity by construction.** Each cluster is passed over
  `candidates_per_cluster` times at temperature 0.85, and each pass is given a
  different **evidence lens** — regulatory, procurement, technology-maturity,
  cross-vertical. §4.4.3 warns that an open-ended loop "elaborates around
  whatever it produced first", so passes need different starting points to
  explore rather than paraphrase. Passes and clusters both run concurrently.
- **Adversarial critique.** A separate critic prompt scores 1–5 as the _minimum_
  across five tests, so one failure caps the whole score.

The funnel over 27 clusters, live:

```
254 raw candidates          (27 clusters × 3 lensed passes)
  6 failed closed vocabulary
  7 failed evidence binding
119 failed the critic
 15 claims stripped by the entailment check
 62 merged as duplicates    ← multi-pass overlap, caught by triple + embedding
 60 accepted
```

That is a 24% yield, close to the document's "generate forty candidates and keep
eight". The 62 merges are the cost of over-producing and are exactly what the
canonical-triple identity rule (§4.4.5) exists to absorb.

### Two scores, never one (SC-12)

Attractiveness and right-to-win travel as separate fields end to end. In the UI
they occupy two different visual channels (marker size and marker colour) and
are never combined into a displayed number.

### Role modes fall out of the data (§4.5.3, FR-31)

Sales sees L0–L1, presales L0–L2, strategy L1–L4. The sales acceptance criterion
("only topics with enough internal content to credibly back up") has a
**computable** definition: a delivery link at L0/L1 **and** a published reference
in the vertical **and** no evidence gap.

**One deliberate extension beyond Table 26.** Every L0–L4 definition describes a
_delivery_ capability. A certification, an analyst position, a published
reference and a capability pool are none of those — they are right-to-win
evidence. Typing them L0 would mean any topic in a regulated vertical scored as
a direct sell purely because Orange holds ISO 27001, which makes portfolio
distance meaningless. They are therefore typed `SUP` (supporting evidence):
linked, displayed and scored, but excluded from portfolio distance and from the
role-mode filter. See `graph.SUPPORTING`. **This is a design decision worth
confirming with the client.**

### Explainability (NFR-01, NFR-02, NFR-03)

Every score component stores the inputs that produced it (DR-05), so any number
is reproducible. Every artefact records pipeline, prompt and model version
(DR-10). Every link records its type, confidence, the evidence that justified it
and the confirming curator (DR-13). The topic detail view shows the breakdown
expanded rather than behind a tooltip, per §4.9.

### Evidence enrichment (§4.4.5)

Synthesis only attaches a signal to a topic when the model happens to cite it.
That left a gap: a topic created six weeks ago stayed frozen at the evidence it
was born with, even when a later refresh ingested signals that plainly belonged
to it. Thin evidence is not cosmetic — it suppresses a topic through the whole
chain, because signal volume, publisher diversity, momentum and the promotion
thresholds all count attached signals.

The `enrich` stage closes that gap, and does so as retrieval plus rules rather
than generation: embedding similarity **plus** an independent taxonomy
corroboration (a vocabulary term in the signal text, or a CPV crosswalk hit).
Similarity alone is refused, because embeddings happily rate two unrelated
security items as close and unchecked attachment would inflate exactly the
components that depend on the count. Enrichment never writes a claim — only
synthesis may do that, and only with citations.

### Collaboration workflow and team conviction (FR-25, §4.10)

§4.10 recommends "A + B + D, with C as a fast follower". Models A and C are
implemented, because they are the two that touch scoring.

**Model A — the stage gate.** Shortlisted → Demand-tested → Packaged → Live,
with ownership following the stage (strategist → sales → presales). §4.10's
named weakness is latency — "a topic can die waiting for a stage owner" — so
age-in-stage is computed and stalled cards are flagged rather than left for
someone to notice. Every transition records who moved it and why.

**Model C — distributed assessment.** Each role rates **only its own axis**:

| Role       | Axis            | Because                                       |
| ---------- | --------------- | --------------------------------------------- |
| Strategist | Strategic fit   | Owns where investment goes                    |
| Sales      | Customer demand | Authoritative on whether customers are asking |
| Presales   | Deliverability  | Knows what it would actually take to build    |

Ratings are 0–5 with **written anchors** per level, plus a separate confidence,
rather than a slider. §4.7.4: "People are unreliable at rating a topic 73 out of
100." Ratings are confidence-weighted, and a changed mind supersedes rather than
duplicates — the earlier opinion is kept, because a changed mind is itself a
label.

**How this affects scoring, and the line it does not cross.** Conviction is a
**third quantity**, never folded into either published score:

```
attractiveness   is the world moving          (external evidence)
right to win     can we play, can we win      (internal assets)
conviction       do our own people believe it (internal judgement)
```

SC-14 says internal data "adjusts but does not replace external discovery" and
SC-12 forbids collapsing scores, so conviction enters only the per-role
**ranking** function — which already exists to order a list and is never
displayed as a score. Every published number stays reproducible from evidence
alone. An unrated topic sits **neutral**, not last: treating "nobody has looked
yet" as "everybody hates it" would be a popularity bias, not a judgement.

**Divergence is the product.** §4.10: "disagreement becomes information rather
than friction." Where team conviction and the evidence-derived score disagree by
more than the configured threshold, the topic enters a review queue with a
written reading of what the gap might mean — either the radar is missing signal,
or enthusiasm is running ahead of it. It is flagged, never averaged away.

### Explaining a score, per topic

NFR-03 asks that "a reviewer outside the project can reconstruct why any topic
holds its rank", and DR-05 stores every component alongside the inputs used to
compute it precisely so that is possible. Every topic therefore carries a **How
was this calculated?** modal that shows the stored inputs and the arithmetic —
the weight table, the weighted total, and per component the actual evidence:
publisher entropy and the publishers counted, the tier distribution, the
per-period signal buckets the momentum slope was fitted to, the rubric level and
its rationale, the named offers and references behind right-to-win.

It is reachable from the topic detail, from every list row, and from the workflow
board, and it deep-links: `?explain=OS021`.

The same surface carries the reproducibility stamps — weight set, pipeline,
prompt and model version — because a number you cannot re-derive is not
explained, only displayed.

### Contextual help

Every dense concept in the interface has a `?` that opens an explanation of what
it is, why it works that way, and which requirement it comes from: portfolio
distance, conviction, divergence, evidence gap, source tiers, horizons, the
lifecycle, the exploration slot, weight sets. Content lives in one registry
(`frontend/src/help.ts`) rather than scattered through components. The dialogs
are real dialogs — Escape and backdrop close them, focus moves in and returns to
the trigger.

### Charts

Every chart picks its colour by the **job the data does**, not by taste, and all
palette values are taken verbatim from the reference instance in its documented
slot order — the order is the colourblind-safety mechanism, so nothing is
re-stepped or re-ordered.

| Chart                     | Data's job                            | Encoding                                                                                                                                    |
| ------------------------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Radar (polar)             | four dimensions at once               | position + area + sequential hue                                                                                                            |
| Vertical × domain heatmap | magnitude on a grid                   | sequential, **blue** — orange already means right-to-win, and reusing it would imply the same quantity                                      |
| Conviction vs evidence    | polarity                              | **diverging**, two poles + a neutral grey midpoint, so agreement reads as nothing                                                           |
| Stage funnel              | position in a sequence                | ordinal ramp — the reader sees the order in the colour                                                                                      |
| Portfolio distance        | ordered buckets                       | ordinal ramp                                                                                                                                |
| Evidence over time        | change over time                      | single hue; this is the series momentum is the slope _of_                                                                                   |
| Signal-type mix           | identity — the series ARE the subject | the only categorical chart, ≤6 slots, with a legend **and** a table view (three light-mode slots sit below 3:1, so the relief rule applies) |
| KPI row                   | headline numbers                      | no chart at all                                                                                                                             |

### Market size, with the working shown (§4.3.4)

§4.3.4 is a warning before it is a requirement:

> the headline market-size figures circulating in press coverage almost always
> originate from paid research houses, are quoted without methodology, and
> frequently conflict by an order of magnitude. The radar should prefer a
> transparent bottom-up estimate — enterprise count in the vertical × adoption
> rate × plausible contract value — and show its working.

So every space carries a size that is **computed, never quoted**, by two
independent methods that are published side by side:

| Method               | What it is                                       | Where each factor comes from                                                            |
| -------------------- | ------------------------------------------------ | --------------------------------------------------------------------------------------- |
| **Bottom-up**        | enterprises × adoption × annual engagement value | Eurostat SBS (`sbs_sc_ovw`), Eurostat enterprise ICT survey, median matching TED tender |
| **Observed tenders** | contracts that actually exist, annualised        | TED notices whose CPV resolves to the space                                             |

Two methods rather than one is the point: figures built from different data that
land in the same order of magnitude are an argument, and a figure with no method
is not. TAM is every adopter; **SAM is computed**, not discounted by a fudge
factor — the same estimate restricted to the size classes and geographies Orange
serves; SOM is the one genuinely modelled number, a share assumption anchored on
right-to-win and portfolio distance and labelled as such everywhere it appears.

Four decisions in that pipeline were load-bearing enough to be worth naming:

- **The denominator and the adoption rate must share a base.** Eurostat
  publishes enterprise ICT adoption for firms with 10+ employees only. Multiplied
  by an all-sizes enterprise count — roughly 90% micro-firms — every estimate
  would have been out by an order of magnitude.
- **The contract value has to come from the right kind of contract.** The CPV
  crosswalk says what a notice is _about_; it does not say whether it is the kind
  of contract Orange would bid for. A €188m hydroelectric turbine retrofit,
  correctly crosswalked to industrial asset management, was setting the price of
  a zero-trust deployment until eligibility was tested on the notice's **main
  object** rather than any of its lots.
- **A public tender is a large-organisation contract.** Applied flat it prices a
  twelve-person manufacturer's project at a ministry's budget, so engagement
  value is scaled per size class, anchored on the class the observed contracts
  came from. The weights are an assumption with an owner, printed in the brief.
- **Proxies widen the range; they never move the base.** The enterprise ICT
  survey measures cloud, AI, IoT and security practice well and enterprise
  connectivity not at all, and it excludes finance, health, public administration
  and mining outright. Where a series has to stand in for another, the substitution
  is declared, the uncertainty band widens from ±15% to ±40%, and the confidence
  grade drops.

The confidence grade — `observed`, `partial`, `modelled` — is the **worst** basis
among the factors, never an average, because an estimate is exactly as good as
its weakest input. Where nothing attributable exists, no number is published:
public administration has no enterprise count in Eurostat at all, so those spaces
are sized from observed procurement only.

Reference data lives in its own tables, not in `signals`. An annual statistical
series has no publisher diversity, no momentum and no relevance; pushing 56,000
Eurostat cells through the signal store would corrupt every component that counts
attached signals while adding nothing to discovery.

The subsystem in depth — every factor with its source, a worked example with the
arithmetic shown, the config surface and the tests that pin each decision — is in
[`MARKET_SIZING.md`](MARKET_SIZING.md).

### Competitive intensity (§4.3.3)

§4.3.3 puts competition on the right-to-win side — "contract award notices
additionally reveal who is winning" — and Table 27 lists award concentration
among competitors as a procurement feature. Each space carries a level of
**NONE / LOW / MEDIUM / HIGH** over a named list, and the two are never conflated:
a level with no names is an opinion, and the names with their evidence are what a
salesperson can use and a colleague can correct.

Two kinds of presence are distinguished, because they are worth different things
in a meeting:

- **evidenced** — this space's own sources name the competitor. The signal id,
  publisher and date travel with the claim and are clickable.
- **structural** — the curated register says they sell this technology into this
  vertical. True, useful, and not proof they are in the deal.

The level is a band over a weighted count: category weight (a hyperscaler moves a
market more than a regional reseller) × how specifically the competitor matches
this space, doubled where the corpus actually names it. It is scored over the
**listed** competitors rather than the whole register — summing a fifty-entry tail
of weak domain matches would rate every cybersecurity space identically, which is
the same score-compression failure §4.6 warns about for the rubrics.

`relationship: both` is the field that makes the register honest for Orange
Business. Microsoft is a Gold partner and the default alternative in most AI
deals; Cisco is a Global Gold partner and sells managed SD-WAN directly. Recording
that is more useful than pretending either half is not true, and 5 of the 8
competitors listed against a typical security space are Orange partners.

Competitive intensity is a **fourth quantity**, beside attractiveness, right to win
and conviction, and kept as separate from them as they are from each other. A
crowded field and a weak Orange position are different facts; averaging them would
hide both.

### Competitor intelligence — what they say they sell (§4.3.3 extension)

Competitive intensity says how crowded a space is. It does not say what those
competitors are **doing** there, or what Orange replies when the customer names
one of them. The register also has a quieter weakness: it is a human's summary,
written once, going stale from the day it is written.

So the radar reads what each competitor publishes about itself — **1,745 pages
across 53 of the 65 registered competitors** — and turns it into a structured
profile where every claim carries the page that said it.

```
crawl ──► profile ──► join ──► compare
robots    1 model     arithmetic  1 model call per topic
-aware    call each   per topic   activity · differentiation · concession
```

**What a profile is allowed to do is the whole design.** A competitor's own
website is **tier 4 — interested party** — exactly like a vendor press release.
So a profile may _explain_ a competitor the register already matched to a topic,
and it may _seed_ generation. It may not lift attractiveness or any other
published score, and SC-09's guarantee that vendor-only evidence scores low is
untouched. A candidate the competitor lens produces still has to bind to
independent, non-vendor evidence to survive.

**The differentiation paragraph** is the part a salesperson repeats verbatim, so
it carries a guard beyond the four defences: it may only name Orange assets
**linked to that topic** in the business graph. Where nothing is linked, the
honest paragraph says Orange would be competing on price and delivery rather than
on a structural advantage. An invented advantage is not caught in review — it is
caught in the meeting. Each competitor also gets a **concession**: what they
genuinely do better. A paragraph that gives the competitor nothing reads as
marketing and gets discounted whole.

**Coverage is reported, not assumed.** Twelve competitors are unprofiled and each
is named in the Coverage view with its reason: six refuse automated clients or
disallow crawling, three render their content client-side, three are unreachable.

> A browser user agent gets through all six of the refusals. It is not used. The
> source catalogue already records Ofcom as unwired for exactly this reason, and
> applying a different standard to competitors because the data is more
> interesting would be the kind of quiet inconsistency the rest of the design
> exists to prevent. **This is a decision with an owner, not a technical limit.**

Two defects worth knowing about, both now regression tests:

- **The model echoed the vocabulary list.** Asked for OVHcloud's technologies it
  returned the _first eight ids in vocabulary order_ — private 5G, O-RAN,
  network slicing, satellite NTN. Every id valid, so closed-vocabulary validation
  passed all eight; OVHcloud's pages mention 5G zero times. A list-echo is the
  characteristic failure of handing a model an enumeration, and the enumeration
  is what makes it survive validation. Tags now need corroboration in the source
  text, word-boundary matched — the same rule `enrich` already applies to signal
  attachment.
- **A citation proved a page was read, not that it said this.** "Accenture LED
  Flashlight" arrived as a named offer with a page id attached.

Full detail: [`COMPETITOR_INTELLIGENCE.md`](COMPETITOR_INTELLIGENCE.md).

### The detailed description, and what it is not allowed to say (FR-14)

Each space carries a long-form description written from its own evidence, its
linked Orange assets and its named competitors — and nothing else. It appears in
the detail pane and is the narrative half of the PDF brief.

Prose is where a model invents, so all four defences of §4.4.4 apply to it in the
same order of effectiveness as in synthesis:

1. **Evidence binding.** The factual sections (`what_is_changing`,
   `competitive_landscape`) must cite signal ids attached to _this_ topic. A
   section that cannot is stripped, not rewritten — and what was stripped is
   listed in the UI rather than quietly omitted. Sections that describe what
   Orange would _do_ are exempt: a proposal cannot be "supported by a source",
   and demanding a citation for one would only teach the model to attach one at
   random.
2. **Closed vocabulary**, applied to the diagram (below).
3. **No model-generated numbers.** A regex over every generated sentence. The
   brief's figures come from the sizing engine; a model sentence contradicting
   them is worse than a missing one.
4. **Named-entity check.** No customer, partner or competitor beyond the supplied
   lists. Naming a plausible account is the failure most likely to be repeated in
   a meeting as though it were a known Orange relationship.

A description records the topic version it was written against, so a topic that
has moved on is flagged as stale rather than left to mislead.

### The PDF brief, and its diagram (FR-18)

FR-18 was previously listed as not built, with the note that "the read API
exposes everything an exporter needs". This is that exporter: a six-page brief a
salesperson or presales engineer can take into a meeting — the opportunity, the
sized market with every factor and its source, the solution drawn as a diagram,
the named assets, the competitive field with its evidence, qualifying questions,
objections, the next action per role, and every source listed at the back.

Three kinds of content meet on the page and are kept visibly distinct, because a
reader has to know which is which:

|              | Produced by                          | Reproducible from                 |
| ------------ | ------------------------------------ | --------------------------------- |
| **computed** | `scoring`, `sizing`, `competition`   | stored inputs (DR-05)             |
| **curated**  | business graph, competitor register  | config with a named owner (DR-11) |
| **written**  | the model, under the §4.4.4 defences | its cited signals                 |

The last page carries the weight set, the sizing version, the register version
and the prompt and model that wrote the prose (DR-10). A brief that cannot be
traced is a brochure.

**The diagram is not drawn by the model.** It emits a _structure_ — layers,
boxes, who provides each one, what flows where — which the renderer draws to the
same geometry every time. A model asked for SVG or drawing code produces
something that looks plausible and overlaps its own labels; a model asked for
structure produces something a renderer can guarantee. The closed-vocabulary rule
applies to it too: a box claiming to be an Orange asset that is not in the linked
graph is **demoted to third party rather than deleted** — the architecture still
needs that component — and the demotion is recorded in the brief.

reportlab renders it rather than an HTML-to-PDF pipeline: no browser dependency,
which matters for the sovereign deployment option (NFR-05).

### The Planner, and what it is allowed to promise

The radar answers "which opportunity", one space at a time. The Planner answers
"which opportunities, in what order, and what do they earn" — which is a
different question, and the reason it opens full screen rather than in a pane.

**Two sources for the portfolio, and they are different questions.** Under
_Parameters_ the caller states constraints and the optimiser chooses the set —
the exploratory question, what _should_ we do. Under _Workflow selected_ the set
is already decided: every opportunity space the collaboration board has moved to
**Demand-tested or beyond** is in, and none of the constraints is applied to it,
because each would overrule a decision a strategist, a salesperson or a presales
engineer has already taken. That mode answers what the business already
committed to earns, and when. The Planner then does the part nobody did by hand:
each space enters when its horizon says the market arrives, a cohort larger than
a year's capacity cascades forward, a space already Live starts in year one
whatever its horizon says, and revenue, margin, ramp, overlap discount and
capability load follow. **Nothing is dropped to make it fit.** Where the
committed set needs more than the capability pools can staff, the plan says so
and by how much — that gap is the finding, not a reason to edit the portfolio —
and a committed space with no market size is listed as a gap rather than
silently missing from a total the reader believes is complete.

**Selection is an optimisation, not a ranking.** A ranked list assumes you can
take the top N, and you cannot: Orange cannot enter 400 spaces at once, or even
twelve in one vertical. A mixed-integer program (scipy `optimize.milp`, HiGHS)
maximises the stated objective subject to entry slots per year, capability-pool
headcount at a stated availability, concentration caps per vertical and
technology, and a target now/next/later mix. The plan then reports **which
constraint bound it** — the thing a ranked list cannot tell you, because the
answer is a constraint rather than a score.

**Obtainable share is not additive.** Two spaces selling to the same buying
centre in the same vertical do not sum, so the aggregate is discounted before it
is totalled. Summing naively implied 42–90% of Orange Business's segment
revenue; discounted and capacity-constrained, a plan lands at 6–9% — and
anything above a stated share of filed segment revenue is flagged on the plan
rather than left for the reader to notice.

**The money is Orange's own.** The margin applied to revenue (7.9% segment
EBITDAaL) and the rate used to discount it (7.3% post-tax) are quoted from the
2025 Universal Registration Document filed with the AMF, not chosen here.
Everything else is a planning band with a named owner in
`config/economics.yaml`, versioned as `economics_version` and carried on every
plan — because a plan built under one version of these assumptions is not
comparable with a plan built under another.

**The narrative may not state a figure.** The business plan is one model call
over the computed plan, under the same discipline as the topic description: a
sentence that disagreed with the table beside it would be a defect the reader
has to adjudicate. Sections that introduce a number are stripped and listed.

**ROI is not offered, and that is deliberate.** There is no cost data — not in
the filings at the granularity a space would need, not anywhere the pipeline can
reach. A five-year _revenue and profit_ projection is defensible from what
exists; an ROI would require inventing the denominator.

**Export to PDF.** A plan that has to leave the tool to be read is a plan that
gets read in a stale copy, so the export is a **Document tab** that renders the
PDF and shows it in the browser: the stated inputs (with the effective value of
anything unstated, and where it came from), the projection with its charts,
every selected space with the one-paragraph summary from its own long-form
description, the business plan, and the assumptions with their owner and
versions. It rebuilds on open rather than serving a cache, because the narrative
can be written after the plan was computed. Download and open-in-a-new-tab are
what you do after you have seen it.

### Three panes, sized by the reader

The middle pane now carries a document and the right pane carries a
decomposition, and which one a user wants larger changes by task. So the
boundary between them is a real separator: drag it, or focus it and use the
arrow keys, or double-click to reset; the width persists. The filter rail
collapses to a strip that still shows how many filters are active, and the detail
pane can be hidden entirely when the brief deserves the full width.

The detail pane answers §4.9's questions in the order they arrive, which is
correct and long — so it carries jump links rather than being reordered. A
presales engineer wants the assets and a strategist wants the sizing; both should
still pass the evidence on the way there.

### The interface, after an adversarial review

Seven independent reviewers went at the running app — three working the sales,
presales and strategist tasks end to end, one on keyboard and contrast, one on
information architecture, one on failure states, one on copy and first use —
and each finding was then handed to a separate reviewer whose job was to refute
it against the code. 82 findings, most confirmed, and the confirmed ones are
fixed. The ones worth naming, because each was a real failure rather than a
preference:

**Nobody could use the list with a keyboard.** Topic rows were `div`s with an
`onClick`. A keyboard or screen-reader user could reach the "how was this
calculated" button on a row but never the row itself, so the detail pane — the
market size, the competitors, the description — was unreachable from the primary
browsing surface. The statement is now a real button inside the row, which also
fixes the selected state: `aria-selected` on a role-less `div` is dropped by
every browser.

**The interface failed its own contrast bar, and worst where it mattered most.**
Measured rather than eyeballed: the evidence-gap warning (SC-13) sat at 2.57:1
in light mode and the "HIGH competition" marker at 2.66:1 in dark — the two marks
that exist to stop someone quoting a thin number were the least legible things on
the page. Status colours are now theme-aware tokens named for the judgement they
carry, every value computed against both surfaces of its own theme. The brand
orange stays on fills and marks, where 3:1 is the bar, and text takes a darkened
sibling: one orange cannot be both a 10px label and a brand colour. **10,056
rendered text elements across seven tabs and two themes now clear WCAG AA.**

**A 20-to-60 second generation finished in silence.** Building a brief swapped
the middle pane with no announcement and no elapsed time. There is now one polite
live region for the whole app, and the wait is counted out loud.

**The five largest sized opportunities were unreachable.** The view is capped at
24 (AC-05) and the only ordering was the role's ranking function, so a strategist
comparing market size could not get to them. There is now an order control —
market size, attractiveness, right to win, least contested, evidence, recency —
which re-orders **within** what the role may see and says so: a salesperson
sorting by market size still cannot reach white space (§4.5.3).

**The filter rail lied about its own counts.** They were computed from the 24
topics on screen, so "CISO: 0" meant "none on this page" while 37 matched. Counts
are now server-computed facets over the whole role-eligible set. Competition level
and "has a sales brief" became filters, filters and sort travel in the URL so a
prepared view can be sent to a colleague, and White space honours the rail
instead of ignoring it while looking interactive.

**Both radar encodings had collapsed.** Marker area spanned 17.8 to 19.9 pixels
and 17 of 26 marks shared one fill, because the scales mapped the nominal 0–100
range while the scores occupy 23–84 and 10–88. Both now map the band the data
actually uses, with the breaks at the measured quartiles; the legend prints them
and has moved above the plot, where it is visible without scrolling.

**The detail pane had grown to ten screenfuls with none of the four quantities in
the first one.** It now opens with attractiveness, right to win, serviceable
market and competitive intensity side by side — four numbers, never combined
(SC-12) — each linking to the section that derives it, followed by the role's own
next action, which had been at screen seven. Jump links cover every section, move
focus rather than only scrolling, and stick to the top of the pane.

**And below 1080px — which is what 200% browser zoom looks like to CSS — the
entire detail pane was `display: none` with no alternative.** Market size,
competition and the description simply vanished. The middle pane now takes it
over.

The full audit, its verdicts and what was refuted are reproducible: the workflow
script is in the session's `workflows/scripts/` directory.

### Serving the same data 18x faster

Assembling a view issued eleven database queries per topic — scores, links, node
labels, competition, size, workflow state, assessments twice, signal count and
two artefact checks. Across 167 topics that was about 1,670 round trips and 1.6
seconds of dead air on **every** filter change, role switch and tab change, and
it was invisible in any frontend profile.

The read model is a read model, so the fix was the obvious one: fetch each table
once for the whole set and index it in memory. `_assemble` reads from that
context when it is given one and queries when it is not, so the single-topic
detail path is untouched — and a test asserts the two paths produce byte-identical
topics, because two code paths for one object is how two surfaces start
disagreeing.

|                       | Before                           | After                           |
| --------------------- | -------------------------------- | ------------------------------- |
| `/api/view`           | 1.69 s · 343 kB · ~1,670 queries | **0.05 s · 84 kB · 11 queries** |
| `/api/workflow/board` | 1.24 s · 2,151 kB                | **0.04 s · 181 kB**             |

The board was shipping every topic's links, score components and rank
explanation to render forty-word cards; it now sends what a card shows. The view
drops the fields only the detail page renders. A test guards the query count
against growing _with the number of topics_, which is the regression that would
make a list feel broken at 150 rows.

### Designed for the refresh, not the first run (§4.1)

Canonical identity is the taxonomy triple, enforced by a unique index. A
recurring topic is **updated**, not recreated (DR-03); new signals attach, the
score is recomputed, the previous score is retained. This is what makes momentum
measurable, and §4.4.5 calls it the requirement most often missed in a first
build.

### Leakage control (FR-35, §4.7.3)

Every connector takes a `reference_date` and rejects anything published after it
— filtering on the **publication** date, never the ingestion date. Raw archives
are retained so a replay needs no re-fetch. `radar replay --date 2024-06-01`
reconstructs the state of the world as of that date.

---

---


