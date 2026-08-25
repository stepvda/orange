"""Market sizing (§4.3.4, Table 19).

§4.3.4 is a warning before it is a requirement:

    "the headline market-size figures circulating in press coverage almost
    always originate from paid research houses, are quoted without methodology,
    and frequently conflict by an order of magnitude. The radar should prefer a
    transparent bottom-up estimate — enterprise count in the vertical x adoption
    rate x plausible contract value — and show its working, rather than
    repeating an unattributable billion-euro number."

So this module computes, it does not retrieve, and it never asks a model. Two
independent methods run per topic and both are published:

  bottom_up_adoption   Eurostat enterprise counts (SBS) x Eurostat enterprise
                       adoption rate (ICT survey) x observed contract value
                       (TED). The estimate §4.3.4 asks for, factor by factor.

  procurement_observed Real contract values already awarded or tendered in the
                       matching CPV categories, annualised. Not a market size in
                       the analyst sense — a floor, made of contracts that
                       actually exist. For public-sector verticals it is the
                       better evidence, and SBS has no enterprise count for
                       public administration anyway.

Publishing both is the point: two methods built from different data that land in
the same order of magnitude is an argument; one number with no method is not.

Every factor records where it came from, which year, and whether it is observed,
a declared proxy or a configured assumption (DR-05). Every stored size records
the sizing config version, for the same reason a score records its weight set
(SC-10): sizes computed under different assumptions are not comparable.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from .config import Config
from .db import Database, js, unjs

log = logging.getLogger(__name__)

#: The ICT survey's own size base. Recorded so the engine can assert that the
#: denominator and the adoption rate share one (see `Denominator`).
ICT_SIZE_CLASS = "GE10"

#: Eurostat's all-activities aggregate, used when a sector has no published
#: adoption rate of its own — the ICT survey excludes finance, public
#: administration, health and mining. Always flagged as a proxy when used.
ALL_ACTIVITIES = "C10-S951_X_K"

BOTTOM_UP = "bottom_up_adoption"
PROCUREMENT = "procurement_observed"

#: Below this many matching notices the observed flow is an anecdote rather than
#: a measurement, and no procurement estimate is published.
MIN_NOTICES_FOR_OBSERVED = 3

#: Never scale an observation up from a window shorter than this. A one-day
#: window multiplied by 365 is not an annual figure, it is an artefact.
MIN_WINDOW_DAYS = 30

#: Basis of a factor, worst-first. The confidence grade of a whole estimate is
#: the worst basis among its factors, never an average: an estimate is exactly
#: as trustworthy as its weakest input.
OBSERVED, PROXY, ASSUMPTION = "observed", "proxy", "assumption"
_BASIS_RANK = {OBSERVED: 0, PROXY: 1, ASSUMPTION: 2}
#: Factors that are modelling choices rather than measurements. They are
#: published, and they are excluded from the confidence grade, which is about
#: the quality of the evidence going in.
_MODELLING_FACTORS = {"obtainable_share", "size_mix"}
_GRADE = {0: "observed", 1: "partial", 2: "modelled"}


@dataclass
class Factor:
    """One input to a size, with everything needed to re-derive or dispute it."""

    name: str
    label: str
    value: float
    unit: str
    basis: str                       # observed | proxy | assumption
    low: float | None = None
    high: float | None = None
    source: dict[str, Any] = field(default_factory=dict)
    detail: dict[str, Any] = field(default_factory=dict)
    note: str = ""


@dataclass
class Estimate:
    method: str
    tam: dict[str, float | None]
    sam: dict[str, float | None]
    som: dict[str, float | None]
    confidence: str
    factors: list[Factor]
    coverage: dict[str, Any]
    caveats: list[str]

    def as_row(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "tam": self.tam,
            "sam": self.sam,
            "som": self.som,
            "confidence": self.confidence,
            "factors": [asdict(f) for f in self.factors],
            "coverage": self.coverage,
            "caveats": self.caveats,
        }


@dataclass
class Denominator:
    total: float
    serviceable: float
    #: Size-weighted counts. A ten-person enterprise and a ten-thousand-person
    #: one both count as one enterprise in `total`, and do not both buy the same
    #: contract — `effective` is `total` weighted toward the classes the
    #: observed contract value actually came from.
    effective: float
    effective_serviceable: float
    by_size_class: dict[str, float]
    slices: list[dict[str, Any]]
    period: str
    geographies: list[str]


def _band(base: float, relative: float) -> tuple[float, float]:
    return base * (1 - relative), base * (1 + relative)


def _clamp(value: float, low: float, high: float) -> float:
    return max(float(low), min(float(high), value))


def _quantile(values: list[float], q: float) -> float:
    """Linear-interpolated quantile, without a numpy dependency in the hot path."""
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = q * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


class MarketSizer:
    """Bottom-up and procurement-observed sizing for opportunity spaces."""

    def __init__(self, cfg: Config, db: Database):
        self.cfg = cfg
        self.db = db
        self.sizing = cfg.sizing
        self.scope = self.sizing["scope"]
        self.contract_cfg = self.sizing["contract_value"]
        self.uncertainty = self.sizing["uncertainty"]
        self._series_meta = {
            row["id"]: dict(row) for row in db.query("SELECT * FROM reference_series")
        }
        self._procurement_index: dict[str, dict[str, list[dict[str, Any]]]] | None = None

    # ------------------------------------------------------------------
    # Entry points
    # ------------------------------------------------------------------

    def run(self, states: tuple[str, ...] = ("active", "watchlist", "fading", "candidate"),
            topic_ids: list[str] | None = None) -> dict[str, Any]:
        """Size every live topic and store the results."""
        self.db.init_schema()
        if topic_ids:
            placeholders = ",".join("?" * len(topic_ids))
            rows = self.db.query(
                f"SELECT * FROM opportunity_spaces WHERE id IN ({placeholders}) AND merged_into IS NULL",
                tuple(topic_ids),
            )
        else:
            placeholders = ",".join("?" * len(states))
            rows = self.db.query(
                f"SELECT * FROM opportunity_spaces WHERE merged_into IS NULL AND state IN ({placeholders})",
                states,
            )
        if not self._series_meta:
            log.warning("No reference series present — run `radar reference-data` first. "
                        "Only the procurement-observed method can run.")

        stats = {"topics": 0, "estimates": 0, "by_method": {}, "by_confidence": {}, "no_estimate": []}
        for row in rows:
            topic = dict(row)
            estimates = self.size_topic(topic)
            stats["topics"] += 1
            if not estimates:
                stats["no_estimate"].append(topic["id"])
                continue
            self._store(topic["id"], estimates)
            for estimate in estimates:
                stats["estimates"] += 1
                stats["by_method"][estimate.method] = stats["by_method"].get(estimate.method, 0) + 1
                stats["by_confidence"][estimate.confidence] = (
                    stats["by_confidence"].get(estimate.confidence, 0) + 1
                )
        return stats

    def size_topic(self, topic: dict[str, Any]) -> list[Estimate]:
        geographies, coverage = self._resolve_geographies(unjs(topic["geographies"], []) or [])
        right_to_win, distance = self._win_position(topic["id"])
        estimates: list[Estimate] = []

        bottom_up = self._bottom_up(topic, geographies, coverage, right_to_win, distance)
        if bottom_up is not None:
            estimates.append(bottom_up)

        observed = self._procurement_observed(topic, geographies, coverage, right_to_win, distance)
        if observed is not None:
            estimates.append(observed)
        return estimates

    # ------------------------------------------------------------------
    # Scope
    # ------------------------------------------------------------------

    def _resolve_geographies(self, requested: list[str]) -> tuple[list[str], dict[str, Any]]:
        """Map a topic's declared geographies onto what Eurostat actually covers.

        NFR-08 asks for coverage to be reported rather than assumed, so the
        geographies that fall outside the reference data are named in the
        result instead of quietly disappearing into an EU-wide number.
        """
        available = set(self.scope["fetch_geographies"])
        eu = self.scope["eu_aggregate"]
        requested = [g.upper() for g in requested]

        covered = [g for g in requested if g in available]
        uncovered = [g for g in requested if g not in available and g != "EU"]
        uses_eu = "EU" in requested or not covered

        if uses_eu:
            # The EU aggregate contains every member state, so mixing it with
            # country rows would double count. The aggregate wins, and the
            # named countries are recorded as being inside it.
            scope_geographies = [eu]
            inside = [g for g in covered if g != eu]
        else:
            scope_geographies = covered
            inside = []

        coverage = {
            "requested": requested,
            "used": scope_geographies,
            "inside_aggregate": inside,
            "outside_reference_data": uncovered,
            "basis": "EU aggregate" if uses_eu else "named member states",
        }
        if uncovered:
            coverage["note"] = (
                f"{len(uncovered)} of {len(requested)} declared geographies are outside the "
                f"European reference data ({', '.join(uncovered)}); the estimate covers the "
                f"European footprint only."
            )
        return scope_geographies, coverage

    def _win_position(self, topic_id: str) -> tuple[float, int]:
        row = self.db.query_one(
            "SELECT score FROM scores WHERE opportunity_id = ? AND kind = 'right_to_win' "
            "ORDER BY computed_at DESC, id DESC LIMIT 1", (topic_id,)
        )
        right_to_win = float(row["score"]) if row else 0.0
        links = self.db.query(
            "SELECT link_type FROM opportunity_links WHERE opportunity_id = ? AND rejected = 0",
            (topic_id,),
        )
        # Same rule as the read model: only delivery-bearing links shorten the
        # distance. Supporting evidence (SUP) is not a path to delivery.
        distances = [int(r["link_type"][1]) for r in links if r["link_type"] in ("L0", "L1", "L2", "L3", "L4")]
        return right_to_win, min(distances, default=4)

    # ------------------------------------------------------------------
    # Method 1 — bottom up
    # ------------------------------------------------------------------

    def _bottom_up(self, topic: dict[str, Any], geographies: list[str], coverage: dict[str, Any],
                   right_to_win: float, distance: int) -> Estimate | None:
        vertical = topic["vertical"]
        rows = self.cfg.vertical_to_nace.get(vertical) or []
        if not rows:
            # public_sector and defense deliberately carry no NACE row: Eurostat
            # SBS is the business economy, and public administration is not in
            # it. Those verticals are sized from procurement instead.
            return None

        denominator = self._enterprise_denominator(rows, geographies)
        if denominator is None or denominator.total <= 0:
            return None

        adoption = self._adoption_factor(topic, rows, geographies, denominator)
        if adoption is None:
            return None

        contract = self._contract_value_factor(topic)
        caveats: list[str] = []
        factors: list[Factor] = []

        enterprise_low, enterprise_high = _band(denominator.total, self.uncertainty["enterprises"])
        series = self._series_meta.get("sbs", {})
        factors.append(Factor(
            name="enterprises",
            label=f"Enterprises in {self.cfg.verticals.label(vertical)} ({'+'.join(geographies)})",
            value=denominator.total,
            unit="enterprises",
            basis=OBSERVED,
            low=enterprise_low,
            high=enterprise_high,
            source={
                "publisher": series.get("publisher", "Eurostat"),
                "dataset": series.get("dataset", "sbs_sc_ovw"),
                "url": series.get("url", ""),
                "period": denominator.period,
                "updated": series.get("source_updated"),
                "licence": series.get("licence", ""),
            },
            detail={
                "size_classes": self.scope["size_classes"],
                "serviceable_size_classes": self.scope["serviceable_size_classes"],
                "serviceable": denominator.serviceable,
                "slices": denominator.slices[:24],
                "nace_codes": sorted({r.sbs_nace for r in rows}),
            },
            note=("Restricted to enterprises with 10 or more persons employed, the same base "
                  "Eurostat publishes the adoption rate on."),
        ))
        factors.append(adoption)
        factors.append(contract)

        if adoption.basis == PROXY:
            caveats.append(f"Adoption rate is a declared proxy. {adoption.note}")
        if contract.basis == ASSUMPTION:
            caveats.append(f"Contract value is a configured assumption, not observed. {contract.note}")
        elif contract.detail.get("proxy_for_private_sector"):
            caveats.append(self.contract_cfg["private_sector_proxy_note"].strip())
        caveats.append(
            "Engagement value is scaled by enterprise size class "
            f"({', '.join(f'{k}: x{v}' for k, v in self.contract_cfg['size_class_value_weights'].items())}), "
            "because the observed contract value comes from large-organisation tenders."
        )
        if coverage.get("note"):
            caveats.append(coverage["note"])
        crosswalk_proxies = sorted({r.note for r in rows if r.note.startswith("PROXY")})
        if crosswalk_proxies:
            caveats.append(
                "Sector adoption is read from Eurostat's all-activities aggregate for part of this "
                "vertical, which the enterprise ICT survey does not cover separately: "
                + "; ".join(crosswalk_proxies)
            )

        adoption_rate = adoption.value / 100.0
        adoption_low = (adoption.low or adoption.value) / 100.0
        adoption_high = (adoption.high or adoption.value) / 100.0

        size_mix = Factor(
            name="size_mix",
            label="Size-weighted buyer base",
            value=denominator.effective,
            unit="enterprise-equivalents at large-enterprise engagement value",
            basis=ASSUMPTION,
            source={"publisher": "config/sizing.yaml", "dataset": "size_class_value_weights",
                    "period": self.cfg.sizing_version, "owner": self.sizing["owner"]},
            detail={
                "weights": self.contract_cfg["size_class_value_weights"],
                "enterprises_by_size_class": {k: round(v) for k, v in denominator.by_size_class.items()},
                "effective_serviceable": denominator.effective_serviceable,
            },
            note=("The observed contract value is a large-organisation contract. Applied flat to "
                  "every enterprise it would price a twelve-person manufacturer's deployment at a "
                  "ministry's budget, so engagement value is scaled per size class, anchored on the "
                  "250+ class the observed contracts came from."),
        )
        factors.append(size_mix)

        def money(enterprises: tuple[float, float, float]) -> dict[str, float]:
            low, base, high = enterprises
            return {
                "low": low * adoption_low * (contract.low or contract.value),
                "base": base * adoption_rate * contract.value,
                "high": high * adoption_high * (contract.high or contract.value),
            }

        effective_low, effective_high = _band(denominator.effective, self.uncertainty["enterprises"])
        serviceable_low, serviceable_high = _band(
            denominator.effective_serviceable, self.uncertainty["enterprises"]
        )
        tam = money((effective_low, denominator.effective, effective_high))
        sam = money((serviceable_low, denominator.effective_serviceable, serviceable_high))
        som, share_factor = self._obtainable(sam, right_to_win, distance)
        factors.append(share_factor)

        # The grade describes the DATA, so the two declared modelling choices —
        # the size-class weighting and the obtainable share — are excluded from
        # it and carried as caveats instead. Otherwise every estimate would read
        # "modelled" and the word would stop distinguishing anything.
        confidence = _GRADE[max(_BASIS_RANK[f.basis] for f in factors if f.name not in _MODELLING_FACTORS)]
        return Estimate(
            method=BOTTOM_UP,
            tam=tam, sam=sam, som=som,
            confidence=confidence,
            factors=factors,
            coverage=coverage,
            caveats=caveats,
        )

    def _enterprise_denominator(self, rows, geographies: list[str]) -> Denominator | None:
        """Eurostat SBS enterprise counts across the vertical's NACE slices.

        The crosswalk's per-row confidence is applied as a weight, not dropped:
        NACE G45 (motor trade) is shared between retail and automotive, so
        counting it whole in both would size the same enterprises twice.
        """
        size_classes = self.scope["size_classes"]
        serviceable_classes = set(self.scope["serviceable_size_classes"])
        weights = self.contract_cfg["size_class_value_weights"]
        total = serviceable = effective = effective_serviceable = 0.0
        by_size_class: dict[str, float] = {}
        slices: list[dict[str, Any]] = []
        periods: set[str] = set()

        for row in rows:
            for geo in geographies:
                for size_class in size_classes:
                    observation = self._latest(
                        "sbs", self.sizing["reference_datasets"]["sbs"]["indicators"]["enterprises"],
                        row.sbs_nace, geo, size_class,
                    )
                    if observation is None:
                        continue
                    weighted = observation["value"] * row.confidence
                    scaled = weighted * float(weights.get(size_class, 1.0))
                    total += weighted
                    effective += scaled
                    by_size_class[size_class] = by_size_class.get(size_class, 0.0) + weighted
                    if size_class in serviceable_classes:
                        serviceable += weighted
                        effective_serviceable += scaled
                    periods.add(observation["period"])
                    slices.append({
                        "nace": row.sbs_nace,
                        "geo": geo,
                        "size_class": size_class,
                        "enterprises": observation["value"],
                        "crosswalk_confidence": row.confidence,
                        "period": observation["period"],
                        "note": row.note,
                    })
        if not slices:
            return None
        return Denominator(
            total=total,
            serviceable=serviceable,
            effective=effective,
            effective_serviceable=effective_serviceable,
            by_size_class=by_size_class,
            slices=sorted(slices, key=lambda s: -s["enterprises"]),
            period=max(periods),
            geographies=geographies,
        )

    def _adoption_factor(self, topic: dict[str, Any], rows, geographies: list[str],
                         denominator: Denominator) -> Factor | None:
        """Enterprise-weighted adoption rate for the topic's technology.

        Weighted by the enterprise counts of the same slices, so a vertical
        whose enterprises sit mostly in one NACE aggregate takes that
        aggregate's rate rather than an unweighted average across aggregates.
        """
        mapping = self.cfg.technology_to_adoption.get(topic["technology"])
        if mapping is None:
            return None
        spec = self.sizing["reference_datasets"][mapping.dataset]

        # Enterprise weight per (ict_nace, geo), from the denominator's slices.
        weights: dict[tuple[str, str], float] = {}
        nace_by_sbs = {row.sbs_nace: row.ict_nace for row in rows}
        for entry in denominator.slices:
            key = (nace_by_sbs.get(entry["nace"], ALL_ACTIVITIES), entry["geo"])
            weights[key] = weights.get(key, 0.0) + entry["enterprises"] * entry["crosswalk_confidence"]

        # A crosswalk row that points at the all-activities aggregate is a
        # declared proxy by construction: that aggregate is, by definition, not
        # this sector's rate. The ICT survey excludes finance, health, public
        # administration and mining outright, and those rows say so.
        used_proxy_sector = any(row.ict_nace == ALL_ACTIVITIES for row in rows)
        weighted_sum = weight_total = 0.0
        periods: set[str] = set()
        trend: list[dict[str, Any]] = []
        detail_cells: list[dict[str, Any]] = []

        for (nace, geo), weight in weights.items():
            observation = self._latest(mapping.dataset, mapping.indicator, nace, geo, ICT_SIZE_CLASS)
            cell_nace = nace
            if observation is None:
                # The enterprise ICT survey does not cover every aggregate; the
                # all-activities rate stands in, and says so.
                observation = self._latest(
                    mapping.dataset, mapping.indicator, ALL_ACTIVITIES, geo, ICT_SIZE_CLASS
                )
                cell_nace = ALL_ACTIVITIES
                used_proxy_sector = observation is not None
            if observation is None:
                continue
            weighted_sum += observation["value"] * weight
            weight_total += weight
            periods.add(observation["period"])
            detail_cells.append({
                "nace": cell_nace, "geo": geo, "rate_pc": observation["value"],
                "period": observation["period"], "enterprise_weight": round(weight, 1),
            })
            history = self._history(mapping.dataset, mapping.indicator, cell_nace, geo, ICT_SIZE_CLASS)
            if len(history) >= 2:
                trend.append({
                    "nace": cell_nace, "geo": geo,
                    "from": {"period": history[0]["period"], "rate_pc": history[0]["value"]},
                    "to": {"period": history[-1]["period"], "rate_pc": history[-1]["value"]},
                })

        if weight_total <= 0:
            return None
        rate = weighted_sum / weight_total
        is_proxy = mapping.proxy or used_proxy_sector
        relative = self.uncertainty["adoption_proxy"] if is_proxy else self.uncertainty["adoption_observed"]
        low, high = _band(rate, relative)
        series = self._series_meta.get(mapping.dataset, {})

        note = mapping.note
        if mapping.proxy:
            note = (f"{spec['label']} series {mapping.indicator} is used as a proxy for "
                    f"{self.cfg.technologies.label(topic['technology'])}: {mapping.note}.")
        if used_proxy_sector:
            note = (note + " Part of this vertical is not covered separately by the enterprise ICT "
                           "survey, so the all-activities rate was used for those slices.").strip()

        return Factor(
            name="adoption_rate",
            label=f"Enterprises adopting {self.cfg.technologies.label(topic['technology'])}",
            value=rate,
            unit="% of enterprises (10+ employees)",
            basis=PROXY if is_proxy else OBSERVED,
            low=max(0.0, low), high=min(100.0, high),
            source={
                "publisher": series.get("publisher", "Eurostat"),
                "dataset": series.get("dataset", spec["dataset"]),
                "indicator": mapping.indicator,
                "url": series.get("url", spec["url"]),
                "period": max(periods) if periods else "",
                "updated": series.get("source_updated"),
                "licence": series.get("licence", spec.get("licence", "")),
            },
            detail={
                "cells": sorted(detail_cells, key=lambda c: -c["enterprise_weight"])[:16],
                "trend": trend[:8],
                "crosswalk_confidence": mapping.confidence,
                "indicator_label": mapping.note,
            },
            note=note,
        )

    def _contract_value_factor(self, topic: dict[str, Any]) -> Factor:
        """Annual value of one engagement, from observed tenders where possible.

        §4.3.4 calls this factor "plausible contract value" and leaves it open.
        The only attributable evidence available is TED: real contracts, with
        real values, already in the signal store because procurement is a
        first-class source (§4.3.3). Where a topic has too few matching notices
        to be robust, a configured band per domain is used instead — declared as
        an assumption, with an owner, rather than presented as evidence.
        """
        matches = self._matching_notices(topic)
        cfg = self.contract_cfg
        years = float(cfg["assumed_contract_years"])
        eligible_prefixes = cfg["eligible_cpv_prefixes"]

        if len(matches) >= int(cfg["min_notices"]):
            values = sorted(m["value"] for m in matches)
            low_q, high_q = cfg["trim_quantiles"]
            bounds = cfg["annual_value_bounds_eur"]
            raw_base = _quantile(values, 0.5) / years
            base = _clamp(raw_base, bounds["min"], bounds["max"])
            low = _clamp(_quantile(values, low_q) / years, bounds["min"], bounds["max"])
            high = _clamp(_quantile(values, high_q) / years, bounds["min"], bounds["max"])
            dates = [m["published_at"] for m in matches if m["published_at"]]
            return Factor(
                name="contract_value",
                label="Annual value of one engagement",
                value=base, unit="EUR per enterprise per year", basis=OBSERVED,
                low=low, high=high,
                source={
                    "publisher": "TED (Tenders Electronic Daily)",
                    "dataset": "ted",
                    "url": "https://ted.europa.eu",
                    "period": f"{min(dates)}..{max(dates)}" if dates else "",
                    "licence": "Open licence",
                },
                detail={
                    "notices": len(matches),
                    "match_level": matches[0]["match_level"],
                    "median_contract_value_eur": _quantile(values, 0.5),
                    "assumed_contract_years": years,
                    "trim_quantiles": [low_q, high_q],
                    "annual_value_bounds_eur": bounds,
                    "clamped": abs(raw_base - base) > 1,
                    "eligible_cpv_prefixes": list(eligible_prefixes),
                    "proxy_for_private_sector": topic["vertical"] not in ("public_sector", "defense"),
                    "examples": [
                        {"signal_id": m["signal_id"], "title": m["title"][:120],
                         "value_eur": m["value"], "published_at": m["published_at"], "url": m["url"]}
                        for m in sorted(matches, key=lambda m: -m["value"])[:5]
                    ],
                },
                note=(f"Median of {len(matches)} EU ICT tender notices whose CPV codes resolve to "
                      f"this topic's {matches[0]['match_level']}, divided by an assumed {years:g}-year "
                      f"contract to give an annual figure."
                      + (" Clamped to the configured per-enterprise annual bound."
                         if abs(raw_base - base) > 1 else "")),
            )

        domains = unjs(topic["domains"], []) or []
        bands = cfg["fallback_bands_eur"]
        band = next((bands[d] for d in domains if d in bands), cfg["fallback_default_eur"])
        return Factor(
            name="contract_value",
            label="Annual value of one engagement",
            value=float(band["base"]), unit="EUR per enterprise per year", basis=ASSUMPTION,
            low=float(band["low"]), high=float(band["high"]),
            source={"publisher": "config/sizing.yaml", "dataset": "fallback_bands_eur",
                    "period": self.cfg.sizing_version, "owner": self.sizing["owner"]},
            detail={"notices": len(matches), "domains": domains,
                    "min_notices_required": int(cfg["min_notices"])},
            note=(f"Only {len(matches)} matching tender notices, below the {cfg['min_notices']} "
                  f"needed for a robust median, so the configured band for this business domain "
                  f"is used. It is an assumption owned by {self.sizing['owner']}, not evidence."),
        )

    # ------------------------------------------------------------------
    # Method 2 — observed procurement
    # ------------------------------------------------------------------

    def _procurement_observed(self, topic: dict[str, Any], geographies: list[str],
                              coverage: dict[str, Any], right_to_win: float,
                              distance: int) -> Estimate | None:
        matches = self._matching_notices(topic)
        if len(matches) < MIN_NOTICES_FOR_OBSERVED:
            # Below a handful of contracts this is an anecdote, not a flow.
            return None
        cfg = self.contract_cfg
        years = float(cfg["assumed_contract_years"])
        dates = sorted(m["published_at"] for m in matches if m["published_at"])
        if not dates:
            return None

        # Annualise against the collection window of the WHOLE priced tender
        # corpus, not the matched subset. The subset's own span is a sampling
        # artefact — three notices that happen to fall on one day would
        # otherwise be scaled by 365 and produce a headline in the billions.
        # §4.12's rule applies: a silent cap or a silent extrapolation reads as
        # a measurement, so the window and the factor are both reported.
        span_days = max(MIN_WINDOW_DAYS, self._corpus_window_days())
        annualisation = 365.0 / span_days

        values = sorted(m["value"] for m in matches)
        low_q, high_q = cfg["trim_quantiles"]
        if len(values) >= 10:
            lower, upper = _quantile(values, low_q), _quantile(values, high_q)
            trimmed = [v for v in values if lower <= v <= upper]
        else:
            trimmed = values
        observed_annual = sum(trimmed) / years * annualisation
        full_annual = sum(values) / years * annualisation

        member_states = {g for g in geographies if g != self.scope["eu_aggregate"]}
        in_scope = [m for m in matches if not member_states or set(m["countries"]) & member_states]
        scope_values = sorted(m["value"] for m in in_scope)
        if len(values) >= 10:
            scope_values = [v for v in scope_values if lower <= v <= upper]
        # SAM is the same observation restricted to the topic's geographies, so
        # it can equal TAM (an EU-wide topic) but never exceed it.
        scope_annual = min(sum(scope_values) / years * annualisation, observed_annual)

        factors = [
            Factor(
                name="observed_procurement",
                label="Tendered contract value in matching CPV categories",
                value=observed_annual, unit="EUR per year", basis=OBSERVED,
                low=observed_annual, high=full_annual,
                source={
                    "publisher": "TED (Tenders Electronic Daily)",
                    "dataset": "ted",
                    "url": "https://ted.europa.eu",
                    "period": f"{dates[0]}..{dates[-1]}",
                    "licence": "Open licence",
                },
                detail={
                    "notices": len(matches),
                    "notices_in_scope": len(in_scope),
                    "match_level": matches[0]["match_level"],
                    "window_days": span_days,
                    "window_basis": "collection window of the priced tender corpus",
                    "annualisation_factor": round(annualisation, 2),
                    "assumed_contract_years": years,
                    "total_contract_value_eur": sum(values),
                    "examples": [
                        {"signal_id": m["signal_id"], "title": m["title"][:120],
                         "value_eur": m["value"], "buyer": m["buyer"],
                         "published_at": m["published_at"], "url": m["url"]}
                        for m in sorted(matches, key=lambda m: -m["value"])[:5]
                    ],
                },
                note=("Contracts that exist, not a modelled market. Public buyers only, so this is "
                      "a floor for the whole market and a direct measure for public-sector topics."),
            ),
        ]
        tam = {"low": observed_annual, "base": observed_annual, "high": full_annual}
        sam = {"low": scope_annual, "base": scope_annual,
               "high": min(scope_annual * (full_annual / observed_annual if observed_annual else 1),
                           full_annual)}
        som, share_factor = self._obtainable(sam, right_to_win, distance)
        factors.append(share_factor)

        caveats = [
            f"Observed over {span_days} days of TED coverage and scaled to a year "
            f"(x{annualisation:.1f}); a short collection window makes that scaling rough.",
            f"{len(matches)} matching notices, matched on {matches[0]['match_level']} via the CPV "
            f"crosswalk — §4.5.2's warning applies: a crosswalk error lands directly in this number.",
            "Public procurement only. Private-sector demand for the same capability is not "
            "visible here at all, so this is a floor rather than a market size.",
        ]
        if coverage.get("note"):
            caveats.append(coverage["note"])

        return Estimate(
            method=PROCUREMENT, tam=tam, sam=sam, som=som,
            confidence="observed", factors=factors, coverage=coverage, caveats=caveats,
        )

    # ------------------------------------------------------------------
    # Shared
    # ------------------------------------------------------------------

    def _obtainable(self, sam: dict[str, float], right_to_win: float,
                    distance: int) -> tuple[dict[str, float], Factor]:
        """SOM: the one deliberately modelled number, labelled as such.

        SC-12 forbids folding internal position into a published score, and this
        is not a score — but it is the same discipline: the share assumption is
        configuration with an owner, it is shown beside the number it produced,
        and it never feeds attractiveness or right to win.
        """
        cfg = self.sizing["obtainable_share"]
        band = next(
            (b for b in cfg["by_right_to_win"] if right_to_win >= b["min_score"]),
            cfg["by_right_to_win"][-1],
        )
        distance_factor = float(cfg["by_portfolio_distance"][f"L{distance}"])
        share = float(band["share"]) * distance_factor
        som = {key: (value or 0.0) * share for key, value in sam.items()}
        factor = Factor(
            name="obtainable_share",
            label="Assumed obtainable share of the serviceable market",
            value=share * 100, unit="% of SAM", basis=ASSUMPTION,
            source={"publisher": "config/sizing.yaml", "dataset": "obtainable_share",
                    "period": self.cfg.sizing_version, "owner": self.sizing["owner"]},
            detail={
                "right_to_win": right_to_win,
                "right_to_win_band": band["label"],
                "band_share": band["share"],
                "portfolio_distance": f"L{distance}",
                "distance_factor": distance_factor,
            },
            note=cfg["note"].strip(),
        )
        return som, factor

    def _latest(self, series_id: str, indicator: str, nace: str, geo: str,
                size_class: str) -> dict[str, Any] | None:
        row = self.db.query_one(
            """SELECT value, period FROM reference_observations
               WHERE series_id=? AND indicator=? AND nace=? AND geo=? AND size_class=?
               ORDER BY period DESC LIMIT 1""",
            (series_id, indicator, nace, geo, size_class),
        )
        return {"value": row["value"], "period": row["period"]} if row else None

    def _history(self, series_id: str, indicator: str, nace: str, geo: str,
                 size_class: str) -> list[dict[str, Any]]:
        rows = self.db.query(
            """SELECT value, period FROM reference_observations
               WHERE series_id=? AND indicator=? AND nace=? AND geo=? AND size_class=?
               ORDER BY period ASC""",
            (series_id, indicator, nace, geo, size_class),
        )
        return [{"value": r["value"], "period": r["period"]} for r in rows]

    # -- procurement matching ---------------------------------------------

    def _matching_notices(self, topic: dict[str, Any]) -> list[dict[str, Any]]:
        """Tender notices whose CPV codes resolve to this topic.

        Preference order is use case, then vertical: a use-case match is the
        more specific statement about what is being bought, and §4.5.2 warns
        that the crosswalk's errors propagate into exactly this number, so the
        match level travels with the result and is displayed.
        """
        index = self._build_procurement_index()
        use_case_matches = index["use_case"].get(topic["use_case"], [])
        if len(use_case_matches) >= int(self.contract_cfg["min_notices"]):
            return use_case_matches
        vertical_matches = index["vertical"].get(topic["vertical"], [])
        return vertical_matches if len(vertical_matches) > len(use_case_matches) else use_case_matches

    def _corpus_window_days(self) -> int:
        """Days spanned by the priced tender notices actually in the store."""
        row = self.db.query_one(
            "SELECT MIN(published_at) a, MAX(published_at) b FROM signals "
            "WHERE attributes LIKE '%total_value_eur%'"
        )
        if not row or not row["a"] or not row["b"]:
            return MIN_WINDOW_DAYS
        try:
            return max(1, (dt.date.fromisoformat(row["b"]) - dt.date.fromisoformat(row["a"])).days)
        except ValueError:
            return MIN_WINDOW_DAYS

    def _build_procurement_index(self) -> dict[str, dict[str, list[dict[str, Any]]]]:
        """One pass over the priced tender notices, bucketed by vertical and use case."""
        if self._procurement_index is not None:
            return self._procurement_index

        cfg = self.contract_cfg
        minimum, maximum = float(cfg["min_value_eur"]), float(cfg["max_value_eur"])
        eligible = tuple(cfg["eligible_cpv_prefixes"])  # matched against the main object
        index: dict[str, dict[str, list[dict[str, Any]]]] = {"vertical": {}, "use_case": {}}
        rows = self.db.query(
            "SELECT id, title, url, published_at, attributes FROM signals "
            "WHERE attributes LIKE '%total_value_eur%'"
        )
        for row in rows:
            attributes = unjs(row["attributes"], {}) or {}
            value = attributes.get("total_value_eur")
            if not isinstance(value, (int, float)) or not (minimum <= float(value) <= maximum):
                continue
            cpv = [str(c) for c in attributes.get("cpv") or []]
            # Eligibility is tested on the MAIN OBJECT — the first CPV code,
            # which the TED connector preserves in that position deliberately.
            # Testing "any code" is not enough: a hydroelectric turbine retrofit
            # carries an IT code for its SCADA lot, and its whole contract value
            # would then price a zero-trust deployment. The crosswalk still
            # reads every code, because a notice can be ABOUT a use case through
            # any of its lots; only its VALUE has to come from an IT contract.
            if not cpv or not cpv[0].startswith(eligible):
                continue
            entry = {
                "signal_id": row["id"],
                "title": row["title"],
                "url": row["url"],
                "published_at": row["published_at"],
                "value": float(value),
                "buyer": attributes.get("buyer_name") or "",
                "countries": [str(c) for c in attributes.get("buyer_country") or []],
            }
            for vertical in self.cfg.cpv_to_vertical.resolve(cpv):
                index["vertical"].setdefault(vertical, []).append(entry | {"match_level": "vertical"})
            for use_case in self.cfg.cpv_to_use_case.resolve(cpv):
                index["use_case"].setdefault(use_case, []).append(entry | {"match_level": "use case"})

        self._procurement_index = index
        return index

    # -- persistence -------------------------------------------------------

    def _store(self, topic_id: str, estimates: Iterable[Estimate]) -> None:
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        with self.db.cursor() as cur:
            for estimate in estimates:
                # One current row per (topic, method): the history that matters
                # for sizes is the reference data's own vintage, which each row
                # already carries per factor.
                cur.execute(
                    "DELETE FROM market_sizes WHERE opportunity_id = ? AND method = ?",
                    (topic_id, estimate.method),
                )
                cur.execute(
                    """INSERT INTO market_sizes
                        (opportunity_id, computed_at, method, currency,
                         tam_low, tam_base, tam_high, sam_low, sam_base, sam_high,
                         som_low, som_base, som_high, confidence, factors, coverage, caveats,
                         sizing_version, pipeline_version)
                       VALUES (?,?,?,'EUR',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (topic_id, now, estimate.method,
                     estimate.tam["low"], estimate.tam["base"], estimate.tam["high"],
                     estimate.sam["low"], estimate.sam["base"], estimate.sam["high"],
                     estimate.som["low"], estimate.som["base"], estimate.som["high"],
                     estimate.confidence,
                     js([asdict(f) for f in estimate.factors]),
                     js(estimate.coverage), js(estimate.caveats),
                     self.cfg.sizing_version, self.cfg.pipeline_version),
                )


