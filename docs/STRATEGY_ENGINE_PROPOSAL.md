# Proposal — the strategy engine

*An automated business plan: given a budget and a few preferences, select the
portfolio of opportunity spaces Orange should expand into, and say what it is
expected to return.*

**Status: proposal. Nothing here is built.**

---

## 1 · The question is portfolio construction, not ranking

The radar already ranks. Every role mode orders 418 spaces by a blend of
attractiveness, right to win, proof-point density and portfolio distance. If the
strategy engine were only "rank harder", it would be a fourth role mode and not
worth building.

The question a business plan asks is different in kind:

> Given **€X** over **five years**, which **set** of spaces should Orange invest
> in, in what **sequence**, and what does that set return?

Three things make *set* selection different from ranking, and all three are
places where a per-topic ranking gives the wrong answer:

**Shared build cost.** Three spaces that all need the same capability pay for it
once. Ranked independently, each carries the full build and all three look
marginal; selected together, the second and third are nearly free. On the current
data this is not hypothetical — 40 spaces sit at L3 (one capability to build) and
they cluster heavily on a handful of technologies.

**The reference flywheel.** Right to win includes reference density in the
vertical. Winning the *first* deal in a vertical raises right-to-win for every
other space in it, which raises their obtainable share. That makes **sequence** a
decision variable, not an afterthought — and a ranked list has no way to express
"do this one first because it unlocks four others".

**Concentration risk.** The top of any ranked list will be correlated: same
vertical, same technology, same regulatory driver. A plan that is nine-tenths
sovereign cloud is one procurement-policy change away from being wrong in its
entirety. Diversification is a property of the set and is invisible per topic.

**So: an optimiser over the portfolio, not a better sort.**

---

## 2 · What the radar can already answer

| Available today | Coverage |
|---|---|
| Market size TAM / SAM / SOM, low·base·high, with a confidence grade | 313 estimates over 181 spaces; **175 at `observed` confidence** |
| Attractiveness, 5 components with stored inputs | all spaces |
| Right to win, 7 components, from the business graph | all spaces |
| Competitive intensity + named competitors + what they publish | 181 spaces |
| Portfolio distance L0–L4 | L0 121 · L1 228 · L2 29 · L3 40 |
| Time horizon now / next / later | 161 · 157 · 100 |
| Strategic relevance against *Trust the future* | all spaces |
| Geography, vertical, use case, technology, persona | all spaces |
| Orange assets: 14 offers, 15 partners, 18 references, 6 certifications, **7 capability pools** | business graph |

That is a genuinely strong basis for **selection**. It is enough to answer "which
set, under these constraints, maximises expected obtainable revenue while
respecting risk and concentration limits" — today, with no new data.

### What it cannot answer

**There is no cost data anywhere in the system.** No build cost, no cost to
serve, no delivery margin, no sales cost, no headcount requirement, no capex/opex
split. I checked the schema and every configuration file.

ROI is `(return − investment) / investment`. The radar models the numerator and
has **no denominator at all**. This is the single most important fact in this
proposal and section 4 is about closing it.

---

## 3 · Input parameters

The user named three — investment size, region, domain. Those are right and not
sufficient. Grouped by what they actually do to the answer:

### 3.1 Hard constraints — these bound the feasible set

| Parameter | Why it changes the answer |
|---|---|
| **Investment envelope** (€ total) | The budget line of the knapsack. Everything else is secondary to it. |
| **Envelope by year** (or a ramp) | €50m available as €10m/year is a different plan from €50m in year one. Constrains how many L3 builds can run concurrently. |
| **Plan horizon** (3 / 5 / 7 years) | Determines how much of a slow-ramping space counts. A 3-year plan structurally excludes most `later` spaces. |
| **Delivery capacity** by capability pool | The radar knows 7 pools. Two simultaneous builds needing the same scarce pool is infeasible regardless of budget — the constraint people discover in month four. |
| **Minimum size confidence** | Admit only `observed` (175 spaces), or allow `partial`. Planning on a `modelled` size is planning on an assumption twice over. |
| **Geography scope** | Which markets Orange will actually sell in. Also gates the sovereignty premium. |
| **Mandatory exclusions** | Verticals or technologies that are off the table for policy reasons, stated rather than silently down-weighted. |

### 3.2 Steering preferences — these shape it within the feasible set

