"""Scoring: attractiveness, right to win, horizon and lifecycle (§4.6, §4.8).

The governing constraint (§3.8): "the scoring model must not produce only a
number — it must explain the number, and if a user cannot explain why a topic is
ranked where it is, the scoring is not good enough."

Every component below therefore returns both a value AND the inputs that
produced it, and both are persisted (DR-05). NFR-01: every displayed number
decomposes into named components; no opaque scores.

Division of labour follows Table 23 exactly:
  * signal counting, diversity, recency, momentum -> ARITHMETIC, never a model.
    "A model asked to count will occasionally be wrong and always be unverifiable."
  * strategic relevance -> rubric-scored by a model with worked anchors.
  * right-to-win -> structured lookup against the graph (SC-15), never asserted
    by a language model.
"""

from __future__ import annotations

import calendar
import datetime as dt
import logging
import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from .config import Config
from .db import Database, js, unjs
from .graph import Linker
from .llm import LLMClient
from .pipeline import prompts

log = logging.getLogger(__name__)


@dataclass
class ComponentResult:
    value: float                       # 0-100
    inputs: dict[str, Any] = field(default_factory=dict)


def _norm(value: float) -> float:
    return max(0.0, min(100.0, value))


class AttractivenessScorer:
    """The five components of SC-01, computed per Table 27."""

    def __init__(self, cfg: Config, db: Database, llm: LLMClient | None = None):
        self.cfg = cfg
        self.db = db
        self.llm = llm
        s = cfg.settings["scoring"]
        self.window_days = int(s["trailing_window_days"])
        self.momentum_periods = int(s["momentum_periods"])
        self.log_base = float(s["signal_volume_log_base"])
        self.no_credible_penalty = float(s["no_credible_evidence_penalty"])
        self.rubric_levels = {int(k): float(v) for k, v in s["rubric_levels"].items()}
        self.tier4_cap = float(cfg.source_tiers["tier4_contribution_cap"])
        self.tier4_discount = float(cfg.source_tiers["diversity_tier4_discount"])

    # -- component 1: market signal strength (30%) --------------------------

    def market_signal_strength(self, signals: list[dict], corpus_max: float) -> ComponentResult:
        """Volume of distinct relevance-gated signals, log-compressed (Table 27).

        Log compression prevents a single noisy topic from saturating the scale;
        normalisation is against the distribution across all live topics, so the
        score answers "how visible is this relative to everything else on the
        radar", not "how many articles exist".
        """
        count = len(signals)
        if count == 0:
            return ComponentResult(0.0, {"signal_count": 0, "note": "no signals in window"})
        compressed = math.log(1 + count, self.log_base)
        ceiling = math.log(1 + max(corpus_max, 1), self.log_base) or 1.0
        value = _norm(100.0 * compressed / ceiling)
        return ComponentResult(value, {
            "signal_count": count,
            "log_compressed": round(compressed, 4),
            "corpus_max_signal_count": corpus_max,
            "formula": f"100 * log_{self.log_base}(1+{count}) / log_{self.log_base}(1+{corpus_max})",
        })

    # -- component 2: source diversity (20%) --------------------------------

    def source_diversity(self, signals: list[dict]) -> ComponentResult:
        """Shannon entropy over the publisher distribution (Table 27).

        §4.3.7: "a topic covered by twenty outlets all syndicating one vendor
        press release is one source, not twenty". Syndicated duplicates are
        collapsed by (publisher, title-prefix) and tier-4 publishers contribute
        at a discount.
        """
        if not signals:
            return ComponentResult(0.0, {"note": "no signals"})

        seen: set[tuple[str, str]] = set()
        weights: Counter[str] = Counter()
        best_tier: dict[str, int] = {}
        collapsed = 0
        for signal in signals:
            publisher = (signal.get("publisher") or "unknown").lower()
            key = (publisher, (signal.get("title") or "")[:60].lower())
            if key in seen:
                collapsed += 1
                continue
            seen.add(key)
            tier = int(signal.get("tier", 3))
            weight = self.tier4_discount if tier == 4 else 1.0
            weights[publisher] += weight
            best_tier[publisher] = min(best_tier.get(publisher, 9), tier)

        total = sum(weights.values())
        if total <= 0 or len(weights) <= 1:
            return ComponentResult(0.0, {
                "distinct_publishers": len(weights), "syndicated_collapsed": collapsed,
                "note": "single publisher — no diversity",
            })
        entropy = -sum((w / total) * math.log(w / total, 2) for w in weights.values())
        # Normalise against the maximum entropy achievable at this publisher
        # count, so a topic is not punished simply for being early.
        max_entropy = math.log(len(weights), 2) or 1.0

        # Breadth counts PUBLISHERS, discounting those that only ever appear at
        # tier 4. Two separate points:
        #
        #  * Shannon entropy is scale-invariant, so a uniform tier-4 discount
        #    cancels out of the entropy ratio entirely — six vendor blogs would
        #    otherwise score exactly as six independent outlets do, which is the
        #    echo-chamber failure §4.3.7 exists to prevent. The discount has to
        #    bite somewhere, and breadth is that somewhere.
        #  * It must count publishers, NOT summed signal weights. Summing the
        #    per-signal weights yields the weighted signal count, so a topic with
        #    twelve publishers and thirty articles reported an "effective
        #    publisher count" of seventeen — a number larger than the publisher
        #    count it claimed to discount, and one that saturated breadth on
        #    volume alone.
        effective_publishers = sum(
            self.tier4_discount if best_tier.get(publisher, 3) == 4 else 1.0
            for publisher in weights
        )
        breadth = min(1.0, effective_publishers / 8.0)
        value = _norm(100.0 * (entropy / max_entropy) * breadth)
        return ComponentResult(value, {
            "distinct_publishers": len(weights),
            "effective_publishers": round(effective_publishers, 3),
            "syndicated_collapsed": collapsed,
            "shannon_entropy_bits": round(entropy, 4),
            "max_entropy_bits": round(max_entropy, 4),
            "breadth_factor": round(breadth, 4),
            "tier4_discount": self.tier4_discount,
            "publishers": dict(weights.most_common(10)),
        })

    # -- component 3: evidence quality (20%) --------------------------------

    def evidence_quality(self, signals: list[dict]) -> ComponentResult:
        """Tier-weighted mean with a floor penalty (Table 27).

        §4.3.7 rule 2: no topic should reach high attractiveness on tier-4
        evidence alone — "this is precisely the 'vendor-specific' case that
        SC-09 says must score low".
        """
        if not signals:
            return ComponentResult(0.0, {"note": "no signals"})
        tiers = Counter(int(s.get("tier", 3)) for s in signals)
        weights = [self.cfg.tier_weight(int(s.get("tier", 3))) for s in signals]
        mean_weight = sum(weights) / len(weights)

        tier4_share = tiers[4] / len(signals)
        capped = False
        if tier4_share > 0:
            # Tier-4 contribution is capped, not merely discounted.
            contribution_cap = self.tier4_cap
            if tier4_share > contribution_cap:
                mean_weight = mean_weight * (1 - (tier4_share - contribution_cap))
                capped = True

        has_credible = (tiers[1] + tiers[2]) > 0
        penalty_applied = False
        if not has_credible:
            mean_weight *= (1 - self.no_credible_penalty)
            penalty_applied = True

        return ComponentResult(_norm(100.0 * mean_weight), {
            "tier_distribution": {str(k): v for k, v in sorted(tiers.items())},
            "tier_weighted_mean": round(mean_weight, 4),
            "tier4_share": round(tier4_share, 4),
            "tier4_cap_applied": capped,
            "no_tier1_or_tier2_penalty_applied": penalty_applied,
            "penalty": self.no_credible_penalty if penalty_applied else 0.0,
        })

    # -- component 4: novelty and momentum (15%) ----------------------------

    def novelty_momentum(self, signals: list[dict], reference_date: dt.date,
                         first_seen: dt.date | None) -> ComponentResult:
        """Slope of recency-weighted volume, plus first-appearance bonus (Table 27).

        §4.4.5: "Momentum is then simply the trajectory of signal accretion,
        which is honest and explainable."
        """
        if not signals:
            return ComponentResult(0.0, {"note": "no signals"})

        period_days = max(1, self.window_days // self.momentum_periods)
        buckets = [0] * self.momentum_periods
        for signal in signals:
            published = _as_date(signal.get("published_at"))
            if published is None:
                continue
            age_days = (reference_date - published).days
            if age_days < 0:
                continue
            index = min(self.momentum_periods - 1, age_days // period_days)
            buckets[self.momentum_periods - 1 - index] += 1   # oldest first

        # Least-squares slope over the bucket series.
        n = len(buckets)
        xs = list(range(n))
        mean_x = sum(xs) / n
        mean_y = sum(buckets) / n
        denominator = sum((x - mean_x) ** 2 for x in xs) or 1.0
        slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, buckets)) / denominator

        # Map slope onto 0-100 with 50 as flat. Scale by the mean level so a
        # topic going 0->1->2 is not treated like one going 0->10->20.
        scale = max(1.0, mean_y)
        value = 50.0 + 50.0 * math.tanh(slope / scale)

        bonus = 0.0
        if first_seen and (reference_date - first_seen).days <= period_days * 2:
            bonus = 10.0                                    # first-appearance bonus
        flat_penalty = 0.0
        if abs(slope) < 0.05 and first_seen and (reference_date - first_seen).days > self.window_days:
            flat_penalty = 15.0                             # long flat history penalty

        return ComponentResult(_norm(value + bonus - flat_penalty), {
            "buckets_oldest_first": buckets,
            "period_days": period_days,
            "slope_per_period": round(slope, 4),
            "first_appearance_bonus": bonus,
            "long_flat_history_penalty": flat_penalty,
            "first_seen": first_seen.isoformat() if first_seen else None,
        })

    # -- component 5: strategic relevance (15%) -----------------------------

    def strategic_relevance(self, topic: dict, links: list[dict] | None = None) -> ComponentResult:
        """Rubric score against Trust the future (Table 23, Table 27, SC-06).

        Deterministic priors are computed first — privileged vertical, sovereign
        deliverability — and the model scores the rubric level. If no model is
        available the deterministic part stands alone, which keeps the pipeline
        runnable and the fallback explainable.
        """
        strategy = self.cfg.strategy
        vertical = topic["vertical"]
        privileged = float(strategy.get("privileged_verticals", {}).get(vertical, 0.0))

        sovereign_evidence: list[str] = []
        for link in links or []:
            evidence = unjs(link.get("evidence"), {}) or {}
            if evidence.get("sovereign"):
                sovereign_evidence.append(link["node_id"])
        for offer in self.cfg.offers.get("offers", []):
            if offer.get("sovereign") and topic["use_case"] in (offer.get("addresses_use_cases") or []):
                sovereign_evidence.append(f"offer:{offer['id']}")

        inputs: dict[str, Any] = {
            "privileged_vertical": vertical if privileged else None,
            "privileged_weight": privileged,
            "sovereign_evidence": sorted(set(sovereign_evidence))[:6],
            "sovereignty_bonus": strategy.get("sovereignty_bonus", 0.0) if sovereign_evidence else 0.0,
        }

        level: int | None = None
        if self.llm is not None:
            try:
                payload = self.llm.complete_json(
                    prompts.strategic_relevance_prompt(self.cfg),
                    _describe_topic_for_rubric(self.cfg, topic),
                    temperature=0.0, max_tokens=400,
                )
                raw_level = payload.get("level")
                if isinstance(raw_level, (int, float)) and 0 <= raw_level <= 5:
                    level = int(raw_level)
                    inputs["rubric_level"] = level
                    inputs["rubric_ambitions"] = payload.get("ambitions", [])
                    inputs["rubric_rationale"] = payload.get("rationale", "")
                    inputs["prompt_version"] = prompts.PROMPT_VERSION_RELEVANCE_RUBRIC
            except Exception as exc:  # noqa: BLE001
                log.warning("Strategic-relevance rubric failed for %s: %s", topic.get("id"), exc)

        if level is None:
            # Deterministic fallback: domain fit against the ambitions' markers.
            text = f"{topic['statement']} {self.cfg.use_cases.label(topic['use_case'])}".lower()
            hits = [
                a["id"] for a in strategy["ambitions"]
                if any(marker.lower() in text for marker in a.get("markers", []))
            ]
            level = 3 if hits else 1
            inputs["rubric_level"] = level
            inputs["rubric_source"] = "deterministic fallback (no model available)"
            inputs["rubric_ambitions"] = hits

        base = self.rubric_levels.get(level, 50.0)
        bonus = 100.0 * (strategy.get("sovereignty_bonus", 0.0) if sovereign_evidence else 0.0)
        privileged_bonus = 10.0 * privileged
        inputs["base_from_rubric_level"] = base
        inputs["privileged_bonus"] = privileged_bonus
        return ComponentResult(_norm(base + bonus + privileged_bonus), inputs)

    # -- combine ------------------------------------------------------------

    def score(self, topic: dict, signals: list[dict], reference_date: dt.date,
              corpus_max: float, links: list[dict] | None = None,
              all_signals: list[dict] | None = None) -> tuple[float, dict, dict]:
        """Combine the five components (SC-01).

        Window scoping follows Table 27 literally. Only two components are
        described there as trailing-window measures:

          market signal strength — "in the trailing window"
          novelty and momentum   — "over the trailing periods"

        Source diversity and evidence quality are described over "the publisher
        distribution" and "contributing signals" with no window, and rightly so:
        they are properties of the evidence BASE, not of its recency. Scoping
        them to the window would zero out a topic resting on solid year-old
        tier-1 regulatory or research evidence, whose age is already penalised
        by the two components that are windowed.
        """
        weights = self.cfg.attractiveness_weights
        first_seen = _as_date(topic.get("first_seen"))
        evidence_base = all_signals if all_signals is not None else signals
        results = {
            "market_signal_strength": self.market_signal_strength(signals, corpus_max),
            "source_diversity": self.source_diversity(evidence_base),
            "evidence_quality": self.evidence_quality(evidence_base),
            "novelty_momentum": self.novelty_momentum(signals, reference_date, first_seen),
            "strategic_relevance": self.strategic_relevance(topic, links),
        }
        components = {k: round(v.value, 2) for k, v in results.items()}
        inputs = {k: v.inputs for k, v in results.items()}
        total = sum(components[k] * weights[k] for k in weights)
        return round(_norm(total), 2), components, inputs


