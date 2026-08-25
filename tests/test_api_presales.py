"""The HTTP contract the Pre-sales tab is written against.

`test_presales.py` covers the builder — that every piece renders, in every
format, and refuses to print a figure a model invented. This covers the three
things the SCREEN depends on and the builder cannot guarantee on its own:

  * the catalogue is served in full before anything is built, because a tab
    that starts empty is one nobody presses a button on;
  * a format the piece does not offer is refused with a message naming what it
    does offer, rather than silently returning the default under the wrong
    extension;
  * a download carries the right media type and filename, since that is what
    decides whether Word opens the file or the browser shows a wall of XML.
"""

from __future__ import annotations

import datetime as dt

import pytest

from radar.db import Database, js

TOPIC = "OS001"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """The API over a scratch database with one fully populated space.

    `radar.api` reads config, opens its database and seeds the first account at
    IMPORT time, so all of that is arranged before the import — the same dance
    `test_api_auth` does, for the same reason.

    And then RELOADED, which `test_api_auth` does not need and this does. Two
    modules that both bind a database at import cannot both get their own by
    importing: whichever runs first wins, the second silently inherits the
    first's database, and every assertion here fails against a space that is not
    there. Passing alone and failing in the suite is the signature of it.
    """
    import importlib

    from fastapi.testclient import TestClient

    from radar import auth, bootstrap

    patch = pytest.MonkeyPatch()
    root = tmp_path_factory.mktemp("api-presales")
    db_path = root / "radar.db"
    database = Database(db_path)
    database.init_schema()
    _seed(database)

    patch.setenv("RADAR_DB_PATH", str(db_path))
    patch.setenv("RADAR_COLLATERAL_DIR", str(root / "collateral"))
    # No key configured means `LLMClient` uses its deterministic stub, so the
    # generate endpoint exercises the real writer and validator path offline.
    patch.setenv("RADAR_LLM_PROVIDER", "mock")
    # And no live research: a test that depends on Google News being reachable
    # is a test that fails for reasons having nothing to do with the code.
    patch.setenv("RADAR_PRESALES_RESEARCH", "0")
    patch.setattr(auth, "ITERATIONS", 1000)
    patch.setattr(bootstrap, "prepare", lambda *args, **kwargs: None)

    import radar.api

    # Re-run the module body against the environment set above, so `_db`, `_cfg`
    # and the read model point at THIS database rather than at whichever test
    # module imported `radar.api` first.
    radar.api = importlib.reload(radar.api)

    with TestClient(radar.api.app) as test_client:
        test_client.post("/api/auth/login", json={"username": "orange", "password": "orange"})
        yield test_client
    patch.undo()


