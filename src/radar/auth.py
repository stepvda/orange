"""Who may read the radar.

Everything the API serves is internal: competitive analysis of named companies,
Orange's own asset graph, market estimates with the workings attached, and the
stage-gate opinions of people who work here. None of it should be readable by
whoever finds the URL, and until this module existed all of it was — the app is
deployed on a public hostname and answered every request.

The shape is deliberately the boring one, because the interesting ones all cost
something this deployment cannot pay:

*   **Session cookie, not a bearer token in JavaScript.** The cookie is
    `HttpOnly`, so a script injected into the page cannot read it; a token in
    `localStorage` is readable by definition. `SameSite=Lax` is what stands in
    for a CSRF token: it stops another origin's form from posting to this API
    with the user's cookie attached, which is the only cross-site write that
    matters here.

*   **Sessions in the database, not signed and stateless.** A JWT cannot be
    revoked without server state, which puts the state back anyway — and the
    thing an operator actually wants ("sign that account out everywhere, now")
    is one `DELETE` here and impossible there. The table is tiny and the lookup
    is a primary-key hit.

*   **The token is stored as a hash.** The database is a file on a share. A copy
    of it must not be a set of live sessions, so what is stored is the SHA-256 of
    the cookie value and the value itself exists only in the browser. The same
    argument, one level up, is why passwords are PBKDF2 verifiers.

*   **PBKDF2-HMAC-SHA256, from the standard library.** Not because it is the best
    KDF — scrypt and argon2 are better — but because it is the best one available
    with no new dependency, and NFR-05's sovereign-deployment option is easier to
    keep if the auth path pulls in nothing. The iteration count follows OWASP's
    current figure and is stamped into every stored hash, so raising it later
    re-hashes each password on its next successful sign-in rather than forcing a
    reset.

The seeded account is `orange` / `orange`, flagged `must_change_password`. That
flag is not decoration: the interface shows a warning on every screen while it is
set, because a default credential nobody is reminded about is a permanent one.
"""

from __future__ import annotations

import base64
import binascii
import datetime as dt
import hashlib
import hmac
import logging
import os
import secrets
import time
from typing import Any

from .db import Database

log = logging.getLogger(__name__)

#: The cookie the browser sends back. Named rather than generic so it is obvious
#: in a jar shared with whatever else runs on the same host in development.
SESSION_COOKIE = "radar_session"

#: Seeded on an empty user table, so a fresh database is usable without a shell.
DEFAULT_USERNAME = "orange"
DEFAULT_PASSWORD = "orange"

#: OWASP's current figure for PBKDF2-HMAC-SHA256. Overridable because the tests
#: hash a dozen passwords and 600k iterations each would dominate their runtime —
#: and because a sovereign deployment on slower hardware may need to trade down
#: knowingly rather than by accident.
ITERATIONS = int(os.getenv("RADAR_PBKDF2_ITERATIONS", "600000"))

#: How long a session survives its last use, and the ceiling it cannot outlive.
#: Rolling, so working through an afternoon never signs you out mid-sentence;
#: capped, so a tab left open over a holiday does not stay signed in.
IDLE_HOURS = float(os.getenv("RADAR_SESSION_IDLE_HOURS", "12"))
ABSOLUTE_HOURS = float(os.getenv("RADAR_SESSION_MAX_HOURS", "168"))

#: Chosen passwords, not the seeded one. The seed is deliberately shorter than
#: this rule allows — it exists to be replaced, and `must_change_password` is
#: what says so.
MIN_PASSWORD_CHARS = 8

#: Failed sign-ins before an account stops answering, and for how long. Sized for
#: a fat-fingered password rather than for a script: five attempts is more than a
#: person needs and far fewer than a guesser does, and the window resets on the
#: first success.
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 300.0
ATTEMPT_WINDOW_SECONDS = 900.0


class AuthError(Exception):
    """Sign-in refused. The message is safe to show a user."""


class RateLimited(AuthError):
    """Too many failures on this account; it is closed for a while."""

    def __init__(self, seconds: int):
        self.seconds = seconds
        super().__init__(
            f"Too many failed sign-ins. Try again in {max(1, round(seconds / 60))} minute"
            f"{'' if round(seconds / 60) == 1 else 's'}."
        )


