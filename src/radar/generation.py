"""On-demand, constrained generation of opportunity spaces (the Generate screen).

`radar refresh` runs the whole seven-stage pipeline on a cadence (FR-19). This
module runs the SYNTHESIS half of it on request, for a stated number of spaces,
optionally bounded to a slice of the taxonomy — "give me five more in
manufacturing, in France and Germany" — and reports what it did well enough that
the answer is inspectable rather than magic.

Three design points are worth stating, because each is a place where the
convenient thing would have been wrong:

1.  IT DOES NOT COLLECT. Collection, classification and clustering are the
    cadence's job and they are slow and network-bound. This runs over the
    clusters that already exist, which is also what makes the run bounded: the
    evidence is fixed, so "the evidence does not support five more" is a real
    and reachable answer (§4.1 — an empty answer is a valid one).

2.  IT SCOPES THE DOWNSTREAM STAGES TO WHAT IT CREATED. A new space needs
    enrichment, links, scores, an action, a size and a competitive read before
    it is worth showing. Running those across the whole radar to serve five new
    spaces would cost hundreds of model calls, so each stage is given the new
    topic ids. Scoring is the exception that proves the rule: it normalises
    against the whole corpus and only WRITES the subset (see ScoringEngine.run).

3.  IT IS ONE AT A TIME. Synthesis writes opportunity spaces and the DR-03
    identity rule is enforced by a unique index on the taxonomy triple; two
    concurrent runs would race on it. A second request is refused with the id of
    the run already in flight rather than queued silently.

The run happens on a background thread and is polled, because it takes minutes
and an HTTP request that takes minutes is a request that dies to a proxy
timeout with the work half-done and no way to find out what happened.
"""

from __future__ import annotations

import datetime as dt
import logging
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from .competition import CompetitionAnalyser
from .config import Config
from .db import Database, js
from .embeddings import Embedder
from .graph import Linker
from .llm import LLMClient
from .pipeline.actions import NextActionGenerator
from .pipeline.enrich import Enricher
from .pipeline.synthesis import (GenerationConstraints, SynthesisProgress, SynthesisStats,
                                Synthesiser)
from .scoring import ScoringEngine
from .sizing import MarketSizer

log = logging.getLogger(__name__)

#: A ceiling on one request. Not a technical limit — a governance one: each
#: space costs several model calls to synthesise and several more to finish, and
#: an unbounded box on a screen is how someone types 500 and finds out what
#: NFR-10 was measuring.
MAX_PER_RUN = 25

#: How much of the progress bar synthesis owns. It is the only model-bound
#: stage that loops, and on a real run it is the overwhelming majority of the
#: wall clock; giving the six finishing stages an equal seventh each would park
#: the bar at 1/7 for minutes and then sprint.
_SYNTHESIS_SHARE = 0.72

#: The most of the synthesis segment that reading evidence alone may fill.
#: Below 1 on purpose — see GenerationJob.progress.
_EVIDENCE_CEILING = 0.85

#: A written brief has to say enough to retrieve evidence with. Below this it
#: matches half the corpus equally badly; above it, it is a document, not a
#: description, and the embedding stops being about any one thing.
MIN_BRIEF_CHARS = 40
MAX_BRIEF_CHARS = 600

#: How many briefs one run may answer. The scoping conversation caps itself
#: lower still (prompts.MAX_BRIEFS_PER_CHAT); this is the API's own bound, and
#: it exists because each brief is a full synthesis pass with its own model
#: calls — a list is not a cheaper way to ask for twenty spaces.
MAX_BRIEFS_PER_RUN = 5

#: Runs kept for inspection after they finish. The screen shows the last few so
#: a reload does not lose the record of what was just generated.
HISTORY_LIMIT = 20