| Parameter | Effect |
|---|---|
| **Risk appetite** | The cleanest single dial. Conservative → L0/L1, `observed` sizes, `now` horizon, low competitive intensity. Aggressive → admits L3/L4, `partial` sizes, `later`. |
| **Horizon mix target** | Three-horizons discipline: e.g. 70% Now / 20% Next / 10% Later of budget. Prevents an optimiser from spending everything on safe near-term wins — the classic failure mode of any NPV-ranked plan. |
| **Margin vs volume** | `strategy.yaml` already states the divisional guidance is `margin_over_volume`. Should be an explicit dial, not a buried default. |
| **Vertical / domain preference weights** | Not just include/exclude — a weight, so "prefer defence and health" (both named investment areas in *Trust the future*) tilts without excluding. |
| **Ambition weighting** | Which of the three *Trust the future* ambitions to serve. Innovative growth carries `b2b_weight 1.0`; the other two are 0.4 and 0.7. |
| **Build vs partner vs acquire** | Changes the cost and the time-to-revenue of every L2/L3 space. A partner-first posture makes L2 cheap and L3 expensive. |
| **Competitive posture** | Avoid crowded fields, or attack them where Orange has a named differentiator. The competitor analysis now supplies the evidence for the second. |
| **Sovereignty requirement** | Hard filter or a scoring premium. Given the strategic frame, probably a premium rather than a filter. |
| **Concentration limits** | Max share of budget in any one vertical / technology / horizon. The diversification control. |
| **Cannibalisation tolerance** | How much overlap with existing Orange revenue is acceptable. Needs the baseline in 4.2. |

### 3.3 The objective — what is being maximised

This must be **stated, not assumed**, because different objectives give
materially different portfolios:

- Maximise 5-year **revenue**
- Maximise 5-year **gross margin** (needs cost data)
- Maximise **risk-adjusted NPV** (needs cost data and a discount rate)
- Maximise **strategic coverage** — presence across the evidenced grid, accepting
  lower return for optionality
- Maximise **defensibility** — weighted toward spaces where Orange has a
  structural differentiator against the named competitors

My recommendation: default to risk-adjusted NPV once costs exist, expose the
others as alternatives, and **always show at least two** so the user sees that
the choice of objective is itself a decision.

---

## 4 · What ROI needs

### 4.1 Configurable now, with a named owner

Each of these can be a band in a versioned config file, exactly as
`config/sizing.yaml` already does for contract duration and obtainable share —
an assumption with an owner, printed wherever the number appears.

| Input | Proposed form | Notes |
|---|---|---|
| **Build cost by portfolio distance** | Band per L-level | L0 ≈ 0 (the offer exists); L1 = packaging; L2 = partner onboarding + integration; L3 = capability build; L4 = new business build. The single highest-leverage assumption in the model. |
| **Cost to serve / delivery gross margin** | % by offer family | Orange finance has this; a placeholder band gets the model running. |
| **Sales cost and cycle length** | € per deal, months | Varies sharply by vertical and deal size. |
| **Ramp curve** | S-curve per horizon | `now` reaches steady state fast; `later` may not start inside the plan window at all. Currently the radar has a horizon *label* and no ramp. |
| **Win rate** | % by portfolio distance × competitive intensity | The radar's own two most decision-relevant variables. Starts as an assumption; becomes calibrated in phase 3. |
| **Discount rate (WACC)** and hurdle rate | single figures | Standard. |

With only these, a defensible five-year projection is possible. It would be a
**scenario**, not a forecast — see 4.3.

### 4.2 Needs Orange data the radar does not have

| Input | Why it matters | Where it lives |
|---|---|---|
| **Existing revenue baseline** by vertical / offer | Distinguishes incremental revenue from cannibalisation. Without it, a plan can "win" revenue Orange already has. | Finance |
| **Historical win rates** and lost-deal reasons | Turns win rate from assumption to evidence, and the lost-deal reasons feed the radar as internal signals. | CRM |
| **Realised pricing** vs tender values | Sizing prices engagements from public tender medians. Realised price differs, systematically. | Finance / bid team |
| **Contract length, renewal, churn** | Five-year value is not five times year-one. | Finance |
| **Capacity by capability pool** in FTE | Converts the capacity constraint from notional to real. | Delivery |
| **Partner economics** | Revenue share on L2 spaces changes their attractiveness materially. | Alliances |

