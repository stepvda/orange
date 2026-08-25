"""Constrained, on-demand generation (the Generate screen).

The screen makes one promise beyond what the cadence refresh already does: when
filters are set, the run stays inside them. These tests are about the ways that
promise can quietly fail — a constraint that only lives in the prompt, a count
that counts refreshed spaces as new ones, a horizon presented as chosen when
§4.8 derives it — and about the rule that what was NOT produced gets reported
(§4.12) rather than showing up as a silent shortfall.
"""

from __future__ import annotations

import datetime as dt
import functools
import json

import pytest

from radar.config import get_config
from radar.db import Database, js
from radar.generation import MAX_PER_RUN, GenerationJob, GenerationService
from radar.embeddings import Embedder
from radar.llm import LLMClient, LLMError
from radar.readmodel import ReadModel, refresh_kind, topic_for_list
from radar.pipeline.synthesis import (GenerationConstraints, Candidate, SynthesisProgress,
                                      SynthesisStats, Synthesiser)

REF = dt.date(2026, 8, 17)


@pytest.fixture(autouse=True)
def no_provider_calls(monkeypatch):
    """Never let a test reach a real model.

    `GenerationService` builds its own `LLMClient` inside the background thread,
    the way the API does, so unlike the rest of the suite there is no client to
    inject at the call site. Without this the tests below run against whatever
    `RADAR_LLM_PROVIDER` and key happen to be in `.env` — which on a developer
    machine is a real provider, and a test suite that quietly spends money is a
    test suite nobody can run in CI.
    """
    monkeypatch.setenv("RADAR_LLM_PROVIDER", "mock")


@pytest.fixture(scope="module")
def cfg():
    return get_config()


@pytest.fixture()
def db(tmp_path):
    database = Database(tmp_path / "t.db")
    database.init_schema()
    return database


def make(**overrides) -> Candidate:
    base = dict(
        vertical="manufacturing",
        use_case="predictive_maintenance",
        technology="machine_learning",
        statement="Predictive maintenance for rotating equipment in chemical process plants using vibration ML.",
        domains=["ox_smart_industries"],
        why_hot=[{"claim": "Three deployments were published this quarter.", "signals": ["SIG-1"]}],
    )
    base.update(overrides)
    return Candidate(**base)


def synth_with(cfg, db, **constraint_kwargs) -> Synthesiser:
    return Synthesiser(cfg, db, LLMClient(provider="mock"),
                       constraints=GenerationConstraints(**constraint_kwargs))


# ---------------------------------------------------------------------------
# The constraint is enforced by the validator, not promised by the prompt
# ---------------------------------------------------------------------------

def test_a_candidate_outside_the_requested_vertical_is_dropped(cfg, db):
    """§4.4.4's posture applied to the operator's filters: the prompt asks, the
    validator decides. A model that ignores the scope must not be able to widen
    it."""
    synth = synth_with(cfg, db, verticals=("manufacturing",))
    stats = SynthesisStats()
    assert synth._validate(make(vertical="energy"), {"SIG-1"}, stats) is False
    assert stats.failed_constraints == 1
    assert "outside the requested" in stats.rejections[0]["reason"]


def test_the_in_scope_candidate_still_passes(cfg, db):
    synth = synth_with(cfg, db, verticals=("manufacturing",))
    stats = SynthesisStats()
    assert synth._validate(make(), {"SIG-1"}, stats) is True
    assert stats.failed_constraints == 0


def test_a_constraint_drop_is_not_counted_as_a_vocabulary_failure(cfg, db):
    """Two different messages. "The model invented a taxonomy value" is a
    quality problem; "the model answered a wider question than it was asked" is
    a scoping one, and the screen reports them separately."""
    synth = synth_with(cfg, db, verticals=("manufacturing",))
    stats = SynthesisStats()
    synth._validate(make(vertical="energy"), {"SIG-1"}, stats)
    assert (stats.failed_vocabulary, stats.failed_specificity) == (0, 0)


def test_domain_scope_requires_an_overlap_not_an_exact_match(cfg, db):
    synth = synth_with(cfg, db, domains=("ox_smart_industries",))
    stats = SynthesisStats()
    assert synth._validate(make(domains=["ox_smart_industries", "cloud"]), {"SIG-1"}, stats) is True
    assert synth._validate(make(domains=["cybersecurity"]), {"SIG-1"}, stats) is False


def test_a_space_with_no_geography_is_global_not_out_of_scope(cfg, db):
    """The read model's own rule (`_matches`): a topic carrying no geography is
    global rather than excluded. Generation has to use the SAME rule, or the
    "spaces that already match" count on the screen would describe a different
    set from the one the run produces."""
    synth = synth_with(cfg, db, geographies=("FR", "DE"))
    stats = SynthesisStats()
    assert synth._validate(make(geographies=[]), {"SIG-1"}, stats) is True
    assert synth._validate(make(geographies=["FR"]), {"SIG-1"}, stats) is True
    assert synth._validate(make(geographies=["US"]), {"SIG-1"}, stats) is False


