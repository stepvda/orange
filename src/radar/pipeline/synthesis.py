"""Pipeline stages 5-6a: Synthesise and curate (Table 16).

Theme clusters + taxonomy -> candidate opportunity spaces -> curated topics.

This module implements the four hallucination defences of §4.4.4 in the order
the document ranks them by effectiveness:

  1. Evidence binding      — every claim references signal ids that must exist
                             in the cluster that produced the candidate.
                             Uncited claims are STRIPPED, not rewritten.
  2. Closed-vocabulary out — taxonomy values validated against the enumerations.
  3. No numbers            — enforced in the prompt (llm.NO_NUMBERS_RULE) and
                             detected here as a critic test.
  4. Entailment check      — a cheap second pass on the "why hot" claims.

and the identity rules of §4.4.5, which are what make momentum measurable:
canonical identity is the taxonomy triple; a recurring topic is UPDATED, not
recreated (DR-03).
"""

from __future__ import annotations

import datetime as dt
import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
from concurrent.futures import ThreadPoolExecutor

from ..config import Config
from ..db import Database, js, unjs
from ..embeddings import Embedder
from ..llm import LLMClient
from . import prompts

log = logging.getLogger(__name__)

#: Used when a helper is called outside the parallel path.
_NULL_LOCK = threading.Lock()

#: A long synthesis run is watched from the Generate screen, so it reports what
#: it is doing and can be asked to stop. All three are optional: nothing in the
#: pipeline path supplies them and nothing in it needs to.
ProgressFn = Callable[[str], None]
CancelFn = Callable[[], bool]


@dataclass(frozen=True)
class SynthesisProgress:
    """A countable position in a run, for a progress bar that is not a fiction.

    Two quantities, because neither alone is honest. `created` is what the user
    asked for and the only thing that finishes the job — but it can sit at zero
    for minutes while the model works, and a bar frozen at zero reads as a hang.
    `clusters_done` of `clusters_total` moves continuously and is real work, but
    reading every cluster does not guarantee a single space. The screen shows
    the first as the number and lets the second drive the motion, capped so that
    evidence read can never render as a request fulfilled.
    """

    round: int
    #: What a "unit" is depends on the path, so it is named rather than assumed:
    #: the grid path reads THEME CLUSTERS, the free-text path makes GENERATION
    #: PASSES over one retrieved evidence set. Both are real, countable work.
    units_total: int
    units_done: int
    unit_label: str = "theme cluster"
    #: Cumulative across rounds, not per round — the screen counts spaces, and
    #: a counter that reset each round would count down.
    created: tuple[str, ...] = ()


TickFn = Callable[[SynthesisProgress], None]

# Numbers the model must never invent (§4.4.4 defence 3). Years and small
# ordinals are allowed through — "2027" in a claim usually comes from a cited
# regulatory deadline, and the entailment check is the right tool for that.
_NUMERIC_CLAIM_RE = re.compile(
    r"(\d+\s*(?:%|percent|per cent))"
    r"|([€$£]\s*\d)"
    r"|(\d+(?:[.,]\d+)?\s*(?:bn|billion|m\b|million|k\b|thousand))"
    r"|(\d+(?:[.,]\d+)?\s*x\b)",
    re.I,
)


#: How a requested HORIZON maps onto the evidence that derives it (§4.8).
#:
#: `derive_horizon` reads signal types, so a horizon constraint cannot be
#: imposed on a candidate — it can only be steered by choosing which clusters to
#: reason over and telling the model what kind of evidence to look for. These
#: are the signal types each derivation test actually reads, in the order the
#: tests are applied in `radar.scoring.derive_horizon`.
HORIZON_EVIDENCE: dict[str, tuple[str, ...]] = {
    "now": ("buying_signal", "proof_signal"),
    "next": ("regulation", "proof_signal"),
    # `trend` is deliberately absent: the LATER test reads technology-maturity
    # signals and nothing else, so ranking on `trend` would steer a Later run
    # toward clusters that cannot derive as Later.
    "later": ("technology_maturity",),
}

#: What to tell the model when a horizon is requested. Phrased as the question
#: the derivation test asks, so the model looks for evidence that would actually
#: pass it rather than asserting a horizon it has no power to set.
HORIZON_GUIDANCE: dict[str, str] = {
    "now": "NOW — the buying window is open. Prefer candidates whose evidence includes "
           "budgeted procurement, live tenders, or an adopted legal instrument alongside "
           "published deployment.",
    "next": "NEXT — the buying window is forming. Prefer candidates resting on regulation "
            "adopted or proposed but not yet applicable, or on published pilots with no "
            "volume procurement behind them yet.",
    "later": "LATER — the buying window is not open. Prefer candidates resting on standards "
             "work, research and technology-maturity evidence, with no product-grade offer "
             "visible in the market yet.",
}


@dataclass(frozen=True)
class GenerationConstraints:
    """Operator-supplied bounds on one synthesis run (the Generate screen).

    The three kinds of constraint are NOT equally enforceable, and conflating
    them would be the dishonest part:

    * `verticals` and `domains` are taxonomy fields the model emits directly, so
      they are ENFORCED in `_validate` — a candidate outside them is dropped and
      counted, exactly like a closed-vocabulary miss (§4.4.4 defence 2). The
      prompt asks as well, but the prompt is not the guarantee.
    * `geographies` are enforced under the same rule the read model filters by:
      a candidate carrying no geography is global, not excluded (`_matches` in
      radar.readmodel). Anything else would make the "spaces that already match"
      count on the Generate screen mean something different from what the run
      produces.
    * `horizons` CANNOT be enforced. §4.8 derives Now/Next/Later from the signal
      types attached to a topic, after scoring — "derived rather than judged,
      because derived classifications are explainable and consistent". So a
      horizon constraint selects clusters carrying that kind of evidence and
      tells the model what to look for; what the topics actually land on is
      reported afterwards rather than promised in advance.

    An empty instance is falsy and every constrained path degrades to the
    unconstrained one, so the pipeline behaves exactly as before when the
    Generate screen sets no filters.
    """

    verticals: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()
    geographies: tuple[str, ...] = ()
    horizons: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "GenerationConstraints":
        data = data or {}
        def clean(key: str) -> tuple[str, ...]:
            values = data.get(key) or ()
            return tuple(dict.fromkeys(str(v).strip() for v in values if str(v).strip()))
        return cls(verticals=clean("verticals"), domains=clean("domains"),
                   geographies=clean("geographies"), horizons=clean("horizons"))

    def __bool__(self) -> bool:
        return bool(self.verticals or self.domains or self.geographies or self.horizons)

    def as_dict(self) -> dict[str, list[str]]:
        return {"verticals": list(self.verticals), "domains": list(self.domains),
                "geographies": list(self.geographies), "horizons": list(self.horizons)}

    def allows(self, candidate: "Candidate") -> str | None:
        """The reason this candidate falls outside the constraints, or None.

        Returning the reason rather than a boolean is what lets the run report
        "12 candidates were dropped because they were outside Manufacturing"
        instead of a silent shortfall — §4.12's rule that what was not produced
        is logged, never dropped without a trace.
        """
        if self.verticals and candidate.vertical not in self.verticals:
            return f"vertical {candidate.vertical!r} outside the requested {list(self.verticals)}"
        if self.domains and not (set(candidate.domains) & set(self.domains)):
            return f"domains {candidate.domains} outside the requested {list(self.domains)}"
        if self.geographies and candidate.geographies:
            # Empty is global and therefore in scope — the same rule the radar
            # view filters by, so the two counts stay comparable.
            if not (set(candidate.geographies) & set(self.geographies)):
                return f"geographies {candidate.geographies} outside the requested {list(self.geographies)}"
        return None


