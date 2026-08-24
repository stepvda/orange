"""Removing an opportunity space, and saying what goes with it.

A space is the hub of this schema. Thirteen tables point at it, and by the time
anybody wants one gone it is carrying evidence attachments, two scored
trajectories, curator-confirmed asset links, stage-gate history, per-role
assessments, a market estimate with its factors, a written description, a
competitive read, a PDF on disk and possibly a place in a portfolio plan. A bare
`DELETE` takes all of that silently — the foreign keys already cascade — which is
why this module exists: not to make the delete work, but to make it *legible*
before and after it happens.

Three decisions are worth stating, because each one could reasonably have gone
the other way:

*   **Signals survive.** Only the attachment rows go. A signal is evidence about
    the world that several spaces may cite, collected under DR-01 and retained
    for replay under DR-14; deleting a synthesis result must not delete the
    reading it was synthesised from.

*   **Duplicates folded into this one go with it.** A row with `merged_into` set
    is a tombstone saying "this triple is the same topic as that one". If the
    survivor is removed, clearing the pointer instead would resurrect duplicates
    against the identity rule (§4.4.5) — and `idx_os_triple` would refuse the
    second one anyway. They are the same space, so they leave together.

*   **Plans are reported, not blocked.** `plan_selections` cascades, so a plan
    that selected this space loses a row while its stored `projection` and
    `selected_count` — computed once and immutable by design — still count it.
    Refusing the delete would make any space that ever appeared in a plan
    permanent; silently breaking the plan would be worse. So the impact names the
    plans, the interface shows them before asking, and the result names them
    again.

One caveat this module cannot fix, and therefore states loudly: deletion is not
suppression. Identity is the vertical × use case × technology triple (DR-03), so
a later refresh that meets the same triple in the evidence will synthesise the
space again — with a new id and none of the history removed here. Removing a
space is a statement about the corpus as it stands, not a permanent veto.
"""

from __future__ import annotations

import logging
from typing import Any

from .brief import resolve_brief
from .db import Database

log = logging.getLogger(__name__)

#: (table, column, human label) for every row that a delete takes with it.
#:
#: Written out rather than discovered from `PRAGMA foreign_key_list`, because the
#: label is the point: this list is what the confirmation dialog reads out, and
#: "3 curator-confirmed asset links" is a reason to stop where
#: "opportunity_links: 3" is not.
DEPENDENTS: tuple[tuple[str, str, str], ...] = (
    ("opportunity_signals", "opportunity_id", "evidence attachments"),
    ("scores", "opportunity_id", "stored scores"),
    ("opportunity_links", "opportunity_id", "asset links"),
    ("assessments", "opportunity_id", "role assessments"),
    ("workflow_transitions", "opportunity_id", "stage-gate moves"),
    ("workflow_state", "opportunity_id", "stage-gate position"),
    ("feedback", "opportunity_id", "feedback events"),
    ("market_sizes", "opportunity_id", "market-size estimates"),
    ("topic_descriptions", "opportunity_id", "written descriptions"),
    ("topic_competition", "opportunity_id", "competitive assessments"),
    ("topic_competitor_analysis", "opportunity_id", "competitor comparisons"),
    ("topic_briefs", "opportunity_id", "sales briefs"),
    ("plan_selections", "opportunity_id", "places in a portfolio plan"),
)


class TopicNotFound(LookupError):
    """No space with that id."""


def _table_exists(db: Database, table: str) -> bool:
    """Whether a table is present in THIS database.

    `init_schema` is idempotent and runs on every start, so in practice they all
    are — but a count against a table that predates the deployed file is a
    `sqlite3.OperationalError` in the middle of a delete, and answering "0 of
    those" is both true and survivable.
    """
    return db.query_one(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ) is not None


def _merged_duplicates(db: Database, topic_id: str) -> list[str]:
    rows = db.query(
        "SELECT id FROM opportunity_spaces WHERE merged_into = ?", (topic_id,)
    )
    return [row["id"] for row in rows]


