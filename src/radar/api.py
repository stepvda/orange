"""Read API (FR-27, pipeline stage 7).

FR-27: "Expose a read API so that topic data can be consumed by other Orange
tools." It is priority C in the requirements, but the React frontend needs it,
so it is built now and serves both.

Reads never write. Scores and topic content are still the pipeline's job, and
keeping that boundary sharp is what makes SC-11 reproducibility checkable — but
the write paths have grown past the two the requirements named (feedback capture
under FR-23/FR-34/DR-15, curator link confirmation under LK-06) to include the
derived artefacts a curator asks for by pressing a button, generation runs, and
removing a space outright.

Every `/api` path here requires a session (`radar.auth`). The bundle and the app
shell do not: the login screen has to load before anyone can sign in, and there
is nothing in a JavaScript file worth protecting. `/docs` and `/openapi.json` are
FastAPI's own routes rather than this router's, so they stay open too — they
describe the shape of the API and serve none of its data.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from . import auth, bootstrap, deletion, internal
from .brief import BriefBuilder, brief_for_topic, brief_path
from .competition import CompetitionAnalyser, LEVEL_MEANING, competition_for_topic
from .config import get_config
from .db import Database, js, unjs
from .generation import (MAX_BRIEF_CHARS, MAX_BRIEFS_PER_RUN, MAX_PER_RUN, MIN_BRIEF_CHARS,
                         GenerationService)
from .graph import LINK_MEANING, Linker
from .pipeline.synthesis import GenerationConstraints
from .llm import LLMClient
from .pipeline.describe import DescriptionGenerator, description_for_topic
from .presales import (PreSalesBuilder, collateral_for_topic, collateral_path,
                       entry as collateral_entry, item_for as collateral_item,
                       resolve_format as collateral_format)
from .reference import ReferenceDataFetcher, reference_status
from .scoping import MAX_MESSAGE_CHARS, MAX_MESSAGES, ScopingError, ScopingService
from .sizing import MarketSizer, sizes_for_topic
from .workflow import (AXIS_ANCHORS, AXIS_LABELS, ROLE_AXIS, STAGE_LABELS,
                       STAGE_OWNER_ROLE, STAGES, WorkflowService)
from .readmodel import (NOT_A_GENERATION, SORTS, ReadModel, facet_counts, matches_filters,
                        refresh_kind, topic_for_list)

log = logging.getLogger(__name__)

#: `/api` paths that answer before anybody has signed in. Everything else is
#: behind `require_session` below.
#:
#: `session` is public and always 200 rather than 401-when-anonymous: it is the
#: probe the frontend runs on every load, and a route whose *normal* answer for a
#: signed-out visitor is an error makes a signed-out visitor indistinguishable
#: from a broken server, in the logs and in the browser console alike.
PUBLIC_API_PATHS = frozenset({
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/session",
})


def require_session(request: Request) -> None:
    """Refuse an `/api` request that carries no valid session.

    Mounted as an application-level dependency rather than as middleware, for two
    reasons. It runs INSIDE FastAPI's exception handling, so a refusal is an
    ordinary `HTTPException` with a `detail` the frontend already knows how to
    read, and it is inside the CORS middleware, so a refusal still carries the
    headers that let a browser see it. It also does not apply to the mounted
    static files, which is correct: the bundle is not a secret and the login
    screen is part of it.

    Non-`/api` paths pass straight through — the app shell, the assets, and the
    platform's liveness probe.
    """
    path = request.url.path
    if not path.startswith("/api/") or path in PUBLIC_API_PATHS:
        return
    try:
        user = _auth.session_user(request.cookies.get(auth.SESSION_COOKIE))
    except Exception as exc:  # noqa: BLE001
        # The session table lives in the same file as everything else, so an
        # unusable database fails here first — for every route at once. A 503
        # naming the startup error is diagnosable; a stack trace per endpoint is
        # the same fault reported forty different ways.
        log.error("Session lookup failed: %s", exc)
        raise HTTPException(503, bootstrap.STARTUP_ERROR
                            or f"The radar cannot read its session store: {exc}") from exc
    if user is None:
        raise HTTPException(401, "Your session has ended. Sign in to continue.")
    # Endpoints that need to know who is asking read it from here rather than
    # taking a second dependency and a second lookup.
    request.state.user = user


app = FastAPI(
    title="Orange Business Innovation Radar",
    description="Read API for the Opportunity Spaces / Innovation Radar MVP.",
    version="0.1.0",
    dependencies=[Depends(require_session)],
)

# The React dev server runs on a different origin. In production the built
# bundle is served from THIS app (see the static mount at the bottom of this
# file), so the deployed origin needs no CORS entry at all — the list stays
# scoped to the local dev servers.
#
# `allow_credentials` is on because the session lives in a cookie and a
# cross-origin fetch drops cookies without it. That combination is only safe
# against an explicit origin list — never against `*` — which is what this is.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                   "http://localhost:5174", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

_cfg = get_config()
# Prepare persistent storage BEFORE opening the database. On App Service the
# database lives on an SMB share that cannot host a WAL journal, and the file
# has to be seeded from the deployment package on first boot — see
# radar.bootstrap for why both of those are done here rather than in a shell
# script wrapped around the process.
bootstrap.prepare(Path(_cfg.db_path), Path(__file__).resolve().parents[2])

try:
    _db = Database(_cfg.db_path)
except Exception as exc:  # noqa: BLE001 — an unusable path must not kill the import
    bootstrap.STARTUP_ERROR = f"{type(exc).__name__}: {exc}"
    log.error("Database path unusable (%s); serving in a degraded state", exc)
    _db = Database(Path(tempfile.gettempdir()) / "radar-unavailable.db")

try:
    # Idempotent, and it means a database created before the sizing, competition
    # and brief tables existed still serves those endpoints rather than 500ing
    # on a missing table.
    _db.init_schema()
except Exception as exc:  # noqa: BLE001
    # NOT fatal. A process that raises at import is restarted by the platform,
    # and enough restarts exhaust a Free plan's quota — which also disables the
    # log endpoints, so the failure hides its own cause. Recording it and
    # answering 503 with the reason is strictly more useful than dying.
    bootstrap.STARTUP_ERROR = f"{type(exc).__name__}: {exc}"
    log.error("Database initialisation failed: %s", exc)

_read = ReadModel(_cfg, _db)
_workflow = WorkflowService(_cfg, _db)
_auth = auth.AuthService(_db)

try:
    # A fresh database has no accounts, and an app nobody can sign in to is
    # indistinguishable from a broken one. Seeding runs only against an EMPTY
    # user table — see `ensure_seed_user` for why that distinction matters.
    _auth.ensure_seed_user()
except Exception as exc:  # noqa: BLE001 — same rule as the schema call above
    bootstrap.STARTUP_ERROR = bootstrap.STARTUP_ERROR or f"{type(exc).__name__}: {exc}"
    log.error("Could not seed the initial account: %s", exc)


def _llm() -> LLMClient:
    """Built per request rather than at import: a missing API key should fail
    the one call that needs a model, not the whole read API."""
    return LLMClient(max_retries=_cfg.settings["llm"]["max_retries"])


def _vocab_payload(vocab) -> list[dict[str, Any]]:
    return [
        {"id": item.id, "label": item.label, "definition": item.definition}
        for item in vocab
    ]


class LoginIn(BaseModel):
    # Bounded so a sign-in attempt cannot be used to post a megabyte into the
    # hashing function. 256 is far past any real password and far short of a
    # denial-of-service.
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


def _cookie_secure(request: Request) -> bool:
    """Whether to mark the session cookie `Secure`.

    Marking it `Secure` over plain HTTP means the browser silently discards it
    and nobody can sign in; NOT marking it in production means the session
    travels in clear over any downgraded hop. Neither is a safe default, so the
    scheme is read from the request — via `x-forwarded-proto` first, because App
    Service terminates TLS at the front end and the origin request arrives as
    HTTP. `RADAR_COOKIE_SECURE` overrides both for a deployment that knows
    better than the headers do.
    """
    override = os.getenv("RADAR_COOKIE_SECURE")
    if override is not None:
        return override.strip().lower() in {"1", "true", "yes", "on"}
    forwarded = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    return (forwarded or request.url.scheme) == "https"


def _set_session_cookie(response: Response, request: Request, token: str) -> None:
    response.set_cookie(
        auth.SESSION_COOKIE, token,
        max_age=int(auth.IDLE_HOURS * 3600),
        # HttpOnly so an injected script cannot read the session; SameSite=Lax so
        # another origin's form cannot post here with the cookie attached, which
        # is the CSRF defence this API relies on instead of a token.
        httponly=True, samesite="lax", path="/",
        secure=_cookie_secure(request),
    )


@app.post("/api/auth/login")
def login(payload: LoginIn, request: Request, response: Response) -> dict[str, Any]:
    """Exchange a username and password for a session cookie.

    Public by construction — it is the one door — and throttled per account, so
    the door is not also a guessing machine.
    """
    try:
        token, user = _auth.login(payload.username, payload.password)
    except auth.RateLimited as exc:
        raise HTTPException(429, str(exc)) from exc
    except auth.AuthError as exc:
        # 401 rather than 400: the credential was understood and rejected.
        raise HTTPException(401, str(exc)) from exc
    _set_session_cookie(response, request, token)
    return {"user": user}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response) -> dict[str, Any]:
    """End this session and clear the cookie.

    Public and idempotent. Requiring a session to sign out means an expired one
    cannot be cleaned up, which leaves a dead cookie in the browser and a user
    looking at a screen that will not let them in or out.
    """
    _auth.logout(request.cookies.get(auth.SESSION_COOKIE))
    response.delete_cookie(auth.SESSION_COOKIE, path="/")
    return {"signed_out": True}


@app.get("/api/auth/session")
def session(request: Request) -> dict[str, Any]:
    """Who is signed in, if anyone. Always 200 — see `PUBLIC_API_PATHS`."""
    user = _auth.session_user(request.cookies.get(auth.SESSION_COOKIE))
    return {
        "authenticated": user is not None,
        "user": user,
        # The frontend shows the password rules beside the field it enforces
        # them on, rather than discovering them from a rejection.
        "password_policy": {"min_length": auth.MIN_PASSWORD_CHARS},
    }


@app.post("/api/auth/password")
def change_password(payload: PasswordChangeIn, request: Request,
                    response: Response) -> dict[str, Any]:
    """Change the signed-in account's password.

    The current password is required even though the session already proves
    identity: the session may be an unlocked laptop, and a password change is
    the one action that locks its owner out.

    Every OTHER session for the account is ended — the usual reason to change a
    password is that somebody else might know the old one — and this one is
    reissued, so the person who just typed it correctly twice is not signed out
    of the tab they did it in.
    """
    user = getattr(request.state, "user", None)
    if user is None:  # pragma: no cover — require_session has already run
        raise HTTPException(401, "Sign in to change a password.")
    try:
        _auth.login(user["username"], payload.current_password)
    except auth.AuthError as exc:
        raise HTTPException(403, "That is not the current password.") from exc
    try:
        _auth.set_password(user["username"], payload.new_password)
        token, refreshed = _auth.login(user["username"], payload.new_password)
    except auth.AuthError as exc:
        raise HTTPException(400, str(exc)) from exc
    _set_session_cookie(response, request, token)
    return {"user": refreshed, "signed_out_elsewhere": True}


@app.get("/api/meta")
def meta() -> dict[str, Any]:
    """Controlled vocabularies, role modes and filter dimensions (AC-04, FR-12)."""
    # AC-02 freshness is a claim about when evidence was last COLLECTED, so an
    # on-demand generation run is excluded: it reorganises the corpus it was
    # given and would otherwise stamp today's date over a six-week-old one.
    last = _db.query_one(
        "SELECT id, started_at, finished_at, reference_date, is_replay, weight_set "
        f"FROM refreshes WHERE {NOT_A_GENERATION} ORDER BY started_at DESC LIMIT 1"
    )
    return {
        "verticals": _vocab_payload(_cfg.verticals),
        "use_cases": _vocab_payload(_cfg.use_cases),
        "technologies": _vocab_payload(_cfg.technologies),
        "domains": _vocab_payload(_cfg.domains),
        "personas": _vocab_payload(_cfg.personas),
        "signal_types": _vocab_payload(_cfg.signal_types),
        "market_clusters": [
            {
                "id": item.id,
                "label": item.label,
                "countries": list(item.extra["members"]),
                # Whether Orange named this grouping or we inferred it. Surfaced
                # so the UI can mark the inferred ones rather than presenting
                # every cluster as equally authoritative.
                "source": item.extra["source"],
                "scope": item.extra["scope"],
            }
            for item in _cfg.market_clusters
        ],
        "horizons": ["now", "next", "later"],
        "states": ["candidate", "watchlist", "active", "fading", "dormant", "rejected"],
        "link_types": [
            {"id": key, "meaning": value[0], "definition": value[1], "owner": value[2], "action": value[3]}
            for key, value in LINK_MEANING.items()
        ],
        "roles": [
            {
                "id": mode["id"],
                "label": mode["label"],
                "description": mode["description"],
                "primary_action": mode["primary_action"],
                "link_types": mode["link_types"],
                "acceptance": mode.get("acceptance"),
                "ranking": mode["ranking"],
            }
            for mode in _cfg.role_modes_raw["modes"]
        ],
        "sorts": [{"id": key, "label": label} for key, label in SORTS.items()],
        "competition_levels": [
            {"id": level, "meaning": meaning} for level, meaning in LEVEL_MEANING.items()
        ],
        "sizing_version": _cfg.sizing_version,
        "competitor_register_version": _cfg.competitor_version,
        "weight_set": _cfg.weight_set,
        "attractiveness_weights": _cfg.attractiveness_weights,
        "right_to_win_weights": _cfg.right_to_win_weights,
        "pipeline_version": _cfg.pipeline_version,
        "last_refresh": dict(last) if last else None,
        "strategy": {
            "plan": _cfg.strategy["plan"],
            "period": _cfg.strategy["period"],
            "ambitions": [
                {"id": a["id"], "label": a["label"], "implication": a["radar_implication"]}
                for a in _cfg.strategy["ambitions"]
            ],
            "privileged_verticals": _cfg.strategy.get("privileged_verticals", {}),
        },
    }


@app.get("/api/view")
def view(
    role: str = Query("strategist"),
    vertical: list[str] | None = Query(None),
    domain: list[str] | None = Query(None),
    persona: list[str] | None = Query(None),
    geography: list[str] | None = Query(None),
    market_cluster: list[str] | None = Query(None),
    horizon: list[str] | None = Query(None),
    state: list[str] | None = Query(None),
    competition: list[str] | None = Query(None),
    has_brief: bool = Query(False),
    q: str | None = Query(None),
    limit: int | None = Query(None),
    sort: str = Query("rank"),
) -> dict[str, Any]:
    """The capped, filtered, role-ranked radar view (FR-13, FR-21, FR-22, AC-05)."""
    if role not in _cfg.role_ids:
        raise HTTPException(400, f"Unknown role {role!r}. Known: {_cfg.role_ids}")
    if sort not in SORTS:
        raise HTTPException(400, f"Unknown sort {sort!r}. Known: {list(SORTS)}")
    filters = {
        key: value
        for key, value in (
            ("vertical", vertical), ("domain", domain), ("persona", persona),
            ("geography", geography), ("market_cluster", market_cluster),
            ("horizon", horizon), ("state", state),
            ("competition", competition), ("has_brief", has_brief or None), ("q", q),
        )
        if value
    }
    return _read.view(role, filters, limit, sort=sort)


@app.get("/api/topics/{topic_id}")
def topic(topic_id: str) -> dict[str, Any]:
    """Topic detail with the full score decomposition (NFR-01, NFR-02, NFR-03)."""
    result = _read.topic(topic_id)
    if result is None:
        raise HTTPException(404, f"No such topic: {topic_id}")
    return result


@app.get("/api/topics/{topic_id}/history")
def history(topic_id: str) -> dict[str, Any]:
    """Score trajectory with the weight-set comparability warning (FR-20, §4.6)."""
    return _read.history(topic_id)


@app.get("/api/topics/{topic_id}/deletion-impact")
def topic_deletion_impact(topic_id: str) -> dict[str, Any]:
    """Everything a delete would take with it, without taking any of it.

    A `GET` that reads and returns, so it sits inside the read-only rule. It
    exists because the confirmation dialog has to name the consequence — thirteen
    tables point at a space, and "are you sure?" over a number nobody was shown
    is not a confirmation.
    """
    try:
        return deletion.deletion_impact(_db, topic_id)
    except deletion.TopicNotFound as exc:
        raise HTTPException(404, f"No such topic: {topic_id}") from exc


@app.delete("/api/topics/{topic_id}")
def delete_topic(topic_id: str, request: Request) -> dict[str, Any]:
    """Remove an opportunity space and everything attached to it.

    The report it returns is the impact computed a moment before the delete, so
    the caller can say what actually went rather than that something did. See
    `radar.deletion` for what travels with a space, what deliberately does not
    (the signals — they are shared evidence), and why a space that sat in a
    portfolio plan is reported rather than refused.
    """
    try:
        report = deletion.delete_topic(_db, topic_id)
    except deletion.TopicNotFound as exc:
        raise HTTPException(404, f"No such topic: {topic_id}") from exc
    user = getattr(request.state, "user", None)
    log.warning("%s deleted opportunity space %s",
                (user or {}).get("username", "unknown"), topic_id)
    return {**report, "deleted_by": (user or {}).get("username")}


@app.get("/api/whitespace")
def whitespace(
    min_attractiveness: float = Query(55.0),
    vertical: list[str] | None = Query(None),
    domain: list[str] | None = Query(None),
    persona: list[str] | None = Query(None),
    geography: list[str] | None = Query(None),
    market_cluster: list[str] | None = Query(None),
    horizon: list[str] | None = Query(None),
    competition: list[str] | None = Query(None),
    q: str | None = Query(None),
) -> dict[str, Any]:
    """High attractiveness, no path from the portfolio (FR-32, §4.5.5).

    Takes the same filters as the radar view: the rail is on screen on this tab
    too, and a control that is offered has to work.
    """
    filters = {
        key: value
        for key, value in (
            ("vertical", vertical), ("domain", domain), ("persona", persona),
            ("geography", geography), ("market_cluster", market_cluster),
            ("horizon", horizon), ("competition", competition), ("q", q),
        )
        if value
    }
    unfiltered = _read.white_space(min_attractiveness)
    rows = _read.white_space_filtered(min_attractiveness, filters)
    return {"min_attractiveness": min_attractiveness, "count": len(rows),
            "total_unfiltered": len(unfiltered), "topics": rows}


@app.get("/api/orphan-offers")
def orphan_offers() -> dict[str, Any]:
    """Offers with no live opportunity space — a portfolio-decay signal (FR-33)."""
    rows = Linker(_cfg, _db).offers_without_topics()
    return {"count": len(rows), "offers": rows}


@app.get("/api/coverage")
def coverage() -> dict[str, Any]:
    """Language, geography, tier and source coverage as a reported metric (NFR-08)."""
    return _read.coverage()


@app.get("/api/refreshes")
def refreshes(limit: int = Query(20)) -> dict[str, Any]:
    """Refresh log (FR-19, NFR-04, NFR-10)."""
    rows = _db.query(
        "SELECT id, started_at, finished_at, reference_date, is_replay, pipeline_version, weight_set "
        "FROM refreshes ORDER BY started_at DESC LIMIT ?", (limit,)
    )
    # Generation runs ARE listed here — this endpoint is the log, and hiding a
    # write from the log would be the wrong kind of tidy. They are labelled
    # instead, because a run that collected nothing is a different event.
    return {"refreshes": [dict(r) | {"kind": refresh_kind(r["id"])} for r in rows]}


@app.get("/api/graph/node/{node_id:path}")
def graph_node(node_id: str) -> dict[str, Any]:
    """Reverse query: which topics attach to this asset (LK-09)."""
    node = _db.query_one("SELECT * FROM graph_nodes WHERE id = ?", (node_id,))
    if node is None:
        raise HTTPException(404, f"No such node: {node_id}")
    rows = _db.query(
        """SELECT o.id, o.statement, o.state, l.link_type, l.confidence
           FROM opportunity_links l JOIN opportunity_spaces o ON o.id = l.opportunity_id
           WHERE l.node_id = ? AND l.rejected = 0 AND o.merged_into IS NULL""",
        (node_id,),
    )
    return {"node": dict(node), "topics": [dict(r) for r in rows]}


# ---------------------------------------------------------------------------
# Write paths — feedback and curation only
# ---------------------------------------------------------------------------


class FeedbackIn(BaseModel):
    role: str
    kind: str = Field(description="rating | comparison | override | engagement")
    opportunity_id: str | None = None
    other_opportunity_id: str | None = None
    verdict: str | None = Field(None, description="useful|not_useful|wrong for ratings; left|right for comparisons")
    reason: str | None = None
    exposure_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Rank shown, view, filters, exploration slot. Required by DR-15 so engagement "
                    "can be inverse-propensity weighted against exposure bias (§4.7.6).",
    )


@app.post("/api/feedback")
def submit_feedback(payload: FeedbackIn) -> dict[str, Any]:
    """FR-23 / FR-34 / DR-15.

    §4.7.4: "ask for comparisons, not scores. People are unreliable at rating a
    topic 73 out of 100 and reliable at saying which of two topics they would
    rather take into a meeting." Both shapes are accepted; the comparison shape
    is the one that produces usable ranking labels.
    """
    if payload.role not in _cfg.role_ids:
        raise HTTPException(400, f"Unknown role {payload.role!r}")
    if payload.kind not in ("rating", "comparison", "override", "engagement"):
        raise HTTPException(400, f"Unknown feedback kind {payload.kind!r}")
    if payload.kind == "comparison" and not payload.other_opportunity_id:
        raise HTTPException(400, "A comparison needs other_opportunity_id")

    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    with _db.cursor() as cur:
        cur.execute(
            """INSERT INTO feedback (created_at, role, kind, opportunity_id, other_opportunity_id,
                                     verdict, reason, exposure_context)
               VALUES (?,?,?,?,?,?,?,?)""",
            (now, payload.role, payload.kind, payload.opportunity_id, payload.other_opportunity_id,
             payload.verdict, payload.reason, js(payload.exposure_context)),
        )
    return {"stored": True, "at": now}


@app.get("/api/feedback/stats")
def feedback_stats() -> dict[str, Any]:
    """How close the learned-ranking model is to being trainable (§4.7.4).

    "Roughly three to six hundred comparisons per role is enough to fit a ranker
    over the feature set above."
    """
    rows = _db.query(
        "SELECT role, kind, COUNT(*) AS n FROM feedback GROUP BY role, kind"
    )
    by_role: dict[str, dict[str, int]] = {}
    for row in rows:
        by_role.setdefault(row["role"], {})[row["kind"]] = row["n"]
    return {
        "by_role": by_role,
        "comparisons_needed_per_role": {"min": 300, "max": 600},
        "note": "Problem A (relevance ranking) needs human labels; Problem B "
                "(emergence forecasting) is self-supervised from historical replay (§4.7.2).",
    }


class LinkDecisionIn(BaseModel):
    pattern: str
    decision: str = Field(description="confirmed | rejected")
    curator: str
    reason: str | None = None


@app.post("/api/links/decision")
def link_decision(payload: LinkDecisionIn) -> dict[str, Any]:
    """LK-06 — curator confirmation of a link pattern.

    "Confirmations and rejections are stored and become training data" (§4.5.4).
    The decision takes effect on the next `link` stage run.
    """
    if payload.decision not in ("confirmed", "rejected"):
        raise HTTPException(400, "decision must be 'confirmed' or 'rejected'")
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    with _db.cursor() as cur:
        cur.execute(
            "INSERT OR REPLACE INTO link_pattern_decisions (pattern, decision, curator, reason, decided_at) "
            "VALUES (?,?,?,?,?)",
            (payload.pattern, payload.decision, payload.curator, payload.reason, now),
        )
    return {"stored": True, "applies_on": "next `radar refresh --stages link` run"}


@app.get("/api/health")
def health() -> dict[str, Any]:
    counts = {}
    for table in ("signals", "opportunity_spaces", "graph_nodes", "opportunity_links", "feedback"):
        row = _db.query_one(f"SELECT COUNT(*) AS n FROM {table}")
        counts[table] = row["n"] if row else 0
    return {"ok": True, "counts": counts, "weight_set": _cfg.weight_set}


# ---------------------------------------------------------------------------
# Collaboration workflow (FR-25, §4.10)
# ---------------------------------------------------------------------------


@app.get("/api/workflow/board")
def workflow_board(role: str | None = Query(None)) -> dict[str, Any]:
    """Stage-gate board (§4.10 model A).

    Optionally ranked for a role, so a stage owner sees their column in their
    own priority order rather than an arbitrary one.
    """
    topics = _read.topics(states=("active", "watchlist", "fading", "candidate"))
    if role:
        if role not in _cfg.role_ids:
            raise HTTPException(400, f"Unknown role {role!r}")
        # Order for the role, but do NOT filter: the board is a workflow view,
        # and a stage owner has to see everything in their column.
        topics = _read.rank(topics, role, apply_role_filter=False)
    return _workflow.board(topics)


@app.get("/api/workflow/meta")
def workflow_meta() -> dict[str, Any]:
    """Stages, per-role axes and the rating anchors the UI renders."""
    return {
        "stages": [
            {"id": s, "label": STAGE_LABELS[s], "owner_role": STAGE_OWNER_ROLE.get(s)}
            for s in STAGES
        ],
        "terminal_stages": [
            {"id": s, "label": STAGE_LABELS[s]} for s in ("parked", "rejected")
        ],
        "role_axis": ROLE_AXIS,
        "axis_labels": AXIS_LABELS,
        "anchors": AXIS_ANCHORS,
        "divergence_threshold": _cfg.settings["workflow"]["divergence_threshold"],
        "conviction_ranking_weight": _cfg.settings["workflow"]["conviction_ranking_weight"],
    }


class AssessmentIn(BaseModel):
    role: str = Field(description="strategist | sales | presales")
    rating: int = Field(ge=0, le=5)
    author: str
    confidence: int = Field(3, ge=1, le=5)
    rationale: str | None = None


@app.post("/api/topics/{topic_id}/assessment")
def submit_assessment(topic_id: str, payload: AssessmentIn) -> dict[str, Any]:
    """§4.10 model C — each role rates its own axis.

    §4.7.4: "ask for comparisons, not scores ... People are unreliable at rating
    a topic 73 out of 100". Hence a 0-5 scale with written anchors, and a
    separate confidence, rather than a free percentage.
    """
    if _read.topic(topic_id) is None:
        raise HTTPException(404, f"No such topic: {topic_id}")
    try:
        conviction = _workflow.record_assessment(
            topic_id, payload.role, payload.rating, payload.author,
            payload.confidence, payload.rationale,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    topic = _read.topic(topic_id)
    return {
        "conviction": conviction,
        "divergence": topic.get("divergence"),
        "attractiveness": (topic.get("attractiveness") or {}).get("score"),
        "right_to_win": (topic.get("right_to_win") or {}).get("score"),
    }


class TransitionIn(BaseModel):
    to_stage: str
    actor: str
    actor_role: str
    reason: str | None = None
    owner: str | None = None


@app.post("/api/topics/{topic_id}/stage")
def move_stage(topic_id: str, payload: TransitionIn) -> dict[str, Any]:
    """Advance, park or reject a topic in the stage gate (§4.10 model A)."""
    if _read.topic(topic_id) is None:
        raise HTTPException(404, f"No such topic: {topic_id}")
    try:
        return _workflow.transition(
            topic_id, payload.to_stage, payload.actor, payload.actor_role,
            payload.reason, payload.owner,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/topics/{topic_id}/transitions")
def transitions(topic_id: str) -> dict[str, Any]:
    rows = _db.query(
        "SELECT * FROM workflow_transitions WHERE opportunity_id = ? ORDER BY created_at DESC",
        (topic_id,),
    )
    return {"transitions": [dict(r) for r in rows]}


@app.get("/api/divergence")
def divergence_review() -> dict[str, Any]:
    """§4.10 model C: "disagreement becomes information rather than friction".

    The review queue — topics where the team and the evidence disagree enough to
    be worth a human looking.
    """
    out = []
    for topic in _read.topics(states=("active", "watchlist", "fading", "candidate")):
        if topic.get("divergence"):
            out.append({
                "id": topic["id"],
                "statement": topic["statement"],
                "attractiveness": (topic.get("attractiveness") or {}).get("score"),
                "right_to_win": (topic.get("right_to_win") or {}).get("score"),
                "conviction": topic.get("conviction"),
                "divergence": topic["divergence"],
                "workflow": topic.get("workflow"),
            })
    out.sort(key=lambda t: max(abs(f["delta"]) for f in t["divergence"]["flags"]), reverse=True)
    return {"count": len(out), "topics": out}


# ---------------------------------------------------------------------------
# Aggregates for the charts
# ---------------------------------------------------------------------------


@app.get("/api/analytics/grid")
def analytics_grid() -> dict[str, Any]:
    """Vertical x domain occupancy, with reference density per vertical.

    This is the white-space map §4.5.5 asks for, as a grid rather than a
    document: where topics exist, and where Orange has proof points to sell them.
    """
    topics = _read.topics(states=("active", "watchlist", "fading", "candidate"))
    verticals = [v.id for v in _cfg.verticals]
    domains = [d.id for d in _cfg.domains]
    cells: dict[str, dict[str, Any]] = {}
    for topic in topics:
        for domain in topic["domains"]:
            key = f"{topic['triple']['vertical']}|{domain}"
            cell = cells.setdefault(key, {"count": 0, "best_attractiveness": 0.0, "gap": False})
            cell["count"] += 1
            cell["best_attractiveness"] = max(
                cell["best_attractiveness"], (topic.get("attractiveness") or {}).get("score", 0.0)
            )
            cell["gap"] = cell["gap"] or topic["evidence_gap_warning"]
    return {
        "verticals": [{"id": v.id, "label": v.label} for v in _cfg.verticals],
        "domains": [{"id": d.id, "label": d.label} for d in _cfg.domains],
        "cells": cells,
        "max_count": max([c["count"] for c in cells.values()], default=0),
    }


@app.get("/api/analytics/summary")
def analytics_summary() -> dict[str, Any]:
    """Headline counts for the KPI row, plus the distributions the charts use."""
    def counts(sql: str) -> dict[str, int]:
        return {str(r[0]): r[1] for r in _db.query(sql)}

    topics = _read.topics(states=("active", "watchlist", "fading", "candidate"))
    distance = {}
    for topic in topics:
        key = f"L{topic['portfolio_distance']}"
        distance[key] = distance.get(key, 0) + 1

    signal_ages = _db.query(
        "SELECT published_at, COUNT(*) n FROM signals WHERE relevance > 0 "
        "GROUP BY published_at ORDER BY published_at"
    )
    stages = _db.query("SELECT stage, COUNT(*) n FROM workflow_state GROUP BY stage")
    assessed = _db.query_one(
        "SELECT COUNT(DISTINCT opportunity_id) n FROM assessments WHERE superseded = 0"
    )
    return {
        "topics": len(topics),
        "signals": _db.query_one("SELECT COUNT(*) n FROM signals")["n"],
        "relevant_signals": _db.query_one("SELECT COUNT(*) n FROM signals WHERE relevance > 0")["n"],
        "sources": _db.query_one("SELECT COUNT(DISTINCT source_id) n FROM signals")["n"],
        "links": _db.query_one("SELECT COUNT(*) n FROM opportunity_links WHERE rejected = 0")["n"],
        "topics_assessed": assessed["n"] if assessed else 0,
        "by_state": counts("SELECT state, COUNT(*) FROM opportunity_spaces GROUP BY state"),
        "by_horizon": counts("SELECT horizon, COUNT(*) FROM opportunity_spaces WHERE horizon IS NOT NULL GROUP BY horizon"),
        "by_distance": distance,
        "by_stage": {r["stage"]: r["n"] for r in stages},
        "by_tier": counts("SELECT tier, COUNT(*) FROM signals GROUP BY tier"),
        "by_signal_type": counts(
            "SELECT COALESCE(signal_type,'unclassified'), COUNT(*) FROM signals WHERE relevance > 0 GROUP BY 1"
        ),
        "by_language": counts("SELECT language, COUNT(*) FROM signals GROUP BY language"),
        "by_source": counts("SELECT source_id, COUNT(*) FROM signals GROUP BY source_id"),
        "signal_timeline": [{"date": r["published_at"], "n": r["n"]} for r in signal_ages],
    }


@app.get("/api/topics/{topic_id}/evidence-timeline")
def evidence_timeline(topic_id: str) -> dict[str, Any]:
    """Signal accretion over time — momentum made visible (§4.6, §4.4.5).

    "Momentum is simply the trajectory of signal accretion, which is honest and
    explainable." This endpoint is that trajectory, so the UI can show the shape
    the momentum component actually measured rather than only its output number.
    """
    rows = _db.query(
        """SELECT s.published_at, s.tier, s.signal_type, s.publisher
           FROM signals s JOIN opportunity_signals os ON os.signal_id = s.id
           WHERE os.opportunity_id = ? ORDER BY s.published_at""",
        (topic_id,),
    )
    buckets: dict[str, dict[str, Any]] = {}
    for row in rows:
        month = (row["published_at"] or "")[:7]
        if not month:
            continue
        bucket = buckets.setdefault(month, {"month": month, "n": 0, "by_type": {}})
        bucket["n"] += 1
        stype = row["signal_type"] or "unclassified"
        bucket["by_type"][stype] = bucket["by_type"].get(stype, 0) + 1
    return {
        "topic_id": topic_id,
        "total": len(rows),
        "distinct_publishers": len({r["publisher"] for r in rows}),
        "months": [buckets[k] for k in sorted(buckets)],
    }


# ---------------------------------------------------------------------------
# Market size, competition, description and the PDF brief
# (§4.3.4, §4.3.3, FR-18)
#
# These are generation endpoints, so they are POSTs, and they are the only
# writes in the API besides feedback and curation. They write derived artefacts
# — a size, an assessment, a description, a PDF — and never a score or a topic,
# so the boundary that makes SC-11 reproducibility checkable still holds.
# ---------------------------------------------------------------------------


@app.get("/api/topics/{topic_id}/market-size")
def market_size(topic_id: str) -> dict[str, Any]:
    """Every stored estimate for a topic, factor by factor (§4.3.4)."""
    if _read.topic(topic_id) is None:
        raise HTTPException(404, f"No such topic: {topic_id}")
    return {"topic_id": topic_id, "estimates": sizes_for_topic(_db, topic_id)}


@app.post("/api/topics/{topic_id}/market-size")
def recompute_market_size(topic_id: str) -> dict[str, Any]:
    """Recompute from the reference data currently in the store."""
    if _read.topic(topic_id) is None:
        raise HTTPException(404, f"No such topic: {topic_id}")
    MarketSizer(_cfg, _db).run(topic_ids=[topic_id])
    return {"topic_id": topic_id, "estimates": sizes_for_topic(_db, topic_id)}


@app.get("/api/reference-data")
def reference_data() -> dict[str, Any]:
    """What the sizing engine has to work with, and how old it is (NFR-08)."""
    return reference_status(_db)


@app.post("/api/reference-data/refresh")
def refresh_reference_data(force: bool = Query(False)) -> dict[str, Any]:
    """Refetch Eurostat. Annual statistics, so this is rarely needed."""
    return ReferenceDataFetcher(_cfg, _db).run(force=force)


@app.get("/api/topics/{topic_id}/competition")
def competition(topic_id: str) -> dict[str, Any]:
    """Named competitors and the computed intensity level (§4.3.3)."""
    if _read.topic(topic_id) is None:
        raise HTTPException(404, f"No such topic: {topic_id}")
    stored = competition_for_topic(_db, topic_id)
    if stored is None:
        CompetitionAnalyser(_cfg, _db).run(topic_ids=[topic_id])
        stored = competition_for_topic(_db, topic_id)
    return stored or {}


@app.post("/api/topics/{topic_id}/competition")
def recompute_competition(topic_id: str) -> dict[str, Any]:
    if _read.topic(topic_id) is None:
        raise HTTPException(404, f"No such topic: {topic_id}")
    CompetitionAnalyser(_cfg, _db).run(topic_ids=[topic_id])
    return competition_for_topic(_db, topic_id) or {}



# ---------------------------------------------------------------------------
# The Planner (strategy engine)
# ---------------------------------------------------------------------------


class PlanIn(BaseModel):
    label: str = "Untitled plan"
    objective: str = "profit"
    plan_years: int = 5
    # Where the set comes from. `parameters` lets the optimiser choose under the
    # constraints below; `workflow` takes what the stage gate already decided
    # and ignores every constraint that would second-guess it.
    source: str = "parameters"
    from_stage: str = "demand_tested"
    budget_person_years: float | None = None
    entry_slots_per_year: int | None = None
    pool_availability: float | None = None
    min_confidence: str = "partial"
    max_portfolio_distance: int = 3
    geographies: list[str] = []
    exclude_verticals: list[str] = []
    exclude_technologies: list[str] = []
    prefer_verticals: list[str] = []
    prefer_domains: list[str] = []
    max_share_per_vertical: float | None = None
    max_share_per_technology: float | None = None
    max_competition: str | None = None


@app.get("/api/planner/meta")
def planner_meta() -> dict[str, Any]:
    """Everything the plan form needs: the assumption set, and what is plannable.

    The assumptions are served rather than hard-coded into the frontend because
    they are configuration with an owner, and a form that silently disagreed
    with the engine would be worse than no form.
    """
    econ = _cfg.economics or {}
    plannable = _db.query_one("""
        SELECT COUNT(DISTINCT o.id) n FROM opportunity_spaces o
        JOIN market_sizes m ON m.opportunity_id=o.id AND m.method='bottom_up_adoption'
        WHERE o.merged_into IS NULL AND o.state IN ('active','watchlist','fading')
          AND m.som_base > 0""")["n"]
    by_conf = {r["confidence"]: r["n"] for r in _db.query(
        "SELECT confidence, COUNT(DISTINCT opportunity_id) n FROM market_sizes "
        "WHERE method='bottom_up_adoption' GROUP BY 1")}
    pools = []
    for r in _db.query("SELECT label, attributes FROM graph_nodes WHERE node_type='capability_pool'"):
        a = unjs(r["attributes"], {}) or {}
        pools.append({"label": r["label"], "headcount": a.get("headcount", 0)})
    return {
        "workflow": _workflow_plannable(),
        "economics_version": econ.get("economics_version"),
        "owner": econ.get("owner"),
        "source_filing": econ.get("source_filing"),
        "filed": econ.get("filed", {}),
        "defaults": econ.get("defaults", {}),
        "margin_by_distance": {k: v for k, v in (econ.get("margin_by_distance") or {}).items()
                               if k != "note"},
        "ramp_by_horizon": {k: v for k, v in (econ.get("ramp_by_horizon") or {}).items()
                            if k != "note"},
        "capacity": econ.get("capacity", {}),
        "aggregation": econ.get("aggregation", {}),
        "pools": sorted(pools, key=lambda p: -p["headcount"]),
        "plannable_spaces": plannable,
        "sizes_by_confidence": by_conf,
        "verticals": [{"id": v.id, "label": v.label} for v in _cfg.verticals],
        "domains": [{"id": d.id, "label": d.label} for d in _cfg.domains],
    }


def _workflow_plannable() -> dict[str, Any]:
    """What the stage gate has committed, and how much of it can be projected.

    The count that matters to the form is not how many spaces reached a stage
    but how many of those carry a bottom-up size — a committed space without one
    contributes nothing to any figure, and a form that counted it would promise
    a plan bigger than the one that comes back.
    """
    from .planner import WORKFLOW_STAGES, WORKFLOW_STAGE_LABELS

    rows = _db.query("""
        SELECT w.stage,
               COUNT(*) n,
               SUM(CASE WHEN EXISTS (SELECT 1 FROM market_sizes m
                                     WHERE m.opportunity_id = o.id
                                       AND m.method = 'bottom_up_adoption'
                                       AND m.som_base > 0) THEN 1 ELSE 0 END) sized
        FROM workflow_state w JOIN opportunity_spaces o ON o.id = w.opportunity_id
        WHERE o.merged_into IS NULL GROUP BY 1""")
    counts = {r["stage"]: {"count": r["n"], "sized": r["sized"] or 0} for r in rows}
    stages = []
    for i, stage in enumerate(WORKFLOW_STAGES):
        here = counts.get(stage, {"count": 0, "sized": 0})
        onward = [counts.get(s, {"count": 0, "sized": 0}) for s in WORKFLOW_STAGES[i:]]
        stages.append({
            "id": stage,
            "label": WORKFLOW_STAGE_LABELS[stage],
            "count": here["count"],
            "sized": here["sized"],
            # "or further" — what a plan starting at this stage would actually take.
            "cumulative": sum(c["count"] for c in onward),
            "cumulative_sized": sum(c["sized"] for c in onward),
        })
    return {"stages": stages,
            "default_from_stage": "demand_tested",
            "parked": sum(counts.get(s, {}).get("count", 0) for s in ("parked", "rejected"))}


@app.get("/api/planner/plans")
def planner_plans(limit: int = Query(25)) -> dict[str, Any]:
    """Stored plans, most recent first, with their headline figures."""
    from .planner import list_plans
    return {"plans": list_plans(_db, limit)}


@app.get("/api/planner/plans/{plan_id}")
def planner_plan(plan_id: str) -> dict[str, Any]:
    """One plan in full: inputs, selections, projection, capacity, flags, narrative."""
    from .planner import Planner
    plan = Planner(_cfg, _db).get(plan_id)
    if plan is None:
        raise HTTPException(404, f"No such plan: {plan_id}")
    return plan


@app.post("/api/planner/plans")
def create_plan(payload: PlanIn) -> dict[str, Any]:
    """Select, schedule and project. Arithmetic only — no model call, so it is fast."""
    from .planner import Planner, PlanInputs
    try:
        return Planner(_cfg, _db).plan(PlanInputs.from_dict(payload.model_dump()))
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))


@app.post("/api/planner/plans/{plan_id}/narrative")
def narrate_plan(plan_id: str) -> dict[str, Any]:
    """Write the business plan. One model call, and it may not introduce a number."""
    from .planner import Planner
    try:
        return Planner(_cfg, _db, llm=_llm()).narrate(plan_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@app.get("/api/planner/plans/{plan_id}/report")
def plan_report_status(plan_id: str) -> dict[str, Any]:
    """Whether an exported PDF exists for this plan, and whether it is current."""
    from .plan_report import plan_report_meta
    plan = _db.query_one("SELECT id, narrative FROM plans WHERE id = ?", (plan_id,))
    if plan is None:
        raise HTTPException(404, f"No plan {plan_id}")
    meta = plan_report_meta(_db, plan_id)
    if meta is not None:
        meta.pop("path", None)   # a server filesystem path is nobody's business over HTTP
    return {"plan_id": plan_id, "generated": meta is not None, "report": meta,
            "narrative_available": bool(plan["narrative"])}


@app.post("/api/planner/plans/{plan_id}/report")
def build_plan_report(plan_id: str) -> dict[str, Any]:
    """Render the whole plan — inputs, projection, spaces, narrative, assumptions.

    Rebuilt on every POST rather than served from cache, because the narrative
    can be written after the plan is computed and a reader who exported before
    that would otherwise get a document quietly missing its business plan.
    """
    from .plan_report import PlanReportBuilder
    from .planner import Planner
    try:
        plan = Planner(_cfg, _db).get(plan_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    try:
        result = PlanReportBuilder(_cfg, _db).build(plan)
        result.pop("path", None)
        result["url"] = f"/api/planner/plans/{plan_id}/report.pdf"
        return result
    except Exception as exc:  # noqa: BLE001
        log.exception("Plan report failed for %s", plan_id)
        raise HTTPException(500, f"Plan report generation failed: {exc}") from exc


@app.get("/api/planner/plans/{plan_id}/report.pdf")
def plan_report_pdf(plan_id: str, download: bool = Query(False)) -> FileResponse:
    """The document itself, inline so the Planner can embed it in the browser."""
    from .plan_report import plan_report_meta
    meta = plan_report_meta(_db, plan_id)
    if meta is None or not meta["exists"]:
        raise HTTPException(404, f"No report generated for {plan_id}. POST to this path first.")
    disposition = "attachment" if download else "inline"
    return FileResponse(
        meta["path"], media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{meta["filename"]}"',
                 "Cache-Control": "no-store"},
    )


@app.delete("/api/planner/plans/{plan_id}")
def delete_plan(plan_id: str) -> dict[str, Any]:
    """Discard a plan. Its selections go with it; the exported PDF is left on disk."""
    with _db.cursor() as cur:
        cur.execute("DELETE FROM plans WHERE id = ?", (plan_id,))
    return {"deleted": plan_id}


@app.get("/api/topics/{topic_id}/competitor-analysis")
def competitor_analysis(topic_id: str) -> dict[str, Any]:
    """What each competitor on this topic is doing, and how Orange differentiates.

    The structural join is computed on demand when it is missing, because it is
    arithmetic over data that already exists and making the caller press a
    button for it would be theatre. The written comparison is not: it is a model
    call, so it is generated only when asked for (POST below) and the response
    says plainly whether it is present.
    """
    from .competitor_analysis import CompetitorAnalyst, analysis_for_topic

    from .competition import competition_for_topic

    if _read.topic(topic_id) is None:
        raise HTTPException(404, f"No such topic: {topic_id}")
    stored = analysis_for_topic(_db, topic_id)
    if stored is None:
        analyst = CompetitorAnalyst(_cfg, _db)
        entries = analyst.join(topic_id)
        if entries:
            row = _db.query_one("SELECT * FROM opportunity_spaces WHERE id = ?", (topic_id,))
            analyst._store(dict(row), entries, narrative=None)
            stored = analysis_for_topic(_db, topic_id)
    # An empty analysis has two entirely different causes and the interface has
    # to tell them apart: competitive intensity was never computed for this
    # space (fixable — press the button), or it was computed and matched nobody
    # (a statement about the register). Saying the second when the first is true
    # is a confident false claim about the market.
    assessed = competition_for_topic(_db, topic_id) is not None
    if stored is None:
        return {"opportunity_id": topic_id, "entries": [], "has_narrative": False,
                "coverage": {}, "competition_assessed": assessed}
    stored["competition_assessed"] = assessed
    return stored


@app.post("/api/topics/{topic_id}/competitor-analysis")
def generate_competitor_analysis(topic_id: str, force: bool = Query(False)) -> dict[str, Any]:
    """Write the comparison for one topic. One model call, synchronous."""
    from .competitor_analysis import CompetitorAnalyst, analysis_for_topic

    row = _db.query_one("SELECT * FROM opportunity_spaces WHERE id = ?", (topic_id,))
    if row is None:
        raise HTTPException(404, f"No such topic: {topic_id}")
    analyst = CompetitorAnalyst(_cfg, _db, llm=_llm())
    entries = analyst.join(topic_id)
    if not entries:
        raise HTTPException(409, "No competitors are matched to this topic, so there is "
                                 "nothing to compare. Run competitive intensity first.")
    analyst.write(dict(row), entries)
    return analysis_for_topic(_db, topic_id) or {}


@app.get("/api/competitors")
def competitors() -> dict[str, Any]:
    """The register with its profiling status — including who refused to be read."""
    from .competitor_intel import profile_coverage

    rows = {r["competitor_id"]: dict(r) for r in _db.query(
        "SELECT competitor_id, status, status_reason, positioning, pages_used, generated_at "
        "FROM competitor_profiles")}
    types = _cfg.competitors_raw.get("types", {})
    out = []
    for entry in _cfg.competitors_raw["competitors"]:
        profile = rows.get(entry["id"], {})
        out.append({
            "id": entry["id"], "label": entry["label"], "type": entry.get("type"),
            "type_label": types.get(entry.get("type"), {}).get("label", entry.get("type")),
            "relationship": entry.get("relationship", "competitor"),
            "website": entry.get("website"),
            "status": profile.get("status", "unread"),
            "status_reason": profile.get("status_reason"),
            "positioning": profile.get("positioning"),
            "pages_used": profile.get("pages_used", 0),
            "profiled_at": profile.get("generated_at"),
        })
    return {"coverage": profile_coverage(_db, _cfg), "competitors": out}


@app.get("/api/competitors/{competitor_id}")
def competitor_profile(competitor_id: str) -> dict[str, Any]:
    """One competitor's profile, with the pages every claim was taken from."""
    from .competitor_intel import pages_for, profile_for

    entry = next((e for e in _cfg.competitors_raw["competitors"] if e["id"] == competitor_id), None)
    if entry is None:
        raise HTTPException(404, f"No such competitor: {competitor_id}")
    profile = profile_for(_db, competitor_id) or {"status": "unread"}
    pages = pages_for(_db, competitor_id, 60)
    return {"competitor": entry, "profile": profile,
            "pages": [{k: p[k] for k in ("id", "url", "kind", "title")} for p in pages]}


