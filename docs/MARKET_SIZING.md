# Market sizing

*How a euro figure gets attached to an opportunity space, what each factor is
made of, and the four places the arithmetic would have gone wrong if it had been
written the obvious way.*

---

## What §4.3.4 asks for

The requirement is a warning before it is a specification:

> the headline market-size figures circulating in press coverage almost always
> originate from paid research houses, are quoted without methodology, and
> frequently conflict by an order of magnitude. The radar should prefer a
> transparent bottom-up estimate — enterprise count in the vertical × adoption
> rate × plausible contract value — and show its working, rather than repeating
> an unattributable billion-euro number.

Everything in `sizing.py` follows from that sentence. The module **computes, it
does not retrieve, and it never asks a model** — §4.4.4 defence 3 forbids a
model-generated number anywhere in this path. Every factor records its dataset,
its year, and whether it is `observed`, a declared `proxy`, or a configured
`assumption`. Where the evidence runs out, nothing is published.

![Market sizing](diagrams/fdd-08-sizing.png)

---

## Two methods, never merged

Both run per space, both are stored, both are shown:

| Method | What it computes | Where the factors come from |
|---|---|---|
| `bottom_up_adoption` | size-weighted enterprises × adoption rate × annual engagement value | Eurostat SBS `sbs_sc_ovw`; Eurostat enterprise ICT survey; median matching TED notice |
| `procurement_observed` | trimmed sum of matching tender values ÷ assumed contract years × annualisation | TED notices whose CPV codes resolve to the space |

Publishing both is the point. Two figures built from different data that land in
the same order of magnitude are an argument; one figure with no method is not.
And when they *don't* agree, the gap is itself informative — see the worked
example below, where they are ~450× apart for a reason the caveat states.

`procurement_observed` is deliberately **not** a market size in the analyst
sense. It is a floor made of contracts that already exist. For public-sector
verticals it is the better evidence, and it is the only method available there,
because Eurostat SBS is the business economy and public administration is not in
it.

Both are stored in `market_sizes`, one current row per `(opportunity_id,
method)` — `_store` deletes and reinserts rather than versioning, because the
history that matters for a size is the reference data's own vintage, and each
row already carries that per factor. For a list row the read model wants one
headline, so it orders bottom-up first and falls back to procurement
(`readmodel.py`, `market_size_summary`).

---

## Method 1 — bottom up, factor by factor

`_bottom_up` assembles four factors and refuses to publish if either of the
first two is missing.

### The denominator — `_enterprise_denominator`

Eurostat SBS enterprise counts, summed across every NACE division the vertical's
crosswalk row names, across the in-scope geographies, across the four size
classes in `scope.size_classes`.

Two things happen to each cell on the way in:

* **The crosswalk's per-row confidence is applied as a multiplier, not
  dropped.** NACE G45 (motor trade) is shared between `retail` and `automotive`
  at confidence 0.6 in each; counting it whole in both would size the same
  enterprises twice.
* **Each cell is also accumulated into an `effective` count** weighted by
  `size_class_value_weights` — the size mix, below.

The result carries `total`, `serviceable`, `effective`, `effective_serviceable`,
the per-size-class breakdown and the individual slices, so the number can be
taken apart in the UI.

### The adoption rate — `_adoption_factor`

The technology's mapped indicator from the enterprise ICT survey, **weighted by
the enterprise counts of the same slices** the denominator was built from. An
unweighted average across NACE aggregates would let a tiny aggregate with an
unusual rate move a vertical whose enterprises sit almost entirely in one other
aggregate.

Two ways it becomes a proxy, and both widen the band from ±15% to ±40% and drop
the confidence grade:

* **The indicator is a stand-in for the technology.** 22 of the 38 technologies
  are mapped `proxy=yes` in `technology_to_adoption.csv`. The survey measures
  cloud, AI, IoT and security practice well and enterprise connectivity
  procurement not at all, so `private_5g` borrows `E_IOT1` (industrial IoT use)
  and says so in the factor's note.