def sizes_for_topic(db: Database, topic_id: str) -> list[dict[str, Any]]:
    """Stored sizes, shaped for the read model and the API."""
    rows = db.query(
        "SELECT * FROM market_sizes WHERE opportunity_id = ? ORDER BY method", (topic_id,)
    )
    out = []
    for row in rows:
        out.append({
            "method": row["method"],
            "method_label": ("Bottom-up: enterprises x adoption x contract value"
                             if row["method"] == BOTTOM_UP
                             else "Observed: tendered contract value, annualised"),
            "currency": row["currency"],
            "tam": {"low": row["tam_low"], "base": row["tam_base"], "high": row["tam_high"]},
            "sam": {"low": row["sam_low"], "base": row["sam_base"], "high": row["sam_high"]},
            "som": {"low": row["som_low"], "base": row["som_base"], "high": row["som_high"]},
            "confidence": row["confidence"],
            "factors": unjs(row["factors"], []),
            "coverage": unjs(row["coverage"], {}),
            "caveats": unjs(row["caveats"], []),
            "sizing_version": row["sizing_version"],
            "computed_at": row["computed_at"],
        })
    return out


def format_eur(value: float | None) -> str:
    """One formatter, so the API, the CLI and the PDF never disagree."""
    if value is None:
        return "—"
    value = float(value)
    for limit, suffix, divisor in ((1e9, "bn", 1e9), (1e6, "m", 1e6)):
        if abs(value) >= limit:
            scaled = value / divisor
            return f"€{scaled:.1f}{suffix}" if abs(scaled) < 100 else f"€{scaled:.0f}{suffix}"
    if abs(value) >= 1e3:
        # No decimals at thousand scale: a hundred euro of precision on a
        # figure built from a median tender value is noise pretending to be
        # information.
        return f"€{value / 1e3:.0f}k"
    return f"€{value:,.0f}"