@app.get("/api/topics/{topic_id}/description")
def description(topic_id: str) -> dict[str, Any]:
    """The generated long-form description, or 404 if none exists yet."""
    stored = description_for_topic(_db, topic_id)
    if stored is None:
        raise HTTPException(404, f"No description generated for {topic_id} yet")
    return stored


@app.post("/api/topics/{topic_id}/description")
def generate_description(topic_id: str, force: bool = Query(False)) -> dict[str, Any]:
    """Generate (or regenerate) the description for one topic.

    Synchronous on purpose: it is one model call, the caller is a person who
    just pressed a button, and a background job would need a status endpoint to
    tell them the same thing.
    """
    row = _db.query_one("SELECT * FROM opportunity_spaces WHERE id = ?", (topic_id,))
    if row is None:
        raise HTTPException(404, f"No such topic: {topic_id}")
    existing = description_for_topic(_db, topic_id)
    if existing and not force and not existing["stale"]:
        return existing
    try:
        DescriptionGenerator(_cfg, _db, _llm()).generate(dict(row))
    except Exception as exc:  # noqa: BLE001 — surfaced to the user, not swallowed
        raise HTTPException(502, f"Description generation failed: {exc}") from exc
    return description_for_topic(_db, topic_id) or {}


@app.get("/api/topics/{topic_id}/brief")
def brief_meta(topic_id: str) -> dict[str, Any]:
    """Whether a brief exists, when it was made and whether it has gone stale."""
    if _read.topic(topic_id) is None:
        raise HTTPException(404, f"No such topic: {topic_id}")
    return brief_for_topic(_db, topic_id) or {"topic_id": topic_id, "exists": False}


