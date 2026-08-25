"""The guard in front of the HTTP surface.

`test_auth.py` covers the mechanism — hashes, sessions, throttling. This covers
the thing that actually failed in production: a route nobody remembered to
protect. The central test therefore walks the router rather than checking a
representative endpoint, because "we forgot one" is the entire failure mode of a
per-route guard, and it is invisible to a test that names its own endpoints.

The rest pins the parts of the cookie contract a browser enforces and a Python
client does not: `HttpOnly` is what stops an injected script reading the session,
`SameSite=Lax` is what stands in for a CSRF token, and `Secure` has to follow the
scheme the *user's* browser used, which behind App Service is not the scheme the
application sees.
"""

from __future__ import annotations

import pytest

from radar.db import Database


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """The API over a scratch database.

    `radar.api` reads its configuration, opens its database and seeds the first
    account at IMPORT time, so all three have to be arranged before the import —
    hence the deferred import and the module scope. `bootstrap.prepare` is
    stubbed out because in a checkout it would copy the 121 MB packaged database
    into the temporary directory to seed a file the schema call creates anyway.
    """
    from fastapi.testclient import TestClient

    from radar import auth, bootstrap

    patch = pytest.MonkeyPatch()
    db_path = tmp_path_factory.mktemp("api") / "radar.db"
    Database(db_path).init_schema()

    patch.setenv("RADAR_DB_PATH", str(db_path))
    patch.setattr(auth, "ITERATIONS", 1000)
    patch.setattr(bootstrap, "prepare", lambda *args, **kwargs: None)

    from radar.api import app

    with TestClient(app) as test_client:
        yield test_client
    patch.undo()


@pytest.fixture(autouse=True)
def signed_out(client):
    """Every test starts anonymous; a cookie left by one must not authorise the
    next."""
    from radar.auth import reset_throttle
    client.cookies.clear()
    reset_throttle()
    yield
    client.cookies.clear()


@pytest.fixture()
def account(client):
    """A throwaway account, so a test that changes a password does not have to
    put the seeded one back afterwards — a restore step that is itself subject
    to the password policy, and which failed silently the first time it was
    written.

    Created through the service rather than over HTTP because there is no
    create-account endpoint, and deliberately so: handing the running app the
    power to mint logins would turn a session hijack into a permanent one.
    """
    from radar.api import _auth
    name, password = "tester", "first-password"
    _auth.create_user(name, password)
    yield name, password
    _auth.delete_user(name)


def sign_in(client, username="orange", password="orange"):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response


#: Path parameters need *a* value to route on. It never has to exist — the guard
#: runs before the handler, so a 401 is proof the handler was never reached.
PLACEHOLDERS = {"topic_id": "OS001", "plan_id": "PLAN-1", "job_id": "JOB-1",
                "competitor_id": "c1", "node_id": "offer:x", "full_path": "index.html",
                "kind": "battlecards"}


def api_routes(app):
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/api/") or path.startswith("/api/auth/"):
            continue
        for method in sorted((getattr(route, "methods", set()) or set()) - {"HEAD", "OPTIONS"}):
            concrete = path
            for name, value in PLACEHOLDERS.items():
                concrete = concrete.replace("{" + name + "}", value).replace(
                    "{" + name + ":path}", value)
            yield method, path, concrete


def test_every_api_route_refuses_an_anonymous_request(client):
    """The one that matters. Walked rather than enumerated by hand, so a route
    added next month is covered the day it is added."""
    served = []
    for method, path, concrete in api_routes(client.app):
        response = client.request(method, concrete, json={} if method != "GET" else None)
        if response.status_code != 401:
            served.append(f"{method} {path} -> {response.status_code}")
    assert not served, "these answered an anonymous request:\n  " + "\n  ".join(served)


def test_the_login_screen_can_load_before_anyone_signs_in(client):
    """The app shell is not behind the guard — it *is* the sign-in form. A guard
    that protects the login page has locked the door from the inside."""
    assert client.get("/").status_code == 200
    assert client.get("/some/client/side/route").status_code == 200


