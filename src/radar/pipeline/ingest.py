"""Pipeline stages 1-3: Collect, Normalise, Classify & filter (Table 16).

Stage 1  Source configuration -> raw items
Stage 2  Raw items -> signal records (dedup, language, dates, geography)
Stage 3  Signal records -> typed, tiered signals (relevance gate)

The relevance gate exists to drop obviously irrelevant items cheaply "before any
expensive step" (Table 16). It runs a deterministic keyword pre-filter first and
only escalates the ambiguous middle to a model — Table 23 assigns relevance
gating to "the cheapest thing that works", and most items are decided without
inference at all.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Iterable

from ..config import Config
from ..connectors import CollectedItem, HttpSession, build_connector
from ..db import Database, js
from ..llm import LLMClient
from .query_grid import expand_source_params

log = logging.getLogger(__name__)

PROMPT_VERSION_SIGNAL_TYPE = "sigtype-v1"
PROMPT_VERSION_RELEVANCE = "relgate-v1"


@dataclass
class IngestStats:
    fetched: int = 0
    stored_raw: int = 0
    new_signals: int = 0
    duplicates: int = 0
    undated_rejected: int = 0
    malformed: int = 0
    gated_out: int = 0
    per_source: dict[str, int] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "fetched": self.fetched,
            "stored_raw": self.stored_raw,
            "new_signals": self.new_signals,
            "duplicates": self.duplicates,
            "undated_rejected": self.undated_rejected,
            "malformed": self.malformed,
            "gated_out": self.gated_out,
            "per_source": self.per_source,
            "errors": self.errors,
        }


def _is_storable(item: CollectedItem) -> bool:
    """Every field bound into SQL must be a string by the time it gets here."""
    return (isinstance(item.url, (str, type(None)))
            and isinstance(item.publisher, str)
            and isinstance(item.title, str)
            and isinstance(item.extract, str))


class Ingestor:
    def __init__(self, cfg: Config, db: Database, llm: LLMClient | None = None):
        self.cfg = cfg
        self.db = db
        self.llm = llm
        ing = cfg.settings["ingestion"]
        self.session = HttpSession(
            cfg.user_agent,
            timeout=ing["request_timeout_seconds"],
            max_retries=ing["max_retries"],
            backoff=ing["retry_backoff_seconds"],
        )
        self.max_extract = ing["max_extract_chars"]
        self.archive_raw = ing.get("archive_raw", True)
        self._relevance_terms = self._build_relevance_terms()
        #: The dedup index, built once per Ingestor and kept in step by `_store`.
        #: See `_dedup_index` for why it is not a query.
        self._seen_urls: set[str] | None = None
        self._seen_content: set[str] = set()

    # -- stage 1 -----------------------------------------------------------

    def collect(self, reference_date: dt.date, refresh_id: str, since_days: int = 30,
                source_ids: list[str] | None = None, max_workers: int | None = None) -> IngestStats:
        """Fetch every enabled source, concurrently.

        Collection is almost entirely network-bound and the sources are
        independent, so they run in a thread pool. This matters more than it
        looks: sources have very different shapes — TED issues one request per
        CPV group per time slice, EUR-Lex one slow SPARQL query, GDELT a paced
        crawl — and run serially the refresh takes as long as their sum. NFR-04
        asks the refresh to complete inside its cadence window.

        Two things stay strictly serial:

        * DATABASE WRITES. SQLite tolerates one writer, and dedup (Table 16
          stage 2) is a read-modify-write against the whole signal table — two
          threads inserting the same syndicated article would both see "no
          duplicate" and both insert. Results are therefore collected in
          parallel and stored on the calling thread.
        * PER-HOST PACING. HttpSession throttles by host, so a connector's own
          rate limit is still honoured inside its thread.
        """
        stats = IngestStats()
        sources = self.cfg.enabled_sources()
        if source_ids:
            sources = [s for s in sources if s["id"] in source_ids]

        jobs: list[tuple[dict[str, Any], Any, int]] = []
        for source in sources:
            # NFR-11: resolve `queries_from_taxonomy` / `cpv_from_taxonomy` into
            # literal params here, so connectors never need a Config and stay
            # testable on a params dict alone.
            source = expand_source_params(self.cfg, source)
            connector = build_connector(source, self.session, self.max_extract)
            if connector is None:
                continue
            window = int(source.get("params", {}).get("since_days", since_days))
            jobs.append((source, connector, window))
        if not jobs:
            return stats

        workers = max_workers or min(len(jobs), int(self.cfg.settings["ingestion"].get("max_parallel_sources", 8)))

        def fetch(job: tuple[dict[str, Any], Any, int]) -> tuple[dict[str, Any], list[CollectedItem], str | None]:
            source, connector, window = job
            log.info("Collecting from %s (window %dd)…", source["id"], window)
            try:
                items = list(connector.collect(reference_date, window))
            except Exception as exc:  # noqa: BLE001 — one bad source must not kill the refresh
                log.exception("Connector %s failed", source["id"])
                return source, [], f"{type(exc).__name__}: {exc}"
            log.info("  %s → %d items", source["id"], len(items))
            return source, items, None

        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="collect") as pool:
            futures = [pool.submit(fetch, job) for job in jobs]
            for future in as_completed(futures):
                source, items, error = future.result()
                if error:
                    stats.errors[source["id"]] = error
                    continue
                stats.fetched += len(items)
                stats.per_source[source["id"]] = len(items)
                # Serial write, on this thread only.
                self._store(items, source, refresh_id, stats)

        # A source whose circuit tripped contributed nothing and must say so.
        # §4.12 lists silent coverage loss as a real risk; a source that quietly
        # returns zero looks identical to a source with no news.
        for host in sorted(self.session.tripped):
            stats.errors[host] = "circuit breaker opened — source unreachable this refresh"
        return stats

    # -- stage 2 -----------------------------------------------------------

    @staticmethod
    def _content_key(publisher: str, extract: str) -> str:
        """The identity a syndicated duplicate shares: same publisher, same words."""
        return hashlib.blake2b(
            f"{publisher}\x00{extract}".encode("utf-8", "replace"), digest_size=16
        ).hexdigest()

    def _dedup_index(self) -> set[str]:
        """URLs already in the signal store, loaded once for the whole run.

        The check used to be one query per collected item:

            SELECT id FROM signals WHERE url = ? OR (publisher = ? AND extract = ?)

        which SQLite plans as a full table SCAN — the `OR` defeats
        `idx_signals_url`, and there is no index the second branch could use
        because `extract` is a 1,200-character column nobody would want one on.
        At 11,500 signals that is ~8 ms per item, and both sides of it grow: a
        refresh collecting n items against a corpus of m signals did O(n*m) work,
        so the dedup step got slower every week for the same amount of new
        evidence.

        Writes are serial on the calling thread (see `collect`), so the set can
        simply be read once and kept in step by `_store`. Same rule, two lookups
        that cost nothing.
        """
        if self._seen_urls is None:
            self._seen_urls = set()
            # Streamed rather than fetched whole. What is KEPT is small — a URL
            # and a 32-character digest per signal — but `extract` is up to
            # 1,200 characters, so materialising the table to build the set
            # would hold tens of megabytes of text that is thrown away a row
            # later, and would keep growing with the corpus.
            conn = self.db.connect()
            try:
                for url, publisher, extract in conn.execute(
                        "SELECT url, publisher, extract FROM signals"):
                    if url:
                        self._seen_urls.add(url)
                    self._seen_content.add(self._content_key(publisher or "", extract or ""))
            finally:
                conn.close()
        return self._seen_urls

    def _store(self, items: Iterable[CollectedItem], source: dict[str, Any],
               refresh_id: str, stats: IngestStats) -> None:
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        with self.db.cursor() as cur:
            for item in items:
                # DR-04: undated evidence is either dated by inference at
                # ingestion or rejected. No connector infers a date today, so
                # undated items are rejected and counted rather than silently
                # given today's date — which would corrupt every momentum and
                # backtest computation downstream.
                if item.published_at is None:
                    stats.undated_rejected += 1
                    continue

                # A connector that yields a non-string where a string belongs
                # must not be able to abort the refresh. This is not
                # hypothetical: TenderNed returns `link` as an object rather
                # than a URL, and one such row raised out of the whole collect
                # stage AFTER all 33 sources had been fetched — discarding
                # thousands of items that were already in hand. Fetch failures
                # were already isolated per source (see `collect`); the store
                # path had no equivalent guard, so it has one now.
                if not _is_storable(item):
                    log.warning("%s yielded an unstorable item (url=%r, publisher=%r) — skipped",
                                item.source_id, type(item.url).__name__, type(item.publisher).__name__)
                    stats.malformed += 1
                    continue

                content_hash = item.content_hash()
                raw_id = item.raw_id()

                # Deduplicate by URL and by (publisher, extract) — Table 16
                # stage 2, unchanged. Only where the answer comes from has moved:
                # see `_dedup_index`.
                seen_urls = self._dedup_index()
                # `item.publisher or item.source_id` is what the INSERT below
                # actually stores, so it is what the index has to be probed with.
                # The old query compared the raw `item.publisher`, which is empty
                # for every source that does not name one — those items could
                # never match their own stored duplicate.
                content_key = self._content_key(item.publisher or item.source_id, item.extract)
                if (item.url and item.url in seen_urls) or content_key in self._seen_content:
                    stats.duplicates += 1
                    continue

                if self.archive_raw:
                    cur.execute(
                        "INSERT OR IGNORE INTO raw_items (id, source_id, url, fetched_at, payload, content_hash) "
                        "VALUES (?,?,?,?,?,?)",
                        (raw_id, item.source_id, item.url, now,
                         json.dumps(item.payload, ensure_ascii=False, default=str), content_hash),
                    )
                    stats.stored_raw += 1

                signal_id = "SIG-" + hashlib.sha256(
                    f"{item.source_id}|{item.url}|{content_hash}".encode()
                ).hexdigest()[:12].upper()

                tier = self._tier_for(item)
                language = item.language or _detect_language(f"{item.title} {item.extract}")

                cur.execute(
                    """INSERT OR IGNORE INTO signals
                       (id, source_id, publisher, title, url, published_at, published_at_inferred,
                        ingested_at, language, geographies, signal_type, signal_type_confidence,
                        tier, extract, attributes, raw_item_id, pipeline_version)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        signal_id, item.source_id, item.publisher or item.source_id, item.title,
                        item.url, item.published_at.isoformat(), int(item.published_at_inferred),
                        now, language, js(item.geographies),
                        item.signal_type_hint, 1.0 if item.signal_type_hint else None,
                        tier, item.extract, js(item.attributes),
                        raw_id if self.archive_raw else None, self.cfg.pipeline_version,
                    ),
                )
                if cur.rowcount:
                    stats.new_signals += 1
                    # Kept in step as the row lands, so two items inside one
                    # batch still deduplicate against each other.
                    if item.url:
                        seen_urls.add(item.url)
                    self._seen_content.add(content_key)
                else:
                    stats.duplicates += 1

    def _tier_for(self, item: CollectedItem) -> int:
        """Assign a source tier (§4.3.7).

        Publisher overrides beat the connector's declared tier, and a
        press-release URL marker beats both — Table 36's echo-chamber risk is
        "inflated scores for whatever is best-marketed", and a vendor press
        release syndicated by a credible outlet is still a vendor press release.
        """
        cfg = self.cfg.source_tiers
        url_lower = (item.url or "").lower()
        for marker in cfg.get("press_release_markers", []):
            if marker in url_lower:
                return 4
        publisher = (item.publisher or "").lower()
        host = publisher if "." in publisher else ""
        overrides = cfg.get("publisher_overrides", {})
        for domain, tier in overrides.items():
            if host.endswith(domain) or domain in url_lower:
                return int(tier)
        source = next((s for s in self.cfg.sources["sources"] if s["id"] == item.source_id), {})
        return int(source.get("default_tier", 3))

    # -- stage 3 -----------------------------------------------------------

    def _build_relevance_terms(self) -> set[str]:
        """Vocabulary-derived keyword set for the cheap half of the gate.

        Built from the taxonomy rather than hand-written, so extending the
        vocabulary automatically extends the gate (NFR-11).
        """
        terms: set[str] = set()
        for vocab in (self.cfg.use_cases, self.cfg.technologies, self.cfg.domains):
            for item in vocab:
                terms.add(item.label.lower())
                terms.update(s.lower() for s in item.synonyms)
        for item in self.cfg.verticals:
            terms.add(item.label.lower())
            terms.update(s.lower() for s in item.synonyms)
        for ambition in self.cfg.strategy.get("ambitions", []):
            terms.update(m.lower() for m in ambition.get("markers", []))
        for axis in self.cfg.domains.raw.get("cross_cutting", []):
            terms.update(m.lower() for m in axis.get("markers", []))
        # FR-28. Everything above is English, and a term scoring zero here is
        # dropped before the model ever sees it — so an English-only gate does
        # not merely rank non-English signals lower, it deletes them. The first
        # live corpus made that visible: French signals averaged 0.06 relevance
        # against 0.26 for English, and 52% never received a signal type at all.
        terms.update(self.cfg.lexicon_terms())
        # Drop very short tokens that would match everything.
        return {t for t in terms if len(t) >= 4}

    def keyword_relevance(self, text: str) -> tuple[float, list[str]]:
        lowered = text.lower()
        hits = [term for term in self._relevance_terms if term in lowered]
        if not hits:
            return 0.0, []
        # Saturating: three distinct vocabulary hits is already a strong signal.
        return min(1.0, len(set(hits)) / 3.0), sorted(set(hits))[:8]

    def classify(self, refresh_id: str, use_llm: bool = True, limit: int | None = None) -> dict[str, Any]:
        """Relevance-gate and signal-type every unclassified signal."""
        rows = self.db.query(
            "SELECT id, title, extract, signal_type, publisher, source_id FROM signals "
            "WHERE relevance IS NULL ORDER BY published_at DESC" + (f" LIMIT {int(limit)}" if limit else "")
        )
        if not rows:
            return {"classified": 0, "gated_out": 0, "llm_calls": 0}

        gated_out = 0
        llm_before = self.llm.calls if self.llm else 0
        pending_type: list[dict[str, Any]] = []

        with self.db.cursor() as cur:
            for row in rows:
                text = f"{row['title']} {row['extract']}"
                score, hits = self.keyword_relevance(text)
                reason = f"vocabulary hits: {', '.join(hits)}" if hits else "no vocabulary term matched"
                cur.execute(
                    "UPDATE signals SET relevance = ?, relevance_reason = ? WHERE id = ?",
                    (score, reason, row["id"]),
                )
                if score <= 0.0:
                    gated_out += 1
                    continue
                if not row["signal_type"]:
                    pending_type.append({"id": row["id"], "title": row["title"], "extract": row["extract"][:300]})

        typed = 0
        if pending_type and use_llm and self.llm is not None:
            typed = self._classify_signal_types(pending_type)
        elif pending_type:
            typed = self._classify_signal_types_heuristic(pending_type)

        return {
            "classified": len(rows),
            "gated_out": gated_out,
            "typed": typed,
            "llm_calls": (self.llm.calls - llm_before) if self.llm else 0,
        }

    def _classify_signal_types(self, pending: list[dict[str, Any]]) -> int:
        """Six well-defined classes, few-shot, on the cheap model (Table 23)."""
        batch_size = self.cfg.settings["llm"]["classify_batch_size"]
        type_ids = self.cfg.signal_types.ids
        system = (
            "MOCK_KIND=signal_type\n"
            "You classify business-intelligence signals for an innovation radar at Orange Business.\n"
            "Assign exactly one type to each item from this closed list:\n"
            + self.cfg.signal_types.prompt_block()
            + "\n\nReturn JSON: {\"items\": [{\"id\": \"<id>\", \"type\": \"<type id>\", \"confidence\": 0.0-1.0}]}\n"
            "Use only type ids from the list. If genuinely unclear, use \"trend\" with low confidence."
        )
        typed = 0
        for start in range(0, len(pending), batch_size):
            batch = pending[start:start + batch_size]
            user = json.dumps({"items": batch}, ensure_ascii=False)
            try:
                payload = self.llm.complete_json(
                    system, user,
                    temperature=self.cfg.settings["llm"]["temperature_classify"],
                    max_tokens=1500,
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("Signal-type classification batch failed: %s — falling back to heuristic", exc)
                typed += self._classify_signal_types_heuristic(batch)
                continue
            with self.db.cursor() as cur:
                for entry in payload.get("items", []):
                    stype = entry.get("type")
                    if stype not in type_ids:
                        continue
                    cur.execute(
                        "UPDATE signals SET signal_type = ?, signal_type_confidence = ?, "
                        "prompt_version = ?, model_version = ? WHERE id = ?",
                        (stype, float(entry.get("confidence", 0.5)), PROMPT_VERSION_SIGNAL_TYPE,
                         self.llm.cheap_model, entry.get("id")),
                    )
                    typed += cur.rowcount
        return typed

    _HEURISTIC_PATTERNS = (
        ("regulation", re.compile(r"\b(directive|regulation|compliance|deadline|legal|act|law|mandat)", re.I)),
        ("buying_signal", re.compile(r"\b(tender|procurement|contract award|rfp|framework agreement)", re.I)),
        ("proof_signal", re.compile(r"\b(deploy|rollout|case study|go[- ]live|pilot result|implemented)", re.I)),
        ("market_move", re.compile(r"\b(acquisit|merger|partnership|launch|invest|joint venture)", re.I)),
        ("technology_maturity", re.compile(r"\b(standard|release|specification|patent|research|benchmark)", re.I)),
    )

    def _classify_signal_types_heuristic(self, pending: list[dict[str, Any]]) -> int:
        """Deterministic fallback so the pipeline runs without an LLM."""
        typed = 0
        with self.db.cursor() as cur:
            for entry in pending:
                text = f"{entry['title']} {entry.get('extract', '')}"
                stype = "trend"
                for candidate, pattern in self._HEURISTIC_PATTERNS:
                    if pattern.search(text):
                        stype = candidate
                        break
                cur.execute(
                    "UPDATE signals SET signal_type = ?, signal_type_confidence = ?, prompt_version = ? WHERE id = ?",
                    (stype, 0.35, "heuristic-v1", entry["id"]),
                )
                typed += cur.rowcount
        return typed


_FR_MARKERS = re.compile(
    r"\b(le|la|les|des|une|pour|avec|dans|sur|est|sont|aux|par|leur|cette|nous|vous)\b", re.I
)
_DE_MARKERS = re.compile(r"\b(der|die|das|und|mit|für|von|den|dem|ein|eine|nicht|auch)\b", re.I)


def _detect_language(text: str) -> str:
    """Cheap language guess for FR-28 / NFR-08 coverage monitoring.

    Deliberately trivial: it only needs to distinguish the languages the MVP
    ingests well enough to report coverage, and NFR-08 requires that language
    coverage is MONITORED, not that it is perfectly labelled.
    """
    sample = text[:400]
    fr = len(_FR_MARKERS.findall(sample))
    de = len(_DE_MARKERS.findall(sample))
    if fr >= 3 and fr > de:
        return "fr"
    if de >= 3 and de > fr:
        return "de"
    return "en"