def test_the_domain_fallback_runs_before_the_scope_check(cfg, db):
    """A candidate with no domain has one derived from its use case. Checking
    the scope first would reject it for a field the pipeline was about to fill
    in."""
    derived = list(cfg.use_cases["predictive_maintenance"].get("domains") or [])
    assert derived, "fixture assumes this use case declares a domain"
    synth = synth_with(cfg, db, domains=tuple(derived))
    stats = SynthesisStats()
    assert synth._validate(make(domains=[]), {"SIG-1"}, stats) is True


def test_no_constraints_changes_nothing(cfg, db):
    """The unconstrained path is the pipeline's existing behaviour, and the
    Generate screen with empty filters must land on exactly it."""
    synth = Synthesiser(cfg, db, LLMClient(provider="mock"))
    assert not synth.constraints
    stats = SynthesisStats()
    assert synth._validate(make(vertical="energy", geographies=["US"]), {"SIG-1"}, stats) is True


# ---------------------------------------------------------------------------
# Coverage targets and cluster selection honour the scope
# ---------------------------------------------------------------------------

def test_coverage_targets_are_confined_to_the_requested_vertical(cfg, db):
    """§4.4.3 steers generation at grid cells with evidence and no candidate. An
    unfiltered target list would steer a Manufacturing run at Energy cells."""
    targets = synth_with(cfg, db, verticals=("manufacturing",))._coverage_targets()
    assert targets, "the empty database should leave every cell uncovered"
    assert {t["vertical"] for t in targets} == {"manufacturing"}


def test_cluster_selection_filters_on_the_geography_of_the_evidence(cfg, db):
    """§4.4.4 defence 1: the evidence block is the only factual material. Asking
    for Germany while handing the model French tenders invites the fabrication
    the whole design exists to prevent, so the filter applies to which clusters
    are read, not only to what the prompt says."""
    _seed_clusters(db)
    synth = synth_with(cfg, db, geographies=("DE",))
    assert synth._cluster_ids(None, set()) == [2]
    assert set(Synthesiser(cfg, db, LLMClient(provider="mock"))._cluster_ids(None, set())) == {1, 2, 3}


def test_a_horizon_ranks_clusters_rather_than_excluding_them(cfg, db):
    """§4.8 derives the horizon from the whole evidence base AFTER enrichment
    widens it, so a cluster with no procurement signal is a poor bet for NOW,
    not an impossible one. It sorts last; it is not dropped."""
    _seed_clusters(db)
    ids = synth_with(cfg, db, horizons=("now",))._cluster_ids(None, set())
    # Cluster 3 is the SMALLEST, so ranking it first proves the horizon beat the
    # default largest-first ordering rather than coinciding with it.
    assert ids[0] == 3, "the cluster carrying the buying signal ranks first"
    assert set(ids) == {1, 2, 3}


def test_geography_and_horizon_compose(cfg, db):
    """Both constraints at once. The affinity subquery sits in the SELECT list
    and the geography test in the WHERE, so their placeholders bind in a
    different order from the order they were built in — a mistake SQLite would
    accept silently and answer wrongly."""
    _seed_clusters(db)
    synth = synth_with(cfg, db, geographies=("DE", "PL"), horizons=("now",))
    # DE carries regulation and PL a buying signal, so both survive the WHERE
    # and the NOW affinity puts the Polish tenders first.
    assert synth._cluster_ids(None, set()) == [3, 2]


def test_consumed_clusters_are_not_re_read_on_the_next_round(cfg, db):
    _seed_clusters(db)
    synth = Synthesiser(cfg, db, LLMClient(provider="mock"))
    assert synth._cluster_ids(None, {1, 3}) == [2]


def test_the_cluster_budget_scales_with_the_request(cfg, db):
    """A five-space request must not read the whole corpus: that is several
    hundred model calls to keep five, and NFR-10 makes inference cost a reported
    quantity rather than an accident."""
    _seed_clusters(db, extra=40)
    synth = Synthesiser(cfg, db, LLMClient(provider="mock"))
    assert len(synth._cluster_ids(None, set(), target_new=2)) == 8
    assert len(synth._cluster_ids(None, set(), target_new=None)) == 43


# ---------------------------------------------------------------------------
# "It keeps giving me spaces that already exist"
#
# §4.4.5 makes the taxonomy triple the canonical identity, so a candidate on an
# occupied cell updates the space that owns it (DR-03) and creates nothing. That
# is right on a refresh and is not an answer to "find me five more", so the run
# has to notice, say so, and ask again.
# ---------------------------------------------------------------------------

