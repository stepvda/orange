"""Curation, hallucination control and leakage control (§4.4, §4.5, FR-35)."""

from __future__ import annotations

import datetime as dt

import pytest

from radar.config import get_config
from radar.db import Database
from radar.graph import LINK_DISTANCE, Linker, build_graph
from radar.llm import LLMClient
from radar.pipeline.synthesis import Candidate, SynthesisStats, Synthesiser

REF = dt.date(2026, 8, 17)


@pytest.fixture(scope="module")
def cfg():
    return get_config()


@pytest.fixture()
def db(tmp_path):
    database = Database(tmp_path / "t.db")
    database.init_schema()
    return database


@pytest.fixture()
def synth(cfg, db):
    return Synthesiser(cfg, db, LLMClient(provider="mock"))


def make(**overrides) -> Candidate:
    base = dict(
        vertical="manufacturing",
        use_case="predictive_maintenance",
        technology="machine_learning",
        statement="Predictive maintenance for rotating equipment in chemical process plants using vibration ML.",
        why_hot=[{"claim": "Three deployments were published this quarter.", "signals": ["SIG-1"]}],
    )
    base.update(overrides)
    return Candidate(**base)


# ---------------------------------------------------------------------------
# §4.4.4 defence 2 — closed-vocabulary output
# ---------------------------------------------------------------------------

def test_invented_taxonomy_values_are_rejected(synth):
    stats = SynthesisStats()
    candidate = make(technology="quantum_blockchain_mesh")
    assert synth._validate(candidate, {"SIG-1"}, stats) is False
    assert stats.failed_vocabulary == 1


def test_a_synonym_is_repaired_rather_than_dropped(synth):
    """§4.4.2: anything outside the enumeration fails validation and is retried
    once. A recognised synonym is exactly that retry."""
    stats = SynthesisStats()
    candidate = make(technology="private cellular")
    assert synth._validate(candidate, {"SIG-1"}, stats) is True
    assert candidate.technology == "private_5g"


# ---------------------------------------------------------------------------
# §4.4.4 defence 1 — evidence binding
# ---------------------------------------------------------------------------

def test_uncited_claims_are_stripped_not_rewritten(synth):
    stats = SynthesisStats()
    candidate = make(why_hot=[
        {"claim": "Cited and therefore kept.", "signals": ["SIG-1"]},
        {"claim": "Asserted with no evidence at all.", "signals": []},
    ])
    assert synth._validate(candidate, {"SIG-1"}, stats) is True
    assert [c["claim"] for c in candidate.why_hot] == ["Cited and therefore kept."]


def test_claims_citing_signals_outside_the_cluster_are_stripped(synth):
    """The validator checks that the cited signal is in the cluster that
    produced the candidate, not merely that the id looks plausible (§4.4.4)."""
    stats = SynthesisStats()
    candidate = make(why_hot=[{"claim": "Cites a signal from another cluster.", "signals": ["SIG-999"]}])
    assert synth._validate(candidate, {"SIG-1"}, stats) is False
    assert stats.failed_evidence == 1


def test_a_candidate_with_no_surviving_claim_is_dropped(synth):
    stats = SynthesisStats()
    candidate = make(why_hot=[])
    assert synth._validate(candidate, {"SIG-1"}, stats) is False


# ---------------------------------------------------------------------------
# §4.1 principle 4 / FR-06 — specificity is a measurable property
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("statement", ["AI", "Cloud", "Cybersecurity", "Digital transformation"])
def test_generic_statements_fail_specificity(synth, statement):
    """The briefing rejects these by name (§3.4, §4.4.2)."""
    stats = SynthesisStats()
    assert synth._validate(make(statement=statement), {"SIG-1"}, stats) is False
    assert stats.failed_specificity == 1


def test_a_paragraph_is_not_an_opportunity_statement(synth):
    stats = SynthesisStats()
    assert synth._validate(make(statement="x " * 300), {"SIG-1"}, stats) is False


def test_a_specific_statement_passes(synth):
    stats = SynthesisStats()
    assert synth._validate(make(), {"SIG-1"}, stats) is True
    assert stats.failed_specificity == 0


