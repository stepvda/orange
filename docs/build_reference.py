#!/usr/bin/env python3
"""Regenerate the API and data-model references from the running code.

These two documents are generated rather than written, so they cannot drift from
the implementation. Everything narrative lives in the hand-written documents.

    python3 docs/build_reference.py
"""
from __future__ import annotations

import inspect
import pathlib
import sqlite3
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))

DB = ROOT / "data" / "radar.db"

ROUTE_GROUPS = [
    ("Meta and health", lambda p: p in ("/api/meta", "/api/health", "/healthz", "/api/refreshes")),
    ("The main read", lambda p: p.startswith(("/api/view", "/api/whitespace", "/api/orphan", "/api/coverage"))),
    ("One topic", lambda p: p.startswith("/api/topics/")),
    ("Competitors", lambda p: p.startswith("/api/competitors")),
    ("The Planner", lambda p: p.startswith("/api/planner")),
    ("Collaboration", lambda p: p.startswith(("/api/workflow", "/api/divergence", "/api/feedback", "/api/links"))),
    ("Analytics", lambda p: p.startswith("/api/analytics")),
    ("Generation", lambda p: p.startswith("/api/generate")),
    ("Reference data", lambda p: p.startswith("/api/reference")),
    ("Internal signals", lambda p: p.startswith("/api/internal")),
    ("Graph", lambda p: p.startswith("/api/graph")),
]

#: Table -> (subject area, one-line purpose). Hand-maintained because a purpose
#: is a judgement; the row counts and the column lists are read from the file.
PURPOSE = {
    "raw_items": ("Discovery", "Replay archive — the connector payload as returned, so a past date can be re-run without re-fetching (DR-14, FR-35)."),
    "signals": ("Discovery", "Dated, attributable evidence, stored by reference plus a bounded extract (DR-01, DR-08)."),
    "clusters": ("Discovery", "Theme clusters, recomputed each refresh; the seed for synthesis."),
    "opportunity_spaces": ("Core", "The canonical unit. Identity is the vertical × use case × technology triple (DR-02, DR-03)."),
    "opportunity_signals": ("Core", "Evidence attachment, recording which refresh first attached each signal — what makes momentum honest."),
    "scores": ("Core", "One row per topic per score kind per computation, with components AND the inputs that produced them (DR-05, SC-10)."),
    "refreshes": ("Core", "One row per run: reference date, replay flag, per-stage statistics, per-source errors."),
    "graph_nodes": ("Business graph", "Offers, references, partners, certifications, analyst positions, capability pools (DR-11)."),
    "graph_edges": ("Business graph", "Typed, dated, sourced edges. A partner's tier is an EDGE property, not a node one."),
    "opportunity_links": ("Business graph", "Typed links topic → asset, with evidence, confidence and the confirming curator (DR-13, LK-04…LK-08)."),
    "link_pattern_decisions": ("Business graph", "Curator adjudications; later occurrences of a pattern inherit the decision (LK-06)."),
    "market_sizes": ("Qualification", "TAM/SAM/SOM by method, every factor with its source and basis, plus caveats (§4.3.4)."),
    "reference_series": ("Qualification", "Eurostat dataset metadata including the publisher's own updated stamp and licence."),
    "reference_observations": ("Qualification", "Statistical values by indicator, industry, geography, size class and period. Denominators, not signals."),
    "topic_competition": ("Qualification", "Competitive intensity level over a named competitor list, with the evidence for each (§4.3.3)."),
    "competitor_pages": ("Competitor intel", "Crawled competitor pages — URL plus a bounded extract, never a mirror."),
    "competitor_profiles": ("Competitor intel", "One structured profile per competitor, or a recorded reason why there is none."),
    "topic_competitor_analysis": ("Competitor intel", "Per-topic join (always present) plus the written comparison (NULL until asked for)."),
    "plans": ("Planner", "One portfolio plan: the stated inputs, the projection, the flags and the narrative. The id is a fingerprint of the inputs, so a plan is immutable once computed."),
    "plan_selections": ("Planner", "One row per selected space per plan: entry year, the margin band applied, the overlap discount and the capability pool it draws on."),
    "topic_descriptions": ("Output", "Long-form narrative, each section carrying the signal ids it was written from (FR-14)."),
    "topic_briefs": ("Output", "Generated PDF metadata, stamped with every version it printed — including `brief_schema` (FR-18)."),
    "workflow_state": ("Collaboration", "Current stage and owner per topic (FR-25, §4.10 model A)."),
    "workflow_transitions": ("Collaboration", "Full stage history with actor, role and reason."),
    "assessments": ("Collaboration", "One role's rating of its own axis, superseded rather than deleted (§4.10 model C)."),
    "feedback": ("Collaboration", "Ratings, comparisons, overrides and engagement, with the exposure context (DR-15, §4.7.6)."),
    "internal_signals": ("Collaboration", "Customer conversations, RFP themes and lost deals — inert until moderated (FR-24, §2.5)."),
}
GROUP_ORDER = ["Core", "Discovery", "Business graph", "Qualification",
               "Competitor intel", "Output", "Planner", "Collaboration", "Other"]