def test_the_prompt_names_the_cells_that_are_already_taken(cfg, db):
    """The model cannot avoid a collision it was never told about. Stated as
    cells rather than statements, because the cell is what identity is defined
    on."""
    from radar.pipeline import prompts
    text = prompts.synthesis_user_prompt(
        {"cluster_id": 1, "label": "x", "keyphrases": "[]", "signals": []},
        avoid=["manufacturing x predictive_maintenance x machine_learning"],
    )
    assert "ALREADY IN THE RADAR" in text
    assert "manufacturing x predictive_maintenance x machine_learning" in text
    assert "return an empty list" in text, "an exhausted cluster must still be allowed to say nothing"


def test_the_up_front_avoid_list_is_narrowed_by_the_request(cfg, db):
    """With a vertical selected the in-scope list is short and every entry is a
    cell the model is likely to propose. Unconstrained it would be the whole
    radar, which costs more input than the evidence it protects — so nothing is
    sent and the retry does the work instead."""
    _space(db, "OS800", index=0)
    _space(db, "OS801", index=1)
    taken = Synthesiser(cfg, db, LLMClient(provider="mock"))._live_triples()

    unconstrained = Synthesiser(cfg, db, LLMClient(provider="mock"))
    assert unconstrained._scoped_taken(taken) == []

    scoped = synth_with(cfg, db, verticals=("manufacturing",))
    assert len(scoped._scoped_taken(taken)) == 2
    assert all(cell.startswith("manufacturing x") for cell in scoped._scoped_taken(taken))

    elsewhere = synth_with(cfg, db, verticals=("energy",))
    assert elsewhere._scoped_taken(taken) == []


def test_a_candidate_on_an_occupied_cell_does_not_satisfy_the_request(cfg, db):
    """The bug behind the complaint: the round stopped once enough CANDIDATES
    had been accepted, so three that all landed on occupied cells satisfied the
    count, ended the round and created nothing."""
    _seed_clusters(db)          # the cited SIG-1 has to exist for the attachment
    _space(db, "OS800", index=0)
    synth = Synthesiser(cfg, db, LLMClient(provider="mock"))
    taken = synth._live_triples()
    assert ("manufacturing", "predictive_maintenance", "machine_learning") in taken
    stats = SynthesisStats()
    # The cell is occupied, so persisting a candidate on it updates rather than
    # creates — which is what the counter the loop reads has to reflect.
    synth._persist([make()], "R-1", stats)
    assert stats.created_ids == []
    assert stats.updated_ids == ["OS800"]


def test_the_retry_is_bounded_so_a_covered_corpus_cannot_multiply_the_bill(cfg, db):
    """NFR-10 makes inference cost a reported quantity. A corpus whose every
    theme is already covered would otherwise spend the per-cluster retry
    allowance on each of a hundred clusters to discover, correctly, that there
    is nothing new."""
    synth = Synthesiser(cfg, db, LLMClient(provider="mock"))
    assert synth.DUPLICATE_RETRIES == 2
    assert synth.AVOID_LIMIT == 40


# ---------------------------------------------------------------------------
# DR-03: created and updated are different events
# ---------------------------------------------------------------------------

def test_persist_separates_spaces_it_created_from_ones_it_refreshed(cfg, db):
    """"Five more spaces" is a request for five NEW rows. A run that lands on
    five existing taxonomy triples refreshes them (DR-03) and has created
    nothing, and the screen must not report that as success."""
    _seed_clusters(db)
    synth = Synthesiser(cfg, db, LLMClient(provider="mock"))
    first = SynthesisStats()
    synth._persist([make()], "R-1", first)
    assert len(first.created_ids) == 1 and first.updated_ids == []

    second = SynthesisStats()
    synth._persist([make(statement="A revised statement about the very same taxonomy triple here.")],
                   "R-2", second)
    assert second.created_ids == []
    assert second.updated_ids == first.created_ids


def test_two_survivors_on_one_triple_are_one_created_space_not_two_events(cfg, db):
    """Deduplication is by statement embedding, not by taxonomy triple, so a
    batch can carry two survivors that land on the same cell: the first INSERTs
    and the second UPDATEs the row the first just made. Counting that as a
    refresh would report one space as "1 created · 1 refreshed" and give the
    shortfall message a DR-03 explanation that never happened."""
    _seed_clusters(db)
    synth = Synthesiser(cfg, db, LLMClient(provider="mock"))
    stats = SynthesisStats()
    synth._persist(
        [make(), make(statement="A different sentence entirely about the very same taxonomy cell.")],
        "R-1", stats,
    )
    assert len(stats.created_ids) == 1
    assert stats.updated_ids == []