### 4.3 The honesty problem, and how to handle it

A five-year ROI here is **a model of a model**. SOM is already a planning
assumption (a share band anchored on right-to-win × portfolio distance). Multiply
it by an assumed cost band, an assumed ramp and an assumed win rate, and the
uncertainty compounds four deep.

Producing a single confident number from that would be precisely the failure this
product exists to prevent — the same failure it refuses to commit when it declines
to quote a press market-size figure.

So the projection must:

- **Carry its interval.** SOM already has low·base·high. Propagate it, do not
  discard it. Monte Carlo over the assumption bands, report P10 / P50 / P90.
- **Show what moves it.** A tornado chart over the input assumptions. If the
  answer is dominated by the build-cost band, the user is looking at a plan whose
  real content is one unvalidated number, and should be told.
- **Grade itself**, on the same worst-factor rule sizing already uses: a
  projection is only as good as its weakest input.
- **Never be called a forecast.** "Scenario under stated assumptions", with the
  assumptions and their owner on the same page.

---

## 4b · What Orange's own filings actually provide

*Checked against the 2025 Universal Registration Document (576 pages, filed with
the AMF on 2 April 2026) and SEC EDGAR. Every figure below is quoted from the
URD, not recalled.*

### First, a dead end worth recording

**Orange deregistered from the SEC in October 2024** (Form 15F-12B, Form 25).
EDGAR holds nothing after the H1 2024 report, so the `sec_edgar` connector — which
the radar already runs for *other* companies' filings — is not a route to current
Orange financials. The AMF filing is the only one.

### What the URD gives, and it is more than expected

**Orange Business segment, FY2025** (§3.1.3.4, page 143):

| Metric | 2025 | 2024 | Change |
|---|---:|---:|---|
| Revenue | €7,325m | €7,777m | −5.8% historical |
| — Fixed-only services | €2,715m | €2,958m | −8.2% |
| — IT & integration services | €3,698m | €3,828m | −3.4% |
| — Mobile services and equipment | €912m | €990m | −7.9% |
| **EBITDAaL** | **€577m** | €624m | −7.5% |
| **EBITDAaL / revenue** | **7.9%** | 8.0% | −0.1 pt |
| Operating income | **−€277m** | €303m | goodwill impairment of €332m |
| **eCAPEX** | €279m | €323m | −13.6% |
| **eCAPEX / revenue** | **3.8%** | 4.1% | −0.3 pt |
| Investments in PP&E and intangibles | €383m | €326m | +17.5% |
| **Average number of employees** | **29,415** | 30,150 | −2.4% |

Orange Cyberdefense revenue is broken out separately at **€1,252m, +6.8%** — the
only growing line inside a declining segment. Orange Business restructuring costs
in 2025 were **€108m**, and specific labour expenses for the French part-time
seniors plan **€165m**.

**The discount rate, published** (Note 7.3, page 221). Orange discloses the rates
used to impairment-test each cash-generating unit. The "Enterprise" CGU *is*
Orange Business:

| CGU | Post-tax discount rate | Pre-tax | Perpetuity growth |
|---|---:|---:|---:|
| **Enterprise (Orange Business)** | **7.3%** (2024: 7.1%) | **9.7%** (2024: 9.2%) | **0.5%** |
| France | 5.9% | 8.1% | 0.8% |
| Poland | 7.2% | 8.5% | 2.0% |

This is Orange's own audited cost of capital for this business, disclosed
annually, with a prior year for the trend. **It closes the WACC input completely
and better than any assumption we would have made** — and the fact that the rate
*rose* from 7.1% to 7.3% is itself part of why the segment took a €332m goodwill
impairment.

### Mapping filings onto the twelve cost inputs