# ---------------------------------------------------------------------------
# §4.4.5 — canonical identity is the triple
# ---------------------------------------------------------------------------

def test_same_triple_merges_and_unions_the_evidence(synth):
    stats = SynthesisStats()
    a = make(why_hot=[{"claim": "First claim.", "signals": ["SIG-1"]}])
    b = make(why_hot=[{"claim": "Second claim.", "signals": ["SIG-2"]}])
    merged = synth._deduplicate([a, b], stats)
    assert len(merged) == 1
    assert stats.merged_duplicates == 1
    assert {c["claim"] for c in merged[0].why_hot} == {"First claim.", "Second claim."}


def test_different_triples_are_distinct_topics(synth):
    stats = SynthesisStats()
    a = make()
    b = make(vertical="energy", statement="Predictive maintenance for grid transformers using vibration ML models.")
    assert len(synth._deduplicate([a, b], stats)) == 2


# ---------------------------------------------------------------------------
# FR-30 / LK-05 — link typing and portfolio distance
# ---------------------------------------------------------------------------

def test_offer_covering_use_case_and_technology_is_l0(cfg, db):
    build_graph(cfg, db)
    linker = Linker(cfg, db)
    # Live Objects addresses asset_tracking and provides iot_platform.
    links = linker.link_topic({
        "vertical": "manufacturing", "use_case": "asset_tracking",
        "technology": "iot_platform", "domains": '["ox_smart_industries"]',
    })
    direct = [l for l in links if l.node_id == "offer:live_objects"]
    assert direct and direct[0].link_type == "L0"
    assert linker.portfolio_distance(links) == LINK_DISTANCE["L0"]


def test_no_portfolio_path_yields_white_space(cfg, db):
    build_graph(cfg, db)
    linker = Linker(cfg, db)
    links = linker.link_topic({
        "vertical": "media_entertainment", "use_case": "workforce_training_xr",
        "technology": "ar_vr_xr", "domains": '["ex_employee_experience"]',
    })
    assert linker.portfolio_distance(links) >= LINK_DISTANCE["L3"]


def test_every_link_records_the_rule_that_justified_it(cfg, db):
    """DR-13 / §4.5.4: a link nobody can explain is worse than no link."""
    build_graph(cfg, db)
    linker = Linker(cfg, db)
    links = linker.link_topic({
        "vertical": "manufacturing", "use_case": "asset_tracking",
        "technology": "iot_platform", "domains": '["ox_smart_industries"]',
    })
    assert links
    for link in links:
        assert link.evidence.get("rule"), f"{link.node_id} has no stated rule"


def test_graph_nodes_carry_their_source_and_date(cfg, db):
    """NFR-02: the graph is auditable to the same standard as the signals."""
    build_graph(cfg, db)
    for row in db.query("SELECT id, source, as_of FROM graph_nodes LIMIT 60"):
        assert row["source"], f"{row['id']} has no source"
        assert row["as_of"], f"{row['id']} has no as_of date"


# ---------------------------------------------------------------------------
# FR-35 / §4.7.3 — leakage control
# ---------------------------------------------------------------------------

def test_connectors_reject_items_published_after_the_reference_date(cfg):
    """§4.7.3: features must be computable from data whose PUBLICATION date
    precedes the reference date. Leakage here is invisible unless the pipeline
    is designed to prevent it from the start."""
    from radar.connectors import HttpSession
    from radar.connectors.news import RssSearchConnector

    connector = RssSearchConnector({"id": "x", "params": {}}, HttpSession("test"))
    future = REF + dt.timedelta(days=5)
    past = REF - dt.timedelta(days=5)
    ancient = REF - dt.timedelta(days=500)

    assert connector.in_window(future, REF, 30) is False, "future item leaked into a replay"
    assert connector.in_window(past, REF, 30) is True
    assert connector.in_window(ancient, REF, 30) is False
    assert connector.in_window(None, REF, 30) is False, "undated evidence must be rejected (DR-04)"