def test_the_absolute_target_loop_still_re_reads_its_clusters(cfg, db, monkeypatch):
    """Cluster rotation belongs to `target_new` only. `radar refresh
    --target-topics N` deliberately re-reads the same clusters each round and
    relies on the coverage targets having moved (§4.4.3); excluding what round 1
    consumed would hand round 2 an empty list and end the loop after one pass."""
    _seed_clusters(db)
    synth = Synthesiser(cfg, db, LLMClient(provider="mock"))
    seen: list[set] = []

    def spy(*args, **kwargs):
        seen.append(set(kwargs.get("exclude_cluster_ids") or ()))
        stats = SynthesisStats()
        stats.processed_cluster_ids = [1, 2, 3]
        stats.accepted = 1          # keep the loop going to the round cap
        return stats

    monkeypatch.setattr(synth, "_run_once", spy)
    synth.run("R-1", target_topics=99, max_rounds=3)
    assert len(seen) == 3, "the loop should reach its round cap"
    assert all(excluded == set() for excluded in seen), "no round may be starved of clusters"


def test_the_new_space_target_does_rotate_its_clusters(cfg, db, monkeypatch):
    """The mirror of the test above: each round of a `target_new` run reads
    evidence the last one did not, so a second round explores rather than
    re-reading the same fourteen signals."""
    _seed_clusters(db)
    synth = Synthesiser(cfg, db, LLMClient(provider="mock"))
    seen: list[set] = []

    def spy(*args, **kwargs):
        seen.append(set(kwargs.get("exclude_cluster_ids") or ()))
        stats = SynthesisStats()
        stats.processed_cluster_ids = [len(seen)]
        return stats

    monkeypatch.setattr(synth, "_run_once", spy)
    synth.run("R-1", target_new=99, max_rounds=3)
    assert seen == [set(), {1}, {1, 2}]


# ---------------------------------------------------------------------------
# One space from a written description
#
# The whole risk of this path is in one sentence: a model handed a plausible
# description and a pile of documents will assert the description and cite the
# documents. §4.4.4 defence 1 is what stops that, and these tests are about
# keeping the brief on the request side of that line.
# ---------------------------------------------------------------------------

def test_a_brief_retrieves_evidence_rather_than_becoming_it(cfg, db):
    """The description is embedded and used to RETRIEVE. What comes back is the
    evidence block; the sentence itself is never a fact."""
    _seed_clusters(db, embed=True)
    synth = Synthesiser(cfg, db, LLMClient(provider="mock"))
    payload = synth.brief_payload("German regulation item", min_signals=1)
    assert payload["signals"], "the seeded corpus should have something close"
    assert all(sig["id"].startswith("SIG-") for sig in payload["signals"])
    assert "embedding" not in payload["signals"][0], "the vector is not evidence"


def test_a_brief_with_nothing_close_returns_no_evidence_at_all(cfg, db):
    """§4.1: an empty answer is a valid one. The alternative — handing the model
    the three least-unrelated items in the corpus — is how a space gets built on
    evidence that is not about it."""
    _seed_clusters(db, embed=True)
    synth = Synthesiser(cfg, db, LLMClient(provider="mock"))
    assert synth.brief_payload("marsupial dentistry in low earth orbit")["signals"] == []


def test_a_brief_needs_at_least_three_signals_to_stand_on(cfg, db):
    """A candidate resting on one loosely-related item is the thin topic the
    critic exists to catch, and catching it before the model call costs
    nothing."""
    _seed_clusters(db, embed=True)
    synth = Synthesiser(cfg, db, LLMClient(provider="mock"))
    # The seed carries one signal per theme, so nothing can clear a floor of 3.
    assert synth.brief_payload("German regulation item", min_signals=3)["signals"] == []


def test_a_run_from_a_brief_with_no_evidence_creates_nothing_and_says_why(cfg, db):
    _seed_clusters(db, embed=True)
    service = GenerationService(cfg, db)
    job = _await(service.start_from_brief(
        "Acoustic gearbox monitoring for offshore wind operators in the North Sea."))
    assert job.status == "done"
    assert job.created_ids == []
    assert any("corpus carries no evidence" in e["message"] or "close enough" in e["message"]
               for e in job.log)


def test_a_brief_too_short_to_retrieve_with_is_refused(cfg, db):
    service = GenerationService(cfg, db)
    with pytest.raises(ValueError, match="at least"):
        service.start_from_brief("predictive maintenance")