@app.post("/api/topics/{topic_id}/brief")
def generate_brief(topic_id: str, force: bool = Query(False)) -> dict[str, Any]:
    """Build the PDF brief, generating its inputs if they are missing.

    The brief is an assembly of computed, curated and generated content, so it
    makes sure all three exist before rendering: sizing and competition are
    cheap and deterministic; the description costs one model call and is only
    made when absent or stale.
    """
    row = _db.query_one("SELECT * FROM opportunity_spaces WHERE id = ?", (topic_id,))
    if row is None:
        raise HTTPException(404, f"No such topic: {topic_id}")
    existing = brief_for_topic(_db, topic_id)
    if existing and existing["exists"] and not existing["stale"] and not force:
        return existing

    if not sizes_for_topic(_db, topic_id):
        MarketSizer(_cfg, _db).run(topic_ids=[topic_id])
    if competition_for_topic(_db, topic_id) is None:
        CompetitionAnalyser(_cfg, _db).run(topic_ids=[topic_id])
    stored_description = description_for_topic(_db, topic_id)
    if stored_description is None or stored_description["stale"] or force:
        try:
            DescriptionGenerator(_cfg, _db, _llm()).generate(dict(row))
        except Exception as exc:  # noqa: BLE001
            # A brief without the narrative is still worth having — it carries
            # the evidence, the assets, the sizing and the competitors — so the
            # failure is reported in the payload rather than as a dead end.
            log.warning("Brief for %s built without a fresh description: %s", topic_id, exc)

    try:
        meta = BriefBuilder(_cfg, _db).build(topic_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Brief generation failed: {exc}") from exc
    meta["description_available"] = description_for_topic(_db, topic_id) is not None
    return meta


@app.get("/api/topics/{topic_id}/brief.pdf")
def brief_pdf(topic_id: str, download: bool = Query(False)) -> FileResponse:
    """The PDF itself.

    Served inline by default so it can be embedded in the radar, and as an
    attachment with ?download=1 — the same file either way, so what a
    salesperson forwards is byte-identical to what they read.
    """
    path = brief_path(_db, topic_id)
    if path is None:
        raise HTTPException(404, f"No brief generated for {topic_id}. POST to this path first.")
    meta = brief_for_topic(_db, topic_id) or {}
    disposition = "attachment" if download else "inline"
    return FileResponse(
        path, media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="{meta.get("filename", path.name)}"',
            # The brief is regenerated in place, so a cached copy would show a
            # stale document at the same URL.
            "Cache-Control": "no-store",
        },
    )


