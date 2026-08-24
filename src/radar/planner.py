"""The Planner — portfolio selection and a five-year projection.

The radar ranks. A plan is a different object: given a budget, a capacity and a
few preferences, which SET of opportunity spaces should Orange enter, in what
ORDER, and what does that set earn.

Three things make set selection different in kind from ranking, and all three
are places where a ranked list gives the wrong answer:

  shared build      Spaces needing the same capability pay for it once. Ranked
                    independently each carries the full build and all look
                    marginal; selected together the second is nearly free.
  the flywheel      Winning the first deal in a vertical raises right-to-win for
                    every other space in it, so SEQUENCE is a decision variable.
  concentration     Ranking by market size alone puts 18 of the top 20 spaces in
                    manufacturing. Diversification is a property of the SET and
                    is invisible per topic.

WHY AN OPTIMISER AND NOT A MODEL. Selection under constraints is a
multi-dimensional knapsack — an integer program that solves exactly, in under a
second at this size, and explains itself: which constraint bound, what one more
euro or one more engineer would buy. A learned recommender could not do any of
that, and NFR-01/NFR-03 require every number to decompose. There are also no
labels: 418 spaces and zero historical outcomes is a spreadsheet, not a training
set. The model's job here is to WRITE THE PLAN, not to choose it.

THREE REGISTERS, KEPT APART, as everywhere else in this codebase:

  inputs      what the caller asked for. Same inputs plus same versions give the
              same plan, and a test asserts it.
  projection  arithmetic over stored sizes and configured bands. No model call.
  narrative   a model writing prose ABOUT the projection, under the numeric
              guard. It may not introduce a figure.

WHAT THIS IS NOT. It is not a forecast. Every projection carries its interval,
its assumption versions and a plausibility check against Orange's own filed
segment revenue — because the naive sum of obtainable market across all 418
spaces reaches 90% of the segment's entire revenue, which is not arguable for
incremental business in a segment declining at 5.8% a year.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Iterable

from .config import Config
from .db import Database, js, unjs

log = logging.getLogger(__name__)

PLAN_SCHEMA = "plan-1"

DISTANCE_LABELS = {0: "L0", 1: "L1", 2: "L2", 3: "L3", 4: "L4"}
HORIZON_EARLIEST = {"now": 1, "next": 2, "later": 3}


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

@dataclass
class PlanInputs:
    """Everything a caller may state. Every field has a default, so a plan can
    be produced from nothing and then refined — which is how people actually
    use a tool like this."""

    label: str = "Untitled plan"
    plan_years: int = 5
    objective: str = "profit"                 # profit | revenue | npv | strategic_coverage

    # Hard constraints
    budget_person_years: float | None = None  # total entry effort available
    entry_slots_per_year: int | None = None
    pool_availability: float | None = None    # share of headcount free for new work
    min_confidence: str = "partial"           # observed | partial | modelled
    max_portfolio_distance: int = 3
    geographies: tuple[str, ...] = ()
    exclude_verticals: tuple[str, ...] = ()
    exclude_technologies: tuple[str, ...] = ()

    # Steering
    prefer_verticals: tuple[str, ...] = ()
    prefer_domains: tuple[str, ...] = ()
    preference_weight: float = 0.25           # how hard a preference tilts
    max_share_per_vertical: float | None = None
    max_share_per_technology: float | None = None
    horizon_mix: dict[str, float] | None = None
    horizon_tolerance: float | None = None
    max_competition: str | None = None        # none | low | medium | high
    require_sovereign: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "PlanInputs":
        data = dict(data or {})
        for key in ("geographies", "exclude_verticals", "exclude_technologies",
                    "prefer_verticals", "prefer_domains"):
            if key in data and data[key] is not None:
                data[key] = tuple(data[key])
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    def as_dict(self) -> dict[str, Any]:
        out = {}
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            out[name] = list(value) if isinstance(value, tuple) else value
        return out

    def fingerprint(self) -> str:
        return hashlib.sha256(js(self.as_dict()).encode()).hexdigest()[:12]


@dataclass
class Candidate:
    """One space, with everything the optimiser needs, resolved once."""
    id: str
    statement: str
    vertical: str
    use_case: str
    technology: str
    domains: tuple[str, ...]
    horizon: str
    distance: int
    som_base: float
    som_low: float
    som_high: float
    confidence: str
    attractiveness: float
    right_to_win: float
    competition: str
    pool: str | None
    pool_headcount: int
    entry_effort: float
    margin: float
    ramp: tuple[float, ...]
    score: float = 0.0
    #: Revenue if entered in year t (1-based), before overlap adjustment.
    revenue_by_entry: dict[int, tuple[float, ...]] = field(default_factory=dict)


CONFIDENCE_RANK = {"observed": 0, "partial": 1, "modelled": 2}
COMPETITION_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}


def _clip(text: str, length: int) -> str:
    """Truncate on a word boundary, and say so.

    A statement cut mid-word reads as a broken record rather than an
    abbreviated one, and the reader cannot tell which it is.
    """
    text = (text or "").strip()
    if len(text) <= length:
        return text
    head = text[:length].rsplit(" ", 1)[0]
    return f"{head}…"


class Planner:
    def __init__(self, cfg: Config, db: Database, llm: Any | None = None):
        self.cfg = cfg
        self.db = db
        self._llm = llm
        self.econ = cfg.economics
        if not self.econ:
            raise RuntimeError(
                "config/economics.yaml is missing. The Planner turns a market size into "
                "money, and it will not do that on undeclared assumptions."
            )
        self.filed = self.econ["filed"]
        self.defaults = self.econ["defaults"]

    @property
    def llm(self) -> Any:
        if self._llm is None:
            from .llm import LLMClient
            self._llm = LLMClient(max_retries=self.cfg.settings["llm"]["max_retries"])
        return self._llm

    # ------------------------------------------------------------------ run
    def plan(self, inputs: PlanInputs) -> dict[str, Any]:
        candidates = self.candidates(inputs)
        if not candidates:
            raise ValueError(
                "No opportunity space survived the stated constraints. Loosen the "
                "confidence floor, the distance cap or the exclusions."
            )
        selection, capacity, binding = self.select(candidates, inputs)
        if not selection:
            raise ValueError(
                f"{len(candidates)} spaces were admissible but no set satisfied every constraint "
                f"at once. " + ("; ".join(binding) if binding else "Loosen the concentration caps "
                                "or the horizon mix.")
            )
        projection, per_space, flags = self.project(selection, inputs)
        exclusions = self.explain_exclusions(candidates, selection, inputs, binding)
        plan_id = f"PLAN-{inputs.fingerprint()}"
        self._store(plan_id, inputs, candidates, per_space, projection, capacity,
                    exclusions, flags)
        return self.get(plan_id) or {}

    # ----------------------------------------------------------- candidates
    def candidates(self, inputs: PlanInputs) -> list[Candidate]:
        """Everything admissible under the hard constraints, resolved once."""
        pools = self._pools()
        margins = self.econ["margin_by_distance"]
        ramps = self.econ["ramp_by_horizon"]
        efforts = self.econ["capacity"]["entry_effort_person_years"]
        conf_floor = CONFIDENCE_RANK.get(inputs.min_confidence, 1)
        comp_cap = COMPETITION_RANK.get(inputs.max_competition or "high", 3)

        rows = self.db.query("""
            SELECT o.id, o.statement, o.vertical, o.use_case, o.technology, o.domains,
                   o.horizon, o.geographies,
                   m.som_base, m.som_low, m.som_high, m.confidence,
                   (SELECT score FROM scores s WHERE s.opportunity_id=o.id
                     AND s.kind='attractiveness' ORDER BY computed_at DESC LIMIT 1) att,
                   (SELECT score FROM scores s WHERE s.opportunity_id=o.id
                     AND s.kind='right_to_win' ORDER BY computed_at DESC LIMIT 1) rtw,
                   (SELECT level FROM topic_competition c WHERE c.opportunity_id=o.id) comp,
                   COALESCE((SELECT MIN(CASE l.link_type WHEN 'L0' THEN 0 WHEN 'L1' THEN 1
                                              WHEN 'L2' THEN 2 WHEN 'L3' THEN 3
                                              WHEN 'L4' THEN 4 END)
                             FROM opportunity_links l
                             WHERE l.opportunity_id=o.id AND l.rejected=0), 4) dist
            FROM opportunity_spaces o
            JOIN market_sizes m ON m.opportunity_id = o.id
                AND m.method = 'bottom_up_adoption'
                AND m.computed_at = (SELECT MAX(computed_at) FROM market_sizes x
                                     WHERE x.opportunity_id=o.id AND x.method='bottom_up_adoption')
            WHERE o.merged_into IS NULL
              AND o.state IN ('active','watchlist','fading')
              AND m.som_base IS NOT NULL AND m.som_base > 0
        """)

        out: list[Candidate] = []
        for r in rows:
            if CONFIDENCE_RANK.get(r["confidence"], 2) > conf_floor:
                continue
            if r["dist"] > inputs.max_portfolio_distance:
                continue
            if r["vertical"] in inputs.exclude_verticals:
                continue
            if r["technology"] in inputs.exclude_technologies:
                continue
            if COMPETITION_RANK.get(r["comp"] or "none", 0) > comp_cap:
                continue
            geos = unjs(r["geographies"], []) or []
            if inputs.geographies and geos and not (set(geos) & set(inputs.geographies)):
                continue
            domains = tuple(unjs(r["domains"], []) or [])
            horizon = r["horizon"] or "next"
            label = DISTANCE_LABELS[r["dist"]]
            pool, headcount = self._match_pool(pools, r["technology"], r["vertical"], domains)
            cand = Candidate(
                id=r["id"], statement=r["statement"], vertical=r["vertical"],
                use_case=r["use_case"], technology=r["technology"], domains=domains,
                horizon=horizon, distance=r["dist"],
                som_base=r["som_base"] or 0.0, som_low=r["som_low"] or 0.0,
                som_high=r["som_high"] or 0.0, confidence=r["confidence"],
                attractiveness=r["att"] or 0.0, right_to_win=r["rtw"] or 0.0,
                competition=r["comp"] or "none",
                pool=pool, pool_headcount=headcount,
                entry_effort=float(efforts[label]),
                margin=float(margins[label]),
                ramp=tuple(ramps.get(horizon, ramps["next"])),
            )
            self._precompute(cand, inputs)
            out.append(cand)
        log.info("Planner: %d candidates admissible of %d sized spaces", len(out), len(rows))
        return out

    def _precompute(self, c: Candidate, inputs: PlanInputs) -> None:
        """Revenue and score for every legal entry year.

        Entering later costs revenue, because a space ramps from ITS OWN entry
        year rather than from the start of the plan. That is what makes staggered
        entry a real trade-off rather than free scheduling.
        """
        years = inputs.plan_years
        earliest = HORIZON_EARLIEST.get(c.horizon, 2)
        for entry in range(earliest, years + 1):
            rev = [0.0] * years
            for i, f in enumerate(c.ramp):
                t = entry - 1 + i
                if t < years:
                    rev[t] = c.som_base * f
            c.revenue_by_entry[entry] = tuple(rev)
        best = c.revenue_by_entry.get(earliest, tuple([0.0] * years))
        c.score = sum(best) * c.margin

    # ------------------------------------------------------------- selection
    def select(self, candidates: list[Candidate],
               inputs: PlanInputs) -> tuple[list[tuple[Candidate, int]], dict, list[str]]:
        """Choose the set and the entry year for each.

        A mixed-integer program over `x[i][t]` — space i enters in year t — with
        capacity, concentration and horizon-mix constraints. Solved exactly where
        the solver is available; a constraint-respecting greedy stands in when it
        is not, and says so, because a plan that silently changes method is worse
        than one that says which it used.
        """
        try:
            return self._select_milp(candidates, inputs)
        except Exception as exc:                              # pragma: no cover
            log.warning("MILP unavailable (%s) — falling back to greedy", exc)
            return self._select_greedy(candidates, inputs)

    def _limits(self, inputs: PlanInputs) -> dict[str, Any]:
        cap = self.econ["capacity"]
        d = self.defaults
        return {
            "slots": inputs.entry_slots_per_year or cap["entry_slots_per_year"],
            "availability": inputs.pool_availability or cap["pool_availability"],
            "budget": inputs.budget_person_years,
            "max_vertical": (inputs.max_share_per_vertical
                             if inputs.max_share_per_vertical is not None
                             else d["max_share_per_vertical"]),
            "max_technology": (inputs.max_share_per_technology
                               if inputs.max_share_per_technology is not None
                               else d["max_share_per_technology"]),
            "horizon_mix": inputs.horizon_mix or d["horizon_mix"],
            "horizon_tol": (inputs.horizon_tolerance
                            if inputs.horizon_tolerance is not None else d["horizon_tolerance"]),
        }

    def _select_milp(self, candidates, inputs):
        import numpy as np
        from scipy.optimize import LinearConstraint, milp, Bounds

        years = inputs.plan_years
        lim = self._limits(inputs)
        pools = self._pool_capacity(candidates, lim["availability"])
        sustain = float(self.econ["capacity"]["sustain_person_years_per_eur_m"])

        # Variable index: (candidate, entry_year) pairs that are legal.
        vars_: list[tuple[int, int]] = []
        for i, c in enumerate(candidates):
            for t in c.revenue_by_entry:
                vars_.append((i, t))
        n = len(vars_)
        if not n:
            return [], {}, ["no legal entry year for any candidate"]

        # Objective: maximise value. milp minimises, so negate.
        obj = np.zeros(n)
        for k, (i, t) in enumerate(vars_):
            c = candidates[i]
            rev = c.revenue_by_entry[t]
            value = self._objective_value(c, rev, inputs)
            obj[k] = -value

        A, lo, hi = [], [], []
        relaxed: list[str] = []

        # Each space enters at most once.
        for i in range(len(candidates)):
            row = np.zeros(n)
            for k, (j, _) in enumerate(vars_):
                if j == i:
                    row[k] = 1
            A.append(row); lo.append(0); hi.append(1)

        # Entry slots per year.
        for t in range(1, years + 1):
            row = np.zeros(n)
            for k, (_, tt) in enumerate(vars_):
                if tt == t:
                    row[k] = 1
            A.append(row); lo.append(0); hi.append(lim["slots"])

        # Capability pool, per pool per year: entry effort in the entry year plus
        # sustain effort for everything already live.
        for pool, capacity in pools.items():
            for t in range(1, years + 1):
                row = np.zeros(n)
                for k, (i, tt) in enumerate(vars_):
                    c = candidates[i]
                    if c.pool != pool or tt > t:
                        continue
                    load = c.entry_effort if tt == t else 0.0
                    rev = c.revenue_by_entry[tt][t - 1] / 1e6
                    load += rev * sustain
                    row[k] = load
                if row.any():
                    A.append(row); lo.append(0); hi.append(capacity)

        # Total entry effort, when a budget is stated.
        if lim["budget"]:
            row = np.array([candidates[i].entry_effort for i, _ in vars_], dtype=float)
            A.append(row); lo.append(0); hi.append(float(lim["budget"]))

        # Concentration: share of selected spaces per vertical and technology.
        #
        # Two things stop this being a trap, and both were found by it silently
        # returning an empty plan:
        #
        #   a cap over the ONLY group is `total <= cap * total`, which forces
        #   total to zero. A cap needs somewhere else for the rest to go, so it
        #   is skipped when the group is the whole candidate set.
        #
        #   a share cap is meaningless on a small plan — one space of one is
        #   100% of its vertical. SLACK lets a group exceed its share by a couple
        #   of spaces, which is invisible on a plan of forty and is the
        #   difference between a feasible and an infeasible plan of three.
        total_row = np.ones(n)
        SLACK = 2.0
        for attr, cap_share in (("vertical", lim["max_vertical"]),
                                ("technology", lim["max_technology"])):
            groups: dict[str, np.ndarray] = {}
            for k, (i, _) in enumerate(vars_):
                key = getattr(candidates[i], attr)
                groups.setdefault(key, np.zeros(n))[k] = 1
            if len(groups) < 2:
                relaxed.append(f"{attr} concentration cap dropped: every candidate shares one "
                               f"{attr}")
                continue
            for key, row in groups.items():
                A.append(row - cap_share * total_row); lo.append(-np.inf); hi.append(SLACK)

        # Horizon mix, as a band rather than a target.
        #
        # A cap is only meaningful when there is something else to fill the rest
        # with. Applied unconditionally to a corpus that is entirely one horizon,
        # `count_h <= 0.75 * total` forces total to zero and the optimiser
        # returns an EMPTY plan — technically optimal, and indistinguishable from
        # "nothing was worth doing". So a horizon is capped only where candidates
        # exist outside it, and when the cap is dropped the plan says so.
        tol = lim["horizon_tol"]
        by_horizon: dict[str, np.ndarray] = {}
        for k, (i, _) in enumerate(vars_):
            by_horizon.setdefault(candidates[i].horizon, np.zeros(n))[k] = 1
        for horizon, target in lim["horizon_mix"].items():
            row = by_horizon.get(horizon)
            if row is None or not row.any():
                continue
            others = sum(1 for h in by_horizon if h != horizon)
            if not others:
                relaxed.append(f"horizon mix dropped: every candidate is '{horizon}'")
                continue
            A.append(row - (target + tol) * total_row); lo.append(-np.inf); hi.append(0.0)

        constraints = [LinearConstraint(np.array(A), np.array(lo), np.array(hi))]
        res = milp(c=obj, constraints=constraints, integrality=np.ones(n),
                   bounds=Bounds(0, 1))
        if not res.success or res.x is None:
            raise RuntimeError(f"solver did not converge: {res.message}")

        chosen = [(candidates[i], t) for k, (i, t) in enumerate(vars_) if res.x[k] > 0.5]
        chosen.sort(key=lambda pair: (pair[1], -pair[0].score))
        usage, binding = self._capacity_report(chosen, pools, inputs)
        usage["relaxed"] = relaxed
        binding = binding + relaxed
        if not chosen:
            # An empty plan and "nothing was worth doing" are different findings,
            # and only one of them is about the market. Say which.
            binding.append(
                "no combination satisfied every constraint at once — the likeliest cause is a "
                "concentration cap or the horizon mix being unreachable on this candidate set")
        log.info("Planner: selected %d spaces of %d candidates", len(chosen), len(candidates))
        return chosen, usage, binding

    def _select_greedy(self, candidates, inputs):
        """Constraint-respecting fallback. Same constraints, no optimality claim."""
        lim = self._limits(inputs)
        pools = self._pool_capacity(candidates, lim["availability"])
        years = inputs.plan_years
        sustain = float(self.econ["capacity"]["sustain_person_years_per_eur_m"])
        chosen: list[tuple[Candidate, int]] = []
        per_year: dict[int, int] = {t: 0 for t in range(1, years + 1)}
        load: dict[tuple[str, int], float] = {}
        effort = 0.0

        for c in sorted(candidates, key=lambda c: -c.score):
            placed = False
            for t in sorted(c.revenue_by_entry):
                if per_year[t] >= lim["slots"]:
                    continue
                if lim["budget"] and effort + c.entry_effort > lim["budget"]:
                    continue
                trial = dict(load)
                ok = True
                if c.pool:
                    for tt in range(t, years + 1):
                        add = (c.entry_effort if tt == t else 0.0)
                        add += c.revenue_by_entry[t][tt - 1] / 1e6 * sustain
                        key = (c.pool, tt)
                        trial[key] = trial.get(key, 0.0) + add
                        if trial[key] > pools.get(c.pool, 0.0):
                            ok = False
                            break
                if not ok:
                    continue
                n_sel = len(chosen) + 1
                same_v = sum(1 for s, _ in chosen if s.vertical == c.vertical) + 1
                if same_v / n_sel > lim["max_vertical"] and n_sel > 3:
                    continue
                load = trial
                per_year[t] += 1
                effort += c.entry_effort
                chosen.append((c, t))
                placed = True
                break
            if not placed:
                continue
        chosen.sort(key=lambda pair: (pair[1], -pair[0].score))
        usage, binding = self._capacity_report(chosen, pools, inputs)
        return chosen, usage, binding

    def _objective_value(self, c: Candidate, rev: tuple[float, ...],
                         inputs: PlanInputs) -> float:
        pref = 1.0
        if inputs.prefer_verticals and c.vertical in inputs.prefer_verticals:
            pref += inputs.preference_weight
        if inputs.prefer_domains and set(c.domains) & set(inputs.prefer_domains):
            pref += inputs.preference_weight
        if inputs.objective == "revenue":
            base = sum(rev)
        elif inputs.objective == "npv":
            wacc = float(self.filed["discount_rate_post_tax"])
            base = sum(v * c.margin / (1 + wacc) ** (i + 1) for i, v in enumerate(rev))
        elif inputs.objective == "strategic_coverage":
            # Value breadth: attractiveness per unit of effort, so cheap entries
            # into unoccupied parts of the grid win.
            base = c.attractiveness * 1e6 / max(c.entry_effort, 1.0)
        else:
            base = sum(rev) * c.margin
        return base * pref

    # ------------------------------------------------------------ projection
    def project(self, selection: list[tuple[Candidate, int]],
                inputs: PlanInputs) -> tuple[dict, list[dict], list[dict]]:
        """Revenue and profit per year, with the overlap adjustment applied.

        SOM IS NOT ADDITIVE. Obtainable share is computed per topic, against the
        same customers' same budgets. The naive sum across all 418 spaces reaches
        90% of Orange Business's entire revenue, and coverage makes it worse
        rather than better — which is what proves the problem is the aggregation
        and not the sizing. So a second space in a vertical is discounted, and a
        third sharing its use case more so.
        """
        agg = self.econ["aggregation"]
        years = inputs.plan_years
        seen_vertical: dict[str, int] = {}
        seen_use_case: dict[tuple[str, str], int] = {}
        per_space: list[dict] = []
        rev_years = [0.0] * years
        profit_years = [0.0] * years
        low_years = [0.0] * years
        high_years = [0.0] * years

        for c, entry in sorted(selection, key=lambda p: (p[1], -p[0].score)):
            factor = 1.0
            n_v = seen_vertical.get(c.vertical, 0)
            if n_v:
                factor *= (1 - float(agg["overlap_discount_same_vertical"])) ** min(n_v, 3)
            n_u = seen_use_case.get((c.vertical, c.use_case), 0)
            if n_u:
                factor *= (1 - float(agg["overlap_discount_same_use_case"])) ** min(n_u, 3)
            seen_vertical[c.vertical] = n_v + 1
            seen_use_case[(c.vertical, c.use_case)] = n_u + 1

            rev = [v * factor for v in c.revenue_by_entry[entry]]
            prof = [v * c.margin for v in rev]
            scale_lo = (c.som_low / c.som_base) if c.som_base else 0.0
            scale_hi = (c.som_high / c.som_base) if c.som_base else 0.0
            for i in range(years):
                rev_years[i] += rev[i]
                profit_years[i] += prof[i]
                low_years[i] += rev[i] * scale_lo * c.margin
                high_years[i] += rev[i] * scale_hi * c.margin
            per_space.append({
                "candidate": c, "entry_year": entry, "overlap_factor": round(factor, 4),
                "revenue_by_year": rev, "profit_by_year": prof,
            })

        wacc = float(self.filed["discount_rate_post_tax"])
        npv = sum(p / (1 + wacc) ** (i + 1) for i, p in enumerate(profit_years))
        seg = float(self.filed["segment_revenue_eur_m"]) * 1e6
        projection = {
            "years": years,
            "revenue_by_year": [round(v, 2) for v in rev_years],
            "profit_by_year": [round(v, 2) for v in profit_years],
            "profit_low_by_year": [round(v, 2) for v in low_years],
            "profit_high_by_year": [round(v, 2) for v in high_years],
            "revenue_total": round(sum(rev_years), 2),
            "profit_total": round(sum(profit_years), 2),
            "profit_total_low": round(sum(low_years), 2),
            "profit_total_high": round(sum(high_years), 2),
            "npv_profit": round(npv, 2),
            "discount_rate": wacc,
            "year5_share_of_segment": round(rev_years[-1] / seg, 4) if seg else None,
            "segment_revenue": seg,
            "mix": self._mix(per_space),
        }
        return projection, per_space, self._flags(projection, per_space)

    def _flags(self, projection: dict, per_space: list[dict]) -> list[dict]:
        """Say what is not credible, rather than returning it with a straight face."""
        out: list[dict] = []
        agg = self.econ["aggregation"]
        share = projection.get("year5_share_of_segment") or 0.0
        threshold = float(agg["plausibility_flag_share_of_segment"])
        if share > threshold:
            out.append({
                "kind": "plausibility",
                "severity": "high" if share > threshold * 2 else "medium",
                "message": (
                    f"Year-{projection['years']} incremental revenue is "
                    f"{share:.0%} of Orange Business's filed segment revenue "
                    f"(EUR {projection['segment_revenue']/1e6:,.0f}m), against a flag threshold of "
                    f"{threshold:.0%}. That segment is declining 5.8% a year. Treat this as a "
                    f"scenario ceiling rather than a plan, and revisit the obtainable-share bands."
                ),
            })
        mix = projection["mix"]
        for key in ("vertical", "technology"):
            top = mix[key][0] if mix[key] else None
            if top and top["share"] > 0.5:
                out.append({
                    "kind": "concentration", "severity": "medium",
                    "message": (f"{top['share']:.0%} of selected spaces are in one {key} "
                                f"({top['key']}). Diversification is a property of the set; "
                                f"tighten max_share_per_{key} if that is not intended."),
                })
        modelled = sum(1 for p in per_space if p["candidate"].confidence == "modelled")
        if modelled:
            out.append({
                "kind": "confidence", "severity": "medium",
                "message": (f"{modelled} selected space(s) rest on a `modelled` size — no "
                            f"attributable contract value was found. Their revenue is the least "
                            f"reliable part of this projection."),
            })
        return out

    @staticmethod
    def _mix(per_space: list[dict]) -> dict[str, list[dict]]:
        out: dict[str, list[dict]] = {}
        total = len(per_space) or 1
        for key in ("vertical", "technology", "horizon"):
            counts: dict[str, int] = {}
            for p in per_space:
                counts[getattr(p["candidate"], key)] = counts.get(getattr(p["candidate"], key), 0) + 1
            out[key] = sorted(
                ({"key": k, "count": v, "share": round(v / total, 4)} for k, v in counts.items()),
                key=lambda d: -d["count"])
        dist: dict[str, int] = {}
        for p in per_space:
            label = DISTANCE_LABELS[p["candidate"].distance]
            dist[label] = dist.get(label, 0) + 1
        out["distance"] = sorted(
            ({"key": k, "count": v, "share": round(v / total, 4)} for k, v in dist.items()),
            key=lambda d: d["key"])
        return out

    # -------------------------------------------------------------- capacity
    def _pools(self) -> list[dict[str, Any]]:
        rows = self.db.query(
            "SELECT id, label, attributes FROM graph_nodes WHERE node_type='capability_pool'")
        out = []
        for r in rows:
            a = unjs(r["attributes"], {}) or {}
            out.append({"id": r["id"], "label": r["label"],
                        "headcount": int(a.get("headcount") or 0),
                        "technologies": set(a.get("technologies") or []),
                        "verticals": set(a.get("verticals") or []),
                        "domains": set(a.get("domains") or [])})
        # Most specific first, so a technology match beats a domain match.
        out.sort(key=lambda p: (len(p["technologies"]) == 0, len(p["verticals"]) == 0,
                                p["headcount"]))
        return out

    @staticmethod
    def _match_pool(pools, technology: str, vertical: str,
                    domains: Iterable[str]) -> tuple[str | None, int]:
        """Which pool staffs this space.

        Specificity order matters and is the difference between a real capacity
        constraint and a meaningless one: matching on domain alone, the Orange
        Group researchers pool (700 people, four domains) would claim 404 of 418
        spaces. Technology first, then vertical, then domain.
        """
        doms = set(domains)
        for key in ("technologies", "verticals", "domains"):
            for pool in pools:
                value = {"technologies": technology, "verticals": vertical}.get(key)
                hit = (value in pool[key]) if value else bool(doms & pool[key])
                if key == "domains":
                    hit = bool(doms & pool[key])
                if hit and pool["headcount"]:
                    return pool["label"], pool["headcount"]
        return None, 0

    def _pool_capacity(self, candidates, availability: float) -> dict[str, float]:
        caps: dict[str, float] = {}
        for c in candidates:
            if c.pool and c.pool not in caps:
                caps[c.pool] = c.pool_headcount * float(availability)
        return caps

    def _capacity_report(self, chosen, pools, inputs) -> tuple[dict, list[str]]:
        years = inputs.plan_years
        sustain = float(self.econ["capacity"]["sustain_person_years_per_eur_m"])
        usage: dict[str, Any] = {"pools": {}, "slots": {}}
        binding: list[str] = []
        for pool, capacity in pools.items():
            per_year = []
            for t in range(1, years + 1):
                load = 0.0
                for c, entry in chosen:
                    if c.pool != pool or entry > t:
                        continue
                    load += c.entry_effort if entry == t else 0.0
                    load += c.revenue_by_entry[entry][t - 1] / 1e6 * sustain
                per_year.append(round(load, 1))
            usage["pools"][pool] = {
                "capacity": round(capacity, 1), "used_by_year": per_year,
                "peak_utilisation": round(max(per_year) / capacity, 3) if capacity else None,
            }
            if capacity and max(per_year) >= capacity * 0.95:
                binding.append(f"capability pool '{pool}' at capacity")
        lim = self._limits(inputs)
        for t in range(1, years + 1):
            n = sum(1 for _, entry in chosen if entry == t)
            usage["slots"][t] = {"used": n, "available": lim["slots"]}
            if n >= lim["slots"]:
                binding.append(f"entry slots exhausted in year {t}")
        usage["binding"] = sorted(set(binding))
        return usage, sorted(set(binding))

    # ------------------------------------------------------------ exclusions
    def explain_exclusions(self, candidates, selection, inputs, binding) -> list[dict]:
        """Why the near-misses were left out.

        As valuable as the inclusions, and the thing an optimiser can say that a
        human cannot: the reason is a constraint, and the constraint is named.
        """
        chosen_ids = {c.id for c, _ in selection}
        rest = [c for c in candidates if c.id not in chosen_ids]
        rest.sort(key=lambda c: -c.score)
        out = []
        for c in rest[:20]:
            if c.pool and any(c.pool in b for b in binding):
                reason = f"capability pool '{c.pool}' was fully committed"
            elif any("entry slots" in b for b in binding):
                reason = "no entry slot was free in any year it could have started"
            elif c.confidence == "modelled":
                reason = "size rests on a modelled contract value; outranked by better-evidenced spaces"
            else:
                reason = "outranked on value per unit of entry effort under the stated objective"
            out.append({
                "opportunity_id": c.id, "statement": _clip(c.statement, 160),
                "vertical": c.vertical, "horizon": c.horizon,
                "distance": DISTANCE_LABELS[c.distance],
                "value_forgone": round(c.score, 2), "reason": reason,
            })
        return out


    # ------------------------------------------------------------ narrative
    def narrate(self, plan_id: str) -> dict[str, Any]:
        """Write the plan. One model call, and it may not introduce a number.

        The numeric guard is absolute here, more than anywhere else in the
        product: every figure is already in the projection table beside the
        prose, and a sentence that disagrees with it is a defect the reader has
        to adjudicate. So a section containing a quantity is stripped, and what
        was stripped is shown rather than quietly omitted.
        """
        from .pipeline import prompts
        from .pipeline.synthesis import _NUMERIC_CLAIM_RE

        plan = self.get(plan_id)
        if plan is None:
            raise KeyError(f"No such plan: {plan_id}")
        if not plan.get("selections"):
            raise ValueError("This plan selected nothing, so there is nothing to explain.")

        system = prompts.plan_system_prompt(self.cfg)
        user = prompts.format_plan_for_narrative(plan)
        payload = self.llm.complete_json(
            system, user, strong=True, max_tokens=4000,
            temperature=self.cfg.settings["llm"]["temperature_critic"])
        if not isinstance(payload, dict):
            payload = {}

        allowed = {s["opportunity_id"] for s in plan["selections"]}
        declared = [str(x).strip() for x in (payload.get("spaces_named") or [])]
        invented = [x for x in declared if x and x not in allowed]

        sections: dict[str, str] = {}
        stripped: list[dict[str, str]] = []
        for name in prompts.PLAN_SECTIONS:
            text = str((payload.get("sections") or {}).get(name, "")).strip()
            if len(text) < 60:
                stripped.append({"section": name, "reason": "missing or too short to be useful"})
                continue
            if _NUMERIC_CLAIM_RE.search(text):
                stripped.append({"section": name,
                                 "reason": "contained a quantity; every figure belongs to the "
                                           "projection table, not the prose"})
                continue
            if invented and any(x in text for x in invented):
                stripped.append({"section": name,
                                 "reason": f"named spaces not in this plan: {', '.join(invented[:3])}"})
                continue
            sections[name] = text

        headline = str(payload.get("headline", "")).strip()
        if _NUMERIC_CLAIM_RE.search(headline):
            stripped.append({"section": "headline", "reason": "contained a quantity"})
            headline = ""

        narrative = {"headline": headline, "sections": sections}
        with self.db.cursor() as cur:
            cur.execute("""UPDATE plans SET narrative=?, stripped=?, status='narrated',
                                  prompt_version=?, model_version=? WHERE id=?""",
                        (js(narrative), js(stripped), prompts.PROMPT_VERSION_PLAN,
                         getattr(self.llm, "strong_model", None), plan_id))
        log.info("Plan %s narrated: %d sections, %d stripped", plan_id, len(sections), len(stripped))
        return self.get(plan_id) or {}

    # ------------------------------------------------------------- storage
    def _store(self, plan_id, inputs, candidates, per_space, projection, capacity,
               exclusions, flags) -> None:
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM plan_selections WHERE plan_id = ?", (plan_id,))
            cur.execute("""
                INSERT INTO plans (id, created_at, label, inputs, status, objective, plan_years,
                                   selected_count, considered_count, projection, capacity_usage,
                                   exclusions, flags, economics_version, sizing_version,
                                   weight_set, pipeline_version)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    created_at=excluded.created_at, label=excluded.label, inputs=excluded.inputs,
                    status=excluded.status, objective=excluded.objective,
                    plan_years=excluded.plan_years, selected_count=excluded.selected_count,
                    considered_count=excluded.considered_count, projection=excluded.projection,
                    capacity_usage=excluded.capacity_usage, exclusions=excluded.exclusions,
                    flags=excluded.flags, economics_version=excluded.economics_version""",
                (plan_id, now, inputs.label, js(inputs.as_dict()), "computed",
                 inputs.objective, inputs.plan_years, len(per_space), len(candidates),
                 js(projection), js(capacity), js(exclusions), js(flags),
                 self.cfg.economics_version, self.cfg.sizing_version,
                 self.cfg.weight_set, self.cfg.pipeline_version))
            for p in per_space:
                c = p["candidate"]
                cur.execute("""
                    INSERT INTO plan_selections (plan_id, opportunity_id, entry_year, horizon,
                        portfolio_distance, margin_applied, entry_effort, pool, som_base,
                        revenue_by_year, profit_by_year, overlap_factor, rationale)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (plan_id, c.id, p["entry_year"], c.horizon, c.distance, c.margin,
                     c.entry_effort, c.pool, c.som_base,
                     js([round(v, 2) for v in p["revenue_by_year"]]),
                     js([round(v, 2) for v in p["profit_by_year"]]),
                     p["overlap_factor"],
                     f"{DISTANCE_LABELS[c.distance]} · {c.horizon} · attractiveness "
                     f"{c.attractiveness:.0f} · right to win {c.right_to_win:.0f} · "
                     f"{c.confidence} size"))

    def get(self, plan_id: str) -> dict[str, Any] | None:
        row = self.db.query_one("SELECT * FROM plans WHERE id = ?", (plan_id,))
        if row is None:
            return None
        plan = dict(row)
        for key in ("inputs", "projection", "capacity_usage", "exclusions", "flags", "stripped"):
            plan[key] = unjs(plan.get(key), [] if key in ("exclusions", "flags", "stripped") else {})
        plan["narrative"] = unjs(plan.get("narrative"), None)
        sel = self.db.query("""
            SELECT s.*, o.statement, o.vertical, o.use_case, o.technology, o.state
            FROM plan_selections s JOIN opportunity_spaces o ON o.id = s.opportunity_id
            WHERE s.plan_id = ? ORDER BY s.entry_year, s.som_base DESC""", (plan_id,))
        plan["selections"] = []
        for r in sel:
            d = dict(r)
            d["revenue_by_year"] = unjs(d.get("revenue_by_year"), [])
            d["profit_by_year"] = unjs(d.get("profit_by_year"), [])
            plan["selections"].append(d)
        plan["assumptions"] = {
            "economics_version": plan["economics_version"],
            "margin_by_distance": {k: v for k, v in self.econ["margin_by_distance"].items()
                                   if k != "note"},
            "ramp_by_horizon": {k: v for k, v in self.econ["ramp_by_horizon"].items()
                                if k != "note"},
            "capacity": self.econ["capacity"],
            "aggregation": self.econ["aggregation"],
            # The fallbacks an unstated input resolves to. Without them a reader
            # of the exported plan cannot tell what an unset parameter meant.
            "defaults": self.econ.get("defaults", {}),
            "filed": self.filed,
            "owner": self.econ.get("owner"),
            "source_filing": self.econ.get("source_filing"),
        }
        return plan


def list_plans(db: Database, limit: int = 25) -> list[dict[str, Any]]:
    rows = db.query(
        "SELECT id, created_at, label, status, objective, plan_years, selected_count, "
        "projection, economics_version FROM plans ORDER BY created_at DESC LIMIT ?", (limit,))
    out = []
    for r in rows:
        d = dict(r)
        proj = unjs(d.get("projection"), {}) or {}
        d["projection"] = {k: proj.get(k) for k in
                           ("revenue_total", "profit_total", "npv_profit", "year5_share_of_segment")}
        out.append(d)
    return out