def test_a_brief_run_is_marked_as_one(cfg, db):
    """The two paths differ in what steers the model, not in what validates it —
    but the report has to say which was used, or a space nobody can trace back
    to a request looks like it came from the evidence sweep."""
    _seed_clusters(db, embed=True)
    service = GenerationService(cfg, db)
    job = _await(service.start_from_brief(
        "Private 5G energy optimisation for high-consumption presses at German automotive plants."))
    payload = job.as_dict()
    assert payload["kind"] == "brief"
    assert payload["brief"].startswith("Private 5G")
    assert payload["requested"] == 1
    assert payload["unit_label"] == "generation pass"


def test_the_brief_reaches_the_prompt_as_a_request_not_as_a_fact(cfg, db):
    """The wording matters more than its presence: the block has to demote the
    sentence explicitly, because the model's default reading of a sentence
    beside evidence is that the evidence supports it."""
    from radar.pipeline import prompts
    text = prompts.synthesis_user_prompt(
        {"cluster_id": "brief", "label": "written brief", "keyphrases": "[]", "signals": []},
        brief="Acoustic gearbox monitoring for offshore wind operators.",
    )
    assert "REQUEST, not evidence" in text
    assert "Acoustic gearbox monitoring" in text
    assert "AT MOST ONE candidate" in text


# ---------------------------------------------------------------------------
# The service: request validation and the single-run rule
# ---------------------------------------------------------------------------

def test_an_unknown_vertical_is_refused_before_the_run_starts(cfg, db):
    """§3.3's closed vocabularies apply to the REQUEST. Without this, a typo
    produces a run that reads the corpus, rejects everything for being outside a
    vertical that does not exist, and reports an evidence shortfall."""
    service = GenerationService(cfg, db)
    with pytest.raises(ValueError, match="Unknown vertical"):
        service.start(3, GenerationConstraints(verticals=("manufakturing",)))


def test_an_unknown_horizon_is_refused(cfg, db):
    service = GenerationService(cfg, db)
    with pytest.raises(ValueError, match="Unknown horizon"):
        service.start(3, GenerationConstraints(horizons=("soon",)))


def test_the_count_is_bounded(cfg, db):
    service = GenerationService(cfg, db)
    with pytest.raises(ValueError):
        service.start(0, GenerationConstraints())
    with pytest.raises(ValueError):
        service.start(MAX_PER_RUN + 1, GenerationConstraints())


def test_a_deployment_without_the_encoder_says_so_instead_of_failing_a_run(cfg, db, monkeypatch):
    """The Azure serving package ships without sentence-transformers on purpose
    (it pulls torch). The read path never needed it; generation does, both to
    deduplicate candidates and to retrieve evidence for a written brief against
    the stored 384-dimensional vectors. Accepting the request and failing at the
    deduplication step with an import error is the wrong way to find out."""
    import importlib.util
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec",
                        lambda name, *a, **k: None if name == "sentence_transformers"
                        else real(name, *a, **k))
    _seed_clusters(db)
    service = GenerationService(cfg, db)
    readiness = service.readiness()
    assert readiness["ready"] is False
    assert "cannot generate" in readiness["reason"]
    assert readiness["clusters"] == 3, "the corpus is fine; the encoder is what is missing"
    with pytest.raises(ValueError, match="cannot generate"):
        service.start(1, GenerationConstraints())
    with pytest.raises(ValueError, match="cannot generate"):
        service.start_from_brief("Acoustic gearbox monitoring for offshore wind operators.")


def test_a_run_without_clusters_reports_why_rather_than_returning_zero(cfg, db):
    """An empty result and an impossible request look identical on screen. They
    are opposite messages, so the second one is named."""
    readiness = GenerationService(cfg, db).readiness()
    assert readiness["ready"] is False
    assert "refresh" in readiness["reason"].lower()


def test_readiness_reports_ready_once_clusters_exist(cfg, db):
    _seed_clusters(db)
    readiness = GenerationService(cfg, db).readiness()
    assert readiness["ready"] is True
    assert readiness["clusters"] == 3


def test_a_finished_run_records_itself_in_the_refresh_log(cfg, db):
    """NFR-04: every score and signal attachment carries a refresh id, so a path
    that writes them has to open one — and it says `generation`, because unlike
    a cadence run it collected nothing."""
    _seed_clusters(db)
    service = GenerationService(cfg, db)
    job = service.start(1, GenerationConstraints())
    _await(job)
    row = db.query_one("SELECT * FROM refreshes WHERE id = ?", (job.id,))
    assert row is not None and row["finished_at"]
    assert json.loads(row["stats"])["kind"] == "generation"