class RightToWinScorer:
    """SC-12 / SC-15 — computed from the graph as named query results.

    §4.6: "Each is a lookup with a stated source, which makes the resulting
    statement inspectable in a way an aggregate score never is."

    Scored and displayed SEPARATELY from attractiveness. The two are never
    collapsed into one number: they answer different questions and are owned by
    different people (§4.1 principle 3).
    """

    def __init__(self, cfg: Config, db: Database):
        self.cfg = cfg
        self.db = db
        self.gap_threshold = int(cfg.references.get("evidence_gap_threshold", 5))
        self._density = self._reference_density()

    def _reference_density(self) -> dict[str, float]:
        """Published story counts apportioned onto the 15 verticals (LK-03)."""
        density: dict[str, float] = {}
        for label, count in (self.cfg.references.get("distribution_by_industry") or {}).items():
            for vertical, share in self.cfg.vertical_for_story_label(label).items():
                density[vertical] = density.get(vertical, 0.0) + count * share
        return density

    def score(self, topic: dict, links: list[dict]) -> tuple[float, dict, dict]:
        vertical = topic["vertical"]
        active = [l for l in links if not l["rejected"]]
        by_prefix: dict[str, list[dict]] = {}
        for link in active:
            by_prefix.setdefault(link["node_id"].split(":", 1)[0], []).append(link)

        components: dict[str, float] = {}
        inputs: dict[str, Any] = {}

        # offer match
        offers = by_prefix.get("offer", [])
        direct = [l for l in offers if l["link_type"] == "L0"]
        components["offer_match"] = _norm(100.0 if direct else (55.0 if offers else 0.0))
        inputs["offer_match"] = {
            "direct_offers": [l["node_id"] for l in direct],
            "bundle_offers": [l["node_id"] for l in offers if l["link_type"] == "L1"],
            "source": "config/business_graph/offers.yaml",
        }

        # reference density
        count = self._density.get(vertical, 0.0)
        named = [l["node_id"] for l in by_prefix.get("reference", [])]
        peak = max(self._density.values()) if self._density else 1.0
        components["reference_density"] = _norm(100.0 * count / peak if peak else 0.0)
        gap = count < self.gap_threshold
        inputs["reference_density"] = {
            "vertical": vertical,
            "published_story_count": round(count, 1),
            "threshold": self.gap_threshold,
            "evidence_gap_warning": gap,          # SC-13
            "named_references_linked": named,
            "source": "orange-business.com customer stories (§2.7, Table 5)",
        }

        # partner coverage
        partners = by_prefix.get("partner", [])
        best_rank = 0.0
        best_partner = None
        for link in partners:
            evidence = unjs(link["evidence"], {}) or {}
            rank = float(evidence.get("tier_rank", 0.0))
            if rank > best_rank:
                best_rank, best_partner = rank, link["node_id"]
        components["partner_coverage"] = _norm(100.0 * best_rank)
        inputs["partner_coverage"] = {
            "partners": [l["node_id"] for l in partners],
            "best_partner": best_partner, "best_tier_rank": best_rank,
            "source": "config/business_graph/assets.yaml (partner pages)",
        }

        # compliance fit
        certs = by_prefix.get("certification", [])
        sovereign_certs = [
            l["node_id"] for l in certs if (unjs(l["evidence"], {}) or {}).get("sovereign")
        ]
        components["compliance_fit"] = _norm(min(100.0, 30.0 * len(certs) + 20.0 * len(sovereign_certs)))
        inputs["compliance_fit"] = {
            "certifications": [l["node_id"] for l in certs],
            "sovereign_certifications": sovereign_certs,
            "source": "config/business_graph/assets.yaml (certifications page)",
        }

        # capability depth
        pools = by_prefix.get("capability_pool", [])
        headcount = 0
        for link in pools:
            headcount += int((unjs(link["evidence"], {}) or {}).get("headcount") or 0)
        # log scale: 7,000 experts is not 17x better than 400.
        components["capability_depth"] = _norm(100.0 * math.log1p(headcount) / math.log1p(10000))
        inputs["capability_depth"] = {
            "pools": [l["node_id"] for l in pools], "total_headcount": headcount,
            "source": "config/business_graph/assets.yaml (corporate presentation §2.2)",
        }

        # external validation
        positions = by_prefix.get("analyst_position", [])
        components["external_validation"] = _norm(100.0 if positions else 0.0)
        inputs["external_validation"] = {
            "analyst_positions": [l["node_id"] for l in positions],
            "source": "config/business_graph/assets.yaml (analyst page §2.8)",
        }

        # technology ownership
        technology = self.cfg.technologies[topic["technology"]]
        owned = bool(technology.get("orange_asset"))
        components["technology_ownership"] = 100.0 if owned else 0.0
        inputs["technology_ownership"] = {
            "technology": topic["technology"],
            "orange_asset": owned,
            "note": "Portfolio-level prior. Per-technology patent counts require the deferred "
                    "patents connector (§2.5, config/sources.yaml).",
            "source": "config/taxonomy/technologies.yaml",
        }

        weights = self.cfg.right_to_win_weights
        total = sum(components[k] * weights[k] for k in weights)
        inputs["_evidence_gap"] = gap
        return round(_norm(total), 2), {k: round(v, 2) for k, v in components.items()}, inputs


