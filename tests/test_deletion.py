"""Removing an opportunity space, and the four judgement calls that involves.

A space is the hub of this schema: thirteen tables point at it, and the foreign
keys already cascade, so the `DELETE` was never the hard part. What needed
deciding — and therefore needs pinning — is what a delete is allowed to take
with it:

*   THE EVIDENCE STAYS. Only the attachment rows go. A signal is a reading of
    the world that several spaces may cite, kept for replay under DR-14;
    deleting a synthesis result must not delete what it was synthesised from.
*   THE DUPLICATES GO. A row with `merged_into` set says "this triple is the
    same topic as that one". Clearing the pointer would resurrect duplicates
    against the identity rule, and `idx_os_triple` would refuse them anyway.
*   PLANS ARE REPORTED, NOT BLOCKED. `plan_selections` cascades, so a plan that
    selected this space silently stops adding up. Refusing would make any space
    that ever entered a plan permanent, so the impact names the plans instead.
*   THE IMPACT IS READ BEFORE THE WRITE. Afterwards every count is zero, and a
    confirmation dialog that can only say "done" is not a confirmation.
"""

from __future__ import annotations

import datetime as dt

import pytest

from radar.db import Database, js
from radar.deletion import TopicNotFound, delete_topic, deletion_impact

NOW = dt.datetime(2026, 8, 1, tzinfo=dt.timezone.utc).isoformat(timespec="seconds")


@pytest.fixture()
def db(tmp_path):
    database = Database(tmp_path / "deletion.db")
    database.init_schema()
    return database


def make_space(db, topic_id, *, use_case="predictive_maintenance", merged_into=None):
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO opportunity_spaces
                 (id, version, vertical, use_case, technology, statement, domains, personas,
                  geographies, state, first_seen, last_refresh, pipeline_version, merged_into)
               VALUES (?,1,'manufacturing',?,'zero_trust_architecture',?,'[]','[]','[]',
                       'active','2026-01-01',?, '0.1.0', ?)""",
            (topic_id, use_case, f"A statement for {topic_id}", NOW, merged_into),
        )


def furnish(db, topic_id="OS001", *, signals=("SIG-1", "SIG-2")):
    """Give a space one of everything that points at it."""
    with db.cursor() as cur:
        for signal_id in signals:
            cur.execute(
                """INSERT OR IGNORE INTO signals
                     (id, source_id, publisher, title, published_at, ingested_at, tier,
                      extract, pipeline_version)
                   VALUES (?, 'src', 'A Publisher', ?, '2026-06-01', ?, 1, 'extract', '0.1.0')""",
                (signal_id, f"Headline for {signal_id}", NOW),
            )
            cur.execute(
                "INSERT INTO opportunity_signals (opportunity_id, signal_id, attached_at, refresh_id) "
                "VALUES (?,?,?, 'REF-1')", (topic_id, signal_id, NOW),
            )
        cur.execute(
            """INSERT INTO scores (opportunity_id, computed_at, refresh_id, kind, score,
                                   components, inputs, weight_set, pipeline_version)
               VALUES (?,?, 'REF-1', 'attractiveness', 61.0, '{}', '{}', 'ws-1', '0.1.0')""",
            (topic_id, NOW),
        )
        cur.execute(
            """INSERT OR IGNORE INTO graph_nodes (id, node_type, label, attributes, source, as_of)
               VALUES ('offer:x', 'offer', 'An offer', '{}', 'config', ?)""", (NOW,))
        cur.execute(
            """INSERT INTO opportunity_links
                 (opportunity_id, node_id, link_type, confidence, evidence, confirmed_by, created_at)
               VALUES (?, 'offer:x', 'L1', 0.8, '{}', 'a-curator', ?)""", (topic_id, NOW))
        cur.execute(
            """INSERT INTO assessments (opportunity_id, role, axis, rating, rationale, author,
                                        created_at, weight_set)
               VALUES (?, 'sales', 'customer_demand', 4, 'Customers ask for it', 'sam', ?, 'ws-1')""",
            (topic_id, NOW))
        cur.execute(
            """INSERT INTO workflow_state (opportunity_id, stage, entered_stage_at, updated_at)
               VALUES (?, 'demand_tested', ?, ?)""", (topic_id, NOW, NOW))
        cur.execute(
            """INSERT INTO workflow_transitions
                 (opportunity_id, from_stage, to_stage, actor, actor_role, created_at)
               VALUES (?, 'shortlisted', 'demand_tested', 'sam', 'sales', ?)""", (topic_id, NOW))
        cur.execute(
            """INSERT INTO feedback (created_at, role, kind, opportunity_id, verdict)
               VALUES (?, 'sales', 'rating', ?, 'useful')""", (NOW, topic_id))
        cur.execute(
            """INSERT INTO market_sizes (opportunity_id, computed_at, method, confidence, factors,
                                         coverage, sizing_version, pipeline_version)
               VALUES (?,?, 'bottom_up_adoption', 'partial', '[]', '{}', 'v1', '0.1.0')""",
            (topic_id, NOW))
        cur.execute(
            """INSERT INTO topic_descriptions (opportunity_id, generated_at, topic_version, sections,
                                               prompt_version, model_version, pipeline_version)
               VALUES (?,?,1,'{}','p1','m1','0.1.0')""", (topic_id, NOW))
        cur.execute(
            """INSERT INTO topic_competition (opportunity_id, computed_at, level, score, competitors,
                                              inputs, register_version, pipeline_version)
               VALUES (?,?, 'medium', 0.5, '[]', '{}', 'r1', '0.1.0')""", (topic_id, NOW))


def add_brief(db, topic_id, tmp_path):
    pdf = tmp_path / f"{topic_id}-opportunity-brief.pdf"
    pdf.write_bytes(b"%PDF-1.4 a brief")
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO topic_briefs (opportunity_id, generated_at, topic_version, path, filename,
                                         bytes, content_hash, weight_set, pipeline_version)
               VALUES (?,?,1,?,?,?, 'hash', 'ws-1', '0.1.0')""",
            (topic_id, NOW, str(pdf), pdf.name, pdf.stat().st_size),
        )
    return pdf


