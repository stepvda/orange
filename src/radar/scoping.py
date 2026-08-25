"""The scoping conversation behind the Generate screen's assistant (FR-06, §4.4).

The screen used to offer a textarea and a character counter. That is the wrong
instrument for the job: an opportunity space is a vertical x use case x
technology plus a buyer's problem and a place, and somebody who knows their
market but not this taxonomy under-specifies at least two of those every time.
The failure arrives minutes later, from a synthesis run, as "nothing in the
corpus is close enough" — true, unhelpful, and paid for.

This module runs the conversation that gets asked first. Its whole reason to
exist is that it can see the same corpus the run will see, so:

1.  EVERY TURN IS RETRIEVED, NOT JUST THE LAST ONE. The probe is the whole
    conversation, re-embedded each turn against the stored signal vectors — the
    identical retrieval `Synthesiser.brief_payload` performs. So an answer that
    sharpens the idea sharpens the evidence the next question is asked from, and
    the assistant can say "the tenders here are German" instead of "which
    country?".

2.  THE MODEL DOES NOT DECIDE WHEN IT IS DONE. It proposes briefs; this module
    re-runs the run's own retrieval over each one and refuses the ready flag if
    a brief would retrieve less than the floor. Asked "do you have enough?" a
    model says yes. The button is enabled by the corpus, not by the model's
    opinion of itself — which is the same posture §4.4.4 takes everywhere else:
    the prompt asks, the validator decides.

3.  SIMILARITY IS NOT SUPPORT. Retrieval clearing the floor only means the
    corpus contains text that reads like the brief. A brief for municipal
    digital signage retrieves French public-sector IT tenders at the same 0.64
    cosine that a well-evidenced brief scores, because they are about the same
    sector in the same country — and then synthesis produces candidates whose
    every claim the critic correctly refuses, because none of those tenders
    mentions signage. `config/settings.yaml` already names this failure for the
    enrichment stage ("embeddings rate unrelated security items as close") and
    already fixes it: require a SECOND, INDEPENDENT reason. So the gate here
    reuses `Enricher.corroborates` rather than inventing a similarity number,
    and asks it of the use case and the technology only — the vertical is the
    broad axis, and "this tender is public sector" evidences nothing about
    signage. Below the floor the brief is refused with that reason, before the
    model calls are spent rather than after.

3.  IT IS STATELESS. The transcript lives in the browser and arrives with every
    request. There is no session table, nothing to expire, and a reload loses a
    conversation rather than leaking one — the conversation is worth nothing
    once its briefs have been run.

Nothing here writes. The only thing this module can cause is a
`GenerationService` run, started by a separate request with the briefs it
produced.
"""

from __future__ import annotations

import logging
from typing import Any

from .config import Config
from .db import Database, unjs
from .embeddings import Embedder
from .llm import LLMClient, LLMError
from .generation import MAX_BRIEF_CHARS, MIN_BRIEF_CHARS
from .pipeline import prompts
from .pipeline.enrich import Enricher
from .pipeline.synthesis import Synthesiser

log = logging.getLogger(__name__)

#: How much of the corpus map goes into the prompt. Enough to orient a question
#: ("the radar is currently mostly about X, Y, Z"), not enough to become the
#: conversation's subject.
_CLUSTER_SAMPLE = 24
_GEOGRAPHY_SAMPLE = 12

#: Signals retrieved per turn to ask the next question from. Larger than the
#: run's own block would be pointless — the run re-retrieves per brief anyway —
#: and smaller stops the assistant noticing the second-best reading of the idea.
_TURN_EVIDENCE = 10

#: Turns after which the assistant is told to stop opening new lines of enquiry.
#: Not enforced by refusing to answer: an interview that hard-stops mid-sentence
#: is worse than one that says "here is what I would still need".
_SOFT_TURN_LIMIT = 6

#: A conversation is a few short turns. This bound is not a policy about how
#: much someone may say, it is what keeps one request from carrying a pasted
#: document into a prompt that already holds two vocabularies and a corpus map.
MAX_MESSAGES = 40
MAX_MESSAGE_CHARS = 2000

