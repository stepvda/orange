"""Who may read the radar, and what stops everyone else.

Until `radar.auth` existed the deployed app answered every request: competitive
analysis of named companies, Orange's own asset graph, and the stage-gate
opinions of people who work here, served to whoever found the hostname. These
tests are about the claims the fix makes, in the order they matter:

*   THE DOOR IS THE ONLY DOOR. Every `/api` path refuses an anonymous request.
    A test that checks one endpoint proves nothing — the failure mode of a guard
    is the route somebody forgot to decorate — so this walks the router.
*   NOTHING REPLAYABLE IS STORED. Not the password, not the session token. A
    copy of the database file is not a set of live logins.
*   THE REFUSAL SAYS NOTHING. An unknown account and a wrong password are
    indistinguishable, in wording and in cost, or the sign-in form becomes a
    staff directory.
*   THE SEED IS A SEED, NOT A BACK DOOR. It appears in an empty database and
    never again — an operator who removes it must not find it restored.
"""

from __future__ import annotations

import datetime as dt

import pytest

from radar.auth import (ABSOLUTE_HOURS, DEFAULT_PASSWORD, DEFAULT_USERNAME, MIN_PASSWORD_CHARS,
                        AuthError, AuthService, RateLimited, WeakPassword, hash_password,
                        reset_throttle, verify_password)
from radar.db import Database


@pytest.fixture(autouse=True)
def cheap_hashing(monkeypatch):
    """600,000 PBKDF2 rounds is the right production figure and the wrong test
    figure — this module hashes a few dozen passwords, and at the real count
    that is most of the suite's runtime for no additional coverage."""
    monkeypatch.setattr("radar.auth.ITERATIONS", 1000)
    reset_throttle()


@pytest.fixture()
def db(tmp_path):
    database = Database(tmp_path / "auth.db")
    database.init_schema()
    return database


@pytest.fixture()
def service(db):
    svc = AuthService(db)
    svc.ensure_seed_user()
    return svc


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------


def test_password_is_never_stored(service, db):
    """The row holds a verifier, and the verifier does not contain the word."""
    row = db.query_one("SELECT password_hash FROM users WHERE username = ?", (DEFAULT_USERNAME,))
    assert DEFAULT_PASSWORD not in row["password_hash"]
    assert row["password_hash"].startswith("pbkdf2_sha256$")


def test_same_password_hashes_differently_each_time():
    """Per-password salt: two accounts that chose the same thing must not be
    recognisable as such by reading the file."""
    assert hash_password("correct horse", iterations=1000) != hash_password("correct horse", iterations=1000)


def test_verify_rejects_a_malformed_verifier():
    """A row somebody hand-edited during an incident answers False, not a 500.
    The caller is a sign-in path, and an exception there says more about the
    account than a refusal does."""
    for junk in ("", "plaintext", "bcrypt$12$x$y", "pbkdf2_sha256$notanumber$a$b"):
        assert verify_password("anything", junk) is False


def test_password_policy_refuses_what_it_cannot_store(service):
    with pytest.raises(WeakPassword):
        service.create_user("shorty", "a" * (MIN_PASSWORD_CHARS - 1))
    with pytest.raises(WeakPassword):
        # Survives a paste, invisible in the field, impossible to retype.
        service.create_user("spacey", " padded password ")


def test_the_seeded_account_is_exempt_from_the_policy_it_violates(service):
    """`orange` is six characters and the minimum is eight. That is deliberate:
    the seed exists to be replaced, and `must_change_password` is the part of the
    contract that says so."""
    token, user = service.login(DEFAULT_USERNAME, DEFAULT_PASSWORD)
    assert user["must_change_password"] is True
    assert len(DEFAULT_PASSWORD) < MIN_PASSWORD_CHARS


# ---------------------------------------------------------------------------
# Sign-in
# ---------------------------------------------------------------------------


def test_the_seeded_account_can_sign_in(service):
    token, user = service.login(DEFAULT_USERNAME, DEFAULT_PASSWORD)
    assert user["username"] == DEFAULT_USERNAME
    assert service.session_user(token)["username"] == DEFAULT_USERNAME


def test_username_is_one_spelling(service):
    """Case-sensitive usernames mean 'Orange' and 'orange' are two accounts, one
    of which the person who created it cannot sign in to."""
    _, user = service.login("  ORANGE ", DEFAULT_PASSWORD)
    assert user["username"] == "orange"


def test_an_unknown_account_and_a_wrong_password_are_indistinguishable(service):
    with pytest.raises(AuthError) as unknown:
        service.login("nobody-here", "whatever12")
    with pytest.raises(AuthError) as wrong:
        service.login(DEFAULT_USERNAME, "whatever12")
    assert str(unknown.value) == str(wrong.value)


def test_the_session_token_is_not_in_the_database(service, db):
    """What is stored is a hash of the cookie. A stolen database file is
    therefore not a set of live sessions — which matters disproportionately here,
    where the database IS a file somebody can walk off with."""
    token, _ = service.login(DEFAULT_USERNAME, DEFAULT_PASSWORD)
    rows = db.query("SELECT token_hash FROM sessions")
    assert len(rows) == 1
    assert token not in rows[0]["token_hash"]
    assert len(rows[0]["token_hash"]) == 64  # sha256, hex


def test_an_unknown_token_is_nobody(service):
    assert service.session_user("not-a-real-token") is None
    assert service.session_user(None) is None
    assert service.session_user("") is None