def _seed(db: Database) -> None:
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO opportunity_spaces
               (id, version, vertical, use_case, technology, statement, domains, personas,
                geographies, state, horizon, first_seen, last_refresh, pipeline_version)
               VALUES (?,1,'manufacturing','predictive_maintenance','private_5g',?,
                       '[]','[]','["DE"]','active','now',?,?,'0.1.0')""",
            (TOPIC, "German manufacturers need predictive maintenance without touching the "
                    "control network.", now, now))
        cur.execute(
            """INSERT INTO market_sizes
               (opportunity_id, computed_at, method, currency, tam_base, sam_base, som_base,
                confidence, factors, coverage, caveats, sizing_version, pipeline_version)
               VALUES (?,?, 'bottom_up_adoption','EUR', 1.2e9, 3.1e8, 5.2e7,
                       'high','[]','{}','[]','v1','0.1.0')""",
            (TOPIC, now))
        cur.execute(
            """INSERT INTO topic_competition
               (opportunity_id, computed_at, level, score, competitors, inputs,
                register_version, pipeline_version)
               VALUES (?,?, 'medium', 0.55, ?, '{}', 'reg-v1','0.1.0')""",
            (TOPIC, now, js([{"id": "c1", "label": "Example Competitor", "type": "telco",
                              "basis": "observed", "mentions": []}])))


# ------------------------------------------------------------- the catalogue

def test_the_catalogue_is_served_in_full_before_anything_is_built(client):
    response = client.get(f"/api/topics/{TOPIC}/presales")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 12
    assert all(item["exists"] is False for item in items)
    # Everything the tab renders a row from, present on every row.
    for item in items:
        assert item["title"] and item["summary"] and item["audience"]
        assert item["formats"], item["kind"]
        assert item["format"] == item["formats"][0]["fmt"]
        assert all(f["built"] is False for f in item["formats"])


def test_the_catalogue_404s_for_a_space_that_does_not_exist(client):
    assert client.get("/api/topics/OS999/presales").status_code == 404


def test_an_unknown_kind_is_a_404_not_a_500(client):
    assert client.post(f"/api/topics/{TOPIC}/presales/not-a-thing").status_code == 404


# ---------------------------------------------------------------- generating

def test_generating_a_piece_returns_it_marked_built(client):
    response = client.post(f"/api/topics/{TOPIC}/presales/reference-pack?fmt=pdf")
    assert response.status_code == 200, response.text
    item = response.json()
    assert item["exists"] is True
    assert item["builds"]["pdf"]["exists"] is True
    assert item["builds"]["pdf"]["bytes"] > 1000
    assert item["builds"]["pdf"]["media_type"] == "application/pdf"
    assert {f["fmt"]: f["built"] for f in item["formats"]}["pdf"] is True


def test_a_second_format_coexists_with_the_first(client):
    client.post(f"/api/topics/{TOPIC}/presales/reference-pack?fmt=pdf")
    response = client.post(f"/api/topics/{TOPIC}/presales/reference-pack?fmt=odt")
    item = response.json()
    assert set(item["builds"]) >= {"pdf", "odt"}, "asking for ODF must not discard the PDF"


def test_an_unsupported_format_is_a_400_naming_the_alternatives(client):
    """Refused, not coerced: silently returning the default would hand somebody
    who asked for Word a .pptx wearing a .docx name."""
    response = client.post(f"/api/topics/{TOPIC}/presales/first-meeting-deck?fmt=docx")
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "docx" in detail and "pptx" in detail


def test_generating_is_idempotent_until_forced(client):
    first = client.post(f"/api/topics/{TOPIC}/presales/reference-pack?fmt=pdf").json()
    again = client.post(f"/api/topics/{TOPIC}/presales/reference-pack?fmt=pdf").json()
    assert again["builds"]["pdf"]["generated_at"] == first["builds"]["pdf"]["generated_at"], (
        "a current piece should be returned, not rebuilt")
    forced = client.post(f"/api/topics/{TOPIC}/presales/reference-pack?fmt=pdf&force=true").json()
    assert forced["builds"]["pdf"]["exists"] is True


# ---------------------------------------------------------------- downloading

def test_the_file_downloads_with_the_right_type_and_name(client):
    client.post(f"/api/topics/{TOPIC}/presales/reference-pack?fmt=pdf")
    response = client.get(
        f"/api/topics/{TOPIC}/presales/reference-pack/file?fmt=pdf&download=1")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert "attachment" in response.headers["content-disposition"]
    assert f"{TOPIC}-reference-pack.pdf" in response.headers["content-disposition"]
    # Regenerated in place, so a cached copy would serve a stale document from
    # the same URL.
    assert response.headers["cache-control"] == "no-store"
    assert response.content[:4] == b"%PDF"


def test_an_office_format_downloads_with_its_own_media_type(client):
    """The header is what decides whether Word opens the file or the browser
    shows a wall of XML."""
    client.post(f"/api/topics/{TOPIC}/presales/rfp-boilerplate?fmt=docx")
    response = client.get(
        f"/api/topics/{TOPIC}/presales/rfp-boilerplate/file?fmt=docx&download=1")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert response.content[:2] == b"PK", "a .docx is a zip container"


def test_downloading_a_format_that_was_never_built_is_a_404(client):
    response = client.get(f"/api/topics/{TOPIC}/presales/risk-register/file?fmt=odt")
    assert response.status_code == 404
    assert "POST" in response.json()["detail"], "the 404 should say how to fix it"