# ---------------------------------------------------------------------------
# Horizon derivation (§4.8, FR-08)
# ---------------------------------------------------------------------------

def derive_horizon(cfg: Config, topic: dict, signals: list[dict], reference_date: dt.date) -> dict[str, Any]:
    """Derive Now / Next / Later rather than judge it (§4.8).

    "Time horizon should be derived rather than judged wherever possible,
    because derived classifications are explainable and consistent."

    Now:   a dated compliance deadline or budgeted procurement within 12 months,
           or a deployable standard release plus live tenders.
    Next:  regulation adopted but not yet applicable, standards frozen but not
           deployed, pilots published but no volume procurement.
    Later: research and patent activity rising, policy consultation open, no
           product-grade offer in the market.
    """
    horizon_cfg = cfg.settings["horizon"]
    now_months = int(horizon_cfg["now_max_months"])
    # NFR-11: thresholds are configuration, not code. This one was read and then
    # ignored — test 1 below compared against a hard-coded 365 days, so moving
    # `now_max_months` in settings.yaml changed nothing and the docstring, the
    # config and the behaviour could disagree without anybody noticing.
    now_window_days = (reference_date - _months_before(reference_date, now_months)).days

    by_type = Counter(s.get("signal_type") for s in signals)
    procurement = [s for s in signals if s.get("signal_type") == "buying_signal"]
    regulation = [s for s in signals if s.get("signal_type") == "regulation"]
    maturity = [s for s in signals if s.get("signal_type") == "technology_maturity"]
    proof = [s for s in signals if s.get("signal_type") == "proof_signal"]

    recent_procurement = [
        s for s in procurement
        if (published := _as_date(s.get("published_at")))
        and (reference_date - published).days <= now_window_days
    ]

    # Test 1 — Now: budgeted procurement inside the window.
    if recent_procurement:
        return {
            "value": "now",
            "basis": f"budgeted_procurement_within_{now_months}_months",
            "anchor_date": None,
            "test_applied": (f"{len(recent_procurement)} procurement signal(s) within "
                             f"{now_months} months of the reference date"),
            "evidence": [s["id"] for s in recent_procurement[:5]],
        }

    # Test 2 — Now: an adopted instrument plus a proof signal.
    adopted = [s for s in regulation if (unjs(s.get("attributes"), {}) or {}).get("instrument_stage") == "adopted"]
    if adopted and proof:
        return {
            "value": "now",
            "basis": "adopted_instrument_plus_deployment_evidence",
            "anchor_date": None,
            "test_applied": "an adopted legal instrument co-occurs with published deployment evidence",
            "evidence": [s["id"] for s in (adopted[:3] + proof[:2])],
        }

    # Test 3 — Next: regulation adopted or proposed, not yet applicable.
    if regulation:
        stages = [(unjs(s.get("attributes"), {}) or {}).get("instrument_stage") for s in regulation]
        return {
            "value": "next",
            "basis": "regulation_adopted_or_proposed_not_yet_applicable",
            "anchor_date": None,
            "test_applied": f"regulatory signals present at stage(s) {sorted(set(x for x in stages if x))}",
            "evidence": [s["id"] for s in regulation[:5]],
        }

    # Test 4 — Next: pilots published but no volume procurement.
    if proof and not procurement:
        return {
            "value": "next",
            "basis": "pilots_published_no_volume_procurement",
            "anchor_date": None,
            "test_applied": "proof signals exist but no procurement activity was observed",
            "evidence": [s["id"] for s in proof[:5]],
        }

    # Test 5 — Later: research and maturity activity only.
    if maturity and not proof and not procurement:
        return {
            "value": "later",
            "basis": "research_and_standards_activity_only",
            "anchor_date": None,
            "test_applied": "technology-maturity signals only; no proof or procurement evidence",
            "evidence": [s["id"] for s in maturity[:5]],
        }

    return {
        "value": "later",
        "basis": "insufficient_dated_evidence_to_derive",
        "anchor_date": None,
        "test_applied": f"no derivation test matched; signal-type mix {dict(by_type)}",
        "evidence": [],
    }


