"""The scoping conversation behind the Generate screen (FR-06, §4.4, §4.4.4).

The screen used to offer a textarea and a character counter — one input, and the
only failure it could warn about was length, which is the one that does not
matter. These tests are about the three claims the conversation replacing it
makes, each of which is a place where a chat UI over a pipeline usually starts
lying:

*   IT READS THE CORPUS, and the retrieval is the same one the run performs, at
    the same floor. A conversation shown evidence the pipeline would refuse to
    build on is more optimistic than the thing behind it.
*   THE MODEL DOES NOT DECIDE WHEN IT IS DONE. `ready` is re-derived from the
    corpus over every brief proposed, so a model that says yes to be helpful
    still cannot enable the button.
*   THE VOCABULARIES ARE STILL CLOSED (§3.3). What a person says is mapped onto
    ids where it can be and dropped where it cannot, never carried through as
    free text that would fail validation three stages later.

Plus the multi-brief run: a conversation that lands on several distinct triples
is one job, and its report has to distinguish what it created from what DR-03
made it refresh.
"""

from __future__ import annotations

import datetime as dt
import functools
import re

import pytest

from radar.config import get_config
from radar.db import Database, js
from radar.embeddings import Embedder
from radar.generation import MAX_BRIEFS_PER_RUN, GenerationService
from radar.llm import LLMClient
from radar.pipeline import prompts
from radar.pipeline.synthesis import SynthesisStats
from radar.scoping import ScopingError, ScopingService

REF = dt.date(2026, 8, 17)


@pytest.fixture(autouse=True)
def no_provider_calls(monkeypatch):
    """No test may reach a real model — see test_generation for the argument."""
    monkeypatch.setenv("RADAR_LLM_PROVIDER", "mock")


@pytest.fixture(scope="module")
def cfg():
    return get_config()


@pytest.fixture()
def db(tmp_path):
    database = Database(tmp_path / "t.db")
    database.init_schema()
    return database


@functools.lru_cache(maxsize=1)
def _embedder() -> Embedder:
    return Embedder()


class Scripted(LLMClient):
    """A model that answers with exactly the object a test wants to test.

    The point of nearly every test below is what the SERVER does with a reply —
    resolve it, re-retrieve it, overrule it — so the reply has to be chosen
    rather than sampled.

    Two prompts reach it, and they are told apart by the marker in the system
    prompt: the scoping turn itself, and the cheap second opinion on whether
    retrieved evidence is about a brief.

    `support` defaults to endorsing everything that was retrieved, which is the
    ordinary case — the corpus is about the brief. A test that is specifically
    about the gate REFUSING passes `support={"supporting": []}`, so the refusal
    is stated in the test rather than inherited from a default.
    """

    def __init__(self, payload: dict, support: dict | None = None):
        super().__init__(provider="mock")
        self.payload = payload
        self.support = support
        self.seen: list[tuple[str, str]] = []

    def complete_json(self, system: str, user: str, **kwargs):
        self.seen.append((system, user))
        if "MOCK_KIND=brief_support" in system:
            if self.support is not None:
                return self.support
            return {"supporting": re.findall(r"^\[(SIG-[^\]]+)\]", user, re.M),
                    "note": "endorsed by default"}
        return self.payload

    @property
    def support_calls(self) -> int:
        return sum(1 for system, _ in self.seen if "MOCK_KIND=brief_support" in system)


#: A corpus about one specific thing, so "close" and "not close" are separable.
_SIGNALS = [
    ("SIG-1", "Gearbox vibration monitoring pilot at a North Sea wind farm",
     "An offshore wind operator reports an acoustic sensor pilot for gearbox condition monitoring.",
     "proof_signal", ["NL"]),
    ("SIG-2", "Tender for predictive maintenance services on offshore turbines",
     "A framework agreement for turbine condition monitoring services was published.",
     "buying_signal", ["DE"]),
    ("SIG-3", "Acoustic emission sensing standard for rotating machinery",
     "An IEC work item covers acoustic emission condition monitoring of rotating equipment.",
     "technology_maturity", ["EU"]),
    ("SIG-4", "Wind operators face new incident reporting duties",
     "Energy operators must report operational incidents under the transposed directive.",
     "regulation", ["DE", "NL"]),
]

_BRIEF = ("Acoustic and vibration condition monitoring of gearboxes for offshore wind turbine "
          "operators in the North Sea, sold as a managed service.")