| Input | Status after the filings |
|---|---|
| **Discount rate / WACC** | ✅ **Closed.** 7.3% post-tax, 9.7% pre-tax, published annually per CGU. |
| **Existing revenue baseline** | ✅ **Largely closed** at line-of-business level: connectivity €2,715m, IT & integration €3,698m, cyberdefence €1,252m. Enough to test a plan for cannibalisation at portfolio level, though not per opportunity space. |
| **Capex intensity** | ✅ **Closed as a ratio.** 3.8% of revenue, with a five-year history available. A usable prior for the capex share of a build. |
| **Headcount base** | ✅ 29,415 average FTE, trending −2.2%/yr. Divided into capability pools it is a capacity denominator. |
| **Blended cost per FTE** | 🟡 **Derivable** from Group labour expenses (€8,302m) but only Group-wide; the segment split is not disclosed. |
| **Delivery gross margin** | 🟡 **Bounded, not measured.** EBITDAaL margin of 7.9% is *after* SG&A and is a segment aggregate. It is a ceiling and a sanity check, not a per-offer delivery margin. |
| **Restructuring / transformation cost** | 🟡 Disclosed in total (€108m in 2025) but not attributable to a decision. |
| **Build cost by portfolio distance (L0–L4)** | ❌ **Not in any filing, and never will be.** This is management accounting, not statutory reporting. |
| **Cost to serve per offer** | ❌ Same. |
| **Sales cost / CAC / cycle length** | ❌ Same. |
| **Win rates** | ❌ Same — CRM, not filings. |
| **Ramp curves** | ❌ Same. |

**The honest summary: filings close three of the twelve inputs outright and
partially close four more — but every input that varies *per opportunity space*
is absent, and those are the ones that actually drive which spaces get selected.**
A filing tells you what the business costs in aggregate. It cannot tell you what
*this* space costs to enter, which is the question the optimiser asks 418 times.

Peer filings (Capgemini, Accenture, Atos/Eviden, T-Systems) would add
industry-standard delivery-margin benchmarks for the IT-services half of the
portfolio — useful as a cross-check on any assumed margin band, and the
competitor profiling subsystem already knows who those peers are.

### The most valuable thing the filings give is a reality check

The radar's aggregate obtainable market, taking one estimate per topic, is
**€3,908m across 181 sized spaces.** Orange Business's *entire* FY2025 revenue is
**€7,325m**.

The radar is therefore describing an obtainable opportunity worth **53% of the
segment's total current revenue** — while that segment is declining at 5.8% a
year on a 7.9% EBITDAaL margin.

That is not a defect in any single estimate. SOM is a per-topic planning
assumption and was never meant to be summed: topics overlap, the two sizing
methods double-count, and each share band is applied independently. But it does
establish something important for the strategy engine:

> **An aggregate plausibility constraint belongs in the optimiser.** A selected
> portfolio whose projected incremental revenue is a large fraction of the
> segment's existing revenue should be flagged automatically, against the filed
> figure. Without it, an optimiser maximising a modelled number will happily
> return a plan that is arithmetically optimal and commercially absurd — and it
> will look confident doing so.

This is the same discipline the sizing engine already applies to a single
estimate (declare the method, show the interval, grade the confidence), raised to
the portfolio level. It is cheap to implement, it uses a published figure that
refreshes annually, and it is the check most likely to prevent the strategy
engine's worst failure mode.

### What to do with this

1. **Take WACC from the URD** rather than assuming it, refreshed annually.
   Version it like `weight_set` — a projection built at 7.1% is not comparable to
   one built at 7.3%.
2. **Seed the baseline** with the three disclosed revenue lines, and treat
   cannibalisation against them as a first-class output.
3. **Use eCAPEX intensity and EBITDAaL margin as bounds**, clearly labelled as
   segment aggregates standing in for per-offer figures — a declared proxy that
   widens the interval, exactly as `sizing.yaml` handles a substituted Eurostat
   series.
4. **Ask Orange only for what filings genuinely cannot give**: the per-distance
   build cost, win rates by competitive intensity, and capacity by capability
   pool. That is a much shorter and more credible ask than the original list.