def test_a_generation_run_does_not_become_the_freshness_date(cfg, db):
    """AC-02's "refreshed <date>" is a claim about when EVIDENCE was last
    collected. A generation run rearranges the corpus it was given and collects
    nothing, so stamping today over a corpus last collected six weeks ago would
    make the radar look fresh for having rewritten its own topic table."""
    _seed_clusters(db)
    with db.cursor() as cur:
        cur.execute("INSERT INTO refreshes (id, started_at, reference_date, is_replay, "
                    "pipeline_version, weight_set) VALUES ('R-old','2026-07-01T00:00:00',"
                    "'2026-07-01',0,'0.1.0','w-test')")
    _await(GenerationService(cfg, db).start(1, GenerationConstraints()))

    latest = db.query_one("SELECT id FROM refreshes ORDER BY started_at DESC LIMIT 1")
    assert latest["id"].startswith("G-"), "the generation row is written and is the newest"
    assert ReadModel(cfg, db).view("strategist")["last_refresh"]["started_at"].startswith("2026-07-01")


def test_the_refresh_log_still_lists_generation_runs_but_labels_them(cfg, db):
    """Hiding a write from the log would be the wrong kind of tidy."""
    assert refresh_kind("G-20260820-120000-abcd") == "generation"
    assert refresh_kind("R-20260820-120000-abcd") == "cadence"


def test_a_space_created_in_one_round_is_not_refreshed_in_the_next(cfg, db, monkeypatch):
    """`_persist` guards this within a round. Across rounds the same space can be
    created in round 1 and re-hit in round 2, and reporting it as both created
    and DR-03-refreshed is the same mis-count one level up."""
    _seed_clusters(db)
    synth = Synthesiser(cfg, db, LLMClient(provider="mock"))
    rounds = iter([(["OS900"], []), ([], ["OS900"])])

    def spy(*args, **kwargs):
        created, updated = next(rounds)
        stats = SynthesisStats()
        stats.processed_cluster_ids = [len(created) + len(updated)]
        stats.created_ids, stats.updated_ids = list(created), list(updated)
        return stats

    monkeypatch.setattr(synth, "_run_once", spy)
    overall = synth.run("R-1", target_new=2, max_rounds=2)
    assert overall.created_ids == ["OS900"]
    assert overall.updated_ids == []


def test_a_padded_brief_is_measured_after_normalisation(cfg, db):
    """The browser's character counter, the request schema and the service all
    have to agree about how long a brief is, or a user types something the
    counter accepts and the server rejects."""
    _seed_clusters(db, embed=True)
    padded = "  Acoustic   gearbox   monitoring   for   offshore   wind   operators.   "
    job = _await(GenerationService(cfg, db).start_from_brief(padded))
    assert job.briefs == ["Acoustic gearbox monitoring for offshore wind operators."]
    assert job.as_dict()["brief"] == "Acoustic gearbox monitoring for offshore wind operators."


def test_two_runs_cannot_proceed_at_once(cfg, db):
    _seed_clusters(db)
    service = GenerationService(cfg, db)
    job = service.start(1, GenerationConstraints())
    try:
        with pytest.raises(RuntimeError, match="already in flight"):
            service.start(1, GenerationConstraints())
    finally:
        _await(job)


def test_the_run_says_which_calls_failed_and_stops_calling_it_evidence(cfg, db):
    """The failure that made generation look broken for a day.

    Synthesis treats a failed model call like a cluster with nothing to say: it
    logs and returns no candidates. Right for one flaky call, catastrophic for a
    provider that cannot be reached — the run reads every cluster, creates
    nothing, and concludes "the evidence in scope did not support more", which
    is an evidence verdict from a run that never reached the model. On the day
    this was written the cause was a wedged DNS resolver, and the screen blamed
    the corpus for it.

    Unit-level, because the service builds its client inside its own thread.
    """
    from radar.pipeline.synthesis import Synthesiser as _S
    service = GenerationService(cfg, db)
    job = GenerationJob(id="G-x", requested=3, constraints=GenerationConstraints())
    synth = _S(cfg, db, LLMClient(provider="mock"))
    synth.llm_failures, synth.llm_successes = 7, 0
    synth.last_llm_error = "APIConnectionError: Connection error."
    service._report_provider(job, synth)
    said = " ".join(e["message"] for e in job.log)
    assert "EVERY model call failed" in said
    assert "never reached the model" in said
    assert "Connection error" in said

    stats = SynthesisStats(raw_candidates=0)
    service._report_shortfall(job, stats)
    closing = job.log[-1]["message"]
    assert "says nothing about the evidence" in closing
    assert "did not support more" not in closing, "no evidence verdict from a run that never ran"


def test_a_partial_provider_failure_is_a_floor_not_a_verdict(cfg, db):
    service = GenerationService(cfg, db)
    job = GenerationJob(id="G-y", requested=5, constraints=GenerationConstraints())
    from radar.pipeline.synthesis import Synthesiser as _S
    synth = _S(cfg, db, LLMClient(provider="mock"))
    synth.llm_failures, synth.llm_successes = 3, 9
    synth.last_llm_error = "APITimeoutError: timed out"
    service._report_provider(job, synth)
    said = job.log[-1]["message"]
    assert "3 of 12 model calls failed" in said
    assert "floor rather than a verdict" in said