@app.get("/api/topics/{topic_id}/presales")
def presales_index(topic_id: str) -> dict[str, Any]:
    """The whole collateral catalogue for one space, each entry with its state.

    Always the full catalogue, never only what has been built: this endpoint
    backs a tab whose job is to say what COULD be produced as much as what has
    been, and a list that starts empty is a list nobody presses a button on.
    """
    if _read.topic(topic_id) is None:
        raise HTTPException(404, f"No such topic: {topic_id}")
    return {"topic_id": topic_id, "items": collateral_for_topic(_db, topic_id)}


@app.post("/api/topics/{topic_id}/presales/{kind}")
def generate_presales(topic_id: str, kind: str,
                      fmt: str | None = Query(None, description="pdf | docx | odt | pptx | odp | md"),
                      force: bool = Query(False)) -> dict[str, Any]:
    """Build one piece of collateral, generating its inputs if they are missing.

    The expensive input is the narrative, and it is generated here rather than
    demanded of the user: somebody who pressed "Generate" on a battlecard wants
    a battlecard, not an error telling them to press a different button first.
    Sizing and competition are cheap and deterministic, so they are simply
    computed. A narrative that will not build is logged and the piece is
    rendered without it, carrying a banner that says so — the same posture
    `generate_brief` takes.
    """
    row = _db.query_one("SELECT * FROM opportunity_spaces WHERE id = ?", (topic_id,))
    if row is None:
        raise HTTPException(404, f"No such topic: {topic_id}")
    try:
        spec = collateral_entry(kind)
        fmt = collateral_format(kind, fmt)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        # An unsupported format is the caller's mistake, not a server fault, and
        # the message names what IS available rather than only what is not.
        raise HTTPException(400, str(exc)) from exc

    existing = collateral_item(_db, topic_id, kind)
    built = (existing or {}).get("builds", {}).get(fmt)
    if built and built.get("exists") and not built.get("stale") and not force:
        return existing

    needs = spec["needs"]
    if "sizing" in needs and not sizes_for_topic(_db, topic_id):
        MarketSizer(_cfg, _db).run(topic_ids=[topic_id])
    if ("competition" in needs or "analysis" in needs) and competition_for_topic(_db, topic_id) is None:
        CompetitionAnalyser(_cfg, _db).run(topic_ids=[topic_id])
    if "description" in needs:
        stored = description_for_topic(_db, topic_id)
        if stored is None or stored["stale"] or force:
            try:
                DescriptionGenerator(_cfg, _db, _llm()).generate(dict(row))
            except Exception as exc:  # noqa: BLE001
                log.warning("Collateral %s for %s built without a fresh description: %s",
                            kind, topic_id, exc)

    try:
        return PreSalesBuilder(_cfg, _db, _llm()).build(topic_id, kind, fmt)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"{spec['title']} generation failed: {exc}") from exc