def _seed(db: Database, embed: bool = True) -> None:
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    embedder = _embedder() if embed else None
    with db.cursor() as cur:
        cur.execute("INSERT INTO clusters (id, label, keyphrases, size, created_at, refresh_id) "
                    "VALUES (1,'offshore wind condition monitoring',?,4,?,'R-seed')",
                    (js(["gearbox", "acoustic", "turbine"]), now))
        for signal_id, title, extract, signal_type, geo in _SIGNALS:
            cur.execute(
                """INSERT INTO signals (id, source_id, publisher, title, url, published_at,
                                        ingested_at, language, geographies, signal_type, tier,
                                        extract, relevance, cluster_id, pipeline_version)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (signal_id, "src", "Publisher", title, f"https://example.invalid/{signal_id}",
                 REF.isoformat(), now, "en", js(geo), signal_type, 2, extract, 0.9, 1, "test"),
            )
            if embedder is not None:
                vector = embedder.encode([f"{title} {extract}"])[0]
                cur.execute("UPDATE signals SET embedding = ? WHERE id = ?",
                            (Embedder.to_blob(vector), signal_id))


def _service(cfg, db, payload: dict, support: dict | None = None) -> tuple[ScopingService, Scripted]:
    llm = Scripted(payload, support)
    return ScopingService(cfg, db, embedder=_embedder(), llm=llm), llm


def _reply(understood=None, ready=False, briefs=()):
    return {"reply": "A question.", "understood": understood or {}, "missing": [],
            "asking_for": None, "suggestions": [], "ready": ready, "briefs": list(briefs)}


def _brief(description=_BRIEF, **overrides):
    base = {"title": "Gearbox monitoring", "description": description, "vertical": "energy",
            "use_case": "predictive_maintenance", "technology": "low_power_sensors",
            "geographies": ["NL", "DE"], "rationale": "The tenders and the pilot corroborate it."}
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# The opening turn costs nothing and still says what it can see
# ---------------------------------------------------------------------------

def test_the_opening_turn_costs_no_model_call(cfg, db):
    """It is identical every time. Generating it would buy latency on a screen
    nobody has typed into yet, and nothing else."""
    _seed(db, embed=False)
    service, llm = _service(cfg, db, _reply())
    opening = service.opening()
    assert llm.seen == []
    assert opening["message"] == prompts.SCOPING_OPENING


def test_the_opening_reports_the_corpus_rather_than_promising_anything(cfg, db):
    """The first screen has to establish that this is an interview about a fixed
    body of evidence. Numbers do that; an invitation to describe anything at all
    does the opposite."""
    _seed(db, embed=False)
    service, _ = _service(cfg, db, _reply())
    corpus = service.opening()["corpus"]
    assert corpus["signals"] == 4
    assert corpus["clusters"] == 1
    assert corpus["clusters_sample"][0]["label"] == "offshore wind condition monitoring"
    assert dict(corpus["by_geography"])["DE"] == 2
    assert dict(corpus["by_signal_type"])["buying_signal"] == 1


# ---------------------------------------------------------------------------
# Retrieval: the same one the run performs, at the same floor
# ---------------------------------------------------------------------------

def test_a_turn_retrieves_from_the_whole_conversation_not_the_last_message(cfg, db):
    """"Germany" retrieves nothing. "Germany" as the third answer in a
    conversation about gearboxes retrieves what the conversation is about — and
    a question asked from the last message alone is the reason chat scoping
    tools feel like they are not listening."""
    _seed(db)
    service, llm = _service(cfg, db, _reply())
    out = service.reply([
        {"role": "user", "content": "acoustic gearbox monitoring for offshore wind operators"},
        {"role": "assistant", "content": "Which countries?"},
        {"role": "user", "content": "Germany"},
    ])
    assert out["evidence"]["count"] >= 3
    _, user_prompt = llm.seen[-1]
    assert "SIG-1" in user_prompt


def test_the_conversation_uses_the_runs_own_similarity_floor(cfg, db):
    """A screen more permissive than the pipeline behind it shows evidence the
    run will refuse to build on, and the mismatch surfaces as an empty result
    from a conversation that looked confident."""
    _seed(db)
    service, _ = _service(cfg, db, _reply())
    out = service.reply([{"role": "user", "content": "offshore wind gearbox condition monitoring"}])
    floor = float(cfg.settings["enrichment"]["similarity_threshold"])
    assert out["evidence"]["floor"] == floor
    assert all(s["similarity"] >= floor for s in out["evidence"]["signals"])


def test_the_evidence_carries_what_makes_it_checkable(cfg, db):
    """Putting a retrieval beside a conversation is only worth anything if it can
    be opened and disagreed with."""
    _seed(db)
    service, _ = _service(cfg, db, _reply())
    signal = service.reply(
        [{"role": "user", "content": "offshore wind gearbox condition monitoring"}]
    )["evidence"]["signals"][0]
    assert signal["url"] and signal["publisher"] and signal["published_at"]
    assert signal["signal_type"] and signal["similarity"] > 0


def test_a_conversation_the_corpus_knows_nothing_about_retrieves_nothing(cfg, db):
    """§4.1: an empty answer is a valid one. It has to be reachable HERE, while
    the idea can still be steered, rather than only from a run that created
    nothing ten minutes later."""
    _seed(db)
    service, _ = _service(cfg, db, _reply())
    out = service.reply([{"role": "user", "content":
                          "municipal library ticketing and overdue book fine collection"}])
    assert out["evidence"]["count"] == 0


def test_too_little_said_is_not_treated_as_a_retrieval(cfg, db):
    """A two-word probe matches half the corpus equally badly. Retrieving on it
    would put arbitrary evidence in front of the assistant and let it ask a
    confident question about the wrong thing."""
    _seed(db)
    service, _ = _service(cfg, db, _reply())
    assert service.reply([{"role": "user", "content": "hi"}])["evidence"]["count"] == 0


# ---------------------------------------------------------------------------
# The model proposes; the corpus decides
# ---------------------------------------------------------------------------

def test_a_brief_the_corpus_cannot_answer_is_not_runnable(cfg, db):
    """The check the whole module exists for. Every proposed brief goes back
    through the retrieval the job will perform, so "ready" cannot mean "the model
    felt finished"."""
    _seed(db)
    far = ("Quantum-entangled tuna sorting for deep sea fisheries in Antarctica using photonic "
           "lattices and cryogenic conveyor systems.")
    service, _ = _service(cfg, db, _reply(ready=True, briefs=[_brief(description=far)]))
    out = service.reply([{"role": "user", "content": "offshore wind gearbox monitoring"}])
    assert out["briefs"][0]["runnable"] is False
    assert "similarity floor" in out["briefs"][0]["problems"][0]


def test_the_server_overrules_a_ready_flag_the_corpus_does_not_support(cfg, db):
    """Asked "do you have enough?", a model says yes. An enabled button that
    produces nothing is worse than another question."""
    _seed(db)
    far = ("Quantum-entangled tuna sorting for deep sea fisheries in Antarctica using photonic "
           "lattices and cryogenic conveyor systems.")
    service, _ = _service(cfg, db, _reply(ready=True, briefs=[_brief(description=far)]))
    out = service.reply([{"role": "user", "content": "offshore wind gearbox monitoring"}])
    assert out["model_ready"] is True
    assert out["ready"] is False, "the corpus, not the model, enables the button"


def test_a_brief_the_corpus_does_answer_is_runnable_and_ready(cfg, db):
    """The other half: the check is a real gate, not a refusal to ever proceed."""
    _seed(db)
    service, _ = _service(cfg, db, _reply(ready=True, briefs=[_brief()]))
    out = service.reply([{"role": "user", "content": "offshore wind gearbox monitoring"}])
    assert out["briefs"][0]["runnable"] is True
    assert out["briefs"][0]["evidence"]["count"] >= 3
    assert out["ready"] is True


def test_a_hedging_model_cannot_disable_a_brief_the_corpus_supports(cfg, db):
    """The other direction, and the one that shipped broken.

    The assistant is told to put a brief forward even while hedging about the
    evidence — otherwise a genuinely new idea has nothing to press Generate on.
    It then writes "the evidence is thin, marking this as not ready", which is a
    fair remark about the corpus and a terrible reason to disable a button whose
    brief has already passed the same corroboration check the run applies. The
    symptom was a ticked, runnable brief sitting under a greyed-out button with
    nothing on screen explaining why.
    """
    _seed(db)
    service, _ = _service(cfg, db, _reply(ready=False, briefs=[_brief()]))
    out = service.reply([{"role": "user", "content": "offshore wind gearbox monitoring"}])
    assert out["briefs"][0]["runnable"] is True
    assert out["model_ready"] is False, "the model hedged"
    assert out["ready"] is True, "and the corpus overruled it"


def test_ready_is_refused_when_the_model_proposes_no_brief_at_all(cfg, db):
    """Nothing to run means nothing to enable, whatever the flag says."""
    _seed(db)
    service, _ = _service(cfg, db, _reply(ready=True, briefs=[]))
    assert service.reply([{"role": "user", "content": "offshore wind"}])["ready"] is False


def test_a_slot_settled_earlier_survives_a_turn_that_forgets_it(cfg, db):
    """The bug behind "it just does not generate".

    Observed against the live radar: turn one settled the use case and the
    technology, turn two settled the vertical and silently dropped both of the
    others, and the assistant then asked again about a use case it had named
    itself. The three axes were never known at once, so no brief was ever
    proposed and the screen had nothing on it to click.
    """
    _seed(db)
    forgetful = _reply(understood={"vertical": "energy"})   # drops the other two
    service, _ = _service(cfg, db, forgetful)
    out = service.reply(
        [{"role": "user", "content": "offshore wind gearbox monitoring"}],
        established={"use_case": "predictive_maintenance", "technology": "low_power_sensors"},
    )
    u = out["understood"]
    assert u["vertical"] == "energy", "this turn's answer"
    assert u["use_case"] == "predictive_maintenance", "carried from an earlier turn"
    assert u["technology"] == "low_power_sensors"
    assert out["missing"] == [], "so nothing is still outstanding"
    assert len(out["briefs"]) == 1, "and a brief exists to act on"


def test_a_fresh_answer_beats_the_carried_one(cfg, db):
    """Somebody who says "actually, make it retail" must be able to."""
    _seed(db)
    service, _ = _service(cfg, db, _reply(understood={"vertical": "retail"}))
    out = service.reply([{"role": "user", "content": "offshore wind gearbox monitoring"}],
                        established={"vertical": "energy"})
    assert out["understood"]["vertical"] == "retail"


def test_what_was_established_reaches_the_prompt(cfg, db):
    """The merge is the safety net; showing the model what is settled is the fix.
    It forgets because it is re-deriving from the transcript every turn."""
    _seed(db)
    service, llm = _service(cfg, db, _reply())
    service.reply([{"role": "user", "content": "offshore wind gearbox monitoring"}],
                  established={"use_case": "predictive_maintenance"})
    user = next(u for sy, u in llm.seen if "MOCK_KIND=scoping" in sy)
    assert "ALREADY ESTABLISHED" in user
    assert "predictive_maintenance" in user


def test_a_carried_slot_is_still_validated(cfg, db):
    """The browser sends it, so it is not trusted: a value outside the closed
    vocabulary must not reach a brief just because it arrived by this door."""
    _seed(db)
    service, _ = _service(cfg, db, _reply())
    out = service.reply([{"role": "user", "content": "offshore wind gearbox monitoring"}],
                        established={"vertical": "underwater basket weaving"})
    assert out["understood"]["vertical"] is None


def test_a_settled_conversation_always_leaves_a_brief_to_act_on(cfg, db):
    """The complaint this exists for: "it often fails for an unclear reason".

    The model is told to propose a brief once the three axes are settled, and
    mostly does — but a turn that resolves all three and then offers nothing
    reads as a refusal with no stated cause, and leaves nowhere to click. So the
    server composes one from the conversation rather than returning an empty
    screen.
    """
    _seed(db)
    settled = {"vertical": "energy", "use_case": "predictive_maintenance",
               "technology": "low_power_sensors"}
    service, _ = _service(cfg, db, _reply(understood=settled, briefs=[]))
    out = service.reply([
        {"role": "user", "content": "gearbox failures on offshore wind turbines in the North Sea"},
        {"role": "assistant", "content": "Which technology?"},
        {"role": "user", "content": "acoustic and vibration sensors with a machine learning model"},
    ])
    assert len(out["briefs"]) == 1, "the server composed one"
    brief = out["briefs"][0]
    assert (brief["vertical"], brief["use_case"], brief["technology"]) == (
        "energy", "predictive_maintenance", "low_power_sensors")
    assert "acoustic and vibration sensors" in brief["description"], "in the person's own words"
    assert brief["hypothesis"] is True, "and it carries a route"


def test_nothing_is_composed_while_the_axes_are_still_open(cfg, db):
    """A brief invented before the interview has settled would be the screen
    guessing, which is the opposite of what the conversation is for."""
    _seed(db)
    service, _ = _service(cfg, db, _reply(understood={"vertical": "energy"}, briefs=[]))
    out = service.reply([{"role": "user", "content": "something about wind turbines"}])
    assert out["briefs"] == []


def test_the_second_route_stays_open_on_a_brief_the_corpus_carries(cfg, db):
    """A runnable brief is not a guaranteed space — the run log's commonest
    ending is a candidate the critic threw out. Someone who has just watched a
    finished run create nothing needs the other route to still be there."""
    _seed(db)
    service, _ = _service(cfg, db, _reply(ready=True, briefs=[_brief()]))
    brief = service.reply([{"role": "user", "content": "offshore wind gearbox monitoring"}])["briefs"][0]
    assert brief["runnable"] is True
    assert brief["hypothesis"] is True


def test_a_brief_too_short_to_retrieve_with_is_reported_not_dropped(cfg, db):
    """"Nearly right, and here is what is wrong" is the outcome worth having —
    it is the only version that tells someone what to say next."""
    _seed(db)
    service, _ = _service(cfg, db, _reply(ready=True, briefs=[_brief(description="gearboxes")]))
    brief = service.reply([{"role": "user", "content": "offshore wind gearbox monitoring"}])["briefs"][0]
    assert brief["runnable"] is False
    assert any("Too short" in problem for problem in brief["problems"])


def test_more_briefs_than_a_conversation_may_produce_are_cut(cfg, db):
    """Each brief is a full synthesis pass with its own model calls (NFR-10), so
    the cap is a cost bound rather than a stylistic preference."""
    _seed(db)
    many = [_brief(title=f"S{i}") for i in range(prompts.MAX_BRIEFS_PER_CHAT + 3)]
    service, _ = _service(cfg, db, _reply(ready=True, briefs=many))
    out = service.reply([{"role": "user", "content": "offshore wind gearbox monitoring"}])
    assert len(out["briefs"]) == prompts.MAX_BRIEFS_PER_CHAT


# ---------------------------------------------------------------------------
# Similarity is not support
#
# The failure these exist for was observed, not imagined. A brief for municipal
# digital signage retrieved fourteen French public-sector IT tenders at 0.64
# cosine — the same closest score as a well-evidenced brief about wind turbine
# gearboxes — and the chat enabled the button. Synthesis then produced two
# candidates and the critic rejected both, correctly and for the right reason:
# "SIG-... is about digital territorial platforms for employment services, not
# digital signage or advertising revenue". Five model calls, nothing created.
#
# A similarity threshold could not have caught it; both briefs scored 0.64. What
# separates them is whether the retrieved signals are ABOUT the use case and the
# technology, which is the test `config/settings.yaml` already prescribes for
# enrichment and which this reuses rather than reinvents.
# ---------------------------------------------------------------------------

def _seed_adjacent(db: Database) -> None:
    """A corpus that is the right sector and country and nothing more.

    Every row is a public-sector IT procurement notice. None mentions signage,
    screens, advertising or edge computing — exactly the shape that retrieves
    well against a signage brief and supports none of it.
    """
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    embedder = _embedder()
    rows = [
        ("SIG-A1", "France - Telecommunications services for a city council",
         "A municipality procures fixed and mobile telecommunications services for its "
         "administrative sites and public buildings."),
        ("SIG-A2", "France - Software supply services for municipal administration",
         "Acquisition and maintenance of software licences for the information systems of a "
         "city administration."),
        ("SIG-A3", "France - IP telephone services framework for public bodies",
         "A framework agreement covering IP telephony for regional public authorities."),
        ("SIG-A4", "Belgium - Digital public services progress report",
         "A review of digital public service delivery for citizens by regional government."),
        ("SIG-A5", "France - Hosting and operation of territorial digital platforms",
         "Hosting, maintenance and operation of digital platforms for regional employment "
         "services."),
    ]
    with db.cursor() as cur:
        cur.execute("INSERT INTO clusters (id, label, keyphrases, size, created_at, refresh_id) "
                    "VALUES (2,'french public sector IT procurement','[]',5,?,'R-seed')", (now,))
        for signal_id, title, extract in rows:
            cur.execute(
                """INSERT INTO signals (id, source_id, publisher, title, url, published_at,
                                        ingested_at, language, geographies, signal_type, tier,
                                        extract, relevance, cluster_id, pipeline_version)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (signal_id, "src", "ted.europa.eu", title,
                 f"https://example.invalid/{signal_id}", REF.isoformat(), now, "en",
                 js(["FR"]), "buying_signal", 1, extract, 0.9, 2, "test"),
            )
            vector = embedder.encode([f"{title} {extract}"])[0]
            cur.execute("UPDATE signals SET embedding = ? WHERE id = ?",
                        (Embedder.to_blob(vector), signal_id))


_SIGNAGE = ("Managed service for French municipalities to deploy digital signage on street "
            "screens, enabling commercial advertising revenue. Edge computing processes content "
            "locally for reliability, including network connectivity and operations.")


def test_a_retrieval_of_same_sector_documents_does_not_make_a_brief_runnable(cfg, db):
    """The observed failure, as a test. The corpus is all French public-sector
    IT; the brief is about advertising screens. Retrieval is happy and the brief
    is still unsupported."""
    _seed_adjacent(db)
    service, _ = _service(cfg, db, _reply(ready=True, briefs=[_brief(
        description=_SIGNAGE, vertical="public_sector",
        use_case="citizen_service_automation", technology="edge_computing")]), support={"supporting": [], "note": "same sector, different subject"})
    out = service.reply([{"role": "user", "content": "digital signage on municipal street screens"}])
    brief = out["briefs"][0]
    assert brief["evidence"]["count"] > 0, "it retrieves — that was never the problem"
    assert brief["evidence"]["corroborated"] < 3
    assert brief["runnable"] is False
    assert out["ready"] is False


def test_the_refusal_names_the_gap_between_retrieved_and_supported(cfg, db):
    """"Nothing was close enough" would be false here and would send someone
    looking for a better sentence. The count that matters is the second one."""
    _seed_adjacent(db)
    service, _ = _service(cfg, db, _reply(ready=True, briefs=[_brief(
        description=_SIGNAGE, vertical="public_sector",
        use_case="citizen_service_automation", technology="edge_computing")]), support={"supporting": [], "note": "same sector, different subject"})
    problem = service.reply(
        [{"role": "user", "content": "digital signage on municipal street screens"}]
    )["briefs"][0]["problems"][0]
    assert "evidence for what it actually describes" in problem
    assert "critic would reject" in problem


def test_a_brief_the_corpus_is_actually_about_still_passes(cfg, db):
    """The gate has to be a gate, not a wall. The seeded corpus IS about gearbox
    condition monitoring, and the vocabulary terms are in the signal text."""
    _seed(db)
    service, _ = _service(cfg, db, _reply(ready=True, briefs=[_brief()]))
    brief = service.reply([{"role": "user", "content": "offshore wind gearbox monitoring"}])["briefs"][0]
    assert brief["evidence"]["corroborated"] >= 3
    assert brief["runnable"] is True


def test_every_retrieved_signal_says_whether_it_supports_the_brief(cfg, db):
    """Summing the count away would leave "10 retrieved, 1 supported" with no way
    to see WHICH one, which is the only view that tells you what to say next."""
    _seed_adjacent(db)
    service, _ = _service(cfg, db, _reply(ready=True, briefs=[_brief(
        description=_SIGNAGE, vertical="public_sector",
        use_case="citizen_service_automation", technology="edge_computing")]), support={"supporting": [], "note": "same sector, different subject"})
    signals = service.reply(
        [{"role": "user", "content": "digital signage on municipal street screens"}]
    )["briefs"][0]["evidence"]["signals"]
    assert signals, "something was retrieved"
    assert all("corroborates" in s for s in signals)
    assert any(s["corroborates"] is None for s in signals), "the unsupported ones are marked"


def test_the_vertical_alone_cannot_corroborate_a_brief(cfg, db):
    """The axis that answers least. A corpus of French public-sector tenders
    corroborates the vertical of every French public-sector brief ever written,
    including the ones about things it has never heard of — §4.4.2's own negative
    example is "a vertical plus a slogan"."""
    _seed_adjacent(db)
    service, _ = _service(cfg, db, _reply())
    # SIG-A1 names a municipality and nothing else the triple asks for.
    signal = dict(db.query_one("SELECT * FROM signals WHERE id = 'SIG-A1'"))
    triple = ("public_sector", "citizen_service_automation", "edge_computing")
    # Enrichment considers all three axes; it is attaching to a space already
    # judged specific, so the vertical is a fair second reason there.
    assert service._get_enricher().corroborates(
        {"vertical": "public_sector", "use_case": "citizen_service_automation",
         "technology": "edge_computing"}, signal, {}) is not None
    # Scoping asks the stricter question, so the same signal supports nothing.
    assert service._corroboration(triple, [signal])[0] is None


def test_the_scoping_gate_reuses_the_rule_enrichment_already_states(cfg, db):
    """Two definitions of "independently supports" would drift apart, and the one
    in config/settings.yaml is the one with an owner."""
    _seed(db)
    service, _ = _service(cfg, db, _reply())
    signal = dict(db.query_one("SELECT * FROM signals WHERE id = 'SIG-1'"))
    reason = service._corroboration(("energy", "predictive_maintenance", "low_power_sensors"),
                                    [signal])[0]
    assert reason and "appears in the signal text" in reason


def test_matching_the_taxonomy_label_is_not_evidence_for_the_brief(cfg, db):
    """The failure that reached a user, as a test.

    The vocabularies are closed, so a proposal about advertising-funded municipal
    screens is filed under the nearest available job and technology. Tenders for
    private-5G video surveillance then corroborate `private_5g` perfectly while
    being no evidence at all for advertising screens. The gate reported four
    supporting signals, the button enabled, the run spent its calls, and the
    critic threw the candidate out: "SIG-... is about video surveillance, neither
    mentions public displays".

    So the model is asked about the SENTENCE, and its answer overrules the label
    match — here it endorses nothing, and the brief must not be runnable however
    well the vocabulary agreed.
    """
    _seed(db)
    service, llm = _service(cfg, db, _reply(ready=True, briefs=[_brief()]),
                            support={"supporting": [], "note": "all about gearboxes, not this"})
    out = service.reply([{"role": "user", "content": "offshore wind gearbox monitoring"}])
    brief = out["briefs"][0]
    assert llm.support_calls == 1, "asked on every proposed brief, not only when vocabulary fails"
    assert brief["evidence"]["corroborated"] == 0, "the label match was overruled"
    assert brief["runnable"] is False
    assert brief["hypothesis"] is True, "and the contributed-evidence route opens instead"


def test_the_support_call_is_told_the_brief_not_just_its_labels(cfg, db):
    """It cannot overrule a label match unless it can see what the label
    approximates."""
    _seed(db)
    service, llm = _service(cfg, db, _reply(ready=True, briefs=[_brief()]))
    service.reply([{"role": "user", "content": "offshore wind gearbox monitoring"}])
    system = next(sy for sy, _ in llm.seen if "MOCK_KIND=brief_support" in sy)
    assert "Acoustic and vibration condition monitoring" in system, "the sentence"
    assert "JUDGE AGAINST THE SENTENCE" in system


def test_the_model_can_rescue_a_brief_the_vocabulary_test_would_refuse(cfg, db):
    """The lexical test has poor recall: journalism and tenders do not write
    "SIEM and SOAR". Refusing on that alone trades one wrong answer for another,
    so where it comes up short the model is asked about the same evidence."""
    _seed_adjacent(db)
    supported = {"supporting": ["SIG-A1", "SIG-A2", "SIG-A3", "SIG-A5"],
                 "note": "French public-sector IT procurement"}
    service, llm = _service(cfg, db, _reply(ready=True, briefs=[_brief(
        description=_SIGNAGE, vertical="public_sector",
        use_case="citizen_service_automation", technology="edge_computing")]), support=supported)
    brief = service.reply(
        [{"role": "user", "content": "digital signage on municipal street screens"}]
    )["briefs"][0]
    assert llm.support_calls == 1, "asked once, about evidence that already retrieved"
    assert brief["evidence"]["support_method"] == "model"
    assert brief["evidence"]["corroborated"] >= 3
    assert brief["runnable"] is True


def test_a_failed_support_call_keeps_the_vocabulary_answer(cfg, db):
    """A provider outage must not silently turn every brief into a refusal — that
    would read as "the corpus does not support this" and be a lie about a
    different system."""
    _seed(db)

    class HalfBroken(Scripted):
        def complete_json(self, system, user, **kwargs):
            if "MOCK_KIND=brief_support" in system:
                from radar.llm import LLMError
                raise LLMError("upstream refused")
            return super().complete_json(system, user, **kwargs)

    llm = HalfBroken(_reply(ready=True, briefs=[_brief()]))
    service = ScopingService(cfg, db, embedder=_embedder(), llm=llm)
    brief = service.reply([{"role": "user", "content": "offshore wind gearbox monitoring"}])["briefs"][0]
    # This one clears on vocabulary anyway, so the outage changes nothing at all.
    assert brief["runnable"] is True
    assert brief["evidence"]["support_method"] == "vocabulary"


# ---------------------------------------------------------------------------
# The vocabularies stay closed (§3.3)
# ---------------------------------------------------------------------------

def test_what_the_person_said_is_mapped_onto_ids_rather_than_rejected(cfg, db):
    """Nobody should have to learn the taxonomy to use this screen. "banking" is
    a synonym the vocabulary already knows; making someone type
    `financial_services` is a validation error dressed up as a conversation."""
    _seed(db)
    service, _ = _service(cfg, db, _reply(understood={
        "vertical": "banking", "use_case": "predictive maintenance", "personas": ["CIO"]}))
    out = service.reply([{"role": "user", "content": "offshore wind gearbox monitoring"}])
    assert out["understood"]["vertical"] == "financial_services"
    assert out["understood"]["use_case"] == "predictive_maintenance"
    assert out["understood"]["personas"] == ["cio"]


def test_a_value_outside_the_vocabulary_is_dropped_and_named(cfg, db):
    """Carried through as free text it would fail validation at synthesis, three
    stages and several model calls later. Dropped silently, the screen would show
    a slot as filled that the run cannot use."""
    _seed(db)
    service, _ = _service(cfg, db, _reply(understood={"vertical": "underwater basket weaving"}))
    out = service.reply([{"role": "user", "content": "offshore wind gearbox monitoring"}])
    assert out["understood"]["vertical"] is None
    assert out["unresolved"]["vertical"] == "underwater basket weaving"


def test_a_brief_on_an_illegal_triple_cannot_be_run(cfg, db):
    """The triple is the space's identity (§4.4.5). One the taxonomy does not
    contain is not a space that could be persisted."""
    _seed(db)
    service, _ = _service(cfg, db, _reply(
        ready=True, briefs=[_brief(technology="telepathy")]))
    brief = service.reply([{"role": "user", "content": "offshore wind gearbox monitoring"}])["briefs"][0]
    assert brief["runnable"] is False
    assert any("controlled vocabulary" in problem for problem in brief["problems"])


def test_the_required_three_are_computed_rather_than_taken_from_the_model(cfg, db):
    """"I have everything I need" is what a model says when it wants to be
    helpful. What is missing is a lookup, so it is looked up."""
    _seed(db)
    service, _ = _service(cfg, db, {**_reply(understood={"vertical": "energy"}), "missing": []})
    out = service.reply([{"role": "user", "content": "offshore wind gearbox monitoring"}])
    assert out["missing"] == ["use_case", "technology"]


# ---------------------------------------------------------------------------
# DR-03, said before the run rather than after it
# ---------------------------------------------------------------------------

def test_a_brief_landing_on_an_existing_space_says_which_one(cfg, db):
    """Under DR-03 the run refreshes that space rather than creating one. That
    is legal and useful, and it is not what "generate" sounds like — so it is
    said while there is still a choice about it."""
    _seed(db)
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO opportunity_spaces (id, vertical, use_case, technology, statement,
                   domains, personas, geographies, state, state_reason, state_changed_at, why_hot,
                   first_seen, last_refresh, pipeline_version)
               VALUES ('OS900','energy','predictive_maintenance','low_power_sensors',
                       'Existing space.','[]','[]','[]','active','seeded','2026-08-01','[]',
                       '2026-08-01','2026-08-01','test')""")
    service, _ = _service(cfg, db, _reply(ready=True, briefs=[_brief()]))
    brief = service.reply([{"role": "user", "content": "offshore wind gearbox monitoring"}])["briefs"][0]
    assert brief["existing"]["id"] == "OS900"
    # Still runnable: refreshing an existing space with new evidence is a real
    # outcome, and refusing it would be the screen deciding for the user.
    assert brief["runnable"] is True


def test_spaces_built_on_the_retrieved_evidence_reach_the_prompt(cfg, db):
    """The assistant can only warn about an occupied cell if it is told which
    cells the evidence in front of it already carries."""
    _seed(db)
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO opportunity_spaces (id, vertical, use_case, technology, statement,
                   domains, personas, geographies, state, state_reason, state_changed_at, why_hot,
                   first_seen, last_refresh, pipeline_version)
               VALUES ('OS901','energy','predictive_maintenance','digital_twin','Turbine twin.',
                       '[]','[]','[]','active','seeded','2026-08-01','[]','2026-08-01',
                       '2026-08-01','test')""")
        cur.execute("INSERT INTO opportunity_signals (opportunity_id, signal_id, attached_at, "
                    "refresh_id) VALUES ('OS901','SIG-1','2026-08-01','R-seed')")
    service, llm = _service(cfg, db, _reply())
    out = service.reply([{"role": "user", "content": "offshore wind gearbox condition monitoring"}])
    assert any("OS901" in cell for cell in out["occupied"])
    assert "OS901" in llm.seen[-1][1]


# ---------------------------------------------------------------------------
# The prompt carries what the assistant needs to be knowledgeable
# ---------------------------------------------------------------------------

def test_the_system_prompt_carries_the_vocabularies_and_the_strategy(cfg, db):
    """It is composing the input to the synthesis prompt, so it needs what that
    prompt needs — otherwise it interviews towards values synthesis will reject."""
    system = prompts.scoping_system_prompt(cfg, 40, 600, 3)
    assert "predictive_maintenance" in system, "use cases"
    assert "private_5g" in system, "technologies"
    assert "financial_services" in system, "verticals"
    assert cfg.strategy["plan"] in system, "the strategic frame"
    for slot in prompts.SCOPING_SLOTS:
        assert slot["ask"] in system, f"the question for {slot['id']}"


def test_the_user_prompt_puts_the_corpus_in_front_of_the_assistant(cfg, db):
    """A question that could have been asked without the corpus is a wasted turn,
    and it can only be asked WITH the corpus if the corpus is in the prompt."""
    _seed(db)
    service, llm = _service(cfg, db, _reply())
    service.reply([{"role": "user", "content": "offshore wind gearbox condition monitoring"}])
    user = llm.seen[-1][1]
    assert "offshore wind condition monitoring" in user, "the theme-cluster map"
    assert "SIG-2" in user and "buying_signal" in user, "the retrieved evidence, typed"
    assert "Publisher" in user, "attribution, so it can cite rather than assert"


def test_the_transcript_reaches_the_prompt_labelled_by_speaker(cfg, db):
    _seed(db)
    service, llm = _service(cfg, db, _reply())
    service.reply([
        {"role": "user", "content": "offshore wind gearbox monitoring"},
        {"role": "assistant", "content": "Which countries?"},
        {"role": "user", "content": "Germany and the Netherlands"},
    ])
    user = llm.seen[-1][1]
    assert "PERSON: Germany and the Netherlands" in user
    assert "YOU: Which countries?" in user


def test_a_conversation_ending_on_the_assistant_is_refused(cfg, db):
    """There is nothing to answer. Answering anyway means the assistant talking
    to itself and spending a model call to do it."""
    _seed(db)
    service, _ = _service(cfg, db, _reply())
    with pytest.raises(ValueError):
        service.reply([{"role": "assistant", "content": "Which industry?"}])


def test_a_provider_failure_is_reported_as_one(cfg, db):
    """502 rather than 500 downstream: the radar is fine, the provider is not,
    and the difference decides whether retrying is worth anything."""
    _seed(db)

    class Broken(LLMClient):
        def __init__(self):
            super().__init__(provider="mock")

        def complete_json(self, system, user, **kwargs):
            from radar.llm import LLMError
            raise LLMError("upstream refused")

    service = ScopingService(cfg, db, embedder=_embedder(), llm=Broken())
    with pytest.raises(ScopingError):
        service.reply([{"role": "user", "content": "offshore wind gearbox monitoring"}])


# ---------------------------------------------------------------------------
# One conversation, several briefs, one run
# ---------------------------------------------------------------------------

def test_several_briefs_are_one_run_with_one_space_requested_each(cfg, db):
    """Synthesis holds the only write lock on the taxonomy triple, so three
    separate requests would collect two 409s and a queue somebody has to watch."""
    _seed(db)
    job = GenerationService(cfg, db, embedder=_embedder()).start_from_briefs([
        _BRIEF,
        "Incident reporting and operational resilience duties for offshore wind operators in "
        "German and Dutch waters, delivered as a monitored service.",
    ])
    assert job.kind == "brief"
    assert job.requested == 2
    assert len(job.briefs) == 2


def test_the_payload_names_one_brief_only_when_there_is_one(cfg, db):
    """A run answering three has no single brief to name, and naming the first
    would read as if the other two had not been asked for."""
    _seed(db)
    service = GenerationService(cfg, db, embedder=_embedder())
    one = service.start_from_briefs([_BRIEF]).as_dict()
    assert one["brief"] == _BRIEF and one["briefs"] == [_BRIEF]


def test_the_same_brief_twice_is_one_pass(cfg, db):
    """They would retrieve the same evidence and land on the same triple, and the
    second would be reported as a DR-03 refresh of the space the first had just
    created — a costed model call spent to produce a misleading number."""
    _seed(db)
    job = GenerationService(cfg, db, embedder=_embedder()).start_from_briefs([_BRIEF, _BRIEF])
    assert job.briefs == [_BRIEF]
    assert job.requested == 1


def test_the_number_of_briefs_in_one_run_is_bounded(cfg, db):
    _seed(db)
    service = GenerationService(cfg, db, embedder=_embedder())
    with pytest.raises(ValueError, match="at most"):
        service.start_from_briefs([f"{_BRIEF} Variant {i}." for i in range(MAX_BRIEFS_PER_RUN + 1)])


def test_an_empty_list_is_refused_rather_than_run_as_an_empty_job(cfg, db):
    _seed(db)
    with pytest.raises(ValueError, match="No brief"):
        GenerationService(cfg, db, embedder=_embedder()).start_from_briefs([])


def test_a_space_one_brief_created_is_not_reported_as_another_refreshing_it(cfg, db):
    """Each brief runs with its own stats object, so a second brief landing on a
    triple the first created has no way to know that row is seconds old.
    Unadjusted, one space arrives as "1 created and 1 refreshed" and the
    shortfall message offers a DR-03 explanation for an event that never
    happened."""
    first = SynthesisStats(created_ids=["OS001"], accepted=1, raw_candidates=2)
    second = SynthesisStats(updated_ids=["OS001"], accepted=1, raw_candidates=3)
    combined = SynthesisStats().absorb(first).absorb(second)
    assert combined.created_ids == ["OS001"]
    assert combined.updated_ids == []
    assert combined.raw_candidates == 5, "counters sum"
    assert combined.rounds == 1, "two briefs are not two rounds"
