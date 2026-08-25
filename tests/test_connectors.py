"""Connector parsing and concurrency invariants (stage 1, FR-35, NFR-04)."""

from __future__ import annotations

import datetime as dt
import threading

import pytest

from radar.connectors import HttpSession, REGISTRY
from radar.connectors.extra import _cordis_date
from radar.connectors.procurement import _as_list, _pick_language

REF = dt.date(2026, 8, 17)


def test_every_configured_connector_is_implemented():
    """config/sources.yaml is the requirements record, but an ENABLED source
    whose connector is missing would silently contribute nothing."""
    from radar.config import get_config

    for source in get_config().enabled_sources():
        assert source["connector"] in REGISTRY, (
            f"source {source['id']!r} is enabled but connector {source['connector']!r} is not implemented"
        )


# ---------------------------------------------------------------------------
# CORDIS date template — the bug that made the connector return nothing
# ---------------------------------------------------------------------------

def test_cordis_unsubstituted_month_template_is_parsed():
    """CORDIS leaks its own i18n template and returns `1 {{month_11}} 2023`.

    parse_date cannot read that, so every project was rejected as undated
    (DR-04) and the connector yielded zero items with no error.
    """
    assert _cordis_date("1 {{month_11}} 2023") == dt.date(2023, 11, 1)
    assert _cordis_date("26 {{month_07}} 2025") == dt.date(2025, 7, 26)


def test_cordis_date_falls_back_to_normal_parsing():
    assert _cordis_date("2024-03-01") == dt.date(2024, 3, 1)


def test_cordis_date_rejects_nonsense_rather_than_guessing():
    assert _cordis_date("99 {{month_44}} 2023") is None
    assert _cordis_date(None) is None
    assert _cordis_date("") is None


# ---------------------------------------------------------------------------
# TED multilingual payloads
# ---------------------------------------------------------------------------

def test_ted_prefers_english_from_a_multilingual_field():
    assert _pick_language({"fra": "Services", "eng": "Services EN"}) == "Services EN"


def test_ted_falls_back_to_any_language_rather_than_dropping_the_notice():
    """A Bulgarian-only notice is still a buying signal."""
    assert _pick_language({"bul": "Услуги"}) == "Услуги"


def test_ted_handles_scalars_and_lists():
    assert _pick_language("plain") == "plain"
    assert _pick_language(None) == ""
    assert _as_list(None) == []
    assert _as_list("x") == ["x"]
    assert _as_list(["x", "y"]) == ["x", "y"]


# ---------------------------------------------------------------------------
# Circuit breaker (NFR-04) — one dead source must not consume the refresh
# ---------------------------------------------------------------------------

def test_circuit_breaker_opens_after_the_failure_budget():
    session = HttpSession("test", failure_budget=2)
    session._record_failure("api.example.com")
    assert "api.example.com" not in session.tripped
    session._record_failure("api.example.com")
    assert "api.example.com" in session.tripped
    # Once open, requests short-circuit instead of retrying.
    assert session.get("https://api.example.com/anything") is None


def test_circuit_breaker_is_per_host():
    session = HttpSession("test", failure_budget=1)
    session._record_failure("dead.example.com")
    assert "dead.example.com" in session.tripped
    assert "healthy.example.com" not in session.tripped


def test_a_success_clears_the_failure_history():
    """A transient blip must not push a healthy source toward its budget."""
    session = HttpSession("test", failure_budget=2)
    session._record_failure("api.example.com")
    session._failures.pop("api.example.com", None)   # what a 2xx does
    session._record_failure("api.example.com")
    assert "api.example.com" not in session.tripped


# ---------------------------------------------------------------------------
# Concurrency (Ingestor.collect runs connectors in a thread pool)
# ---------------------------------------------------------------------------

def test_throttle_bookkeeping_is_thread_safe():
    """Sources are fetched concurrently, so the per-host clock is shared state.

    Without the lock, two threads could read the same `last` and both decide to
    go immediately, defeating the pacing that keeps GDELT and friends from
    returning 429.
    """
    session = HttpSession("test", min_interval=0.0)
    errors: list[BaseException] = []

    def hammer():
        try:
            for _ in range(200):
                session._throttle("https://api.example.com/x")
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=hammer) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert "api.example.com" in session._last_call


