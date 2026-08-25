# Orange Business — Opportunity Spaces / Innovation Radar

MVP implementation of the requirements baseline in
[`docs/Orange_Innovation_Radar_Requirements_and_Approach.docx`](docs/).

**Documentation:** [documentation index](docs/DOCUMENTATION.md) — the Functional Design Document and
Technical Architecture as Word documents, plus the
[API](docs/API.md), [data model](docs/DATA_MODEL.md),
[runbook](docs/OPERATIONS.md), [decisions](docs/DECISIONS.md),
[market sizing](docs/MARKET_SIZING.md),
[scoring formulas](docs/SCORING_FORMULAS.md),
[competitor intelligence](docs/COMPETITOR_INTELLIGENCE.md) and
[changelog](docs/CHANGELOG.md) references.

An opportunity space is **Vertical × Use Case × Technology** with a human-readable
statement. Each one carries two scores that are never combined: **attractiveness**
("is the world moving") and **right to win** ("can we play, can we win"), plus
**conviction** ("do our own people believe it") and **competitive intensity**
("how crowded is the field") as separate quantities beside them. Each also carries
a **market size** computed bottom-up from published statistics, a written
description bound to its own evidence, a **competitor analysis** saying what each
named competitor is doing there and how Orange differentiates against each of
them, and a **PDF brief** a salesperson can take into a meeting. Every claim is bound to a dated, attributable source, and every
number decomposes into named components.

Beyond the brief, each space carries **twelve pieces of pre-sales collateral**
for the work between the first meeting and a proposal — qualification, a
solution outline, battlecards, a business case, a PoC scope, tender blocks, a
risk register and more — each with its own diagrams, and each available as PDF,
Word or OpenDocument (decks as PowerPoint, OpenDocument or PDF). All twelve are
built from one snapshot of the space, so nothing in the pack can disagree with
anything else in it.

Section references below (§4.5.3, SC-13, FR-30 …) point at the requirements
document. They are also carried in the code as comments, so any given behaviour
can be traced back to the requirement that asked for it.

---

## The six questions

Short answers with the working behind them. Every claim links to the section
that derives it, and every number is read from the working database rather than
typed here.

