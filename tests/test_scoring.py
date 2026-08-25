"""Scoring invariants (§4.6, §4.8, SC-01..SC-19)."""

from __future__ import annotations

import datetime as dt

import pytest

from radar.config import get_config
from radar.db import Database
from radar.scoring import AttractivenessScorer, RightToWinScorer, derive_horizon, next_state

REF = dt.date(2026, 8, 17)


@pytest.fixture(scope="module")
def cfg():
    return get_config()


@pytest.fixture()
def db(tmp_path):
    database = Database(tmp_path / "test.db")
    database.init_schema()
    return database


@pytest.fixture()
def scorer(cfg, db):
    # llm=None: the deterministic components are the ones under test here.
    # Table 23 assigns counting, diversity, recency and momentum to arithmetic
    # precisely so they are testable without a model in the loop.
    return AttractivenessScorer(cfg, db, llm=None)


def signal(sid: str, *, tier: int = 2, publisher: str = "reuters.com",
           days_ago: int = 10, title: str = "t", stype: str = "trend", **extra):
    return {
        "id": sid, "tier": tier, "publisher": publisher, "title": title,
        "published_at": (REF - dt.timedelta(days=days_ago)).isoformat(),
        "signal_type": stype, "attributes": "{}", **extra,
    }


# ---------------------------------------------------------------------------
# SC-11 reproducibility
# ---------------------------------------------------------------------------

def test_scores_are_reproducible(scorer):
    """SC-11: identical inputs and identical configuration yield identical output."""
    signals = [signal(f"SIG-{i}", publisher=f"pub{i}.com", days_ago=i * 3) for i in range(8)]
    topic = {"id": "OS001", "vertical": "manufacturing", "use_case": "predictive_maintenance",
             "technology": "machine_learning", "statement": "s", "first_seen": "2026-06-01", "domains": "[]"}
    first = scorer.score(topic, signals, REF, 10)
    second = scorer.score(topic, signals, REF, 10)
    assert first == second


# ---------------------------------------------------------------------------
# SC-03 source diversity
# ---------------------------------------------------------------------------

def test_syndicated_duplicates_collapse_to_one_source(scorer):
    """§4.3.7: twenty outlets syndicating one press release is one source, not twenty."""
    syndicated = [
        signal(f"SIG-{i}", publisher="wire.com", title="Identical vendor announcement")
        for i in range(20)
    ]
    result = scorer.source_diversity(syndicated)
    assert result.value == 0.0
    assert result.inputs["distinct_publishers"] == 1
    assert result.inputs["syndicated_collapsed"] == 19


def test_diversity_rewards_independent_publishers(scorer):
    few = [signal(f"SIG-{i}", publisher=f"pub{i}.com") for i in range(2)]
    many = [signal(f"SIG-{i}", publisher=f"pub{i}.com") for i in range(8)]
    assert scorer.source_diversity(many).value > scorer.source_diversity(few).value


def test_effective_publishers_never_exceeds_the_publisher_count(scorer):
    """Breadth counts PUBLISHERS, not summed per-signal weights.

    Summing the weights yields the weighted signal count, so a topic with twelve
    publishers across thirty articles reported an "effective publisher count" of
    seventeen — larger than the count it claimed to discount, and saturating
    breadth on volume alone.
    """
    signals = []
    for p in range(12):
        for a in range(3):                       # three articles per publisher
            signals.append(signal(f"SIG-{p}-{a}", publisher=f"pub{p}.com", title=f"story {p}-{a}"))
    result = scorer.source_diversity(signals)
    assert result.inputs["distinct_publishers"] == 12
    assert result.inputs["effective_publishers"] <= 12
    assert result.inputs["breadth_factor"] <= 1.0


def test_a_tier4_only_publisher_counts_as_a_fraction_of_a_publisher(scorer, cfg):
    credible = [signal(f"SIG-{i}", publisher=f"pub{i}.com", tier=2) for i in range(4)]
    vendor = [signal(f"SIG-{i}", publisher=f"pub{i}.com", tier=4) for i in range(4)]
    discount = float(cfg.source_tiers["diversity_tier4_discount"])
    assert scorer.source_diversity(credible).inputs["effective_publishers"] == pytest.approx(4.0)
    assert scorer.source_diversity(vendor).inputs["effective_publishers"] == pytest.approx(4 * discount)


def test_tier4_publishers_are_discounted_in_diversity(scorer, cfg):
    credible = [signal(f"SIG-{i}", publisher=f"pub{i}.com", tier=2) for i in range(6)]
    vendor = [signal(f"SIG-{i}", publisher=f"pub{i}.com", tier=4) for i in range(6)]
    assert scorer.source_diversity(credible).value > scorer.source_diversity(vendor).value


# ---------------------------------------------------------------------------
# SC-04 / SC-09 evidence quality
# ---------------------------------------------------------------------------