@app.get("/api/topics/{topic_id}/presales/{kind}/file")
def presales_file(topic_id: str, kind: str, fmt: str | None = Query(None),
                  download: bool = Query(False)) -> FileResponse:
    """The file itself.

    Inline by default so a PDF can be previewed in the tab; as an attachment
    with ?download=1. PowerPoint, Word and Markdown have no inline viewer worth
    the name, so the frontend always asks for the attachment form for those —
    but the choice stays here rather than being hard-coded per format, because
    a browser that CAN preview one should be allowed to.
    """
    try:
        collateral_entry(kind)
        fmt = collateral_format(kind, fmt)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    path = collateral_path(_db, topic_id, kind, fmt)
    if path is None:
        raise HTTPException(
            404, f"No {kind} generated for {topic_id} as .{fmt}. POST to this path first.")
    build = ((collateral_item(_db, topic_id, kind) or {}).get("builds", {})).get(fmt, {})
    disposition = "attachment" if download else "inline"
    return FileResponse(
        path, media_type=build.get("media_type", "application/octet-stream"),
        headers={
            "Content-Disposition": f'{disposition}; filename="{build.get("filename", path.name)}"',
            # Regenerated in place, so a cached copy would serve a stale document
            # from the same URL.
            "Cache-Control": "no-store",
        },
    )