* **The sector aggregate is a stand-in for the sector.** The survey excludes
  finance (K), public administration (O), health (Q) and mining (B) outright.
  Rows in those verticals point at `ALL_ACTIVITIES` (`C10-S951_X_K`) at reduced
  confidence, which is a declared proxy by construction — that aggregate is, by
  definition, not this sector's rate.

There is no horizontal escape hatch in the technology crosswalk. A technology
with no row gets no bottom-up estimate at all; §4.3.4 prefers a missing number
to a manufactured one. (All 38 currently have one.)

### The engagement value — `_contract_value_factor`

This is the factor §4.3.4 leaves open as "plausible", and the only attributable
evidence for it is TED: real contracts, with real values, already in the signal
store because procurement is a first-class source (§4.3.3).

Notices matching the space are gathered, their values divided by
`assumed_contract_years` (4) to give an annual figure, and the median taken.
`trim_quantiles` gives the low and high. All three are clamped to
`annual_value_bounds_eur` (€25k–€3m) and **the clamp is recorded in the factor's
detail rather than applied silently.**

Below `min_notices` matching notices the median is an anecdote, so a configured
band per business domain is used instead — declared as an `assumption` with an
owner, never presented as evidence.

For every vertical except `public_sector` and `defense` the factor is also
flagged `proxy_for_private_sector`, and the caveat says what the substitution
is: the buying entity differs, the scope of work is comparable.

### The size mix

The observed contract value is a *large-organisation* contract. Applied flat to
every enterprise in the denominator it would price a twelve-person
manufacturer's deployment at a ministry's budget. So engagement value is scaled
per size class, anchored at 1.0 on the 250+ class the observed contracts
actually came from:

| Size class | Weight |
|---|---|
| 10–19 | 0.04 |
| 20–49 | 0.09 |
| 50–249 | 0.35 |
| 250+ | 1.00 |

The weights are the classes' employee midpoints over a 400-employee anchor —
an assumption with an owner, printed in the brief. Scaling by Eurostat turnover
instead was rejected: turnover per enterprise differs by a factor of several
hundred between the smallest and largest classes, which would price a small
manufacturer's project in the hundreds of euro.

---

## Method 2 — observed procurement

`_procurement_observed` needs at least `MIN_NOTICES_FOR_OBSERVED` matching
notices; below a handful of contracts this is an anecdote, not a flow.

Matching is by CPV crosswalk, **use case first, then vertical** — a use-case
match is the more specific statement about what is being bought — and the match
level travels with the result and is displayed, because §4.5.2 warns that a
crosswalk error lands directly in this number.

Where there are ten or more notices the values are trimmed to `trim_quantiles`;
the survivors are summed, divided by
`assumed_contract_years`, and scaled to a year. The high bound is the same sum
*untrimmed*, so the range shows what the tail is worth rather than hiding it.

SAM is the same observation restricted to the space's geographies, capped at
TAM so it can equal but never exceed it.

---

## TAM, SAM, SOM

**TAM** is every adopter in the denominator. **SAM is computed, not
discounted** — the identical estimate restricted to
`serviceable_size_classes` (50+ employees, where Orange Business sells managed
services) and to geographies inside the scope list. No fudge factor anywhere.

**SOM is the one genuinely modelled number in the pipeline**, and it is fenced
off accordingly. `_obtainable` picks a share band from the space's own
right-to-win score and multiplies it by a portfolio-distance factor:

| Right to win | Share of SAM | | Portfolio distance | Factor |
|---|---|---|---|---|
| ≥ 70 — strong assets, credible incumbent | 6.0% | | L0 | 1.00 |
| ≥ 55 — assets exist, competitive fight | 3.5% | | L1 | 0.80 |
| ≥ 40 — partial assets, challenger | 1.5% | | L2 | 0.50 |
| ≥ 0 — thin assets, opportunistic only | 0.5% | | L3 | 0.25 |
| | | | L4 | 0.10 |