#: Lifecycle states that occupy a taxonomy cell for DR-03 purposes. The same set
#: the Generate screen counts as "already in the radar", and for the same
#: reason: a candidate nobody promoted still owns its triple.
_OCCUPYING_STATES = ("active", "watchlist", "fading", "candidate", "dormant")


class ScopingError(RuntimeError):
    """The conversation cannot proceed, and it is not the caller's fault."""


class ScopingService:
    """One turn of the interview, grounded in the corpus.

    Constructed per request rather than held: it owns no state beyond its
    dependencies, and the embedder it borrows is the process-wide one the
    generation service already loaded.
    """

    def __init__(self, cfg: Config, db: Database, embedder: Embedder | None = None,
                 llm: LLMClient | None = None):
        self.cfg = cfg
        self.db = db
        self._embedder = embedder
        self._llm = llm
        self._enricher: Enricher | None = None

    # -- what the screen needs before anyone has typed anything --------------

    def opening(self) -> dict[str, Any]:
        """The assistant's first turn, plus what it can see.

        Written rather than generated (`prompts.SCOPING_OPENING`). It is
        identical every time, so paying a model call for it would buy nothing
        but latency on a screen that has not been used yet.
        """
        corpus = self.corpus_map()
        return {
            "message": prompts.SCOPING_OPENING,
            "suggestions": list(prompts.SCOPING_OPENING_SUGGESTIONS),
            "corpus": corpus,
            "slots": [
                {"id": slot["id"], "label": slot["label"], "required": slot["required"]}
                for slot in prompts.SCOPING_SLOTS
            ],
            "min_brief_chars": MIN_BRIEF_CHARS,
            "max_brief_chars": MAX_BRIEF_CHARS,
            "max_briefs": prompts.MAX_BRIEFS_PER_CHAT,
            "prompt_version": prompts.PROMPT_VERSION_SCOPING,
        }

    # -- the corpus, as much of it as a prompt can usefully hold -------------

    def corpus_map(self) -> dict[str, Any]:
        """What the radar is about, in the shape a question can be asked from.

        Cluster labels rather than signal titles: a hundred titles is a reading
        assignment, and the clusters are the pipeline's own answer to "what is
        this corpus about" (stage 4). Counts come from the same `relevance > 0`
        population synthesis reads, so a number here is a number the run agrees
        with.
        """
        signals = self.db.query_one(
            "SELECT COUNT(*) n FROM signals WHERE relevance > 0 AND cluster_id IS NOT NULL")["n"]
        clusters = self.db.query_one("SELECT COUNT(*) n FROM clusters")["n"]
        placeholders = ",".join("?" * len(_OCCUPYING_STATES))
        spaces = self.db.query_one(
            f"SELECT COUNT(*) n FROM opportunity_spaces WHERE merged_into IS NULL "
            f"AND state IN ({placeholders})", _OCCUPYING_STATES)["n"]

        by_type = [(row["signal_type"] or "unclassified", row["n"]) for row in self.db.query(
            "SELECT signal_type, COUNT(*) n FROM signals WHERE relevance > 0 "
            "GROUP BY signal_type ORDER BY n DESC")]

        geo: dict[str, int] = {}
        for row in self.db.query("SELECT geographies FROM signals WHERE relevance > 0"):
            for code in unjs(row["geographies"], []) or []:
                geo[str(code)] = geo.get(str(code), 0) + 1
        by_geography = sorted(geo.items(), key=lambda kv: (-kv[1], kv[0]))[:_GEOGRAPHY_SAMPLE]

        sample = [
            {"id": row["id"], "label": row["label"] or f"cluster {row['id']}",
             "size": row["size"],
             "keyphrases": ", ".join((unjs(row["keyphrases"], []) or [])[:6])}
            for row in self.db.query(
                "SELECT id, label, size, keyphrases FROM clusters ORDER BY size DESC LIMIT ?",
                (_CLUSTER_SAMPLE,))
        ]

        dates = self.db.query_one(
            "SELECT MIN(published_at) lo, MAX(published_at) hi FROM signals WHERE relevance > 0")
        date_range = ([dates["lo"], dates["hi"]] if dates and dates["lo"] else None)

        return {
            "signals": signals, "clusters": clusters, "spaces": spaces,
            "by_signal_type": by_type, "by_geography": by_geography,
            "clusters_sample": sample, "date_range": date_range,
        }

    # -- one turn ------------------------------------------------------------

    def reply(self, messages: list[dict[str, str]],
              established: dict[str, Any] | None = None) -> dict[str, Any]:
        """Answer the last thing said, and report what is still missing.

        The returned payload is deliberately larger than "here is a reply": the
        screen shows what has been understood, what the words retrieved, and
        which briefs would actually run. A chat bubble alone would hide exactly
        the part that makes this different from a text box — that the assistant
        is reading a corpus and can be checked against it.
        """
        transcript = self._clean(messages)
        if not transcript or transcript[-1]["role"] != "user":
            raise ValueError("The last message must be from the person, not the assistant.")

        synth = Synthesiser(self.cfg, self.db, self._client(), self._encoder())
        corpus = self.corpus_map()
        evidence = self._retrieve(synth, transcript)
        turns = sum(1 for m in transcript if m["role"] == "assistant")
        occupied = self._occupied_cells(evidence)

        carried, _ = self._resolve(established or {})
        system = prompts.scoping_system_prompt(
            self.cfg, MIN_BRIEF_CHARS, MAX_BRIEF_CHARS, self._min_signals)
        user = prompts.scoping_user_prompt(transcript, corpus, evidence, occupied, turns,
                                           established=carried)
        try:
            raw = self._client().complete_json(
                system, user, strong=True, temperature=0.3, max_tokens=2000)
        except LLMError as exc:
            raise ScopingError(str(exc)) from exc
        if not isinstance(raw, dict):
            raise ScopingError("The model did not return a scoping object.")

        understood, unknown = self._resolve(raw.get("understood") or {})
        # `understood` is supposed to be cumulative and is not.
        #
        # Observed: turn one settles the use case and the technology, turn two
        # settles the vertical and SILENTLY DROPS the other two, and the
        # assistant then asks again about a use case it named itself. The three
        # axes are never known at once, so no brief is ever proposed and the
        # screen has nothing on it to click — which is what "it just does not
        # generate" turned out to mean.
        #
        # The prompt now shows what was established, which is the real fix. This
        # is the belt: anything settled earlier survives a turn that forgets it,
        # and a fresh value still wins because the person is allowed to change
        # their mind.
        understood = self._carry_forward(carried, understood)
        briefs = self._check_briefs(synth, raw.get("briefs") or [])
        # A conversation that has settled the three axes must always leave
        # something to act on. The model is told to propose a brief once it has
        # them and mostly does, but "mostly" is the whole complaint: a turn that
        # resolves the vertical, the use case and the technology and then offers
        # nothing reads as a refusal for no stated reason, and the person has
        # nowhere to click. So the server composes one from what it has.
        # Deliberately NOT inferred from the transcript by matching vocabulary
        # terms against it. That was tried: "large TV screens in public spaces"
        # resolved the vertical to `aerospace_defense`, because "public spaces"
        # contains a synonym for aerospace, and a municipal signage idea filed
        # under defence is a worse outcome than one more question. The model
        # reads the conversation; substring matching reads the letters.
        if not briefs and all(understood.get(k) for k in ("vertical", "use_case", "technology")):
            briefs = self._check_briefs(synth, [self._compose_brief(understood, transcript)])
        # THE CORPUS DECIDES, IN BOTH DIRECTIONS. The model's flag is a
        # proposal and nothing more.
        #
        # Overruling it downward is the obvious half: a brief that retrieves
        # nothing cannot produce a space, so the button it would enable is a lie.
        #
        # Overruling it UPWARD matters just as much, and is easier to miss.
        # The assistant is told to put a brief forward even when it is hedging
        # about the evidence — otherwise a genuinely new idea has nothing to
        # press Generate on. It then writes "the evidence is thin, marking this
        # as not ready", which is a fair remark about the corpus and a terrible
        # reason to disable a button whose brief has already passed the same
        # corroboration check the run will apply. Gating on the model's mood
        # left a ticked, runnable brief sitting under a greyed-out button with
        # no way to find out why.
        #
        # So `ready` is simply whether anything here can be run. The model's
        # opinion travels beside it as `model_ready`, for the screen to show
        # where the two disagree.
        runnable = [b for b in briefs if b["runnable"]]
        ready = bool(runnable)

        return {
            "reply": str(raw.get("reply") or "").strip(),
            "understood": understood,
            "unresolved": unknown,
            "missing": self._missing(understood, raw.get("missing")),
            "asking_for": raw.get("asking_for") or None,
            "suggestions": [str(s) for s in (raw.get("suggestions") or [])][:4],
            "evidence_note": raw.get("evidence_note") or None,
            "ready": ready,
            "model_ready": bool(raw.get("ready")),
            "briefs": briefs,
            "evidence": self._evidence_payload(evidence),
            "occupied": occupied,
            "turns": turns + 1,
            "soft_turn_limit": _SOFT_TURN_LIMIT,
            "prompt_version": prompts.PROMPT_VERSION_SCOPING,
        }

    # -- retrieval -----------------------------------------------------------

    @property
    def _min_signals(self) -> int:
        """The floor a run needs, quoted from the run rather than restated.

        `Synthesiser.brief_payload` returns nothing at all below this, so the
        number the assistant tells someone has to be that number or the
        conversation is calibrated against a threshold that does not exist.
        """
        return 3

    def _retrieve(self, synth: Synthesiser, transcript: list[dict[str, str]]) -> dict[str, Any]:
        """Retrieve from the WHOLE conversation, not the last message.

        "Germany" retrieves nothing. "Germany" as the third answer in a
        conversation about gearbox monitoring for wind operators retrieves what
        the conversation is about — so the probe is every user turn, most recent
        last, which is also the order the embedding weights least by position.

        The retrieval floor is deliberately NOT lowered for the conversation:
        showing signals the run would refuse to build on is how a chat screen
        ends up more optimistic than the pipeline behind it. Where a probe
        retrieves too little to reach the run's own minimum, the assistant is
        told the retrieval was empty and says so.
        """
        probe = " ".join(m["content"] for m in transcript if m["role"] == "user")
        probe = probe[-MAX_BRIEF_CHARS * 2:].strip()
        if len(probe) < 12:
            return {"signals": [], "similarities": [], "floor": synth.brief_floor}
        payload = synth.brief_payload(probe, limit=_TURN_EVIDENCE,
                                      min_signals=self._min_signals)
        signals = [dict(s) | {"geographies": unjs(s.get("geographies"), []) or []}
                   for s in payload["signals"]]
        return {"signals": signals, "similarities": payload["similarities"],
                "floor": synth.brief_floor, "probe": probe}

    def _check_briefs(self, synth: Synthesiser, raw: list[Any]) -> list[dict[str, Any]]:
        """Put every proposed brief through the run's own front door.

        This is the check the whole module exists for. A brief is runnable when
        it is the right length, its triple is legal, and — the part a model
        cannot self-assess — the corpus answers it above the same floor the
        synthesis job will use. Anything else comes back with the reason
        attached, so the screen can show a brief that is nearly right and say
        what is wrong with it rather than silently dropping it.
        """
        checked: list[dict[str, Any]] = []
        for item in raw[:prompts.MAX_BRIEFS_PER_CHAT]:
            if not isinstance(item, dict):
                continue
            description = " ".join(str(item.get("description") or "").split())
            triple, invalid = self._resolve_triple(item)
            problems: list[str] = []
            if len(description) < MIN_BRIEF_CHARS:
                problems.append(
                    f"Too short to retrieve with — {MIN_BRIEF_CHARS} characters is the minimum.")
            if len(description) > MAX_BRIEF_CHARS:
                description = description[:MAX_BRIEF_CHARS].rstrip()
            if invalid:
                problems.append("Outside the controlled vocabulary: "
                                + ", ".join(f"{k}={v!r}" for k, v in invalid.items()))

            evidence: dict[str, Any] = {"count": 0, "best": None, "corroborated": 0,
                                        "signals": []}
            if not problems:
                payload = synth.brief_payload(description, limit=_TURN_EVIDENCE,
                                              min_signals=self._min_signals)
                reasons, method = self._support(triple, description, payload["signals"])
                evidence = {
                    "count": len(payload["signals"]),
                    "best": (payload["similarities"][0] if payload["similarities"] else None),
                    "corroborated": sum(1 for r in reasons if r),
                    #: Which test answered — `vocabulary` when the free one was
                    #: enough, `model` when it was not and a cheap call was spent.
                    "support_method": method,
                    "signals": [
                        {"id": s["id"], "title": s["title"], "publisher": s["publisher"],
                         "published_at": s["published_at"], "signal_type": s["signal_type"],
                         "tier": s["tier"], "url": s["url"], "similarity": sim,
                         # Why this signal counts as support, or null if it is only
                         # close. Shown rather than summed away: "similarity only"
                         # beside a title is what makes the refusal below legible.
                         "corroborates": reason}
                        for s, sim, reason in zip(payload["signals"], payload["similarities"],
                                                  reasons)
                    ],
                }
                if not payload["signals"]:
                    problems.append(
                        f"Nothing in the corpus sits above the similarity floor "
                        f"({synth.brief_floor:.2f}) for this brief, so an evidence-backed run "
                        f"would create nothing. The corpus is fixed — but it is also silent about "
                        f"every idea nobody has published yet, which is not the same as the idea "
                        f"being wrong."
                    )
                elif evidence["corroborated"] < self._min_signals:
                    # NOT a dead end — see the `hypothesis` key below. Refusing
                    # here and stopping is what made this screen useless for the
                    # thing it was most wanted for.
                    supported = evidence["corroborated"]
                    problems.append(
                        f"{evidence['count']} signal(s) read like this brief, but only "
                        f"{supported} of them {'is' if supported == 1 else 'are'} evidence for "
                        f"what it actually describes — the rest share its industry, its country or "
                        f"its technology label while being about something else. Synthesis would "
                        f"produce candidates whose claims cite them, "
                        f"and the critic would reject those claims for not being about this. "
                        f"Narrow to what the corpus actually evidences, or accept that this is a "
                        f"gap in it."
                    )

            existing = self._existing_space(triple) if triple else None
            checked.append({
                "title": str(item.get("title") or "").strip()[:120],
                "description": description,
                "vertical": triple[0] if triple else None,
                "use_case": triple[1] if triple else None,
                "technology": triple[2] if triple else None,
                "geographies": [str(g).upper() for g in (item.get("geographies") or [])][:8],
                "rationale": str(item.get("rationale") or "").strip()[:400],
                # What the PERSON asserted, in their terms, drawn from the
                # conversation they have already had. Pre-fills the contributed-
                # evidence box: they have just spent six turns saying this, and
                # asking them to type it again is the refusal with an extra step.
                "hypothesis_rationale": str(item.get("hypothesis_rationale") or "").strip()[:2000],
                "evidence": evidence,
                # DR-03 is not a problem — the run is legal and useful — but it
                # changes what pressing Generate means, so it travels separately
                # from the things that would stop it.
                "existing": existing,
                "problems": problems,
                "runnable": not problems,
                # Whether the OTHER route is open. The corpus cannot evidence a
                # genuinely new idea — that is what "new" means — so a silent
                # corpus must not be a dead end, only a different kind of run.
                # A brief that is malformed or outside the vocabulary cannot be
                # run by either route, which is why this is not just `not
                # runnable`.
                # Open whenever the triple is legal, NOT only when the corpus
                # came up short. A brief the corpus does carry can still lose its
                # candidate at the critic — that is the commonest outcome in the
                # run log — and a person left with a finished run, nothing
                # created and no second route has been refused twice.
                "hypothesis": bool(triple),
            })
        return checked

    @staticmethod
    def _carry_forward(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
        """Keep what an earlier turn settled when this one forgot it.

        A new value always wins — somebody who says "actually, make it retail"
        must be able to. Only absence defers to the past.
        """
        merged = dict(current)
        for key, value in (previous or {}).items():
            if not merged.get(key) and value:
                merged[key] = value
        return merged

    def _compose_brief(self, understood: dict[str, Any],
                       transcript: list[dict[str, str]]) -> dict[str, Any]:
        """Build a brief from what the conversation settled, without the model.

        A fallback, not a preference: the model writes a better sentence than
        this, because it can weigh which of six turns mattered. What this
        guarantees is that a settled conversation is never a dead end — the axes
        are known, so a brief exists, so there is a route.

        The description is the person's own words, most recent first because the
        later turns are the ones that sharpened it, trimmed to the length the
        retrieval wants. The labels come from `understood`, which the server has
        already resolved against the closed vocabularies, so the triple is legal
        by construction.
        """
        said = [" ".join(m["content"].split()) for m in transcript if m["role"] == "user"]
        # Chronological, because that is how it was told and how it reads. An
        # earlier version put the most recent turn first, on the theory that the
        # later answers are the specific ones. They are — but they are also one
        # or two words each ("both", "managed service"), so leading with them
        # produced "both IT and operations sign municipalities buy it place large
        # TV screens...", which is not a sentence and retrieves like nothing.
        description = " ".join(said)
        if understood.get("buyer_problem"):
            description = f"{description} The problem: {understood['buyer_problem']}."
        description = " ".join(description.split())[:MAX_BRIEF_CHARS].rstrip()
        # The longest thing they said, not the last: the opening statement is
        # almost always the idea, and the closing turns are answers to questions.
        longest = max(said, key=len) if said else "Untitled space"
        return {
            "title": longest[:80].rstrip(),
            "description": description,
            "vertical": understood["vertical"],
            "use_case": understood["use_case"],
            "technology": understood["technology"],
            "geographies": understood.get("geographies") or [],
            "rationale": "Composed from the conversation — the assistant settled the taxonomy "
                         "but did not write a brief, so this is what it had.",
            "hypothesis_rationale": description,
        }

    def _support(self, triple: tuple[str, str, str] | None, description: str,
                 signals: list[dict[str, Any]]) -> tuple[list[str | None], str]:
        """Which retrieved signals actually bear on the brief, and how we know.

        THE MODEL DECIDES, AND IT IS ASKED ABOUT THE SENTENCE. That is a
        correction of an earlier design that asked only about the taxonomy
        triple, and it was wrong in a way worth recording, because the failure
        was invisible until a run wasted its calls on it.

        The vocabulary test — does the signal text carry the use case's or the
        technology's own term — is free and precise about the LABEL. The label,
        however, is routinely an approximation: the vocabularies are closed, so a
        proposal about advertising-funded municipal screens gets filed under the
        nearest available job and the nearest available technology. Tenders for
        private-5G video surveillance then corroborate `private_5g` perfectly
        while being no evidence at all for advertising screens. The gate reported
        four supporting signals, the button enabled, the run spent four model
        calls, and the critic threw the candidate out with exactly that reason:
        "SIG-... is about video surveillance, neither mentions public displays".

        So the cheap model is now asked on every proposed brief, about the
        brief's own sentence, and its answer is authoritative: a signal it does
        not endorse does not count however well it matches the label. The
        vocabulary reason is kept for display where the two agree, because
        "technology term 'private 5g' appears in the signal text" is a more
        checkable thing to show than a model's say-so.

        One cheap call per proposed brief, on the turn where somebody is about to
        spend a whole synthesis run — the same trade §4.4.4 makes for the
        entailment check. A provider failure degrades to the vocabulary answer
        rather than losing the turn.
        """
        reasons = self._corroboration(triple, signals)
        if not triple or not signals:
            return reasons, "vocabulary"

        vertical, use_case, technology = triple
        try:
            verdict = self._client().complete_json(
                prompts.brief_support_prompt(vertical, use_case, technology, description),
                prompts.format_signals_for_support(signals),
                temperature=0.0, max_tokens=600,
            )
        except LLMError as exc:
            log.warning("Brief support check failed, keeping the vocabulary answer: %s", exc)
            return reasons, "vocabulary"
        if not isinstance(verdict, dict):
            return reasons, "vocabulary"

        supporting = {str(i) for i in (verdict.get("supporting") or [])}
        note = str(verdict.get("note") or "").strip()[:200]
        merged = [
            # Endorsed: show the concrete vocabulary reason if there is one,
            # otherwise say the model vouched for it. Not endorsed: nothing, even
            # if the label matched — that match is what this call exists to
            # overrule.
            ((reason or f"judged to be about this — {note}")
             if signal["id"] in supporting else None)
            for reason, signal in zip(reasons, signals)
        ]
        return merged, "model"

    def _corroboration(self, triple: tuple[str, str, str] | None,
                       signals: list[dict[str, Any]]) -> list[str | None]:
        """Why each retrieved signal independently supports the brief, or None.

        The same test the enrichment stage applies before attaching a signal to a
        topic, asked here of a brief nobody has run yet — a vocabulary term (in
        any language the lexicon covers, which matters when the evidence is
        French) or a CPV crosswalk hit.

        THE VERTICAL IS DELIBERATELY BLANKED. Enrichment considers all three axes
        because it is adding evidence to a space that already exists and has
        already been judged specific. Deciding whether the corpus can support a
        NEW space is a stricter question, and the vertical is the axis that
        answers it least: a corpus full of French public-sector tenders
        corroborates the vertical of every French public-sector brief ever
        written, including the ones about things it has never heard of. §4.4.2's
        own negative example is "a vertical plus a slogan".
        """
        if not triple:
            return [None] * len(signals)
        _, use_case, technology = triple
        axes = {"vertical": "", "use_case": use_case, "technology": technology}
        enricher = self._get_enricher()
        out: list[str | None] = []
        for signal in signals:
            out.append(enricher.corroborates(axes, signal, self._cpv_for(signal)))
        return out

    def _cpv_for(self, signal: dict[str, Any]) -> dict[str, float]:
        """Resolve a procurement notice's CPV codes, as enrichment does.

        A tender's prose is boilerplate — the codes are where its subject
        actually lives, and they are the reason a French notice can corroborate
        an English use case at all.
        """
        row = self.db.query_one("SELECT attributes FROM signals WHERE id = ?", (signal["id"],))
        codes = [str(c) for c in ((unjs(row["attributes"], {}) if row else {}) or {}).get("cpv", [])]
        if not codes:
            return {}
        resolved = dict(self.cfg.cpv_to_use_case.resolve(codes))
        resolved.update(self.cfg.cpv_to_vertical.resolve(codes))
        return resolved

    def _get_enricher(self) -> Enricher:
        if self._enricher is None:
            self._enricher = Enricher(self.cfg, self.db, self._encoder())
        return self._enricher

    # -- vocabulary ----------------------------------------------------------

    def _resolve(self, understood: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
        """Map what the model claims to understand onto legal ids.

        `Vocabulary.resolve` accepts an id, a label or a synonym, which is what
        makes it safe to let the assistant talk in the person's words: "banking"
        comes back as `financial_services` rather than as a validation error
        somebody has to read.
        """
        out: dict[str, Any] = {}
        unknown: dict[str, str] = {}
        for key, vocab in (("vertical", self.cfg.verticals), ("use_case", self.cfg.use_cases),
                           ("technology", self.cfg.technologies)):
            value = understood.get(key)
            resolved = vocab.resolve(str(value)) if value else None
            out[key] = resolved
            if value and not resolved:
                unknown[key] = str(value)

        personas: list[str] = []
        for value in (understood.get("personas") or []):
            resolved = self.cfg.personas.resolve(str(value))
            if resolved:
                personas.append(resolved)
            else:
                unknown.setdefault("personas", str(value))
        out["personas"] = personas

        out["geographies"] = [str(g).upper()[:2] if str(g).upper() != "EU" else "EU"
                              for g in (understood.get("geographies") or [])][:8]
        horizon = str(understood.get("horizon") or "").lower() or None
        out["horizon"] = horizon if horizon in ("now", "next", "later") else None
        for key in ("buyer_problem", "deployment"):
            value = understood.get(key)
            out[key] = str(value).strip()[:200] if value else None
        return out, unknown

    def _resolve_triple(self, item: dict[str, Any]) -> tuple[tuple[str, str, str] | None,
                                                             dict[str, str]]:
        resolved: dict[str, str | None] = {}
        invalid: dict[str, str] = {}
        for key, vocab in (("vertical", self.cfg.verticals), ("use_case", self.cfg.use_cases),
                           ("technology", self.cfg.technologies)):
            value = item.get(key)
            hit = vocab.resolve(str(value)) if value else None
            resolved[key] = hit
            if not hit:
                invalid[key] = str(value) if value else "missing"
        if invalid:
            return None, invalid
        return (resolved["vertical"], resolved["use_case"], resolved["technology"]), {}

    def _missing(self, understood: dict[str, Any], claimed: Any) -> list[str]:
        """What is still needed — computed, with the model's list as a hint.

        The required three are checked here rather than trusted, because "I have
        everything I need" is the answer a model gives when it wants to be
        helpful. The optional slots are taken from the model, since whether the
        buyer's problem has been said is a reading of the conversation and not a
        lookup.
        """
        required = [slot["id"] for slot in prompts.SCOPING_SLOTS if slot["required"]]
        missing = [key for key in required if not understood.get(key)]
        for key in (claimed or []):
            key = str(key)
            if key not in missing and any(s["id"] == key for s in prompts.SCOPING_SLOTS):
                missing.append(key)
        return missing

    # -- what already occupies the neighbourhood -----------------------------

    def _occupied_cells(self, evidence: dict[str, Any]) -> list[str]:
        """Spaces already built on the evidence this conversation retrieved.

        Not "all spaces" — that is a list nobody reads and a prompt nobody can
        afford. The ones sharing retrieved signals are the ones a brief from this
        conversation could actually land on, which is exactly the DR-03 warning
        worth giving before the run rather than after it.
        """
        ids = [s["id"] for s in evidence.get("signals") or []]
        if not ids:
            return []
        placeholders = ",".join("?" * len(ids))
        states = ",".join("?" * len(_OCCUPYING_STATES))
        rows = self.db.query(
            f"SELECT DISTINCT o.id, o.vertical, o.use_case, o.technology, o.statement, o.state "
            f"FROM opportunity_spaces o JOIN opportunity_signals os ON os.opportunity_id = o.id "
            f"WHERE os.signal_id IN ({placeholders}) AND o.merged_into IS NULL "
            f"AND o.state IN ({states}) LIMIT 12",
            (*ids, *_OCCUPYING_STATES),
        )
        return [f"[{r['id']}] {r['vertical']} x {r['use_case']} x {r['technology']} — "
                f"{r['statement']}" for r in rows]

    def _existing_space(self, triple: tuple[str, str, str]) -> dict[str, Any] | None:
        row = self.db.query_one(
            "SELECT id, statement, state FROM opportunity_spaces "
            "WHERE vertical=? AND use_case=? AND technology=? AND merged_into IS NULL", triple)
        return dict(row) if row else None

    # -- plumbing ------------------------------------------------------------

    @staticmethod
    def _evidence_payload(evidence: dict[str, Any]) -> dict[str, Any]:
        """The retrieval, in the shape the screen shows it.

        Every signal carries its url and its similarity because the point of
        putting evidence beside a conversation is that it can be opened and
        disagreed with. A retrieval nobody can check is decoration.
        """
        return {
            "floor": evidence.get("floor"),
            "count": len(evidence.get("signals") or []),
            "signals": [
                {"id": s["id"], "title": s["title"], "publisher": s["publisher"],
                 "published_at": s["published_at"], "signal_type": s["signal_type"],
                 "tier": s["tier"], "url": s["url"], "geographies": s["geographies"],
                 "similarity": sim}
                for s, sim in zip(evidence.get("signals") or [],
                                  evidence.get("similarities") or [])
            ],
        }

    @staticmethod
    def _clean(messages: list[dict[str, str]]) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        for message in (messages or [])[-MAX_MESSAGES:]:
            role = str(message.get("role") or "").lower()
            content = " ".join(str(message.get("content") or "").split())[:MAX_MESSAGE_CHARS]
            if role in ("user", "assistant") and content:
                out.append({"role": role, "content": content})
        return out

    def _client(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMClient(max_retries=self.cfg.settings["llm"]["max_retries"])
        return self._llm

    def _encoder(self) -> Embedder:
        if self._embedder is None:
            self._embedder = Embedder()
        return self._embedder