def test_extracts_are_truncated_so_no_source_is_mirrored(cfg):
    """DR-08 / NFR-07: storage is by reference plus a SHORT extract."""
    from radar.connectors import HttpSession
    from radar.connectors.news import RssSearchConnector

    connector = RssSearchConnector({"id": "x", "params": {}}, HttpSession("test"), max_extract_chars=200)
    clipped = connector.clip("word " * 500)
    assert len(clipped) <= 210


# ---------------------------------------------------------------------------
# DR-03 — stable identifiers across refreshes
# ---------------------------------------------------------------------------

def test_space_ids_keep_counting_past_the_thousandth(db):
    """`OS999` sorts above `OS1000` as TEXT, and `id` is a TEXT primary key.

    Minting the next id from `ORDER BY id DESC` therefore stopped advancing at
    the thousandth space: it read 'OS999' back for ever, handed out 'OS1000'
    twice, and the second INSERT failed the primary-key constraint — which, in
    `_persist`, rolls back every candidate in the batch rather than one.
    """
    conn = db.connect()
    try:
        cur = conn.cursor()
        assert Synthesiser._next_id(cur) == "OS001", "an empty radar starts at OS001"
        for n in range(1, 1000):
            cur.execute(
                "INSERT INTO opportunity_spaces (id, vertical, use_case, technology, statement, "
                "state, first_seen, last_refresh, pipeline_version) "
                "VALUES (?,?,?,?,?,'candidate','2026-01-01','2026-01-01','t')",
                (f"OS{n:03d}", "manufacturing", f"uc{n}", f"tech{n}", "s"),
            )
        minted = Synthesiser._next_id(cur)
        assert minted == "OS1000"
        cur.execute(
            "INSERT INTO opportunity_spaces (id, vertical, use_case, technology, statement, "
            "state, first_seen, last_refresh, pipeline_version) "
            "VALUES (?,?,?,?,?,'candidate','2026-01-01','2026-01-01','t')",
            (minted, "manufacturing", "uc1000", "tech1000", "s"),
        )
        assert Synthesiser._next_id(cur) == "OS1001", "the next id must not collide with OS1000"
    finally:
        conn.close()


def test_a_hand_written_id_does_not_derail_the_sequence(db):
    """`CAST(SUBSTR(id, 3) AS INTEGER)` reads 'OS-manual' as 0, so the GLOB that
    keeps it out of the max is load-bearing rather than decoration."""
    conn = db.connect()
    try:
        cur = conn.cursor()
        for space_id in ("OS007", "OS-manual"):
            cur.execute(
                "INSERT INTO opportunity_spaces (id, vertical, use_case, technology, statement, "
                "state, first_seen, last_refresh, pipeline_version) "
                "VALUES (?,?,?,?,?,'candidate','2026-01-01','2026-01-01','t')",
                (space_id, "manufacturing", f"uc-{space_id}", f"tech-{space_id}", "s"),
            )
        assert Synthesiser._next_id(cur) == "OS008"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# LK-07 — asset withdrawal
# ---------------------------------------------------------------------------

def test_a_withdrawn_asset_is_retired_once_however_often_the_graph_is_rebuilt(cfg, db):
    """`node_type || '_retired'` is not idempotent.

    An asset that stays out of the config was re-suffixed on every rebuild —
    'offer_retired_retired_retired' — which nothing downstream matches on, and
    it was re-counted as a fresh withdrawal each time, so the build stats
    reported the same removal for ever.
    """
    build_graph(cfg, db)
    with db.cursor() as cur:
        cur.execute("INSERT INTO graph_nodes (id, node_type, label, attributes, source, as_of) "
                    "VALUES ('offer:withdrawn','offer','Withdrawn','{}','test','2026-01-01')")

    first = build_graph(cfg, db)
    assert first["retired_nodes"] == 1
    assert db.query_one("SELECT node_type FROM graph_nodes WHERE id='offer:withdrawn'"
                        )["node_type"] == "offer_retired"

    for _ in range(3):
        again = build_graph(cfg, db)
        assert again["retired_nodes"] == 0, "an already-retired node is not a new withdrawal"
    assert db.query_one("SELECT node_type FROM graph_nodes WHERE id='offer:withdrawn'"
                        )["node_type"] == "offer_retired", "the suffix must not accumulate"