def test_parallel_collect_stores_every_source_and_isolates_failures(tmp_path, monkeypatch):
    """One failing connector must not lose the others' results, and the counts
    must survive being gathered off several threads."""
    from radar.config import get_config
    from radar.db import Database
    from radar.connectors.base import CollectedItem, Connector
    from radar.pipeline.ingest import Ingestor

    cfg = get_config()
    db = Database(tmp_path / "c.db")
    db.init_schema()
    ingestor = Ingestor(cfg, db, llm=None)

    class Good(Connector):
        def collect(self, reference_date, since_days):
            for i in range(5):
                yield CollectedItem(
                    source_id=self.source_id,
                    url=f"https://{self.source_id}.example.com/{i}",
                    title=f"{self.source_id} item {i}",
                    published_at=reference_date - dt.timedelta(days=1),
                    extract=f"extract {self.source_id} {i}",
                    publisher=f"{self.source_id}.example.com",
                )

    class Bad(Connector):
        def collect(self, reference_date, since_days):
            raise RuntimeError("upstream exploded")
            yield  # pragma: no cover

    sources = [
        {"id": "alpha", "connector": "t_good", "enabled": True, "default_tier": 2, "params": {}},
        {"id": "beta", "connector": "t_good", "enabled": True, "default_tier": 2, "params": {}},
        {"id": "gamma", "connector": "t_bad", "enabled": True, "default_tier": 2, "params": {}},
    ]
    REGISTRY["t_good"] = Good
    REGISTRY["t_bad"] = Bad
    try:
        monkeypatch.setattr(cfg, "enabled_sources", lambda: sources)
        stats = ingestor.collect(REF, "R-test", since_days=30)
    finally:
        REGISTRY.pop("t_good", None)
        REGISTRY.pop("t_bad", None)

    assert stats.per_source == {"alpha": 5, "beta": 5}
    assert "gamma" in stats.errors and "upstream exploded" in stats.errors["gamma"]
    assert stats.new_signals == 10
    stored = db.query_one("SELECT COUNT(*) n FROM signals")["n"]
    assert stored == 10, "parallel collection lost or double-counted rows"


def test_parallel_collect_still_deduplicates_across_sources(tmp_path, monkeypatch):
    """Dedup is a read-modify-write over the whole signal table, which is why
    writes stay on one thread. Two sources carrying the same syndicated URL must
    still collapse to one signal (Table 16 stage 2)."""
    from radar.config import get_config
    from radar.db import Database
    from radar.connectors.base import CollectedItem, Connector
    from radar.pipeline.ingest import Ingestor

    cfg = get_config()
    db = Database(tmp_path / "d.db")
    db.init_schema()
    ingestor = Ingestor(cfg, db, llm=None)

    class Syndicated(Connector):
        def collect(self, reference_date, since_days):
            yield CollectedItem(
                source_id=self.source_id,
                url="https://wire.example.com/same-story",
                title="Identical syndicated story",
                published_at=reference_date - dt.timedelta(days=2),
                extract="the same wire copy",
                publisher="wire.example.com",
            )

    sources = [
        {"id": "s1", "connector": "t_syn", "enabled": True, "default_tier": 2, "params": {}},
        {"id": "s2", "connector": "t_syn", "enabled": True, "default_tier": 2, "params": {}},
        {"id": "s3", "connector": "t_syn", "enabled": True, "default_tier": 2, "params": {}},
    ]
    REGISTRY["t_syn"] = Syndicated
    try:
        monkeypatch.setattr(cfg, "enabled_sources", lambda: sources)
        stats = ingestor.collect(REF, "R-test", since_days=30)
    finally:
        REGISTRY.pop("t_syn", None)

    assert stats.new_signals == 1
    assert stats.duplicates == 2
    assert db.query_one("SELECT COUNT(*) n FROM signals")["n"] == 1