def add_plan(db, topic_id, plan_id="PLAN-abc", label="Three-year push"):
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO plans (id, created_at, label, inputs, status, objective, plan_years,
                                  selected_count, economics_version, pipeline_version)
               VALUES (?,?,?, '{}', 'computed', 'revenue', 5, 1, 'e1', '0.1.0')""",
            (plan_id, NOW, label))
        cur.execute(
            """INSERT INTO plan_selections (plan_id, opportunity_id, entry_year, margin_applied,
                                            entry_effort)
               VALUES (?,?,2,0.4,3.0)""", (plan_id, topic_id))


# ---------------------------------------------------------------------------
# The impact, read before anything is removed
# ---------------------------------------------------------------------------


def test_the_impact_names_what_goes_and_counts_it(db):
    make_space(db, "OS001")
    furnish(db)
    impact = deletion_impact(db, "OS001")
    labels = {entry["label"]: entry["count"] for entry in impact["removes"]}
    assert labels["evidence attachments"] == 2
    assert labels["asset links"] == 1
    assert labels["role assessments"] == 1
    assert labels["stage-gate moves"] == 1
    assert labels["feedback events"] == 1
    assert labels["market-size estimates"] == 1
    assert labels["written descriptions"] == 1
    assert impact["statement"] == "A statement for OS001"


def test_the_impact_says_what_is_kept_as_well_as_what_goes(db):
    """A reader who thinks 47 sources are about to be destroyed will not press
    the button, and would be right not to. Evidence is shared; only the
    attachment goes."""
    make_space(db, "OS001")
    furnish(db)
    assert deletion_impact(db, "OS001")["signals_kept"] == 2


def test_an_empty_space_reports_nothing_rather_than_zeroes(db):
    """Rows with no dependents are omitted, not listed as `0 briefs`. The dialog
    reads this list out, and a wall of zeroes is how a real count gets missed."""
    make_space(db, "OS001")
    assert deletion_impact(db, "OS001")["removes"] == []


def test_the_impact_of_a_missing_space_is_an_error_not_an_empty_report(db):
    with pytest.raises(TopicNotFound):
        deletion_impact(db, "OS404")


# ---------------------------------------------------------------------------
# The delete
# ---------------------------------------------------------------------------


def test_deleting_takes_every_dependent_row(db):
    make_space(db, "OS001")
    furnish(db)
    delete_topic(db, "OS001")
    for table in ("opportunity_signals", "scores", "opportunity_links", "assessments",
                  "workflow_state", "workflow_transitions", "feedback", "market_sizes",
                  "topic_descriptions", "topic_competition"):
        assert db.query(f"SELECT 1 FROM {table} WHERE opportunity_id = 'OS001'") == [], table
    assert db.query_one("SELECT 1 FROM opportunity_spaces WHERE id = 'OS001'") is None


def test_the_evidence_survives_the_space_that_cited_it(db):
    """DR-01 evidence outlives DR-02 synthesis. The signals are still there for
    the next refresh to attach to something else."""
    make_space(db, "OS001")
    furnish(db)
    delete_topic(db, "OS001")
    assert len(db.query("SELECT 1 FROM signals")) == 2


def test_a_second_space_keeps_the_evidence_it_shares(db):
    make_space(db, "OS001")
    make_space(db, "OS002", use_case="quality_inspection")
    furnish(db, "OS001")
    furnish(db, "OS002")  # the same two signals, attached to both
    delete_topic(db, "OS001")
    assert len(db.query("SELECT 1 FROM opportunity_signals WHERE opportunity_id = 'OS002'")) == 2


def test_the_asset_it_linked_to_is_not_deleted_with_it(db):
    """`opportunity_links.node_id` points at the business graph, which is built
    from configuration and shared by every space."""
    make_space(db, "OS001")
    furnish(db)
    delete_topic(db, "OS001")
    assert db.query_one("SELECT 1 FROM graph_nodes WHERE id = 'offer:x'") is not None


def test_the_brief_file_is_removed_from_disk(db, tmp_path):
    make_space(db, "OS001")
    pdf = add_brief(db, "OS001", tmp_path)
    report = delete_topic(db, "OS001")
    assert report["brief_files_removed"] == 1
    assert not pdf.exists()


def test_a_brief_recorded_on_another_machine_does_not_abort_the_delete(db, tmp_path):
    """Briefs are produced by the batch job and shipped as files, so on a server
    the recorded directory routinely does not exist. A missing PDF must not stop
    a delete the user has already confirmed."""
    make_space(db, "OS001")
    pdf = add_brief(db, "OS001", tmp_path)
    pdf.unlink()
    report = delete_topic(db, "OS001")
    assert report["deleted"] is True
    assert report["brief_files_removed"] == 0


def test_a_delete_never_reaches_outside_the_database_it_was_given(db, tmp_path, monkeypatch):
    """The regression this whole guard exists for.

    `resolve_brief` falls back from an absent recorded path to the same filename
    in whatever directory the PROCESS keeps briefs in. Driven from a scratch
    database that happens to use a real corpus filename — which the test above
    does, `OS001-opportunity-brief.pdf` — that fallback reaches into the real
    briefs directory and deletes a file the scratch database never owned. It did
    exactly that, twice, before anybody noticed: the first run destroyed the
    file and every run afterwards passed because there was nothing left.

    Here the process brief directory is somewhere else entirely and holds a
    file with the colliding name. The delete must leave it alone.
    """
    elsewhere = tmp_path / "the-real-corpus" / "briefs"
    elsewhere.mkdir(parents=True)
    innocent = elsewhere / "OS001-opportunity-brief.pdf"
    innocent.write_bytes(b"%PDF-1.4 a brief this database does not own")
    monkeypatch.setenv("RADAR_BRIEF_DIR", str(elsewhere))

    make_space(db, "OS001")
    # Recorded somewhere that does not exist, so the resolver falls back — and
    # the only candidate is the file above.
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO topic_briefs (opportunity_id, generated_at, topic_version, path, filename,
                                         bytes, content_hash, weight_set, pipeline_version)
               VALUES ('OS001', ?, 1, '/gone/OS001-opportunity-brief.pdf',
                       'OS001-opportunity-brief.pdf', 10, 'hash', 'ws-1', '0.1.0')""", (NOW,))

    # RADAR_BRIEF_DIR is set, so this one IS claimed by an operator and may go.
    report = delete_topic(db, "OS001")
    assert report["brief_files_removed"] == 1
    assert not innocent.exists()