class WeakPassword(AuthError):
    """A chosen password the policy will not store."""


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _stamp(moment: dt.datetime | None = None) -> str:
    return (moment or _now()).isoformat(timespec="seconds")


def _parse(stamp: str) -> dt.datetime:
    """Read a stored timestamp, tolerating one written without a zone.

    Rows are always written by `_stamp` above, which is zoned — but a database
    hand-edited during an incident is a normal thing to meet, and a naive value
    comparing against an aware one raises `TypeError` deep inside a session
    check, which fails every request rather than the one row.
    """
    parsed = dt.datetime.fromisoformat(stamp)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------


def hash_password(password: str, *, iterations: int | None = None) -> str:
    """A verifier for `password`, in the format the `users` table stores.

    `pbkdf2_sha256$<iterations>$<salt>$<hash>` — the iteration count travels
    with the hash so it can be raised without invalidating what is already
    stored, and the salt is per-password so two accounts that chose the same
    thing do not look the same in the file.
    """
    rounds = ITERATIONS if iterations is None else iterations
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return "$".join((
        "pbkdf2_sha256",
        str(rounds),
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    ))


def verify_password(password: str, stored: str) -> bool:
    """Whether `password` produces `stored`, in constant time.

    A malformed or unknown-scheme value answers False rather than raising: the
    caller is a sign-in path, and an exception there would turn one unreadable
    row into a 500 that says more about the account than a refusal does.
    """
    try:
        scheme, rounds, salt_b64, digest_b64 = stored.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        expected = base64.b64decode(digest_b64)
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), base64.b64decode(salt_b64), int(rounds)
        )
    except (ValueError, TypeError, binascii.Error):
        return False
    return hmac.compare_digest(candidate, expected)


def needs_rehash(stored: str) -> bool:
    """Whether a stored verifier is weaker than the current setting."""
    try:
        scheme, rounds, _, _ = stored.split("$")
    except ValueError:
        return True
    return scheme != "pbkdf2_sha256" or int(rounds) < ITERATIONS


def check_password_policy(password: str) -> None:
    """Refuse a password the policy will not store, saying which rule it broke."""
    if len(password) < MIN_PASSWORD_CHARS:
        raise WeakPassword(
            f"A password needs at least {MIN_PASSWORD_CHARS} characters."
        )
    if password.strip() != password:
        # Leading or trailing whitespace survives a paste and is invisible in the
        # field, so it becomes a password nobody can retype.
        raise WeakPassword("A password cannot start or end with a space.")


# ---------------------------------------------------------------------------
# Sign-in throttling
#
# Deliberately in process memory rather than in the database. It guards a
# password guess, which is a burst measured in seconds, and the deployment is one
# worker — so a table would add writes on the hot path and a row to clean up in
# exchange for surviving a restart, which is exactly the event that also ends the
# burst.
# ---------------------------------------------------------------------------

_failures: dict[str, tuple[int, float]] = {}


def _lockout_remaining(username: str) -> float:
    count, last = _failures.get(username, (0, 0.0))
    if count < MAX_ATTEMPTS:
        return 0.0
    remaining = LOCKOUT_SECONDS - (time.monotonic() - last)
    return remaining if remaining > 0 else 0.0


def _record_failure(username: str) -> None:
    count, last = _failures.get(username, (0, 0.0))
    now = time.monotonic()
    # A wrong password this morning and another this afternoon are two accidents,
    # not an attack — so the count only accumulates inside the window.
    if now - last > ATTEMPT_WINDOW_SECONDS:
        count = 0
    _failures[username] = (count + 1, now)


def _clear_failures(username: str) -> None:
    _failures.pop(username, None)


def reset_throttle() -> None:
    """Forget every recorded failure. For tests and for an operator who has just
    unlocked an account the honest way."""
    _failures.clear()


# ---------------------------------------------------------------------------
# The service
# ---------------------------------------------------------------------------


