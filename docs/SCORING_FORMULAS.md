# Scoring formulas and hand-calculation guide

This document is the calculation specification for the three quantities shown by
the radar:

- **Attractiveness** — is the external market moving?
- **Right to Win** — can Orange play and win with its current assets?
- **Conviction** — do the people closest to the opportunity believe in it?

It describes the implementation in `src/radar/scoring.py`,
`src/radar/workflow.py`, and `src/radar/readmodel.py`. Configuration values below
are from weight set **`w-2026-08-a`**. If `config/settings.yaml` names a different
weight set, use that version's values instead. Scores from different weight sets
are not directly comparable.

## Reproducing a stored score

Use the score row's stored `inputs`, `components`, `weight_set`,
`pipeline_version`, and `model_version`. The database stores these in `scores`.
Do not reconstruct a historical score from today's config or today's corpus:
market-signal strength is relative to the corpus at the time of calculation.

Unless a section says otherwise, `clamp(x)` means:

```text
clamp(x) = max(0, min(100, x))
```

### Rounding rules

Rounding order is part of the formula:

- Attractiveness components are rounded to 2 decimals **before** weighting.
- The Attractiveness weighted total is then clamped and rounded to 2 decimals.
- Right-to-Win components are weighted at full floating-point precision. The
  component values returned for display and the final total are rounded to 2
  decimals separately.
- Each Conviction axis is rounded to 1 decimal. Overall Conviction is the mean of
  those already-rounded axis scores, rounded to 1 decimal.
- Role ranking uses the stored/display component values and rounds the final
  ordering value to 3 decimals. It is not clamped to 0–100.

## 1. Attractiveness

Current weights are defined in `config/settings.yaml`:

| Component | Weight |
|---|---:|
| Market signal strength | 0.30 |
| Source diversity | 0.20 |
| Evidence quality | 0.20 |
| Novelty and momentum | 0.15 |
| Strategic relevance | 0.15 |

```text
A = clamp(
      0.30 × market_signal_strength
    + 0.20 × source_diversity
    + 0.20 × evidence_quality
    + 0.15 × novelty_momentum
    + 0.15 × strategic_relevance
)
```

### 1.1 Market signal strength

Only attached signals published on or before the reference date and inside the
90-day trailing window are counted. `corpus_max` is the largest corresponding
count among all live, non-merged topics.

```text
n = number of topic signals in the trailing window
M = maximum trailing-window signal count in the live corpus

if n = 0:
    market_signal_strength = 0
else:
    market_signal_strength = clamp(100 × log2(1+n) / log2(1+max(M,1)))
```

The log base is configurable, but it cancels from the ratio if the same base is
used in numerator and denominator.

### 1.2 Source diversity

This component uses **all** evidence attached as of the reference date, not only
the trailing window.

First collapse duplicates by this exact key:

```text
(lowercase publisher or "unknown", lowercase first 60 characters of title)
```

For every remaining signal, add this weight to its publisher:

```text
tier 1, 2, or 3: 1.00
tier 4:          0.35
```

Let `w_i` be publisher `i`'s accumulated weight, `W = sum(w_i)`, and `P` the
number of distinct publishers:

```text
p_i = w_i / W
H = -sum(p_i × log2(p_i))
H_max = log2(P)
```

For the breadth factor, a publisher counts as `1.00` if it has any tier 1–3
item, or `0.35` if all its items are tier 4:

```text
effective_publishers = sum(per-publisher breadth contribution)
breadth = min(1, effective_publishers / 8)

source_diversity = clamp(100 × H/H_max × breadth)
```

No signals, zero total weight, or one publisher produces a score of `0`.

### 1.3 Evidence quality

Source-tier weights come from `config/source_tiers.yaml`:

| Tier | Weight |
|---|---:|
| 1 — authoritative | 1.00 |
| 2 — independent reporting | 0.75 |
| 3 — practitioner | 0.45 |
| 4 — interested party/vendor | 0.15 |

```text
mean_weight = sum(tier weight for every signal) / number of signals
tier4_share = tier-4 count / number of signals

if tier4_share > 0.25:
    mean_weight = mean_weight × (1 - (tier4_share - 0.25))

if there is no tier-1 or tier-2 signal:
    mean_weight = mean_weight × (1 - 0.45)

evidence_quality = clamp(100 × mean_weight)
```

No signals produces `0`. Notice that the `tier_weighted_mean` recorded in score
inputs is the value **after** both adjustments.

### 1.4 Novelty and momentum

Only signals inside the trailing window are used. With the current settings,
the 90-day window is divided into six 15-day buckets.

Signals are assigned to buckets using integer age in days. The stored list is
oldest first. Future-dated signals and signals without a usable date do not enter
a bucket.