# ---------------------------------------------------------------------------
# Lifecycle state machine (§4.8, FR-09)
# ---------------------------------------------------------------------------

def next_state(cfg: Config, topic: dict, signals: list[dict], components: dict[str, float],
               reference_date: dt.date, all_signals: list[dict] | None = None) -> tuple[str, str]:
    """Table 32 state machine.

    "A topic whose signal flow stops does not vanish. It decays through the
    lifecycle states, which is how the briefing's 'topics enter, rise, and fade'
    behaviour actually gets implemented" (§4.4.5).

    `signals` are those inside the trailing scoring window and drive the volume
    and diversity thresholds. `all_signals` is every signal ever attached and
    drives RECENCY: several connectors ingest a wider window than the scoring
    window (OpenAlex looks back a year), so a topic built from older research
    genuinely has no recent signal but is not therefore evidence-free.
    """
    life = cfg.settings["lifecycle"]
    promote = life["promote_to_active"]
    period_days = int(life["period_days"])
    current = topic.get("state", "candidate")

    if current == "rejected":
        return "rejected", topic.get("state_reason") or "previously rejected"

    # Promotion thresholds count the whole evidence base, for the same reason
    # evidence quality does: a topic supported by four tier-1 regulatory items
    # published five months ago is not thin, it is simply not breaking news.
    recency_pool = all_signals if all_signals is not None else signals
    publishers = {(s.get("publisher") or "").lower() for s in recency_pool}
    non_tier4 = [s for s in recency_pool if int(s.get("tier", 3)) < 4]
    latest = max(
        (d for s in recency_pool if (d := _as_date(s.get("published_at")))),
        default=None,
    )
    periods_silent = (
        (reference_date - latest).days // period_days if latest else 999
    )

    # A topic discovered on this refresh cannot be dormant: dormancy means
    # "no qualifying signal for n periods", which presupposes that the topic
    # has existed for n periods. Without this guard, every topic built from
    # older evidence would be filed as dormant on the run that created it.
    first_seen = _as_date(topic.get("first_seen")) or reference_date
    periods_observed = max(0, (reference_date - first_seen).days // period_days)

    meets_promotion = (
        len(recency_pool) >= int(promote["min_signals"])
        and len(publishers) >= int(promote["min_distinct_publishers"])
        and components.get("evidence_quality", 0) >= float(promote["min_evidence_quality"])
        and (not promote.get("require_non_tier4_evidence") or bool(non_tier4))
    )
    detail = (
        f"{len(recency_pool)} signals ({len(signals)} in window), {len(publishers)} publishers, "
        f"evidence quality {components.get('evidence_quality', 0):.0f}, "
        f"{len(non_tier4)} non-tier-4"
    )

    dormant_after = int(life["dormant_after_periods"])
    if periods_silent >= dormant_after and periods_observed >= dormant_after:
        return "dormant", f"no qualifying signal for {periods_silent} periods"

    if meets_promotion:
        if current in ("candidate", "watchlist", "dormant"):
            return "active", f"met promotion thresholds ({detail})"
        if current == "fading" and components.get("novelty_momentum", 50) > 50:
            return "active", f"momentum recovered ({detail})"
        if current == "active" and periods_silent >= int(life["fading_after_periods"]):
            return "fading", f"no new signal for {periods_silent} period(s)"
        return current, f"thresholds still met ({detail})"

    if current == "active":
        if components.get("novelty_momentum", 50) < 50 or periods_silent >= int(life["fading_after_periods"]):
            return "fading", f"below promotion thresholds and momentum negative ({detail})"
        return "active", f"retained ({detail})"

    if len(signals) >= int(life["watchlist_min_signals"]):
        return "watchlist", f"real but thin: {detail}"
    return "candidate", f"insufficient evidence: {detail}"


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

class ScoringEngine:
    def __init__(self, cfg: Config, db: Database, llm: LLMClient | None = None):
        self.cfg = cfg
        self.db = db
        self.llm = llm
        self.attractiveness = AttractivenessScorer(cfg, db, llm)
        self.right_to_win = RightToWinScorer(cfg, db)
        self.linker = Linker(cfg, db)

    def run(self, refresh_id: str, reference_date: dt.date,
            topic_ids: list[str] | None = None) -> dict[str, Any]:
        """Score every live topic, or just `topic_ids`.

        The subset form exists for constrained generation: scoring five new
        spaces should not spend a strategic-relevance model call on the other
        two hundred and ninety. NORMALISATION STILL READS THE WHOLE CORPUS —
        Table 27 normalises market signal strength against the distribution
        across all live topics, so scoping the write set must not scope the
        denominator, or the five new topics would be scored on a scale of their
        own and rank against the rest meaninglessly.
        """
        topics = self.db.query("SELECT * FROM opportunity_spaces WHERE merged_into IS NULL")
        if not topics:
            return {"scored": 0}
        scope = set(topic_ids) if topic_ids is not None else None

        window_start = (reference_date - dt.timedelta(days=self.attractiveness.window_days)).isoformat()
        signals_by_topic: dict[str, list[dict]] = {}
        all_signals_by_topic: dict[str, list[dict]] = {}
        for topic in topics:
            if scope is not None and topic["id"] not in scope:
                continue
            # Everything attached and published on or before the reference date.
            # The reference-date bound is the FR-35 leakage control and applies
            # on replay as well as on a live refresh.
            every = self.db.query(
                """SELECT s.* FROM signals s
                   JOIN opportunity_signals os ON os.signal_id = s.id
                   WHERE os.opportunity_id = ? AND s.published_at <= ?""",
                (topic["id"], reference_date.isoformat()),
            )
            all_signals_by_topic[topic["id"]] = [dict(r) for r in every]
            signals_by_topic[topic["id"]] = [
                r for r in all_signals_by_topic[topic["id"]] if r["published_at"] >= window_start
            ]

        # Normalisation is against the distribution across all live topics
        # (Table 27), so the corpus maximum is computed once per refresh — over
        # the WHOLE corpus even when the write set is scoped. Scoped runs read it
        # as a single grouped count rather than materialising every signal row of
        # three hundred topics they are not going to score.
        if scope is None:
            corpus_max = max((len(v) for v in signals_by_topic.values()), default=1)
        else:
            corpus_max = self.db.query_one(
                """SELECT MAX(n) m FROM (
                       SELECT COUNT(*) n FROM opportunity_signals os
                       JOIN signals s ON s.id = os.signal_id
                       JOIN opportunity_spaces o ON o.id = os.opportunity_id
                       WHERE o.merged_into IS NULL AND s.published_at <= ? AND s.published_at >= ?
                       GROUP BY os.opportunity_id)""",
                (reference_date.isoformat(), window_start),
            )["m"] or 1

        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        scored = 0
        state_changes: list[dict[str, str]] = []

        with self.db.cursor() as cur:
            for topic in topics:
                if topic["id"] not in signals_by_topic:
                    continue
                topic_dict = dict(topic)
                signals = signals_by_topic[topic["id"]]
                links = [dict(r) for r in self.db.query(
                    "SELECT * FROM opportunity_links WHERE opportunity_id = ?", (topic["id"],)
                )]

                all_signals = all_signals_by_topic[topic["id"]]
                att_score, att_components, att_inputs = self.attractiveness.score(
                    topic_dict, signals, reference_date, corpus_max, links, all_signals
                )
                rtw_score, rtw_components, rtw_inputs = self.right_to_win.score(topic_dict, links)

                for kind, score, components, inputs in (
                    ("attractiveness", att_score, att_components, att_inputs),
                    ("right_to_win", rtw_score, rtw_components, rtw_inputs),
                ):
                    cur.execute(
                        """INSERT INTO scores (opportunity_id, computed_at, refresh_id, kind, score,
                                               components, inputs, weight_set, pipeline_version, model_version)
                           VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (topic["id"], now, refresh_id, kind, score, js(components), js(inputs),
                         self.cfg.weight_set, self.cfg.pipeline_version,
                         self.llm.strong_model if self.llm else None),
                    )

                # Horizon reads every attached signal: a compliance deadline
                # published 14 months ago still dates the buying window.
                horizon = derive_horizon(self.cfg, topic_dict, all_signals, reference_date)
                state, reason = next_state(
                    self.cfg, topic_dict, signals, att_components, reference_date, all_signals
                )
                if state != topic["state"]:
                    state_changes.append({"id": topic["id"], "from": topic["state"], "to": state,
                                          "reason": reason})
                    cur.execute(
                        "UPDATE opportunity_spaces SET state = ?, state_reason = ?, state_changed_at = ? WHERE id = ?",
                        (state, reason, reference_date.isoformat(), topic["id"]),
                    )
                else:
                    cur.execute(
                        "UPDATE opportunity_spaces SET state_reason = ? WHERE id = ?", (reason, topic["id"])
                    )

                cur.execute(
                    "UPDATE opportunity_spaces SET horizon = ?, horizon_basis = ?, horizon_anchor_date = ?, "
                    "last_refresh = ? WHERE id = ?",
                    (horizon["value"], horizon["basis"], horizon["anchor_date"],
                     reference_date.isoformat(), topic["id"]),
                )
                scored += 1

        return {"scored": scored, "state_changes": state_changes, "corpus_max_signals": corpus_max}


def _months_before(reference: dt.date, months: int) -> dt.date:
    """`reference` less `months` calendar months, landing on a day that exists.

    Calendar months rather than `months * 30`: the config is written in months
    because that is how a procurement cycle is discussed, and 12 of them is a
    year on the calendar whether or not it is a leap one.
    """
    total = reference.year * 12 + (reference.month - 1) - max(0, months)
    year, month = divmod(total, 12)
    day = min(reference.day, calendar.monthrange(year, month + 1)[1])
    return dt.date(year, month + 1, day)


def _as_date(value: Any) -> dt.date | None:
    if value is None:
        return None
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def _describe_topic_for_rubric(cfg: Config, topic: dict) -> str:
    return (
        f"OPPORTUNITY SPACE\n"
        f"Statement: {topic['statement']}\n"
        f"Vertical: {cfg.verticals.label(topic['vertical'])} ({topic['vertical']})\n"
        f"Use case: {cfg.use_cases.label(topic['use_case'])} ({topic['use_case']})\n"
        f"Technology: {cfg.technologies.label(topic['technology'])} ({topic['technology']})\n"
        f"Domains: {', '.join(unjs(topic.get('domains'), []) or [])}\n"
        f"Score the strategic relevance level. Return JSON."
    )
