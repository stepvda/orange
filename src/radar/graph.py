"""The Orange Business Graph and opportunity-space linking (§4.5).

"The briefing asks two questions of every topic — can we play, and can we win —
but leaves the mechanism open. This join is the product. Without it the radar is
a competent trend feed, and trend feeds already exist."

Two things live here:

  build_graph()  — materialises the curated graph from config/business_graph/*
                   into nodes and typed, dated, sourced edges (LK-01, DR-11).

  Linker         — generates, filters, types and scores links from an
                   opportunity space to business assets (LK-04..LK-06), and
                   derives portfolio distance (LK-05, FR-30).

§4.5.4 governs the method: "Link assertion is a retrieval and rules problem, not
a generation problem. The model may propose; rules and humans dispose." No LLM
is used in this module at all — Table 23 assigns the right-to-win join to
"structured lookup", because matching against the asset catalogue is a join, not
an inference.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Any

from .config import Config
from .db import Database, js, unjs

log = logging.getLogger(__name__)

# Link types (Table 26). Portfolio distance is the ordinal position: the
# shortest path in the graph from the opportunity space to a configuration that
# could actually deliver it (§4.5.3).
LINK_TYPES = ["L0", "L1", "L2", "L3", "L4"]
LINK_DISTANCE = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4}

# SUP is an extension beyond Table 26, and a deliberate one.
#
# Every L0-L4 definition in Table 26 describes a DELIVERY capability: an offer
# that addresses the opportunity, offers that combine, a partner that supplies
# the missing piece, a capability to build. Portfolio distance is defined
# (§4.5.3) as "the shortest path to a configuration that could actually deliver
# it", so only delivery-bearing links may shorten it.
#
# A certification, an analyst position, a published reference and a capability
# pool are none of those. They are right-to-win EVIDENCE — they feed compliance
# fit, external validation, reference density and capability depth. Typing them
# L0 would mean any topic in a regulated vertical scored as a direct sell purely
# because Orange holds ISO 27001, which would make portfolio distance — "the
# most decision-relevant number in the product" — meaningless.
#
# So supporting evidence is linked, displayed and scored, but excluded from the
# distance computation and from the role-mode link filter.
SUPPORTING = "SUP"
LINK_MEANING = {
    "L0": ("Direct", "An existing commercial offer addresses this opportunity as it stands", "Sales", "Sell it"),
    "L1": ("Bundle", "Two or more existing offers combined address it", "Presales", "Package it"),
    "L2": ("Partner-dependent", "Requires a capability held by an existing partner at a usable tier",
           "Presales / alliances", "Assemble it"),
    "L3": ("Adjacent", "Requires building or acquiring one capability; nearby assets already exist",
           "Strategy", "Study it"),
    "L4": ("White space", "No plausible path from the current portfolio", "Strategy", "Watch it, or reject it"),
    SUPPORTING: ("Supporting evidence",
                 "Proof, certification, analyst recognition or capability that strengthens the case "
                 "without itself delivering the opportunity",
                 "All roles", "Cite it"),
}


def build_graph(cfg: Config, db: Database) -> dict[str, int]:
    """Materialise the curated graph (LK-01, DR-11).

    Edges carry the semantics that matter (§4.5.1): an offer ADDRESSES a use
    case; a reference DEMONSTRATES an offer IN a vertical; a partner PROVIDES a
    technology AT a tier; a certification is REQUIRED_BY a vertical; a
    capability pool STAFFS a domain.
    """
    counts = {"nodes": 0, "edges": 0}
    offers_src = cfg.offers.get("source", "config/business_graph/offers.yaml")
    offers_asof = cfg.offers.get("as_of", "unknown")
    refs_src = cfg.references.get("source", "config/business_graph/references.yaml")
    refs_asof = cfg.references.get("as_of", "unknown")
    assets_src = cfg.assets.get("source", "config/business_graph/assets.yaml")
    assets_asof = cfg.assets.get("as_of", "unknown")

    written: set[str] = set()

    with db.cursor() as cur:
        # Edges are pure derived data with nothing referencing them, so they are
        # rebuilt wholesale. Nodes are NOT: opportunity_links carries a foreign
        # key onto them, so nodes are upserted and the disappeared ones are
        # retired below rather than deleted out from under live links.
        cur.execute("DELETE FROM graph_edges")

        def add_node(node_id: str, node_type: str, label: str, attributes: dict, source: str, as_of: str) -> None:
            cur.execute(
                "INSERT OR REPLACE INTO graph_nodes (id, node_type, label, attributes, source, as_of) "
                "VALUES (?,?,?,?,?,?)",
                (node_id, node_type, label, js(attributes), source, as_of),
            )
            written.add(node_id)
            counts["nodes"] += 1

        def add_edge(src: str, dst: str, edge_type: str, strength: float,
                     source: str, as_of: str, attributes: dict | None = None) -> None:
            cur.execute(
                "INSERT INTO graph_edges (src, dst, edge_type, strength, as_of, source, attributes) "
                "VALUES (?,?,?,?,?,?,?)",
                (src, dst, edge_type, strength, as_of, source, js(attributes or {})),
            )
            counts["edges"] += 1

        # -- offers --------------------------------------------------------
        for offer in cfg.offers.get("offers", []):
            node_id = f"offer:{offer['id']}"
            add_node(node_id, "offer", offer["label"], {
                "definition": offer.get("definition", ""),
                "domains": offer.get("domains", []),
                "technologies": offer.get("technologies", []),
                "use_cases": offer.get("addresses_use_cases", []),
                "verticals": offer.get("verticals", []),
                "sovereign": offer.get("sovereign", False),
                "status": offer.get("status", "live"),
            }, offers_src, offers_asof)
            for use_case in offer.get("addresses_use_cases") or []:
                add_edge(node_id, f"use_case:{use_case}", "ADDRESSES", 1.0, offers_src, offers_asof)
            for tech in offer.get("technologies") or []:
                add_edge(node_id, f"technology:{tech}", "COVERS", 1.0, offers_src, offers_asof)

        # -- references ----------------------------------------------------
        for ref in cfg.references.get("named", []):
            node_id = f"reference:{ref['id']}"
            add_node(node_id, "reference", ref["label"], {
                "description": ref.get("description", ""),
                "verticals": ref.get("verticals", []),
                "domains": ref.get("domains", []),
                "use_cases": ref.get("use_cases", []),
                "curation_status": ref.get("curation_status", "confirmed"),
            }, refs_src, refs_asof)
            for offer_id in ref.get("demonstrates") or []:
                add_edge(node_id, f"offer:{offer_id}", "DEMONSTRATES", 1.0, refs_src, refs_asof,
                         {"verticals": ref.get("verticals", [])})

        # -- partners ------------------------------------------------------
        tier_ranks = cfg.assets.get("partner_tier_ranks", {})
        for partner in cfg.assets.get("partners", []):
            node_id = f"partner:{partner['id']}"
            tier = partner.get("tier", "unspecified")
            rank = float(tier_ranks.get(tier, 0.5))
            add_node(node_id, "partner", partner["label"], {
                "tier": tier, "tier_rank": rank, "tier_note": partner.get("tier_note", ""),
                "technologies": partner.get("provides_technologies", []),
                "domains": partner.get("domains", []),
            }, assets_src, assets_asof)
            for tech in partner.get("provides_technologies") or []:
                # Tier is an EDGE property (§4.5.1) and decays — LK-07.
                add_edge(node_id, f"technology:{tech}", "PROVIDES", rank, assets_src, assets_asof,
                         {"tier": tier})

        # -- certifications ------------------------------------------------
        for cert in cfg.assets.get("certifications", []):
            node_id = f"certification:{cert['id']}"
            add_node(node_id, "certification", cert["label"], {
                "geographies": cert.get("geographies", []),
                "sovereign": cert.get("sovereign", False),
                "verticals": cert.get("required_by_verticals", []),
            }, assets_src, assets_asof)
            for vertical in cert.get("required_by_verticals") or []:
                add_edge(node_id, f"vertical:{vertical}", "REQUIRED_BY", 1.0, assets_src, assets_asof,
                         {"geographies": cert.get("geographies", [])})

        # -- analyst positions ---------------------------------------------
        for pos in cfg.assets.get("analyst_positions", []):
            node_id = f"analyst_position:{pos['id']}"
            add_node(node_id, "analyst_position", pos["label"], {
                "analyst": pos.get("analyst"), "position": pos.get("position"),
                "year": pos.get("year"), "technologies": pos.get("technologies", []),
                "domains": pos.get("domains", []), "use_cases": pos.get("use_cases", []),
            }, assets_src, assets_asof)
            for tech in pos.get("technologies") or []:
                add_edge(node_id, f"technology:{tech}", "COVERS", 1.0, assets_src, assets_asof)

        # -- capability pools ----------------------------------------------
        for pool in cfg.assets.get("capability_pools", []):
            node_id = f"capability_pool:{pool['id']}"
            add_node(node_id, "capability_pool", pool["label"], {
                "headcount": pool.get("headcount"), "domains": pool.get("staffs_domains", []),
                "technologies": pool.get("technologies", []), "verticals": pool.get("verticals", []),
                "note": pool.get("note", ""),
            }, assets_src, assets_asof)
            for domain in pool.get("staffs_domains") or []:
                add_edge(node_id, f"domain:{domain}", "STAFFS", 1.0, assets_src, assets_asof,
                         {"headcount": pool.get("headcount")})

        # -- taxonomy nodes -------------------------------------------------
        for vocab, prefix, node_type in (
            (cfg.verticals, "vertical", "taxonomy_vertical"),
            (cfg.use_cases, "use_case", "taxonomy_use_case"),
            (cfg.technologies, "technology", "taxonomy_technology"),
            (cfg.domains, "domain", "taxonomy_domain"),
        ):
            for item in vocab:
                add_node(f"{prefix}:{item.id}", node_type, item.label,
                         {"definition": item.definition}, f"config/taxonomy/{vocab.name}.yaml", vocab.version)

        # LK-07: re-validate on the internal-catalogue refresh cycle and flag
        # topics whose supporting offer has been withdrawn or whose partner tier
        # has changed. §4.5.4: "offers are withdrawn and partner tiers change" —
        # and a right-to-win claim that has become false is worse than an absent
        # one (Table 36), so a retired asset rejects its links with a reason
        # rather than vanishing silently.
        retired = 0
        withdrawn_links = 0
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        # Already-retired nodes are skipped, not retired again. `node_type ||
        # '_retired'` is not idempotent: an asset that stays out of the config
        # collects a suffix on every rebuild — 'offer_retired_retired_retired' —
        # which no reader matches on, and it was re-counted as a fresh
        # withdrawal each time, so the stats reported the same removal for ever.
        for row in cur.execute("SELECT id, node_type FROM graph_nodes").fetchall():
            if row["id"] in written or row["node_type"].endswith("_retired"):
                continue
            cur.execute(
                "UPDATE opportunity_links SET rejected = 1, rejection_reason = ?, revalidated_at = ? "
                "WHERE node_id = ? AND rejected = 0",
                ("asset withdrawn from the internal catalogue (LK-07)", now, row["id"]),
            )
            withdrawn_links += cur.rowcount
            # Keep the node so the rejected link still resolves to a label for
            # audit (NFR-03); mark it retired so it cannot be linked again.
            cur.execute(
                "UPDATE graph_nodes SET node_type = node_type || '_retired', as_of = ? WHERE id = ?",
                (now[:10], row["id"]),
            )
            retired += 1
        counts["retired_nodes"] = retired
        counts["withdrawn_links"] = withdrawn_links

    log.info("Business graph built: %d nodes, %d edges, %d retired, %d links withdrawn",
             counts["nodes"], counts["edges"], counts["retired_nodes"], counts["withdrawn_links"])
    return counts


@dataclass
class Link:
    node_id: str
    link_type: str
    confidence: float
    evidence: dict[str, Any]


class Linker:
    """Generate, filter, type and score opportunity-space -> asset links (§4.5.4)."""

    def __init__(self, cfg: Config, db: Database):
        self.cfg = cfg
        self.db = db
        self._offers = {o["id"]: o for o in cfg.offers.get("offers", [])}
        self._partners = {p["id"]: p for p in cfg.assets.get("partners", [])}
        self._refs = {r["id"]: r for r in cfg.references.get("named", [])}
        self._certs = {c["id"]: c for c in cfg.assets.get("certifications", [])}
        self._positions = {p["id"]: p for p in cfg.assets.get("analyst_positions", [])}
        self._pools = {p["id"]: p for p in cfg.assets.get("capability_pools", [])}

    # -- link generation ---------------------------------------------------

    def link_topic(self, topic: dict[str, Any]) -> list[Link]:
        """Rules-based candidate generation and typing (LK-04).

        Steps 1-3 of §4.5.4. Candidate generation by taxonomy compatibility,
        rule filtering, then typing by graph path shape. Step 4 (human
        confirmation) is a separate curator action; step 5 (decay) runs on the
        internal-catalogue refresh cycle.
        """
        vertical, use_case, technology = topic["vertical"], topic["use_case"], topic["technology"]
        domains = set(unjs(topic.get("domains"), []) or [])
        links: list[Link] = []

        # --- offers -------------------------------------------------------
        direct_offers, bundle_offers = [], []
        for offer_id, offer in self._offers.items():
            addresses = set(offer.get("addresses_use_cases") or [])
            provides = set(offer.get("technologies") or [])
            offer_verticals = set(offer.get("verticals") or [])
            # Rule filtering (§4.5.4 step 2): an offer restricted to other
            # verticals is eliminated regardless of textual similarity.
            if offer_verticals and vertical not in offer_verticals:
                continue
            if use_case in addresses and technology in provides:
                direct_offers.append(offer_id)
                links.append(Link(f"offer:{offer_id}", "L0", 0.9, {
                    "rule": "offer addresses the use case AND provides the technology",
                    "use_case": use_case, "technology": technology,
                }))
            elif use_case in addresses:
                bundle_offers.append(offer_id)
                links.append(Link(f"offer:{offer_id}", "L1", 0.7, {
                    "rule": "offer addresses the use case but not this technology",
                    "use_case": use_case, "missing_technology": technology,
                }))
            elif technology in provides and domains & set(offer.get("domains") or []):
                bundle_offers.append(offer_id)
                links.append(Link(f"offer:{offer_id}", "L1", 0.5, {
                    "rule": "offer provides the technology in a matching domain",
                    "technology": technology,
                }))

        # --- partners -----------------------------------------------------
        for partner_id, partner in self._partners.items():
            if technology not in set(partner.get("provides_technologies") or []):
                continue
            rank = float(self.cfg.assets["partner_tier_ranks"].get(partner.get("tier", "unspecified"), 0.5))
            links.append(Link(f"partner:{partner_id}", "L2", round(0.4 + 0.5 * rank, 3), {
                "rule": "partner provides the required technology",
                "tier": partner.get("tier"), "tier_rank": rank, "technology": technology,
            }))

        # --- references ---------------------------------------------------
        for ref_id, ref in self._refs.items():
            ref_verticals = set(ref.get("verticals") or [])
            ref_use_cases = set(ref.get("use_cases") or [])
            if vertical in ref_verticals and use_case in ref_use_cases:
                confidence = 0.6 if ref.get("curation_status") == "unconfirmed" else 0.9
                links.append(Link(f"reference:{ref_id}", SUPPORTING, confidence, {
                    "rule": "published reference in this vertical for this use case",
                    "curation_status": ref.get("curation_status", "confirmed"),
                    "exact_use_case": True,
                }))
            elif vertical in ref_verticals:
                links.append(Link(f"reference:{ref_id}", SUPPORTING, 0.4, {
                    "rule": "published reference in this vertical, different use case",
                    "exact_use_case": False,
                }))

        # --- certifications ------------------------------------------------
        for cert_id, cert in self._certs.items():
            if vertical in set(cert.get("required_by_verticals") or []):
                links.append(Link(f"certification:{cert_id}", SUPPORTING, 0.8, {
                    "rule": "certification Orange holds is required by this vertical",
                    "geographies": cert.get("geographies", []),
                    "sovereign": cert.get("sovereign", False),
                }))

        # --- analyst positions ----------------------------------------------
        for pos_id, pos in self._positions.items():
            if technology in set(pos.get("technologies") or []) or use_case in set(pos.get("use_cases") or []):
                links.append(Link(f"analyst_position:{pos_id}", SUPPORTING, 0.75, {
                    "rule": "analyst recognition covers this technology or use case",
                    "analyst": pos.get("analyst"), "position": pos.get("position"),
                }))

        # --- capability pools -----------------------------------------------
        for pool_id, pool in self._pools.items():
            pool_domains = set(pool.get("staffs_domains") or [])
            pool_verticals = set(pool.get("verticals") or [])
            pool_techs = set(pool.get("technologies") or [])
            if (domains & pool_domains) or (vertical in pool_verticals) or (technology in pool_techs):
                links.append(Link(f"capability_pool:{pool_id}", SUPPORTING, 0.6, {
                    "rule": "capability pool staffs this domain, vertical or technology",
                    "headcount": pool.get("headcount"),
                }))

        # --- L3 / L4 -------------------------------------------------------
        # §4.5.3: L3 is "requires building or acquiring one capability; nearby
        # assets, references or research already exist". L4 is "no plausible
        # path from the current portfolio" — the strategist's innovation agenda,
        # and precisely the thing a salesperson should never be shown.
        if not direct_offers and not bundle_offers:
            nearby = [l for l in links
                      if l.node_id.startswith(("partner:", "reference:", "capability_pool:"))]
            technology_owned = bool(self.cfg.technologies[technology].get("orange_asset"))
            if nearby or technology_owned:
                links.append(Link(f"technology:{technology}", "L3", 0.5, {
                    "rule": "no offer path, but adjacent assets or Orange research exist",
                    "nearby_assets": [l.node_id for l in nearby][:5],
                    "orange_technology_asset": technology_owned,
                }))
            else:
                links.append(Link(f"technology:{technology}", "L4", 0.5, {
                    "rule": "no offer, partner, reference or capability path from the current portfolio",
                }))
        return links

    def portfolio_distance(self, links: list[Link]) -> int:
        """LK-05 / FR-30 — the shortest path to a deliverable configuration.

        §4.5.3: "This is the most decision-relevant number in the product. It
        says which conversation a topic belongs in."
        """
        delivery = [l for l in links if l.link_type in LINK_DISTANCE]
        if not delivery:
            return LINK_DISTANCE["L4"]
        return min(LINK_DISTANCE[l.link_type] for l in delivery)

    # -- persistence -------------------------------------------------------

    def run(self, topic_ids: list[str] | None = None) -> dict[str, Any]:
        where = ""
        params: tuple = ()
        if topic_ids:
            placeholders = ",".join("?" * len(topic_ids))
            where = f" AND id IN ({placeholders})"
            params = tuple(topic_ids)
        topics = self.db.query(
            f"SELECT * FROM opportunity_spaces WHERE merged_into IS NULL{where}", params
        )
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        decisions = {
            r["pattern"]: r for r in self.db.query("SELECT * FROM link_pattern_decisions")
        }
        stats = {"topics": 0, "links": 0, "auto_confirmed": 0, "auto_rejected": 0, "needs_review": 0}

        with self.db.cursor() as cur:
            for topic in topics:
                topic_dict = dict(topic)
                links = self.link_topic(topic_dict)
                stats["topics"] += 1
                cur.execute("DELETE FROM opportunity_links WHERE opportunity_id = ?", (topic["id"],))
                for link in links:
                    # LK-06: the FIRST occurrence of each link pattern needs
                    # curator confirmation; later occurrences inherit it.
                    pattern = f"{link.node_id}|{topic['use_case']}|{topic['technology']}"
                    decision = decisions.get(pattern)
                    confirmed_by = confirmed_at = None
                    rejected = 0
                    reason = None
                    if decision:
                        if decision["decision"] == "confirmed":
                            confirmed_by, confirmed_at = decision["curator"], decision["decided_at"]
                            stats["auto_confirmed"] += 1
                        else:
                            rejected, reason = 1, decision["reason"]
                            stats["auto_rejected"] += 1
                    else:
                        stats["needs_review"] += 1
                    cur.execute(
                        """INSERT OR REPLACE INTO opportunity_links
                           (opportunity_id, node_id, link_type, confidence, evidence,
                            confirmed_by, confirmed_at, rejected, rejection_reason, created_at, revalidated_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        (topic["id"], link.node_id, link.link_type, link.confidence,
                         js({**link.evidence, "pattern": pattern}), confirmed_by, confirmed_at,
                         rejected, reason, now, now),
                    )
                    stats["links"] += 1
        return stats

    # -- reverse query (FR-33) ---------------------------------------------

    def offers_without_topics(self) -> list[dict[str, Any]]:
        """§4.5.5: "Which offers have no live opportunity space attached?"

        "That is a portfolio-decay signal, it comes free with the graph, and it
        is the kind of finding that gets a tool invited back to the Strategy and
        Technology Committee."
        """
        rows = self.db.query(
            """SELECT n.id, n.label FROM graph_nodes n
               WHERE n.node_type = 'offer'
                 AND NOT EXISTS (
                   SELECT 1 FROM opportunity_links l
                   JOIN opportunity_spaces o ON o.id = l.opportunity_id
                   WHERE l.node_id = n.id AND l.rejected = 0
                     AND o.state IN ('active','watchlist') AND o.merged_into IS NULL
                 )"""
        )
        return [{"id": r["id"], "label": r["label"]} for r in rows]