**Sources**
[2025 Universal Registration Document (PDF)](https://assets.orange.com/medias/domain12751/media101746/523989-ffp7njes6v-75.pdf) ·
[Publication announcement](https://www.globenewswire.com/news-release/2026/04/02/3267567/0/en/Orange-Publication-of-the-2025-Universal-Registration-Document.html) ·
[FY2025 results release](https://www.globenewswire.com/news-release/2026/02/18/3240477/0/en/orange-success-of-lead-the-future-2023-2025-strategic-plan-2025-objectives-fully-achieved.html) ·
[SEC EDGAR submissions for Orange](https://data.sec.gov/submissions/CIK0001038143.json)

---

## 4c · Revised: sales-and-profit projection replaces ROI as the phase-2 deliverable

ROI was the wrong target. It requires an investment figure that does not exist in
any form, and a projection built on an invented build-cost band is a restatement
of that band wearing a percentage sign. **Dropping the investment side and
projecting sales and profit instead is achievable, and the arithmetic was tested
rather than assumed.**

### What was tested

Running the projection over the spaces with an `observed` bottom-up size, at the
margin Orange files:

```
              Y1      Y2      Y3      Y4      Y5    5y cum
revenue       75     460   1,148   2,110   3,070    6,863
profit         6      36      91     167     243      542     (EUR m, at 7.9%)
```

Uncertainty compared with the ROI attempt:

| Formulation | Compounded spread |
|---|---:|
| ROI (investment invented) | **393×** |
| Sales + profit (investment dropped) | **37×** |

The investment side was most of the noise. What remains is the sizing band
itself — the median space has a SOM high/low ratio of **29.9×** — which is
declared uncertainty propagated honestly, not error introduced by the model.

### The margin question is the real modelling choice

7.9% is the Orange Business **EBITDAaL margin**: fully loaded, after all
overhead, at segment level. Applying it to incremental revenue asserts that new
business carries the same overhead as existing business. That is defensible and
systematically wrong in both directions:

* **L0/L1** sell an existing offer on existing overhead. True contribution margin
  is higher, so 7.9% **understates**.
* **L3** requires a capability build whose cost lands in operating expense. True
  margin is lower, so 7.9% **overstates**.

Portfolio distance is exactly the variable that should modulate this, and the
radar already carries it. On illustrative bands, varying margin by distance moves
five-year profit by **1.66×** on that modelling choice alone — and the revenue is
heavily concentrated at L0, so the L0 margin dominates the answer.

**One small table from Orange finance — margin by portfolio distance — is worth
more to this model than any other single input, including build cost.**

For context on why the segment figure and not the Group one: Group EBITDAaL
margin is **30.9%**, driven by the infrastructure businesses. Using it for B2B
opportunity spaces would overstate profit roughly fourfold.

### What is still missing

Only the **ramp curve** — one S-curve per horizon, currently assumed, worth
±0.5–1.3×. Neither it nor the margin table is commercially sensitive, which makes
this a far more credible ask than the original twelve-item list.

---

## 4d · Sizing coverage: what was closed, and the hard limit

The projection is only as broad as the sizing. Coverage was extended across the
whole radar:

| | Before | After |
|---|---:|---:|
| Spaces with any size | 181 | **418 (all)** |
| Bottom-up at `observed` | 44 | **110** |
| Procurement-observed | 175 | **387** |

### Why it cannot be 418, and never will be

`observed` is not a setting. It is a statement that **every factor came from a
dated, attributable series**, and the grade is the worst factor rather than an
average. The remaining estimates are capped by the evidence, not by effort:

| Cause | Count | Fixable? |
|---|---:|---|
| Adoption rate is a declared **proxy** series | 133 partial | Only with a new statistical source |
| **Too few matching tenders** for a contract value | 71 modelled | Yes — broader CPV crosswalk coverage |
| Geography **outside Eurostat** (US and others) | 57 partial, 26 modelled | Only with non-EU reference data |
| Adoption read from the **all-activities aggregate** | 38 partial, 28 modelled | Only with finer series |

The hard limit is structural. **Eurostat's enterprise ICT survey contains no
NACE K (finance) or Q (health) codes at all** — verified directly against the
56,385 stored observations. So:

| Vertical | Bottom-up `observed` |
|---|---|
| Manufacturing / energy / transport / construction | 52–60% |
| **Healthcare (28 spaces)** | **0%** |
| **Financial services (27 spaces)** | **0%** |
| Wholesale, natural resources, media | **0%** |

No amount of engineering changes this. Marking those `observed` would falsify the
one field whose entire job is to tell a reader how much to trust the number —
which is the same reason the sizing engine already refuses to publish a
bottom-up figure for public administration.

**What would legitimately raise coverage**, in order of value:

1. **Broader CPV crosswalk coverage** — closes most of the 71 `modelled`, and is
   entirely within the team's control.
2. **OECD / national statistics offices** for finance and health — would unlock
   55+ spaces that Eurostat structurally cannot serve.
3. **Non-EU reference data** for the US and other geographies.

---

## 4e · SOM is not additive, and this constrains the whole design

Extending coverage produced a finding that changes the optimiser's requirements.

| Basis | Year-5 revenue as % of Orange Business segment revenue |
|---|---:|
| 110 `observed` spaces | **42%** |
| 243 `observed` + `partial` | **90%** |
| Top 10 spaces only | **28%** |

Orange Business revenue is €7,325m and **declining 5.8% a year**. An incremental
year-5 revenue of 42% of the segment is not plausible; 90% is not arguable. And
critically, **more coverage makes the aggregate worse, not better** — which
proves the problem is the aggregation, not the coverage.

The cause is structural and was always latent: SOM is a per-topic obtainable
share, applied independently to each space. Spaces overlap in the market —
several compete for the same customer's same budget — so summing them
double-counts. Each estimate can be individually reasonable while the sum is
nonsense.

**Three consequences for the design:**

1. **The optimiser must never report a naive sum.** An overlap adjustment is
   required — at minimum, de-duplicating addressable spend where selected spaces
   share a vertical and a buying centre.
2. **The aggregate plausibility check is not optional.** Any selected portfolio
   must be tested against the filed segment revenue and flagged when the
   implied growth is not credible. Even a top-10 selection trips this today.
3. **Concentration limits are proven necessary, not theoretical.** Ranking by SOM
   alone puts **18 of the top 20 spaces in manufacturing**. Without an explicit
   constraint, the optimiser returns a single-vertical plan and calls it a
   portfolio.

That third point is the clearest argument in this document for building an
optimiser rather than a ranked list.


---

## 5 · Method — and why not machine learning

The user asked whether an ML model needs training on the opportunity-space data.
**For the selection itself: no, and I'd argue against it.**

### Why optimisation is the right tool

Portfolio selection under a budget constraint is a **multi-dimensional knapsack**
— a well-understood integer program:

```
maximise    Σ  value(topic) · x(topic)          x ∈ {0,1}
subject to  Σ  cost(topic) · x(topic)  ≤  budget
            Σ  capacity_demand(topic, pool) · x ≤ capacity(pool)   ∀ pool
            Σ  x(topic ∈ vertical v)           ≤  concentration_limit  ∀ v
            Σ  budget(horizon h)               ∈  [target_h ± tolerance]
            shared-build cost counted once per capability
```

At 418 topics this solves exactly, in under a second, with an off-the-shelf
solver. It is **deterministic, reproducible and fully explainable** — you can say
precisely why a space was in or out, and what would have to change for the answer
to flip (the shadow price on each constraint, which is genuinely useful: *"€3m
more budget would add these two spaces"*).

### Why ML would be worse here

1. **There are no labels.** 418 spaces and zero historical outcomes. Supervised
   learning needs "we invested in this and it returned that". Orange has that
   history; the radar does not, and it is not in the opportunity-space data.
2. **The objective is a choice, not a pattern.** ML learns what *was* chosen.
   A strategy engine's job is to propose what *should* be — including things
   never chosen before, which is the entire point of white space.
3. **It would break the product's core guarantee.** NFR-01 and NFR-03 require
   every number to decompose into named components and be reconstructable by an
   outsider. A learned recommendation cannot do that, and this is a system whose
   credibility rests on it. Section 18 of the Technical Architecture makes
   *"counting, diversity and momentum are arithmetic, never a model"* an explicit
   guarantee; portfolio selection belongs on the same side of that line.
4. **n is small and the stakes are high.** 175 well-sized spaces is not a training
   set. It is a spreadsheet.

### Where ML genuinely earns its place — later

Three narrow, well-posed problems, all of which need data that does not exist yet:

| Problem | Method | Prerequisite |
|---|---|---|
| **Calibrate the obtainable-share band** — replace the four-step `by_right_to_win` table with a learned function | Regression on won/lost deals with their right-to-win score at the time | ~200+ historical deals with outcomes |
| **Calibrate win rate** by distance × competitive intensity | Same | CRM outcomes |
| **Learn the per-role ranking** from expert judgement | Pairwise learning-to-rank | 300–600 expert comparisons — already scoped and deferred in the README |

All three are *calibration of an existing transparent model*, not replacement of
it. The model stays explainable; the constants stop being guesses. That is the
right shape for ML in this product.

---

## 6 · What a plan should output

Not a ranked list. A plan.

1. **The selected portfolio** — spaces, with why each is in, and the marginal
   ones with why they nearly were not.
2. **The sequence** — which first, and what each unlocks. Reference-flywheel
   ordering: spaces that create a reference in a vertical where other selected
   spaces are waiting.
3. **Investment schedule by year**, split build / partner / go-to-market.
4. **The five-year projection** — revenue and margin, P10/P50/P90, with the
   sensitivity chart and the confidence grade.
5. **The shape of the portfolio** — horizon mix, vertical and technology
   concentration, distance mix, against the targets set as inputs.
6. **What was excluded and why** — budget, capacity, confidence, concentration
   cap, or strategic exclusion. This is as valuable as the inclusions and is
   where an optimiser beats a human: it can say *why not*.
7. **Shadow prices** — what one more euro, or one more engineer in a given pool,
   would buy.
8. **The assumption register** — every configured band used, with its owner and
   version, on the last page. Same discipline as the brief.

Exportable as a board-ready PDF, on the same rendering path as the sales brief.

---

## 7 · Suggested phasing

**Phase 1 — Selection, no ROI.** The optimiser over existing data: budget as a
proxy cost by portfolio distance, constraints, concentration limits, horizon mix.
Output is the portfolio, the sequence and the exclusion reasons. *No money
projection.* Ships on data that exists today and is immediately useful for
"where do we point next year's effort".

**Phase 2 — Sales and profit projection** (revised; see 4c). Not ROI. Add
`config/economics.yaml` with a ramp curve per horizon and a margin band per
portfolio distance — two assumptions with a named owner, anchored on the filed
7.9% segment margin and the filed 7.3% discount rate. Produces a five-year
revenue and profit projection with its interval, its sensitivity and an aggregate
plausibility check against the filed segment revenue. ROI moves to phase 3,
because it needs a build cost no filing will ever contain.

**Phase 3 — Calibration.** Replace assumed constants with values learned from
Orange's own won-deal history. This is where ML enters, narrowly, and where the
projection stops being a model of a model.

Phase 1 is worth building whether or not phases 2 and 3 ever happen. Phase 2 is
worth building only if someone will own the assumptions. **Phase 3 is blocked on
data Orange has and the radar does not.**

---

## 8 · Risks

| Risk | Why it matters | Mitigation |
|---|---|---|
| **Spurious precision** | A five-year euro figure from four stacked assumptions will be quoted without its interval the moment it leaves the screen. | Intervals and the confidence grade travel with the number into the PDF; no point estimate is ever displayed alone. |
| **Optimising a modelled number** | SOM is a planning assumption. Optimising hard against it will exploit its artefacts — the four-step share band in particular. | Sensitivity analysis surfaces it; the share band is the first thing phase 3 calibrates. |
| **The plan looks objective** | An optimiser's output carries more authority than the inputs deserve. | Show at least two objectives and the efficient frontier, so the trade-off is visible rather than resolved silently. |
| **Concentration in disguise** | Diversifying by vertical while every space depends on the same regulation is not diversification. | Compute correlation on the evidence, not only on the taxonomy. |
| **The capacity constraint is fiction** | 7 capability pools with no FTE figures. | Phase 1 should treat capacity as advisory and say so, until real numbers exist. |
| **White space is thin** | Currently L0 121 · L1 228 · L2 29 · L3 40 and **no L4 at all**. A tool built to find expansion may mostly rediscover the existing portfolio. | Worth checking before building: is that the market, or is it the linker being generous? Either way it shapes what phase 1 can deliver. |

---

## 9 · Questions for Orange

1. **What is the objective?** Revenue, margin, NPV, strategic coverage, or a
   stated blend. Different answers, materially different portfolios.
2. **Who owns the cost assumptions?** The same question already open for the
   sizing assumptions and the competitor register. Without an owner, phase 2
   produces numbers nobody will stand behind.
3. **Can the existing revenue baseline be supplied?** Without it, incremental and
   cannibalised revenue cannot be distinguished, and the plan may claim revenue
   Orange already has.
4. **Is won-deal history available for calibration?** Determines whether phase 3
   is a project or a wish.
5. **What are the real capacity constraints?** FTE by skill pool. This is
   frequently the binding constraint, and it is currently absent.
6. **What horizon mix does the business actually want?** The three-horizons split
   is a policy decision, not something the optimiser should infer.
7. **Is a plan that recommends *not* spending the full envelope acceptable?**
   If the evidence does not support deploying all of it, the honest optimiser
   says so — the same way the radar declines to publish a market size it cannot
   support. That needs to be acceptable before it is built.
