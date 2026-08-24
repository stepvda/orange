"""Planner invariants.

The Planner turns a market size into a number somebody will put in front of an
executive committee, so the tests here are about the ways that number could be
wrong in a way nobody notices:

  * a plan that spends capacity it does not have;
  * a plan that is really one vertical wearing a portfolio's clothes;
  * a projection that sums obtainable share as though topics did not compete
    for the same budget;
  * a narrative that quietly introduces a figure the projection does not
    contain, which a reader then has to adjudicate against the table beside it;
  * a plan whose implied growth is not credible against Orange's own filed
    revenue, returned with a straight face.
"""

from __future__ import annotations

import datetime as dt

import pytest

from radar.config import get_config
from radar.db import Database, js
from radar.planner import DISTANCE_LABELS, PlanInputs, Planner


@pytest.fixture(scope="module")
def cfg():
    return get_config()


@pytest.fixture()
def db(tmp_path):
    database = Database(tmp_path / "test.db")
    database.init_schema()
    return database


class _FakeLLM:
    strong_model = "test-model"

    def __init__(self, payload):
        self.payload = payload

    def complete_json(self, system, user, **kwargs):
        return self.payload


def seed(db, cfg, *, n=6, vertical="manufacturing", som=50e6, horizon="now",
         confidence="observed", distance=0, pool_tech="private_5g", headcount=5000):
    """A small corpus with a real capability pool behind it."""
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    with db.cursor() as cur:
        cur.execute("""INSERT OR IGNORE INTO graph_nodes
                       (id, node_type, label, attributes, source, as_of)
                       VALUES (?,?,?,?,?,?)""",
                    ("capability_pool:test", "capability_pool", "Test experts",
                     js({"headcount": headcount, "technologies": [pool_tech],
                         "verticals": [], "domains": []}), "test", now))
        for i in range(n):
            tid = f"OS{i:03d}"
            cur.execute("""INSERT INTO opportunity_spaces
                (id, version, vertical, use_case, technology, statement, domains, personas,
                 geographies, state, horizon, first_seen, last_refresh, pipeline_version)
                VALUES (?,1,?,?,?,?,'[]','[]','[]','active',?,?,?,'0.1.0')""",
                (tid, vertical, f"use_case_{i}", pool_tech,
                 f"A statement long enough to look like a real opportunity space, number {i}.",
                 horizon, now, now))
            cur.execute("""INSERT INTO market_sizes
                (opportunity_id, computed_at, method, currency, som_low, som_base, som_high,
                 confidence, factors, coverage, caveats, sizing_version, pipeline_version)
                VALUES (?,?, 'bottom_up_adoption','EUR',?,?,?,?, '[]','{}','[]','v1','0.1.0')""",
                (tid, now, som * 0.3, som, som * 3, confidence))
            cur.execute("""INSERT INTO opportunity_links
                (opportunity_id, node_id, link_type, confidence, evidence, created_at)
                VALUES (?,?,?,?,'{}',?)""",
                (tid, "capability_pool:test", DISTANCE_LABELS[distance], 0.8, now))


# --------------------------------------------------------------- capacity

def test_entry_slots_cap_how_many_spaces_start_each_year(cfg, db):
    seed(db, cfg, n=20)
    plan = Planner(cfg, db).plan(PlanInputs(entry_slots_per_year=2, plan_years=5))
    by_year: dict[int, int] = {}
    for s in plan["selections"]:
        by_year[s["entry_year"]] = by_year.get(s["entry_year"], 0) + 1
    assert by_year, "the plan selected nothing"
    assert max(by_year.values()) <= 2


def test_a_plan_cannot_spend_capability_capacity_it_does_not_have(cfg, db):
    """The constraint that stops a plan being a wish list.

    1,000 people at 15% availability is 150 person-years a year. An L3 entry
    costs 40, so at most a handful can start together whatever the market says.
    """
    seed(db, cfg, n=20, distance=3, headcount=1000)
    plan = Planner(cfg, db).plan(
        PlanInputs(max_portfolio_distance=3, pool_availability=0.15, entry_slots_per_year=99))
    pools = plan["capacity_usage"]["pools"]
    for name, data in pools.items():
        assert max(data["used_by_year"]) <= data["capacity"] + 1e-6, name