def test_a_shortfall_is_explained_rather_than_left_as_a_number(cfg, db):
    """§4.12: what was not produced is logged, never silently dropped. The mock
    provider emits no candidates, which is exactly the "asked for three, got
    none" case the screen has to be able to explain."""
    _seed_clusters(db)
    service = GenerationService(cfg, db)
    job = _await(service.start(3, GenerationConstraints()))
    assert job.status == "done"
    assert job.created_ids == []
    assert any("Asked for 3, created 0" in entry["message"] for entry in job.log)


def test_the_payload_names_every_stage_and_which_ones_finished(cfg, db):
    _seed_clusters(db)
    service = GenerationService(cfg, db)
    job = _await(service.start(1, GenerationConstraints(verticals=("manufacturing",))))
    payload = job.as_dict()
    assert [s["id"] for s in payload["stages"]][0] == "synthesise"
    assert payload["constrained"] is True
    assert payload["constraints"]["verticals"] == ["manufacturing"]


# ---------------------------------------------------------------------------
# The progress bar has to be true as well as moving
# ---------------------------------------------------------------------------

def _job(requested: int = 4) -> GenerationJob:
    return GenerationJob(id="G-test", requested=requested, constraints=GenerationConstraints())


def test_progress_starts_at_nothing(cfg, db):
    assert _job().progress == 0.0


def test_reading_evidence_moves_the_bar_without_filling_it(cfg, db):
    """A run that has produced nothing yet must not read as hung — but reading
    every cluster is not the same as producing anything, so evidence alone can
    never fill the synthesis segment."""
    job = _job()
    job.observe(SynthesisProgress(round=1, units_total=10, units_done=1, created=()))
    early = job.progress
    job.observe(SynthesisProgress(round=1, units_total=10, units_done=10, created=()))
    assert 0 < early < job.progress < 0.72


def test_a_created_space_outranks_the_evidence_reading(cfg, db):
    job = _job(requested=2)
    job.observe(SynthesisProgress(round=1, units_total=10, units_done=1, created=("OS1",)))
    assert job.progress > 0.72 * 0.4


def test_the_count_never_goes_backwards_across_a_round(cfg, db):
    """Ticks carry the CUMULATIVE list. A round-two tick that arrived with only
    that round's ids would count the bar down mid-run."""
    job = _job()
    job.observe(SynthesisProgress(round=1, units_total=6, units_done=6, created=("OS1", "OS2")))
    job.observe(SynthesisProgress(round=2, units_total=6, units_done=0, created=("OS1", "OS2")))
    assert job.created_ids == ["OS1", "OS2"]


def test_the_finishing_stages_take_the_bar_the_rest_of_the_way(cfg, db):
    job = _job(requested=1)
    job.observe(SynthesisProgress(round=1, units_total=4, units_done=4, created=("OS1",)))
    job.stages_done.append("synthesise")
    after_synthesis = job.progress
    job.stages_done.extend(["enrich", "link", "score"])
    assert after_synthesis < job.progress < 1.0
    job.stages_done.extend(["actions", "size", "competition"])
    assert job.progress == pytest.approx(1.0)


def test_a_finished_run_reads_as_finished_whatever_it_produced(cfg, db):
    """Including the run that created nothing: the bar reports completion of the
    RUN, and the count beside it reports what came of it."""
    job = _job()
    job.status = "done"
    assert job.progress == 1.0
    job.status = "error"
    assert job.progress == 1.0


def test_a_run_reports_its_progress_over_the_wire(cfg, db):
    _seed_clusters(db)
    service = GenerationService(cfg, db)
    job = _await(service.start(2, GenerationConstraints()))
    payload = job.as_dict()
    assert payload["progress"] == 1.0
    assert payload["units_total"] == 3
    assert payload["unit_label"] == "theme cluster"
    assert set(payload) >= {"progress", "round", "units_done", "units_total", "unit_label"}


# ---------------------------------------------------------------------------
# Showing what a run produced
# ---------------------------------------------------------------------------

#: DR-03 enforces one space per taxonomy triple with a unique index, so seeded
#: rows have to differ in one of the three. The technology is the free one here.
_SEED_TECHNOLOGIES = ("machine_learning", "computer_vision", "private_5g", "edge_computing")