For bucket values `y_0 ... y_5` and `x = [0,1,2,3,4,5]`:

```text
mean_x = mean(x)
mean_y = mean(y)
slope = sum((x_i-mean_x) × (y_i-mean_y)) / sum((x_i-mean_x)^2)
scale = max(1, mean_y)
base = 50 + 50 × tanh(slope / scale)
```

Then apply:

```text
bonus = 10 if first_seen is no more than 30 days before reference_date, else 0

flat_penalty = 15 if abs(slope) < 0.05
                  and first_seen is more than 90 days before reference_date,
               else 0

novelty_momentum = clamp(base + bonus - flat_penalty)
```

No signals produces `0`.

### 1.5 Strategic relevance

The topic is assigned a discrete rubric level, mapped as follows:

| Rubric level | Base score |
|---:|---:|
| 0 | 0 |
| 1 | 20 |
| 2 | 40 |
| 3 | 60 |
| 4 | 80 |
| 5 | 100 |

When an LLM is available, it selects level 0–5 using the configured strategy
rubric. The arithmetic after that selection is deterministic. To reproduce a
published score by hand, use the stored `rubric_level`; do not ask another model
to select it again.

If no model is available or its result is invalid, the fallback searches the
topic statement plus use-case label for configured ambition markers:

```text
level = 3 if at least one ambition marker matches, otherwise 1
```

Final component:

```text
base = configured score for rubric level
sovereignty_bonus = 100 × 0.15 if sovereign evidence exists, otherwise 0
privileged_bonus = 10 × configured privileged-vertical weight

strategic_relevance = clamp(base + sovereignty_bonus + privileged_bonus)
```

Sovereign evidence may come from an active opportunity link whose evidence has
`sovereign=true`, or from a configured sovereign offer addressing the topic's
use case.

## 2. Right to Win

Right to Win is a deterministic structured lookup over active
`opportunity_links` and the configured business graph. Rejected links are
excluded. It does not call an LLM.

| Component | Weight |
|---|---:|
| Offer match | 0.25 |
| Reference density | 0.20 |
| Partner coverage | 0.15 |
| Compliance fit | 0.12 |
| Capability depth | 0.12 |
| External validation | 0.08 |
| Technology ownership | 0.08 |

```text
W = clamp(
      0.25 × offer_match
    + 0.20 × reference_density
    + 0.15 × partner_coverage
    + 0.12 × compliance_fit
    + 0.12 × capability_depth
    + 0.08 × external_validation
    + 0.08 × technology_ownership
)
```

### Component formulas

```text
offer_match = 100 if an L0 offer link exists
               55 if an offer link exists but none is L0
                0 otherwise
```

```text
vertical_count = sum(reference story count × crosswalk share for the vertical)
peak_count = largest vertical_count in the configured reference distribution
reference_density = clamp(100 × vertical_count / peak_count)

evidence_gap_warning = vertical_count < 5
```

The warning does not subtract an additional number from Right to Win, but it is
used by the UI and the Sales eligibility filter.

```text
best_partner_rank = maximum evidence.tier_rank among partner links, or 0
partner_coverage = clamp(100 × best_partner_rank)
```

```text
C = number of certification links
S = number of those certifications with evidence.sovereign = true
compliance_fit = clamp(min(100, 30×C + 20×S))
```

```text
headcount = sum(evidence.headcount across capability-pool links)
capability_depth = clamp(100 × ln(1+headcount) / ln(1+10000))
```

```text
external_validation = 100 if any analyst-position link exists, otherwise 0
technology_ownership = 100 if the technology config has orange_asset=true,
                       otherwise 0
```

## 3. Conviction

Conviction comes from current, non-superseded human assessments in the database.
It is not produced by an LLM and is never folded into Attractiveness or Right to
Win.

Each role owns one axis:

| Role | Axis |
|---|---|
| Strategist | Strategic fit |
| Sales | Customer demand |
| Presales | Deliverability |

Ratings are integers from 0 to 5. Confidence is an integer from 1 to 5. Within
one axis:

```text
weighted_rating = sum(rating_i × confidence_i) / sum(confidence_i)
axis_score = round(weighted_rating × 20, 1)
```

The overall score gives each assessed axis equal weight:

```text
conviction = round(mean(available rounded axis scores), 1)
```

An unassessed axis is omitted rather than treated as zero. An axis is marked
`contested` when `max(rating) - min(rating) >= 3`. A new assessment by the same
author for the same topic and role supersedes that author's previous assessment.

## 4. Role-specific ranking

Role ranking controls ordering only. It does not alter any published score and
is not constrained to 0–100.

Derived terms:

```text
proof_point_density = 0.60 × reference_density
                    + 0.40 × external_validation

differentiation = 0.35 × technology_ownership
                + 0.35 × external_validation
                + 0.30 × compliance_fit

distance_term = 100 × portfolio_distance / 4
```

Portfolio distance is the shortest active delivery-bearing link: L0=0, L1=1,
L2=2, L3=3, L4=4. Supporting (`SUP`) evidence does not shorten distance.

If the selected role's own axis is assessed, ranking uses that axis. Otherwise
it falls back to overall Conviction. If there are no assessments, no Conviction
term is added at all.

```text
Strategist rank =
    0.60×A + 0.30×novelty_momentum + 0.00×W
  + 0.10×distance_term + 0.25×strategic_fit_if_assessed

Sales rank =
    0.25×A + 0.45×W + 0.30×proof_point_density
  - 0.30×distance_term + 0.25×customer_demand_if_assessed

Presales rank =
    0.30×A + 0.35×W + 0.35×differentiation
  - 0.10×distance_term + 0.25×deliverability_if_assessed
```

Eligibility is applied before ordering:

- Strategist: at least one L1–L4 delivery link.
- Sales: at least one L0–L1 delivery link, a linked reference, and no evidence
  gap.
- Presales: at least one L0–L2 delivery link.

## 5. Complete worked example

Assume a topic has six recent signals, while the corpus maximum is twelve. Their
ages in days are `[80,65,40,20,8,3]`, their tiers are `[1,2,2,3,4,1]`, and each
has a distinct publisher. The deterministic strategic fallback gives rubric
level 1 with no bonus.

```text
market_signal_strength = 100×log2(7)/log2(13) = 75.87

effective_publishers = 5×1 + 1×0.35 = 5.35
entropy = 2.5186; max_entropy = log2(6) = 2.5850
source_diversity = 100×(2.5186/2.5850)×(5.35/8) = 65.16

evidence_quality = 100×(1+.75+.75+.45+.15+1)/6 = 68.33

buckets oldest-first = [1,1,0,1,1,2]
slope = 0.1714; mean bucket = 1
novelty_momentum = 50 + 50×tanh(0.1714) = 58.49

strategic_relevance = 20.00

A = .30×75.87 + .20×65.16 + .20×68.33 + .15×58.49 + .15×20
  = 61.23
```

Assume the graph has an L0 offer; reference density is at the peak; best partner
rank is `0.8`; one sovereign certification; a capability pool of 1,000 people;
one analyst position; and an Orange-owned technology.

```text
offer_match = 100
reference_density = 100
partner_coverage = 80
compliance_fit = 30×1 + 20×1 = 50
capability_depth = 100×ln(1001)/ln(10001) = 75.01...
external_validation = 100
technology_ownership = 100

W = .25×100 + .20×100 + .15×80 + .12×50
  + .12×75.01... + .08×100 + .08×100
  = 88.00
```

Assume assessments are:

- Sales: rating 5/confidence 5 and rating 1/confidence 1.
- Strategist: rating 4/confidence 3.
- Presales: rating 3/confidence 4.

```text
customer_demand = round(((5×5 + 1×1)/(5+1))×20, 1) = 86.7
strategic_fit = 4×20 = 80.0
deliverability = 3×20 = 60.0
Conviction = round((86.7+80.0+60.0)/3, 1) = 75.6
```

For this example `proof_point_density=100`, `differentiation=85`, and an L0
path gives `distance_term=0`:

```text
Strategist rank = .60×61.23 + .30×58.49 + .25×80.0 = 74.285
Sales rank      = .25×61.23 + .45×88 + .30×100 + .25×86.7 = 106.583
Presales rank   = .30×61.23 + .35×88 + .35×85 + .25×60 = 93.919
```

Values above 100 are valid for role ranking because it is only an ordering
function. Published Attractiveness, Right to Win, and Conviction remain separate.

## 6. Source-of-truth map

| Concern | Source of truth |
|---|---|
| Score implementation | `src/radar/scoring.py` |
| Conviction implementation and role axes | `src/radar/workflow.py` |
| Role-ranking implementation | `src/radar/readmodel.py` |
| Score/component weights and thresholds | `config/settings.yaml` |
| Role ranking weights and eligibility | `config/role_modes.yaml` |
| Source-tier weights and discounts | `config/source_tiers.yaml` |
| Strategy rubric and bonuses | `config/strategy.yaml` |
| Business assets and references | `config/business_graph/*.yaml` |
| Technology ownership | `config/taxonomy/technologies.yaml` |
| Stored score decomposition | `scores` table in `src/radar/db.py` |
| Human rating inputs | `assessments` table in `src/radar/db.py` |