def deletion_impact(db: Database, topic_id: str) -> dict[str, Any]:
    """What deleting `topic_id` would remove, without removing anything.

    Read by the confirmation dialog. The counts are of rows that WILL go; the
    signal count is called out separately because it is the one number a reader
    is likely to misread as a loss.
    """
    space = db.query_one(
        "SELECT id, statement, vertical, use_case, technology, state FROM opportunity_spaces "
        "WHERE id = ?", (topic_id,)
    )
    if space is None:
        raise TopicNotFound(topic_id)

    ids = [topic_id, *_merged_duplicates(db, topic_id)]
    placeholders = ",".join("?" for _ in ids)

    removes: list[dict[str, Any]] = []
    for table, column, label in DEPENDENTS:
        if not _table_exists(db, table):
            continue
        row = db.query_one(
            f"SELECT COUNT(*) AS n FROM {table} WHERE {column} IN ({placeholders})", tuple(ids)
        )
        count = int(row["n"]) if row else 0
        if count:
            removes.append({"table": table, "label": label, "count": count})

    # Comparison feedback names two spaces. The event is about the pair, so it
    # cannot survive one of them — and it is not counted above, which matches on
    # `opportunity_id` only.
    if _table_exists(db, "feedback"):
        row = db.query_one(
            f"SELECT COUNT(*) AS n FROM feedback WHERE other_opportunity_id IN ({placeholders}) "
            f"AND (opportunity_id IS NULL OR opportunity_id NOT IN ({placeholders}))",
            tuple(ids) * 2,
        )
        if row and row["n"]:
            removes.append({"table": "feedback", "label": "comparisons against other spaces",
                            "count": int(row["n"])})

    plans: list[dict[str, Any]] = []
    if _table_exists(db, "plan_selections"):
        plans = [
            {"id": row["id"], "label": row["label"], "created_at": row["created_at"],
             "entry_year": row["entry_year"]}
            for row in db.query(
                "SELECT p.id, p.label, p.created_at, s.entry_year FROM plan_selections s "
                f"JOIN plans p ON p.id = s.plan_id WHERE s.opportunity_id IN ({placeholders}) "
                "ORDER BY p.created_at DESC", tuple(ids)
            )
        ]

    signals = db.query_one(
        f"SELECT COUNT(*) AS n FROM opportunity_signals WHERE opportunity_id IN ({placeholders})",
        tuple(ids),
    )
    briefs = [
        row["filename"] for row in db.query(
            f"SELECT filename FROM topic_briefs WHERE opportunity_id IN ({placeholders})", tuple(ids)
        )
    ] if _table_exists(db, "topic_briefs") else []

    return {
        "topic_id": topic_id,
        "statement": space["statement"],
        "triple": {"vertical": space["vertical"], "use_case": space["use_case"],
                   "technology": space["technology"]},
        "state": space["state"],
        "removes": removes,
        "merged_duplicates": ids[1:],
        "plans": plans,
        "briefs": briefs,
        # Named so the dialog can say what is NOT lost. Evidence is shared and
        # replayable; a reader who thinks 47 sources are about to be destroyed
        # will not press the button, and would be wrong not to.
        "signals_kept": int(signals["n"]) if signals else 0,
    }


def delete_topic(db: Database, topic_id: str) -> dict[str, Any]:
    """Remove a space, its dependent rows and its brief files.

    Returns the same shape `deletion_impact` produces, with the removal
    confirmed — the caller reports what went rather than what would have. The
    impact is computed BEFORE the delete for exactly that reason: afterwards
    every count is zero and there is nothing left to describe.
    """
    impact = deletion_impact(db, topic_id)
    ids = [topic_id, *impact["merged_duplicates"]]
    placeholders = ",".join("?" for _ in ids)

    # Files first, while the rows that name them still exist — and best-effort,
    # because a brief written on the machine that ran the pipeline is routinely
    # absent from the machine serving the app (see `brief.resolve_brief`). A
    # missing PDF must not abort a delete the user has already confirmed.
    files_removed = 0
    if _table_exists(db, "topic_briefs"):
        for row in db.query(
            f"SELECT path FROM topic_briefs WHERE opportunity_id IN ({placeholders})", tuple(ids)
        ):
            path = resolve_brief(row["path"])
            if path is None:
                continue
            try:
                path.unlink()
                files_removed += 1
            except OSError as exc:  # noqa: PERF203 — one message per file is the point
                log.warning("Could not remove brief %s: %s", path, exc)

    with db.cursor() as cur:
        # The tombstones first: their `merged_into` points at the row about to
        # go, and with foreign keys ON the parent delete would be refused.
        if impact["merged_duplicates"]:
            cur.execute(
                "DELETE FROM opportunity_spaces WHERE id IN ("
                + ",".join("?" for _ in impact["merged_duplicates"]) + ")",
                tuple(impact["merged_duplicates"]),
            )
        cur.execute("DELETE FROM opportunity_spaces WHERE id = ?", (topic_id,))
        deleted = cur.rowcount

    if not deleted:
        # Nothing matched between the impact read and the write — another writer
        # got there first. Saying so beats reporting a delete that did nothing.
        raise TopicNotFound(topic_id)

    log.warning(
        "Deleted opportunity space %s (%s) — %d dependent row group(s), %d brief file(s), "
        "%d plan(s) affected",
        topic_id, impact["statement"][:80], len(impact["removes"]), files_removed,
        len({plan["id"] for plan in impact["plans"]}),
    )
    return {**impact, "deleted": True, "brief_files_removed": files_removed}