@dataclass
class Candidate:
    vertical: str
    use_case: str
    technology: str
    statement: str
    domains: list[str] = field(default_factory=list)
    personas: list[str] = field(default_factory=list)
    geographies: list[str] = field(default_factory=list)
    why_hot: list[dict[str, Any]] = field(default_factory=list)
    why_specific: str = ""
    cluster_id: int | None = None
    critic_score: int | None = None
    critic_notes: str = ""
    rejection: str | None = None

    @property
    def triple(self) -> tuple[str, str, str]:
        return (self.vertical, self.use_case, self.technology)

    @property
    def signal_ids(self) -> list[str]:
        out: list[str] = []
        for claim in self.why_hot:
            out.extend(claim.get("signals", []))
        return sorted(set(out))


@dataclass
class SynthesisStats:
    clusters_processed: int = 0
    raw_candidates: int = 0
    failed_vocabulary: int = 0
    failed_specificity: int = 0
    failed_evidence: int = 0
    failed_critic: int = 0
    merged_duplicates: int = 0
    accepted: int = 0
    entailment_stripped: int = 0
    #: Candidates the model produced that fell outside the requested
    #: constraints. Counted separately from a vocabulary failure: the candidate
    #: was well-formed, it was simply not what was asked for.
    failed_constraints: int = 0
    #: Well-formed candidates that landed on a taxonomy cell the radar already
    #: holds. Kept and merged (DR-03), but they create nothing, so a request for
    #: five new spaces is not answered by five of these.
    duplicate_of_existing: int = 0
    #: Extra generation passes spent because every candidate from a cluster hit
    #: an occupied cell. NFR-10 makes inference cost a reported quantity, and
    #: this is the one loop that can spend more than the plan implies.
    duplicate_retries: int = 0
    rounds: int = 1
    rejections: list[dict[str, str]] = field(default_factory=list)
    #: DR-03 makes "updated" and "created" different events, and the Generate
    #: screen counts the second one: asking for five new spaces and receiving
    #: five refreshed old ones is not the same answer.
    created_ids: list[str] = field(default_factory=list)
    updated_ids: list[str] = field(default_factory=list)
    #: Which clusters this round consumed, so a later round can reason over
    #: evidence it has not already been through.
    processed_cluster_ids: list[int] = field(default_factory=list)

    _EXCLUDE_FROM_DICT = ("rejections", "processed_cluster_ids")

    #: Counters that are simply summed when several passes are reported as one
    #: run. Named rather than inferred from the type, because `rounds` is an int
    #: too and adding it would report a two-brief run as having gone round twice.
    _SUMMED = ("clusters_processed", "raw_candidates", "failed_vocabulary", "failed_specificity",
               "failed_evidence", "failed_critic", "merged_duplicates", "accepted",
               "entailment_stripped", "failed_constraints", "duplicate_of_existing",
               "duplicate_retries")

    def absorb(self, other: "SynthesisStats") -> "SynthesisStats":
        """Fold another pass into this one — for a run made of several briefs.

        The one subtlety is the created/updated split, and it is the same one
        `_persist` already guards inside a single pass: a second brief landing
        on the triple a first brief just created UPDATES the row, and its own
        stats object has no way to know that row is seconds old. Reported
        unadjusted, one space would arrive as "1 created and 1 refreshed", and
        the shortfall message would offer a DR-03 explanation for an event that
        never happened. So `created` wins wherever the two lists overlap.
        """
        for name in self._SUMMED:
            setattr(self, name, getattr(self, name) + getattr(other, name))
        self.rounds = max(self.rounds, other.rounds)
        self.rejections.extend(other.rejections)
        self.processed_cluster_ids.extend(other.processed_cluster_ids)
        for topic_id in other.created_ids:
            if topic_id not in self.created_ids:
                self.created_ids.append(topic_id)
        for topic_id in other.updated_ids:
            if topic_id not in self.updated_ids and topic_id not in self.created_ids:
                self.updated_ids.append(topic_id)
        self.updated_ids = [i for i in self.updated_ids if i not in self.created_ids]
        return self

    def as_dict(self) -> dict[str, Any]:
        data = {k: v for k, v in self.__dict__.items() if k not in self._EXCLUDE_FROM_DICT}
        data["rejections_sample"] = self.rejections[:20]
        data["clusters_consumed"] = len(self.processed_cluster_ids)
        return data