1. [What makes it unique, and the top five features](#1-what-makes-it-unique-and-the-top-five-features)
2. [The top three limitations and next steps](#2-the-top-three-limitations-and-next-steps)
3. [Where AI is used, where it is not, and why](#3-where-ai-is-used-where-it-is-not-and-why)
4. [How to trust the accuracy](#4-how-to-trust-the-accuracy)
5. [How the scoring works, and why this approach](#5-how-the-scoring-works-and-why-this-approach)
6. [The tools and packages, and why these ones](#6-the-tools-and-packages-and-why-these-ones)

### 1. What makes it unique, and the top five features

**The claim in one sentence.** Most innovation radars are a curated slide: a
committee's opinion, drawn as a chart, with the reasoning left in the room where
it was decided. This one is a pipeline that **cannot state a number it cannot
source and cannot name a thing it did not read** — and it does not stop at the
insight, it ends at the artefact a salesperson carries into the meeting.

Two consequences are worth separating, because either alone is common and both
together is not. First, the discipline runs all the way down: 11,498 signals,
5,217 links, 752 market sizes and 449 opportunity spaces each decompose into
named inputs with a publisher and a date, and where the evidence runs out the
radar publishes nothing rather than an estimate. Second, the chain does not stop
at a score. The same evidence that ranks a space also writes its description,
sizes its market, names its competitors, drafts its brief, fills twelve pre-sales
documents and feeds a five-year portfolio plan — from one snapshot, so no two
artefacts in the pack can disagree.

The five features that carry it:

1. **Generation that is fenced in by evidence, and a funnel that publishes its
   own rejection rate.** Four defences in the requirements' order of
   effectiveness — evidence binding, closed vocabulary, no model-generated
   numbers, entailment — plus an adversarial critic with a different system
   prompt that scores as the _minimum_ across five tests. An uncited claim is
   **stripped, not rewritten**. In the live run, 254 candidates produced 60
   accepted spaces: 6 failed vocabulary, 7 failed evidence binding, 119 failed
   the critic, 62 merged as duplicates, and 15 individual claims were stripped by
   entailment. That funnel is printed rather than hidden.
   → [Evidence before generation](#evidence-before-generation-41)

2. **Four quantities that are never collapsed into one, each explaining itself
   on demand.** Attractiveness (is the world moving), right to win (can we play),
   conviction (do our own people believe it) and competitive intensity (how
   crowded is it) travel as separate fields end to end and occupy separate visual
   channels. Every space carries a **How was this calculated?** modal that shows
   the stored inputs and the arithmetic — the publishers counted, the tier
   distribution, the per-period buckets the momentum slope was fitted to, the
   rubric level and its rationale, the named offers behind right-to-win — plus
   the weight set, pipeline, prompt and model that produced it.
   → [Explaining a score, per topic](#explaining-a-score-per-topic)

3. **Market size computed from published statistics, never quoted from a press
   release.** Two independent methods side by side — enterprises × adoption ×
   engagement value from Eurostat, and annualised contracts that actually exist
   from TED — with every factor carrying its dataset, year and basis. SAM is
   _computed_ rather than discounted by a fudge factor. The confidence grade is
   the **worst** basis among the factors, never an average, and where nothing
   attributable exists no number is published: 531 of 752 computations are graded
   `observed`, 145 `partial`, 76 `modelled`.
   → [Market size, with the working shown](#market-size-with-the-working-shown-434)

4. **Competitors read from what they publish about themselves, with the reply a
   salesperson can actually say.** 1,745 pages crawled robots-aware across 65
   registered competitors, turned into structured profiles where every claim
   carries the page that said it, then joined per space into an activity
   paragraph, a **differentiation** paragraph and a **concession** — what the
   competitor genuinely does better, because a paragraph that gives them nothing
   reads as marketing. The differentiation paragraph may only name Orange assets
   linked to _that_ space in the business graph; where nothing is linked it says
   Orange would be competing on price and delivery. An invented advantage is not
   caught in review, it is caught in the meeting.
   → [Competitor intelligence](#competitor-intelligence--what-they-say-they-sell-433-extension)

5. **It ends in a deliverable, and then in a portfolio.** Each space produces a
   six-page PDF brief whose solution diagram is drawn by a renderer from a
   model-emitted _structure_ rather than by the model itself, plus twelve
   pre-sales artefacts — qualification, solution outline, battlecards, business
   case, PoC scope, tender blocks, risk register and more — documents as PDF,
   Word or OpenDocument and decks as PowerPoint, OpenDocument or PDF. Above them
   the Planner answers the
   different question: a mixed-integer program selects a portfolio under entry
   slots, capability headcount and concentration caps, projects five years using
   Orange's own filed margin and discount rate, and reports **which constraint
   bound it** — the thing a ranked list cannot tell you.
   → [The Planner](#the-planner-and-what-it-is-allowed-to-promise)

### 2. The top three limitations and next steps

Ranked by how much they would change what the tool is worth, not by how hard
they are to fix. All three are surfaced in the interface rather than left to be
discovered.

**1. Not one of the 5,217 links has been confirmed by a human.** LK-06 asks for a
named curator to adjudicate the _first occurrence of each link pattern_, and the
count of confirmed links is currently zero. Right to win is a structured lookup
over exactly those links, so every right-to-win score in the radar rests on
machine-proposed evidence nobody has signed. The same gap runs wider than links:
the 65-entry competitor register and the sizing assumptions in
`config/sizing.yaml` — contract duration, size-class weights, obtainable share —
both carry `innovation-radar-curator` as a placeholder owner, and both appear in
front of customers. This is the one limitation that is an organisational decision
rather than an engineering task, which is why it is first: the code to record a
curator's decision exists and is tested, and no curator exists.

**2. Nothing is calibrated, and nothing has been backtested.** The weights — 0.30
market signal strength, 0.20 diversity, and so on — are the briefing's indicative
figures. No outcome data has ever moved them. The replay harness that a backtest
needs is built and works (`radar replay --date 2024-06-01`, publication-date
leakage control, retained raw archives), but the §4.7.5 evaluation metrics are
not implemented, so the radar cannot yet answer the question that would justify
it: did a space scoring 80 in June behave differently by December from one
scoring 40? Until it can, the scores are a defensible, transparent, _asserted_
ordering. The next step is small and specific — run the replay at three past
dates, and measure rank stability and precision against what has since been
tendered.

**3. Coverage is uneven, and the gaps propagate silently into the outputs that
matter.** 113 of 449 spaces have no bottom-up market size, which makes them
invisible to the Planner rather than merely unqualified; 236 have no competitive
assessment, so their competitor tab is empty; 12 of 65 competitors are unprofiled
(six refuse automated clients, three render client-side, three are unreachable);
and the reference data is European business economy only — public administration
has no Eurostat enterprise count at all, so those spaces are sized from observed
procurement alone. Each of these is reported with its reason, which is the
correct behaviour and is not the same as being fixed. The stage gate is the same
shape of problem from the other end: 446 of 449 spaces sit in Shortlisted, so a
workflow-sourced plan currently describes a portfolio of three.

Three more are named in full rather than implied, because they bear on anyone
deploying this: there is **no per-role authorisation** (sign-in answers _who_,
not _may they_ — every signed-in account can move a stage, delete a space and
spend model budget), **no rate limiting** on the endpoints that spend that
budget, and **no ROI on a plan**, because no cost data exists at the granularity
a space would need and inventing the denominator would be worse than omitting the
ratio.
→ [What is deliberately not built](#what-is-deliberately-not-built) ·
[Open questions for Orange](#open-questions-for-orange)

### 3. Where AI is used, where it is not, and why

The division of labour is not incidental — it follows Table 23 of the
requirements, and the governing rule is that **a model is used where judgement or
language is unavoidable, and never where arithmetic is available.** "A model
asked to count will occasionally be wrong and always be unverifiable."

**Where a model is used.** Every call records the prompt version and model that
produced it (DR-10), and every generative system prompt has the no-numbers rule
appended in the client itself rather than left to the prompt author.

| Stage                                        | What the model does                                                                                                                                                                                                                                                    | Why a model rather than rules                                                                                                                                                                                                                          | What stops it being wrong                                                                                                                                             |
| -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `classify` (`pipeline/ingest.py`)            | Assigns one of six signal types to each item, batched, cheap model                                                                                                                                                                                                     | 11,498 items across six languages. A keyword rule cannot tell a regulatory consultation from a funding award from a deployment announcement — the distinction is in what the document _does_, not which words it contains                              | Closed six-value list, per-item confidence stored, heuristic fallback if the batch fails                                                                              |
| `synthesise` (`pipeline/synthesis.py`)       | Reads a theme cluster and proposes a vertical × use case × technology with a written statement and cited claims. Three passes per cluster at temperature 0.85, each under a different **evidence lens** — regulatory, procurement, technology-maturity, cross-vertical | This is the irreducible step. The whole point of a radar is the cell that is not in anybody's catalogue yet; no rule proposes what nobody has written down. The lenses exist because an open-ended loop "elaborates around whatever it produced first" | All four §4.4.4 defences plus the critic. 194 of 254 candidates did not survive                                                                                       |
| `critique` (same)                            | A separate system prompt scores a candidate 1–5 as the **minimum** across five tests                                                                                                                                                                                   | Judging whether a proposal is specific, evidenced and non-obvious is a reading task                                                                                                                                                                    | Minimum rather than mean, so one failure caps the score. Rejections carry written reasons                                                                             |
| `entailment` (same)                          | Cheap second pass: is this claim entailed by the span it cites?                                                                                                                                                                                                        | Citation formatting is checkable by code; _entailment_ is not                                                                                                                                                                                          | Temperature 0, and a failed call keeps the claim rather than deleting evidence                                                                                        |
| `strategic_relevance` (`scoring.py`)         | Scores a space against the _Trust the future_ ambitions on a 0–5 rubric with worked anchors                                                                                                                                                                            | Judging a topic against a written strategy document is comprehension, not lookup                                                                                                                                                                       | Discrete levels mapped to fixed numbers, deterministic priors computed first, and a deterministic fallback if no model is available. This is 15% of one of two scores |
| `describe` (`pipeline/describe.py`)          | Writes the long-form description from the space's own evidence, linked assets and named competitors                                                                                                                                                                    | Turning structured evidence into something a human reads is what language models are for                                                                                                                                                               | Evidence binding, closed vocabulary on the diagram, no-numbers regex, named-entity check. Stripped sections are listed in the UI                                      |
| `competitor-profile` / `competitor-analysis` | One call per competitor turns crawled pages into a structured profile; one call per space writes activity, differentiation and concession                                                                                                                              | Reading 1,745 marketing pages and extracting what each firm claims to sell                                                                                                                                                                             | Tags need word-boundary corroboration in the source text; named offers must be supported by the cited page; differentiation may only name linked Orange assets        |
| `actions` (`pipeline/actions.py`)            | The next action per role                                                                                                                                                                                                                                               | A next step is a sentence, not a field                                                                                                                                                                                                                 | Role-scoped, bound to the space's own links                                                                                                                           |
| `plan` narrative (`planner.py`)              | One call writes the business plan over the already-computed plan                                                                                                                                                                                                       | The plan is a table; the argument is prose                                                                                                                                                                                                             | **A section that introduces a number is stripped and listed.** The table is authoritative                                                                             |
| `presales/content.py`                        | Fills the twelve collateral pieces                                                                                                                                                                                                                                     | Same reason as `describe`, twelve times                                                                                                                                                                                                                | One snapshot per pack, so pieces cannot disagree; a piece with a missing input still builds and says so                                                               |
| `scoping.py` / `scouting.py`                 | The Generate screen's interview, and turning a brief into search queries                                                                                                                                                                                               | Somebody who knows their market but not this taxonomy under-specifies two of five fields every time                                                                                                                                                    | The Generate button is enabled by the **corpus**, not by the assistant's opinion of itself; where the two disagree the screen says so                                 |

**Where a model is deliberately not used.** This list is the more load-bearing
half, because it is what makes the first list cheap enough to verify.

| Task                                                    | What does it instead                                                | Why not a model                                                                                                                                   |
| ------------------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Signal counting, publisher diversity, recency, momentum | Arithmetic — log compression, Shannon entropy, least-squares slope  | Unverifiable and occasionally wrong, for a task where a `for` loop is exact                                                                       |
| Relevance gating                                        | Vocabulary keyword match over the taxonomy                          | 11,498 items × a model call is a cost with no accuracy gain over a controlled vocabulary                                                          |
| Theme clustering                                        | Local embeddings + agglomerative clustering at a distance threshold | SC-11 requires identical inputs to give identical output. Generation here "would invent structure"                                                |
| Right to win                                            | Structured lookup against the business graph (SC-15)                | Asking a model whether Orange can win is asking it to assert a fact about a company. Seven components, all from config with named owners          |
| Market size                                             | Arithmetic over Eurostat observations and TED notices               | The whole point of §4.3.4 is that quoted figures conflict by an order of magnitude                                                                |
| Competitive intensity level                             | Weighted count over the listed competitors, banded                  | A level with no names is an opinion                                                                                                               |
| Evidence enrichment                                     | Embedding similarity **plus** independent taxonomy corroboration    | Similarity alone happily rates two unrelated security items as close, and unchecked attachment inflates exactly the components that count signals |
| Portfolio selection                                     | Mixed-integer program (scipy `milp`, HiGHS)                         | Selection under capacity and concentration constraints has an optimum; a model would approximate it and could not say which constraint bound      |
| The solution diagram                                    | The model emits a _structure_; reportlab draws it                   | A model asked for SVG produces something plausible that overlaps its own labels                                                                   |
| Duplicate identity                                      | The canonical taxonomy triple, plus an embedding threshold          | Identity must be stable across refreshes or momentum is unmeasurable                                                                              |

**Why the AI parts are better than not having them.** Three things this pipeline
does that a rules-only version could not do at any reasonable cost. It **reads**
— 11,498 documents in six languages, placed onto a 15 × 59 × 38 grid, which is
the work that otherwise does not happen and is why most radars cover the four
verticals somebody had time for. It **proposes** — the radar's product is the
cell nobody wrote down, and a rule engine can only recombine cells somebody
already enumerated; the coverage-driven prompting turns that from "produce more
ideas" into "cover the evidenced grid", which terminates and is measurable. And
it **writes** — a description, a battlecard and a business plan are prose, and
the alternative to generating them is not a template, it is nobody writing them.

The honest limit, stated the same way: everything above is a _drafting_ function
with a human gate downstream, and nothing above is trusted to state a fact. That
is why the model never produces a number, never asserts an Orange capability, and
never survives its own first pass without a critic.

### 4. How to trust the accuracy

Trust is not asserted here; it is decomposed. Seven mechanisms, and then the list
of things you should **not** trust, which is the part that makes the rest
credible.

**1. Every claim resolves to a document.** A claim carries signal ids, validated
to exist _in the cluster that produced the candidate_; each signal carries its
publisher, publication date, tier and URL. In the interface the citation is
clickable — you can read the source that produced the sentence. A claim that
cannot cite is **stripped, not rewritten**, and what was stripped is listed
rather than quietly omitted.

**2. No number in the system was generated.** The rule is enforced in three
places rather than one: appended to every generative system prompt in the LLM
client itself, backstopped by a regex over every generated sentence, and tested —
a generated percentage or euro figure kills the section carrying it. Every
published figure is arithmetic over named inputs, and every input names its
dataset, year and basis.

**3. Every number is reproducible from stored inputs.** DR-05 stores each score
component _with the inputs that produced it_; DR-10 stamps every artefact with
its pipeline, prompt and model version. NFR-03 asks that "a reviewer outside the
project can reconstruct why any topic holds its rank", so the **How was this
calculated?** modal shows the weight table, the weighted total, and per component
the actual evidence — expanded, not behind a tooltip. It deep-links:
`?explain=OS021`.

**4. Numbers that are not comparable cannot be plotted together.** Changing any
weight requires a new `weight_set` id; the same rule extends to `sizing_version`,
`register_version` and `economics_version`, each carried on the artefact it
produced. A plan's id encodes its economics version, so two plans built under
different assumptions cannot be confused. The UI refuses to draw a trajectory
across a boundary.

**5. The pipeline argues with itself, and reports how often it wins.** The critic
runs on a different system prompt and rejected 119 of 254 candidates with written
reasons. Entailment stripped 15 claims that cited a real source which did not
support them. The interface itself was put through the same treatment: seven
independent reviewers worked the running app, each finding was handed to a
separate reviewer whose job was to **refute** it against the code, and 82
findings survived that. Contrast was measured rather than eyeballed — the
evidence-gap warning sat at 2.57:1 — and 10,056 rendered text elements across
seven tabs and two themes now clear WCAG AA.

**6. 486 tests pin the invariants, and several of them caught real defects.**
Not coverage for its own sake — the specific things that would be expensive to
discover late: score reproducibility, syndication collapse, vendor-only evidence
scoring low, uncited claims being stripped, triple-based identity, leakage
control on publication date. The bugs they caught are named in the
[Tests](#tests) section, and two are worth repeating here because they were
silently wrong rather than broken: Shannon entropy is scale-invariant, so a
uniform tier-4 discount cancelled out entirely and six vendor blogs scored
identically to six independent outlets; and the competitor profiler, asked for
OVHcloud's technologies, returned the _first eight ids in vocabulary order_ —
every id valid, so closed-vocabulary validation passed all eight, and OVHcloud's
pages mention 5G zero times. Both are now regression tests.

**7. Where the evidence runs out, nothing is published.** The market-size
confidence grade is the **worst** basis among its factors, never an average,
because an estimate is exactly as good as its weakest input. Public
administration has no Eurostat enterprise count, so those spaces are sized from
observed procurement only rather than from a substituted proxy. Twelve
competitors are named in the Coverage view as unprofiled with the reason for
each. Nine catalogued sources are unwired and say why.

**What you should not trust, and why it is listed here.** Every one of these is
labelled in the interface as well, but a reader deserves them in one place:

- **SOM is a modelled number.** TAM and SAM are computed; the obtainable share is
  an assumption anchored on right-to-win and portfolio distance, and it is
  labelled as such everywhere it appears.
- **The four-year contract duration is an assumption with an owner.** TED
  publishes a contract's whole value and annualising it needs a duration. Every
  market size in the radar moves inversely with that figure.
- **The size-class weights are an assumption with an owner**, printed in the
  brief rather than buried.
- **The scoring weights are uncalibrated** — see limitation 2 above.
- **No link has a human's name on it** — see limitation 1 above.
- **Contract values are a public-procurement proxy for private-sector deals**,
  used because it is the only attributable source available.
- **A competitor's own website is tier 4** — an interested party, exactly like a
  vendor press release. A profile may _explain_ a competitor and _seed_
  generation; it may not lift attractiveness or any other published score.

### 5. How the scoring works, and why this approach

**The shape first: two scores, never one.** Attractiveness answers "is the world
moving" from external evidence. Right to win answers "can we play, can we win"
from internal assets. They are different questions, actionable by different
people, and a single blended number hides which half is weak: a space at 85
attractiveness and 20 right-to-win averages to exactly the same 52.5 as one at
50 and 55, and the two mean completely different things to a salesperson. They
travel as separate fields end to end and occupy separate visual channels (marker
size, marker colour). Conviction and competitive
intensity sit beside them as a third and fourth quantity, equally uncombined.

**Attractiveness — five components, four of them arithmetic.**

| Component              | Weight | How it is computed                                                                                                                                                                                           | The failure it is designed against                                                                                                                                                                                                             |
| ---------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Market signal strength | 0.30   | `100 × log₂(1+n) / log₂(1+corpus_max)` over relevance-gated signals                                                                                                                                          | Log compression stops one noisy topic saturating the scale. Normalising against the live corpus makes the score mean "how visible is this relative to everything else on the radar", not "how many articles exist"                             |
| Source diversity       | 0.20   | Shannon entropy over the publisher distribution, syndicated duplicates collapsed on (publisher, title prefix), tier-4 publishers discounted to 0.35                                                          | "Twenty outlets all syndicating one vendor press release is one source, not twenty." The discount is applied to the **effective publisher count**, not to summed weights — applied naively, entropy's scale-invariance cancels it out entirely |
| Evidence quality       | 0.20   | Tier-weighted mean (1.00 / 0.75 / 0.45 / 0.15). Tier-4 **share** above a 0.25 cap cuts the mean in proportion to the excess, and a further 45% cut applies when there is no tier-1 or tier-2 evidence at all | A cap on the _share_, not a discount on each item, so no volume of vendor material reaches a high score (SC-09)                                                                                                                                |
| Novelty and momentum   | 0.15   | Least-squares slope over six trailing 15-day buckets, scaled by the mean level, plus a first-appearance bonus and a long-flat-history penalty                                                                | Scaling by mean level stops 0→1→2 being read like 0→10→20. The flat penalty is what demotes a topic that has been quietly present for a year                                                                                                   |
| Strategic relevance    | 0.15   | Deterministic priors (privileged vertical, sovereign deliverability) plus a 0–5 rubric level mapped to {0, 20, 40, 60, 80, 100}                                                                              | Discrete anchored levels rather than a free 0–100 ask, because §4.6 warns free numeric asks compress toward the middle. Falls back to deterministic marker matching with no model                                                              |

**Right to win — seven components, all structured lookup, none asserted by a
model** (SC-15).

| Component            | Weight | Source                                                                                                                                                     |
| -------------------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Offer match          | 0.25   | 100 for a direct (L0) offer link, 55 for a bundle (L1), 0 otherwise — `config/business_graph/offers.yaml`                                                  |
| Reference density    | 0.20   | Published customer stories apportioned onto the 15 verticals, normalised to the peak vertical. Below threshold raises the **evidence-gap warning** (SC-13) |
| Partner coverage     | 0.15   | Best partner tier rank among linked partners                                                                                                               |
| Compliance fit       | 0.12   | Certifications held, with a bonus for sovereign ones                                                                                                       |
| Capability depth     | 0.12   | `log1p(headcount) / log1p(10000)` — 7,000 experts is not 17× better than 400                                                                               |
| External validation  | 0.08   | An analyst position exists, or it does not                                                                                                                 |
| Technology ownership | 0.08   | A portfolio-level prior from `technologies.yaml`, flagged in its own inputs as awaiting the deferred patents connector                                     |

Both scores also drive derived state without a second model: the **horizon** (Now
/ Next / Later) from evidence dates and published Orange commitment anchors, and
the **lifecycle** (candidate → active → fading → dormant) from thresholds on
signal count, distinct publishers, evidence quality and the requirement of
non-tier-4 evidence.

**Why this is a good approach — five reasons, and the honest caveat.**

1. **It explains itself, which was the governing constraint.** §3.8: "the scoring
   model must not produce only a number — it must explain the number, and if a
   user cannot explain why a topic is ranked where it is, the scoring is not good
   enough." Every component returns its value _and_ the inputs that produced it,
   and both are persisted. That is why the explain modal is possible at all; it
   was not retrofitted.

2. **Arithmetic where arithmetic is honest, a rubric where judgement is
   unavoidable.** 85% of attractiveness and 100% of right to win are computed
   from counted evidence and config with named owners. The one judgement call is
   discrete, anchored, and worth 15% of one of two scores — so a bad rubric call
   moves a score by at most 15 points and the rationale is stored beside it.

3. **It is built against the failure modes that actually occur** rather than
   against an abstract idea of quality. Syndication, vendor astroturf, one-hit
   spikes, topics that have been quietly present for a year, six vendor blogs
   dressed as six sources — each has a named defence in the table above, and each
   defence has a test.

4. **It is versioned, and the versioning is enforced rather than documented.**
   Changing a weight requires a new `weight_set` id, every score records the set
   that produced it, and the UI refuses to plot across the boundary. Calibration
   drift is the failure mode that makes a year-old radar quietly meaningless.

5. **It is the right baseline to be replaced.** The correct long-run answer is a
   learned per-role ranking from expert pairwise comparisons — which needs 300–600
   labels that do not exist on day one. So the MVP ships the transparent baseline
   _plus_ the capture and replay harness the learned model will need: feedback
   capture, retained raw archives, and publication-date leakage control so a
   backtest is possible without re-fetching. A transparent wrong weight is
   fixable by argument; an opaque learned weight trained on no labels is not.

**The caveat, stated once more because it belongs here.** These weights are the
briefing's indicative figures and have never been calibrated against an outcome.
The approach is defensible; the specific numbers are a starting position. What
makes that acceptable is that they are configuration with an id, not code — and
that every score carries the id, so the day they change, nothing already
published silently changes meaning.
→ [Two scores, never one](#two-scores-never-one-sc-12) ·
[Explaining a score](#explaining-a-score-per-topic)

### 6. The tools and packages, and why these ones

Two rules ran through every choice. **Pure Python or nothing** — no LibreOffice,
no headless browser, no external renderer — because NFR-05 keeps a sovereign,
air-gapped deployment on the table and every binary dependency closes that door a
little. And **the abstraction matters more than the vendor**, because §4.4.6 is
right that the economics change every few months.

**The model, and why DeepSeek.** `deepseek-chat` behind a provider-agnostic
client (`llm.py`) that speaks the OpenAI wire format. The pipeline is
call-heavy — 11,498 classifications, then per cluster three lensed generations
plus a critique plus one entailment check per claim — so cost per token, not
benchmark position, was the deciding factor for a corpus this size, and
DeepSeek's published price per token is a small fraction of the frontier models'
at an output quality that survives the critic. But the provider is the
_replaceable_ part, and that is the actual design decision:
`deepseek | openai | ollama | mock` is an `.env` change, not a re-architecture,
and Ollama is there because Orange sells trusted AI on sovereign infrastructure
and a design that cannot run in a French datacentre is the wrong design. `mock`
is not a toy either — it is what lets the suite run without a provider key, and
the generation tests force it in an autouse fixture, because "a test suite that
quietly spends money is a test suite nobody can run in CI". Two rules live in
the client rather than in prompts: every call records its prompt version
(DR-10), and the no-generated-numbers rule is appended to every generative
system prompt automatically.

**The embedding, and what it actually buys.**
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, run locally.
Three specific reasons, in order:

- **Multilingual is not optional here.** FR-28 requires English and French
  ingestion and the corpus is 9,594 English, 1,054 French, 314 Spanish, 197
  German, 193 Italian and 137 Dutch items. Table 36 names "anglophone and EU
  bias in sources" as a risk — an English-only encoder would bake that bias into
  the clusters, and clustering is upstream of _everything_: a French tender that
  fails to cluster with its English equivalent becomes a separate theme, a
  separate candidate space, and a duplicate that dedup never sees.
- **Local means free and reproducible.** Zero marginal cost per refresh over a
  corpus this size, no second provider dependency, no per-call variance, and the
  sovereign option stays open. An API embedding would have added a vendor to the
  critical path of a stage whose whole justification (Table 23) is that it is
  "deterministic and reproducible".
- **Small enough to be ordinary.** 12 layers, 384 dimensions, runs on a laptop
  without a GPU. A larger encoder would improve cluster quality at the margin and
  make the pipeline undeployable on the machines it actually runs on. A TF-IDF +
  SVD fallback exists so a checkout with no model download still runs — with a
  loud warning, because cluster quality degrades materially.

**Everything else, and what each is doing.**

| Package                                               | Where                | Why this one                                                                                                                                                                                                                                                                                                                                                                                               |
| ----------------------------------------------------- | -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `scikit-learn` — agglomerative clustering             | Stage 4, themes      | Chosen over k-means and HDBSCAN specifically because it needs **no k, no random initialisation and no minimum cluster count**. SC-11 requires identical inputs to give identical output; a seeded k-means is reproducible only if you also version the seed                                                                                                                                                |
| `scipy.optimize.milp` (HiGHS)                         | Planner              | Portfolio selection under entry slots, capability headcount, concentration caps and a horizon mix is a constrained optimisation with an optimum, not a ranking to truncate. HiGHS ships inside scipy — no separate solver, no licence, no install step for whoever runs this next. It also reports **which constraint bound**, which is the output a ranked list structurally cannot produce               |
| `FastAPI` + `uvicorn` + `pydantic`                    | Read API             | Typed request/response contracts that match the pipeline's stage contracts, and one process serving both the API and the built bundle from the same origin. The application-level auth guard is a FastAPI dependency rather than a per-route decorator, because the failure mode of a per-route guard is the route somebody forgot                                                                         |
| `SQLite`                                              | Everywhere           | The database is **one file**, which is what makes the deployment story work: the whole corpus ships as a build artefact, seeds onto `/home` once, and the replay archive lives inside it. Correct for a single-writer batch pipeline plus a read API; it would be the wrong choice under concurrent writers, and that limit is named rather than discovered                                                |
| `reportlab`                                           | Briefs, plan report  | Renders the PDF _and_ draws the solution diagram to a deterministic geometry from a model-emitted structure. Chosen over an HTML-to-PDF pipeline because that needs a browser, and a browser in the serving container is hundreds of megabytes and a sovereignty problem                                                                                                                                   |
| `python-pptx`, `python-docx`                          | Pre-sales collateral | Pre-sales edits decks and documents; a PDF-only pack gets retyped. Both are pure Python, so five output formats cost no LibreOffice and no conversion service                                                                                                                                                                                                                                              |
| `pymupdf`                                             | Tests only           | Reads the generated PDFs back so the tests assert **what a reader sees** — including that every text frame on every generated slide fits its box, which is how four overflowing chart labels were caught                                                                                                                                                                                                   |
| `numpy`, `pandas`                                     | Throughout           | Vector operations on embeddings and the sizing arithmetic                                                                                                                                                                                                                                                                                                                                                  |
| `React` + `Vite` + `TypeScript`, **no chart library** | Frontend             | The radar's encoding is specific to this product — angular sector is business domain, radius is time horizon, marker size is attractiveness, marker colour is right to win — and every chart library would have been fought rather than used. Hand-drawn SVG also made the palette auditable, which is what let the contrast failures be measured rather than argued about. Two runtime dependencies total |

**How the data sources were selected.** 42 catalogued, 33 wired, across 17
connector types. Four rules decided which:

1. **Attributable and dated, or not a source.** DR-04 rejects an undated item
   outright, and momentum is a slope over publication dates — so a feed that
   cannot date its items contributes nothing and corrupts what it touches. This
   is also why CORDIS silently returned zero for a while: it emits
   `1 {{month_11}} 2023`, and every project was correctly rejected as undated.
2. **Authoritative by default, and it happens to be free.** 7,341 of 11,498
   signals are tier 1, because the tier-1 sources — TED, EUR-Lex, CORDIS,
   OpenAlex, Eurostat, NIST, national regulators — are public infrastructure. The
   corpus is weighted toward authority not by discounting the rest but by
   collecting mostly from sources that are authoritative to begin with.
3. **Terms of use recorded before the connector runs** (NFR-07 / DR-08). Every
   enabled source carries a `terms_checked` position, `pending` is an open action
   rather than an assertion, and the nine unwired sources each carry the reason —
   Ofcom answers 403 to automated clients, ENISA retired its RSS endpoints, EPO
   OPS needs registration.
4. **No key where a key can be avoided.** A source needing registration is a
   source that breaks in somebody else's checkout, which is why OpenAlex was taken
   over Scopus and Web of Science.

The individual choices worth defending:

- **TED is the single most valuable source** — 4,267 signals, and the only one
  where a buyer states a budget. It works twice: as demand-side evidence, and as
  the observed contract value that prices the bottom-up market size. It is also
  where the worst sampling bug lived (40 of 14,485 notices, all from one day),
  which is the argument for reading what actually landed in the database rather
  than trusting a connector that returns 200.
- **Eurostat is the denominator, and deliberately not a signal.** 56,385
  observations across five series live in their own reference tables. An annual
  statistical series has no publisher diversity, no momentum and no relevance;
  pushing it through the signal store would corrupt every component that counts
  attached signals while adding nothing to discovery.
- **GDELT is kept despite being the worst-behaved source in the set** — it
  rate-limits aggressively and is the long pole in every refresh — because it is
  the only source with real publisher diversity per signal (153 distinct
  publishers from 281 items) and the only geo-tagged news in the corpus. The
  trade-off it forced is written into `config/sources.yaml` as a comment: depth
  over breadth, because an unsliced GDELT has a 14-day memory and a six-period
  momentum slope over a 14-day memory measures the result-set length.
- **SEC EDGAR earns its place on a different axis.** Named enterprises describing
  their own deployments, under a legal obligation to be accurate — which is a
  materially different kind of evidence from a press release about the same
  deployment.

---

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
[`docs/MARKET_SIZING.md`](docs/MARKET_SIZING.md).

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

Full detail: [`docs/COMPETITOR_INTELLIGENCE.md`](docs/COMPETITOR_INTELLIGENCE.md).

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

## Where the build stands

Read live from the working database, not typed here.

|                         |                                                                                                                                                  |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Opportunity spaces      | **449** — 363 active, 40 watchlist, 29 fading, 17 candidate                                                                                      |
| Grid coverage           | 15 of 15 verticals · 51 of 59 use cases · 35 of 38 technologies                                                                                  |
| Signals                 | **11,498** from 33 enabled sources, plus internal intake · 7,341 tier-1 · 1,054 French-language                                                  |
| Evidence attachment     | 11,602 signal-to-topic attachments across 325 theme clusters                                                                                     |
| Business graph          | 5,217 typed links onto 181 nodes and 182 edges                                                                                                   |
| Qualification           | 752 market-size computations over 449 spaces · 336 with a bottom-up estimate · 213 competitive assessments                                       |
| Competitor intelligence | 1,745 pages from 53 of 65 competitors · 53 profiles · 176 per-topic analyses                                                                     |
| Outputs                 | 173 long-form descriptions · 173 PDF briefs · 15 pre-sales artefacts built across 5 formats                                                      |
| Reference data          | 56,385 Eurostat observations across five series                                                                                                  |
| Planning                | 8 stored plans — the baseline parameter plan selects 51 spaces from 231 admissible; the workflow plan takes every committed space and drops none |
| Workflow                | 449 on the board — 446 Shortlisted, 2 Demand-tested, 1 Packaged                                                                                  |
| Tests                   | **486 passing**                                                                                                                                  |

Four numbers worth reading as gaps rather than achievements: **all 5,217 links
are machine-proposed and unconfirmed** — LK-06 wants a named human on the first
occurrence of each pattern; **236 of 449 spaces have no competitive assessment
yet**, so their competitor tab is empty; **113 spaces have no bottom-up market
size**, which is what makes them invisible to the Planner rather than merely
unqualified; and **the stage gate has three cards past Shortlisted**, so a
workflow-sourced plan currently describes a portfolio of three. All four are
surfaced in the interface rather than left to be discovered. They are the same
three limitations set out in [question 2](#2-the-top-three-limitations-and-next-steps).

## Data sources

**33 of 42 catalogued sources are wired and fetching**, across 17 connector types. The remaining nine are
catalogued in `config/sources.yaml` with the reason they are not — the catalogue
is the requirements record from Appendix A, not only runtime config.

Collection is **parallel**: sources are independent and network-bound, so they
run in a thread pool (`max_parallel_sources`, default 8); database writes stay
serial because dedup is a read-modify-write over the whole signal table.

Collection queries are **derived from the taxonomy** (`pipeline/query_grid.py`)
rather than hand-written. `config/sources.yaml` had claimed this was already true
and it was not — the first corpus showed the consequence, with whole branches of
a 59-use-case vocabulary carrying no query at all while manufacturing and public
sector ran away with the topic count.

| Source                             | Category    | Signals    | Notes                                                                                     |
| ---------------------------------- | ----------- | ---------- | ----------------------------------------------------------------------------------------- |
| TED                                | Procurement | 4,267      | Above-threshold EU tenders with CPV, country, buyer, value                                |
| Google News (EN)                   | Signals     | 1,488      | Queries derived from the taxonomy grid                                                    |
| OpenAlex                           | Technology  | 910        | Carries an Orange-affiliation flag (§2.5)                                                 |
| Google News (FR)                   | Signals     | 765        | French-language coverage                                                                  |
| Crossref                           | Technology  | 603        | Peer-reviewed output by concept                                                           |
| Google News (ES/DE/IT/NL/MEA/APAC) | Signals     | 966        | Six further language and region editions                                                  |
| GDELT                              | Signals     | 296        | Rate-limited, see below                                                                   |
| BOAMP                              | Procurement | 289        | French below-threshold tenders (§4.3.3)                                                   |
| CERT-BUND                          | Regulation  | 243        | German national regulator                                                                 |
| arXiv                              | Technology  | 236        |                                                                                           |
| Bing News                          | Signals     | 177        |                                                                                           |
| Find a Tender                      | Procurement | 173        | UK post-Brexit notices                                                                    |
| EC "Have your say"                 | Regulation  | 171        | Consultations with their feedback **deadline**                                            |
| Trade press                        | Signals     | 156        | Curated industry titles                                                                   |
| SEC EDGAR                          | Demand      | 142        | Named enterprises describing their own deployments, under legal obligation to be accurate |
| EUR-Lex                            | Regulation  | 86         | Dated legal instruments, stage inferred                                                   |
| CORDIS                             | Technology  | 77         | EU-funded projects — what Europe decided to fund                                          |
| TenderNed                          | Procurement | 77         | Dutch notices                                                                             |
| National regulators                | Regulation  | 86         | ANSSI, ACER, the EU financial regulators and peers                                        |
| Hacker News                        | Signals     | 66         | Practitioner attention, tier 3                                                            |
| UK Contracts Finder                | Procurement | 63         |                                                                                           |
| IETF Datatracker                   | Technology  | 51         | Standards timelines                                                                       |
| NIST · CISA · NCSC-UK · CERT-EU    | Regulation  | 100        | Standards and advisories                                                                  |
| Internal signals                   | Internal    | 10         | Moderated conversations and RFP themes, tier 3 (§2.5)                                     |
| **Total**                          |             | **11,498** | 7,341 tier-1 · 1,054 French-language                                                      |

Not wired, with the reason: Ofcom (403 to automated clients), BNetzA and BIPT
(documented feed paths 404), ENISA (retired its RSS endpoints), 3GPP and ETSI
(publish HTML, not feeds), EPO OPS (needs registration), PatentsView and ACLED
(DNS failures), Eurostat and World Bank (reachable, but they are _reference_
data for bottom-up sizing rather than dated signals — see below).

### Three sampling bugs worth knowing about

Each of these produced a plausible-looking corpus that was quietly wrong. All
three were found by looking at what actually landed in the database.

- **TED returned 40 of 14,485 matching notices, all from one day.** The API
  accepts no sort parameter and returns publication-date ascending, so a single
  capped request samples only the oldest day in the window — 182 of 218 notices
  from one date. Momentum (§4.6) is the slope of signal volume over trailing
  periods, so that corpus made every procurement-driven momentum figure
  meaningless. Fixed by slicing the window into 14-day chunks and querying each:
  now 827 notices across 35 distinct dates spanning the full 90 days.
- **CORDIS returned nothing at all.** It leaks its own localisation template and
  emits dates as `1 {{month_11}} 2023`, which failed date parsing, so every
  project was rejected as undated (DR-04) — silently, with no error.
- **EUR-Lex yielded 20 distinct acts from 120 rows.** CELLAR returns one row per
  expression title and several titles share a work, so rows collapsed on URL
  dedup. The limit was raised to compensate; a EuroVoc-concept query is the
  proper Sprint 0 fix.

**GDELT caveat.** The connector is correct and does return data, but GDELT
applies an aggressive per-IP cooldown and 429'd most requests during the build.
It is paced at one request per 6s. Two guards keep one sick source from damaging
a refresh:

- **Graceful degradation** — a failing source is recorded in the refresh stats
  and never aborts the run.
- **Circuit breaker** — after two exhausted requests to a host, the rest of that
  host's requests are skipped and the host is reported in `collect.errors`.
  Without it, ten blocked GDELT queries cost eleven minutes for zero data. GDELT
  is the long pole in every refresh: everything else finishes in 45 seconds
  while it takes up to 11 minutes alone.

**Reference data is wired, on its own path.** Five Eurostat series feed market
sizing and are stored as reference observations rather than signals, for the
reason given in the sizing section above:

| Series                         | Dataset            | Observations | What it gives                                                                             |
| ------------------------------ | ------------------ | ------------ | ----------------------------------------------------------------------------------------- |
| Structural business statistics | `sbs_sc_ovw`       | 27,958       | Enterprise counts and turnover by NACE division, size class and country — the denominator |
| Enterprise cloud use           | `isoc_cicce_usen2` | 6,885        | Paid cloud adoption by NACE aggregate                                                     |
| Enterprise AI use              | `isoc_eb_ain2`     | 11,440       | AI adoption by technology and NACE aggregate                                              |
| Enterprise IoT use             | `isoc_eb_iotn2`    | 2,759        | IoT adoption by purpose                                                                   |
| ICT security measures          | `isoc_cisce_ran2`  | 7,343        | Security practice by measure                                                              |

30 geographies (EU27 aggregate plus member states, Norway and Switzerland), the
last three published periods each, refetched only when older than the configured
age — these are annual statistics, not a feed. The AI series carries its own
trajectory, which the UI shows as an adoption trend: machine learning in EU
vehicle manufacturing went 3.2% (2023) → 4.8% (2024) → 7.8% (2025), which is a
dated, attributable growth statement rather than a generated one.

Still not wired **as reference data**: OECD, ITU, IEA and the national statistics
offices from Table 19. They matter for topics outside the European business
economy — today those are sized on the covered subset and the shortfall is
reported. SEC EDGAR is in the same Table 19 row and _is_ wired, but as a signal
source (142 items above): filings are dated, attributable statements of what a
named enterprise deployed, not a statistical denominator, so they feed discovery
rather than sizing.

## Frontend

React + Vite + TypeScript, no chart library — the radar is hand-drawn SVG
because the encoding is specific to this product.

**The radar view** (§4.9): angular sector = business domain, radial distance =
time horizon (Now at the centre), marker **size** = attractiveness, marker
**colour** = right to win. Position carries identity, so no categorical hues are
needed. Colour encodes a magnitude, so it uses a single-hue sequential ramp,
validated for lightness monotonicity, adjacent step separation, single hue and
light-end contrast against its own surface in **both** light and dark mode.
Evidence-gap marks carry a `!` glyph as well as a border, so the warning never
depends on colour alone.

**The full-screen view of a space** is the same content with the panes out of the
way, in four tabs — the space, the competitors, the brief, the pre-sales pack.
That is the order the questions arrive: what is this, who else is here, what do
I send, and what comes after the meeting. The three-pane layout is right for
working _through_ the radar — filter, scan, open, compare, move on — and wrong
for the moment somebody actually reads a space, because §4.9 gives the detail
pane ten sections and reading them in a 420px column beside a chart nobody is
looking at any more is the narrowest possible view of the longest content in the
interface. The pre-sales tab is last on purpose: putting it before the brief
would suggest a team should build a tender response before they have had the
first meeting. It lists all twelve pieces whether or not anything has been
built, because what _could_ be produced is as much of the answer as what has
been, and a screen that starts empty is one nobody presses a button on.

**The Generate screen opens with a conversation, not a text box.** The box asked
for one thing and gave one piece of feedback — a character count, which is the
only failure that did not matter. An opportunity space is a vertical × use case
× technology plus a buyer's problem and a place, and somebody who knows their
market but not this taxonomy under-specified two of those every time; they found
out minutes later, from a run that created nothing. The assistant interviews
instead, with the corpus in front of it, and shows what each turn retrieved —
publisher, date and cosine — beside the conversation. The Generate button is
enabled by the corpus rather than by the assistant's opinion of itself, and
where the two disagree the screen says so in either direction. The parameters
route is still there for somebody who does know the taxonomy, and it shows the
spaces that _already_ match before spending a run on rediscovering them.

**The brief view** is the middle pane rendering the PDF inline, with Download,
Regenerate and a staleness warning when the topic has moved past the version the
brief was built against. Showing it beside the radar rather than only offering a
download is what makes anyone notice it is out of date.

**Market opportunity and competition** appear in the detail pane as the working,
not just the number: TAM/SAM/SOM with their ranges, every factor with its source,
year and basis badge, the caveats behind a disclosure, and per competitor the
signals that name them.

**Signing in** is a screen of its own, rendered instead of the radar rather than
over it: every panel behind it opens by fetching, and mounting them for a
signed-out visitor means a dozen requests that all answer `401`, painting the
error state of eight panels behind a login form. One refusal message covers both
an unknown account and a wrong password — a sign-in form that distinguishes them
is a staff directory with a slow interface.

**Deleting a space** sits at the bottom of the detail pane, behind its own rule,
because every other control there is reversible and that one is not. The dialog
asks the server what would go and reads the answer out first: thirteen tables
point at a space, and "are you sure?" over a number nobody was shown is not a
confirmation. It also says what is _not_ lost — the signals are shared evidence
and stay — and that a later refresh meeting the same taxonomy triple will
synthesise the space again, because identity is the triple (DR-03) and deleting
is a statement about the corpus as it stands, not a permanent veto.

Deep links work: `?topic=OS012&role=presales&theme=dark`, and `?tab=brief` opens
the brief for the selected space.

---

## Deployment

The radar runs as a single Azure App Service: one process serving the read API
and the built React bundle from the same origin, which is what the CORS list in
`api.py` was always scoped for.

```bash
./scripts/deploy-azure.sh          # build, package, provision if needed, push
```

|                |                                                                                       |
| -------------- | ------------------------------------------------------------------------------------- |
| Subscription   | Azure for Students (`9ca89421…`), tenant `33ac9060…`                                  |
| Resource group | `rg-railpulse-cloud`                                                                  |
| Region         | France Central                                                                        |
| Plan / app     | `plan-railpulse-cdb4ce` (F1, Linux, shared) / `web-orange-radar-1521f5`               |
| Runtime        | Python 3.13, `python3 -m uvicorn main:app` (no script, no absolute paths — see below) |

Three deployment decisions worth recording, because each is a constraint someone
will otherwise rediscover:

**Where it runs.** The subscription carries an `Allowed resource deployment
regions` policy — Italy North, France Central, Germany West Central, Poland
Central, Spain Central, all EU, which suits a product whose strategic frame is
sovereignty. The radar shares `plan-railpulse-cdb4ce` with the RailPulse app: a
Free plan hosts up to 21 sites and the two draw on the same 60 CPU-minutes a day.
Giving the radar its own plan means paying for one — B1 is about USD 13/month:

    RG=rg-orange-radar PLAN=plan-orange-radar SKU=B1 ./scripts/deploy-azure.sh

**Nothing may raise at import, and no bash wrapper.** These two are one lesson.
A container that exits is restarted, fifteen restarts exhaust the Free plan's
`WP stop requests` quota, and that quota **also disables Kudu** — so a crash loop
erases the logs that would explain it. Five deployments failed that way before
the design changed to make it impossible:

- The startup command names **no absolute path and no console script**:
  `python3 -m uvicorn main:app`. This is the one that cost five deployments, and
  the cause is not obvious. App Service does not run the deployed tree in place.
  Oryx builds it, compresses the result to `output.tar.zst`, and on _every_
  container start extracts that tarball to a fresh `/tmp/<hash>` which becomes
  the working directory. `/home/site/wwwroot` holds the tarball and nothing
  else, and the extraction path changes with each deploy — so no absolute path
  into `wwwroot` is ever valid at runtime, not for a startup script, not for
  `PYTHONPATH`, not for a module. Every such command exits **127** before
  printing anything. `python3 -m` resolves through `PYTHONPATH` (which Oryx
  points at the extracted virtualenv) rather than `PATH` (which it does not
  extend), and `main.py` puts its own sibling `src` on `sys.path`, so both
  resolve relative to wherever the tarball happened to land.
- Everything that wrapper used to do — seeding `/home/data/radar.db` from the
  package, converting its journal mode, copying the briefs — is in
  `radar/bootstrap.py`, which runs inside the app, inside the venv, and catches
  everything it can hit.
- `api.py` no longer dies when the database is unusable. It records the error
  and `/healthz` answers **503 with the reason**, so a bad deployment describes
  itself over HTTPS instead of disappearing.
  **What a redeploy replaces, and what it never touches.** The database is seeded
  onto `/home` once and then _not_ replaced, so a deployment cannot discard the
  feedback and workflow decisions production accumulated. That protection is right,
  and taken alone it is also why 62 briefs once sat on disk that nobody could open:
  the PDFs shipped, the rows that make them visible did not. So `bootstrap` brings
  `CONTENT_TABLES` forward from the package — the topics themselves plus
  `topic_descriptions`, `topic_briefs`, `topic_competition` and `market_sizes`.

Not unconditionally, and this is the part worth reading. An earlier version of
this took those tables wholesale on the strength of a comment claiming the UI
never writes them. That was false: `POST /api/topics/{id}/description|brief|
market-size|competition` all write them, and the shipped UI has a **Regenerate**
button wired to each. Taking them wholesale would have silently rolled back work
a curator paid a model call for, and charged them to do it twice. Every row is
therefore compared on its own timestamp and the newer one wins — the package is
authoritative for content it refreshed, production for anything regenerated
since. The PDFs follow the same rule from the other end: `content_hash` is the
SHA-256 of the file a row was written for, so the row decides which PDF belongs
on disk, and a brief regenerated in production is recognised and left alone.

Topics travel _with_ their content rather than being frozen, because
`opportunity_spaces.version` is what `brief_for_topic` compares against: shipping
new briefs against frozen topics flags every one of them "the topic has been
refreshed since". They are taken wholesale — the pipeline is their only writer.
`PRAGMA foreign_keys = OFF` is load-bearing here, not incidental: `INSERT OR
REPLACE` is a delete followed by an insert, and these tables are the parents of
`workflow_state` and `feedback` through `ON DELETE CASCADE`.

The sync is keyed on a SHA-256 of the packaged database and skipped when it
matches the marker in `/home/data/.content-fingerprint` — the container cold
starts far more often than it is deployed — and the marker is written only when
every table applied, so a partial sync is retried rather than recorded as done.
It is wrapped in its own `except`: stale content is worth serving, a crash loop
is not. `tests/test_bootstrap_sync.py` pins all of it, including the case that
matters most — a curator regenerates a brief, the next deploy lands, and their
work is still there.

- Briefs are resolved by **filename against the configured directory**, not by
  the absolute path recorded in `topic_briefs.path`. That column records the
  machine that _built_ the PDF — a laptop the server has never seen — so taken
  literally every brief 404s in Azure and the UI reports that none were ever
  generated. `resolve_brief()` falls back to `RADAR_BRIEF_DIR`, and both the
  file route and the metadata payload go through it so they cannot disagree.

**Reading the logs when Kudu is 403.** The deadlock above is escapable without
waiting an hour. Point the startup command at a static server over the whole
persisted tree —

    az webapp config set -g $RG -n $APP \
      --startup-file "python3 -m http.server 8000 --directory /home"

— and the container stays up (so the restart quota stops draining) while
`/LogFiles/*_docker.log` becomes readable over plain HTTPS. That is what finally
produced the `exit code 127` and the `can't open file` line above, after five
attempts spent guessing. Reach for it early, not late.

**SQLite cannot use WAL on `/home`.** This one cost a night. `/home` is the only
path that survives a restart on Linux App Service, and it is an SMB mount:
Azure Files. WAL needs shared memory that SMB does not provide, so opening a WAL
database there fails — and because `api.py` calls `init_schema()` at import, the
failure takes the worker with it. The platform restarts the worker, the worker
fails again, and after fifteen restarts the plan's hourly `WP stop requests`
quota is spent. At that point the app returns 403 `QuotaExceeded`, **and so does
Kudu**, so the logs that would explain it are unreadable until the quota resets.

The symptom is easy to misread as a Free-tier limitation — a second app on the
plan was even stopped to "free a slot", which changed nothing: the F1 plan runs
both apps side by side. It is not a resource limit — CPU sat at
0% of its daily allowance throughout. `db.py` therefore takes
`RADAR_SQLITE_JOURNAL_MODE` (default `WAL`, set to `DELETE` in App Service),
`radar.bootstrap` converts the seeded copy before its first write, and writes its own log to
`/home/LogFiles/radar-startup.log`, which survives a container that does not.

**What is not deployed.** The serving package carries no pipeline dependencies:
`radar.api` imports scikit-learn, sentence-transformers and the OpenAI client
only inside the functions that need them, so a serving instance never loads
torch. That is a 28 MB package instead of a multi-gigabyte one, and on the Free
tier it is the difference between starting and not. Discovery stays a local
batch job against the same SQLite file; deploying is the publish step.

**What persists.** `/home` is the only path that survives a restart or a
redeploy on Linux App Service, so the database and generated briefs live in
`/home/data`. `radar.bootstrap` seeds it from the package on first boot and then
leaves it alone — feedback, assessments, descriptions and briefs created in
production are not thrown away by the next push. The replay archive
(`raw_items`) is dropped from the serving copy: it exists so the pipeline can be
re-run as of a past date (DR-14, FR-35), which is not something the API does,
and it is half the file. Every citation still resolves.

**Secrets** are App Settings, read from the local `.env` at deploy time and never
written into the package. The `.env` itself is excluded.

**If the site answers 403 and the portal says `QuotaExceeded`,** it is almost
certainly a crash loop rather than a resource limit. Check which quota before
assuming it is CPU:

```bash
az rest --method get --url "https://management.azure.com/subscriptions/$SUB/resourceGroups/\
rg-railpulse-cloud/providers/Microsoft.Web/serverfarms/plan-railpulse-cdb4ce/usages?api-version=2022-03-01"
```

During this deployment the answer was `WP stop requests: 41 / 15` while CPU sat
at 0% — a container failing to boot, restarted until the cap was reached. It
clears on the hour. Redeploying to fix it makes it worse: stop the app first,
which ends the loop, then read `/home/LogFiles/radar-startup.log` once the quota
allows Kudu to answer again.

### Before this goes anywhere real

The app now requires a sign-in (`src/radar/auth.py`). Every `/api` path is behind
a session; the built bundle and `/healthz` are not, because the login screen has
to load before anyone can sign in and a liveness probe that answers `401` makes
every deployment look unhealthy. The session is an `HttpOnly`, `SameSite=Lax`
cookie whose value is stored only as a SHA-256, and passwords are PBKDF2-HMAC-SHA256
verifiers at OWASP's current iteration count — so a copy of the database file is
neither a set of passwords nor a set of live logins, which matters when the
database _is_ a file on a share.

Two things that were true before it and are still worth acting on:

- **The shipped account is `orange` / `orange`.** It exists so a fresh database
  is usable without a shell, it is flagged `must_change_password`, and the
  interface carries a banner until it is changed. Change it on first sign-in.
- The generation endpoints (`POST /api/topics/{id}/description`, `POST
/api/topics/{id}/brief`) call the configured model with the deployed key, so
  anyone who _can_ sign in can spend it. The key in question was shared in
  plaintext over chat during development and should be rotated regardless.

Defence in depth is still worth having — a password is one factor, and the
platform can add a second in one command:

```bash
# Only your address may reach it
az webapp config access-restriction add -g rg-orange-radar -n web-orange-radar-1521f5 \
  --rule-name office --priority 100 --action Allow --ip-address "$(curl -s ifconfig.me)/32"

# Or require a Microsoft Entra sign-in from the tenant
az webapp auth update -g rg-orange-radar -n web-orange-radar-1521f5 \
  --enabled true --action RedirectToLoginPage --redirect-provider AzureActiveDirectory
```

---

## Tests

```bash
python3 -m pytest tests/ -q      # 486 tests
```

They cover the invariants that would be expensive to discover late: score
reproducibility (SC-11), syndication collapse and tier-4 discounting (SC-03),
vendor-only evidence scoring low (SC-09), evidence binding stripping uncited
claims, specificity validation rejecting the briefing's named negative examples,
triple-based identity and merge, link typing and portfolio distance, horizon
derivation, the lifecycle state machine, evidence-gap warnings (SC-13), and
publication-date leakage control (FR-35).

The competitor suite (23 tests) holds the line on the newest subsystem: that a
vocabulary tag the model supplied is dropped unless the pages corroborate it;
that a named offer citing a page the page does not support is dropped; that a
differentiation paragraph naming an unlinked Orange asset is stripped while the
activity half survives; that a competitor absent from the topic cannot be added
by the model; that a competitor whose site refused us is _marked_ rather than
omitted; and that re-running the cheap join never discards an expensive
comparison that still holds.

The sizing, competition and brief suites (48 tests) hold the same kind of line:
that the denominator and the adoption rate share a size base; that a crosswalk's
per-row confidence reaches the arithmetic rather than sitting in the CSV; that
only a tender whose _main object_ is an IT contract may price an engagement; that
a proxy widens the range without moving the base; that the confidence grade is
the worst factor rather than an average; that SAM never exceeds TAM; that an
uncited factual section is stripped; that a generated percentage or euro figure
kills the section carrying it; that an unsupplied organisation does the same; and
that a diagram box cannot claim an Orange asset the graph does not hold.

The planner, collateral, scoping, auth and deletion suites (137 tests) hold the
newest lines: that identical inputs give an identical plan id, so a plan cannot
be silently recomputed under changed assumptions; that a capability pool is never
over-committed under the optimiser and _is_ reported when a committed set
over-commits it; that `selected_count == considered_count` under the workflow
source, because nothing there may be dropped; that a committed space with no
market size is declared rather than quietly missing; that **every text frame on
every generated slide fits its box**; that a collateral piece with a missing
input still builds and says so; that a second format coexists with the first
rather than replacing it; that `ready` on a proposed brief is the corpus's
verdict rather than the model's; that a brief corroborated only on its vertical
is refused; that signals survive a delete while their attachments do not; and
that a plan which selected a deleted space is named rather than blocking the
delete.

The auth suite is worth one more sentence, because of _how_ it tests. It **walks
the router** rather than naming endpoints, so a route added without the guard
fails a test that already exists. The failure mode of a per-route guard is the
route somebody forgot, and a test that names endpoints has exactly the same
failure mode.

Several of these tests caught real bugs during the build:

- Shannon entropy is scale-invariant, so a uniform tier-4 discount cancelled out
  entirely — six vendor blogs scored identically to six independent outlets.
  Fixed by applying the discount to the effective publisher count.
- Certifications were typed L0, making portfolio distance meaningless for every
  topic in a regulated vertical.
- `build_graph` wiped `graph_nodes` while `opportunity_links` held a foreign key
  onto it, so a second rebuild failed. Fixed by upserting nodes and retiring the
  disappeared ones — which is also where LK-07 (withdrawn assets propagating to
  affected topics) now lives.
- The exploration slot (§4.7.6) drew from all filtered topics rather than
  role-eligible ones, so it could show a salesperson a topic with no proof point
  — bypassing the very filter §4.5.3 requires.
- A slide test that checked only the bullet column passed while four chart labels
  on the same slide overflowed off the edge. It now walks _every_ text frame on
  every slide, which is what should have been asserted the first time.
- The scoping gate corroborated a brief against its taxonomy **labels**, and the
  labels are approximations — closed lists of 15 verticals, 59 use cases and 32
  technologies mean a proposal is filed under the nearest available cell. Tenders
  for private-5G video surveillance duly "corroborated" a brief about
  advertising-funded municipal screens, the button enabled, and the critic threw
  out every candidate the run produced. The gate now judges the brief's own
  sentence.

---

## What is deliberately not built

Matching the MVP exclusions in Table 15, plus what this pass did not reach:

| Not built                   | Why                                                                                                                                                                                                                       |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CRM integration             | Deferred by the briefing; public assets give a sufficient right-to-win proxy                                                                                                                                              |
| Learned scoring models      | No labels exist on day one. The MVP ships the transparent baseline and the capture/replay harness the learned models need (§4.7)                                                                                          |
| Patent connector            | Needs EPO OPS registration or BigQuery credentials. Technology ownership currently uses a portfolio-level prior from `technologies.yaml`                                                                                  |
| Headless-browser rendering  | Three competitor sites render client-side only. Adding a browser to a pipeline that deliberately has none, for three profiles of sixty-five, is not the trade                                                             |
| Learned per-role ranking    | Needs 300–600 expert comparisons; the capture widget ships first                                                                                                                                                          |
| Backtest evaluation harness | The replay path exists (FR-35); the metrics of §4.7.5 are not implemented                                                                                                                                                 |
| Per-role authorisation      | Sign-in answers _who_; it does not yet answer _may they_. Every signed-in account can currently move a stage, delete a space and spend model budget                                                                       |
| Rate limiting on generation | Sign-in bounds who can reach the endpoints that spend model budget, not how often they may                                                                                                                                |
| ROI on a plan               | There is no cost data at the granularity a space would need — not in the filings, not anywhere the pipeline can reach. Revenue and profit are defensible from what exists; an ROI would require inventing the denominator |

Two rows moved out of this table during this pass and are worth naming, because
both were listed as _not built_ in an earlier edition of this README:
**collaboration workflow (FR-25)** is the stage gate and per-role assessment
described above, and **slide export** now exists — not as a PowerPoint variant of
the brief, but as four of the twelve pre-sales artefacts, which is what the
request was actually for.

---

## Open questions for Orange

§4.13 lists thirteen. The four that most affect the code as written:

1. **Refresh cadence** — drives connector design and cost more than any other
   decision. Currently `period_days: 14`.
2. **Sovereign deployment** — may an external model API be used during the MVP?
   The abstraction supports Ollama today; the question is whether it must be
   exercised now.
3. **Internal taxonomies** — the 59 use cases and 38 technologies are a drafted
   Sprint 0 deliverable. If an internal catalogue exists it should replace them.
4. **Who is the curator?** 5,217 links are currently unconfirmed. LK-06 requires a
   named human to adjudicate the first occurrence of each link pattern, and
   without one, quality drifts. The same question now applies twice over: the
   sizing assumptions in `config/sizing.yaml` (contract duration, size-class
   weights, obtainable share) and the 65-entry competitor register both carry
   `innovation-radar-curator` as a placeholder owner, and both will appear in
   front of customers.
5. **Is the four-year contract assumption right?** TED publishes a contract's
   whole value, and annualising it needs a duration. Four years is the figure
   used and printed; an Orange bid team will have a better one, and every size in
   the radar moves inversely with it.
6. **May a browser user agent be used for competitor profiling?** Six competitor
   sites — including Cisco and Fortinet — answer 403 to a declared automated
   client. A browser agent gets through all of them, and not using one costs
   twelve profiles that thin the competitive picture on security spaces most.
   Recorded as a refusal rather than routed around; the decision is Orange's.

7. **How wide is the private-sector proxy?** Contract values are observed from
   public procurement because that is the only attributable source available.
   Where Orange has its own won-deal distribution, substituting it would move
   these estimates off a proxy and onto evidence.

---

## Security note

`.env` is gitignored and holds the DeepSeek API key supplied for development.
That key was shared in plaintext over chat, so **rotate it before any wider
use**, and issue a separate key for CI.

Every `/api` path now requires a session (`src/radar/auth.py`), which closes the
two things that made a public deployment unsafe to show anyone: it answered every
request it received, and anyone with the URL could spend the deployed model key.
The guard is an application-level dependency rather than a decorator per route,
because the failure mode of a per-route guard is the route somebody forgot, and
`tests/test_api_auth.py` walks the router instead of naming endpoints for the
same reason.

Three things are still absent and are named rather than implied:

- **Per-role authorisation.** Sign-in answers _who_, not _may they_. Every
  signed-in account can move a stage, delete a space and spend model budget.
- **Rate limiting on the generation endpoints.** Sign-in bounds who reaches them,
  not how often.
- **An audit log** distinct from the workflow transition history.

The seeded account is `orange` / `orange`, flagged `must_change_password`, and
the interface warns on every screen until that is cleared. Accounts are created
only from the command line (`radar user add`), so a hijacked session cannot mint
itself a permanent login.