@app.get("/api/analytics/market-size")
def analytics_market_size() -> dict[str, Any]:
    """Sized opportunity by vertical, for the analytics view."""
    rows = _db.query(
        """SELECT o.vertical, m.method, m.confidence, m.tam_base, m.sam_base, m.som_base
           FROM market_sizes m JOIN opportunity_spaces o ON o.id = m.opportunity_id
           WHERE o.merged_into IS NULL AND m.method = 'bottom_up_adoption'"""
    )
    by_vertical: dict[str, dict[str, Any]] = {}
    for row in rows:
        entry = by_vertical.setdefault(
            row["vertical"],
            {"vertical": row["vertical"],
             "label": _cfg.verticals.label(row["vertical"]),
             "topics": 0, "sam_base": 0.0, "som_base": 0.0},
        )
        entry["topics"] += 1
        entry["sam_base"] += row["sam_base"] or 0.0
        entry["som_base"] += row["som_base"] or 0.0
    confidence = {}
    for row in rows:
        confidence[row["confidence"]] = confidence.get(row["confidence"], 0) + 1
    levels = _db.query("SELECT level, COUNT(*) n FROM topic_competition GROUP BY level")
    return {
        # Summing SAM across topics double counts: two topics in the same
        # vertical address overlapping budgets. Reported as "sized opportunity",
        # never as a portfolio total, and the note travels with the payload so a
        # chart cannot lose it.
        "note": "Sizes are per topic and overlap within a vertical; this is a comparison of where "
                "sized opportunity concentrates, not a total addressable figure for Orange.",
        "by_vertical": sorted(by_vertical.values(), key=lambda v: -v["sam_base"]),
        "by_confidence": confidence,
        "competition_by_level": {r["level"]: r["n"] for r in levels},
        "sizing_version": _cfg.sizing_version,
    }


# ---------------------------------------------------------------------------
# Generation (the Generate screen)
#
# The one place this API writes something the pipeline would otherwise own. The
# module docstring above says the API is read-only "except for the two write
# paths the requirements demand" — this is a third, and it is a deliberate
# widening rather than an oversight: FR-19 refreshes on a cadence, and a
# strategist who wants five more spaces in one vertical today should not have to
# wait for the cadence or reach a shell. What it is NOT allowed to do is
# invent a score: it runs the same pipeline stages, in the same order, with the
# same validation, and the only thing the screen adds is a bound on the scope.
# ---------------------------------------------------------------------------

#: Live for the purpose of "what already exists here". Wider than the radar
#: view's default, because a `candidate` space that nobody promoted still
#: occupies its taxonomy cell — and DR-03 means a run that lands on that cell
#: refreshes it rather than creating anything. Somebody deciding whether to
#: generate needs to see it. `rejected` is excluded: it was ruled out.
_GENERATION_STATES = ("active", "watchlist", "fading", "candidate", "dormant")

_generation = GenerationService(_cfg, _db)


def _generation_filters(vertical: list[str] | None, domain: list[str] | None,
                        geography: list[str] | None, horizon: list[str] | None,
                        market_cluster: list[str] | None = None) -> dict[str, Any]:
    """Filters for the generation preview.

    Clusters are expanded here rather than passed through as their own filter so
    the preview counts what the run will actually be scoped to: `POST /api/generate`
    expands clusters into member codes before building its constraints, and a
    preview filtering on a different dimension than the run would be a lie told
    with a number.
    """
    return {key: value for key, value in (
        ("vertical", vertical), ("domain", domain), ("horizon", horizon),
        ("geography", _expand_clusters(geography, market_cluster)),
    ) if value}


def _expand_clusters(geography: list[str] | None,
                     market_cluster: list[str] | None) -> list[str]:
    """Union of explicit ISO codes and the members of any named cluster."""
    codes = list(geography or [])
    for cluster in market_cluster or []:
        for code in _cfg.market_clusters.members(cluster):
            if code not in codes:
                codes.append(code)
    return codes


class GenerateIn(BaseModel):
    count: int = Field(5, ge=1, le=MAX_PER_RUN,
                       description="How many NEW opportunity spaces to create (DR-03: a run that "
                                   "lands on an existing taxonomy triple refreshes it instead, and "
                                   "that does not count towards this).")
    geographies: list[str] = Field(default_factory=list)
    market_clusters: list[str] = Field(
        default_factory=list,
        description="Orange Business market clusters. Expanded into their member "
                    "ISO codes and unioned with `geographies`, so a run scoped by "
                    "cluster is exactly a run scoped by the countries in it.",
    )
    verticals: list[str] = Field(default_factory=list)
    horizons: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    run_critic: bool = True
    run_entailment: bool = True