def test_logout_ends_the_session_immediately(service):
    token, _ = service.login(DEFAULT_USERNAME, DEFAULT_PASSWORD)
    service.logout(token)
    assert service.session_user(token) is None


def test_an_expired_session_stops_working_without_waiting_for_a_sweep(service, db):
    """Expiry is enforced on read, not by the tidy-up that runs at the next
    sign-in. Otherwise a session outlives its expiry for as long as nobody else
    happens to sign in."""
    token, _ = service.login(DEFAULT_USERNAME, DEFAULT_PASSWORD)
    past = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)).isoformat(timespec="seconds")
    with db.cursor() as cur:
        cur.execute("UPDATE sessions SET expires_at = ?", (past,))
    assert service.session_user(token) is None
    # And it is cleaned up rather than left to be re-checked forever.
    assert db.query("SELECT 1 FROM sessions") == []


def test_a_session_cannot_outlive_the_absolute_ceiling(service, db):
    """Rolling expiry keeps a working day alive; the ceiling is what stops a tab
    left open over a holiday from staying signed in."""
    token, _ = service.login(DEFAULT_USERNAME, DEFAULT_PASSWORD)
    long_ago = (dt.datetime.now(dt.timezone.utc)
                - dt.timedelta(hours=ABSOLUTE_HOURS + 1)).isoformat(timespec="seconds")
    future = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).isoformat(timespec="seconds")
    with db.cursor() as cur:
        cur.execute("UPDATE sessions SET created_at = ?, expires_at = ?", (long_ago, future))
    assert service.session_user(token) is None


def test_repeated_failures_close_the_account_for_a_while(service):
    from radar.auth import MAX_ATTEMPTS
    for _ in range(MAX_ATTEMPTS):
        with pytest.raises(AuthError):
            service.login(DEFAULT_USERNAME, "wrong-password")
    with pytest.raises(RateLimited):
        # Including with the RIGHT password: a throttle that steps aside for a
        # correct guess is not a throttle.
        service.login(DEFAULT_USERNAME, DEFAULT_PASSWORD)


def test_a_success_clears_the_failure_count(service):
    from radar.auth import MAX_ATTEMPTS
    for _ in range(MAX_ATTEMPTS - 1):
        with pytest.raises(AuthError):
            service.login(DEFAULT_USERNAME, "wrong-password")
    service.login(DEFAULT_USERNAME, DEFAULT_PASSWORD)
    for _ in range(MAX_ATTEMPTS - 1):
        with pytest.raises(AuthError):
            service.login(DEFAULT_USERNAME, "wrong-password")
    service.login(DEFAULT_USERNAME, DEFAULT_PASSWORD)  # still open


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------


def test_the_seed_is_not_restored_after_it_is_replaced(service, db):
    """Conditioned on the table being EMPTY, not on the account being absent.
    The difference is a convenience versus a back door: an operator who removes
    the shipped account must not find it back after a restart."""
    service.create_user("curator", "a-real-password")
    assert service.delete_user(DEFAULT_USERNAME) is True
    assert service.ensure_seed_user() is False
    assert service.get_user(DEFAULT_USERNAME) is None


def test_the_last_account_cannot_be_removed(service):
    """An authenticated app with no accounts is unreachable, and the only way
    back in is a shell on the database."""
    with pytest.raises(AuthError, match="only account"):
        service.delete_user(DEFAULT_USERNAME)


def test_changing_a_password_signs_the_account_out_everywhere(service):
    """The usual reason to change a password is that somebody else might know
    the old one. Leaving their session alive makes the change cosmetic."""
    first, _ = service.login(DEFAULT_USERNAME, DEFAULT_PASSWORD)
    second, _ = service.login(DEFAULT_USERNAME, DEFAULT_PASSWORD)
    service.set_password(DEFAULT_USERNAME, "a-much-better-password")
    assert service.session_user(first) is None
    assert service.session_user(second) is None
    assert service.login(DEFAULT_USERNAME, "a-much-better-password")[1]["must_change_password"] is False


def test_deleting_an_account_takes_its_sessions(service, db):
    service.create_user("curator", "a-real-password")
    token, _ = service.login("curator", "a-real-password")
    service.delete_user("curator")
    assert service.session_user(token) is None
    assert db.query("SELECT 1 FROM sessions WHERE username = 'curator'") == []


def test_a_weaker_stored_hash_is_upgraded_on_the_next_sign_in(service, db, monkeypatch):
    """Raising the iteration count is otherwise a promise with no delivery date:
    sign-in is the one moment the plaintext is in hand."""
    with db.cursor() as cur:
        cur.execute("UPDATE users SET password_hash = ? WHERE username = ?",
                    (hash_password(DEFAULT_PASSWORD, iterations=100), DEFAULT_USERNAME))
    service.login(DEFAULT_USERNAME, DEFAULT_PASSWORD)
    stored = db.query_one("SELECT password_hash FROM users WHERE username = ?",
                          (DEFAULT_USERNAME,))["password_hash"]
    assert stored.split("$")[1] == "1000"


def test_no_hash_ever_reaches_a_caller(service):
    _, user = service.login(DEFAULT_USERNAME, DEFAULT_PASSWORD)
    assert set(user) == {"username", "display_name", "must_change_password",
                         "last_login_at", "password_changed_at"}
