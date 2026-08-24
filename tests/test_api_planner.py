"""The HTTP contract the Planner screen is written against.

`test_planner.py` covers the engine — what is selected, how it is scheduled,
what the arithmetic does. This covers the three things the SCREEN depends on and
the engine cannot guarantee on its own:

  * the form is told what the workflow board holds BEFORE anything is built,
    and told it in the number that matters — how many committed spaces can
    actually be projected, not how many reached a stage. A form quoting the
    larger number promises a plan bigger than the one that comes back;
  * a plan built from the workflow and a plan built from parameters are two
    plans, not one, so neither can quietly overwrite the other;
  * an empty board fails with a message about the board. Telling a user of the
    workflow mode to loosen a confidence floor sends them to a control that is
    not on their screen.
"""

from __future__ import annotations

import datetime as dt

import pytest

from radar.db import Database, js


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """The API over a scratch database with a small board already populated.

    `radar.api` reads config, opens its database and seeds the first account at
    IMPORT time, so all of that is arranged before the import — and then the
    module is RELOADED, because two test modules that both bind a database at
    import cannot both get their own by importing. See `test_api_presales` for
    the full account of that failure mode.
    """
    import importlib

    from fastapi.testclient import TestClient

    from radar import auth, bootstrap

    patch = pytest.MonkeyPatch()
    root = tmp_path_factory.mktemp("api-planner")
    db_path = root / "radar.db"
    database = Database(db_path)
    database.init_schema()
    _seed(database)

    patch.setenv("RADAR_DB_PATH", str(db_path))
    patch.setenv("RADAR_LLM_PROVIDER", "mock")
    patch.setattr(auth, "ITERATIONS", 1000)
    patch.setattr(bootstrap, "prepare", lambda *args, **kwargs: None)

    import radar.api

    radar.api = importlib.reload(radar.api)

    with TestClient(radar.api.app) as test_client:
        test_client.post("/api/auth/login", json={"username": "orange", "password": "orange"})
        yield test_client
    patch.undo()


#: Six spaces on the board: two waiting, three committed and sized, one
#: committed and unsized — the case the meta endpoint has to count correctly.
BOARD = [
    ("OS001", "shortlisted", True),
    ("OS002", "shortlisted", True),
    ("OS003", "demand_tested", True),
    ("OS004", "demand_tested", True),
    ("OS005", "packaged", True),
    ("OS006", "demand_tested", False),
]


def _seed(db: Database) -> None:
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    with db.cursor() as cur:
        cur.execute("""INSERT INTO graph_nodes (id, node_type, label, attributes, source, as_of)
                       VALUES (?,?,?,?,?,?)""",
                    ("capability_pool:test", "capability_pool", "Test experts",
                     js({"headcount": 20000, "technologies": ["private_5g"],
                         "verticals": [], "domains": []}), "test", now))
        for i, (topic, stage, sized) in enumerate(BOARD):
            cur.execute("""INSERT INTO opportunity_spaces
                (id, version, vertical, use_case, technology, statement, domains, personas,
                 geographies, state, horizon, first_seen, last_refresh, pipeline_version)
                VALUES (?,1,'manufacturing',?,'private_5g',?,'[]','[]','[]','active','now',?,?,
                        '0.1.0')""",
                (topic, f"use_case_{i}",
                 f"A statement long enough to look like a real opportunity space, number {i}.",
                 now, now))
            cur.execute("""INSERT INTO workflow_state
                (opportunity_id, stage, owner_role, entered_stage_at, updated_at)
                VALUES (?,?,'sales',?,?)""", (topic, stage, now, now))
            cur.execute("""INSERT INTO opportunity_links
                (opportunity_id, node_id, link_type, confidence, evidence, created_at)
                VALUES (?,?,'L0',0.8,'{}',?)""", (topic, "capability_pool:test", now))
            if sized:
                cur.execute("""INSERT INTO market_sizes
                    (opportunity_id, computed_at, method, currency, som_low, som_base, som_high,
                     confidence, factors, coverage, caveats, sizing_version, pipeline_version)
                    VALUES (?,?, 'bottom_up_adoption','EUR',1e7,5e7,1.5e8,'observed',
                            '[]','{}','[]','v1','0.1.0')""", (topic, now))


# ------------------------------------------------------------------- the form

def test_the_form_is_told_what_the_board_holds_before_anything_is_built(client):
    """And in the number that matters: how many committed spaces can actually
    be projected, not how many reached a stage."""
    meta = client.get("/api/planner/meta").json()
    stages = {s["id"]: s for s in meta["workflow"]["stages"]}

    assert stages["demand_tested"]["count"] == 3
    # Demand-tested OR FURTHER: three at the stage plus one Packaged.
    assert stages["demand_tested"]["cumulative"] == 4
    # One of those four has no bottom-up size and contributes to no figure.
    assert stages["demand_tested"]["cumulative_sized"] == 3
    assert stages["packaged"]["cumulative"] == 1
    assert meta["workflow"]["default_from_stage"] == "demand_tested"


# ------------------------------------------------------------------ the plan

def test_a_workflow_plan_takes_the_committed_set_and_no_parameter_touches_it(client):
    response = client.post("/api/planner/plans", json={
        "label": "Committed", "source": "workflow", "from_stage": "demand_tested",
        "min_confidence": "observed", "max_portfolio_distance": 0,
        "entry_slots_per_year": 99,
    })
    assert response.status_code == 200, response.text
    plan = response.json()

    assert {s["opportunity_id"] for s in plan["selections"]} == {"OS003", "OS004", "OS005"}
    assert plan["inputs"]["source"] == "workflow"
    assert plan["capacity_usage"]["from_stage"] == "demand_tested"
    # The unsized commitment is declared rather than quietly missing.
    assert any(f["kind"] == "unsized_commitment" and "OS006" in f["message"]
               for f in plan["flags"])


def test_the_two_sources_produce_two_plans(client):
    """A workflow plan must not overwrite the parameter plan it is compared
    against — the source is part of the plan's fingerprint."""
    body = {"label": "Same name", "entry_slots_per_year": 99}
    a = client.post("/api/planner/plans", json={**body, "source": "parameters"}).json()
    b = client.post("/api/planner/plans", json={**body, "source": "workflow"}).json()
    assert a["id"] != b["id"]
    assert client.get(f"/api/planner/plans/{a['id']}").json()["inputs"]["source"] == "parameters"
    assert client.get(f"/api/planner/plans/{b['id']}").json()["inputs"]["source"] == "workflow"


def test_an_empty_stage_fails_in_the_terms_of_the_mode_that_was_used(client):
    """Nothing has reached Live. The message has to send the reader to the
    workflow board, not to a confidence floor that is not on their screen."""
    response = client.post("/api/planner/plans", json={
        "label": "Nothing live", "source": "workflow", "from_stage": "live"})
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "Live" in detail and "workflow board" in detail
    assert "confidence floor" not in detail


def test_an_unknown_stage_is_refused_rather_than_planned_as_something_else(client):
    response = client.post("/api/planner/plans", json={
        "label": "Bad stage", "source": "workflow", "from_stage": "not_a_stage"})
    assert response.status_code == 409
    assert "Unknown workflow stage" in response.json()["detail"]
