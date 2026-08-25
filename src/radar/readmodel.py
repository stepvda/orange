"""Pipeline stage 7: Serve (Table 16).

Scored topics -> radar, briefs, API. Read model, role-specific ranking,
filtering, export, feedback capture.

The central design point is §4.5.3: the three role modes are not arbitrary
interface presets. They fall out of portfolio distance — sales sees L0 and L1,
presales L0 to L2, strategy L2 to L4 with the highest attractiveness. "A
high-attractiveness topic at L4 is precisely the innovation agenda the
strategist is looking for, and precisely the thing a salesperson should never be
shown."

SC-12 is enforced structurally: attractiveness and right_to_win travel as
separate fields and are never combined into a displayed number. `rank_score`
exists only to order a list and is deliberately not surfaced as a score.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
from typing import Any

from .competition import competition_for_topic, competition_from_row
from .config import Config
from .db import Database, unjs
from .graph import LINK_DISTANCE, LINK_MEANING
from .sizing import sizes_for_topic
from .workflow import WorkflowService

log = logging.getLogger(__name__)


class ReadModel:
    def __init__(self, cfg: Config, db: Database):
        self.cfg = cfg
        self.db = db
        self.workflow = WorkflowService(cfg, db) if db is not None else None

    # -- assembly ----------------------------------------------------------

    def topic(self, topic_id: str) -> dict[str, Any] | None:
        row = self.db.query_one("SELECT * FROM opportunity_spaces WHERE id = ?", (topic_id,))
        return self._assemble(dict(row), full=True) if row else None

    def topics(self, states: tuple[str, ...] = ("active", "watchlist", "fading")) -> list[dict[str, Any]]:
        placeholders = ",".join("?" * len(states))
        rows = self.db.query(
            f"SELECT * FROM opportunity_spaces WHERE merged_into IS NULL AND state IN ({placeholders})",
            states,
        )
        context = self._bulk([r["id"] for r in rows])
        return [self._assemble(dict(r), context=context) for r in rows]

    def topics_by_id(self, topic_ids: list[str]) -> list[dict[str, Any]]:
        """Assemble a named set of topics, in the given order.

        Distinct from `topics()`, which selects by lifecycle state: a freshly
        synthesised space is `candidate` until scoring promotes it, so anything
        wanting to show what a generation run just produced has to ask by id.
        Goes through `_bulk` for the same reason `topics()` does — eleven queries
        for the whole set rather than eleven per topic.
        """
        if not topic_ids:
            return []
        placeholders = ",".join("?" * len(topic_ids))
        rows = {
            r["id"]: r for r in self.db.query(
                f"SELECT * FROM opportunity_spaces WHERE id IN ({placeholders})", tuple(topic_ids)
            )
        }
        context = self._bulk(list(rows))
        return [self._assemble(dict(rows[i]), context=context) for i in topic_ids if i in rows]

    def _bulk(self, topic_ids: list[str]) -> dict[str, Any]:
        """Everything `_assemble` needs for a list of topics, in eleven queries.

        Assembling one topic asks eleven questions — two scores, its links, its
        node labels, its competition, its size, its workflow state, its
        assessments (twice, before `divergence_for` learned to take a
        conviction), its signal count and whether it has a description and a
        brief. Per topic that is nothing. Across a 167-topic view it was 1,670
        round trips and 1.6 seconds of dead air on every filter change, role
        switch and tab change — the single slowest thing in the interface, and
        invisible in any profile of the frontend.

        The read model is a read model, so the fix is the obvious one: fetch each
        table once for the whole set and index it in memory. `_assemble` reads
        from the context when it is given one and queries when it is not, so the
        single-topic detail path is untouched.
        """
        if not topic_ids:
            return {}
        placeholders = ",".join("?" * len(topic_ids))
        params = tuple(topic_ids)

        # Latest score per (topic, kind). The window function does the
        # "ORDER BY computed_at DESC LIMIT 1" that used to run once per topic
        # per kind; SQLite has had them since 3.25 and the schema is indexed for
        # exactly this partition.
        scores: dict[tuple[str, str], dict[str, Any]] = {}
        for row in self.db.query(
            f"""SELECT * FROM (
                     SELECT *, ROW_NUMBER() OVER (
                         PARTITION BY opportunity_id, kind ORDER BY computed_at DESC, id DESC
                     ) AS rn
                     FROM scores WHERE opportunity_id IN ({placeholders})
                 ) WHERE rn = 1""",
            params,
        ):
            scores[(row["opportunity_id"], row["kind"])] = dict(row)

        links: dict[str, list[dict[str, Any]]] = {}
        for row in self.db.query(
            f"SELECT * FROM opportunity_links WHERE opportunity_id IN ({placeholders}) AND rejected = 0",
            params,
        ):
            links.setdefault(row["opportunity_id"], []).append(dict(row))

        node_ids = sorted({l["node_id"] for rows in links.values() for l in rows})
        node_labels = self._node_labels(node_ids)

        # The competition block is shaped by its own module, so the row is
        # fetched here and handed to `competition_from_row` — one place decides
        # what a competition block looks like.
        competition_rows = {
            row["opportunity_id"]: dict(row)
            for row in self.db.query(
                f"SELECT * FROM topic_competition WHERE opportunity_id IN ({placeholders})", params
            )
        }

        sizes: dict[str, dict[str, Any]] = {}
        for row in self.db.query(
            f"""SELECT opportunity_id, method, sam_base, tam_base, confidence FROM market_sizes
                WHERE opportunity_id IN ({placeholders})
                ORDER BY CASE method WHEN 'bottom_up_adoption' THEN 0 ELSE 1 END""",
            params,
        ):
            # Bottom-up wins where both methods exist; the ORDER BY above puts it
            # first, so the first row per topic is the one to keep.
            sizes.setdefault(row["opportunity_id"], dict(row))

        counts = {
            row["opportunity_id"]: row["n"]
            for row in self.db.query(
                f"SELECT opportunity_id, COUNT(*) AS n FROM opportunity_signals "
                f"WHERE opportunity_id IN ({placeholders}) GROUP BY opportunity_id", params
            )
        }
        described = {
            row["opportunity_id"] for row in self.db.query(
                f"SELECT opportunity_id FROM topic_descriptions WHERE opportunity_id IN ({placeholders})",
                params,
            )
        }
        briefed = {
            row["opportunity_id"] for row in self.db.query(
                f"SELECT opportunity_id FROM topic_briefs WHERE opportunity_id IN ({placeholders})",
                params,
            )
        }
        workflow = self.workflow.prefetch(list(topic_ids)) if self.workflow else {"state": {}, "assessments": {}}

        return {
            "scores": scores,
            "links": links,
            "node_labels": node_labels,
            "competition": competition_rows,
            "sizes": sizes,
            "signal_counts": counts,
            "described": described,
            "briefed": briefed,
            "workflow_state": workflow["state"],
            "assessments": workflow["assessments"],
        }

    def _assemble(self, topic: dict[str, Any], full: bool = False,
                  context: dict[str, Any] | None = None) -> dict[str, Any]:
        topic_id = topic["id"]
        context = context or {}
        latest = {}
        for kind in ("attractiveness", "right_to_win"):
            if context:
                row = (context.get("scores") or {}).get((topic_id, kind))
            else:
                row = self.db.query_one(
                    "SELECT * FROM scores WHERE opportunity_id = ? AND kind = ? "
                    "ORDER BY computed_at DESC, id DESC LIMIT 1",
                    (topic_id, kind),
                )
            if row:
                latest[kind] = {
                    "score": row["score"],
                    "components": unjs(row["components"], {}),
                    "inputs": unjs(row["inputs"], {}) if full else None,
                    "weight_set": row["weight_set"],       # SC-10
                    "computed_at": row["computed_at"],
                }

        if context:
            links = list((context.get("links") or {}).get(topic_id, []))
            node_labels = context.get("node_labels") or {}
        else:
            links = [dict(r) for r in self.db.query(
                "SELECT * FROM opportunity_links WHERE opportunity_id = ? AND rejected = 0", (topic_id,)
            )]
            node_labels = self._node_labels([l["node_id"] for l in links])
        typed_links = []
        for link in links:
            meaning = LINK_MEANING[link["link_type"]]
            typed_links.append({
                "node_id": link["node_id"],
                "node_type": link["node_id"].split(":", 1)[0],
                "label": node_labels.get(link["node_id"], link["node_id"]),
                "link_type": link["link_type"],
                "link_meaning": meaning[0],
                "owner": meaning[2],
                "action": meaning[3],
                "confidence": link["confidence"],
                "evidence": unjs(link["evidence"], {}),      # LK-08: inspectable, never aggregated
                "confirmed_by": link["confirmed_by"],        # DR-13
            })

        # Only delivery-bearing links shorten portfolio distance; supporting
        # evidence (references, certifications, analyst positions, capability
        # pools) is displayed and scored but never counted here — see
        # graph.SUPPORTING for why.
        distance = min(
            (LINK_DISTANCE[l["link_type"]] for l in links if l["link_type"] in LINK_DISTANCE),
            default=4,
        )

        signals = []
        if full:
            rows = self.db.query(
                """SELECT s.id, s.title, s.url, s.publisher, s.published_at, s.signal_type, s.tier,
                          s.extract, s.language, s.geographies
                   FROM signals s JOIN opportunity_signals os ON os.signal_id = s.id
                   WHERE os.opportunity_id = ? ORDER BY s.tier ASC, s.published_at DESC""",
                (topic_id,),
            )
            signals = [dict(r) | {"geographies": unjs(r["geographies"], [])} for r in rows]

        rtw_inputs = (latest.get("right_to_win") or {}).get("inputs") or {}
        if not full:
            # SC-13's evidence-gap flag lives in the stored inputs, which the
            # summary shape deliberately drops — so it is read back here rather
            # than shipped to every list row.
            if context:
                row = (context.get("scores") or {}).get((topic_id, "right_to_win"))
                rtw_inputs = unjs(row["inputs"], {}) if row else {}
            else:
                row = self.db.query_one(
                    "SELECT inputs FROM scores WHERE opportunity_id = ? AND kind = 'right_to_win' "
                    "ORDER BY computed_at DESC, id DESC LIMIT 1", (topic_id,)
                )
                rtw_inputs = unjs(row["inputs"], {}) if row else {}
        evidence_gap = bool(rtw_inputs.get("_evidence_gap"))

        attractiveness_score = (latest.get("attractiveness") or {}).get("score")
        rtw_score = (latest.get("right_to_win") or {}).get("score")
        workflow_state = conviction = divergence = None
        if self.workflow is not None:
            prefetched_state = (context.get("workflow_state") or {}).get(topic_id) if context else None
            prefetched_assessments = (
                (context.get("assessments") or {}).get(topic_id, []) if context else None
            )
            workflow_state = self.workflow.state_for(topic_id, prefetched_state)
            conviction = self.workflow.conviction_for(topic_id, prefetched_assessments)
            divergence = self.workflow.divergence_for(
                topic_id, attractiveness_score, rtw_score, conviction
            )

        assembled = {
            "id": topic_id,
            "version": topic["version"],
            "triple": {
                "vertical": topic["vertical"],
                "use_case": topic["use_case"],
                "technology": topic["technology"],
            },
            "labels": {
                "vertical": self.cfg.verticals.label(topic["vertical"]),
                "use_case": self.cfg.use_cases.label(topic["use_case"]),
                "technology": self.cfg.technologies.label(topic["technology"]),
            },
            "statement": topic["statement"],
            "domains": unjs(topic["domains"], []),
            "domain_labels": [self.cfg.domains.label(d) for d in unjs(topic["domains"], []) or []],
            "personas": unjs(topic["personas"], []),
            "persona_labels": [self.cfg.personas.label(p) for p in unjs(topic["personas"], []) or []],
            "geographies": unjs(topic["geographies"], []),
            # Derived, not stored: the ISO codes above are the truth and a
            # cluster is a reading of them (Orange Business grouping).
            "market_clusters": self.cfg.market_clusters.clusters_for(
                unjs(topic["geographies"], []) or []
            ),
            "market_cluster_labels": [
                self.cfg.market_clusters.label(c)
                for c in self.cfg.market_clusters.clusters_for(
                    unjs(topic["geographies"], []) or []
                )
            ],
            # What it is ABOUT versus who should SEE it. A third of the corpus is
            # tagged EU and nothing else: those topics are attributed to no
            # cluster (above) but must still reach a planner filtering on France,
            # which is what this carries. Kept in the payload rather than hidden
            # so the filter's behaviour can be read off the data it filters.
            "market_cluster_reach": self.cfg.market_clusters.reach_for(
                unjs(topic["geographies"], []) or []
            ),
            "state": topic["state"],
            "state_reason": topic["state_reason"],
            "horizon": topic["horizon"],
            "horizon_basis": topic["horizon_basis"],
            "why_hot": unjs(topic["why_hot"], []),            # FR-14, every claim cited
            "next_actions": unjs(topic["next_actions"], {}),  # FR-17
            "attractiveness": latest.get("attractiveness"),
            "right_to_win": latest.get("right_to_win"),
            "portfolio_distance": distance,                    # FR-30
            "link_types": sorted({l["link_type"] for l in links}),
            "links": typed_links,                              # FR-29, LK-08
            "evidence_gap_warning": evidence_gap,              # SC-13
            "reference_density": rtw_inputs.get("reference_density", {}),
            "critic_score": topic["critic_score"],
            "first_seen": topic["first_seen"],
            "last_refresh": topic["last_refresh"],             # FR-19
            # FR-25 / §4.10. Conviction is a THIRD quantity, never folded into
            # attractiveness or right-to-win (SC-12, SC-14).
            "workflow": workflow_state,
            "conviction": conviction,
            "divergence": divergence,
            # §4.3.4 market sizing and §4.3.3 competitive intensity. Both are
            # quantities in their own right, kept beside attractiveness and
            # right to win rather than folded into either (SC-12): "the world is
            # big", "we can win" and "the field is crowded" are three different
            # facts and a reader needs all three separately.
            "competition": (
                competition_from_row((context.get("competition") or {}).get(topic_id))
                if context else competition_for_topic(self.db, topic_id)
            ),
            "provenance": {                                    # DR-10, NFR-02
                "pipeline_version": topic["pipeline_version"],
                "prompt_version": topic["prompt_version"],
                "model_version": topic["model_version"],
                "weight_set": (latest.get("attractiveness") or {}).get("weight_set"),
            },
        }
        if full:
            assembled["signals"] = signals
            assembled["signal_count"] = len(signals)
            assembled["market_size"] = sizes_for_topic(self.db, topic_id)
            # Imported lazily: `brief` imports the read model to assemble a
            # topic, so importing it at module scope would close the loop.
            from .brief import brief_for_topic
            from .pipeline.describe import description_for_topic

            assembled["description"] = description_for_topic(self.db, topic_id)
            assembled["brief"] = brief_for_topic(self.db, topic_id)
        else:
            if context:
                assembled["signal_count"] = (context.get("signal_counts") or {}).get(topic_id, 0)
            else:
                row = self.db.query_one(
                    "SELECT COUNT(*) AS n FROM opportunity_signals WHERE opportunity_id = ?", (topic_id,)
                )
                assembled["signal_count"] = row["n"] if row else 0
            # A list row needs the headline figure, not the whole derivation.
            # The bottom-up estimate is the one §4.3.4 asks for; the observed
            # procurement floor stands in where no bottom-up estimate exists,
            # which is the public-sector case.
            if context:
                size = (context.get("sizes") or {}).get(topic_id)
            else:
                size = self.db.query_one(
                    """SELECT method, sam_base, tam_base, confidence FROM market_sizes
                       WHERE opportunity_id = ?
                       ORDER BY CASE method WHEN 'bottom_up_adoption' THEN 0 ELSE 1 END LIMIT 1""",
                    (topic_id,),
                )
            # Whether the written artefacts exist. A list that offers "open the
            # brief" on every row, when two thirds of them have none, teaches
            # people to distrust the button.
            if context:
                assembled["has_description"] = topic_id in (context.get("described") or set())
                assembled["has_brief"] = topic_id in (context.get("briefed") or set())
            else:
                artefacts = self.db.query_one(
                    "SELECT EXISTS(SELECT 1 FROM topic_descriptions WHERE opportunity_id = ?) AS d, "
                    "       EXISTS(SELECT 1 FROM topic_briefs WHERE opportunity_id = ?) AS b",
                    (topic_id, topic_id),
                )
                assembled["has_description"] = bool(artefacts["d"]) if artefacts else False
                assembled["has_brief"] = bool(artefacts["b"]) if artefacts else False
            assembled["market_size_summary"] = (
                {"method": size["method"], "sam_base": size["sam_base"],
                 "tam_base": size["tam_base"], "confidence": size["confidence"]}
                if size else None
            )
        return assembled

    def _node_labels(self, node_ids: list[str]) -> dict[str, str]:
        if not node_ids:
            return {}
        placeholders = ",".join("?" * len(node_ids))
        rows = self.db.query(
            f"SELECT id, label FROM graph_nodes WHERE id IN ({placeholders})", tuple(node_ids)
        )
        return {r["id"]: r["label"] for r in rows}

    # -- role-specific ranking (FR-13, FR-22, FR-31) ------------------------

    def rank(self, topics: list[dict[str, Any]], role: str,
             apply_role_filter: bool = True) -> list[dict[str, Any]]:
        """Each role has a DISTINCT default ranking function (FR-13, §3.2).

        §3.2: "The same topic can be excellent for a strategist (large, early, no
        proof points yet) and useless for a salesperson (nothing to show a
        customer). The system must express this as different default ranking
        functions per role mode, not as a single score with different filters."
        """
        mode = self.cfg.role_mode(role)
        weights = mode["ranking"]
        allowed = set(mode.get("link_types", []))
        require_ref = mode.get("default_filters", {}).get("require_reference_in_vertical", False)

        if not apply_role_filter:
            # Ordering without gatekeeping. The workflow board needs this: a
            # stage owner must see every topic sitting in their column, even one
            # their role mode would not normally surface. Hiding a topic from
            # the person accountable for advancing it would break the stage gate
            # (§4.10 model A) in the name of enforcing a discovery filter.
            allowed = set()
            require_ref = False

        eligible = []
        for topic in topics:
            # FR-31: role-mode filtering is DRIVEN by portfolio distance, so it
            # matches on delivery link types only. A certification alone must
            # not put a topic in front of a salesperson.
            delivery_types = {t for t in topic["link_types"] if t in LINK_DISTANCE}
            if allowed and not (delivery_types & allowed):
                continue
            if require_ref:
                # §4.5.3 gives the sales acceptance criterion a computable
                # definition: L0 or L1, with at least one published reference in
                # the vertical. Without this the persona's own acceptance
                # criterion — "only topics with enough internal content to
                # credibly back up" — cannot be met.
                has_reference = any(l["node_type"] == "reference" for l in topic["links"])
                if not has_reference or topic["evidence_gap_warning"]:
                    continue
            eligible.append(topic)

        for topic in eligible:
            attractiveness = (topic.get("attractiveness") or {}).get("score", 0.0)
            components = (topic.get("attractiveness") or {}).get("components", {}) or {}
            rtw = (topic.get("right_to_win") or {}).get("score", 0.0)
            rtw_components = (topic.get("right_to_win") or {}).get("components", {}) or {}

            proof_density = (
                rtw_components.get("reference_density", 0.0) * 0.6
                + rtw_components.get("external_validation", 0.0) * 0.4
            )
            # Presales differentiation: Orange has assets AND the market has few
            # credible providers. Partner-tier strength and analyst recognition
            # stand in for "few credible providers" until a competitor feed exists.
            differentiation = (
                rtw_components.get("technology_ownership", 0.0) * 0.35
                + rtw_components.get("external_validation", 0.0) * 0.35
                + rtw_components.get("compliance_fit", 0.0) * 0.30
            )
            conviction_block = topic.get("conviction") or {}
            conviction_score = conviction_block.get("score")
            axes = conviction_block.get("axes") or {}
            # Each role leans on the axis it is accountable for, and falls back
            # to the blended conviction when its own axis has no rating yet.
            role_axis = {"strategist": "strategic_fit", "sales": "customer_demand",
                         "presales": "deliverability"}.get(role)
            own_axis = (axes.get(role_axis) or {}).get("score") if role_axis else None
            conviction_term = own_axis if own_axis is not None else conviction_score

            terms = {
                "attractiveness": attractiveness,
                "right_to_win": rtw,
                "novelty_momentum": components.get("novelty_momentum", 0.0),
                "proof_point_density": proof_density,
                "differentiation": differentiation,
                # Normalised so a further-away topic scores 100 on this term;
                # the sign in role_modes.yaml decides whether that helps or hurts.
                "portfolio_distance": 100.0 * topic["portfolio_distance"] / 4.0,
                # Absent conviction is NOT zero — an unrated topic would be
                # pushed to the bottom purely for being unrated, which is a
                # popularity bias, not a judgement. Unrated topics sit neutral.
                "conviction": conviction_term if conviction_term is not None else 50.0,
            }
            effective = dict(weights)
            if conviction_term is not None:
                effective["conviction"] = float(
                    self.cfg.settings.get("workflow", {}).get("conviction_ranking_weight", 0.0)
                )
            topic["rank_score"] = round(sum(terms.get(k, 0.0) * w for k, w in effective.items()), 3)
            topic["rank_explanation"] = {
                k: {"value": round(terms.get(k, 0.0), 2), "weight": w,
                    "contribution": round(terms.get(k, 0.0) * w, 2)}
                for k, w in effective.items()
            }
            if mode.get("low_rtw_is_penalty") is False and rtw < 40:
                topic["strategist_flag"] = "low right-to-win — flagged, not penalised"

        eligible.sort(key=lambda t: t.get("rank_score", 0.0), reverse=True)
        return eligible

    def view(self, role: str, filters: dict[str, Any] | None = None,
             limit: int | None = None, explore: bool = True,
             sort: str | None = None) -> dict[str, Any]:
        """A capped, filtered, role-ranked view (FR-21, FR-22, AC-04, AC-05).

        `sort` re-orders what the role ranking has already selected; it never
        replaces it. FR-13 makes the per-role ranking function the default
        contract, and the role filter still decides what is eligible — a
        salesperson sorting by market size still sees only topics with a proof
        point behind them (§4.5.3).
        """
        filters = filters or {}
        cap = limit or int(self.cfg.settings["serving"]["max_topics_per_view"])
        topics = self.topics()
        filtered = [t for t in topics if _matches(t, filters)]
        ranked = self.rank(filtered, role)
        if sort and sort != "rank":
            ranked = _sorted(ranked, sort)

        # Facet counts over everything the ROLE can see, not over the capped
        # head. The rail was counting the 24 topics on screen, so "CISO: 0" meant
        # "none in this page" while 26 matched — a filter that appears to lead
        # nowhere is a filter nobody clicks. Counted before the cap and after the
        # role filter, because a count that promises topics the role may not see
        # (§4.5.3) would be a different lie.
        facets = _facets(ranked)

        head = ranked[:cap]
        exploration: list[dict[str, Any]] = []
        if explore:
            # §4.7.6 exposure-bias remedy: reserve a small randomised slot in
            # every view for topics the model did not rank first, and
            # deliberately sample Watchlist topics into it (the selection-bias
            # remedy, since Watchlist topics otherwise never accumulate labels).
            #
            # The pool is drawn from ROLE-ELIGIBLE topics only. The bias being
            # corrected is a RANKING bias, not the role's eligibility filter:
            # §4.5.3 is explicit that a topic with no proof point is "precisely
            # the thing a salesperson should never be shown", and an exploration
            # slot that smuggled one past the filter would break the sales
            # persona's own acceptance criterion in the name of fixing a
            # different problem.
            #
            # Selection is seeded so the same view is reproducible (SC-11) while
            # still rotating across days.
            slot = int(self.cfg.settings["serving"]["exploration_slot_size"])
            head_ids = {t["id"] for t in head}
            tail = ranked[cap:]
            watchlist = [t for t in ranked if t["state"] == "watchlist" and t["id"] not in head_ids]
            pool = watchlist + [t for t in tail if t["id"] not in {w["id"] for w in watchlist}]
            if pool and slot:
                seed = f"{role}|{sorted(filters.items())}|{dt.date.today().isoformat()}"
                digest = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
                # Compared by id. The membership test used to be `chosen not in
                # exploration`, against a list holding COPIES that carry an extra
                # `exploration_slot` key — so it never matched and the guard it
                # looks like was doing nothing. Two offsets can land on the same
                # index whenever the stride and the pool size share a factor, and
                # the same topic would then be shown twice in one slot.
                picked: set[str] = set()
                for offset in range(min(slot, len(pool))):
                    chosen = pool[(digest + offset * 7919) % len(pool)]
                    if chosen["id"] in picked:
                        continue
                    picked.add(chosen["id"])
                    chosen = dict(chosen)
                    chosen["exploration_slot"] = True
                    exploration.append(chosen)

        last_refresh = self.db.query_one(
            "SELECT finished_at, started_at, reference_date FROM refreshes "
            f"WHERE {NOT_A_GENERATION} ORDER BY started_at DESC LIMIT 1"
        )
        return {
            "role": role,
            "sort": sort or "rank",
            "role_label": self.cfg.role_mode(role)["label"],
            "primary_action": self.cfg.role_mode(role)["primary_action"],
            "filters": filters,
            "total_matching": len(ranked),
            "facets": facets,
            "cap": cap,
            "topics": [_for_list(t) for t in head],
            "exploration": [_for_list(t) for t in exploration],
            "last_refresh": dict(last_refresh) if last_refresh else None,   # AC-02, FR-19
            "weight_set": self.cfg.weight_set,
        }

    # -- history (FR-20) ---------------------------------------------------

    def history(self, topic_id: str) -> dict[str, Any]:
        """Score trajectory and state transitions.

        §4.6 calibration-drift guard: every score records the configuration
        version that produced it, and the UI never plots trajectories across a
        version boundary without saying so. The `weight_set_changed` flag is how
        the UI is told.
        """
        rows = self.db.query(
            "SELECT computed_at, kind, score, components, weight_set FROM scores "
            "WHERE opportunity_id = ? ORDER BY computed_at ASC", (topic_id,)
        )
        series: dict[str, list[dict[str, Any]]] = {"attractiveness": [], "right_to_win": []}
        weight_sets: list[str] = []
        for row in rows:
            weight_sets.append(row["weight_set"])
            series.setdefault(row["kind"], []).append({
                "at": row["computed_at"],
                "score": row["score"],
                "components": unjs(row["components"], {}),
                "weight_set": row["weight_set"],
            })
        distinct = sorted(set(weight_sets))
        return {
            "topic_id": topic_id,
            "series": series,
            "weight_sets": distinct,
            "weight_set_changed": len(distinct) > 1,
            "comparability_warning": (
                "Scores span more than one weight set and are not directly comparable (§4.6)."
                if len(distinct) > 1 else None
            ),
        }

    # -- white space (FR-32) -----------------------------------------------

    def white_space_filtered(self, min_attractiveness: float,
                             filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """White space, honouring the filter rail.

        The rail stayed fully interactive on this tab and changed nothing, which
        is worse than not offering it: a strategist who filtered to Manufacturing
        and read the unchanged list drew a conclusion about the wrong set.
        """
        rows = self.white_space(min_attractiveness)
        return [t for t in rows if _matches(t, filters or {})]

    def white_space(self, min_attractiveness: float = 55.0) -> list[dict[str, Any]]:
        """High attractiveness with no path from the current portfolio (§4.5.5)."""
        out = []
        for topic in self.topics(states=("active", "watchlist", "fading", "candidate")):
            score = (topic.get("attractiveness") or {}).get("score", 0.0)
            if topic["portfolio_distance"] >= 3 and score >= min_attractiveness:
                out.append(topic)
        out.sort(key=lambda t: (t.get("attractiveness") or {}).get("score", 0.0), reverse=True)
        return out

    # -- coverage metrics (NFR-08) -----------------------------------------

    def coverage(self) -> dict[str, Any]:
        """Language and geography coverage, reported as a metric (NFR-08).

        Table 36 lists "anglophone and EU bias in sources" as a principal risk
        whose mitigation is "explicit language and geography coverage monitoring
        as a reported metric" — so it is computed and served, not assumed.
        """
        languages = self.db.query(
            "SELECT language, COUNT(*) AS n FROM signals GROUP BY language ORDER BY n DESC"
        )
        tiers = self.db.query("SELECT tier, COUNT(*) AS n FROM signals GROUP BY tier ORDER BY tier")
        types = self.db.query(
            "SELECT signal_type, COUNT(*) AS n FROM signals GROUP BY signal_type ORDER BY n DESC"
        )
        sources = self.db.query(
            "SELECT source_id, COUNT(*) AS n FROM signals GROUP BY source_id ORDER BY n DESC"
        )
        geo: dict[str, int] = {}
        clusters: dict[str, int] = {}
        supranational = 0
        unmapped: dict[str, int] = {}
        mc = self.cfg.market_clusters
        for row in self.db.query("SELECT geographies FROM signals"):
            for code in unjs(row["geographies"], []) or []:
                geo[code] = geo.get(code, 0) + 1
                if mc.is_supranational(code):
                    supranational += 1
                elif cluster := mc.cluster_for(code):
                    clusters[cluster] = clusters.get(cluster, 0) + 1
                else:
                    # Named rather than absorbed. These are extraction bugs (TU
                    # for TR, JA for JP) and countries the taxonomy has not
                    # caught up with; a cluster chart that quietly dropped them
                    # would read as full coverage of a corpus it did not cover.
                    norm = mc.normalise(code)
                    unmapped[norm] = unmapped.get(norm, 0) + 1
        verticals = self.db.query(
            "SELECT vertical, COUNT(*) AS n FROM opportunity_spaces WHERE merged_into IS NULL "
            "GROUP BY vertical ORDER BY n DESC"
        )
        return {
            "languages": {r["language"] or "unknown": r["n"] for r in languages},
            "tiers": {str(r["tier"]): r["n"] for r in tiers},
            "signal_types": {r["signal_type"] or "unclassified": r["n"] for r in types},
            "sources": {r["source_id"]: r["n"] for r in sources},
            "geographies": dict(sorted(geo.items(), key=lambda kv: -kv[1])[:25]),
            "market_clusters": {
                mc.label(k): v
                for k, v in sorted(clusters.items(), key=lambda kv: -kv[1])
            },
            "market_cluster_gaps": {
                "supranational": supranational,
                "unmapped": dict(sorted(unmapped.items(), key=lambda kv: -kv[1])),
            },
            "topics_per_vertical": {r["vertical"]: r["n"] for r in verticals},
            "competitors": self._competitor_coverage(),
        }

    def _competitor_coverage(self) -> dict[str, Any]:
        """How much of the competitive picture actually exists (NFR-08).

        This view is where the radar says what it does not know, and competitor
        profiling has three separate gaps that a reader would otherwise have to
        infer from an empty panel:

          the register   how many competitors have been read from their own site,
                         and — named individually — which ones refused. A blocked
                         competitor is a permanent gap, not a pending one.
          the assessment how many spaces have a competitive intensity at all. A
                         space without one shows an empty competitor tab, and
                         that is a processing gap rather than a finding.
          the comparison how many have the written per-competitor analysis, which
                         costs a model call and is therefore never universal.

        Reported together because they compound: a written comparison over a
        space whose competitors are mostly unprofiled is thinner than the same
        comparison elsewhere, and only these three numbers side by side say so.
        """
        register = self.cfg.competitors_raw["competitors"]
        rows = {r["competitor_id"]: r for r in self.db.query(
            "SELECT competitor_id, status, status_reason FROM competitor_profiles")}
        labels = {e["id"]: e["label"] for e in register}

        by_status: dict[str, int] = {}
        unread_named: dict[str, list[str]] = {}
        for entry in register:
            row = rows.get(entry["id"])
            status = row["status"] if row else "unread"
            by_status[status] = by_status.get(status, 0) + 1
            if status != "profiled":
                unread_named.setdefault(status, []).append(labels[entry["id"]])

        topics_total = self.db.query_one(
            "SELECT COUNT(*) AS n FROM opportunity_spaces WHERE merged_into IS NULL")["n"]
        assessed = self.db.query_one("SELECT COUNT(*) AS n FROM topic_competition")["n"]
        analysed = self.db.query_one(
            "SELECT COUNT(*) AS n FROM topic_competitor_analysis")["n"]
        written = self.db.query_one(
            "SELECT COUNT(*) AS n FROM topic_competitor_analysis WHERE narrative IS NOT NULL")["n"]
        pages = self.db.query_one("SELECT COUNT(*) AS n FROM competitor_pages")["n"]

        return {
            "register_total": len(register),
            "register_version": self.cfg.competitors_raw["version"],
            "by_status": by_status,
            "unread_named": {k: sorted(v) for k, v in unread_named.items()},
            "pages_read": pages,
            "topics_total": topics_total,
            "topics_assessed": assessed,
            "topics_analysed": analysed,
            "topics_written": written,
        }


#: Fields a topic carries that only the DETAIL view renders. They are computed
#: for ranking and filtering and then dropped before the response: every claim
#: with its citations, every asset link, the per-role next actions and the rank
#: arithmetic came to about a megabyte per view, for content no list row shows.
#: Opening a topic fetches them from /api/topics/{id}, which is where they are
#: read (§4.9 puts the decomposition on the topic page, not in the list).
#: `next_actions` deliberately stays: AC-03 requires that "every topic in every
#: role mode renders a non-empty, role-appropriate next action", and the CLI's
#: topic list prints it. It is three sentences on the topics actually shown, not
#: on every topic matched.
_DETAIL_ONLY_FIELDS = ("links", "why_hot", "reference_density",
                       "rank_explanation", "provenance", "state_reason", "horizon_basis")


#: Orderings a user can ask for, beyond the role's own ranking function.
SORTS = {
    "rank": "Ranked for this role",
    "market_size": "Largest serviceable market",
    "attractiveness": "Highest attractiveness",
    "right_to_win": "Strongest right to win",
    "competition": "Least contested first",
    "signals": "Most evidence",
    "recent": "Most recently refreshed",
}

_COMPETITION_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3}


def _facets(topics: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """How many topics each filter value would leave, across the whole result set."""
    facets: dict[str, dict[str, int]] = {
        "vertical": {}, "domain": {}, "persona": {}, "geography": {},
        "market_cluster": {}, "horizon": {}, "state": {}, "competition": {},
    }

    def bump(dimension: str, value: str | None) -> None:
        if value:
            facets[dimension][value] = facets[dimension].get(value, 0) + 1

    for topic in topics:
        bump("vertical", topic["triple"]["vertical"])
        bump("horizon", topic.get("horizon"))
        bump("state", topic.get("state"))
        bump("competition", (topic.get("competition") or {}).get("level"))
        for domain in topic.get("domains") or []:
            bump("domain", domain)
        for persona in topic.get("personas") or []:
            bump("persona", persona)
        for geography in topic.get("geographies") or []:
            bump("geography", geography)
        for cluster in topic.get("market_clusters") or []:
            bump("market_cluster", cluster)
    facets["with_brief"] = {"true": sum(1 for t in topics if t.get("has_brief"))}
    return facets


def _sorted(topics: list[dict[str, Any]], sort: str) -> list[dict[str, Any]]:
    """Re-order a ranked list without letting a missing value pretend to be zero.

    A topic that could not be sized is not a topic worth nothing — §4.3.4 leaves
    it unsized on purpose. Sorting it to the bottom of a "largest first" list is
    honest; sorting it to the top of a "smallest first" one would not be, so
    unknowns are always last whichever direction the sort runs.
    """
    def key(topic: dict[str, Any]):
        if sort == "market_size":
            size = (topic.get("market_size_summary") or {}).get("sam_base")
            return (size is None, -(size or 0.0))
        if sort == "attractiveness":
            score = (topic.get("attractiveness") or {}).get("score")
            return (score is None, -(score or 0.0))
        if sort == "right_to_win":
            score = (topic.get("right_to_win") or {}).get("score")
            return (score is None, -(score or 0.0))
        if sort == "competition":
            level = (topic.get("competition") or {}).get("level")
            return (level is None, _COMPETITION_ORDER.get(level, 99))
        if sort == "signals":
            return (False, -topic.get("signal_count", 0))
        if sort == "recent":
            return (False, topic.get("last_refresh") or "")
        return (False, -topic.get("rank_score", 0.0))

    reverse = sort == "recent"
    return sorted(topics, key=key, reverse=reverse)


def _for_list(topic: dict[str, Any]) -> dict[str, Any]:
    """Project an assembled topic down to what a list row or radar marker shows."""
    trimmed = {k: v for k, v in topic.items() if k not in _DETAIL_ONLY_FIELDS}
    # Conviction's `voices` carry every rationale anyone has written; the list
    # shows a number and the detail pane shows the words.
    conviction = trimmed.get("conviction")
    if conviction and conviction.get("axes"):
        trimmed["conviction"] = dict(conviction, axes={
            axis: {k: v for k, v in block.items() if k != "voices"}
            for axis, block in conviction["axes"].items()
        })
    # Same for competitors: the row shows the level, the pane shows who.
    competition = trimmed.get("competition")
    if competition:
        trimmed["competition"] = {
            k: v for k, v in competition.items() if k not in ("competitors", "inputs")
        }
    return trimmed


def _matches(topic: dict[str, Any], filters: dict[str, Any]) -> bool:
    """Multi-select filtering on vertical, geography, domain and persona (AC-04, FR-12)."""
    if (verticals := filters.get("vertical")) and topic["triple"]["vertical"] not in verticals:
        return False
    if (domains := filters.get("domain")) and not (set(topic["domains"]) & set(domains)):
        return False
    if (personas := filters.get("persona")) and not (set(topic["personas"]) & set(personas)):
        return False
    if geographies := filters.get("geography"):
        topic_geo = set(topic["geographies"])
        # A topic with no geography is global, not excluded.
        if topic_geo and not (topic_geo & set(geographies)):
            return False
    if clusters := filters.get("market_cluster"):
        # Reach, not attribution: an EU-wide directive is attributed to no single
        # cluster but is relevant to every European one, and filtering on the
        # attributed set would have shown it under Asia (empty set matches
        # everything) instead. A genuinely empty reach — no geography, or a
        # global code — still matches, which is the rule geography already uses.
        reach = set(topic.get("market_cluster_reach") or [])
        if reach and not (reach & set(clusters)):
            return False
    if (horizons := filters.get("horizon")) and topic["horizon"] not in horizons:
        return False
    if (states := filters.get("state")) and topic["state"] not in states:
        return False
    # §4.3.3: a crowded field is a filterable fact — "show me where we would not
    # be fighting four incumbents" is a real strategist question.
    if levels := filters.get("competition"):
        level = (topic.get("competition") or {}).get("level")
        if level not in levels:
            return False
    if filters.get("has_brief") and not topic.get("has_brief"):
        return False
    if query := filters.get("q"):
        needle = str(query).lower()
        haystack = " ".join([
            topic["statement"],
            " ".join(c.get("claim", "") for c in topic["why_hot"]),
            topic["labels"]["vertical"], topic["labels"]["use_case"], topic["labels"]["technology"],
        ]).lower()
        if needle not in haystack:
            return False
    return True


# ---------------------------------------------------------------------------
# Public aliases.
#
# The generation endpoints have to filter, count and shape opportunity spaces
# with EXACTLY the rules the radar view uses — including "no geography means
# global" — or the "spaces that already match" count on the Generate screen
# would mean something different from the same filter set on the radar. These
# exist so that reuse is a stated contract rather than a private import.
# ---------------------------------------------------------------------------

#: Refresh ids are prefixed by what produced them: `R-` for a cadence run
#: (`radar refresh` / `replay`), `G-` for an on-demand generation run. Both
#: write scores and signal attachments, so both need a row in `refreshes`
#: (NFR-04) — but only the first COLLECTED anything, and AC-02's freshness date
#: is a claim about the evidence, not about the topic table. A generation run
#: that stamped today over a corpus last collected six weeks ago would make the
#: radar look fresh for having rearranged what it already had.
GENERATION_ID_PREFIX = "G-"

#: The freshness clause, as one string so the two places that ask cannot drift.
NOT_A_GENERATION = f"id NOT LIKE '{GENERATION_ID_PREFIX}%'"


def refresh_kind(refresh_id: str | None) -> str:
    return "generation" if (refresh_id or "").startswith(GENERATION_ID_PREFIX) else "cadence"


matches_filters = _matches
topic_for_list = _for_list
facet_counts = _facets