def test_the_platform_probe_is_not_behind_the_guard(client):
    """`/healthz` answering 401 would make every deployment look unhealthy, and
    the platform would restart a perfectly good container until the plan's quota
    ran out."""
    assert client.get("/healthz").status_code == 200


def test_the_session_probe_answers_rather_than_refusing(client):
    """200 with `authenticated: false`, not 401. The frontend runs this on every
    load, and a route whose normal answer for a signed-out visitor is an error
    makes a signed-out visitor indistinguishable from a broken server."""
    body = client.get("/api/auth/session").json()
    assert body["authenticated"] is False
    assert body["user"] is None
    assert body["password_policy"]["min_length"] >= 8


def test_signing_in_opens_the_api(client):
    assert client.get("/api/meta").status_code == 401
    sign_in(client)
    assert client.get("/api/meta").status_code == 200
    assert client.get("/api/auth/session").json()["authenticated"] is True


def test_the_shipped_default_is_flagged_to_the_interface(client):
    """The seeded credential is only acceptable if the interface keeps saying so."""
    assert sign_in(client).json()["user"]["must_change_password"] is True


def test_the_session_cookie_is_httponly_and_samesite(client):
    response = sign_in(client)
    header = response.headers["set-cookie"].lower()
    assert "httponly" in header
    assert "samesite=lax" in header
    assert "path=/" in header


def test_the_cookie_follows_the_scheme_the_browser_used(client):
    """App Service terminates TLS at the front end, so the origin request arrives
    as HTTP. Reading the scheme off the request would leave the session cookie
    unmarked on a site that is HTTPS everywhere the user can see."""
    plain = sign_in(client)
    assert "secure" not in plain.headers["set-cookie"].lower()
    client.cookies.clear()
    forwarded = client.post("/api/auth/login", json={"username": "orange", "password": "orange"},
                            headers={"x-forwarded-proto": "https"})
    assert "secure" in forwarded.headers["set-cookie"].lower()


def test_a_wrong_password_is_401_and_says_nothing_useful(client):
    response = client.post("/api/auth/login", json={"username": "orange", "password": "nope"})
    assert response.status_code == 401
    assert "orange" not in response.json()["detail"]


def test_signing_out_closes_the_api_again(client):
    sign_in(client)
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/meta").status_code == 401


def test_signing_out_works_without_a_session(client):
    """Requiring one means an expired session cannot be cleared, which leaves a
    dead cookie in the browser and a user who can get neither in nor out."""
    assert client.post("/api/auth/logout").status_code == 200


def test_changing_a_password_needs_the_current_one(client, account):
    """The session proves the laptop is unlocked, not that the person at it knows
    the password — and a password change is the one action that locks its owner
    out."""
    name, password = account
    sign_in(client, name, password)
    refused = client.post("/api/auth/password",
                          json={"current_password": "not-it", "new_password": "a-long-new-one"})
    assert refused.status_code == 403


def test_changing_a_password_keeps_this_session_and_ends_the_others(client, account):
    name, password = account
    sign_in(client, name, password)
    changed = client.post("/api/auth/password",
                          json={"current_password": password, "new_password": "a-long-new-one"})
    assert changed.status_code == 200
    # The tab that did it stays signed in: it just proved it knows the password.
    assert client.get("/api/meta").status_code == 200
    # The old credential no longer works anywhere.
    client.cookies.clear()
    assert client.post("/api/auth/login",
                       json={"username": name, "password": password}).status_code == 401
    sign_in(client, name, "a-long-new-one")


def test_a_rejected_password_says_which_rule_it_broke(client, account):
    name, password = account
    sign_in(client, name, password)
    response = client.post("/api/auth/password",
                           json={"current_password": password, "new_password": "short"})
    assert response.status_code == 400
    assert "8 characters" in response.json()["detail"]