class Synthesiser:
    #: Model calls that never returned, and the last reason. A run whose passes
    #: all fail has not learned anything about the corpus, and must not report
    #: an evidence verdict — see `_generate`.
    llm_failures: int
    llm_successes: int
    last_llm_error: str | None

    def __init__(self, cfg: Config, db: Database, llm: LLMClient, embedder: Embedder | None = None,
                 constraints: GenerationConstraints | None = None):
        self.cfg = cfg
        self.db = db
        self.llm = llm
        self.embedder = embedder or Embedder()
        self.constraints = constraints or GenerationConstraints()
        self.llm_failures = 0
        self.llm_successes = 0
        self.last_llm_error: str | None = None
        self._fail_lock = threading.Lock()
        cur = cfg.settings["curation"]
        self.min_chars = int(cur["statement_min_chars"])
        self.max_chars = int(cur["statement_max_chars"])
        self.banned = {b.lower() for b in cur["banned_generic_statements"]}
        self.dup_threshold = float(cur["duplicate_similarity_threshold"])
        self.critic_min = int(cur["critic_min_score"])
        self.temperature = float(cfg.settings["llm"]["temperature_synthesis"])
        self.critic_temperature = float(cfg.settings["llm"]["temperature_critic"])

    # -- stage 5 -----------------------------------------------------------

    def run(self, refresh_id: str, max_clusters: int | None = None,
            run_critic: bool = True, run_entailment: bool = True,
            target_topics: int | None = None, max_rounds: int = 4,
            target_new: int | None = None,
            progress: "ProgressFn | None" = None,
            cancelled: "CancelFn | None" = None,
            tick: "TickFn | None" = None) -> SynthesisStats:
        """Synthesise candidates, optionally looping until a topic target is met.

        §4.4.3's coverage-driven prompting is what makes a target sensible
        rather than arbitrary: each round recomputes which taxonomy cells have
        evidence but no candidate yet, so a second round explores the grid
        rather than re-elaborating what the first round already produced.

        Two kinds of target are supported and they answer different questions.
        `target_topics` is the ABSOLUTE live topic count a refresh aims at.
        `target_new` — what the Generate screen asks for — is how many topics
        this run must CREATE, which under DR-03 is not the same thing: a round
        that refreshes eight existing spaces has moved the first target and not
        the second. When `target_new` is set, each round consumes clusters the
        previous rounds have not already been through, so a second round reasons
        over new evidence instead of re-reading the same fourteen signals.

        The loop stops on whichever comes first — the target, the round cap, a
        round that adds nothing, or cancellation. That third condition matters:
        without it, a target higher than the evidence can support would spin,
        and §4.1's whole posture is that an empty answer is a valid one.
        """
        overall = SynthesisStats()
        rounds = 0
        consumed: set[int] = set()
        while True:
            rounds += 1
            remaining = None if target_new is None else target_new - len(overall.created_ids)
            if progress:
                progress(f"synthesis round {rounds}"
                         + (f": {remaining} more space(s) to create" if remaining is not None else ""))
            # Cumulative, so the count the screen shows never goes backwards
            # when a round boundary is crossed.
            done_before = tuple(overall.created_ids)

            def emit(units_total: int, units_done: int,
                     round_created: list[str] | None = None, _round=rounds) -> None:
                if tick:
                    tick(SynthesisProgress(round=_round, units_total=units_total,
                                           units_done=units_done,
                                           created=done_before + tuple(round_created or ())))

            stats = self._run_once(refresh_id, max_clusters, run_critic, run_entailment,
                                   # Rotation belongs to the target_new path ONLY. The
                                   # absolute-target loop deliberately re-reads the same
                                   # clusters each round and relies on `_coverage_targets`
                                   # having moved; excluding what round 1 consumed would
                                   # leave round 2 with nothing and end the loop early.
                                   exclude_cluster_ids=consumed if target_new is not None else set(),
                                   target_new=remaining,
                                   progress=progress, cancelled=cancelled, tick=emit)
            for field_name in ("clusters_processed", "raw_candidates", "failed_vocabulary",
                              "failed_specificity", "failed_evidence", "failed_critic",
                              "failed_constraints", "duplicate_of_existing", "duplicate_retries",
                              "merged_duplicates", "accepted", "entailment_stripped"):
                setattr(overall, field_name,
                        getattr(overall, field_name) + getattr(stats, field_name))
            overall.rejections.extend(stats.rejections)
            overall.created_ids.extend(stats.created_ids)
            # `_persist` guards this within a round; across rounds the same
            # space can be created in round 1 and re-hit in round 2, and
            # reporting it as both created and DR-03-refreshed is the same
            # mis-count one level up.
            overall.updated_ids.extend(
                topic_id for topic_id in stats.updated_ids
                if topic_id not in set(overall.created_ids)
            )
            overall.processed_cluster_ids.extend(stats.processed_cluster_ids)
            if target_new is not None:
                consumed.update(stats.processed_cluster_ids)

            if cancelled and cancelled():
                log.info("synthesis cancelled after round %d", rounds)
                break

            if target_new is not None:
                created = len(overall.created_ids)
                log.info("round %d: %d new space(s) created (target %d)", rounds, created, target_new)
                if progress:
                    progress(f"round {rounds} created {stats.accepted} space(s) "
                             f"({created}/{target_new} new so far)")
                if created >= target_new:
                    break
                if rounds >= max_rounds:
                    log.warning("stopping at round cap %d with %d new space(s) — the evidence did "
                                "not support the target", max_rounds, created)
                    break
                if not stats.processed_cluster_ids:
                    # Deliberately NOT "this round accepted nothing", which is
                    # the stop condition the absolute-target path uses. Under a
                    # narrow constraint a batch of clusters legitimately yields
                    # nothing while the next batch yields three, and each round
                    # here reads evidence the last one did not. Running out of
                    # unread clusters is the real end; `max_rounds` bounds the
                    # rest.
                    log.warning("round %d found no unconsumed evidence in scope. Stopping at %d new "
                                "space(s) rather than manufacturing more.", rounds, created)
                    break
                continue

            if target_topics is None:
                break
            live = self.db.query_one(
                "SELECT COUNT(*) n FROM opportunity_spaces WHERE merged_into IS NULL"
            )["n"]
            log.info("round %d: %d topics live (target %d)", rounds, live, target_topics)
            if live >= target_topics:
                log.info("target reached after %d round(s)", rounds)
                break
            if rounds >= max_rounds:
                log.warning("stopping at round cap %d with %d topics — the evidence did not "
                            "support the target", max_rounds, live)
                break
            if stats.accepted == 0:
                log.warning("round %d added nothing; the evidenced grid is covered. Stopping at %d "
                            "topics rather than manufacturing more.", rounds, live)
                break
        overall.rounds = rounds
        return overall

    def _run_once(self, refresh_id: str, max_clusters: int | None = None,
                  run_critic: bool = True, run_entailment: bool = True,
                  exclude_cluster_ids: set[int] | None = None,
                  target_new: int | None = None,
                  progress: "ProgressFn | None" = None,
                  cancelled: "CancelFn | None" = None,
                  tick: "Callable[..., None] | None" = None) -> SynthesisStats:
        stats = SynthesisStats()
        clusters = self._cluster_ids(max_clusters, exclude_cluster_ids or set(), target_new)
        if clusters and tick:
            # Announce the round's evidence budget before reading any of it.
            # A round that found NOTHING deliberately stays silent: reporting
            # "0 of 0 clusters" would overwrite the last real position with a
            # reading that looks like a reset.
            tick(len(clusters), 0)
        if progress and (self.constraints.geographies or self.constraints.horizons):
            # Say how much evidence the scope left, because it is the usual
            # reason a run under-delivers and it is invisible otherwise. A
            # geography filter is strict on purpose — it requires a signal
            # actually tagged with the code, and roughly two signals in five
            # carry no geography at all — so "12 of 139 clusters" is the
            # difference between "the model refused" and "we handed it a
            # twelfth of the corpus".
            total = self.db.query_one("SELECT COUNT(*) n FROM clusters")["n"]
            progress(f"{len(clusters)} of {total} theme cluster(s) carry evidence inside the "
                     f"requested scope; this round reads them.")
        if not clusters:
            if exclude_cluster_ids:
                log.info("No unconsumed clusters left that match the constraints.")
            else:
                log.warning("No clusters present — run the `themes` stage first. Nothing to synthesise.")
            return stats

        target_cells = self._coverage_targets()

        # Clusters are independent until the deduplication step, and each one
        # spends most of its time waiting on the model (generation passes,
        # critic, entailment), so they are processed concurrently. Nothing is
        # written to the database until _persist below, so there is no write
        # contention to manage here — only the shared stats counters, which take
        # a lock.
        lock = threading.Lock()
        accepted: list[Candidate] = []
        # Cells that are spoken for: everything the radar already holds, plus
        # everything accepted so far in this batch. Shared under the lock so two
        # clusters running in parallel cannot both claim the same new cell and
        # then merge into one at persist time.
        taken = self._live_triples()
        # Frozen before the batch mutates `taken`, so "new" always means "not in
        # the radar when this round started" rather than drifting as cells are
        # claimed.
        already_live = frozenset(taken)
        scoped_taken = self._scoped_taken(taken)
        # Set once enough NEW cells are claimed. Counting accepted candidates
        # instead was the bug behind "it keeps giving me spaces that already
        # exist": three candidates that all land on occupied cells satisfied the
        # count, stopped the round, and created nothing.
        enough = threading.Event()
        # A round-level budget on retrying, on top of the per-cluster cap.
        # Without it a corpus whose every theme is already covered spends
        # DUPLICATE_RETRIES extra model passes on each of a hundred clusters to
        # discover, correctly, that there is nothing new — and NFR-10 makes that
        # cost a reported quantity rather than a surprise.
        retry_budget = [max(4, (target_new or 1) * 2)]

        def new_cells() -> int:
            """Distinct cells this batch would CREATE. Must be called under the lock."""
            return len({c.triple for c in accepted} - already_live)

        def process(cluster_id: int) -> None:
            if enough.is_set() or (cancelled and cancelled()):
                return
            payload = self._cluster_payload(cluster_id)
            if not payload["signals"]:
                return
            valid_ids = {s["id"] for s in payload["signals"]}
            survivors: list[Candidate] = []
            fresh = 0
            collided: list[str] = []

            # Attempt 0 is the ordinary pass. Each retry names the cells the last
            # attempt collided with, which is the shortest and most relevant
            # "do not propose these" list available — far better than shipping
            # four hundred occupied cells with every prompt.
            for attempt in range(1 + self.DUPLICATE_RETRIES):
                if enough.is_set() or (cancelled and cancelled()):
                    break
                with lock:
                    if attempt and retry_budget[0] <= 0:
                        break
                    if attempt:
                        retry_budget[0] -= 1
                    avoid = list(dict.fromkeys(collided + scoped_taken))[: self.AVOID_LIMIT]
                candidates = self._generate(payload, target_cells, avoid=avoid or None)
                with lock:
                    if attempt == 0:
                        stats.clusters_processed += 1
                        stats.processed_cluster_ids.append(cluster_id)
                    else:
                        stats.duplicate_retries += 1
                    stats.raw_candidates += len(candidates)

                for candidate in candidates:
                    candidate.cluster_id = cluster_id
                    with lock:
                        ok = self._validate(candidate, valid_ids, stats)
                    if not ok:
                        continue
                    if run_critic:
                        # The critic compares against neighbouring candidates, so
                        # it reads the shared accepted list — a snapshot is enough
                        # and avoids holding the lock across a model call.
                        with lock:
                            neighbours = list(accepted[-8:])
                        if not self._criticise(candidate, payload, neighbours, stats, lock):
                            continue
                    if run_entailment:
                        self._entailment_check(candidate, payload, stats, lock)
                        if not candidate.why_hot:
                            with lock:
                                stats.failed_evidence += 1
                                stats.rejections.append(
                                    {"statement": candidate.statement, "reason": "all claims failed entailment"}
                                )
                            continue
                    survivors.append(candidate)
                    with lock:
                        occupied = candidate.triple in taken
                        accepted.append(candidate)
                        if occupied:
                            # Kept, not dropped: DR-03 says the new evidence
                            # attaches to the space that already owns this cell,
                            # and that is worth having. It just is not what was
                            # asked for, so it does not count.
                            stats.duplicate_of_existing += 1
                            collided.append(self._format_cells([candidate.triple])[0])
                        else:
                            taken.add(candidate.triple)
                            fresh += 1
                        # Over-shoot deliberately: near-duplicate merging turns
                        # accepted candidates into fewer spaces, so stopping
                        # exactly on the number would undershoot.
                        # One spare, not two: `new_cells` already counts DISTINCT
                        # cells, so the DR-03 merge is accounted for and only the
                        # rarer near-duplicate merge across different cells can
                        # still shrink the result. Asking for one and reading
                        # until three exist was doing triple the work.
                        if target_new is not None and new_cells() >= target_new + 1:
                            enough.set()
                if fresh or not collided:
                    # Either it found something new, or it found nothing at all —
                    # and "nothing" means the evidence is exhausted, not that the
                    # model needs another go at the same cells.
                    break
                if progress:
                    progress(f"cluster {cluster_id}: attempt {attempt + 1} produced only cells that "
                             f"are already taken ({collided[-1]}) — asking again, excluding them")

            log.info("cluster %s → %d survived, %d on new cells", cluster_id, len(survivors), fresh)
            if progress:
                progress(f"cluster {cluster_id}: {len(survivors)} candidate(s) survived, "
                         f"{fresh} on cells the radar does not already have")
            if tick:
                # Reported from inside the pool, so the bar moves as each
                # cluster lands rather than once at the end of the round.
                with lock:
                    tick(len(clusters), stats.clusters_processed)

        workers = max(1, int(self.cfg.settings["llm"].get("max_parallel_clusters", 4)))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="cluster") as pool:
            list(pool.map(process, clusters))

        # Near-duplicate merge across the whole batch (§4.4.5).
        deduped = self._deduplicate(accepted, stats)
        self._persist(deduped, refresh_id, stats)
        stats.accepted = len(deduped)
        if tick:
            tick(len(clusters), stats.clusters_processed, stats.created_ids)
        return stats

    def _cluster_ids(self, max_clusters: int | None, exclude: set[int],
                     target_new: int | None = None) -> list[int]:
        """Which clusters to reason over, largest first, constraints applied.

        Read the current cluster set rather than this refresh's, so that stages
        can be run in separate invocations (`radar refresh --stages themes` then
        `--stages synthesise`) without silently finding nothing. The themes
        stage replaces the cluster table wholesale, so whatever is present is by
        definition the latest clustering.

        A geography or horizon constraint is applied HERE rather than only in
        the prompt, because the evidence a cluster contains is what the model
        can reason from: asking for Germany while handing it a cluster of French
        tenders produces either nothing or a fabrication, and §4.4.4's first
        defence is that the evidence block is the only factual material.
        """
        where: list[str] = []
        params: list[Any] = []
        order = ["c.size DESC"]

        if self.constraints.geographies:
            # geographies is a JSON array column; a LIKE on the quoted code is
            # exact enough for two-letter ISO codes and needs no json1.
            clauses = " OR ".join(["s.geographies LIKE ?"] * len(self.constraints.geographies))
            params_geo = [f'%"{code}"%' for code in self.constraints.geographies]
            where.append(f"EXISTS (SELECT 1 FROM signals s WHERE s.cluster_id = c.id AND ({clauses}))")
            params.extend(params_geo)

        if self.constraints.horizons:
            types = sorted({t for h in self.constraints.horizons for t in HORIZON_EVIDENCE.get(h, ())})
            if types:
                placeholders = ",".join("?" * len(types))
                # Ranked, not required: a cluster with no signal of the right
                # type is a poor bet for this horizon but not an impossible one,
                # and §4.8 derives the horizon from the topic's whole evidence
                # base, which enrichment widens after synthesis.
                order.insert(0, "affinity DESC")
                affinity = (f"(SELECT COUNT(*) FROM signals s WHERE s.cluster_id = c.id "
                            f"AND s.signal_type IN ({placeholders}))")
                params = types + params
            else:
                affinity = "0"
        else:
            affinity = "0"

        sql = (f"SELECT c.id AS id, {affinity} AS affinity FROM clusters c"
               + (f" WHERE {' AND '.join(where)}" if where else "")
               + f" ORDER BY {', '.join(order)}")
        rows = [r["id"] for r in self.db.query(sql, tuple(params)) if r["id"] not in exclude]

        if max_clusters:
            return rows[: int(max_clusters)]
        if target_new is not None:
            # A budget rather than a cap: each cluster yields a candidate or two
            # after curation, so reading a few times the requested number leaves
            # room for the critic to reject without forcing another round, while
            # keeping a five-space request off the whole corpus.
            return rows[: max(6, target_new * 4)]
        return rows

    # -- free text: one space from a written description ---------------------

    def run_from_brief(self, refresh_id: str, description: str,
                       run_critic: bool = True, run_entailment: bool = True,
                       progress: "ProgressFn | None" = None,
                       cancelled: "CancelFn | None" = None,
                       tick: "TickFn | None" = None) -> SynthesisStats:
        """Synthesise ONE space from a written description of the opportunity.

        The description is a SEARCH BRIEF, never evidence. §4.4.4's first and
        most effective defence is that the evidence block is the only factual
        material the model may use, and a sentence somebody typed is not
        evidence — it is a statement of what they are looking for. So the brief
        is embedded, used to retrieve the closest corroborated signals in the
        corpus, and then discarded from the factual role: the retrieved signals
        become the evidence block and every claim must still cite them.

        That distinction is the whole design of this path. It means the honest
        outcome "the corpus carries nothing close to what you described" is
        reachable — and it is the correct answer far more often than a model
        asked to elaborate on a prompt would ever admit.

        Everything downstream is the ordinary path: closed vocabulary,
        specificity, evidence binding, the critic, the entailment check, and the
        DR-03 identity rule on persistence.
        """
        stats = SynthesisStats()
        brief = " ".join(description.split())
        payload = self.brief_payload(brief)
        passes = max(1, int(self.cfg.settings["curation"].get("candidates_per_cluster", 1)))
        if tick:
            tick(SynthesisProgress(round=1, units_total=passes + 1, units_done=1,
                                   unit_label="generation pass"))
        if not payload["signals"]:
            if progress:
                progress(
                    "No signal in the corpus is close enough to that description to serve as "
                    "evidence for it. Nothing was generated — a claim with nothing behind it is "
                    "exactly what this pipeline exists not to produce."
                )
            return stats
        if progress:
            best = payload["similarities"][0]
            progress(f"{len(payload['signals'])} signal(s) retrieved as evidence for the brief "
                     f"(closest {best:.2f} cosine, floor {self.brief_floor:.2f}).")

        candidates = self._generate(payload, target_cells=[], brief=brief)
        stats.raw_candidates = len(candidates)
        stats.clusters_processed = 1
        if tick:
            tick(SynthesisProgress(round=1, units_total=passes + 1, units_done=passes,
                                   unit_label="generation pass"))
        if progress:
            progress(f"{len(candidates)} candidate(s) produced from the retrieved evidence.")

        valid_ids = {sig["id"] for sig in payload["signals"]}
        survivors: list[Candidate] = []
        for candidate in candidates:
            if cancelled and cancelled():
                break
            if not self._validate(candidate, valid_ids, stats):
                continue
            if run_critic and not self._criticise(candidate, payload, survivors, stats):
                continue
            if run_entailment:
                self._entailment_check(candidate, payload, stats)
                if not candidate.why_hot:
                    stats.failed_evidence += 1
                    stats.rejections.append({"statement": candidate.statement,
                                             "reason": "all claims failed entailment"})
                    continue
            survivors.append(candidate)

        # One space, not several: the request was for one. The survivors are
        # ranked by the critic's own score, so what persists is the best reading
        # of the brief the evidence supports rather than the first one produced.
        survivors.sort(key=lambda c: (c.critic_score or 0), reverse=True)
        chosen = survivors[:1]
        self._persist(chosen, refresh_id, stats)
        stats.accepted = len(chosen)
        if tick:
            tick(SynthesisProgress(round=1, units_total=passes + 1, units_done=passes + 1,
                                   unit_label="generation pass", created=tuple(stats.created_ids)))
        return stats

    @property
    def brief_floor(self) -> float:
        """Similarity below which a retrieved signal is not evidence.

        Reuses the enrichment threshold rather than inventing a number: that
        stage asks the identical question — "is this signal about this text?" —
        against the identical embedding space, and it is already calibrated in
        config (NFR-11 keeps thresholds out of code).
        """
        return float(self.cfg.settings["enrichment"]["similarity_threshold"])

    def brief_payload(self, description: str, limit: int = 14,
                      min_signals: int = 3) -> dict[str, Any]:
        """Retrieve the evidence a written brief is closest to.

        The same retrieval the enrichment stage performs, pointed at a typed
        sentence instead of a stored statement. `min_signals` is the floor below
        which the answer is "nothing", not "here is one weak match": a candidate
        resting on a single loosely-related item is precisely the thin topic the
        critic exists to catch, and catching it here costs nothing.
        """
        rows = self.db.query(
            "SELECT id, title, extract, publisher, published_at, signal_type, tier, geographies, "
            "url, embedding FROM signals WHERE relevance > 0 AND embedding IS NOT NULL"
        )
        empty = {"cluster_id": "brief", "label": "written brief", "keyphrases": "[]",
                 "signals": [], "similarities": []}
        if not rows:
            log.warning("No embedded signals available — run the `themes` stage first.")
            return empty

        matrix = np.vstack([Embedder.from_blob(r["embedding"]) for r in rows]).astype(np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        vector = np.asarray(self.embedder.encode([description])[0], dtype=np.float32)
        vector = vector / (np.linalg.norm(vector) or 1.0)
        sims = (matrix / norms) @ vector

        order = [int(i) for i in np.argsort(-sims)[:limit] if float(sims[int(i)]) >= self.brief_floor]
        if len(order) < min_signals:
            log.info("Brief retrieved only %d signal(s) above %.2f — not enough to ground a space.",
                     len(order), self.brief_floor)
            return empty
        signals = []
        for index in order:
            row = dict(rows[index])
            row.pop("embedding", None)
            signals.append(row)
        return {"cluster_id": "brief", "label": "written brief", "keyphrases": "[]",
                "signals": signals, "similarities": [round(float(sims[i]), 3) for i in order]}

    def _cluster_payload(self, cluster_id: int) -> dict[str, Any]:
        cluster = self.db.query_one("SELECT * FROM clusters WHERE id = ?", (cluster_id,))
        signals = self.db.query(
            "SELECT id, title, extract, publisher, published_at, signal_type, tier, geographies, url "
            "FROM signals WHERE cluster_id = ? ORDER BY tier ASC, published_at DESC LIMIT 14",
            (cluster_id,),
        )
        return {
            "cluster_id": cluster_id,
            "label": cluster["label"] if cluster else "",
            "keyphrases": cluster["keyphrases"] if cluster else "[]",
            "signals": [dict(s) for s in signals],
        }

    def _coverage_targets(self) -> list[dict[str, str]]:
        """Grid cells with evidence but no candidate yet (§4.4.3).

        "This converts brainstorming from 'produce more ideas' into 'cover the
        evidenced grid', which terminates and is measurable."
        """
        existing = {
            (r["vertical"], r["use_case"], r["technology"])
            for r in self.db.query(
                "SELECT vertical, use_case, technology FROM opportunity_spaces WHERE merged_into IS NULL"
            )
        }
        wanted_verticals = set(self.constraints.verticals)
        wanted_domains = set(self.constraints.domains)
        targets: list[dict[str, str]] = []
        for use_case in self.cfg.use_cases:
            for domain_id in use_case.get("domains") or []:
                if wanted_domains and domain_id not in wanted_domains:
                    continue
                for vertical in self.cfg.verticals:
                    if wanted_verticals and vertical.id not in wanted_verticals:
                        continue
                    for tech_id in _technologies_for_domain(self.cfg, domain_id)[:2]:
                        cell = (vertical.id, use_case.id, tech_id)
                        if cell not in existing:
                            targets.append(
                                {"vertical": vertical.id, "use_case": use_case.id, "technology": tech_id}
                            )
        # A cell several competitors have already staked out is a better target
        # than one the grid merely permits, so those are moved to the front
        # rather than added: the list is a priority order, not a set.
        competitor_cells = self._competitor_targets(existing)
        if competitor_cells:
            keyed = {(t["vertical"], t["use_case"], t["technology"]): t for t in targets}
            for cell in competitor_cells:
                keyed.pop(cell, None)
            targets = [
                {"vertical": v, "use_case": u, "technology": t} for v, u, t in competitor_cells
            ] + list(keyed.values())
        return targets

    def _competitor_targets(self, existing: set[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
        """Cells where competitors are demonstrably active and the radar is not.

        This is the competitor profile acting as a SEED, which is the only role
        the tiering allows it. A vendor's own site is tier-4 evidence: it may not
        lift a score and it may not, on its own, justify a topic. What it can do
        is say where to look — and "three named competitors sell this technology
        into this vertical and we have no topic there" is a better reason to look
        than an empty cell in a grid that permits thousands of them.

        The candidate a competitor-seeded pass produces still has to bind to the
        cluster's own evidence, still faces the critic, and still scores on the
        corpus rather than on the fact that a competitor said something. If no
        independent evidence supports it, it does not survive — which is the
        correct outcome, and is why seeding here is safe.
        """
        try:
            rows = self.db.query(
                """SELECT competitor_id, verticals, use_cases, technologies
                   FROM competitor_profiles WHERE status = 'profiled'""")
        except Exception:                                   # pragma: no cover - table may predate
            return []
        counts: dict[tuple[str, str, str], set[str]] = {}
        for row in rows:
            verticals = unjs(row["verticals"], []) or []
            use_cases = unjs(row["use_cases"], []) or []
            technologies = unjs(row["technologies"], []) or []
            for vertical in verticals:
                for use_case in use_cases:
                    for technology in technologies:
                        cell = (vertical, use_case, technology)
                        if cell in existing:
                            continue
                        counts.setdefault(cell, set()).add(row["competitor_id"])
        if not counts:
            return []
        # Two competitors, not one. A single vendor tagging a cell is that
        # vendor's marketing; two independently is a pattern worth a pass.
        contested = {cell: who for cell, who in counts.items() if len(who) >= 2}
        ranked = sorted(contested.items(), key=lambda kv: -len(kv[1]))
        log.info("Competitor-seeded targets: %d cells contested by 2+ profiled competitors",
                 len(ranked))
        return [cell for cell, _ in ranked[: self.COMPETITOR_TARGET_LIMIT]]

    #: §4.4.3 warns that an open-ended brainstorming loop "tends to produce
    #: volume rather than coverage: the model elaborates around whatever it
    #: produced first". Passes are therefore given DIFFERENT EVIDENCE LENSES
    #: rather than just a different random seed — each pass is told which kind
    #: of signal to reason from, so the passes explore genuinely different parts
    #: of the same cluster instead of paraphrasing one another.
    GENERATION_LENSES = (
        "Reason primarily from the REGULATORY and compliance evidence in this cluster. "
        "What becomes non-optional, for whom, and by when?",
        "Reason primarily from the PROCUREMENT and buying evidence in this cluster. "
        "Who is already spending, on what, and what would they buy next?",
        "Reason primarily from the TECHNOLOGY MATURITY and deployment evidence in this "
        "cluster. What has just become deployable that was not before?",
        "Reason from the CROSS-VERTICAL angle: this cluster's evidence may be concentrated "
        "in one sector, but the same problem may be more acute in another. Say which.",
        # Competitor-move lens. The profiles cannot justify a topic — a vendor's
        # own site is tier-4 — but they are a legitimate place to LOOK, and
        # "several competitors have built for this and the evidence here
        # supports it" is a different and better-founded candidate than the same
        # cell reached by grid enumeration alone.
        "Reason from COMPETITIVE MOVEMENT. Some of the target cells below are places where "
        "two or more named competitors already sell. Ask what customer problem that movement "
        "implies, then check whether THIS cluster's evidence independently supports it. If the "
        "evidence does not support it, do not propose it — a competitor's marketing is not a "
        "market, and an unsupported candidate is rejected downstream anyway.",
    )

    #: Competitor-seeded cells promoted to the front of the target list. Capped
    #: because the cross-product of one profile's tags is large and mostly
    #: spurious: a competitor tagged with 6 verticals, 8 use cases and 6
    #: technologies implies 288 cells, almost none of which it actually sells.
    #: Requiring two independent competitors and then taking the top slice is
    #: what turns that cross-product back into a signal.
    COMPETITOR_TARGET_LIMIT = 24

    #: How many occupied cells to name in a prompt. The radar holds hundreds and
    #: the whole list would cost more input tokens per pass than the evidence it
    #: is meant to protect. What matters is naming the ones this cluster is
    #: actually about — which is why the retry below, whose list is exactly what
    #: the model just proposed, is the part that does the work.
    AVOID_LIMIT = 40

    #: Extra generation passes for ONE cluster when every candidate landed on a
    #: cell that already exists. Two, not more: if the evidence in a cluster
    #: supports one opportunity and the radar already has it, saying so beats
    #: manufacturing a worse one.
    DUPLICATE_RETRIES = 2

    def _live_triples(self) -> set[tuple[str, str, str]]:
        """Every taxonomy cell currently occupied (§4.4.5 canonical identity)."""
        return {
            (r["vertical"], r["use_case"], r["technology"])
            for r in self.db.query(
                "SELECT vertical, use_case, technology FROM opportunity_spaces "
                "WHERE merged_into IS NULL"
            )
        }

    def _format_cells(self, triples) -> list[str]:
        return [f"{v} x {u} x {t}" for v, u, t in triples]

    def _scoped_taken(self, taken: set[tuple[str, str, str]]) -> list[str]:
        """Occupied cells worth naming up front, narrowed by the request.

        With a vertical or domain selected the in-scope list is short and every
        entry is a cell the model is genuinely likely to propose. Unconstrained
        it is the whole radar, so nothing is sent and the retry does the work —
        a list of four hundred cells would cost more than the evidence block.
        """
        if not self.constraints.verticals and not self.constraints.domains:
            return []
        wanted_verticals = set(self.constraints.verticals)
        wanted_domains = set(self.constraints.domains)
        in_scope = []
        for triple in sorted(taken):
            vertical, use_case, _ = triple
            if wanted_verticals and vertical not in wanted_verticals:
                continue
            if wanted_domains:
                domains = set(self.cfg.use_cases[use_case].get("domains") or []) \
                    if use_case in self.cfg.use_cases else set()
                if not (domains & wanted_domains):
                    continue
            in_scope.append(triple)
        return self._format_cells(in_scope[: self.AVOID_LIMIT])

    def _constraint_block(self) -> list[str] | None:
        """The requested bounds, phrased for the model.

        Kept beside the validation that enforces them, so the two cannot drift:
        anything the prompt promises here is checked in `_validate`, and the one
        thing that is not checkable — the horizon — is asked for as a property
        of the EVIDENCE rather than as a label the model may assert.
        """
        if not self.constraints:
            return None
        lines: list[str] = []
        if self.constraints.verticals:
            labels = ", ".join(f"{v} ({self.cfg.verticals.label(v)})" for v in self.constraints.verticals)
            lines.append(f"- VERTICAL must be one of: {labels}. Any other vertical is discarded.")
        if self.constraints.domains:
            labels = ", ".join(f"{d} ({self.cfg.domains.label(d)})" for d in self.constraints.domains)
            lines.append(f"- DOMAINS must include at least one of: {labels}. Any other is discarded.")
        if self.constraints.geographies:
            codes = ", ".join(self.constraints.geographies)
            lines.append(f"- GEOGRAPHIES must include at least one of: {codes}. Leave the list empty "
                         f"only if the opportunity is genuinely not geography-specific.")
        for horizon in self.constraints.horizons:
            guidance = HORIZON_GUIDANCE.get(horizon)
            if guidance:
                lines.append(f"- {guidance}")
        return lines or None

    def _generate(self, payload: dict[str, Any], target_cells: list[dict[str, str]],
                  brief: str | None = None, avoid: list[str] | None = None) -> list[Candidate]:
        """Over-produce candidates for one cluster (§4.4.3).

        "It is cheaper to generate forty candidates and keep eight than to coax
        eight good ones out of a single careful pass." So the cluster is passed
        over `candidates_per_cluster` times at high temperature, each pass under
        a different evidence lens, and the pool is deduplicated and critiqued
        afterwards. Passes are independent, so they run concurrently.
        """
        system = prompts.synthesis_system_prompt(self.cfg)
        passes = max(1, int(self.cfg.settings["curation"].get("candidates_per_cluster", 1)))

        # The lens window is OFFSET PER CLUSTER, not fixed at zero.
        #
        # With `index % len(LENSES)` and three passes over four lenses, lenses 0,
        # 1 and 2 fired on every cluster and lens 3 fired on none — the
        # cross-vertical lens was unreachable for the whole life of the pipeline,
        # and every lens added after it would have been dead on arrival too.
        # Rotating the start by the cluster means each cluster still gets three
        # DIFFERENT lenses (which is what §4.4.3 asks for) while the corpus as a
        # whole gets all of them.
        offset = abs(hash(str(payload.get("cluster_id") or payload.get("label") or ""))) % len(
            self.GENERATION_LENSES)

        def one_pass(index: int) -> list[Candidate]:
            # No lens on a brief run. The lenses exist to stop several passes
            # over one cluster from paraphrasing each other (§4.4.3) — but a
            # written brief IS the steer, and telling the model to follow the
            # brief and to reason primarily from regulatory evidence is two
            # instructions pulling apart. The passes still diverge, through
            # temperature, which is what they were for.
            lens = (self.GENERATION_LENSES[(offset + index) % len(self.GENERATION_LENSES)]
                    if passes > 1 and not brief else None)
            user = prompts.synthesis_user_prompt(payload, target_cells, lens=lens,
                                                 constraints=self._constraint_block(), brief=brief,
                                                 avoid=avoid)
            try:
                data = self.llm.complete_json(
                    system, user, strong=True, temperature=self.temperature, max_tokens=4000
                )
            except Exception as exc:  # noqa: BLE001
                # A swallowed provider failure is indistinguishable from a
                # cluster that had nothing to say, and the two need completely
                # different answers. Left as a bare log line, an unreachable
                # model produced a run that read every cluster, created nothing,
                # and reported "the evidence in scope did not support more" —
                # blaming the corpus for a network fault, which is the most
                # misleading thing this pipeline can say. Counted here so the
                # run can tell the difference.
                log.warning("Synthesis pass %d failed for cluster %s: %s", index,
                            payload["cluster_id"], exc)
                with self._fail_lock:
                    self.llm_failures += 1
                    self.last_llm_error = f"{type(exc).__name__}: {exc}"
                return []
            with self._fail_lock:
                self.llm_successes += 1
            return self._parse(data)

        out: list[Candidate] = []
        if passes == 1:
            return one_pass(0)
        with ThreadPoolExecutor(max_workers=passes, thread_name_prefix="synth") as pool:
            for result in pool.map(one_pass, range(passes)):
                out.extend(result)
        return out

    @staticmethod
    def _parse(data: dict[str, Any]) -> list[Candidate]:
        out: list[Candidate] = []
        for entry in data.get("candidates", []) or []:
            if not isinstance(entry, dict):
                continue
            try:
                out.append(
                    Candidate(
                        vertical=str(entry.get("vertical", "")).strip(),
                        use_case=str(entry.get("use_case", "")).strip(),
                        technology=str(entry.get("technology", "")).strip(),
                        statement=str(entry.get("statement", "")).strip(),
                        domains=[str(d) for d in entry.get("domains") or []],
                        personas=[str(p) for p in entry.get("personas") or []],
                        geographies=[str(g).upper() for g in entry.get("geographies") or []],
                        why_hot=[c for c in entry.get("why_hot") or [] if isinstance(c, dict)],
                        why_specific=str(entry.get("why_specific", "")).strip(),
                    )
                )
            except (TypeError, ValueError):
                continue
        return out

    # -- stage 6a: validation ---------------------------------------------

    def _validate(self, candidate: Candidate, valid_signal_ids: set[str], stats: SynthesisStats) -> bool:
        """Closed vocabulary, specificity and evidence binding (§4.4.4)."""
        # 2. Closed-vocabulary output. One retry via synonym resolution, then drop.
        for field_name, vocab in (
            ("vertical", self.cfg.verticals),
            ("use_case", self.cfg.use_cases),
            ("technology", self.cfg.technologies),
        ):
            value = getattr(candidate, field_name)
            if value not in vocab:
                repaired = vocab.resolve(value)
                if repaired is None:
                    stats.failed_vocabulary += 1
                    stats.rejections.append(
                        {"statement": candidate.statement, "reason": f"invalid {field_name}: {value!r}"}
                    )
                    return False
                setattr(candidate, field_name, repaired)

        candidate.domains = [d for d in candidate.domains if d in self.cfg.domains]
        candidate.personas = [p for p in candidate.personas if p in self.cfg.personas]
        if not candidate.domains:
            # Route via the use case's declared domains rather than dropping the
            # candidate: the domain is derivable, so a missing one is a prompt
            # miss, not a substantive failure.
            candidate.domains = list(self.cfg.use_cases[candidate.use_case].get("domains") or [])

        # Requested bounds (the Generate screen). Checked after the vocabulary
        # repair, so a candidate whose vertical was a near-miss is judged on the
        # repaired value rather than on the model's spelling of it.
        if outside := self.constraints.allows(candidate):
            stats.failed_constraints += 1
            stats.rejections.append({"statement": candidate.statement, "reason": outside})
            return False

        # Specificity validation (§4.4 principle 4, FR-06). "A candidate that
        # does not resolve to exactly one vertical, one use case and one
        # technology fails validation."
        statement = candidate.statement.strip()
        if not (self.min_chars <= len(statement) <= self.max_chars):
            stats.failed_specificity += 1
            stats.rejections.append(
                {"statement": statement, "reason": f"statement length {len(statement)} outside "
                                                   f"[{self.min_chars},{self.max_chars}]"}
            )
            return False
        if statement.lower().strip(" .") in self.banned:
            stats.failed_specificity += 1
            stats.rejections.append({"statement": statement, "reason": "banned generic statement"})
            return False

        # 1. Evidence binding. Every claim must cite ids that exist IN THIS
        # CLUSTER. Uncited claims are stripped, not rewritten.
        kept: list[dict[str, Any]] = []
        for claim in candidate.why_hot:
            text = str(claim.get("claim", "")).strip()
            cited = [s for s in claim.get("signals", []) if s in valid_signal_ids]
            if text and cited:
                kept.append({"claim": text, "signals": cited})
        candidate.why_hot = kept
        if not candidate.why_hot:
            stats.failed_evidence += 1
            stats.rejections.append({"statement": statement, "reason": "no claim survived evidence binding"})
            return False
        return True

    def _criticise(self, candidate: Candidate, payload: dict[str, Any],
                   accepted: list[Candidate], stats: SynthesisStats,
                   lock: "threading.Lock | None" = None) -> bool:
        """Adversarial critique pass (§4.4.3)."""
        guard = lock or _NULL_LOCK
        neighbours = [c.statement for c in accepted[-8:]]
        system = prompts.critic_system_prompt(self.cfg)
        user = prompts.format_candidate_for_critic(
            candidate.__dict__, payload["signals"], neighbours
        )
        try:
            verdict = self.llm.complete_json(
                system, user, strong=True, temperature=self.critic_temperature, max_tokens=900
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("Critic pass failed, keeping candidate unjudged: %s", exc)
            return True

        score = int(verdict.get("score", 0) or 0)
        candidate.critic_score = score
        candidate.critic_notes = "; ".join(str(i) for i in verdict.get("issues", [])[:4])

        # Deterministic backstop for defence 3: the critic is asked about
        # invented numbers, but a regex is not subject to model judgement.
        for claim in candidate.why_hot:
            if _NUMERIC_CLAIM_RE.search(claim["claim"]):
                candidate.critic_notes = (candidate.critic_notes + "; quantitative claim in generated text").strip("; ")
                score = min(score, 2)
                candidate.critic_score = score

        if verdict.get("verdict") == "revise" and verdict.get("revised_statement"):
            revised = str(verdict["revised_statement"]).strip()
            if self.min_chars <= len(revised) <= self.max_chars:
                candidate.statement = revised

        if score < self.critic_min:
            with guard:
                stats.failed_critic += 1
                stats.rejections.append(
                    {"statement": candidate.statement, "reason": f"critic score {score} < {self.critic_min}"
                                                                 f" ({candidate.critic_notes})"}
                )
            return False
        return True

    def _entailment_check(self, candidate: Candidate, payload: dict[str, Any], stats: SynthesisStats,
                          lock: "threading.Lock | None" = None) -> None:
        """§4.4.4 defence 4 — verify each claim is entailed by its cited span."""
        by_id = {s["id"]: s for s in payload["signals"]}
        survivors: list[dict[str, Any]] = []
        for claim in candidate.why_hot:
            spans = [
                f"[{sid}] {by_id[sid]['title']} — {by_id[sid]['extract'][:400]}"
                for sid in claim["signals"] if sid in by_id
            ]
            if not spans:
                continue
            try:
                result = self.llm.complete_json(
                    prompts.entailment_prompt(),
                    f"CLAIM: {claim['claim']}\n\nEVIDENCE SPANS:\n" + "\n".join(spans),
                    temperature=0.0, max_tokens=200,
                )
            except Exception:  # noqa: BLE001 — a failed check must not delete evidence
                survivors.append(claim)
                continue
            if result.get("supported"):
                survivors.append(claim)
            else:
                with (lock or _NULL_LOCK):
                    stats.entailment_stripped += 1
        candidate.why_hot = survivors

    # -- stage 6b: identity, dedup, persistence ---------------------------

    def _deduplicate(self, candidates: list[Candidate], stats: SynthesisStats) -> list[Candidate]:
        """§4.4.5 — canonical identity is the triple; near-duplicates merge."""
        by_triple: dict[tuple[str, str, str], Candidate] = {}
        for candidate in candidates:
            existing = by_triple.get(candidate.triple)
            if existing is None:
                by_triple[candidate.triple] = candidate
                continue
            # Same triple = same topic. Merge evidence, keep the better statement.
            stats.merged_duplicates += 1
            existing.why_hot = _merge_claims(existing.why_hot, candidate.why_hot)
            existing.geographies = sorted(set(existing.geographies) | set(candidate.geographies))
            existing.personas = sorted(set(existing.personas) | set(candidate.personas))
            if (candidate.critic_score or 0) > (existing.critic_score or 0):
                existing.statement = candidate.statement
                existing.critic_score = candidate.critic_score

        survivors = list(by_triple.values())
        if len(survivors) < 2:
            return survivors

        # Near-duplicates with DIFFERENT triples, detected by embedding
        # similarity on the statement (§4.4.5). §4.4.5 asks for human review the
        # first time each merge rule fires — the merge is recorded as a
        # curator-reviewable event rather than applied silently.
        vectors = self.embedder.encode([c.statement for c in survivors])
        similarity = vectors @ vectors.T
        merged_away: set[int] = set()
        for i in range(len(survivors)):
            if i in merged_away:
                continue
            for j in range(i + 1, len(survivors)):
                if j in merged_away or similarity[i, j] < self.dup_threshold:
                    continue
                stats.merged_duplicates += 1
                survivors[i].why_hot = _merge_claims(survivors[i].why_hot, survivors[j].why_hot)
                survivors[i].critic_notes = (
                    f"{survivors[i].critic_notes}; merged near-duplicate "
                    f"'{survivors[j].statement}' (cos={similarity[i, j]:.3f}) — pending curator review"
                ).strip("; ")
                merged_away.add(j)
        return [c for idx, c in enumerate(survivors) if idx not in merged_away]

    def _persist(self, candidates: list[Candidate], refresh_id: str, stats: SynthesisStats) -> None:
        """DR-03: a topic that recurs is UPDATED, not recreated."""
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        today = now[:10]
        with self.db.cursor() as cur:
            for candidate in candidates:
                existing = cur.execute(
                    "SELECT id, version, why_hot FROM opportunity_spaces "
                    "WHERE vertical=? AND use_case=? AND technology=? AND merged_into IS NULL",
                    candidate.triple,
                ).fetchone()

                if existing:
                    # Refresh: new signals attach, score is recomputed later,
                    # previous score is retained in history (§4.4.5).
                    merged = _merge_claims(unjs(existing["why_hot"], []) or [], candidate.why_hot)
                    cur.execute(
                        """UPDATE opportunity_spaces
                           SET version = version + 1, statement = ?, why_hot = ?, last_refresh = ?,
                               critic_score = ?, critic_notes = ?, prompt_version = ?, model_version = ?
                           WHERE id = ?""",
                        (candidate.statement, js(merged), today, candidate.critic_score,
                         candidate.critic_notes, prompts.PROMPT_VERSION_SYNTHESIS,
                         self.llm.strong_model, existing["id"]),
                    )
                    topic_id = existing["id"]
                    # Deduplication is by statement embedding, not by taxonomy
                    # triple, so two survivors in one batch can share a triple:
                    # the first INSERTs and the second UPDATEs the row the first
                    # just created. Recording that as a refresh would report one
                    # space as "1 created and 1 refreshed" and hand the shortfall
                    # message a DR-03 explanation that never happened.
                    if topic_id not in stats.created_ids:
                        stats.updated_ids.append(topic_id)
                else:
                    topic_id = self._next_id(cur)
                    cur.execute(
                        """INSERT INTO opportunity_spaces
                           (id, version, vertical, use_case, technology, statement, domains, personas,
                            geographies, state, state_reason, state_changed_at, why_hot, critic_score,
                            critic_notes, first_seen, last_refresh, pipeline_version, prompt_version, model_version)
                           VALUES (?,1,?,?,?,?,?,?,?,'candidate','emitted by synthesis',?,?,?,?,?,?,?,?,?)""",
                        (topic_id, candidate.vertical, candidate.use_case, candidate.technology,
                         candidate.statement, js(candidate.domains), js(candidate.personas),
                         js(candidate.geographies), today, js(candidate.why_hot), candidate.critic_score,
                         candidate.critic_notes, today, today, self.cfg.pipeline_version,
                         prompts.PROMPT_VERSION_SYNTHESIS, self.llm.strong_model),
                    )
                    stats.created_ids.append(topic_id)

                for signal_id in candidate.signal_ids:
                    cur.execute(
                        "INSERT OR IGNORE INTO opportunity_signals "
                        "(opportunity_id, signal_id, attached_at, refresh_id) VALUES (?,?,?,?)",
                        (topic_id, signal_id, now, refresh_id),
                    )

    @staticmethod
    def _next_id(cur) -> str:
        row = cur.execute(
            "SELECT id FROM opportunity_spaces WHERE id LIKE 'OS%' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            return "OS001"
        try:
            return f"OS{int(row['id'][2:]) + 1:03d}"
        except ValueError:
            return f"OS{dt.datetime.now().strftime('%H%M%S')}"


def _merge_claims(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Union claims by text, unioning their cited signal ids."""
    merged: dict[str, set[str]] = {}
    order: list[str] = []
    for claim in list(a) + list(b):
        text = str(claim.get("claim", "")).strip()
        if not text:
            continue
        if text not in merged:
            merged[text] = set()
            order.append(text)
        merged[text].update(claim.get("signals", []))
    return [{"claim": text, "signals": sorted(merged[text])} for text in order]


def _technologies_for_domain(cfg: Config, domain_id: str) -> list[str]:
    """Technologies plausibly serving a domain, for coverage targeting."""
    out = []
    for offer in cfg.offers.get("offers", []):
        if domain_id in (offer.get("domains") or []):
            out.extend(offer.get("technologies") or [])
    for partner in cfg.assets.get("partners", []):
        if domain_id in (partner.get("domains") or []):
            out.extend(partner.get("provides_technologies") or [])
    seen: list[str] = []
    for tech in out:
        if tech not in seen and tech in cfg.technologies:
            seen.append(tech)
    return seen