def test_more_available_headcount_admits_more_spaces(cfg, db):
    seed(db, cfg, n=20, distance=2, headcount=1000)
    lean = Planner(cfg, db).plan(
        PlanInputs(label="lean", pool_availability=0.05, max_portfolio_distance=2))
    rich = Planner(cfg, db).plan(
        PlanInputs(label="rich", pool_availability=0.60, max_portfolio_distance=2))
    assert rich["selected_count"] > lean["selected_count"]


# ---------------------------------------------------------- concentration

def test_concentration_cap_prevents_a_single_vertical_plan(cfg, db):
    """Ranking by size alone puts 18 of the top 20 spaces in manufacturing.
    Without an explicit cap the optimiser returns that and calls it a portfolio."""
    seed(db, cfg, n=10, vertical="manufacturing", headcount=200000)
    seed_other(db, n=10, vertical="energy")
    plan = Planner(cfg, db).plan(
        PlanInputs(max_share_per_vertical=0.6, entry_slots_per_year=99, pool_availability=1.0))
    mix = {m["key"]: m["share"] for m in plan["projection"]["mix"]["vertical"]}
    assert max(mix.values()) <= 0.6 + 1e-6, mix


def seed_other(db, *, n, vertical):
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    with db.cursor() as cur:
        for i in range(n):
            tid = f"OX{i:03d}"
            cur.execute("""INSERT INTO opportunity_spaces
                (id, version, vertical, use_case, technology, statement, domains, personas,
                 geographies, state, horizon, first_seen, last_refresh, pipeline_version)
                VALUES (?,1,?,?,?,?,'[]','[]','[]','active','now',?,?,'0.1.0')""",
                (tid, vertical, f"other_use_case_{i}", "private_5g",
                 f"Another statement long enough to pass as a real space, number {i}.", now, now))
            cur.execute("""INSERT INTO market_sizes
                (opportunity_id, computed_at, method, currency, som_low, som_base, som_high,
                 confidence, factors, coverage, caveats, sizing_version, pipeline_version)
                VALUES (?,?, 'bottom_up_adoption','EUR',1e7,5e7,1.5e8,'observed',
                        '[]','{}','[]','v1','0.1.0')""", (tid, now))
            cur.execute("""INSERT INTO opportunity_links
                (opportunity_id, node_id, link_type, confidence, evidence, created_at)
                VALUES (?,?,'L0',0.8,'{}',?)""", (tid, "capability_pool:test", now))


# ------------------------------------------------------------- projection

def test_som_is_not_summed_naively(cfg, db):
    """Obtainable share is per topic, against the same customers' same budgets.

    Summing selected spaces double-counts — and across the whole radar the naive
    sum reaches 90% of Orange Business's entire revenue. So a second space in a
    vertical is discounted, and the projection must come in BELOW the raw sum.
    """
    seed(db, cfg, n=6, vertical="manufacturing", som=100e6, distance=0)
    plan = Planner(cfg, db).plan(PlanInputs(entry_slots_per_year=99, pool_availability=1.0))
    assert len(plan["selections"]) > 1
    factors = sorted(s["overlap_factor"] for s in plan["selections"])
    assert factors[0] < 1.0, "no overlap discount was applied to the later entrants"
    # The naive sum is what a per-topic view would report. The projection must
    # come in below it, because these spaces compete for one buying centre.
    naive = sum(s["som_base"] for s in plan["selections"])
    year5 = plan["projection"]["revenue_by_year"][-1]
    assert year5 < naive


def test_entering_later_earns_less_inside_the_window(cfg, db):
    """A space ramps from ITS OWN entry year, which is what makes staggering
    cost something rather than being free scheduling."""
    seed(db, cfg, n=1)
    planner = Planner(cfg, db)
    cands = planner.candidates(PlanInputs())
    c = cands[0]
    early = sum(c.revenue_by_entry[1])
    late = sum(c.revenue_by_entry[max(c.revenue_by_entry)])
    assert late < early