#: The stages a generated space passes through after synthesis, in order, with
#: the label the screen shows. `describe` is deliberately NOT here: a long-form
#: description is one more model call per space, the detail pane already
#: generates it on demand (FR-14), and making it part of every run would double
#: the cost of the cheap case to serve the occasional one.
STAGE_LABELS: tuple[tuple[str, str], ...] = (
    ("synthesise", "Synthesising candidates"),
    ("enrich", "Attaching corroborating evidence"),
    ("link", "Linking to the Orange Business Graph"),
    ("score", "Scoring attractiveness and right to win"),
    ("actions", "Writing the next action per role"),
    ("size", "Sizing the market"),
    ("competition", "Reading the competitive field"),
)


@dataclass
class GenerationJob:
    """One run, its progress, and everything it is prepared to say about itself."""

    id: str
    requested: int
    constraints: GenerationConstraints
    #: `grid` covers the evidenced taxonomy grid, bounded by the constraints.
    #: `brief` answers one written description. They differ in what steers the
    #: model, not in what validates it — both go through the same curation.
    kind: str = "grid"
    #: The written briefs a `brief` run answers, one space attempted per brief.
    #: A list rather than a string because the scoping conversation can land on
    #: several genuinely distinct taxonomy triples in one sitting, and running
    #: them separately would mean three trips through the single-run guard.
    briefs: list[str] = field(default_factory=list)
    status: str = "queued"          # queued | running | done | error | cancelled
    stage: str | None = None
    stages_done: list[str] = field(default_factory=list)
    started_at: str = ""
    finished_at: str | None = None
    refresh_id: str | None = None
    created_ids: list[str] = field(default_factory=list)
    updated_ids: list[str] = field(default_factory=list)
    error: str | None = None
    log: list[dict[str, str]] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    #: Live synthesis position, so the screen can count spaces as they land
    #: rather than only when the whole stage returns.
    round: int = 0
    units_total: int = 0
    units_done: int = 0
    unit_label: str = "theme cluster"
    _cancel: threading.Event = field(default_factory=threading.Event, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # -- progress reporting -------------------------------------------------

    def say(self, message: str) -> None:
        stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        with self._lock:
            self.log.append({"at": stamp, "message": message})
            # A synthesis round over a hundred clusters is chatty. The tail is
            # what anyone reads, and an unbounded list on a long run is a slow
            # memory leak in a process that is meant to stay up.
            if len(self.log) > 400:
                del self.log[:-300]
        log.info("[%s] %s", self.id, message)

    def cancel(self) -> None:
        self._cancel.set()
        self.say("Cancellation requested — the run stops after the work in flight.")

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def observe(self, progress: SynthesisProgress) -> None:
        """Take a synthesis position. Called from the cluster pool, so it locks."""
        with self._lock:
            self.round = progress.round
            self.units_total = progress.units_total
            self.units_done = progress.units_done
            self.unit_label = progress.unit_label
            # Assigned rather than extended: the tick carries the cumulative
            # list, so a replayed or out-of-order tick cannot double-count.
            if len(progress.created) >= len(self.created_ids):
                self.created_ids = list(progress.created)

    @property
    def progress(self) -> float:
        """How far along, in 0..1, without claiming more than is true.

        Synthesis owns the first `_SYNTHESIS_SHARE` of the bar because it is the
        long pole — the six finishing stages together are a fraction of one
        model-bound round. Inside it, the fraction is the larger of two honest
        readings: spaces created against spaces asked for, and evidence read
        against the evidence budget for this round. The second is CAPPED below
        1, because reading every cluster is not the same as producing anything,
        and a bar that reached the end on evidence alone would promise a result
        the run may not have.
        """
        if self.status in ("done", "error", "cancelled"):
            return 1.0
        finishing = [key for key, _ in STAGE_LABELS if key != "synthesise"]
        completed = sum(1 for key in finishing if key in self.stages_done)
        if "synthesise" not in self.stages_done:
            by_created = len(self.created_ids) / self.requested if self.requested else 0.0
            by_evidence = (self.units_done / self.units_total) if self.units_total else 0.0
            inner = max(min(1.0, by_created), min(_EVIDENCE_CEILING, by_evidence))
            return round(_SYNTHESIS_SHARE * inner, 4)
        return round(_SYNTHESIS_SHARE + (1 - _SYNTHESIS_SHARE) * (completed / len(finishing)), 4)

    def as_dict(self) -> dict[str, Any]:
        with self._lock:
            tail = list(self.log[-80:])
        return {
            "id": self.id,
            "progress": self.progress,
            "round": self.round,
            "kind": self.kind,
            # `brief` stays singular for the one-brief case the screen has
            # always shown; `briefs` is the truth. A run answering three of them
            # has no single brief to name, and naming the first would read as if
            # the other two were not asked for.
            "brief": self.briefs[0] if len(self.briefs) == 1 else None,
            "briefs": list(self.briefs),
            "units_total": self.units_total,
            "units_done": self.units_done,
            "unit_label": self.unit_label,
            "requested": self.requested,
            "constraints": self.constraints.as_dict(),
            "constrained": bool(self.constraints),
            "min_brief_chars": MIN_BRIEF_CHARS,
            "max_brief_chars": MAX_BRIEF_CHARS,
            "status": self.status,
            "stage": self.stage,
            "stage_label": dict(STAGE_LABELS).get(self.stage or "", self.stage),
            "stages": [{"id": key, "label": label, "done": key in self.stages_done}
                       for key, label in STAGE_LABELS],
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "refresh_id": self.refresh_id,
            "created": len(self.created_ids),
            "created_ids": self.created_ids,
            "updated": len(self.updated_ids),
            "updated_ids": self.updated_ids,
            "error": self.error,
            "log": tail,
            "stats": self.stats,
        }


class GenerationService:
    """Owns the single in-flight run and the recent history of finished ones."""

    def __init__(self, cfg: Config, db: Database, embedder: Embedder | None = None):
        self.cfg = cfg
        self.db = db
        self._embedder = embedder
        self._jobs: dict[str, GenerationJob] = {}
        self._order: list[str] = []
        self._active: str | None = None
        self._lock = threading.Lock()

    # -- embedder ------------------------------------------------------------

    def embedder(self) -> Embedder:
        """Loaded on first use and then kept.

        The sentence-transformer model takes seconds to load and several hundred
        megabytes to hold. Building it at import would pay that on every API
        process whether or not anyone ever generates anything.

        Public because the scoping conversation (`radar.scoping`) retrieves
        against the same stored vectors on every turn, and a second copy of the
        model in the same process is several hundred megabytes bought to compute
        the identical numbers.
        """
        if self._embedder is None:
            self._embedder = Embedder()
        return self._embedder

    # -- read side -----------------------------------------------------------

    def active(self) -> GenerationJob | None:
        with self._lock:
            return self._jobs.get(self._active) if self._active else None

    def get(self, job_id: str) -> GenerationJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def recent(self, limit: int = 10) -> list[GenerationJob]:
        with self._lock:
            ids = list(reversed(self._order))[:limit]
            return [self._jobs[i] for i in ids if i in self._jobs]

    @staticmethod
    def encoder_reason() -> str | None:
        """Why this process cannot generate, if it cannot. None when it can.

        The serving deployment ships WITHOUT the sentence-transformer encoder on
        purpose: it pulls torch, and requirements-azure.txt calls that "the
        difference between a 150 MB deployment and a 2.5 GB one, and on the Free
        tier the difference between starting and not". `radar.api` never needed
        it, because the read path never embeds anything.

        Generation does. Synthesis deduplicates candidates by statement
        similarity (§4.4.5) and the free-text path retrieves evidence by
        embedding a brief against the stored signal vectors. Those vectors are
        384-dimensional and were produced by that model, so the TF-IDF fallback
        is not a substitute for the second job at any quality — its output has a
        different width and cannot be compared against them at all.

        `find_spec` rather than an import: this is called on every poll of the
        Generate screen, and importing the package would load torch.
        """
        import importlib.util
        if importlib.util.find_spec("sentence_transformers") is not None:
            return None
        return (
            "This deployment serves the radar but cannot generate. Synthesis needs the "
            "sentence-transformer encoder — to deduplicate candidates, and to retrieve the "
            "evidence behind a written brief — and the serving package ships without it "
            "deliberately, because it pulls torch and would not fit the plan this runs on. "
            "The stored signal embeddings came from that model, so no substitute encoder can "
            "be compared against them. Generation is a batch step: run it locally "
            "(`radar refresh`, or this screen against a local server) and redeploy — the "
            "deployed app serves what the pipeline produced."
        )

    def readiness(self) -> dict[str, Any]:
        """Whether a run could succeed right now, and if not, why not.

        Two ways it cannot. Synthesis reads clusters, and a database that has
        been initialised but never refreshed has none — the failure mode without
        that check is a run that starts, does nothing and reports zero, which is
        indistinguishable from "the evidence does not support it" and is a
        completely different message. And the serving deployment has no encoder;
        see `encoder_reason`.
        """
        clusters = self.db.query_one("SELECT COUNT(*) n FROM clusters")["n"]
        signals = self.db.query_one("SELECT COUNT(*) n FROM signals WHERE cluster_id IS NOT NULL")["n"]
        active = self.active()
        reason = self.encoder_reason() or (
            None if clusters > 0 else
            "No theme clusters exist yet, so there is no evidence to synthesise from. "
            "Run a refresh (`radar refresh`) first — generation reasons over the corpus "
            "the pipeline has already collected and clustered."
        )
        return {
            "clusters": clusters,
            "clustered_signals": signals,
            "ready": reason is None,
            "reason": reason,
            "max_per_run": MAX_PER_RUN,
            "busy": active.id if active and active.status in ("queued", "running") else None,
        }

    # -- write side ----------------------------------------------------------

    def start_from_brief(self, description: str, run_critic: bool = True,
                         run_entailment: bool = True) -> GenerationJob:
        """One space from a written description of the opportunity."""
        return self.start_from_briefs([description], run_critic=run_critic,
                                      run_entailment=run_entailment)

    def start_from_briefs(self, descriptions: list[str], run_critic: bool = True,
                          run_entailment: bool = True) -> GenerationJob:
        """One space per written brief, in a single run.

        Shares the single-run guard, the stage chain and the reporting with the
        grid path — the only thing that differs is what steers the model. Each
        description is a search brief, never evidence: it retrieves the closest
        corroborated signals in the corpus and those become the evidence block
        (see Synthesiser.run_from_brief).

        Several briefs are one run rather than several because synthesis holds
        the only write lock on the taxonomy triple: three separate requests would
        mean two 409s and a queue somebody has to babysit. They are still three
        independent passes — a brief the corpus cannot answer creates nothing and
        says so, and the two beside it are unaffected.
        """
        briefs: list[str] = []
        for description in (descriptions or []):
            brief = " ".join((description or "").split())
            if len(brief) < MIN_BRIEF_CHARS:
                raise ValueError(
                    f"Describe the opportunity in at least {MIN_BRIEF_CHARS} characters. A few "
                    f"words cannot retrieve evidence specific enough to build a space on — name "
                    f"the sector, who has the problem, and what would be deployed."
                )
            if len(brief) > MAX_BRIEF_CHARS:
                raise ValueError(f"Keep each description under {MAX_BRIEF_CHARS} characters.")
            # Two identical briefs are one pass, not two: they would retrieve the
            # same evidence, land on the same triple, and the second would be
            # reported as a DR-03 refresh of the space the first had just made.
            if brief not in briefs:
                briefs.append(brief)
        if not briefs:
            raise ValueError("No brief was given to generate from.")
        if len(briefs) > MAX_BRIEFS_PER_RUN:
            raise ValueError(
                f"One run answers at most {MAX_BRIEFS_PER_RUN} briefs; {len(briefs)} were given. "
                f"Each is a full synthesis pass with its own model calls."
            )
        return self._enqueue(GenerationJob(
            id=self._next_id(),
            requested=len(briefs),
            constraints=GenerationConstraints(),
            kind="brief",
            briefs=briefs,
            started_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        ), run_critic, run_entailment)

    def start(self, count: int, constraints: GenerationConstraints,
              run_critic: bool = True, run_entailment: bool = True) -> GenerationJob:
        if count < 1 or count > MAX_PER_RUN:
            raise ValueError(f"Ask for between 1 and {MAX_PER_RUN} spaces; {count} was requested.")
        self._validate_constraints(constraints)
        return self._enqueue(GenerationJob(
            id=self._next_id(),
            requested=count,
            constraints=constraints,
            started_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        ), run_critic, run_entailment)

    @staticmethod
    def _next_id() -> str:
        return f"G-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"

    def _enqueue(self, job: GenerationJob, run_critic: bool, run_entailment: bool) -> GenerationJob:
        # Refused here, not three stages in. A deployment that cannot generate
        # at all should say so on the request rather than accept it, spend model
        # calls, and fail at the deduplication step with an import error.
        if (reason := self.encoder_reason()) is not None:
            raise ValueError(reason)
        with self._lock:
            current = self._jobs.get(self._active) if self._active else None
            if current and current.status in ("queued", "running"):
                raise RuntimeError(
                    f"Generation run {current.id} is already in flight. Synthesis writes opportunity "
                    f"spaces and the identity rule (DR-03) is enforced by a unique index on the "
                    f"taxonomy triple, so two runs cannot proceed at once."
                )
            self._jobs[job.id] = job
            self._order.append(job.id)
            self._active = job.id
            for stale in self._order[:-HISTORY_LIMIT]:
                self._jobs.pop(stale, None)
            del self._order[:-HISTORY_LIMIT]

        thread = threading.Thread(
            target=self._run, args=(job, run_critic, run_entailment),
            name=f"generate-{job.id}", daemon=True,
        )
        thread.start()
        return job

    def _validate_constraints(self, constraints: GenerationConstraints) -> None:
        """Closed vocabularies apply to the REQUEST too (§3.3).

        A typo'd vertical would otherwise produce a run that reads the whole
        corpus, rejects every candidate for being outside a vertical that does
        not exist, and reports an evidence shortfall.
        """
        unknown = [v for v in constraints.verticals if v not in self.cfg.verticals]
        if unknown:
            raise ValueError(f"Unknown vertical(s): {unknown}. Known: {self.cfg.verticals.ids}")
        unknown = [d for d in constraints.domains if d not in self.cfg.domains]
        if unknown:
            raise ValueError(f"Unknown domain(s): {unknown}. Known: {self.cfg.domains.ids}")
        unknown = [h for h in constraints.horizons if h not in ("now", "next", "later")]
        if unknown:
            raise ValueError(f"Unknown horizon(s): {unknown}. Known: ['now', 'next', 'later']")

    # -- the run itself ------------------------------------------------------

    def _run(self, job: GenerationJob, run_critic: bool, run_entailment: bool) -> None:
        reference_date = dt.date.today()
        try:
            ready = self.readiness()
            if not ready["ready"]:
                raise RuntimeError(ready["reason"])

            job.status = "running"
            llm = LLMClient(max_retries=self.cfg.settings["llm"]["max_retries"])
            job.refresh_id = self._open_refresh(job, reference_date)
            if job.kind == "brief":
                job.say(f"Run {job.id} started from {len(job.briefs)} written brief(s).")
                for index, brief in enumerate(job.briefs, 1):
                    job.say(f"Brief {index}: “{brief}”")
                job.say("A brief is a search request, not evidence. It retrieves the closest "
                        "corroborated signals in the corpus, and those become the only facts the "
                        "model may use (§4.4.4).")
            else:
                job.say(
                    f"Run {job.id} started: {job.requested} space(s) requested"
                    + (f", bounded to {job.constraints.as_dict()}" if job.constraints
                       else ", unconstrained (the whole evidenced grid is in scope)")
                )
                job.say(f"Reasoning over {ready['clusters']} theme cluster(s) "
                        f"covering {ready['clustered_signals']} classified signal(s).")

            # -- stage 1: synthesis, the only creative step ------------------
            job.stage = "synthesise"
            synth = Synthesiser(self.cfg, self.db, llm, self.embedder(),
                                constraints=job.constraints)
            if job.kind == "brief":
                stats = self._run_briefs(job, synth, run_critic, run_entailment)
            else:
                stats = synth.run(
                    job.refresh_id, run_critic=run_critic, run_entailment=run_entailment,
                    target_new=job.requested, progress=job.say, cancelled=lambda: job.cancelled,
                    tick=job.observe,
                )
            job.created_ids = list(stats.created_ids)
            job.updated_ids = list(dict.fromkeys(stats.updated_ids))
            job.stats["synthesis"] = stats.as_dict()
            self._report_provider(job, synth)
            job.stages_done.append("synthesise")
            job.say(
                f"Synthesis finished after {stats.rounds} round(s): {len(job.created_ids)} new space(s), "
                f"{len(job.updated_ids)} existing space(s) refreshed with new evidence."
            )
            self._report_shortfall(job, stats)

            # A run that created nothing has nothing to enrich, link or score,
            # and running those stages anyway would report seven green stages
            # over an empty result.
            if job.created_ids:
                self._finish_topics(job, llm, reference_date)
            else:
                job.say("No new spaces were created, so the downstream stages have nothing to do.")

            job.stats["llm_usage"] = llm.usage_summary()   # NFR-10
            job.status = "cancelled" if job.cancelled else "done"
        except Exception as exc:  # noqa: BLE001 — a background thread must not die silently
            log.exception("Generation run %s failed", job.id)
            job.status = "error"
            job.error = f"{type(exc).__name__}: {exc}"
            job.say(f"Run failed: {job.error}")
        finally:
            job.finished_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            job.stage = None
            self._close_refresh(job)
            with self._lock:
                if self._active == job.id:
                    self._active = None

    def _run_briefs(self, job: GenerationJob, synth: Synthesiser,
                    run_critic: bool, run_entailment: bool) -> SynthesisStats:
        """Answer each brief in turn and report the passes as one run.

        Sequential rather than concurrent on purpose: `_persist` resolves the
        DR-03 identity rule by reading the taxonomy triple and then writing it,
        and two briefs converging on the same cell in parallel would race that
        read. They are cheap to run in order — one retrieval and one generation
        pass each — and the sequence is also what makes the log readable.

        A brief that retrieves nothing is not an error. It creates nothing, says
        why, and the next brief runs regardless: the corpus answering two of
        three questions is exactly the outcome §4.1 asks to be reportable.
        """
        total = len(job.briefs)
        combined = SynthesisStats()
        created_before: list[str] = []
        for index, brief in enumerate(job.briefs):
            if job.cancelled:
                job.say(f"Cancelled after {index} of {total} brief(s).")
                break
            if total > 1:
                job.say(f"Brief {index + 1} of {total}: “{brief}”")

            # Each pass reports its own position from 1; the screen is watching
            # one run. Rebase the tick onto the whole set so the bar advances
            # across briefs instead of resetting on each, and hand it the ids
            # created so far — `observe` keeps the longer list, so a per-brief
            # list would look like the count going backwards.
            def tick(progress: SynthesisProgress, _offset: int = index,
                     _seen: list[str] = created_before) -> None:
                job.observe(SynthesisProgress(
                    round=_offset + 1,
                    units_total=progress.units_total * total,
                    units_done=progress.units_total * _offset + progress.units_done,
                    unit_label=progress.unit_label,
                    created=tuple(_seen) + tuple(progress.created),
                ))

            part = synth.run_from_brief(
                job.refresh_id or "", brief, run_critic=run_critic,
                run_entailment=run_entailment, progress=job.say,
                cancelled=lambda: job.cancelled, tick=tick,
            )
            combined.absorb(part)
            created_before = list(combined.created_ids)
            if total > 1:
                job.say(f"Brief {index + 1} of {total}: "
                        f"{len(part.created_ids)} space(s) created, "
                        f"{len(part.updated_ids)} refreshed.")
        return combined

    def _finish_topics(self, job: GenerationJob, llm: LLMClient, reference_date: dt.date) -> None:
        """Take the new spaces from `candidate` to something worth opening.

        Each stage is scoped to the ids this run created. The order is the
        pipeline's own (Table 16) and it matters: sizing reads right-to-win for
        its obtainable-share assumption and links for portfolio distance, so it
        cannot run before scoring and linking.
        """
        ids = job.created_ids
        steps = (
            ("enrich", lambda: Enricher(self.cfg, self.db, self.embedder())
                .run(job.refresh_id or "", reference_date, topic_ids=ids)),
            ("link", lambda: Linker(self.cfg, self.db).run(topic_ids=ids)),
            ("score", lambda: ScoringEngine(self.cfg, self.db, llm)
                .run(job.refresh_id or "", reference_date, topic_ids=ids)),
            ("actions", lambda: NextActionGenerator(self.cfg, self.db, llm).run(topic_ids=ids)),
            ("size", lambda: MarketSizer(self.cfg, self.db).run(topic_ids=ids)),
            ("competition", lambda: CompetitionAnalyser(self.cfg, self.db).run(topic_ids=ids)),
        )
        for name, step in steps:
            if job.cancelled:
                job.say(f"Cancelled before {name}. The {len(ids)} space(s) already created remain, "
                        f"unfinished — a refresh will complete them.")
                return
            job.stage = name
            job.say(dict(STAGE_LABELS)[name] + f" for {len(ids)} space(s)…")
            try:
                job.stats[name] = step()
            except Exception as exc:  # noqa: BLE001
                # One failed finishing stage should not discard spaces that were
                # legitimately synthesised. It is recorded and the run continues:
                # a space with no market size is still a space, and §4.12's rule
                # is that the gap is reported rather than hidden.
                job.stats[name] = {"error": f"{type(exc).__name__}: {exc}"}
                job.say(f"Stage {name} failed ({exc}). The spaces remain; re-run this stage to complete them.")
                continue
            job.stages_done.append(name)

        landed = self._horizon_landing(job)
        if landed:
            job.stats["horizon_landed"] = landed
            job.say("Derived horizons (§4.8 derives these from the evidence; the filter steered "
                    "the run, it did not set them): "
                    + ", ".join(f"{k}: {v}" for k, v in sorted(landed.items())))

    # -- reporting helpers ---------------------------------------------------

    def _report_provider(self, job: GenerationJob, synth: Synthesiser) -> None:
        """Say when the model, not the corpus, is what came up empty.

        Synthesis treats a failed model call as a cluster with nothing to say —
        it logs and returns no candidates, which is right for one flaky call and
        catastrophic for a provider that is down. A run then reads every cluster,
        creates nothing, and reports "the evidence in scope did not support
        more": an evidence verdict from a run that never reached the model.

        That is worth being loud about. It is the difference between "the radar
        has nothing here" — which is a finding — and "this machine could not
        reach the model", which is a broken tool.
        """
        failures = getattr(synth, "llm_failures", 0)
        if not failures:
            return
        successes = getattr(synth, "llm_successes", 0)
        job.stats["llm_failures"] = failures
        job.stats["llm_last_error"] = synth.last_llm_error
        total = failures + successes
        if successes == 0:
            job.say(
                f"EVERY model call failed ({failures} of {total}). Nothing here is a statement "
                f"about the corpus — the run never reached the model. Last error: "
                f"{synth.last_llm_error}. Check the provider, the API key and this machine's "
                f"network before reading anything below as an evidence verdict."
            )
        else:
            job.say(
                f"{failures} of {total} model calls failed and were skipped (last: "
                f"{synth.last_llm_error}). Those clusters produced nothing for reasons that have "
                f"nothing to do with what they contain, so the count below is a floor rather than "
                f"a verdict."
            )

    def _report_shortfall(self, job: GenerationJob, stats) -> None:
        """Say why the run fell short, if it did (§4.12).

        The requirement everyone skips: what was NOT produced is logged, never
        silently dropped. A screen that asked for eight and shows three has to
        say which gate the other five died at, or the honest answer ("the
        evidence does not support eight in this slice") is indistinguishable
        from a bug.
        """
        created = len(stats.created_ids)
        if created >= job.requested:
            return
        if job.kind == "brief" and not stats.raw_candidates:
            which = "that description" if len(job.briefs) == 1 else "any of those descriptions"
            job.say(
                f"Nothing was generated. Either the corpus carries no evidence close enough to "
                f"{which}, or what it carries does not support an opportunity space along those "
                f"lines. Both are real answers — the alternative would be restating your sentence "
                f"back to you with citations that do not support it."
            )
            return
        reasons = []
        if stats.duplicate_of_existing:
            reasons.append(
                f"{stats.duplicate_of_existing} landed on taxonomy cells the radar already holds "
                f"and were merged into them instead (DR-03)"
                + (f", after {stats.duplicate_retries} extra pass(es) asking for something else"
                   if stats.duplicate_retries else "")
            )
        if stats.failed_constraints:
            reasons.append(f"{stats.failed_constraints} fell outside the requested scope")
        if stats.failed_critic:
            reasons.append(f"{stats.failed_critic} were rejected by the critic")
        if stats.failed_evidence:
            reasons.append(f"{stats.failed_evidence} had no claim that survived evidence binding")
        if stats.failed_specificity:
            reasons.append(f"{stats.failed_specificity} failed the specificity test")
        if stats.failed_vocabulary:
            reasons.append(f"{stats.failed_vocabulary} used a value outside the taxonomy")
        if stats.merged_duplicates:
            reasons.append(f"{stats.merged_duplicates} were near-duplicates of one another")
        if stats.updated_ids:
            reasons.append(f"{len(set(stats.updated_ids))} matched an existing space and refreshed it "
                           f"instead of creating a new one (DR-03)")
        # The closing sentence is an evidence verdict, so it may only be said by
        # a run that actually consulted the evidence.
        reached_the_model = job.stats.get("llm_failures", 0) == 0 or stats.raw_candidates > 0
        job.say(
            f"Asked for {job.requested}, created {created}. Of {stats.raw_candidates} raw candidate(s): "
            + ("; ".join(reasons) if reasons else "no candidate cleared curation")
            + (". The evidence in scope did not support more — that is an answer, not a failure."
               if reached_the_model else
               ". This run could not reach the model, so it says nothing about the evidence.")
        )

    def _horizon_landing(self, job: GenerationJob) -> dict[str, int]:
        """Where the new spaces actually landed on Now / Next / Later."""
        if not job.created_ids:
            return {}
        placeholders = ",".join("?" * len(job.created_ids))
        rows = self.db.query(
            f"SELECT horizon, COUNT(*) n FROM opportunity_spaces WHERE id IN ({placeholders}) "
            f"GROUP BY horizon", tuple(job.created_ids)
        )
        return {(r["horizon"] or "underived"): r["n"] for r in rows}

    # -- provenance ----------------------------------------------------------

    def _open_refresh(self, job: GenerationJob, reference_date: dt.date) -> str:
        """Record the run in `refreshes` (NFR-04).

        Every score and every signal attachment carries a refresh id, so a run
        that writes those has to have one. It is recorded as a refresh of kind
        `generation` rather than pretending to be a cadence run: the difference
        matters to anyone reading the log, since this one collected nothing.
        """
        self.db.init_schema()
        with self.db.cursor() as cur:
            cur.execute(
                "INSERT INTO refreshes (id, started_at, reference_date, is_replay, pipeline_version, "
                "weight_set) VALUES (?,?,?,0,?,?)",
                (job.id, job.started_at, reference_date.isoformat(),
                 self.cfg.pipeline_version, self.cfg.weight_set),
            )
        return job.id

    def _close_refresh(self, job: GenerationJob) -> None:
        if not job.refresh_id:
            return
        stats = {
            "kind": "generation",
            "requested": job.requested,
            "constraints": job.constraints.as_dict(),
            "status": job.status,
            "created_ids": job.created_ids,
            "updated_ids": job.updated_ids,
            **job.stats,
        }
        try:
            with self.db.cursor() as cur:
                cur.execute("UPDATE refreshes SET finished_at = ?, stats = ? WHERE id = ?",
                            (job.finished_at, js(stats), job.refresh_id))
        except Exception:  # noqa: BLE001
            log.exception("Could not close refresh row for %s", job.id)