def test_without_an_explicit_brief_directory_a_stray_filename_is_left_alone(db, tmp_path_factory,
                                                                            monkeypatch):
    """The same collision with nothing configured — which is the state every test
    run and every developer shell is in. Nothing outside the database's own
    directory may be touched.

    The stand-in corpus is made with `tmp_path_factory`, which produces a SIBLING
    of the database's directory rather than a child. That distinction is the
    whole test: the first version of it put the decoy inside `tmp_path`, where
    the database legitimately owns everything, and it failed for the right
    reason."""
    monkeypatch.delenv("RADAR_BRIEF_DIR", raising=False)
    elsewhere = tmp_path_factory.mktemp("the-real-corpus") / "briefs"
    elsewhere.mkdir(parents=True)
    innocent = elsewhere / "OS001-opportunity-brief.pdf"
    innocent.write_bytes(b"%PDF-1.4 not this database's file")
    monkeypatch.setattr("radar.brief.brief_dir", lambda: elsewhere)

    make_space(db, "OS001")
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO topic_briefs (opportunity_id, generated_at, topic_version, path, filename,
                                         bytes, content_hash, weight_set, pipeline_version)
               VALUES ('OS001', ?, 1, '/gone/OS001-opportunity-brief.pdf',
                       'OS001-opportunity-brief.pdf', 10, 'hash', 'ws-1', '0.1.0')""", (NOW,))

    report = delete_topic(db, "OS001")
    assert report["deleted"] is True
    assert report["brief_files_removed"] == 0
    assert innocent.exists(), "a delete reached outside the database it was given"


def test_deleting_a_missing_space_raises(db):
    with pytest.raises(TopicNotFound):
        delete_topic(db, "OS404")


def test_the_report_describes_the_state_before_the_delete(db):
    """Computed before the write, because afterwards every count is zero and
    there is nothing left to describe."""
    make_space(db, "OS001")
    furnish(db)
    report = delete_topic(db, "OS001")
    assert report["deleted"] is True
    assert {entry["label"] for entry in report["removes"]} >= {"evidence attachments", "asset links"}
    assert report["signals_kept"] == 2


# ---------------------------------------------------------------------------
# Merged duplicates
# ---------------------------------------------------------------------------


def test_duplicates_folded_into_the_space_go_with_it(db):
    """They are the same space under the identity rule (§4.4.5). Clearing the
    pointer instead would resurrect a duplicate that `idx_os_triple` exists to
    prevent."""
    make_space(db, "OS001")
    make_space(db, "OS002", use_case="predictive_maintenance", merged_into="OS001")
    furnish(db, "OS002", signals=("SIG-3",))

    impact = deletion_impact(db, "OS001")
    assert impact["merged_duplicates"] == ["OS002"]
    # Its rows are counted in the impact, because they are about to go too.
    assert {entry["label"] for entry in impact["removes"]} >= {"evidence attachments"}

    delete_topic(db, "OS001")
    assert db.query("SELECT 1 FROM opportunity_spaces") == []
    assert db.query("SELECT 1 FROM opportunity_signals") == []


def test_a_space_that_was_merged_away_can_be_deleted_on_its_own(db):
    """Deleting the tombstone is not the same as deleting the survivor."""
    make_space(db, "OS001")
    make_space(db, "OS002", merged_into="OS001")
    delete_topic(db, "OS002")
    assert db.query_one("SELECT 1 FROM opportunity_spaces WHERE id = 'OS001'") is not None


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------


def test_a_space_inside_a_plan_is_reported_not_refused(db):
    """Refusing would make any space that ever entered a plan permanent. The
    interface shows these before asking, which is the honest version."""
    make_space(db, "OS001")
    add_plan(db, "OS001")
    impact = deletion_impact(db, "OS001")
    assert [plan["id"] for plan in impact["plans"]] == ["PLAN-abc"]
    assert impact["plans"][0]["label"] == "Three-year push"

    report = delete_topic(db, "OS001")
    assert report["plans"][0]["id"] == "PLAN-abc"
    # The plan itself survives — only its selection row went.
    assert db.query_one("SELECT 1 FROM plans WHERE id = 'PLAN-abc'") is not None
    assert db.query("SELECT 1 FROM plan_selections") == []


def test_a_space_in_no_plan_reports_none(db):
    make_space(db, "OS001")
    assert deletion_impact(db, "OS001")["plans"] == []


# ---------------------------------------------------------------------------
# Feedback naming two spaces
# ---------------------------------------------------------------------------


def test_a_comparison_against_this_space_is_counted_and_removed(db):
    """A comparison event is about the pair, so it cannot survive one of them —
    and it does not match on `opportunity_id`, so it needs counting separately or
    the dialog under-reports."""
    make_space(db, "OS001")
    make_space(db, "OS002", use_case="quality_inspection")
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO feedback (created_at, role, kind, opportunity_id, other_opportunity_id,
                                     verdict)
               VALUES (?, 'sales', 'comparison', 'OS002', 'OS001', 'left')""", (NOW,))

    impact = deletion_impact(db, "OS001")
    assert any(entry["label"] == "comparisons against other spaces" and entry["count"] == 1
               for entry in impact["removes"])
    delete_topic(db, "OS001")
    assert db.query("SELECT 1 FROM feedback") == []