def test_margin_varies_by_portfolio_distance(cfg, db):
    seed(db, cfg, n=2, distance=0)
    near = Planner(cfg, db).plan(PlanInputs(label="near"))
    assert near["selections"][0]["margin_applied"] == pytest.approx(
        cfg.economics["margin_by_distance"]["L0"])


def test_the_discount_rate_is_the_filed_one(cfg, db):
    seed(db, cfg, n=2)
    plan = Planner(cfg, db).plan(PlanInputs(objective="npv"))
    assert plan["projection"]["discount_rate"] == pytest.approx(
        cfg.economics["filed"]["discount_rate_post_tax"])


# ------------------------------------------------------------------ flags

def test_an_implausible_total_is_flagged_not_returned_silently(cfg, db):
    """Orange Business is 7,325m euros and declining. A plan implying a large
    fraction of that as INCREMENTAL revenue has to say so."""
    seed(db, cfg, n=8, som=3e9, distance=0, headcount=200000)
    plan = Planner(cfg, db).plan(PlanInputs(entry_slots_per_year=99, pool_availability=1.0))
    kinds = {f["kind"] for f in plan["flags"]}
    assert "plausibility" in kinds
    message = next(f["message"] for f in plan["flags"] if f["kind"] == "plausibility")
    assert "segment revenue" in message


def test_modelled_sizes_are_flagged_when_they_reach_a_plan(cfg, db):
    seed(db, cfg, n=4, confidence="modelled")
    plan = Planner(cfg, db).plan(PlanInputs(min_confidence="modelled"))
    assert any(f["kind"] == "confidence" for f in plan["flags"])


def test_the_evidence_floor_excludes_weaker_sizes(cfg, db):
    seed(db, cfg, n=4, confidence="modelled")
    with pytest.raises(ValueError):
        Planner(cfg, db).plan(PlanInputs(min_confidence="observed"))


# ------------------------------------------------------- reproducibility

def test_same_inputs_give_the_same_plan(cfg, db):
    seed(db, cfg, n=8)
    a = Planner(cfg, db).plan(PlanInputs(label="x"))
    b = Planner(cfg, db).plan(PlanInputs(label="x"))
    assert a["id"] == b["id"]
    assert ([s["opportunity_id"] for s in a["selections"]]
            == [s["opportunity_id"] for s in b["selections"]])
    assert a["projection"]["profit_total"] == b["projection"]["profit_total"]


def test_a_plan_records_the_assumptions_that_produced_it(cfg, db):
    seed(db, cfg, n=3)
    plan = Planner(cfg, db).plan(PlanInputs())
    assert plan["economics_version"] == cfg.economics_version
    assert plan["assumptions"]["filed"]["segment_ebitdaal_margin"]


# --------------------------------------------------------------- narrative

def test_a_narrative_section_containing_a_number_is_stripped(cfg, db):
    """The strictest guard in the Planner.

    Every figure already sits in the projection table beside the prose. A
    sentence that disagrees with it is a defect the reader has to adjudicate, so
    a section carrying a quantity is removed rather than reconciled.
    """
    seed(db, cfg, n=3)
    planner = Planner(cfg, db)
    plan = planner.plan(PlanInputs())
    planner._llm = _FakeLLM({
        "headline": "We will lead European industrial security.",
        "sections": {
            "thesis": "This portfolio concentrates on regulated industry where Orange has a "
                      "structural advantage, and it does so deliberately rather than opportunistically.",
            "why_these": "The plan will deliver 42% revenue growth over the window, which is "
                         "well ahead of the market and reflects our unique position.",
            "sequence": "Early entries establish reference deployments that later cohorts rely on "
                        "for credibility, so the ordering is load-bearing rather than cosmetic.",
            "capacity": "The plan commits the scarcer capability pools almost fully, which is the "
                        "real constraint on going faster than this.",
            "risks": "Obtainable share is a planning assumption rather than a forecast, and the "
                     "scarce pools may not staff up in time to hold this schedule.",
            "not_doing": "Spaces needing capabilities already committed were left out, and the "
                         "constraint rather than a preference is what excluded them.",
        },
        "spaces_named": [s["opportunity_id"] for s in plan["selections"]],
    })
    out = planner.narrate(plan["id"])
    assert "why_these" not in out["narrative"]["sections"]
    assert any(s["section"] == "why_these" and "quantity" in s["reason"]
               for s in out["stripped"])
    # The clean sections must survive; one bad section does not discard the rest.
    assert "thesis" in out["narrative"]["sections"]
    assert "risks" in out["narrative"]["sections"]


