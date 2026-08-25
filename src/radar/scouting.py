"""Go and look, for one brief, on demand (FR-06 with the NFR-04 caveat stated).

WHY THIS EXISTS, AND WHY IT IS A DEPARTURE. A scheduled refresh collects; a
generation run does not. That separation is what lets the Generate screen say
"the evidence does not support that" and mean something: the corpus is fixed
while you look at it, so an empty answer is a finding rather than a timeout, and
NFR-04's promise that a run "collected nothing new" is what makes a run
reproducible.

The cost of that separation is a screen that answers a genuinely new idea with
"nobody has published about this" and then stops. That is the correct statement
about the corpus and the wrong end to the conversation, because the corpus is
not the world — it is a taxonomy-driven crawl of it, and an idea outside the
crawl's query grid is absent from the corpus for reasons that have nothing to do
with whether anybody has written about it.

So this fetches for ONE brief, from the sources that take a free-text query and
need no key, and puts what it finds through the ordinary front door: the same
relevance gate, the same signal-type classifier, the same tiering, the same
embedding. Nothing here writes an opportunity space and nothing here bypasses a
check. What comes back is either evidence — dated, attributed, openable — or
nothing, and a run that then finds nothing has a much better claim to be telling
you something about the world.

TWO THINGS IT DELIBERATELY DOES NOT DO. It does not re-cluster (that is a
whole-corpus operation and a per-brief run has no business reshaping the theme
map everybody else reads). And it does not touch the refresh cadence's own
record: what it collects is recorded against the generation run that asked for
it, so a corpus that grew mid-week is traceable to the person who grew it.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from .config import Config
from .db import Database
from .embeddings import Embedder
from .llm import LLMClient, LLMError
from .pipeline.ingest import IngestStats, Ingestor
from .pipeline.query_grid import expand_source_params
from .connectors import build_connector

log = logging.getLogger(__name__)

#: Sources that take a free-text query and need no API key. Everything else in
#: `sources.yaml` is either a fixed feed (nothing to steer), a procurement
#: endpoint keyed on CPV rather than words, or gated behind a key this
#: deployment does not hold.
SEARCHABLE = ("google_news", "bing_news", "gdelt", "openalex", "arxiv")

#: How far back an on-demand look reaches. Wider than the cadence's default
#: window because this is answering "has anyone ever written about this", not
#: "what moved this week".
SINCE_DAYS = 365

#: Queries per brief. Each one costs a round trip per source, and past three or
#: four they stop being different questions and start being paraphrases.
MAX_QUERIES = 4


def queries_for(llm: LLMClient, description: str) -> list[str]:
    """Turn a brief into search phrases a news or paper index would answer.

    Asked of the model rather than assembled from the taxonomy, because the
    taxonomy grid is precisely what did not cover this idea — building the query
    from vocabulary ids would go back and fetch the same corpus that is already
    silent about it.
    """
    system = (
        "MOCK_KIND=scout_queries\n"
        "You turn a description of a business opportunity into search queries for a news index "
        "and an academic index.\n\n"
        "Write the words a journalist or a researcher would actually use, not the words a "
        "strategist would. Concrete nouns; the thing itself, the people who buy it, the problem "
        "it solves. No boolean operators, no quotes, no site: filters. Three to four queries, "
        "each different enough to reach different documents — not paraphrases of one another.\n\n"
        'Return JSON: {"queries": ["...", "..."]}'
    )
    try:
        raw = llm.complete_json(system, description, temperature=0.2, max_tokens=300)
        out = [" ".join(str(q).split()) for q in (raw.get("queries") or []) if str(q).strip()]
    except (LLMError, AttributeError) as exc:
        log.warning("Could not derive scout queries (%s); falling back to the brief itself", exc)
        out = []
    if not out:
        # The brief itself is a serviceable query and always available.
        out = [" ".join(description.split())[:180]]
    return out[:MAX_QUERIES]


def research_brief(cfg: Config, db: Database, llm: LLMClient, embedder: Embedder,
                   description: str, refresh_id: str,
                   progress=None) -> dict[str, Any]:
    """Fetch, gate, classify and embed evidence for one brief.

    Returns what it found. Everything it stores is an ordinary signal: tiered by
    its source, gated for relevance, typed, dated, and openable at a URL. The
    only thing unusual about it is when it arrived.
    """
    def say(message: str) -> None:
        log.info(message)
        if progress:
            progress(message)

    queries = queries_for(llm, description)
    say(f"Searching for: {'; '.join(queries)}")

    ingestor = Ingestor(cfg, db, llm)
    stats = IngestStats()
    by_source: dict[str, int] = {}
    reference_date = dt.date.today()

    for source_id in SEARCHABLE:
        base = next((s for s in cfg.sources["sources"] if s["id"] == source_id), None)
        if base is None:
            continue
        source = expand_source_params(cfg, dict(base))
        # The taxonomy grid is what missed this idea; override it with the
        # brief's own words rather than adding to it.
        source["params"] = dict(source.get("params") or {}) | {"queries": queries}
        connector = build_connector(source, ingestor.session, ingestor.max_extract)
        if connector is None:
            continue
        before = stats.new_signals
        try:
            items = list(connector.collect(reference_date, SINCE_DAYS))
            ingestor._store(items, source, refresh_id, stats)
        except Exception as exc:  # noqa: BLE001 — one dead source must not stop the look
            say(f"  {source_id}: unavailable ({type(exc).__name__})")
            continue
        found = stats.new_signals - before
        by_source[source_id] = found
        say(f"  {source_id}: {found} new item(s)")

    if not stats.new_signals:
        say("Nothing new was found. The corpus is not missing this because of the crawl — "
            "as far as these sources go, it does not appear to have been written about.")
        return {"queries": queries, "stored": 0, "kept": 0, "by_source": by_source,
                "fetched": stats.fetched}

    say(f"{stats.new_signals} new item(s) stored — gating and classifying them…")
    classified = ingestor.classify(refresh_id)
    kept = _embed_new(db, embedder)
    say(f"{kept} cleared the relevance gate and are now evidence the run can cite.")
    return {"queries": queries, "stored": stats.new_signals, "kept": kept,
            "fetched": stats.fetched, "duplicates": stats.duplicates,
            "by_source": by_source, "classified": classified}


def _embed_new(db: Database, embedder: Embedder) -> int:
    """Embed anything relevant that has no vector yet.

    Retrieval filters on `relevance > 0 AND embedding IS NOT NULL`, so a signal
    without a vector is invisible to the very run that went and fetched it —
    which is the same trap `internal.promote` fell into. Deliberately does NOT
    cluster: the theme map is a whole-corpus artefact and one brief has no
    business reshaping what everybody else reads.
    """
    rows = db.query(
        "SELECT id, title, extract FROM signals "
        "WHERE relevance > 0 AND embedding IS NULL ORDER BY published_at DESC")
    if not rows:
        return 0
    vectors = embedder.encode([f"{r['title']}. {r['extract']}" for r in rows])
    with db.cursor() as cur:
        for row, vector in zip(rows, vectors):
            cur.execute("UPDATE signals SET embedding = ? WHERE id = ?",
                        (Embedder.to_blob(vector), row["id"]))
    return len(rows)
