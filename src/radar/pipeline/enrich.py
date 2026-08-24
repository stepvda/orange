"""Evidence enrichment — attach newly ingested signals to existing topics.

Synthesis only attaches a signal to a topic when the model happens to cite it
while re-emitting that topic's triple. That is fine for topics the current
refresh re-generates, but it leaves an obvious gap: a topic created six weeks
ago stays frozen at the evidence it was born with, even when the latest refresh
ingests signals that plainly belong to it.

That gap matters more than it looks, because thin evidence is not merely
cosmetic — it suppresses the topic through the whole scoring chain:

  * market signal strength counts signals in the trailing window (Table 27);
  * source diversity is entropy over the attached publishers (SC-03);
  * momentum is the slope of attached signal volume (§4.6);
  * promotion to Active needs 4 signals from 3 distinct publishers (§4.8).

So a topic with real support in the corpus but no attachment path looks
identical to one nobody is talking about. §4.4.5 says the intended behaviour is
that "on refresh, new signals attach to the existing topic" — this stage is what
makes that true for every topic, not just the re-generated ones.

METHOD, and why it is not generation. Attachment is retrieval plus rules, in the
same spirit as §4.5.4's "the model may propose; rules and humans dispose":

  1. embed the topic statement and every candidate signal (already embedded by
     the themes stage, so this is a lookup);
  2. require semantic similarity above a threshold;
  3. require taxonomy corroboration — the signal must independently support the
     topic's vertical, use case or technology through its own text, its CPV
     crosswalk result, or its cluster;
  4. record WHY each attachment was made, so an enriched topic is auditable to
     the same standard as a synthesised one (NFR-02).

No claim is created here. Enrichment adds evidence to a topic's signal set; it
never adds a sentence to `why_hot`, because an uncited claim is exactly what
§4.4.4 forbids and only synthesis may write claims.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

import numpy as np

from ..config import Config
from ..db import Database, unjs
from ..embeddings import Embedder

log = logging.getLogger(__name__)


class Enricher:
    def __init__(self, cfg: Config, db: Database, embedder: Embedder | None = None):
        self.cfg = cfg
        self.db = db
        self.embedder = embedder or Embedder()
        enrich = cfg.settings.get("enrichment", {})
        self.similarity_threshold = float(enrich.get("similarity_threshold", 0.45))
        self.max_new_per_topic = int(enrich.get("max_new_signals_per_topic", 12))
        self.require_corroboration = bool(enrich.get("require_taxonomy_corroboration", True))

    # -- corroboration ----------------------------------------------------

    def _vocab_terms(self, vocab, key: str) -> list[str]:
        """Every surface form of one vocabulary id, in every language we read.

        The English labels and synonyms alone would make corroboration the
        second English-only gate in the pipeline. That matters more here than it
        looks: a French or Dutch signal that now survives stage 3 would arrive,
        clear the similarity threshold, and then be refused for not containing
        an English word — so the corpus unlocked by the lexicon would pass the
        gate and still never attach to a topic. Multilingual terms come from the
        same file for the same reason (config/taxonomy/lexicon.yaml).
        """
        item = vocab.get(key)
        if item is None:
            return []
        terms = [item.label.lower(), *(s.lower() for s in item.synonyms)]
        for language, values in (self.cfg.lexicon.get("terms", {}).get(key) or {}).items():
            terms.extend(str(v).lower() for v in values or ())
        return [t for t in terms if len(t) >= 4]

    def corroborates(self, topic: dict, signal: dict, signal_cpv: dict[str, float]) -> str | None:
        """Return the reason this signal independently supports the topic.

        Similarity alone is not enough: embeddings happily rate two unrelated
        cybersecurity items as close. Requiring a second, INDEPENDENT reason is
        what stops enrichment from quietly inflating every topic's signal count
        — which would corrupt exactly the components that depend on it.

        Public because the scoping conversation (`radar.scoping`) asks the same
        question of a brief before it lets anyone run one, and asking it a second
        way would mean two definitions of "independently supports" that could
        drift apart. `topic` is any mapping carrying `vertical`, `use_case` and
        `technology`; a caller that wants only some of those axes considered
        blanks the others, and an unknown id contributes no terms.
        """
        haystack = f"{signal.get('title','')} {signal.get('extract','')}".lower()

        for vocab, key, label in (
            (self.cfg.use_cases, topic["use_case"], "use case"),
            (self.cfg.technologies, topic["technology"], "technology"),
            (self.cfg.verticals, topic["vertical"], "vertical"),
        ):
            for term in self._vocab_terms(vocab, key):
                if term in haystack:
                    return f"{label} term '{term}' appears in the signal text"

        # A procurement notice corroborates through its CPV crosswalk rather
        # than its prose, which is usually boilerplate.
        if signal_cpv.get(topic["use_case"]):
            return f"CPV crosswalk maps this notice to use case {topic['use_case']}"
        if signal_cpv.get(topic["vertical"]):
            return f"CPV crosswalk maps this notice to vertical {topic['vertical']}"
        return None

    # -- main ---------------------------------------------------------------

    def run(self, refresh_id: str, reference_date: dt.date | None = None,
            topic_ids: list[str] | None = None) -> dict[str, Any]:
        """Attach corroborated signals to every live topic, or just `topic_ids`.

        A newly synthesised space carries only the signals of the cluster that
        produced it — at most fourteen, and all from one theme. Enrichment is
        what widens that to the rest of the corpus, which is why a generation run
        calls this before scoring, scoped to the spaces it just created.
        """
        reference_date = reference_date or dt.date.today()
        scope = ""
        params: tuple = ()
        if topic_ids:
            scope = f" AND id IN ({','.join('?' * len(topic_ids))})"
            params = tuple(topic_ids)
        topics = self.db.query(
            "SELECT id, vertical, use_case, technology, statement FROM opportunity_spaces "
            f"WHERE merged_into IS NULL AND state != 'rejected'{scope}", params
        )
        if not topics:
            return {"topics": 0, "attached": 0}

        signals = self.db.query(
            "SELECT id, title, extract, publisher, published_at, embedding, attributes, signal_type "
            "FROM signals WHERE relevance > 0 AND embedding IS NOT NULL AND published_at <= ?",
            (reference_date.isoformat(),),
        )
        if not signals:
            log.warning("No embedded signals available — run the `themes` stage first.")
            return {"topics": len(topics), "attached": 0}

        matrix = np.vstack([Embedder.from_blob(s["embedding"]) for s in signals]).astype(np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        matrix = matrix / norms

        # Pre-resolve each signal's CPV crosswalk once rather than per topic.
        signal_cpv: list[dict[str, float]] = []
        for signal in signals:
            attrs = unjs(signal["attributes"], {}) or {}
            codes = [str(c) for c in (attrs.get("cpv") or [])]
            resolved: dict[str, float] = {}
            if codes:
                resolved.update(self.cfg.cpv_to_use_case.resolve(codes))
                resolved.update(self.cfg.cpv_to_vertical.resolve(codes))
            signal_cpv.append(resolved)

        statements = [t["statement"] for t in topics]
        topic_vectors = self.embedder.encode(statements)

        existing: dict[str, set[str]] = {}
        for row in self.db.query("SELECT opportunity_id, signal_id FROM opportunity_signals"):
            existing.setdefault(row["opportunity_id"], set()).add(row["signal_id"])

        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        attached = 0
        enriched_topics = 0
        rejected_similarity_only = 0

        with self.db.cursor() as cur:
            for topic, vector in zip(topics, topic_vectors):
                already = existing.get(topic["id"], set())
                sims = matrix @ np.asarray(vector, dtype=np.float32)
                order = np.argsort(-sims)

                added = 0
                for idx in order:
                    score = float(sims[idx])
                    if score < self.similarity_threshold or added >= self.max_new_per_topic:
                        break
                    signal = signals[int(idx)]
                    if signal["id"] in already:
                        continue
                    reason = self.corroborates(dict(topic), dict(signal), signal_cpv[int(idx)])
                    if reason is None and self.require_corroboration:
                        rejected_similarity_only += 1
                        continue
                    cur.execute(
                        "INSERT OR IGNORE INTO opportunity_signals "
                        "(opportunity_id, signal_id, attached_at, refresh_id) VALUES (?,?,?,?)",
                        (topic["id"], signal["id"], now, f"{refresh_id}:enrich"),
                    )
                    if cur.rowcount:
                        attached += 1
                        added += 1
                if added:
                    enriched_topics += 1
                    log.info("%s +%d signals", topic["id"], added)

        return {
            "topics": len(topics),
            "topics_enriched": enriched_topics,
            "attached": attached,
            "rejected_similarity_without_corroboration": rejected_similarity_only,
            "similarity_threshold": self.similarity_threshold,
        }