def _job_payload(job) -> dict[str, Any]:
    """A run, plus what it actually produced.

    The ids alone answer "did it work" and not "what did it make", which is the
    question somebody who just generated five spaces is actually asking. The
    rows are the same projection the radar list uses, so the screen can show a
    new space the way it shows an existing one — statement, taxonomy, horizon,
    scores — without a second round trip per id.
    """
    payload = job.as_dict()
    payload["created_topics"] = [
        # The list projection, plus `why_hot` put back. A list row drops the
        # cited claims because the detail pane is one click away and the radar
        # shows two dozen rows at once — neither is true here. These spaces were
        # made seconds ago, nobody has read them, and "why does the radar think
        # this is a thing" is the first question. It is answerable at all only
        # because §4.4.4 makes every claim carry the signal ids behind it, so
        # showing it beside the statement is the point rather than a decoration.
        topic_for_list(topic) | {"why_hot": topic.get("why_hot", [])}
        for topic in _read.topics_by_id(payload.get("created_ids") or [])
    ]
    return payload


@app.get("/api/generate/options")
def generation_options() -> dict[str, Any]:
    """What the Generate screen can offer, and whether a run is possible now.

    Geographies are not a controlled vocabulary — they are ISO codes carried by
    signals (§2.6: geography attaches to signals, not only to topics) — so the
    list has to be read from the corpus rather than from config. Both counts are
    returned because they answer different questions: `spaces` is what already
    exists there, `signals` is whether there is evidence to generate from.
    """
    from_signals: dict[str, int] = {}
    for row in _db.query("SELECT geographies FROM signals WHERE relevance > 0"):
        for code in unjs(row["geographies"], []) or []:
            from_signals[str(code)] = from_signals.get(str(code), 0) + 1
    from_spaces: dict[str, int] = {}
    placeholders = ",".join("?" * len(_GENERATION_STATES))
    for row in _db.query(
        f"SELECT geographies FROM opportunity_spaces WHERE merged_into IS NULL "
        f"AND state IN ({placeholders})", _GENERATION_STATES
    ):
        for code in unjs(row["geographies"], []) or []:
            from_spaces[str(code)] = from_spaces.get(str(code), 0) + 1

    geographies = [
        {"id": code, "signals": from_signals.get(code, 0), "spaces": from_spaces.get(code, 0)}
        for code in sorted(set(from_signals) | set(from_spaces))
    ]
    geographies.sort(key=lambda g: (-g["signals"], g["id"]))

    # The same corpus counts rolled up the way the business buys: a planner who
    # thinks in "the Nordics" should not have to tick five boxes and know which
    # five. Built from the codes actually present, so a cluster with no evidence
    # behind it reports zero rather than being quietly omitted.
    mc = _cfg.market_clusters
    clusters = []
    for item in mc:
        members = [c for c in item.extra["members"]
                   if c in from_signals or c in from_spaces]
        clusters.append({
            "id": item.id,
            "label": item.label,
            "countries": members,
            "source": item.extra["source"],
            "signals": sum(from_signals.get(c, 0) for c in members),
            "spaces": sum(from_spaces.get(c, 0) for c in members),
        })
    clusters.sort(key=lambda c: (-c["signals"], c["id"]))
    total_live = _db.query_one(
        f"SELECT COUNT(*) n FROM opportunity_spaces WHERE merged_into IS NULL "
        f"AND state IN ({placeholders})", _GENERATION_STATES
    )["n"]
    return {"geographies": geographies, "market_clusters": clusters,
            "unmapped_geographies": mc.unmapped(set(from_signals) | set(from_spaces)),
            "total_live": total_live,
            "min_brief_chars": MIN_BRIEF_CHARS, "max_brief_chars": MAX_BRIEF_CHARS,
            **_generation.readiness()}


@app.get("/api/generate/matching")
def generation_matching(
    vertical: list[str] | None = Query(None),
    domain: list[str] | None = Query(None),
    geography: list[str] | None = Query(None),
    market_cluster: list[str] | None = Query(None),
    horizon: list[str] | None = Query(None),
    limit: int = Query(60, ge=1, le=500),
) -> dict[str, Any]:
    """The opportunity spaces that ALREADY meet the criteria a run would use.

    Deliberately not `/api/view`: that endpoint filters by role first (§4.5.3),
    and "what does a salesperson get to see" is the wrong question here.
    Generation writes to the whole corpus, so the screen has to show the whole
    corpus, or someone asks for five more in a cell that already holds eleven.

    Filtering uses the read model's own `_matches`, so this count means exactly
    what the same filters mean on the radar — including its rule that a space
    carrying no geography is global rather than excluded, which is the same rule
    constrained synthesis validates candidates against.
    """
    filters = _generation_filters(vertical, domain, geography, horizon, market_cluster)
    topics = _read.topics(states=_GENERATION_STATES)
    matched = [t for t in topics if matches_filters(t, filters)]
    matched.sort(key=lambda t: (t.get("attractiveness") or {}).get("score", 0.0), reverse=True)
    return {
        "filters": filters,
        "count": len(matched),
        "total_live": len(topics),
        "facets": facet_counts(matched),
        "truncated": len(matched) > limit,
        "topics": [topic_for_list(t) for t in matched[:limit]],
    }


@app.post("/api/generate")
def start_generation(payload: GenerateIn) -> dict[str, Any]:
    """Start a constrained generation run (background; poll the job)."""
    unknown = [c for c in payload.market_clusters if c not in _cfg.market_clusters]
    if unknown:
        raise HTTPException(
            400, f"Unknown market cluster(s) {unknown}. Known: {_cfg.market_clusters.ids}"
        )
    geographies = _expand_clusters(payload.geographies, payload.market_clusters)
    constraints = GenerationConstraints.from_dict({
        "verticals": payload.verticals, "domains": payload.domains,
        "geographies": geographies, "horizons": payload.horizons,
    })
    try:
        job = _generation.start(payload.count, constraints,
                                run_critic=payload.run_critic,
                                run_entailment=payload.run_entailment)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        # 409, not 500: the request is well-formed and will succeed later.
        raise HTTPException(409, str(exc)) from exc
    return _job_payload(job)


class GenerateFromBriefIn(BaseModel):
    description: str = Field(
        description="A written description of the opportunity being looked for. Treated as a "
                    "SEARCH BRIEF, never as evidence: it retrieves the closest corroborated "
                    "signals in the corpus and those become the only facts the model may cite.",
    )
    run_critic: bool = True
    run_entailment: bool = True

    @field_validator("description")
    @classmethod
    def _collapse_whitespace(cls, value: str) -> str:
        """Normalise here, so the schema measures what the service will measure.

        A length bound on the raw string and a second one on the collapsed string
        disagree about padded input: the browser's own character counter says
        the brief is long enough, the schema agrees, and the service rejects it.
        One normalisation, applied before either check.
        """
        return " ".join((value or "").split())


@app.post("/api/generate/brief")
def start_generation_from_brief(payload: GenerateFromBriefIn) -> dict[str, Any]:
    """Generate ONE opportunity space from a written description.

    Same background job, same stage chain, same curation as the grid path — the
    difference is only what steers the model. If the corpus carries nothing close
    to the description, the run says so and creates nothing, which is the answer
    §4.1 asks for rather than a failure to work around.
    """
    try:
        job = _generation.start_from_brief(payload.description,
                                           run_critic=payload.run_critic,
                                           run_entailment=payload.run_entailment)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return _job_payload(job)


class GenerateFromBriefsIn(BaseModel):
    """Several briefs, one run.

    The plural endpoint exists because the scoping conversation can legitimately
    land on more than one taxonomy triple, and synthesis holds the only write
    lock on that identity — three separate requests would mean two 409s.
    """

    descriptions: list[str] = Field(
        min_length=1, max_length=MAX_BRIEFS_PER_RUN,
        description="One search brief per opportunity space to attempt. Each is treated the same "
                    "way the singular endpoint treats its description: a retrieval request, never "
                    "evidence.",
    )
    run_critic: bool = True
    run_entailment: bool = True


@app.post("/api/generate/briefs")
def start_generation_from_briefs(payload: GenerateFromBriefsIn) -> dict[str, Any]:
    """Generate one opportunity space per written brief, in a single run."""
    try:
        job = _generation.start_from_briefs(payload.descriptions,
                                            run_critic=payload.run_critic,
                                            run_entailment=payload.run_entailment)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return _job_payload(job)


class HypothesisIn(BaseModel):
    """Build a space the corpus cannot evidence, on evidence you supply.

    The description is still a search brief. What is new is `rationale`: what the
    person actually knows — the conversation they had, the RFP they saw, the deal
    they lost — which is recorded as an internal signal and becomes the evidence
    the space rests on.
    """

    description: str = Field(min_length=MIN_BRIEF_CHARS, max_length=MAX_BRIEF_CHARS)
    rationale: str = Field(
        min_length=80, max_length=2000,
        description="What you know that the corpus does not. This is stored as an attributable, "
                    "dated internal signal (FR-24) and cited by the resulting space — so it has "
                    "to say something a colleague could act on, not restate the brief.",
    )
    kind: str = Field(
        "customer_conversation",
        description="Which of the three internal evidence kinds this is (§2.5).",
    )
    vertical: str | None = None
    geographies: list[str] = Field(default_factory=list)
    run_critic: bool = True
    run_entailment: bool = True


class GenerateAnywayIn(BaseModel):
    """Build this space, whatever the corpus currently says.

    The corpus is a taxonomy-driven crawl, not the world, so "no evidence here"
    can mean "nobody wrote about it" or "our query grid never asked". This path
    stops guessing between the two: it goes and looks, and if the person has
    first-hand knowledge it records that too. Then it runs the ordinary
    synthesis, which still has to cite whatever came back.
    """

    description: str = Field(min_length=MIN_BRIEF_CHARS, max_length=MAX_BRIEF_CHARS)
    #: Optional. What the person knows that nobody has published — recorded as
    #: an attributable internal signal so the space can rest on it if the search
    #: comes back empty.
    rationale: str | None = Field(None, max_length=2000)
    kind: str = "customer_conversation"
    vertical: str | None = None
    geographies: list[str] = Field(default_factory=list)
    #: Search outside the corpus first. On by default: this endpoint exists
    #: because the corpus came up short.
    research: bool = True
    run_critic: bool = True
    run_entailment: bool = True