def test_vendor_only_evidence_scores_low(scorer):
    """SC-09: a vendor-specific signal must score low.

    §4.3.7 rule 2: no topic should reach high attractiveness on tier-4 evidence
    alone.
    """
    vendor_only = [signal(f"SIG-{i}", tier=4, publisher=f"vendor{i}.com") for i in range(6)]
    authoritative = [signal(f"SIG-{i}", tier=1, publisher=f"reg{i}.europa.eu") for i in range(6)]
    vendor_result = scorer.evidence_quality(vendor_only)
    assert vendor_result.value < 20
    assert vendor_result.inputs["no_tier1_or_tier2_penalty_applied"] is True
    assert scorer.evidence_quality(authoritative).value > 90


def test_one_credible_source_removes_the_floor_penalty(scorer):
    mixed = [signal("SIG-1", tier=1, publisher="eur-lex.europa.eu")] + [
        signal(f"SIG-{i}", tier=4, publisher=f"v{i}.com") for i in range(2, 5)
    ]
    assert scorer.evidence_quality(mixed).inputs["no_tier1_or_tier2_penalty_applied"] is False


# ---------------------------------------------------------------------------
# Market signal strength and momentum
# ---------------------------------------------------------------------------

def test_signal_volume_is_log_compressed(scorer):
    """Table 27: log compression prevents one noisy topic saturating the scale."""
    small = scorer.market_signal_strength([signal(f"SIG-{i}") for i in range(4)], 64)
    large = scorer.market_signal_strength([signal(f"SIG-{i}") for i in range(64)], 64)
    assert large.value == pytest.approx(100.0)
    # Sixteen times the volume is nowhere near sixteen times the score.
    assert small.value > large.value / 4


def test_rising_signal_volume_beats_falling(scorer):
    rising = [signal(f"SIG-{i}", days_ago=d) for i, d in enumerate([2, 4, 6, 8, 20, 40, 70])]
    falling = [signal(f"SIG-{i}", days_ago=d) for i, d in enumerate([80, 75, 70, 65, 60, 12, 88])]
    first_seen = dt.date(2026, 1, 1)
    assert (scorer.novelty_momentum(rising, REF, first_seen).value
            > scorer.novelty_momentum(falling, REF, first_seen).value)


# ---------------------------------------------------------------------------
# DR-05 decomposition
# ---------------------------------------------------------------------------

def test_every_component_records_its_inputs(scorer):
    """DR-05 / NFR-01: any number must be reproducible from what is stored."""
    signals = [signal(f"SIG-{i}", publisher=f"p{i}.com") for i in range(5)]
    topic = {"id": "OS001", "vertical": "manufacturing", "use_case": "predictive_maintenance",
             "technology": "machine_learning", "statement": "s", "first_seen": "2026-06-01", "domains": "[]"}
    _, components, inputs = scorer.score(topic, signals, REF, 10)
    assert set(components) == set(inputs)
    for name, payload in inputs.items():
        assert isinstance(payload, dict) and payload, f"{name} recorded no inputs"


# ---------------------------------------------------------------------------
# FR-08 horizon derivation (§4.8)
# ---------------------------------------------------------------------------

def test_procurement_within_twelve_months_is_now(cfg):
    signals = [signal("SIG-1", stype="buying_signal", days_ago=30)]
    horizon = derive_horizon(cfg, {"statement": "s"}, signals, REF)
    assert horizon["value"] == "now"
    assert horizon["basis"] == "budgeted_procurement_within_12_months"
    assert horizon["evidence"] == ["SIG-1"]


def test_regulation_without_procurement_is_next(cfg):
    signals = [signal("SIG-1", stype="regulation", days_ago=40)]
    horizon = derive_horizon(cfg, {"statement": "s"}, signals, REF)
    assert horizon["value"] == "next"


def test_research_only_is_later(cfg):
    signals = [signal("SIG-1", stype="technology_maturity", days_ago=40)]
    horizon = derive_horizon(cfg, {"statement": "s"}, signals, REF)
    assert horizon["value"] == "later"


def test_the_now_window_is_configuration_rather_than_a_constant(cfg, monkeypatch):
    """NFR-11: thresholds are configuration, not code.

    `settings.horizon.now_max_months` was read into a local and then ignored —
    the Now test compared against a hard-coded 365 days — so moving the knob
    changed nothing and the config, the docstring and the behaviour were free to
    disagree without anybody noticing.
    """
    just_over_a_year = [signal("SIG-1", stype="buying_signal", days_ago=400)]

    at_twelve = derive_horizon(cfg, {"statement": "s"}, just_over_a_year, REF)
    assert at_twelve["value"] == "later", "400 days is outside a twelve-month window"

    monkeypatch.setitem(cfg.settings["horizon"], "now_max_months", 18)
    at_eighteen = derive_horizon(cfg, {"statement": "s"}, just_over_a_year, REF)
    assert at_eighteen["value"] == "now"
    assert at_eighteen["basis"] == "budgeted_procurement_within_18_months"
    assert "18 months" in at_eighteen["test_applied"], "the stated test must quote the real window"