def test_a_narrative_naming_a_space_not_in_the_plan_is_stripped(cfg, db):
    seed(db, cfg, n=3)
    planner = Planner(cfg, db)
    plan = planner.plan(PlanInputs())
    planner._llm = _FakeLLM({
        "headline": "A focused European industrial portfolio.",
        "sections": {
            "thesis": "The plan leans on OS999, which anchors the whole industrial thesis and "
                      "gives the portfolio its centre of gravity in regulated manufacturing.",
        },
        "spaces_named": ["OS999"],
    })
    out = planner.narrate(plan["id"])
    assert "thesis" not in out["narrative"]["sections"]
    assert any("not in this plan" in s["reason"] for s in out["stripped"])


# ------------------------------------------------------------ the document

def _pdf_text(path):
    """Every page's text, so an assertion can be about what a reader sees."""
    import fitz

    with fitz.open(path) as doc:
        return "\n".join(page.get_text() for page in doc)


def _describe(db, topic_id, summary):
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    with db.cursor() as cur:
        cur.execute("""INSERT INTO topic_descriptions
                       (opportunity_id, generated_at, topic_version, sections, stripped,
                        prompt_version, model_version, pipeline_version)
                       VALUES (?,?,1,?,'[]','test','test','0.1.0')""",
                    (topic_id, now, js({"summary": {"text": summary}})))


def test_the_export_carries_every_section_the_screen_shows(cfg, db, tmp_path):
    """One document, or it is not an export.

    The point of the PDF is that somebody who was not in the room can read the
    whole argument — what was asked for, what came out, which spaces, why, and
    on what assumptions. A document missing one of those sends the reader back
    to the tool, which is the thing it exists to avoid.
    """
    from radar.plan_report import PlanReportBuilder

    seed(db, cfg, n=6)
    plan = Planner(cfg, db).plan(PlanInputs(label="Export test", plan_years=5))
    result = PlanReportBuilder(cfg, db, output_dir=tmp_path).build(plan)
    text = _pdf_text(result["path"])

    assert "The inputs that produced this plan" in text
    assert "The projection" in text
    assert "The selected opportunity spaces" in text
    assert "The business plan" in text
    assert "What this plan rests on" in text
    assert plan["id"] in text


def test_each_space_carries_its_own_one_paragraph_description(cfg, db, tmp_path):
    """A list of ids and euro figures does not tell a reader what anything IS."""
    from radar.plan_report import PlanReportBuilder

    seed(db, cfg, n=3)
    _describe(db, "OS000", "A distinctive sentence about brownfield telemetry backhaul.")
    plan = Planner(cfg, db).plan(PlanInputs(label="Descriptions"))
    text = _pdf_text(PlanReportBuilder(cfg, db, output_dir=tmp_path).build(plan)["path"])

    assert "brownfield telemetry backhaul" in text
    # And a space without one has to say so rather than leaving a silent gap.
    assert "No long-form description has been generated" in text


def test_the_export_states_the_filing_it_rests_on(cfg, db, tmp_path):
    """The two figures that turn a market size into money are Orange's own."""
    from radar.plan_report import PlanReportBuilder

    seed(db, cfg, n=4)
    plan = Planner(cfg, db).plan(PlanInputs(label="Provenance"))
    text = _pdf_text(PlanReportBuilder(cfg, db, output_dir=tmp_path).build(plan)["path"])

    assert "Universal Registration Document" in text
    assert "7.3%" in text and "7.9%" in text
    assert plan["economics_version"] in text


