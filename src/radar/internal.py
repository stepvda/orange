"""Internal signal intake — customer conversations, RFP themes, lost deals.

THE GAP THIS CLOSES. `internal_signals` was created by the schema and
referenced by nothing: no writer, no reader, no promotion path, zero rows. It is
the only evidence class in the design that the radar cannot obtain by fetching a
URL, and also the only one that says what Orange's own people are hearing —
§2.5's point that internal knowledge precedes market signal, applied to the
sales conversation rather than to research.

MODERATION IS THE POINT, not a formality. External evidence arrives with a
publisher and a date that a reviewer can check; an internal note arrives with
neither. So a record here is inert until someone moderates it, and only then is
it promoted into `signals` where scoring can see it. That ordering is what keeps
NFR-02 true — every claim traceable to a dated, attributable source — for a
class of evidence whose attribution is a colleague rather than a publication.

TIER 3, deliberately. §4.3.7 reserves tier 1 for published authoritative
records, and a conversation is not one however well informed. It sits with
practitioner evidence: real, current, ahead of the press, and not independently
checkable.

DR-09 — no personal data beyond the strictly necessary. `author` is who to ask
about the note, and `account_hint` is deliberately a HINT: a segment or an
industry, never a named customer contact. Nothing here is indexed as an entity.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
from typing import Any

from .config import Config
from .db import Database, js
from .embeddings import Embedder

log = logging.getLogger(__name__)

#: The three kinds the schema names. A closed list for the same reason the
#: vocabularies are closed (§4.4.2) — free text here would make the intake
#: unqueryable within a month.
KINDS = {
    "customer_conversation": "trend",
    "rfp_theme": "buying_signal",
    "lost_deal": "market_move",
}

SOURCE_ID = "internal"
DEFAULT_TIER = 3


def record(db: Database, *, author: str, kind: str, title: str, body: str,
           vertical: str | None = None, geographies: list[str] | None = None,
           account_hint: str | None = None, moderated: bool = False) -> str:
    """Store one internal signal. Inert until moderated."""
    if kind not in KINDS:
        raise ValueError(f"Unknown kind {kind!r}. Known: {', '.join(sorted(KINDS))}")
    if not title.strip():
        raise ValueError("An internal signal needs a title")

    created = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    internal_id = "INT-" + hashlib.sha256(
        f"{author}|{title}|{created}".encode()
    ).hexdigest()[:12].upper()

    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO internal_signals
               (id, created_at, author, kind, title, body, vertical, geographies,
                account_hint, moderated, signal_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,NULL)""",
            (internal_id, created, author, kind, title.strip(), body.strip(),
             vertical, js([g.upper() for g in geographies or []]),
             account_hint, int(moderated)),
        )
    log.info("Recorded internal signal %s (%s) by %s", internal_id, kind, author)
    return internal_id


def moderate(db: Database, internal_id: str, *, approved: bool = True) -> bool:
    """Mark a record reviewed. Returns False if the id is unknown."""
    with db.cursor() as cur:
        cur.execute("UPDATE internal_signals SET moderated = ? WHERE id = ?",
                    (int(approved), internal_id))
        return cur.rowcount > 0


def pending(db: Database) -> list[dict[str, Any]]:
    return [dict(r) for r in db.query(
        "SELECT * FROM internal_signals WHERE moderated = 0 ORDER BY created_at DESC")]


def promote(cfg: Config, db: Database, embedder: "Embedder | None" = None) -> dict[str, Any]:
    """Turn moderated internal records into signals the pipeline can score.

    A promoted record becomes an ordinary row in `signals`, so it clusters,
    attaches to topics and counts toward volume exactly like anything else —
    with one deliberate difference: its `url` is null, because there is no page
    to open. Every consumer already tolerates that (`idx_signals_url` is a
    partial index precisely for URL-less rows), and inventing a URL to satisfy
    a schema would be the sort of fabricated attribution §4.4.4 forbids.

    `embedder` decides whether the promoted row is visible before the next full
    refresh. Without one it lands with a null `relevance` and no vector, which
    every retrieval path filters out (`relevance > 0 AND embedding IS NOT NULL`)
    — so the note a colleague took today would sit inert until the cadence ran,
    which for the batch caller is fine and for someone who has just written it
    down in order to use it is not. Given one, the row is embedded and admitted
    at full relevance: it was written by a named person and moderated by another,
    which is a stronger provenance claim than the gate the relevance classifier
    applies to a fetched page, not a weaker one.
    """
    rows = db.query(
        "SELECT * FROM internal_signals WHERE moderated = 1 AND signal_id IS NULL "
        "ORDER BY created_at")
    if not rows:
        return {"promoted": 0, "skipped": 0}

    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    source = next((s for s in cfg.sources["sources"] if s["id"] == SOURCE_ID), {})
    tier = int(source.get("default_tier", DEFAULT_TIER))

    promoted = 0
    with db.cursor() as cur:
        for row in rows:
            created = str(row["created_at"])[:10]
            signal_id = "SIG-" + hashlib.sha256(
                f"{SOURCE_ID}|{row['id']}".encode()).hexdigest()[:12].upper()
            attributes = {
                "internal_id": row["id"],
                "kind": row["kind"],
                "author": row["author"],
                "account_hint": row["account_hint"],
                "vertical_hint": row["vertical"],
            }
            cur.execute(
                """INSERT OR IGNORE INTO signals
                   (id, source_id, publisher, title, url, published_at, published_at_inferred,
                    ingested_at, language, geographies, signal_type, signal_type_confidence,
                    tier, extract, attributes, raw_item_id, pipeline_version)
                   VALUES (?,?,?,?,NULL,?,0,?,?,?,?,?,?,?,?,NULL,?)""",
                (signal_id, SOURCE_ID, f"Orange internal — {row['author']}", row["title"],
                 created, now, "en", row["geographies"],
                 KINDS[row["kind"]], 1.0, tier,
                 (row["body"] or row["title"])[: cfg.settings["ingestion"]["max_extract_chars"]],
                 json.dumps(attributes, ensure_ascii=False),
                 cfg.pipeline_version),
            )
            cur.execute("UPDATE internal_signals SET signal_id = ? WHERE id = ?",
                        (signal_id, row["id"]))
            if embedder is not None:
                text = f"{row['title']} {row['body'] or ''}".strip()
                vector = embedder.encode([text])[0]
                cur.execute(
                    "UPDATE signals SET relevance = ?, relevance_reason = ?, embedding = ? "
                    "WHERE id = ?",
                    (1.0, f"internal signal moderated from {row['id']}",
                     Embedder.to_blob(vector), signal_id),
                )
            promoted += 1

    log.info("Promoted %d internal signals into the signal store", promoted)
    return {"promoted": promoted, "skipped": 0}