The two multiply: a space at right-to-win 60 sitting at L2 obtains
`3.5% × 0.50 = 1.75%` of its SAM.

SC-12 forbids folding internal position into a published score. SOM is not a
score — but it gets the same discipline: the assumption is configuration with an
owner, it is shown beside the number it produced, it is labelled `assumption`
everywhere it appears, and **it never feeds attractiveness or right to win.**

Only delivery-bearing links (L0–L4) shorten the distance. Supporting evidence
(SUP) is not a path to delivery, and `_win_position` filters it out — the same
rule the read model uses.

---

## The confidence grade

`observed` · `partial` · `modelled`, and it is the **worst basis among the
factors, never an average**, because an estimate is exactly as trustworthy as
its weakest input.

The two declared modelling choices — `size_mix` and `obtainable_share` — sit in
`_MODELLING_FACTORS` and are excluded from the grade, and carried as caveats
instead. They are both permanently `assumption`; leaving them in would make
every estimate read `modelled` and the word would stop distinguishing anything.
The grade describes the *data going in*, not the modelling choices, which are
disclosed separately.

---

## A worked example

*Live figures, as of 2026-08-25.* Space: **"Unified identity and access
management for OT environments in discrete manufacturing"** (`OS220`) —
manufacturing × identity_access_management × zero_trust_architecture, geography
`EU`, graded `observed`.

| Factor | Value | Basis | Source |
|---|---|---|---|
| Enterprises, 10+ employees, 12 NACE divisions | 238,122 | observed | Eurostat `sbs_sc_ovw`, 2024 |
| Size-weighted buyer base | 39,220 | assumption | `size_class_value_weights` |
| Adoption of `E_SECMNAC`, enterprise-weighted | 68.1% | observed | Eurostat `isoc_cisce_ran2`, 2024 |
| Annual engagement value | €562,500 | observed | TED, median of 6 notices (€2.25m) ÷ 4 years |
| Obtainable share | 6.0% | assumption | RtW 86.15 → "strong assets" × L0 (1.00) |

The buyer base is where the size mix earns its keep: 101,420 + 78,070 + 46,915 +
11,717 enterprises weight down to **39,220 large-enterprise equivalents**, of
which **28,137** are serviceable.

```
TAM  39,220 × 0.681 × €562,500  =  €15.0bn
SAM  28,137 × 0.681 × €562,500  =  €10.8bn
SOM  €10.8bn × 6.0%             =  €647m
```

The same space's `procurement_observed` estimate is **€33m/year** from 6
notices over a 90-day window, scaled ×4.06. Some 450× below the bottom-up
figure, and correctly so — it is EU public tenders only, which the caveat states
outright: *"a floor rather than a market size."* The two are not rival estimates
of the same quantity and should never be reconciled into one.

**Two things to know about the published range.**

*It is asymmetric, and the contract value is why.* TAM high here is €101bn, 6.7×
the base — that is not noise in the adoption rate. The p90 of six notices lands
above €12m, so divided by four years it exceeds `annual_value_bounds_eur.max`
and is clamped to exactly €3m: 5.3× the €562.5k median, compounded with the ±15%
adoption and ±10% enterprise bands. The upper bound of a bottom-up range is
dominated by the contract-value tail, not by adoption uncertainty. Read the base
and the grade; treat the high bound as *"what if every buyer bought like the
largest observed tender."*

*And `detail.clamped` will not tell you that happened.* The flag is computed as
`abs(raw_base - base) > 1` — it tracks **the base only**. A clamped low or high
is applied without a flag, which is why this space reads `clamped: false` while
its high bound sits exactly on the ceiling. The module's own rule is that
clamping is recorded rather than applied silently, so this is a reporting gap
rather than an arithmetic one: to see it, compare `high` against
`annual_value_bounds_eur.max`.

---

## Four decisions that were load-bearing

Each is pinned by a test in `tests/test_sizing.py`, named below. If you change
the behaviour, the test name tells you what argument you are overturning.