def test_the_now_window_counts_calendar_months(cfg):
    """Twelve months is a year on the calendar, not `12 * 30` days."""
    from radar.scoring import _months_before

    assert _months_before(dt.date(2026, 8, 17), 12) == dt.date(2025, 8, 17)
    # A day the target month does not have is clamped rather than overflowing.
    assert _months_before(dt.date(2026, 3, 31), 1) == dt.date(2026, 2, 28)
    assert _months_before(dt.date(2026, 1, 15), 13) == dt.date(2024, 12, 15)


def test_horizon_always_states_which_test_it_applied(cfg):
    """§4.8: where derivation is impossible the model may classify, but must say
    which test it applied."""
    for signals in ([], [signal("SIG-1", stype="buying_signal")], [signal("SIG-2", stype="regulation")]):
        horizon = derive_horizon(cfg, {"statement": "s"}, signals, REF)
        assert horizon["test_applied"]
        assert horizon["basis"]


# ---------------------------------------------------------------------------
# FR-09 lifecycle (Table 32)
# ---------------------------------------------------------------------------

def test_a_topic_created_today_is_never_dormant(cfg):
    """Dormancy means "no qualifying signal for n periods", which presupposes the
    topic has existed for n periods."""
    topic = {"state": "candidate", "first_seen": REF.isoformat()}
    state, reason = next_state(cfg, topic, [], {"evidence_quality": 0}, REF, all_signals=[])
    assert state != "dormant", reason


def test_strong_evidence_promotes_to_active(cfg):
    signals = [signal(f"SIG-{i}", publisher=f"pub{i}.com", tier=1, days_ago=3) for i in range(5)]
    topic = {"state": "candidate", "first_seen": "2026-07-01"}
    state, _ = next_state(cfg, topic, signals, {"evidence_quality": 90}, REF, all_signals=signals)
    assert state == "active"


def test_thin_evidence_lands_on_the_watchlist(cfg):
    signals = [signal("SIG-1", publisher="a.com", tier=2, days_ago=3)]
    topic = {"state": "candidate", "first_seen": "2026-08-10"}
    state, _ = next_state(cfg, topic, signals, {"evidence_quality": 60}, REF, all_signals=signals)
    assert state == "watchlist"


def test_tier4_only_evidence_cannot_be_promoted(cfg):
    """lifecycle.promote_to_active.require_non_tier4_evidence."""
    signals = [signal(f"SIG-{i}", publisher=f"vendor{i}.com", tier=4, days_ago=2) for i in range(8)]
    topic = {"state": "candidate", "first_seen": "2026-07-01"}
    state, _ = next_state(cfg, topic, signals, {"evidence_quality": 90}, REF, all_signals=signals)
    assert state != "active"


def test_a_long_silent_topic_goes_dormant(cfg):
    old = [signal("SIG-1", days_ago=200)]
    topic = {"state": "active", "first_seen": "2025-01-01"}
    state, _ = next_state(cfg, topic, [], {"evidence_quality": 80}, REF, all_signals=old)
    assert state == "dormant"


# ---------------------------------------------------------------------------
# SC-13 evidence gap
# ---------------------------------------------------------------------------

def test_thin_vertical_raises_an_evidence_gap_warning(cfg, db):
    """§2.7: a radar that ignores the reference asymmetry will hand a
    salesperson a banking topic with no proof point behind it."""
    rtw = RightToWinScorer(cfg, db)
    defense_topic = {"vertical": "defense", "use_case": "drone_airspace_protection",
                     "technology": "drones_uav"}
    _, _, inputs = rtw.score(defense_topic, [])
    assert inputs["reference_density"]["evidence_gap_warning"] is True

    manufacturing = {"vertical": "manufacturing", "use_case": "predictive_maintenance",
                     "technology": "machine_learning"}
    _, _, inputs = rtw.score(manufacturing, [])
    assert inputs["reference_density"]["evidence_gap_warning"] is False


def test_right_to_win_components_name_their_source(cfg, db):
    """SC-15: right-to-win components are named query results, not assertions."""
    rtw = RightToWinScorer(cfg, db)
    _, _, inputs = rtw.score(
        {"vertical": "manufacturing", "use_case": "predictive_maintenance", "technology": "machine_learning"},
        [],
    )
    for key in ("offer_match", "reference_density", "partner_coverage", "compliance_fit",
                "capability_depth", "external_validation", "technology_ownership"):
        assert inputs[key].get("source"), f"{key} does not state where its number came from"
