"""Regulatory connectors (§4.3.2).

"Three of the six briefing examples are regulation-driven, and for good reason:
a regulation with a compliance deadline creates a budgeted, dated, non-optional
buying window. This is the highest-value signal category for the radar and it is
entirely free and machine-readable."

Regulatory items carry `signal_type_hint = "regulation"` and are the primary
input to horizon derivation (§4.8): a dated compliance deadline within twelve
months is what makes a topic Now rather than Next.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Iterator

from .base import CollectedItem, Connector, clean_text, parse_date, register

log = logging.getLogger(__name__)


@register("eurlex")
class EurLexConnector(Connector):
    """EUR-Lex via the CELLAR SPARQL endpoint (Table 18).

    CELLAR models a legal act as a `work` with one `expression` per language.
    We query English expressions with their document date, then filter titles
    against the configured subject fragments — EuroVoc concept filtering is
    materially more precise and is a Sprint 0 refinement, but free-text title
    filtering is enough to prove the connector and the horizon logic.
    """

    default_tier = 1
    ENDPOINT = "https://publications.europa.eu/webapi/rdf/sparql"

    QUERY_TEMPLATE = """
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
SELECT DISTINCT ?work ?date ?title WHERE {{
  ?work cdm:work_date_document ?date .
  ?expr cdm:expression_belongs_to_work ?work ;
        cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/ENG> ;
        cdm:expression_title ?title .
  FILTER(?date >= "{start}"^^<http://www.w3.org/2001/XMLSchema#date>)
  FILTER(?date <= "{end}"^^<http://www.w3.org/2001/XMLSchema#date>)
  FILTER({title_filter})
}}
LIMIT {limit}
"""

    def collect(self, reference_date: dt.date, since_days: int) -> Iterator[CollectedItem]:
        endpoint = self.params.get("endpoint", self.ENDPOINT)
        window = int(self.params.get("since_days", since_days))
        start = reference_date - dt.timedelta(days=window)
        filters = self.params.get("title_filters") or ["cyber"]
        limit = int(self.params.get("limit", 100))

        # One clause per subject fragment, OR-ed. CONTAINS on lcase is slow but
        # CELLAR handles it at this limit, and it keeps the connector free of a
        # EuroVoc concept table we have not curated yet.
        title_filter = " || ".join(f'CONTAINS(LCASE(STR(?title)), "{frag.lower()}")' for frag in filters)
        query = self.QUERY_TEMPLATE.format(
            start=start.isoformat(), end=reference_date.isoformat(),
            title_filter=title_filter, limit=limit,
        )

        resp = self.get(
            endpoint,
            params={"query": query, "format": "application/sparql-results+json"},
            headers={"Accept": "application/sparql-results+json"},
        )
        if resp is None:
            return
        try:
            bindings = resp.json()["results"]["bindings"]
        except (ValueError, KeyError) as exc:
            log.warning("EUR-Lex SPARQL returned unexpected payload: %s", exc)
            return

        for row in bindings:
            work_uri = row.get("work", {}).get("value", "")
            title = clean_text(row.get("title", {}).get("value", ""))
            published = parse_date(row.get("date", {}).get("value"))
            if not title or not work_uri:
                continue
            if not self.in_window(published, reference_date, window):
                continue
            yield CollectedItem(
                source_id=self.source_id,
                url=_cellar_to_public_url(work_uri),
                title=title,
                published_at=published,
                extract=self.clip(title),
                publisher="eur-lex.europa.eu",
                language="en",
                geographies=["EU"],
                signal_type_hint="regulation",
                attributes={"cellar_uri": work_uri, "instrument_stage": _infer_stage(title)},
                payload=dict(row),
            )


def _cellar_to_public_url(work_uri: str) -> str:
    """Turn a CELLAR resource URI into a citable EUR-Lex URL.

    NFR-02 requires the displayed claim to trace back to a reachable source, so
    the stored URL must be one a reviewer can open — not an RDF identifier.
    """
    if "/cellar/" in work_uri:
        cellar_id = work_uri.rsplit("/cellar/", 1)[1]
        return f"https://publications.europa.eu/resource/cellar/{cellar_id}"
    return work_uri


def _infer_stage(title: str) -> str:
    """Instrument stage is a feature group in its own right (Table 29).

    Consultation < proposal < adopted < applicable maps directly onto
    Later < Next < Now in the horizon logic (§4.8).
    """
    lowered = title.lower()
    if lowered.startswith("proposal") or "proposal for a" in lowered:
        return "proposal"
    if "draft" in lowered[:60]:
        return "draft"
    if "corrigendum" in lowered:
        return "corrigendum"
    if any(word in lowered for word in ("regulation", "directive", "decision", "implementing")):
        return "adopted"
    return "unknown"