**1 · The denominator and the adoption rate must share a size base.**
Eurostat publishes enterprise ICT adoption for firms with 10+ employees only
(`ICT_SIZE_CLASS = "GE10"`). Multiplied by an all-sizes enterprise count —
roughly 90% micro-firms — every estimate would have been out by an order of
magnitude. `scope.size_classes` restricts the denominator to the same base.
→ `test_denominator_and_adoption_share_the_same_size_base`

**2 · Contract value has to come from the right *kind* of contract.**
The CPV crosswalk says what a notice is *about*; it does not say whether it is
the kind of contract Orange would bid for. A €188m hydroelectric turbine
retrofit, correctly crosswalked to industrial asset management, was setting the
price of a zero-trust deployment. Eligibility is now tested on the notice's
**main object** — `cpv[0]`, which the TED connector preserves in that position
deliberately — against `eligible_cpv_prefixes`. Testing "any code" is not
enough: the turbine contract carries an IT code for its SCADA lot. The crosswalk
still reads every code, because a notice can be *about* a use case through any
of its lots; only its **value** has to come from an IT contract.
→ `test_only_ict_main_object_tenders_price_an_engagement`

**3 · A public tender is a large-organisation contract.**
Applied flat to a denominator that is ~75% firms under 50 employees, it prices a
twelve-person manufacturer's project at a ministry's budget and every TAM in the
radar comes out roughly an order of magnitude high. Hence the size mix, anchored
on the class the observed contracts actually came from.
→ `test_size_weighting_reduces_the_effective_buyer_base`

**4 · Annualise against the corpus window, not the matched subset's span.**
Three notices that happen to fall on one day would otherwise be scaled by 365
and produce a headline in the billions. `_corpus_window_days` measures the span
of the *whole* priced tender corpus, floored at `MIN_WINDOW_DAYS`, and both the
window and the resulting factor are reported. §4.12's rule applies: a silent cap
or a silent extrapolation reads as a measurement.
→ `test_observed_procurement_is_not_annualised_from_a_one_day_window`

And the general one behind all four — **proxies widen the range, they never move
the base.** → `test_proxy_adoption_is_flagged_and_widens_the_range`,
`test_crosswalk_confidence_is_applied_not_dropped`,
`test_confidence_grade_is_the_worst_factor_not_an_average`

---

## Where no number is published

`radar size` prints its own shortfall and the CLI says why. As of 2026-08-25,
**113 of 450 live spaces have no bottom-up estimate**, in three distinct
situations — all of them the rule working, not a gap to be filled:

| Situation | Count | Why |
|---|---|---|
| `public_sector` | 92 | SBS is the business economy; NACE O84 has no enterprise count at all. Sized from observed procurement, which for a public buyer is the better evidence anyway. |
| `defense` | 18 | Same. Both verticals deliberately carry no SBS row in `vertical_to_nace.csv`. |
| Switzerland-only spaces | 3 | CH is in SBS but **not** in the enterprise ICT survey, so there is no adoption rate to multiply by. `_adoption_factor` returns `None` and no estimate is published. |

Every live space does have at least a `procurement_observed` estimate, so the
grid never shows a blank where a number is expected — it shows a floor, labelled
as one.

Two coverage behaviours worth knowing:

* **Geographies outside the reference data are named, not dropped** (NFR-08).
  `_resolve_geographies` reports them in `coverage.outside_reference_data` and
  adds a caveat saying the estimate covers the European footprint only.
  → `test_geographies_outside_the_reference_data_are_reported_not_dropped`
* **The EU aggregate wins over named member states.** Mixing `EU27_2020` with
  country rows would double count, so the aggregate is used and the named
  countries are recorded as being inside it.

---

## The reference store, and why it is not in `signals`

56,385 observations across five Eurostat series live in
`reference_observations` / `reference_series`, on their own path.

