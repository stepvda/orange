# -*- coding: utf-8 -*-
"""Per-slide speaker notes, transcribed from the recorded walkthrough and
extended with the material that is on the slide but was compressed on the day.

`dur` is how long to spend on that slide; `end` is the running clock when it
finishes. Slides 10 to 21 are delivered as a LIVE APPLICATION DEMO rather than
as slides — the deck carries a screenshot of each so the pack still reads on its
own, and so a presenter who cannot reach the running instance can still give the
talk."""

SLIDES = [
# ---------------------------------------------------------------- 1
dict(n=1, section="OPENING", title="Opportunity Spaces / Innovation Radar",
     onscreen="Title slide — Orange Business, subtitle, and the one-line promise.",
     dur=20, end=20,
     say=[
"This is the **Orange Business Innovation Radar** — a working prototype, built against the requirements baseline.",
"It maintains a regularly refreshed view of **specific innovation opportunities**. Each one is scored on how attractive it is, how urgent the window is, and how strong Orange's right to win is.",
"[Set expectations] I'll take about twelve minutes, in three parts: the concepts the product rests on, what it does, and how it is built. There's a running system behind every number you'll see.",
     ],
     advance="ADVANCE TO SLIDE 2  —  “The problem is not a shortage of information”"),
# ---------------------------------------------------------------- 2
dict(n=2, section="WHY", title="The problem is not a shortage of information",
     onscreen="Rejected topics on the left (“AI”, “Cloud”, “Cybersecurity”) against one real topic on the right.",
     dur=28, end=48,
     say=[
"The problem this solves is **not a shortage of information** about technology.",
"The information that exists is generic, undated, unsourced — and disconnected from what Orange can actually sell.",
"So “AI”, “cloud” and “cybersecurity” are **rejected as topics**. They fail validation. [point at the left column]",
"A real topic reads like this: **private 5G plus edge vision for safety compliance in mining**. Specific enough to open a customer meeting with.",
"That is the bar the whole product is built to clear — the join between an external signal and an internal asset, at a level of specificity a salesperson can use in a meeting on Thursday.",
     ],
     advance="ADVANCE TO SLIDE 3  —  “An opportunity space is a triple”"),
# ---------------------------------------------------------------- 3
dict(n=3, section="CONCEPT", title="An opportunity space is a triple",
     onscreen="Manufacturing × OT/ICS security × SIEM and SOAR, with the rendered statement underneath.",
     dur=27, end=75,
     say=[
"So — an opportunity space is a **triple**: a vertical, times a use case, times a technology.",
"The triple is the **identity**. It gives deduplication and filtering, and it is what makes a topic **recur** across refreshes rather than being recreated each time. That is what makes momentum measurable.",
"The human-readable statement underneath is a **rendering** of that triple. Both are stored.",
"And a candidate that does not resolve to exactly one vertical, one use case and one technology **fails validation automatically**.",
     ],
     advance="ADVANCE TO SLIDE 4  —  “Two scores, never one”"),
# ---------------------------------------------------------------- 4
dict(n=4, section="CONCEPT", title="Two scores, never one",
     onscreen="Three columns: Attractiveness, Right to win, Conviction — with their components listed.",
     dur=37, end=112,
     say=[
"Every topic carries **two scores that are never combined**.",
"**Attractiveness** asks whether the world is moving. It is computed from external evidence alone.",
"**Right to win** asks whether we can play and whether we can win. It is computed from a curated graph of Orange's offers, references, partners and certifications — as **named query results**, never asserted by a language model.",
"Collapsing them into one number would destroy the information the strategist needs. [beat] A topic can be excellent for a strategist — large, early, no proof points — and useless for a salesperson, because there is nothing to show.",
"There is a third quantity, **conviction** — what our own people believe. It adjusts what surfaces first for each role, and it never touches the other two.",
     ],
     advance="ADVANCE TO SLIDE 5  —  “Evidence before generation”"),
# ---------------------------------------------------------------- 5
dict(n=5, section="CONCEPT", title="Evidence before generation",
     onscreen="Four numbered defences, plus the adversarial critic panel at the foot.",
     dur=41, end=153,
     say=[
"The model **never invents a topic** out of its own knowledge. Four defences enforce that.",
"**One — evidence binding.** Every claim must cite signal identifiers that exist in the cluster that produced it. Uncited claims are **stripped, not rewritten** — asking a model to repair a claim just teaches it to attach a citation at random.",
"**Two — closed vocabulary.** Taxonomy values are validated against the enumerations. A recognised synonym is repaired once; anything else is dropped.",
"**Three — no generated numbers.** Market sizes are looked up and attributed, or they are absent. It is backstopped by a regex over every generated sentence.",
"**Four — an entailment check.** A second pass verifies each claim is genuinely entailed by the span it cites.",
"And on top of all four, an **adversarial critic** — a separate prompt that scores one to five as the **minimum** across five tests, so a single failure caps the whole score. In the live run it rejected **345 of 644 candidates**, each with a written reason.",
     ],
     advance="ADVANCE TO SLIDE 6  —  “Portfolio distance”"),
# ---------------------------------------------------------------- 6
dict(n=6, section="CONCEPT", title="Portfolio distance decides whose conversation it is",
     onscreen="The L0–L4 ladder, each rung with its owner and its verb.",
     dur=34, end=187,
     say=[
"**Portfolio distance** is the most decision-relevant number in the product. It is the shortest path from a topic to something Orange could **actually deliver**.",
"**L0** means an existing offer already addresses it as it stands. That is a sales conversation — sell it.",
"**L2** needs a capability a partner already holds — presales and alliances assemble it.",
"**L4** is white space: no plausible path from the current portfolio at all.",
"And this is what drives the **role modes** — they are not arbitrary interface presets, they fall out of this ladder.",
"A high-attractiveness **L4** topic is exactly the strategist's innovation agenda — and exactly what a salesperson should never be shown.",
     ],
     advance="ADVANCE TO SLIDE 7  —  “What the MVP has actually produced”"),
# ---------------------------------------------------------------- 7
dict(n=7, section="STATUS", title="What the MVP has actually produced",
     onscreen="Five headline figures, then four supporting lines on coverage and evidence quality.",
     dur=29, end=216,
     say=[
"Here is what the prototype has actually produced — and every figure on this slide is **read live from its database**, not typed into the deck.",
"**418 opportunity spaces**, from eleven thousand signals, gathered across **34 live sources**, joined to **4,800 named asset links**.",
"**All 15 verticals** are covered.",
"And the corpus carries over a **thousand French-language signals** — so the anglophone bias that was named as a principal risk is **measured, rather than assumed**.",
     ],
     numbers=["418 opportunity spaces  ·  11,354 signals ingested, 6,804 through the gate  ·  34 live sources of 42 catalogued",
              "4,832 asset links over 181 graph nodes  ·  26.7 signals per topic after enrichment",
              "7,267 tier-1 signals  ·  47 of 59 use cases and 33 of 38 technologies appear in at least one topic",
              "314 sized bottom-up  ·  181 competition-scored  ·  174 with a sales brief  ·  8 portfolio plans"],
     ifasked=[("“Why is the grid so sparse?”", "Deliberately. Most cells in a 15 × 59 × 38 grid **should** stay empty — a topic only exists where evidence puts it.")],
     advance="ADVANCE TO SLIDE 8  —  “Sizing and competition”"),
# ---------------------------------------------------------------- 8
dict(n=8, section="CONCEPT", title="Sizing and competition, with the working shown",
     onscreen="Two panels — bottom-up market size on the left, competitive intensity on the right.",
     dur=41, end=257,
     say=[
"Two further questions a topic cannot be acted on without: **how big is it**, and **who else is already there**.",
"Headline market figures in the press come from paid research, are quoted without methodology, and often conflict by an order of magnitude.",
"So the radar builds **its own estimate, bottom up** — enterprise counts by sector and size class, times an observed adoption rate, times a plausible contract value — and it **shows its working**, with a method and a confidence label attached. You can reject the number on its arithmetic.",
"**Competitive intensity** is scored against a versioned competitor register, against the evidence actually collected — who is visibly playing here.",
"And a crowded field is **not a reason to walk away**. It is a reason to win on a specific differentiator.",
"[If you have time] One detail worth naming: “no competitor found” is reported as **unverified**, not as empty — because it may only mean the register has a gap.",
     ],
     advance="ADVANCE TO SLIDE 9  —  “Two routes into a new opportunity space”"),
# ---------------------------------------------------------------- 9
dict(n=9, section="CONCEPT", title="Two routes into a new opportunity space",
     onscreen="Two cards — parameters on the left, a scoping conversation on the right — over a dark panel describing the gate they share.",
     dur=34, end=291,
     say=[
"Everything so far arrives from a **scheduled refresh**. These two are for the case a refresh cannot serve: somebody has a specific question **now**, about a cell of the grid the corpus has not been asked about yet.",
"**Parameters** is for somebody who knows the taxonomy. Pick a vertical, a use case, a technology and a horizon — and before anything is spent, the screen shows the spaces that **already** satisfy them. [beat] The most common outcome of an on-demand run is rediscovering what the last refresh produced.",
"**A scoping conversation** is for somebody who knows their market but not this vocabulary. The assistant interviews, with the corpus in front of it, and re-retrieves on **every turn** against the same signal vectors the run itself will read.",
"And both are refused by the **same gate**, which the corpus holds rather than the model. Asked \u201cdo you have enough?\u201d a model says yes — so the button is enabled by what actually came back, not by the assistant's opinion of itself.",
"[If asked why the vertical is excluded] Because it corroborates every brief ever written about a well-covered sector. Municipal digital signage retrieves French public-sector tenders at the same cosine a well-evidenced brief scores.",
     ],
     ifasked=[("\u201cWhat does the gate actually check?\u201d", "Two things. That the brief clears the run's own **retrieval floor**, and that it is **corroborated** on its use case or its technology by a second, independent reason.")],
     advance="ADVANCE TO SLIDE 10  —  the radar view (the live demo starts here)"),
# ---------------------------------------------------------------- 10
dict(n=10, section="FUNCTIONALITY", title="The radar view", demo=True,
     onscreen="Screenshot of the polar radar. In the recording this was a live application demo.",
     dur=40, end=331,
     say=[
"Here is the **running application**. The radar is the signature view.",
"**Angular sectors** are the six business domains. **Distance from the centre** is the time horizon — Now at the middle, Later at the rim.",
"**Marker size** is attractiveness and **marker colour** is right to win — so the two questions the radar exists to answer are visible at the same time, without a legend anyone has to study.",
"Position already carries identity, which is what frees colour to encode a quantity.",
"A marker with an **exclamation mark** carries an evidence gap — it means Orange has few published references in that vertical. [point at one]",
"And switching role changes the **ranking function**, not just a filter. Sales sees only topics with a delivery path, a published reference in the vertical, and no evidence gap — which is why the count drops when you switch. [switch the role selector]",
     ],
     advance="ADVANCE TO SLIDE 11  —  the role-ranked list"),
# ---------------------------------------------------------------- 11
dict(n=11, section="FUNCTIONALITY", title="Role-ranked list", demo=True,
     onscreen="Screenshot of the list view with the per-row score columns.",
     dur=11, end=342,
     say=[
"The **list view** shows the same topics, ranked for the selected role — with attractiveness, right to win, horizon, portfolio distance and the number of supporting signals on every row.",
"Three genuinely different rankings, not three filters: the **strategist** ranks on attractiveness and novelty and ignores right to win; **sales** ranks on right to win and proof-point density; **presales** ranks on differentiation.",
     ],
     advance="ADVANCE TO SLIDE 12  —  topic detail"),
# ---------------------------------------------------------------- 12
dict(n=12, section="FUNCTIONALITY", title="Topic detail", demo=True,
     onscreen="Screenshot of the detail pane, with the cited-claim chips visible.",
     dur=24, end=366,
     say=[
"Opening a topic gives the **detail pane**.",
"Every claim under **“why it is hot now”** is bound to the signal identifiers that support it, and each chip links out to the **original dated source**. [click one]",
"Further down, **can we play / can we win** is itemised against **named Orange assets** — a specific offer, a specific certification, a specific partner tier.",
"Never an aggregate assertion that Orange has relevant capabilities. That distinction is the whole point.",
     ],
     advance="ADVANCE TO SLIDE 13  —  one space, full screen"),
# ---------------------------------------------------------------- 13
dict(n=13, section="FUNCTIONALITY", title="One space, full screen", demo=True,
     onscreen="The full-screen view of one opportunity space, with its four tabs across the top.",
     dur=22, end=388,
     say=[
"The three-pane layout is right for working **through** the radar — filter, scan, open, compare, move on.",
"It is wrong for the moment somebody actually **reads** a space: ten sections in a four-hundred-pixel column beside a chart they are no longer looking at.",
"So the same content opens with the panes out of the way, in **four tabs**, in the order the questions arrive: what is this, who else is here, what do I send, and what happens after the meeting. [point along the tabs]",
"The brief sits one click from the space on purpose — it is generated from the space and goes stale when the space moves, and reading them in the same frame is how anyone notices.",
     ],
     advance="ADVANCE TO SLIDE 14  —  how this score was calculated"),
# ---------------------------------------------------------------- 14
dict(n=14, section="FUNCTIONALITY", title="How this score was calculated", demo=True,
     onscreen="Screenshot of the score-explanation modal.",
     dur=29, end=417,
     say=[
"Now the part that makes the scoring **defensible**.",
"Every topic has a **“How was this calculated”** panel. It shows the weight table and the weighted total — and then, per component, the **actual stored inputs**:",
"the publishers counted and their entropy; the tier distribution; the per-period buckets the momentum slope was fitted to; the rubric level and its written rationale.",
"This is how a reviewer **outside the project** can reconstruct why a topic holds its rank. [beat] The governing constraint was: if a user cannot explain why a topic ranks where it does, the scoring is not good enough.",
     ],
     advance="ADVANCE TO SLIDE 15  —  pre-sales collateral"),
# ---------------------------------------------------------------- 15
dict(n=15, section="FUNCTIONALITY", title="Pre-sales collateral", demo=True,
     onscreen="The fourth tab of the full-screen view: twelve pre-sales artefacts, grouped by when they are used.",
     dur=30, end=447,
     say=[
"The brief is **one document for one conversation**. This is the twelve pieces a team needs **between** that conversation and a proposal.",
"Discovery and qualification, an outreach sequence, a first-meeting deck, a value hypothesis, a reference pack, battlecards, a solution outline, a PoC scope, a partner brief, commercial model options, tender blocks, a bid risk register.",
"All twelve are listed **whether or not anything has been built** — what could be produced is as much of the answer as what has been, and a screen that starts empty is one nobody presses a button on.",
"The **format is the reader's choice, per piece**. A battlecard defaults to PDF because it is read on a phone and must not have been edited since it was approved; tender blocks default to Word because a PDF of paste-fodder obstructs. And the formats coexist.",
"And all twelve are built from **one snapshot** of the space. Two documents in the same pack quoting different market sizes is the failure that makes impossible rather than merely unlikely.",
     ],
     ifasked=[("\u201cAre the charts pictures?\u201d", "In PowerPoint they are **native shapes** — an architect moves a box rather than redrawing the slide. In PDF they are drawn geometry. Word and OpenDocument get the same picture rasterised, because neither has a drawing model this code can target.")],
     advance="ADVANCE TO SLIDE 16  —  the stage gate"),
# ---------------------------------------------------------------- 16
dict(n=16, section="FUNCTIONALITY", title="Stage gate and role assessment", demo=True,
     onscreen="Screenshot of the workflow board — Shortlisted, Demand-tested, Packaged, Live.",
     dur=18, end=465,
     say=[
"The **workflow board** implements the stage gate. A topic moves from Shortlisted, through Demand-tested and Packaged, to Live — and **ownership follows the stage**. Stalled cards are flagged, because latency is the known weakness of a stage gate.",
"Each role assesses **only the axis it owns**: sales rates customer demand, presales rates deliverability — on a **0 to 5 scale with written anchors**, because people are unreliable at rating something 73 out of 100.",
     ],
     advance="ADVANCE TO SLIDE 17  —  analytics"),
# ---------------------------------------------------------------- 17
dict(n=17, section="FUNCTIONALITY", title="Analytics", demo=True,
     onscreen="Screenshot of the analytics tab — heatmap, funnel, divergence chart.",
     dur=19, end=484,
     say=[
"The **analytics view** visualises the whole corpus.",
"The **heatmap** is vertical by domain — and the empty cells are the white space.",
"The **diverging chart** shows where the team and the evidence disagree. That is a **review queue**, because disagreement is information rather than friction.",
"[If asked about the charts] Each chart is chosen by the job the data does: sequential for magnitude, diverging with a neutral midpoint for polarity, ordinal for the funnel. Only the signal-type mix is categorical, and it ships a legend **and** a table.",
     ],
     advance="ADVANCE TO SLIDE 18  —  generating a space on demand"),
# ---------------------------------------------------------------- 18
dict(n=18, section="FUNCTIONALITY", title="Generating a space on demand", demo=True,
     onscreen="The Generate screen with the conversation tab open, retrieved signals listed down the right-hand side.",
     dur=24, end=508,
     say=[
"The Generate screen used to be a text box with a character counter — which is the one failure that did not matter.",
"An opportunity space is a vertical times a use case times a technology, plus a buyer's problem and a place. Somebody who knows their market but not this taxonomy **under-specified two of those every time**, and found out minutes later from a run that created nothing.",
"So the assistant **interviews** instead, with the corpus in front of it — and shows what each turn retrieved down the side: publisher, date and cosine similarity, per signal. [point at the evidence column]",
"An answer that sharpens the idea sharpens the evidence the next question is asked from.",
     ],
     advance="ADVANCE TO SLIDE 19  —  the Planner"),
# ---------------------------------------------------------------- 19
dict(n=19, section="FUNCTIONALITY", title="The Planner", demo=True,
     onscreen="The Planner overview: five headline figures, then the projection, entry schedule, capability load and constraint waterfall.",
     dur=34, end=542,
     say=[
"The radar answers **which opportunity**, one space at a time. The Planner answers **which opportunities, in what order, and what do they earn**.",
"A ranked list cannot answer that, because it assumes you can take the top N — and you cannot. Not four hundred spaces at once, and not twelve in the same vertical.",
"So selection is a **mixed-integer program**: maximise the stated objective subject to entry slots per year, capability headcount at a stated availability, concentration caps, and a target now/next/later mix.",
"And it reports **which constraint bound it**. [point at the waterfall] That is the thing a ranked list cannot tell you, because the answer is a constraint rather than a score.",
"Selection and projection are **arithmetic** — no model call, so this is immediate. The written business plan is a separate step, and it may not introduce a figure.",
     ],
     ifasked=[("\u201cWhy not a recommender?\u201d", "There are **no labels**. Four hundred and eighteen spaces and zero historical outcomes is a spreadsheet, not a training set. And an optimiser explains which constraint bound; a learned model cannot.")],
     advance="ADVANCE TO SLIDE 20  —  the plan the business already chose"),
# ---------------------------------------------------------------- 20
dict(n=20, section="FUNCTIONALITY", title="The plan the business already chose", demo=True,
     onscreen="The Planner with Workflow selected as its source, showing the written business plan for the committed set.",
     dur=30, end=572,
     say=[
"There is a **second source** for a plan, and it asks a different question.",
"Under **Workflow selected**, the portfolio is already decided: every space the collaboration board has moved to **Demand-tested or beyond** is in — and **none** of those constraints is applied to it.",
"Each of them would overrule a decision somebody already took. Dropping a space for resting on a modelled size answers a salesperson's judgement with an assumption band.",
"So there is no objective and nothing is excluded for being outranked. What is left is **scheduling**: each space enters when its horizon says the market arrives, and a space already Live starts in year one whatever its horizon says.",
"And **nothing is dropped to make it fit**. Where the committed set needs more than the capability pools can staff, the plan says so and by how much — that gap is the **finding**, not a reason to edit the portfolio.",
     ],
     advance="ADVANCE TO SLIDE 21  —  contextual help"),
# ---------------------------------------------------------------- 21
dict(n=21, section="FUNCTIONALITY", title="Contextual help", demo=True,
     onscreen="Screenshot of a help dialog. Short slide — this was one sentence in the recording.",
     dur=6, end=578,
     say=[
"And throughout, **every dense concept explains itself** — with a pointer back to the requirement it comes from, so the answer is checkable rather than merely confident.",
     ],
     advance="ADVANCE TO SLIDE 22  —  the pipeline"),
# ---------------------------------------------------------------- 22
dict(n=22, section="ARCHITECTURE", title="Seven pipeline stages, each with a contract",
     onscreen="The stage chain, with the Orange Business Graph as a parallel path underneath.",
     dur=28, end=606,
     say=[
"Architecturally, this is **seven pipeline stages**, each with a defined input and output contract — so they can be developed, tested and replaced independently.",
"Collect, normalise, classify, cluster into themes, synthesise candidates, enrich them with further evidence, score — and serve.",
"A **parallel, slower path** maintains the Orange Business Graph — offers, references, partners with tiers, certifications, analyst positions, capability pools. It **joins at the scoring stage**, so right to win can be improved without re-running discovery.",
"[If asked about speed] Collection runs in parallel — twelve sources in about forty-five seconds — while database writes stay serial, because deduplication is a read-modify-write over the whole signal table.",
     ],
     advance="ADVANCE TO SLIDE 23  —  the stack"),
# ---------------------------------------------------------------- 23
dict(n=23, section="ARCHITECTURE", title="Stack and separation of concerns",
     onscreen="Three columns — Ingestion, Intelligence, Serving — with the configuration note beneath.",
     dur=37, end=643,
     say=[
"The stack is **deliberately unremarkable**, because the value is in the schema and the curation rather than the infrastructure.",
"**19 connectors** feed a signal store — procurement portals, regulators, standards bodies, research, news in English and French.",
"**DeepSeek** sits behind a provider-agnostic client, so switching to a **sovereign, local model** is an environment variable rather than a rewrite. Embeddings already run locally.",
"The graph is **thousands of nodes, not millions**, so SQLite is entirely adequate. A FastAPI read API, and a React front end with a hand-drawn SVG radar — no chart library, because the encoding is specific to this product.",
"And taxonomies, weights, thresholds, sources and the crosswalks are all **configuration, not code** — validated at load time, so a dangling identifier is a **startup error** rather than a wrong number three stages later.",
     ],
     advance="ADVANCE TO SLIDE 24  —  what makes the numbers defensible"),
# ---------------------------------------------------------------- 24
dict(n=24, section="ARCHITECTURE", title="What makes the numbers defensible",
     onscreen="Six guarantees: decomposable, reproducible, traceable, versioned, auditable, bounded.",
     dur=35, end=678,
     say=[
"That gives **six guarantees** about the numbers.",
"**Decomposable** — every displayed score breaks into named components. No opaque scores.",
"**Reproducible** — every component stores the inputs used to compute it, so any number can be re-derived.",
"**Traceable** — lineage runs from a displayed claim all the way back to the raw ingested item, including prompt and model version.",
"**Versioned** — every score records its weight set, so trajectories are never plotted across an incomparable boundary.",
"**Auditable** — a reviewer outside the project can reconstruct why any topic holds its rank.",
"And **bounded** — counting, diversity, recency and momentum are **arithmetic, never a model**. A model asked to count is occasionally wrong and always unverifiable.",
     ],
     advance="ADVANCE TO SLIDE 25  —  what is not built"),
# ---------------------------------------------------------------- 25
dict(n=25, section="STATUS", title="What is deliberately not built — and what needs a decision",
     onscreen="Two columns: not built with the reason, and four open decisions for Orange.",
     dur=37, end=715,
     say=[
"Finally — what is **deliberately not built**, and what needs a decision from Orange.",
"There is no CRM integration, and **no learned scoring model**, because no labels exist on day one. The capture-and-replay harness ships instead, so the labels can start accumulating now.",
"And where the data will not support a figure, **no market size is shown at all**, rather than a wrong one. There is also **no return on investment on a plan** — there is no cost data at the granularity a space would need, so revenue and profit are defensible and an ROI would require inventing the denominator.",
"Sign-in exists, but it answers **who**, not **may they**: per-role authorisation on the write endpoints is still absent.",
"Four things need a human. [count them off]",
"**One** — 4,832 links are machine-proposed and **unconfirmed**. Who is the curator?",
"**Two** — **margin by portfolio distance**. One table from Orange finance moves five-year profit by a factor of **1.66**, and revenue concentrates at L0, so that one band dominates the whole plan.",
"**Three** — how much **capability headcount is free for new work**. It is the constraint that binds first in most plans, and the shipped figure is a guess.",
"**Four** — **terms of use** are unconfirmed for several enabled sources. That is a Sprint 0 blocker.",
"The point to take from this slide is that the radar **surfaces its own gaps** rather than hiding them.",
     ],
     advance="ADVANCE TO SLIDE 26  —  the close"),
# ---------------------------------------------------------------- 26
dict(n=26, section="CLOSE", title="The join is the product",
     onscreen="Closing statement, with the four headline figures repeated underneath.",
     dur=17, end=732,
     say=[
"The **join** between an external signal and an internal asset **is the product**.",
"Without it, this is a competent trend feed — and trend feeds already exist.",
"With it, the radar answers a question **nobody else can answer for Orange**.",
"[Stop. Hold the slide and take questions.]",
     ],
     advance="END OF DECK  —  hold this slide and take questions",
     terminal=True),
]
