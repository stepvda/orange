"""Generated-description defences and the PDF brief (FR-14, FR-18, §4.4.4).

Prose is where a model invents, so the four defences of §4.4.4 are applied to it
in the same order of effectiveness as in synthesis. These tests hold the line on
each: an uncited factual section is stripped, a generated quantity kills the
section that carries it, an unsupplied organisation kills the section that names
it, and a diagram box cannot claim an Orange asset that is not linked.

The brief tests are deliberately end-to-end and file-level: a PDF that raises no
exception but renders an empty page is the failure a unit test misses.
"""

from __future__ import annotations

import datetime as dt

import pytest

from radar.brief import BriefBuilder, brief_for_topic, brief_path
from radar.competition import CompetitionAnalyser
from radar.config import get_config
from radar.db import Database, js
from radar.llm import LLMClient
from radar.pipeline.describe import DescriptionGenerator, description_for_topic


@pytest.fixture(scope="module")
def cfg():
    return get_config()


@pytest.fixture()
def db(tmp_path):
    database = Database(tmp_path / "test.db")
    database.init_schema()
    return database


class ScriptedLLM(LLMClient):
    """A model that returns exactly what a test wants it to return.

    Subclassing the real client rather than mocking it keeps the prompt
    construction, the JSON contract and the provenance stamping in the code path
    under test — those are where the defences live.
    """

    def __init__(self, payload):
        super().__init__(provider="mock")
        self.payload = payload
        self.strong_model = "scripted-test-model"

    def complete_json(self, system, user, **kwargs):  # noqa: D102 — see class docstring
        return self.payload


def base_payload(**overrides):
    sections = {
        "summary": {"text": "A specific opportunity for manufacturers with brownfield sites that "
                            "need to secure legacy control systems.", "signals": []},
        "what_is_changing": {"text": "Regulators now treat this as non-optional for industrial "
                                     "operators, and the evidence shows convergence pressure.",
                             "signals": ["SIG-1"]},
        "who_buys_and_why": {"text": "The head of OT security signs and the plant manager feels "
                                     "the downtime risk that triggers the conversation.",
                             "signals": []},
        "what_orange_would_deliver": {"text": "An assessment, then a segmentation design, then a "
                                              "managed service running it day to day.", "signals": []},
        "why_orange_can_win": {"text": "The managed-service model and the certifications matter "
                                       "more here than the product choice does.", "signals": []},
        "competitive_landscape": {"text": "The field is a mix of security specialists and "
                                          "integrators, and the customer will compare on "
                                          "operating model.", "signals": ["SIG-1"]},
        "risks_and_unknowns": {"text": "Brownfield estates differ enough that a single approach "
                                       "may not transfer between sites.", "signals": []},
    }
    payload = {
        "sections": sections,
        "qualifying_questions": ["What does your current segmentation look like on the plant floor?"],
        "objection_handling": [{"objection": "We already have a security vendor.",
                                "response": "That is true, and the gap is usually the operating "
                                            "model rather than the product."}],
        "diagram": {
            "title": "Zero trust for OT",
            "caption": "How the controls sit between the plant floor and the business.",
            "layers": [
                {"label": "Outcomes", "nodes": [{"label": "Regulatory compliance", "provider": "customer"}]},
                {"label": "Controls", "nodes": [{"label": "Microsegmentation", "provider": "third_party"}]},
                {"label": "Plant floor", "nodes": [{"label": "Legacy PLCs", "provider": "customer"}]},
            ],
            "flows": [{"from": "Legacy PLCs", "to": "Microsegmentation", "label": "traffic"}],
        },
        "entities_named": [],
    }
    payload.update(overrides)
    return payload