@app.post("/api/generate/anyway")
def start_generation_anyway(payload: GenerateAnywayIn, request: Request) -> dict[str, Any]:
    """Generate the space regardless of what the corpus holds today.

    Two ways to close the gap, used together rather than chosen between. The run
    SEARCHES for evidence on this brief (`radar.scouting`) — the sources that
    take a free-text query, through the ordinary relevance gate and tiering — and
    where the person has first-hand knowledge that is recorded as an internal
    signal under their name. Synthesis then runs unchanged: every claim still
    cites something dated and attributable, and the critic still gets a vote.

    What this does NOT do is let a space be written on nothing. That is the one
    line worth keeping: a radar whose spaces might rest on invented citations is
    a radar nobody can check.
    """
    if (reason := _generation.encoder_reason()) is not None:
        raise HTTPException(409, reason)
    if payload.vertical and payload.vertical not in _cfg.verticals:
        raise HTTPException(400, f"Unknown vertical {payload.vertical!r}.")

    internal_id = None
    if payload.rationale and payload.rationale.strip():
        if payload.kind not in internal.KINDS:
            raise HTTPException(400, f"Unknown kind {payload.kind!r}.")
        author = getattr(request.state, "user", None) or {}
        internal_id = internal.record(
            _db, author=str(author.get("username") or "unknown"), kind=payload.kind,
            title=payload.description[:180], body=payload.rationale.strip(),
            vertical=payload.vertical, geographies=payload.geographies, moderated=True)
        internal.promote(_cfg, _db, embedder=_generation.embedder())

    try:
        job = _generation.start_from_briefs([payload.description],
                                            run_critic=payload.run_critic,
                                            run_entailment=payload.run_entailment,
                                            research=payload.research)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    if internal_id:
        job.say(f"Contributed evidence {internal_id} recorded and available to this run.")
    out = _job_payload(job)
    out["internal_signal_id"] = internal_id
    return out


@app.post("/api/generate/hypothesis")
def start_generation_from_hypothesis(payload: HypothesisIn, request: Request) -> dict[str, Any]:
    """Generate a space the external corpus is silent about (FR-24, §2.5).

    THE CASE THIS EXISTS FOR. The corpus cannot evidence a genuinely new idea —
    that is what "new" means — and the scoping conversation was refusing on
    exactly that basis, which made the screen useless for the thing it was most
    wanted for. Fabricating the evidence was never an option: §4.4.4's whole
    posture is that a claim rests on a dated, attributable source or it does not
    exist, and a space citing signals that are not about it is the failure this
    system was built to prevent.

    So the evidence is not invented, it is CONTRIBUTED. What the person knows is
    recorded as an internal signal — authored by them, dated now, moderated as
    the act of asserting it, promoted at tier 3 because §4.3.7 reserves the
    higher tiers for published records and a conversation is not one. Then the
    ordinary brief run proceeds, unchanged: it retrieves that signal along with
    whatever adjacent evidence exists, and every claim still has to cite what
    came back and survive the critic and the entailment check.

    What comes out is honest in both directions. The space exists, and it scores
    low — one tier-3 signal, no independent corroboration — because a hypothesis
    is not a proven trend, and the radar saying so is the feature rather than a
    shortcoming to work around.
    """
    if (reason := _generation.encoder_reason()) is not None:
        raise HTTPException(409, reason)
    if payload.kind not in internal.KINDS:
        raise HTTPException(400, f"Unknown kind {payload.kind!r}. "
                                 f"Known: {', '.join(sorted(internal.KINDS))}")
    if payload.vertical and payload.vertical not in _cfg.verticals:
        raise HTTPException(400, f"Unknown vertical {payload.vertical!r}.")

    author = getattr(request.state, "user", None) or {}
    author_name = str(author.get("username") or author.get("display_name") or "unknown")

    internal_id = internal.record(
        _db, author=author_name, kind=payload.kind,
        # The brief is the headline the signal is retrieved by; the rationale is
        # its substance. Titling it with the rationale's first words instead
        # would make the signal retrieve badly against the very brief it exists
        # to support.
        title=payload.description[:180],
        body=payload.rationale,
        vertical=payload.vertical,
        geographies=payload.geographies,
        # Moderated by the act of asserting it, under a named account. That is
        # weaker than independent review and stronger than an anonymous note,
        # and it is recorded either way: `author` says who to ask.
        moderated=True,
    )
    # Embedded on the way in, or the signal this run exists to use would be
    # invisible to the retrieval that run performs until the next full refresh.
    internal.promote(_cfg, _db, embedder=_generation.embedder())

    try:
        job = _generation.start_from_briefs([payload.description],
                                            run_critic=payload.run_critic,
                                            run_entailment=payload.run_entailment)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    job.say(f"Contributed evidence {internal_id} by {author_name} (internal, tier 3) — this run "
            f"rests on it. It is an assertion, not a published record, and the score will say so.")
    payload_out = _job_payload(job)
    payload_out["internal_signal_id"] = internal_id
    return payload_out


# ---------------------------------------------------------------------------
# The scoping conversation (the Generate screen's assistant tab)
#
# Declared BEFORE /api/generate/{job_id}: FastAPI matches routes in declaration
# order, and "chat" is a perfectly good job id as far as that pattern is
# concerned.
#
# Stateless. The transcript lives in the browser and arrives whole on every
# turn — there is no session to expire, nothing to clean up, and a conversation
# is worth nothing once its briefs have been run. It is also the only thing
# here that costs a model call per request, which is why the opening turn is
# written rather than generated.
# ---------------------------------------------------------------------------


class ChatMessageIn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class ScopingChatIn(BaseModel):
    messages: list[ChatMessageIn] = Field(min_length=1, max_length=MAX_MESSAGES)
    #: What earlier turns settled, echoed back by the browser.
    #:
    #: The conversation is stateless by design — the transcript lives in the tab
    #: — and this is the rest of that state. It exists because the model's own
    #: `understood` is supposed to be cumulative and demonstrably is not: a turn
    #: that settles the vertical will drop the use case it named a turn earlier,
    #: and the interview then stalls on questions it has already answered.
    #: Re-resolved against the vocabularies server-side like anything else, so a
    #: client cannot smuggle a value past validation by putting it here.
    understood: dict[str, Any] | None = None


def _scoping() -> ScopingService:
    """Built per request, sharing the generation service's loaded encoder.

    Retrieval on every turn goes against the same stored signal vectors the run
    will read, so a second copy of the sentence-transformer model would be
    several hundred megabytes bought to compute identical numbers.
    """
    return ScopingService(_cfg, _db, embedder=_generation.embedder())


@app.get("/api/generate/chat")
def scoping_opening() -> dict[str, Any]:
    """The assistant's first turn, and what it can see.

    Costs no model call: the opening is written (`prompts.SCOPING_OPENING`),
    because it is identical every time and paying for it would buy nothing but
    latency on a screen nobody has typed into yet.
    """
    if (reason := _generation.encoder_reason()) is not None:
        # The conversation retrieves as its whole reason for existing. Without
        # the encoder it would be a chatbot with opinions and no corpus, which
        # is precisely the thing this screen is built not to be.
        raise HTTPException(409, reason)
    return _scoping().opening()


@app.post("/api/generate/chat")
def scoping_turn(payload: ScopingChatIn) -> dict[str, Any]:
    """One turn: answer, re-retrieve, report what is still missing.

    The response carries more than a reply because the screen shows more than a
    reply — what has been understood, what the words retrieved, and which briefs
    would actually run. `ready` is the server's verdict, not the model's: every
    proposed brief is put through the same retrieval the job will perform, and a
    brief the corpus cannot answer disables the button it would otherwise enable.
    """
    if (reason := _generation.encoder_reason()) is not None:
        raise HTTPException(409, reason)
    try:
        return _scoping().reply([m.model_dump() for m in payload.messages],
                                established=payload.understood)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except ScopingError as exc:
        # 502 rather than 500: the radar is fine, the model provider is not, and
        # the difference decides whether retrying is worth anything.
        raise HTTPException(502, f"The scoping assistant could not answer: {exc}") from exc


@app.get("/api/generate/jobs")
def generation_jobs(limit: int = Query(10, ge=1, le=20)) -> dict[str, Any]:
    """Recent runs, newest first — so a page reload does not lose the record."""
    active = _generation.active()
    return {
        "active": active.id if active and active.status in ("queued", "running") else None,
        "jobs": [_job_payload(job) for job in _generation.recent(limit)],
    }


@app.get("/api/generate/{job_id}")
def generation_status(job_id: str) -> dict[str, Any]:
    job = _generation.get(job_id)
    if job is None:
        raise HTTPException(404, f"No such generation run: {job_id}")
    return _job_payload(job)


@app.post("/api/generate/{job_id}/cancel")
def cancel_generation(job_id: str) -> dict[str, Any]:
    """Stop after the work in flight.

    Cooperative rather than abrupt: a model call already issued is allowed to
    finish and spaces already written stay written. Killing the thread mid-write
    would leave a space with evidence attached and no score, which is worse than
    a slightly late stop.
    """
    job = _generation.get(job_id)
    if job is None:
        raise HTTPException(404, f"No such generation run: {job_id}")
    if job.status not in ("queued", "running"):
        raise HTTPException(409, f"Run {job_id} has already finished ({job.status}).")
    job.cancel()
    return _job_payload(job)


# ---------------------------------------------------------------------------
# Serving the frontend (production)
#
# One process, one origin: the API and the built React bundle are the same
# deployment. That is what makes the CORS list above a dev-only concern, and it
# means a deployed radar has no second thing to keep in step.
#
# Mounted LAST so every /api route above wins. Everything else falls through to
# the bundle, and unknown paths return index.html rather than a 404 — the app
# owns its own routing (?topic=OS012&tab=brief must survive a refresh).
# ---------------------------------------------------------------------------

_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@app.get("/healthz", include_in_schema=False)
def healthz() -> Any:
    """Liveness for the platform, distinct from /api/health's data counts.

    Reports a failed start rather than the process disappearing: 503 with the
    reason, and the startup notes alongside it, is what makes a bad deployment
    diagnosable from outside.
    """
    payload = {
        "ok": bootstrap.STARTUP_ERROR is None,
        "frontend": _FRONTEND_DIST.is_dir(),
        "database": str(_cfg.db_path),
        "startup": bootstrap.STARTUP_NOTES[-8:],
    }
    if bootstrap.STARTUP_ERROR:
        payload["error"] = bootstrap.STARTUP_ERROR
        return JSONResponse(payload, status_code=503)
    return payload


if _FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        candidate = (_FRONTEND_DIST / full_path).resolve()
        # Only serve real files from inside the bundle; anything else is a
        # client-side route and gets the app shell.
        if full_path and candidate.is_file() and _FRONTEND_DIST in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")
else:
    log.warning("No built frontend at %s — serving the API only. "
                "Run `npm --prefix frontend run build` before deploying.", _FRONTEND_DIST)