#: (table, column) -> why it was added. The list itself is read from
#: `db.MIGRATIONS`, so a migration cannot be applied without appearing here.
MIGRATION_REASON = {
    ("topic_briefs", "brief_schema"):
        "Distinguishing an INCOMPLETE brief (missing a section that current briefs carry) from a merely STALE one.",
    ("plans", "pdf_path"): "Where the exported plan document was written.",
    ("plans", "pdf_bytes"): "Size, so the interface can show it without opening the file.",
    ("plans", "pdf_hash"): "Content hash — cache-busts the embedded viewer when a plan is re-exported.",
    ("plans", "pdf_generated_at"): "When the export was rendered.",
    ("plans", "pdf_schema"): "Which renderer version produced it, so an old export can be recognised as stale.",
}


def routes() -> list[tuple[str, str, str]]:
    from radar.api import app
    out = []
    for route in app.routes:
        path = getattr(route, "path", "")
        if not (path.startswith("/api") or path == "/healthz"):
            continue
        methods = sorted((getattr(route, "methods", set()) or set()) - {"HEAD", "OPTIONS"})
        endpoint = getattr(route, "endpoint", None)
        doc = ""
        if endpoint:
            doc = (inspect.getdoc(endpoint) or "").split("\n\n")[0].replace("\n", " ").strip()
        out.append((methods[0] if methods else "?", path, doc))
    return sorted(out, key=lambda r: (r[1], r[0]))


def write_api(rows) -> None:
    body, used = [], set()
    for title, pred in ROUTE_GROUPS:
        sel = [r for r in rows if pred(r[1]) and r[1] not in used]
        if not sel:
            continue
        used.update(r[1] for r in sel)
        body += [f"\n## {title}\n", "| Method | Path | Purpose |", "|---|---|---|"]
        for method, path, doc in sel:
            doc = (doc or "").replace("|", "\\|")
            body.append(f"| `{method}` | `{path}` | {doc[:147] + '…' if len(doc) > 150 else doc} |")
    rest = [r for r in rows if r[1] not in used]
    if rest:
        body += ["\n## Other\n", "| Method | Path | Purpose |", "|---|---|---|"]
        body += [f"| `{m}` | `{p}` | {(d or '')[:150]} |" for m, p, d in rest]

    (HERE / "API.md").write_text(f"""# API reference

The read API is a single FastAPI application (`src/radar/api.py`) that also
serves the built React bundle from the same origin. {len(rows)} endpoints.

**Generated by `docs/build_reference.py`** from the running application, so it
cannot drift from the code.

## Conventions

**Reads are `GET` and never write.** The one deliberate exception is that a
missing *derived* artefact which is pure arithmetic — the competitor join, a
competitive assessment — is computed on first read rather than making the caller
press a button for a number the system could have worked out itself. Anything
that costs a model call is a `POST`.

**`POST` means "spend something".** Description, brief, competitor comparison and
generation are all synchronous, because each is one model call and the caller is
a person who just pressed a button. A background job would need a status
endpoint to tell them the same thing.

**Filters repeat their key.** `?vertical=manufacturing&vertical=energy` — FastAPI
reads repeated keys as a list.

**Unknown `/api` paths do not 404.** The catch-all serves the app shell so a
client-side route survives a reload. The cost is that an `/api` path the *server*
does not know answers `200 text/html`, which the frontend detects and reports as
"the running server is older than the bundle it is serving" — the usual cause.
{chr(10).join(body)}

## Errors

| Status | Meaning |
|---|---|
| `404` | No such topic, competitor or artefact. |
| `409` | Well-formed, but the precondition is absent — asking for a competitor comparison on a space with no competitive assessment, for instance. |
| `503` | The serving instance could not open its database. It starts and says so rather than crash-looping (see `bootstrap.py`). |
""")
    print(f"  API.md            {len(rows)} endpoints")


def write_data_model() -> None:
    con = sqlite3.connect(DB)
    counts = {t: con.execute(f"select count(*) from {t}").fetchone()[0] for (t,) in con.execute(
        "select name from sqlite_master where type='table' and name not like 'sqlite_%'")}
    by_group: dict[str, list] = {}
    for table in sorted(counts):
        group, purpose = PURPOSE.get(table, ("Other", ""))
        by_group.setdefault(group, []).append((table, purpose))

    tables = []
    for group in GROUP_ORDER:
        if group not in by_group:
            continue
        tables += [f"\n### {group}\n", "| Table | Rows | Purpose |", "|---|---:|---|"]
        tables += [f"| `{t}` | {counts[t]:,} | {d} |" for t, d in by_group[group]]

    from radar.db import MIGRATIONS
    migrations = ["| Table | Column | Added for |", "|---|---|---|"]
    migrations += [f"| `{t}` | `{c}` | {MIGRATION_REASON.get((t, c), '')} |"
                   for t, c, _ in MIGRATIONS]

    template = (HERE / "_build" / "data_model_template.md").read_text()
    (HERE / "DATA_MODEL.md").write_text(
        template.replace("{{TABLE_COUNT}}", str(len(counts)))
                .replace("{{MIGRATIONS}}", "\n".join(migrations))
                .replace("{{TABLES}}", "\n".join(tables)))
    print(f"  DATA_MODEL.md     {len(counts)} tables")


if __name__ == "__main__":
    print("Regenerating reference documentation from live code:")
    write_api(routes())
    write_data_model()
