# Interview guide

Concise answers to the six project questions, with the evidence and implementation reasoning behind them.

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
   → [Evidence before generation](IMPLEMENTATION_GUIDE.md#evidence-before-generation-41)

2. **Four quantities that are never collapsed into one, each explaining itself
   on demand.** Attractiveness (is the world moving), right to win (can we play),
   conviction (do our own people believe it) and competitive intensity (how
   crowded is it) travel as separate fields end to end and occupy separate visual
   channels. Every space carries a **How was this calculated?** modal that shows
   the stored inputs and the arithmetic — the publishers counted, the tier
   distribution, the per-period buckets the momentum slope was fitted to, the
   rubric level and its rationale, the named offers behind right-to-win — plus
   the weight set, pipeline, prompt and model that produced it.
   → [Explaining a score, per topic](IMPLEMENTATION_GUIDE.md#explaining-a-score-per-topic)

3. **Market size computed from published statistics, never quoted from a press
   release.** Two independent methods side by side — enterprises × adoption ×
   engagement value from Eurostat, and annualised contracts that actually exist
   from TED — with every factor carrying its dataset, year and basis. SAM is
   _computed_ rather than discounted by a fudge factor. The confidence grade is
   the **worst** basis among the factors, never an average, and where nothing
   attributable exists no number is published: 531 of 752 computations are graded
   `observed`, 145 `partial`, 76 `modelled`.
   → [Market size, with the working shown](IMPLEMENTATION_GUIDE.md#market-size-with-the-working-shown-434)

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
   → [Competitor intelligence](IMPLEMENTATION_GUIDE.md#competitor-intelligence--what-they-say-they-sell-433-extension)

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
   → [The Planner](IMPLEMENTATION_GUIDE.md#the-planner-and-what-it-is-allowed-to-promise)

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
→ [What is deliberately not built](QUALITY_LIMITATIONS_AND_SECURITY.md#what-is-deliberately-not-built) ·
[Open questions for Orange](QUALITY_LIMITATIONS_AND_SECURITY.md#open-questions-for-orange)

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
[Tests](QUALITY_LIMITATIONS_AND_SECURITY.md#tests) section, and two are worth repeating here because they were
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
→ [Two scores, never one](IMPLEMENTATION_GUIDE.md#two-scores-never-one-sc-12) ·
[Explaining a score](IMPLEMENTATION_GUIDE.md#explaining-a-score-per-topic)

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