class AuthService:
    """Accounts and sessions, over the same `Database` as everything else."""

    def __init__(self, db: Database):
        self.db = db

    # -- accounts ----------------------------------------------------------

    def ensure_seed_user(self) -> bool:
        """Create `orange` / `orange` on an empty user table. Returns whether it did.

        Conditioned on the table being EMPTY rather than on the account being
        absent, which is the difference between a convenience and a back door: an
        operator who deletes the seeded account and creates their own must not
        find it resurrected by the next restart.
        """
        row = self.db.query_one("SELECT COUNT(*) AS n FROM users")
        if row and row["n"]:
            return False
        now = _stamp()
        with self.db.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash, display_name, created_at, "
                "password_changed_at, must_change_password) VALUES (?, ?, ?, ?, ?, 1)",
                (DEFAULT_USERNAME, hash_password(DEFAULT_PASSWORD), "Orange", now, now),
            )
        log.warning(
            "Seeded the initial account '%s' with the shipped default password. "
            "Change it: radar user passwd %s", DEFAULT_USERNAME, DEFAULT_USERNAME,
        )
        return True

    def create_user(self, username: str, password: str, *,
                    display_name: str | None = None) -> dict[str, Any]:
        name = normalise_username(username)
        check_password_policy(password)
        if self.get_user(name):
            raise AuthError(f"There is already an account called '{name}'.")
        now = _stamp()
        with self.db.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash, display_name, created_at, "
                "password_changed_at, must_change_password) VALUES (?, ?, ?, ?, ?, 0)",
                (name, hash_password(password), display_name or None, now, now),
            )
        return self.get_user(name)  # type: ignore[return-value]

    def set_password(self, username: str, password: str, *,
                     revoke_sessions: bool = True) -> None:
        """Replace an account's password, and by default sign it out everywhere.

        Signing out is the point rather than a side effect. The reason to change
        a password is usually that somebody else might know the old one, and
        leaving their session alive would make the change cosmetic. The caller
        that has just re-authenticated (the change-password form) keeps its own
        session by passing it to `login` again.
        """
        name = normalise_username(username)
        check_password_policy(password)
        if not self.get_user(name):
            raise AuthError(f"No account called '{name}'.")
        now = _stamp()
        with self.db.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash = ?, password_changed_at = ?, "
                "must_change_password = 0 WHERE username = ?",
                (hash_password(password), now, name),
            )
            if revoke_sessions:
                cur.execute("DELETE FROM sessions WHERE username = ?", (name,))
        _clear_failures(name)

    def delete_user(self, username: str) -> bool:
        """Remove an account and every session it holds.

        Refuses to remove the last one: an authenticated app with no accounts is
        unreachable, and the only way back in is a shell on the database.
        """
        name = normalise_username(username)
        if not self.get_user(name):
            return False
        row = self.db.query_one("SELECT COUNT(*) AS n FROM users")
        if row and row["n"] <= 1:
            raise AuthError(
                "That is the only account. Removing it would lock everyone out — "
                "create another one first."
            )
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE username = ?", (name,))
            cur.execute("DELETE FROM users WHERE username = ?", (name,))
        _clear_failures(name)
        return True

    def get_user(self, username: str) -> dict[str, Any] | None:
        row = self.db.query_one(
            "SELECT * FROM users WHERE username = ?", (normalise_username(username),)
        )
        return dict(row) if row else None

    def list_users(self) -> list[dict[str, Any]]:
        rows = self.db.query(
            "SELECT username, display_name, created_at, password_changed_at, "
            "must_change_password, last_login_at FROM users ORDER BY username"
        )
        return [dict(row) for row in rows]

    # -- sessions ----------------------------------------------------------

    def login(self, username: str, password: str) -> tuple[str, dict[str, Any]]:
        """Verify a credential and open a session. Returns (cookie value, user).

        Every refusal raises the same `AuthError` with the same wording, whether
        the account is unknown or the password is wrong. Telling the two apart
        turns the sign-in form into a list of who works here.
        """
        name = normalise_username(username)
        remaining = _lockout_remaining(name)
        if remaining:
            raise RateLimited(int(remaining))

        user = self.get_user(name)
        # An unknown account still pays for a hash. Answering instantly when the
        # username does not exist and slowly when it does is an enumeration
        # oracle that no amount of identical wording closes.
        stored = user["password_hash"] if user else _decoy()
        if not verify_password(password, stored) or user is None:
            _record_failure(name)
            raise AuthError("That username and password do not match an account.")

        _clear_failures(name)
        now = _now()
        token = secrets.token_urlsafe(32)
        with self.db.cursor() as cur:
            cur.execute(
                "INSERT INTO sessions (token_hash, username, created_at, last_seen_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (_token_hash(token), name, _stamp(now), _stamp(now),
                 _stamp(now + dt.timedelta(hours=IDLE_HOURS))),
            )
            cur.execute("UPDATE users SET last_login_at = ? WHERE username = ?", (_stamp(now), name))
            # Raising ITERATIONS is otherwise a promise with no delivery date:
            # this is the one moment the plaintext is in hand, so an old verifier
            # is upgraded here or never.
            if needs_rehash(user["password_hash"]):
                cur.execute("UPDATE users SET password_hash = ? WHERE username = ?",
                            (hash_password(password), name))
            # Cheap and self-limiting: the table only grows by one row per
            # sign-in, so tidying it at the same rate keeps it bounded without a
            # scheduled job the deployment has nowhere to run.
            cur.execute("DELETE FROM sessions WHERE expires_at < ?", (_stamp(now),))

        return token, public_user(self.get_user(name))  # type: ignore[arg-type]

    def session_user(self, token: str | None) -> dict[str, Any] | None:
        """The account behind a cookie, or None. Extends the session on use.

        Expiry is checked in Python against the stored stamp rather than left to
        the `DELETE` in `login`: a session must stop working the moment it
        expires, not the next time somebody else signs in.
        """
        if not token:
            return None
        row = self.db.query_one(
            "SELECT s.token_hash AS session_token_hash, s.created_at AS session_created_at, "
            "s.expires_at AS session_expires_at, u.* "
            "FROM sessions s JOIN users u ON u.username = s.username WHERE s.token_hash = ?",
            (_token_hash(token),),
        )
        if row is None:
            return None
        now = _now()
        if _parse(row["session_expires_at"]) <= now:
            self.logout(token)
            return None
        if _parse(row["session_created_at"]) + dt.timedelta(hours=ABSOLUTE_HOURS) <= now:
            self.logout(token)
            return None

        # Rolling expiry, written at most once a minute. Every request would mean
        # a write per request, which on the SMB-mounted deployment locks the file
        # for the duration — for a value nobody reads at that resolution.
        fresh_until = _stamp(now + dt.timedelta(hours=IDLE_HOURS))
        if (_parse(row["session_expires_at"]) - now) < dt.timedelta(hours=IDLE_HOURS, minutes=-1):
            with self.db.cursor() as cur:
                cur.execute(
                    "UPDATE sessions SET last_seen_at = ?, expires_at = ? WHERE token_hash = ?",
                    (_stamp(now), fresh_until, row["session_token_hash"]),
                )
        return public_user(dict(row))

    def logout(self, token: str | None) -> None:
        if not token:
            return
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))

    def logout_everywhere(self, username: str) -> int:
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE username = ?", (normalise_username(username),))
            return cur.rowcount


def normalise_username(username: str) -> str:
    """One spelling per account: trimmed and lower-cased.

    Case-sensitive usernames mean 'Orange' and 'orange' are two accounts, one of
    which the person who created it cannot sign in to.
    """
    name = (username or "").strip().lower()
    if not name:
        raise AuthError("A username is required.")
    return name


def public_user(row: dict[str, Any]) -> dict[str, Any]:
    """The parts of an account a browser may see. No hash leaves this module."""
    return {
        "username": row["username"],
        "display_name": row.get("display_name") or row["username"],
        "must_change_password": bool(row.get("must_change_password")),
        "last_login_at": row.get("last_login_at"),
        "password_changed_at": row.get("password_changed_at"),
    }


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


#: Compared against when the username is unknown, so a miss costs the same as a
#: hit. Built on first use rather than at import: at the real iteration count it
#: is a third of a second, and every `radar` CLI invocation would pay it to sign
#: nobody in.
_dummy_hash: str | None = None


def _decoy() -> str:
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password(secrets.token_urlsafe(32))
    return _dummy_hash