def seed(db, *, with_signal=True, with_offer=False):
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO opportunity_spaces
                 (id, version, vertical, use_case, technology, statement, domains, personas,
                  geographies, state, why_hot, first_seen, last_refresh, pipeline_version)
               VALUES ('OS001',1,'manufacturing','it_operations_automation','zero_trust_architecture',
                       'Zero trust for brownfield OT estates in manufacturing plants',
                       '["cybersecurity"]','[]','["EU"]','active',?, '2026-01-01','2026-08-01','0.1.0')""",
            (js([{"claim": "Regulators treat this as non-optional", "signals": ["SIG-1"]}]),),
        )
        if with_signal:
            cur.execute(
                """INSERT INTO signals
                     (id, source_id, publisher, title, url, published_at, ingested_at, tier, extract,
                      pipeline_version)
                   VALUES ('SIG-1','news','example.com','Zero trust becomes mandatory for OT',
                           'https://example.invalid','2026-07-01','2026-07-01',2,'extract','0.1.0')""",
            )
            cur.execute(
                "INSERT INTO opportunity_signals (opportunity_id, signal_id, attached_at, refresh_id) "
                "VALUES ('OS001','SIG-1','2026-07-01','R-test')"
            )
        if with_offer:
            cur.execute(
                "INSERT INTO graph_nodes (id, node_type, label, source, as_of) "
                "VALUES ('offer:managed_security','offer','Managed security services','config','2026-01-01')"
            )
            cur.execute(
                """INSERT INTO opportunity_links
                     (opportunity_id, node_id, link_type, confidence, evidence, created_at)
                   VALUES ('OS001','offer:managed_security','L0',0.9,'{"rule":"offer addresses use case"}',
                           '2026-08-01')"""
            )
    return dict(db.query_one("SELECT * FROM opportunity_spaces WHERE id = 'OS001'"))


def generate(cfg, db, payload, topic):
    return DescriptionGenerator(cfg, db, ScriptedLLM(payload)).generate(topic)


# ---------------------------------------------------------------------------
# Defence 1 — evidence binding
# ---------------------------------------------------------------------------

def test_uncited_factual_section_is_stripped_not_rewritten(cfg, db):
    topic = seed(db)
    payload = base_payload()
    payload["sections"]["what_is_changing"]["signals"] = []
    result = generate(cfg, db, payload, topic)

    assert "what_is_changing" not in result["sections"]
    assert any(entry["section"] == "what_is_changing" and "evidence binding" in entry["reason"]
               for entry in result["stripped"])


def test_citations_must_be_signals_attached_to_this_topic(cfg, db):
    """A plausible id from another topic is not evidence for this one."""
    topic = seed(db)
    payload = base_payload()
    payload["sections"]["what_is_changing"]["signals"] = ["SIG-DOES-NOT-EXIST"]
    result = generate(cfg, db, payload, topic)
    assert "what_is_changing" not in result["sections"]


def test_non_factual_sections_do_not_need_a_citation(cfg, db):
    """A proposal cannot be 'supported by a source'.

    Demanding a citation for one would only teach the model to attach one at
    random, which is exactly what makes §4.4.4's binding rule work elsewhere.
    """
    topic = seed(db)
    result = generate(cfg, db, base_payload(), topic)
    assert result["sections"]["what_orange_would_deliver"]["signals"] == []
    assert result["sections"]["what_orange_would_deliver"]["text"]


# ---------------------------------------------------------------------------
# Defence 3 — no model-generated numbers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "The market is growing 30% a year across the region and shows no sign of slowing down.",
    "A typical deployment costs €400,000 for a mid-sized plant with several production lines.",
    "Adoption has risen 3x since the directive was adopted across the European industrial base.",
])
def test_a_generated_quantity_kills_its_section(cfg, db, text):
    """The brief's figures come from the sizing engine.

    A model sentence that contradicts them is worse than a missing one, so the
    regex backstop runs over prose exactly as it runs over claims.
    """
    topic = seed(db)
    payload = base_payload()
    payload["sections"]["summary"]["text"] = text
    result = generate(cfg, db, payload, topic)
    assert "summary" not in result["sections"]
    assert any("generated quantity" in entry["reason"] for entry in result["stripped"])


def test_a_generated_quantity_in_a_question_drops_that_question(cfg, db):
    topic = seed(db)
    payload = base_payload()
    payload["qualifying_questions"] = [
        "How many of your sites are affected by the directive?",
        "Would you spend €250,000 on a pilot this year?",
    ]
    result = generate(cfg, db, payload, topic)
    assert result["sections"]["qualifying_questions"] == [
        "How many of your sites are affected by the directive?"
    ]


# ---------------------------------------------------------------------------
# Defence 4 — named entities
# ---------------------------------------------------------------------------

def test_naming_an_unsupplied_organisation_removes_the_section(cfg, db):
    """Naming a plausible account is the failure most likely to reach a meeting."""
    topic = seed(db)
    payload = base_payload()
    payload["sections"]["why_orange_can_win"]["text"] = (
        "Heathrow already runs this model and would act as the reference for the next deal.")
    payload["entities_named"] = ["Heathrow"]
    result = generate(cfg, db, payload, topic)
    assert "why_orange_can_win" not in result["sections"]
    assert any("never supplied" in entry["reason"] for entry in result["stripped"])


def test_supplied_competitors_and_assets_may_be_named(cfg, db):
    topic = seed(db, with_offer=True)
    CompetitionAnalyser(cfg, db).run(topic_ids=["OS001"])
    payload = base_payload()
    payload["sections"]["why_orange_can_win"]["text"] = (
        "Managed security services is the asset that carries this, and the comparison will be "
        "against Fortinet on operating model rather than on features.")
    payload["entities_named"] = ["Managed security services", "Fortinet"]
    result = generate(cfg, db, payload, topic)
    assert "why_orange_can_win" in result["sections"]


# ---------------------------------------------------------------------------
# Defence 2 — closed vocabulary, applied to the diagram
# ---------------------------------------------------------------------------

def test_a_diagram_box_cannot_claim_an_unlinked_orange_asset(cfg, db):
    """The visual equivalent of an invented account name.

    The component still belongs in the picture, so it is demoted rather than
    deleted — and the demotion is recorded.
    """
    topic = seed(db)  # no linked assets
    payload = base_payload()
    payload["diagram"]["layers"][1]["nodes"] = [
        {"label": "Orange Sovereign Zero Trust Platform", "provider": "orange"}
    ]
    result = generate(cfg, db, payload, topic)
    node = result["sections"]["diagram"]["layers"][1]["nodes"][0]
    assert node["provider"] == "third_party"
    assert any("Orange asset that was not supplied" in entry["reason"] for entry in result["stripped"])


def test_a_diagram_box_backed_by_a_linked_asset_keeps_its_claim(cfg, db):
    topic = seed(db, with_offer=True)
    payload = base_payload()
    payload["diagram"]["layers"][1]["nodes"] = [
        {"label": "Managed security services", "provider": "orange"}
    ]
    result = generate(cfg, db, payload, topic)
    assert result["sections"]["diagram"]["layers"][1]["nodes"][0]["provider"] == "orange"


def test_flows_to_boxes_that_do_not_exist_are_dropped(cfg, db):
    """An arrow to nowhere is a drawing bug the reader would have to debug."""
    topic = seed(db)
    payload = base_payload()
    payload["diagram"]["flows"] = [
        {"from": "Legacy PLCs", "to": "Microsegmentation", "label": "traffic"},
        {"from": "Legacy PLCs", "to": "A box that was never declared", "label": "?"},
    ]
    result = generate(cfg, db, payload, topic)
    assert len(result["sections"]["diagram"]["flows"]) == 1


def test_an_unknown_provider_value_falls_back_to_third_party(cfg, db):
    topic = seed(db)
    payload = base_payload()
    payload["diagram"]["layers"][1]["nodes"] = [{"label": "Some control", "provider": "magic"}]
    result = generate(cfg, db, payload, topic)
    assert result["sections"]["diagram"]["layers"][1]["nodes"][0]["provider"] == "third_party"


# ---------------------------------------------------------------------------
# Staleness and provenance
# ---------------------------------------------------------------------------

def test_description_records_the_topic_version_and_reports_staleness(cfg, db):
    """§4.1: a description of evidence the topic no longer rests on is worse than none."""
    topic = seed(db)
    generate(cfg, db, base_payload(), topic)
    assert description_for_topic(db, "OS001")["stale"] is False

    with db.cursor() as cur:
        cur.execute("UPDATE opportunity_spaces SET version = version + 1 WHERE id = 'OS001'")
    stored = description_for_topic(db, "OS001")
    assert stored["stale"] is True
    assert stored["provenance"]["prompt_version"]
    assert stored["provenance"]["model_version"] == "scripted-test-model"


def test_regeneration_is_skipped_while_the_topic_is_unchanged(cfg, db):
    topic = seed(db)
    generator = DescriptionGenerator(cfg, db, ScriptedLLM(base_payload()))
    generator.generate(topic)
    stats = generator.run(topic_ids=["OS001"])
    assert stats["generated"] == 0 and stats["skipped_fresh"] == 1


# ---------------------------------------------------------------------------
# The brief itself (FR-18)
# ---------------------------------------------------------------------------

def test_brief_renders_a_multi_page_pdf_with_its_provenance(cfg, db, tmp_path):
    topic = seed(db, with_offer=True)
    CompetitionAnalyser(cfg, db).run(topic_ids=["OS001"])
    generate(cfg, db, base_payload(), topic)

    meta = BriefBuilder(cfg, db, output_dir=tmp_path / "briefs").build("OS001")
    path = brief_path(db, "OS001")
    assert path is not None and path.exists()
    assert meta["bytes"] > 5000
    assert meta["weight_set"] and meta["sizing_version"]
    assert path.read_bytes().startswith(b"%PDF")

    import pypdf
    reader = pypdf.PdfReader(str(path))
    text = "\n".join(page.extract_text() for page in reader.pages)
    # The three kinds of content must all reach the page.
    assert "Zero trust for brownfield OT estates" in text          # computed/curated identity
    assert "Managed security services" in text                     # curated asset
    assert "competitive intensity" in text.lower()                 # computed intensity
    assert "How this brief was made" in text                       # provenance page


def test_brief_builds_without_a_description(cfg, db, tmp_path):
    """The computed and curated content is worth having on its own.

    A model outage should degrade the brief, not block it.
    """
    seed(db, with_offer=True)
    meta = BriefBuilder(cfg, db, output_dir=tmp_path / "briefs").build("OS001")
    assert meta["bytes"] > 3000
    import pypdf
    text = "\n".join(p.extract_text() for p in pypdf.PdfReader(str(brief_path(db, "OS001"))).pages)
    assert "No generated description yet" in text


def test_brief_reports_staleness_against_the_topic_version(cfg, db, tmp_path):
    seed(db)
    BriefBuilder(cfg, db, output_dir=tmp_path / "briefs").build("OS001")
    assert brief_for_topic(db, "OS001")["stale"] is False
    with db.cursor() as cur:
        cur.execute("UPDATE opportunity_spaces SET version = version + 1 WHERE id = 'OS001'")
    assert brief_for_topic(db, "OS001")["stale"] is True


def test_brief_is_deterministic_for_unchanged_inputs(cfg, db, tmp_path):
    """Two builds of the same topic differ only by their timestamp.

    Byte equality is not achievable — the PDF embeds a creation date and the
    footer prints the build time — so the check is on the extracted text with
    the generated-at line removed.
    """
    import re

    import pypdf

    topic = seed(db, with_offer=True)
    generate(cfg, db, base_payload(), topic)
    builder = BriefBuilder(cfg, db, output_dir=tmp_path / "briefs")

    def text_of() -> str:
        builder.build("OS001")
        raw = "\n".join(p.extract_text() for p in pypdf.PdfReader(str(brief_path(db, "OS001"))).pages)
        return re.sub(r"Generated \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC", "", raw)

    assert text_of() == text_of()


def test_brief_goes_stale_when_the_narrative_is_rewritten(cfg, db, tmp_path):
    """The likelier staleness: the topic is unchanged but the prose was redone.

    Someone reads the description, presses Regenerate, and the PDF a colleague
    received an hour ago now says something the radar does not. Checking only the
    topic version missed exactly that case.
    """
    topic = seed(db, with_offer=True)
    generate(cfg, db, base_payload(), topic)
    BriefBuilder(cfg, db, output_dir=tmp_path / "briefs").build("OS001")
    assert brief_for_topic(db, "OS001")["stale"] is False

    with db.cursor() as cur:
        cur.execute("UPDATE topic_descriptions SET generated_at = '2099-01-01T00:00:00+00:00' "
                    "WHERE opportunity_id = 'OS001'")
    meta = brief_for_topic(db, "OS001")
    assert meta["stale"] is True
    assert "description" in meta["stale_reason"]


def test_brief_goes_stale_when_the_market_size_is_recomputed(cfg, db, tmp_path):
    """A brief quotes figures; recomputing them invalidates the quote."""
    # `tests` is not a package — pytest puts this directory on sys.path, so the
    # sibling module is imported by its own name. `from tests.test_sizing import`
    # only resolves when the project root happens to be on the path, which
    # `pythonpath = ["src"]` guarantees it is not.
    from test_sizing import seed_reference, seed_tender

    from radar.sizing import MarketSizer

    topic = seed(db, with_offer=True)
    seed_reference(db, nace_sbs="C10", nace_ict="C10-C12")
    for index in range(8):
        seed_tender(db, f"SIG-T{index}", 400_000.0, days_ago=index * 9)
    MarketSizer(cfg, db).run(topic_ids=["OS001"])
    generate(cfg, db, base_payload(), topic)
    BriefBuilder(cfg, db, output_dir=tmp_path / "briefs").build("OS001")
    assert brief_for_topic(db, "OS001")["stale"] is False

    with db.cursor() as cur:
        cur.execute("UPDATE market_sizes SET computed_at = '2099-01-01T00:00:00+00:00' "
                    "WHERE opportunity_id = 'OS001'")
    meta = brief_for_topic(db, "OS001")
    assert meta["stale"] is True
    assert "market size" in meta["stale_reason"]
