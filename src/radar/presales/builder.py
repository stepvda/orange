"""Building, storing and ageing one piece of pre-sales collateral, in one format.

The lifecycle is the brief's, deliberately: build to a file, record the file with
the versions that produced it, and report staleness against the space, the
narrative and the sizing separately. A pack whose battlecard was built against
last month's competitor register and whose value case was built this morning is
the failure this tracking exists to make visible, and the tab shows it per item
rather than per space.

TWO THINGS ARE DIFFERENT FROM THE BRIEF.

There are twelve pieces rather than one, so the expensive inputs are prepared
once for whichever pieces need them, and a piece whose declared inputs are
missing STILL BUILDS — with a banner naming the gap. Nothing here refuses to
produce a document. A pre-sales engineer who asked for a solution outline and
got an error has nothing; one who got an outline with "built without the written
description" across the top has the component map, the portfolio path and a
clear instruction.

And each piece can exist in several formats at once. The row key is
(space, kind, format), not (space, kind): somebody who has the battlecard as a
PDF and then asks for Word wants both, and overwriting the first would be a
surprising way to answer the second.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
import os
from pathlib import Path
from typing import Any

from ..config import Config
from ..db import Database
from ..llm import LLMClient
from . import content as content_module
from . import context as context_module
from . import decks, documents, emitters, office, research
from .catalogue import (CATALOGUE, COLLATERAL_SCHEMA, FORMAT_LABELS, entry, filename_for,
                        formats_for, media_type_for, resolve_format)

log = logging.getLogger(__name__)

#: Which writer produces the content for each kind. A kind with no entry is
#: rendered from computed and curated data alone.
WRITERS = {
    "discovery-pack": "discovery",
    "solution-outline": "solution",
    "battlecards": "battlecards",
    "value-hypothesis": "value",
    "first-meeting-deck": "deck",
    "demo-scope": "demo",
    "rfp-boilerplate": "rfp",
    "outreach-sequence": "outreach",
    "pricing-options": "pricing",
    "risk-register": "risks",
    "partner-brief": "partner",
}

#: (document emitter, deck emitter) per format. Documents and decks are separate
#: models — a deck flowed into A4 portrait stops being a deck, because
#: one-idea-per-page is the only property that made it one — so each format
#: names the emitter for whichever of the two it is handed, and `None` where
#: that combination is deliberately not offered.
EMITTERS: dict[str, tuple[Any, Any]] = {
    "pdf": (emitters.document_to_pdf, emitters.deck_to_pdf),
    "docx": (emitters.document_to_docx, None),
    "odt": (emitters.document_to_odt, None),
    "md": (emitters.document_to_md, None),
    "pptx": (None, office.deck_to_pptx),
    "odp": (None, emitters.deck_to_odp),
}


def collateral_dir() -> Path:
    """Where collateral lives for this process.

    Anchored exactly as `brief.brief_dir` is, so a process started from outside
    the repository root does not write to one directory and read from another.
    """
    configured = os.getenv("RADAR_COLLATERAL_DIR")
    if configured:
        return Path(configured)
    from ..config import PROJECT_ROOT
    return (PROJECT_ROOT / os.getenv("RADAR_DB_PATH", "data/radar.db")).parent / "collateral"


def resolve(recorded: str) -> Path | None:
    """The file for a recorded path, or None if it is not on this machine.

    Same fallback as the brief's: collateral is written by whichever process
    pressed the button, and on a deployment the recorded directory may not
    exist. The filename is stable, so the directory this process uses is tried
    second. Without this every download 404s in Azure.
    """
    path = Path(recorded)
    if path.exists():
        return path
    fallback = collateral_dir() / path.name
    return fallback if fallback.exists() else None


class PreSalesBuilder:
    """Builds one piece of collateral for one opportunity space, in one format."""

    def __init__(self, cfg: Config, db: Database, llm: Any | None = None,
                 output_dir: Path | None = None):
        self.cfg = cfg
        self.db = db
        self._llm = llm
        self.output_dir = Path(output_dir or collateral_dir())

    @property
    def llm(self) -> Any:
        if self._llm is None:
            self._llm = LLMClient()
        return self._llm

    # ------------------------------------------------------------------

    def build(self, topic_id: str, kind: str, fmt: str | None = None,
              live_research: bool = True) -> dict[str, Any]:
        """Assemble, render, record. Raises only on an unknown space, kind or format."""
        spec = entry(kind)
        fmt = resolve_format(kind, fmt)
        ctx = context_module.load(self.cfg, self.db, topic_id)

        written: dict[str, Any] = {}
        writer_name = WRITERS.get(kind)
        if writer_name and spec.get("model_calls"):
            # A live look at the public record before writing. The corpus is
            # refreshed on a cadence and this document is being written today,
            # and the gap between those two is exactly where a regulator's
            # deadline or a competitor's announcement lives. Enrichment only:
            # `gather` never raises, and an empty result means the writer runs
            # on the stored corpus as it always did.
            if live_research:
                ctx.research = research.gather(self.cfg, ctx)
            writer = content_module.PreSalesWriter(self.llm)
            written = getattr(writer, writer_name)(ctx.prompt_context())
        written["_research"] = ctx.research

        # The model is built once and handed to whichever emitter the caller
        # asked for. That is the whole point of `blocks`: the same battlecard,
        # not three battlecards that drift apart.
        document_emit, deck_emit = EMITTERS[fmt]
        if kind in decks.DECKS:
            if deck_emit is None:
                raise ValueError(f"{spec['title']} cannot be produced as .{fmt}")
            model, emit = decks.DECKS[kind](ctx, written), deck_emit
        else:
            if document_emit is None:
                raise ValueError(f"{spec['title']} cannot be produced as .{fmt}")
            model, emit = documents.DOCUMENTS[kind](ctx, written), document_emit

        self.output_dir.mkdir(parents=True, exist_ok=True)
        filename = filename_for(topic_id, kind, fmt)
        path = self.output_dir / filename
        emit(model, ctx, path)

        payload = path.read_bytes()
        return self._store(ctx, kind, fmt, path, filename, payload, bool(written))

    def _store(self, ctx: context_module.TopicContext, kind: str, fmt: str, path: Path,
               filename: str, payload: bytes, has_narrative: bool) -> dict[str, Any]:
        size = ctx.best_size
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        with self.db.cursor() as cur:
            cur.execute(
                """INSERT INTO topic_collateral
                       (opportunity_id, kind, fmt, generated_at, topic_version, path, filename,
                        bytes, content_hash, media_type, description_at, market_size_at,
                        weight_set, sizing_version, prompt_version, model_version,
                        pipeline_version, collateral_schema, has_narrative)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(opportunity_id, kind, fmt) DO UPDATE SET
                       generated_at=excluded.generated_at,
                       topic_version=excluded.topic_version,
                       path=excluded.path, filename=excluded.filename,
                       bytes=excluded.bytes, content_hash=excluded.content_hash,
                       media_type=excluded.media_type,
                       description_at=excluded.description_at,
                       market_size_at=excluded.market_size_at,
                       weight_set=excluded.weight_set,
                       sizing_version=excluded.sizing_version,
                       prompt_version=excluded.prompt_version,
                       model_version=excluded.model_version,
                       pipeline_version=excluded.pipeline_version,
                       collateral_schema=excluded.collateral_schema,
                       has_narrative=excluded.has_narrative""",
                (ctx.topic_id, kind, fmt, now, ctx.topic.get("version"), str(path), filename,
                 len(payload), hashlib.sha256(payload).hexdigest(), media_type_for(kind, fmt),
                 (ctx.description or {}).get("generated_at"), (size or {}).get("computed_at"),
                 (ctx.topic.get("provenance") or {}).get("weight_set") or self.cfg.weight_set,
                 (size or {}).get("sizing_version"),
                 content_module.PROMPT_VERSION_PRESALES if has_narrative else None,
                 getattr(self.llm, "strong_model", None) if has_narrative else None,
                 self.cfg.pipeline_version, COLLATERAL_SCHEMA, 1 if has_narrative else 0),
            )
        log.info("Collateral %s/%s.%s: %s (%d bytes)", ctx.topic_id, kind, fmt, path, len(payload))
        return item_for(self.db, ctx.topic_id, kind) or {}


# ---------------------------------------------------------------------------
# Read side
# ---------------------------------------------------------------------------

def _build_state(db: Database, topic_id: str, row: Any) -> dict[str, Any]:
    """What has been built in one format, and the three ways it can be stale.

    Reported separately because they need different actions: rebuild,
    regenerate the narrative first, or re-run sizing first. "Out of date" alone
    tells the reader nothing they can act on.
    """
    topic = db.query_one("SELECT version FROM opportunity_spaces WHERE id = ?", (topic_id,))
    description = db.query_one(
        "SELECT generated_at FROM topic_descriptions WHERE opportunity_id = ?", (topic_id,))
    size = db.query_one(
        "SELECT MAX(computed_at) AS at FROM market_sizes WHERE opportunity_id = ?", (topic_id,))

    reasons = []
    if topic and row["topic_version"] != topic["version"]:
        reasons.append("the opportunity space has changed since this was built")
    if description and row["description_at"] and description["generated_at"] != row["description_at"]:
        reasons.append("the written description has been regenerated underneath it")
    if size and size["at"] and row["market_size_at"] and size["at"] != row["market_size_at"]:
        reasons.append("the market sizing has been recomputed")
    path = resolve(row["path"])
    if path is None:
        reasons.append("the file is not on this machine")

    return {
        "fmt": row["fmt"],
        "format_label": FORMAT_LABELS.get(row["fmt"], row["fmt"]),
        "exists": path is not None,
        "generated_at": row["generated_at"],
        "topic_version": row["topic_version"],
        "filename": row["filename"],
        "bytes": row["bytes"],
        "content_hash": row["content_hash"],
        "media_type": row["media_type"],
        "stale": bool(reasons),
        "stale_reason": "; ".join(reasons) or None,
        "incomplete": row["collateral_schema"] != COLLATERAL_SCHEMA,
        "has_narrative": bool(row["has_narrative"]),
        "weight_set": row["weight_set"],
        "sizing_version": row["sizing_version"],
        "prompt_version": row["prompt_version"],
        "model_version": row["model_version"],
        "url": f"/api/topics/{topic_id}/presales/{row['kind']}/file?fmt={row['fmt']}",
    }


def item_for(db: Database, topic_id: str, kind: str) -> dict[str, Any] | None:
    """One catalogue entry, with whatever has been built for it in any format."""
    spec = entry(kind)
    rows = db.query(
        "SELECT * FROM topic_collateral WHERE opportunity_id = ? AND kind = ? ORDER BY fmt",
        (topic_id, kind))
    builds = {row["fmt"]: _build_state(db, topic_id, row) for row in rows}
    default = formats_for(kind)[0]
    # The headline state is the DEFAULT format's, falling back to whatever else
    # exists — so a row that has only been built as Word still reads as built.
    primary = builds.get(default) or (next(iter(builds.values())) if builds else None)

    return {
        "kind": kind,
        "title": spec["title"],
        "audience": spec["audience"],
        "summary": spec["summary"],
        "charts": spec["charts"],
        "model_calls": spec["model_calls"],
        "format": default,
        "formats": [{"fmt": fmt, "label": FORMAT_LABELS[fmt],
                     "built": fmt in builds,
                     "stale": bool(builds.get(fmt, {}).get("stale")),
                     "bytes": builds.get(fmt, {}).get("bytes"),
                     "url": f"/api/topics/{topic_id}/presales/{kind}/file?fmt={fmt}"}
                    for fmt in formats_for(kind)],
        "builds": builds,
        "exists": bool(primary and primary["exists"]),
        "stale": bool(primary and primary["stale"]),
        "stale_reason": primary["stale_reason"] if primary else None,
        "incomplete": bool(primary and primary["incomplete"]),
        "has_narrative": bool(primary and primary["has_narrative"]),
        "generated_at": primary["generated_at"] if primary else None,
        "bytes": primary["bytes"] if primary else None,
        "content_hash": primary["content_hash"] if primary else None,
        "filename": primary["filename"] if primary else None,
        "url": primary["url"] if primary else
               f"/api/topics/{topic_id}/presales/{kind}/file?fmt={default}",
    }


def collateral_for_topic(db: Database, topic_id: str) -> list[dict[str, Any]]:
    """The whole catalogue, each entry carrying its build state.

    Always the full list, never only what exists: the tab's job is to say what
    could be produced as much as what has been, and a screen that shows nothing
    until something is built is a screen nobody presses a button on.
    """
    return [item_for(db, topic_id, spec["kind"]) or {} for spec in CATALOGUE]


def collateral_path(db: Database, topic_id: str, kind: str,
                    fmt: str | None = None) -> Path | None:
    fmt = resolve_format(kind, fmt)
    row = db.query_one(
        "SELECT path FROM topic_collateral WHERE opportunity_id = ? AND kind = ? AND fmt = ?",
        (topic_id, kind, fmt))
    return resolve(row["path"]) if row else None
