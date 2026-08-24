"""Live web research for one opportunity space, before the collateral is written.

WHY THIS EXISTS. The radar's corpus is built on a refresh cadence, and a piece
of pre-sales material is written on the day somebody has a meeting. Between
those two moments a regulator publishes a deadline, a competitor announces a
partnership, a tender closes. The collateral is the artefact most exposed to
that gap — it is the one that gets read out loud in front of somebody who may
already know — so this module goes and looks before the writer writes.

WHY IT IS NOT A WEB SCRAPER. Three constraints, none negotiable in this
codebase:

  ATTRIBUTION      Every claim in this system is bound to a dated, attributable
                   source. Free-text retrieval that hands a model a wall of page
                   content produces prose nobody can trace, which is the exact
                   thing the §4.4.4 defences exist to prevent. So retrieval here
                   returns ITEMS — publisher, title, date, URL, short extract —
                   and the prompt requires a claim drawn from one to name it.

  SOVEREIGNTY      NFR-05. No headless browser, no third-party search API with
                   an opaque index and a data-processing agreement nobody has
                   read. This reuses the connectors the pipeline already trusts
                   and the `HttpSession` that already throttles per host, retries
                   with backoff and trips a breaker on a dead source.

  ROBOTS AND       DR-08 / NFR-07: content is stored BY REFERENCE — URL plus a
  MIRRORING        truncated extract, never the full page. `CollectedItem`
                   truncates at the connector boundary, so nothing downstream
                   can accidentally mirror an article.

WHAT IT ACTUALLY DOES. Builds a handful of queries from the space's own
vocabulary — the vertical, the use case, the technology, the geographies, the
named competitors — runs them through the query-driven connectors already
configured in `sources.yaml`, keeps what is recent and on-topic, and returns it.
Failure is not fatal: a research pass that finds nothing, times out or has no
configured query source produces an empty list, the writer runs on the stored
corpus as before, and the document says which of the two it got.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Any

from ..config import Config

log = logging.getLogger(__name__)

#: Switch the live pass off entirely. On by default, because the whole point is
#: that collateral written today reflects today.
#:
#: It needs an off switch for three real situations, not just for tests: a CI
#: box with no route to the open internet, an air-gapped or sovereign
#: deployment where outbound calls are the thing being prevented (NFR-05), and
#: a test suite that must not depend on Google News being reachable. Read per
#: call rather than at import so it can be flipped without a restart.
ENV_FLAG = "RADAR_PRESALES_RESEARCH"


def enabled() -> bool:
    return str(os.getenv(ENV_FLAG, "1")).strip().lower() not in ("0", "false", "no", "off")

#: Connectors that take a free-text query. Only these can be pointed at a
#: specific opportunity space; a bulk-download source has no query to vary.
QUERY_CONNECTORS = ("gdelt", "rss_search")

#: How far back a research pass looks. Long enough to catch a quarter's
#: announcements, short enough that "recent" means something to a reader.
LOOKBACK_DAYS = 120

#: Items kept per query and in total. A prompt is a budget: forty half-relevant
#: headlines crowd out the space's own evidence, which is better.
PER_QUERY = 6
TOTAL = 14

#: Wall-clock ceiling for the whole pass. This runs inside a button press, and a
#: research step that turns a ten-second generate into a ninety-second one will
#: be switched off by the people it was built for.
TIMEOUT_SECONDS = 25

#: Sources per pass. `sources.yaml` configures ten query-capable feeds — GDELT
#: plus a Google News feed per region — and running all of them against five
#: queries is fifty throttled requests, which cannot finish inside the budget
#: above. Three is enough: these feeds overlap heavily, so the fourth mostly
#: returns what the first three already did, and `_rank` would drop it anyway.
MAX_SOURCES = 3


def _queries(ctx: Any) -> list[str]:
    """Targeted queries from the space's own vocabulary.

    Built from the labels rather than from the statement: a statement is a
    sentence and makes a poor query, while vertical × use case × technology is
    exactly the three-term intersection that finds the announcement worth
    knowing about. The geography term matters more than it looks — the same use
    case in Germany and in France is two different regulatory conversations.
    """
    labels = ctx.topic.get("labels") or {}
    vertical = str(labels.get("vertical") or "").strip()
    use_case = str(labels.get("use_case") or "").strip()
    technology = str(labels.get("technology") or "").strip()
    geographies = [str(g) for g in (ctx.topic.get("geographies") or [])][:2]

    out: list[str] = []
    if use_case and technology:
        out.append(f"{use_case} {technology}")
    if vertical and use_case:
        out.append(f"{vertical} {use_case}")
    for geography in geographies:
        if use_case:
            out.append(f"{use_case} {vertical} {geography}".strip())
    # One competitor query, not one per competitor: the point is to notice a
    # move in this space, not to profile the field — `competitor_intel` already
    # does that properly, from each competitor's own pages.
    competitors = ctx.competitor_names[:2]
    if competitors and use_case:
        out.append(f"{competitors[0]} {use_case}")
    return [q for q in dict.fromkeys(q.strip() for q in out) if len(q) > 6][:5]


def _sources(cfg: Config) -> list[dict[str, Any]]:
    """The configured, ENABLED sources that accept a query.

    `Config.enabled_sources` rather than a raw settings lookup, so a source
    disabled in `sources.yaml` stays disabled here — a research pass must not
    reach a source the pipeline has been told not to touch, whether it was
    switched off for terms-of-use reasons (NFR-07) or because it is broken.
    """
    candidates = [source for source in cfg.enabled_sources()
                  if source.get("connector") in QUERY_CONNECTORS]
    # Deliberately NOT GDELT-first. It carries geography and tone, which is why
    # the pipeline values it, but it is also the most aggressively throttled of
    # the ten and answers 429 to everything once it has decided you have had
    # enough. Leading with it spends a short budget on the source least likely
    # to answer, so the news feeds go first and GDELT takes whatever is left.
    candidates.sort(key=lambda s: 1 if s.get("connector") == "gdelt" else 0)
    return candidates[:MAX_SOURCES]


def gather(cfg: Config, ctx: Any) -> list[dict[str, Any]]:
    """Recent, dated, attributable items about this space. Never raises.

    Every failure mode — no query sources configured, a malformed source entry,
    a source that is down, a network with no route out, a slow API — produces an
    empty list and a log line. Research is an ENRICHMENT: the collateral was
    buildable without it before this module existed and must stay buildable
    without it, because the alternative is a sales team unable to produce a
    battlecard because a news API is rate-limiting.

    The blanket guard is deliberate and is the only one in this package. Every
    other failure here is reported ON the document, where a reader can act on
    it; this one has nothing to report — the document is simply the one the
    system would have produced anyway.
    """
    if not enabled():
        log.info("Research disabled by %s — building %s from the stored corpus only",
                 ENV_FLAG, getattr(ctx, "topic_id", "?"))
        return []
    try:
        return _gather(cfg, ctx)
    except Exception as exc:  # noqa: BLE001 — enrichment must never break a build
        log.warning("Research pass for %s failed and was skipped: %s",
                    getattr(ctx, "topic_id", "?"), exc)
        return []


def _gather(cfg: Config, ctx: Any) -> list[dict[str, Any]]:
    from ..connectors import HttpSession, build_connector

    queries = _queries(ctx)
    sources = _sources(cfg)
    if not queries or not sources:
        log.info("Research skipped for %s: %d queries, %d query-capable sources",
                 ctx.topic_id, len(queries), len(sources))
        return []

    ingestion = cfg.settings["ingestion"]
    session = HttpSession(
        cfg.user_agent,
        timeout=min(int(ingestion["request_timeout_seconds"]), 10),
        # One cheap retry, against the pipeline's three. These are free APIs
        # behind hard rate limits — GDELT answers 429 to everything once it has
        # decided you have had enough — and a long backoff inside a button press
        # buys nothing. One second covers a transient blip; anything worse is a
        # source that is not going to answer, and the deadline below handles it.
        max_retries=1,
        backoff=1,
    )
    reference_date = dt.date.today()
    collected: list[dict[str, Any]] = []

    def run(job: tuple[dict[str, Any], str]) -> list[dict[str, Any]]:
        source, query = job
        # The source is copied with its queries replaced, so a research pass
        # cannot mutate the configured source and leak into the next refresh.
        scoped = dict(source)
        scoped["params"] = dict(source.get("params") or {}) | {"queries": [query]}
        connector = build_connector(scoped, session, ingestion["max_extract_chars"])
        if connector is None:
            return []
        try:
            items = list(connector.collect(reference_date, LOOKBACK_DAYS))
        except Exception as exc:  # noqa: BLE001 — one bad source must not stop the pass
            log.info("Research query %r against %s failed: %s", query, source.get("id"), exc)
            return []
        return [_shape(item, query) for item in items[:PER_QUERY]]

    jobs = [(source, query) for source in sources for query in queries]
    # `pool.map(..., timeout=)` bounds only the ITERATION; the executor's own
    # __exit__ then joins every outstanding thread, so a throttled source pushed
    # a nominal 25-second budget to 58 real seconds. Futures plus an explicit
    # deadline plus a non-waiting shutdown is what actually bounds it: whatever
    # has landed by the deadline is used, and the rest is abandoned.
    pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="presales-research")
    try:
        futures = [pool.submit(run, job) for job in jobs]
        done, pending = wait(futures, timeout=TIMEOUT_SECONDS)
        for future in done:
            try:
                collected.extend(future.result())
            except Exception as exc:  # noqa: BLE001
                log.info("Research job failed: %s", exc)
        if pending:
            log.info("Research for %s: %d of %d queries finished inside %ds",
                     ctx.topic_id, len(done), len(futures), TIMEOUT_SECONDS)
            for future in pending:
                future.cancel()
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    return _rank(collected)[:TOTAL]


def _shape(item: Any, query: str) -> dict[str, Any]:
    published = getattr(item, "published_at", None)
    return {
        "title": str(getattr(item, "title", "") or "")[:200],
        "url": str(getattr(item, "url", "") or ""),
        "publisher": str(getattr(item, "publisher", "") or "") or "unattributed",
        "published_at": (published.isoformat()[:10] if hasattr(published, "isoformat")
                         else str(published or "")[:10]),
        "extract": str(getattr(item, "extract", "") or "")[:400],
        "query": query,
    }


def _rank(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """De-duplicate by URL, then newest first.

    Newest rather than most-relevant on purpose: the reason to do this at all is
    the gap between the last refresh and today, so recency IS the relevance
    signal. Anything older than the corpus is already in the corpus.
    """
    seen: set[str] = set()
    unique = []
    for item in items:
        key = item["url"] or item["title"]
        if not key or key in seen or not item["title"]:
            continue
        seen.add(key)
        unique.append(item)
    return sorted(unique, key=lambda i: i["published_at"] or "", reverse=True)


def as_prompt_block(items: list[dict[str, Any]]) -> str:
    """The research, formatted for a prompt, with the citation rule attached.

    The rule is stated at both ends — here and in the system prompt — because
    this is the one block in the context that the space's own evidence
    validators have never seen. Everything else a writer is given has already
    been through entailment checking; these items have not, so the requirement
    to attribute is the only thing standing between a fresh headline and an
    unsourced claim in front of a customer.
    """
    if not items:
        return ""
    lines = [
        "",
        "RECENT PUBLIC ITEMS, retrieved today, newer than the radar's last refresh.",
        "These have NOT been through the radar's evidence validation. Use them to make the "
        "material current, and obey both rules:",
        "  1. Any statement you draw from one of these must name its publisher inline, "
        "for example: \"(Handelsblatt, 2026-07-14)\". A claim from here without its source "
        "is worse than no claim.",
        "  2. The NO GENERATED NUMBERS rule still applies. A figure appearing in one of these "
        "extracts may be quoted ONLY with its source named; a figure you infer from them may "
        "not be stated at all.",
        "",
    ]
    for item in items:
        lines.append(f"- [{item['publisher']}, {item['published_at'] or 'undated'}] "
                     f"{item['title']}")
        if item["extract"]:
            lines.append(f"    {item['extract']}")
    return "\n".join(lines)