def test_dedup_matches_the_stored_publisher_not_the_declared_one(tmp_path):
    """Table 16 stage 2 dedups on URL, or on (publisher, extract).

    The second half was comparing `item.publisher` while the INSERT stores
    `item.publisher or item.source_id`, so an item from a source that names no
    publisher could never match its own stored duplicate: re-collect the same
    URL-less story and it landed a second time.
    """
    from radar.config import get_config
    from radar.db import Database
    from radar.connectors.base import CollectedItem
    from radar.pipeline.ingest import IngestStats, Ingestor

    cfg = get_config()
    db = Database(tmp_path / "p.db")
    db.init_schema()

    def item(url: str) -> CollectedItem:
        # Different URLs, same words: the syndication case the (publisher,
        # extract) branch exists for, from a source that names no publisher.
        return CollectedItem(
            source_id="anonymous_feed", url=url, title="A story with no named publisher",
            published_at=REF - dt.timedelta(days=3), extract="the body copy", publisher="",
        )

    first, second = IngestStats(), IngestStats()
    Ingestor(cfg, db, llm=None)._store(
        [item("https://a.example/story")], {"id": "anonymous_feed"}, "R-1", first)
    # A SECOND Ingestor, so the answer comes from the store rather than from a
    # set the first run happened to be holding.
    Ingestor(cfg, db, llm=None)._store(
        [item("https://b.example/reprint")], {"id": "anonymous_feed"}, "R-2", second)

    assert first.new_signals == 1
    assert second.new_signals == 0 and second.duplicates == 1
    assert db.query_one("SELECT COUNT(*) n FROM signals")["n"] == 1


def test_dedup_does_not_rescan_the_corpus_per_item(tmp_path, monkeypatch):
    """The check used to be one `WHERE url = ? OR (publisher = ? AND extract = ?)`
    per collected item, which SQLite plans as a full table SCAN — so a refresh
    of n items against a corpus of m signals did O(n*m) work and got slower
    every week for the same amount of new evidence.

    Asserted as a statement count rather than a duration: a timing bound is a
    flaky test on shared hardware, and the SHAPE is what regressed. Reading the
    corpus twice would be fine; reading it once per item is not.
    """
    import sqlite3

    from radar.config import get_config
    from radar.db import Database
    from radar.connectors.base import CollectedItem
    from radar.pipeline.ingest import IngestStats, Ingestor

    seen: list[str] = []

    class CountingCursor(sqlite3.Cursor):
        def execute(self, sql, parameters=(), /):
            seen.append(" ".join(sql.split()))
            return super().execute(sql, parameters)

    class CountingConnection(sqlite3.Connection):
        def cursor(self, factory=CountingCursor):
            return super().cursor(factory)

        def execute(self, sql, parameters=(), /):
            seen.append(" ".join(sql.split()))
            return super().execute(sql, parameters)

    real_connect = sqlite3.connect
    monkeypatch.setattr(
        sqlite3, "connect",
        lambda *a, **kw: real_connect(*a, **{**kw, "factory": CountingConnection}))

    cfg = get_config()
    db = Database(tmp_path / "q.db")
    db.init_schema()

    def batch(prefix: str, n: int) -> list[CollectedItem]:
        return [CollectedItem(source_id="s", url=f"https://example.invalid/{prefix}-{i}",
                              title=f"{prefix}{i}", published_at=REF - dt.timedelta(days=1),
                              extract=f"{prefix} body {i}", publisher="p")
                for i in range(n)]

    Ingestor(cfg, db, llm=None)._store(batch("seed", 200), {"id": "s"}, "R-seed", IngestStats())

    def reads_for(n: int) -> int:
        seen.clear()
        Ingestor(cfg, db, llm=None)._store(
            batch(f"new{n}", n), {"id": "s"}, f"R-{n}", IngestStats())
        return sum(1 for sql in seen if sql.startswith("SELECT") and "FROM signals" in sql)

    small, large = reads_for(10), reads_for(120)
    assert small == large, (
        f"dedup reads scale with the batch: {small} SELECT(s) for 10 items, {large} for 120")
    assert large <= 2, f"the corpus should be read about once per run, not {large} times"