def test_unstated_inputs_are_shown_at_the_value_the_planner_actually_used(cfg, db, tmp_path):
    """An unset parameter is not an absent one.

    It falls back to the economics default and the optimiser plans against
    that, so an export that showed only the stated values would misrepresent
    what produced the plan.
    """
    from radar.plan_report import PlanReportBuilder

    seed(db, cfg, n=4)
    plan = Planner(cfg, db).plan(PlanInputs(label="Defaults"))
    text = _pdf_text(PlanReportBuilder(cfg, db, output_dir=tmp_path).build(plan)["path"])

    slots = cfg.economics["capacity"]["entry_slots_per_year"]
    assert "New spaces started per year" in text
    assert str(slots) in text
    assert "default" in text


def test_an_ungenerated_business_plan_is_declared_rather_than_omitted(cfg, db, tmp_path):
    from radar.plan_report import PlanReportBuilder

    seed(db, cfg, n=4)
    plan = Planner(cfg, db).plan(PlanInputs(label="No narrative"))
    assert not plan.get("narrative")
    text = _pdf_text(PlanReportBuilder(cfg, db, output_dir=tmp_path).build(plan)["path"])
    assert "has not been generated for this portfolio" in text


def test_the_narrative_reaches_the_document(cfg, db, tmp_path):
    from radar.plan_report import PlanReportBuilder

    seed(db, cfg, n=4)
    planner = Planner(cfg, db, llm=_FakeLLM({
        "headline": "Win the regulated European industrial edge.",
        "sections": {
            "thesis": "We concentrate where regulation forces a decision and where we already "
                      "deliver, rather than spreading thinly across every space the radar found.",
            "why_these": "These spaces reuse the capabilities we can staff today, which is why "
                         "they clear the capacity constraint that excluded the alternatives.",
            "sequence": "Regulated demand comes first and the platform plays follow, once the "
                        "reference deployments exist to sell them against.",
            "capacity": "The capability pools are the binding constraint here, not the market, "
                        "and the entry schedule is shaped by hiring rather than by demand.",
            "risks": "Obtainable share is a planning assumption rather than a forecast, and the "
                     "sequence stalls if hiring into the scarce pools lags the entry schedule.",
            "not_doing": "We decline anything that needs a capability already at its ceiling, "
                         "because taking it on would delay the commitments already made.",
        },
    }))
    plan = planner.plan(PlanInputs(label="Narrated"))
    plan = planner.narrate(plan["id"])
    text = _pdf_text(PlanReportBuilder(cfg, db, output_dir=tmp_path).build(plan)["path"])

    assert "Win the regulated European industrial edge." in text
    assert "regulation forces a decision" in text
    assert "has not been generated for this portfolio" not in text


def test_the_export_is_recorded_against_the_plan(cfg, db, tmp_path):
    """So the interface can tell a stale document from a current one."""
    from radar.plan_report import PLAN_REPORT_SCHEMA, PlanReportBuilder, plan_report_meta

    seed(db, cfg, n=4)
    plan = Planner(cfg, db).plan(PlanInputs(label="Recorded"))
    assert plan_report_meta(db, plan["id"]) is None

    result = PlanReportBuilder(cfg, db, output_dir=tmp_path).build(plan)
    meta = plan_report_meta(db, plan["id"])
    assert meta is not None
    assert meta["content_hash"] == result["content_hash"]
    assert meta["schema"] == PLAN_REPORT_SCHEMA
    assert meta["exists"] and not meta["stale"]


def test_missing_descriptions_are_counted_once_rather_than_left_as_a_gap(cfg, db, tmp_path):
    from radar.plan_report import PlanReportBuilder

    seed(db, cfg, n=3)
    _describe(db, "OS000", "One space here has a description and the other two do not.")
    plan = Planner(cfg, db).plan(PlanInputs(label="Coverage"))
    text = _pdf_text(PlanReportBuilder(cfg, db, output_dir=tmp_path).build(plan)["path"])
    assert f"1 of {plan['selected_count']} selected spaces have a long-form description" in text