def _space(db: Database, topic_id: str, state: str = "candidate", index: int = 0) -> None:
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO opportunity_spaces
               (id, version, vertical, use_case, technology, statement, domains, personas,
                geographies, state, state_reason, why_hot, first_seen, last_refresh,
                pipeline_version)
               VALUES (?,1,'manufacturing','predictive_maintenance',?,?,?,?,?,
                       ?,'seeded',?,?,?,'test')""",
            (topic_id, _SEED_TECHNOLOGIES[index % len(_SEED_TECHNOLOGIES)],
             f"A specific statement for {topic_id} about rotating equipment in plants.",
             js(["ox_smart_industries"]), js([]), js(["DE"]), state,
             js([{"claim": f"{topic_id} is evidenced.", "signals": ["SIG-1"]}]),
             REF.isoformat(), REF.isoformat()),
        )


def test_a_freshly_created_space_is_readable_before_scoring_promotes_it(cfg, db):
    """`topics()` selects by lifecycle state and a new space is `candidate`
    until scoring moves it, so the report on the Generate screen would show
    nothing for the ids it had just created. Selecting by id is the point."""
    _space(db, "OS900", state="candidate")
    read = ReadModel(cfg, db)
    assert [t["id"] for t in read.topics()] == []
    assert [t["id"] for t in read.topics_by_id(["OS900"])] == ["OS900"]


def test_the_created_spaces_come_back_in_the_order_asked_for(cfg, db):
    _space(db, "OS901", index=0)
    _space(db, "OS902", index=1)
    read = ReadModel(cfg, db)
    assert [t["id"] for t in read.topics_by_id(["OS902", "OS901"])] == ["OS902", "OS901"]
    assert read.topics_by_id([]) == []
    assert read.topics_by_id(["OS999"]) == [], "an id with no row is skipped, not an error"


def test_a_created_space_row_carries_the_statement_and_its_cited_claims(cfg, db):
    """The card on the screen is the list projection plus `why_hot`. A row that
    lost the claims would leave "why does the radar think this is a thing"
    unanswerable on the one screen where nobody has read the space yet."""
    _space(db, "OS903")
    topic = ReadModel(cfg, db).topics_by_id(["OS903"])[0]
    card = topic_for_list(topic) | {"why_hot": topic.get("why_hot", [])}
    assert card["statement"].startswith("A specific statement")
    assert card["labels"]["vertical"] and card["labels"]["technology"]
    assert card["why_hot"][0]["signals"] == ["SIG-1"]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def _shared_embedder() -> Embedder:
    """One encoder for the whole module.

    The sentence-transformer model takes seconds to load and every test that
    seeds embedded signals would otherwise pay it again — which is how a fast
    suite quietly becomes a two-minute one.
    """
    return Embedder()


def _await(job, timeout: float = 60.0):
    """Block until the background run finishes."""
    import time
    deadline = time.monotonic() + timeout
    while job.status in ("queued", "running") and time.monotonic() < deadline:
        time.sleep(0.05)
    return job


def _seed_clusters(db: Database, extra: int = 0, embed: bool = False) -> None:
    """Three clusters whose evidence differs in geography and signal type.

    Sizes descend with the id so the default "largest first" ordering is
    distinguishable from the constraint-driven one.
    """
    rows = [
        (1, "French research", 30, [("SIG-1", "FR", "trend")]),
        (2, "German regulation", 20, [("SIG-2", "DE", "regulation")]),
        (3, "Polish tenders", 10, [("SIG-3", "PL", "buying_signal")]),
    ]
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    embedder = _shared_embedder() if embed else None
    with db.cursor() as cur:
        for cluster_id, label, size, signals in rows:
            cur.execute("INSERT INTO clusters (id, label, keyphrases, size, created_at, refresh_id) "
                        "VALUES (?,?,'[]',?,?,'R-seed')", (cluster_id, label, size, now))
            for signal_id, geo, signal_type in signals:
                cur.execute(
                    """INSERT INTO signals (id, source_id, publisher, title, url, published_at,
                                            ingested_at, language, geographies, signal_type, tier,
                                            extract, relevance, cluster_id, pipeline_version)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (signal_id, "src", "Publisher", f"{label} item", f"https://example.invalid/{signal_id}",
                     REF.isoformat(), now, "en", js([geo]), signal_type, 1,
                     "An extract long enough to be evidence.", 0.9, cluster_id, "test"),
                )
                if embedder is not None:
                    vector = embedder.encode([f"{label} item An extract long enough to be evidence."])[0]
                    cur.execute("UPDATE signals SET embedding = ? WHERE id = ?",
                                (Embedder.to_blob(vector), signal_id))
        for index in range(extra):
            cur.execute("INSERT INTO clusters (id, label, keyphrases, size, created_at, refresh_id) "
                        "VALUES (?,?,'[]',?,?,'R-seed')", (100 + index, f"filler {index}", 5, now))