| Series | Dataset | Observations | Periods |
|---|---|---|---|
| `sbs` | `sbs_sc_ovw` | 27,958 | 2022–2024 |
| `ict_ai` | `isoc_eb_ain2` | 11,440 | 2023–2025 |
| `ict_security` | `isoc_cisce_ran2` | 7,343 | 2019–2024 |
| `ict_cloud` | `isoc_cicce_usen2` | 6,885 | 2023–2025 |
| `ict_iot` | `isoc_eb_iotn2` | 2,759 | 2021 |

An annual statistical series has no publisher diversity, no momentum and no
relevance. Pushing 56,000 Eurostat cells through the signal store would corrupt
every scoring component that counts attached signals while adding nothing to
discovery.

**`ict_iot` is the stale one — 2021, and the only vintage published at NACE
level.** Every connectivity technology proxies through `E_IOT1` (`private_5g`,
`5g_ran_oran`, `network_slicing`, `satellite_ntn`, `lpwan`), so those spaces are
carrying a five-year-old adoption rate behind a ±40% band. The band and the
period are both printed; it is disclosed, not hidden. But if one number in the
sizing path is worth revisiting first, it is this one.

---

## The config surface

Everything tunable is in `config/sizing.yaml` and the two crosswalks. Nothing in
the sizing path is tunable in code.

| Where | What it controls |
|---|---|
| `config/sizing.yaml` | Scope and size classes, the five datasets and their indicators, contract-value matching and bounds, uncertainty bands, obtainable share, confidence notes |
| `config/crosswalks/vertical_to_nace.csv` | Vertical → SBS division (the denominator) and → ICT aggregate (the adoption rate), one row per division, with per-row confidence |
| `config/crosswalks/technology_to_adoption.csv` | Technology → dataset and indicator, with the `proxy` flag |
| `config/crosswalks/cpv_to_vertical.csv`, `cpv_to_use_case.csv` | Which tender notices count toward a space |

**Changing any of them requires a new `version` id.** This is the same rule as
`weight_set` for scores, for the same reason: sizes computed under different
assumptions are not comparable. Every stored row records `sizing_version`, and
the UI shows it.
→ `test_stored_size_records_the_assumptions_that_made_it`, `test_sizing_is_reproducible`

---

## Where it appears

| Surface | What it shows |
|---|---|
| **Radar grid** | The headline SAM, and market size as a sort order |
| **Full-screen space → Market tab** | Both methods, every factor with its source, period and basis, the slices, the caveats — `MarketSize.tsx` |
| **PDF brief and the pre-sales pack** | The sized market with every factor and its source |
| **The Planner** | SOM is what a five-year portfolio plan is built on, through `config/economics.yaml` — which discounts overlapping spaces, because obtainable share is computed per space against the same customers' same budgets and summing it double-counts |
| **`GET /api/topics/{id}/market-size`** | Every stored estimate, factor by factor. `POST` to the same path recomputes one space from the reference data currently in the store. |
| **`GET /api/topics/{id}`** | `market_size` (full derivation) and `market_size_summary` (headline) |

Currency formatting goes through one function, `format_eur`, so the API, the CLI
and the PDF never disagree — and it stops at thousands, because a hundred euro
of precision on a figure built from a median tender value is noise pretending to
be information.

---

## Running it

```bash
radar reference-data                    # fetch the five Eurostat series
radar reference-data --force            # refetch even if recently fetched
radar reference-data --series sbs       # one series

radar size                              # every live space, both methods
radar size --topics OS220,OS285         # named spaces only
```

`radar size` prints its stats and, if any space could not be sized, says how
many and why. Run `reference-data` first: without it only the
procurement-observed method can run, and the sizer logs a warning saying so.

Options and troubleshooting are in [OPERATIONS.md](OPERATIONS.md). The tables
are described in [DATA_MODEL.md](DATA_MODEL.md).

To re-derive the live counts quoted above:

```sql
SELECT method, confidence, COUNT(*) FROM market_sizes GROUP BY method, confidence;
```
