"""The written half of the collateral, and the rules it has to survive.

Everything in this package is one of three registers, kept apart exactly as the
brief and the plan keep them:

  computed    scores, sizes, competitive intensity, portfolio distance. Stored,
              reproducible, never generated.
  curated     named assets, references, competitors, from the business graph.
  written     what this module produces.

A model writes the third register only. It never supplies a figure — the
`NO_NUMBERS_RULE` goes onto every system prompt by `LLMClient`, and anything
numeric that slips through is stripped here before it can reach a page. The
positions on the competitive field map, the durations on the phase timeline and
the likelihood/impact coordinates on the risk matrix are the one apparent
exception, and are not one: they are ORDINAL JUDGEMENTS on a fixed three- or
five-point scale, clamped on arrival, and they are never printed as quantities.
A model saying "this risk is high impact" is doing the job it is good at; a
model saying "EUR 4.2m" is fabricating.

WHAT HAPPENS WHEN THE MODEL FAILS. Nothing is abandoned. Every piece of
collateral here can be rendered from computed and curated data alone, and the
written sections are additive. A failed or refused generation produces a
document with fewer sections and an explicit note saying which — the same
posture `api.generate_brief` already takes when the description will not build.
That is why `generate` returns `(content, stripped)` rather than raising.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from ..llm import LLMError
from ..pipeline.synthesis import _NUMERIC_CLAIM_RE

log = logging.getLogger(__name__)

#: Collateral is held to a STRICTER numeric rule than the pipeline is, and the
#: difference is the audience. `_NUMERIC_CLAIM_RE` deliberately lets bare counts
#: through, because inside the pipeline a number in a claim is about to meet the
#: entailment check, which is a better instrument than a regex. Nothing here
#: meets an entailment check — it goes to a customer. And the most dangerous
#: fabricated number in pre-sales material is exactly the kind that regex
#: permits: "1,200 plants in scope" is a claim about the customer's own estate,
#: it will be read as researched, and it is wrong.
#:
#: Two patterns, both narrow enough not to eat legitimate prose:
#:   comma-grouped   1,200 / 45,000 — thousands separators essentially only
#:                   appear in statistics, never in "three phases".
#:   long bare       four digits or more that is not a plausible year, so a
#:                   cited regulatory deadline ("2027") still passes, as it does
#:                   everywhere else in this codebase.
_COLLATERAL_NUMERIC_RE = re.compile(r"\b\d{1,3}(?:,\d{3})+\b|\b\d{4,}\b")


def _fabricated_quantity(text: str) -> bool:
    if _NUMERIC_CLAIM_RE.search(text):
        return True
    for match in _COLLATERAL_NUMERIC_RE.finditer(text):
        token = match.group(0)
        if "," not in token and 1900 <= int(token) <= 2100:
            continue  # a year, which the entailment check owns
        return True
    return False

PROMPT_VERSION_PRESALES = "presales-v1"

#: Ordinal scales the model is allowed to place things on. Words, not numbers,
#: so a model that has been told it may not produce quantities is not being
#: asked to contradict itself — the mapping to a coordinate happens here.
BANDS = {"low": 0, "medium": 1, "high": 2}


def _band(value: Any, default: int = 1) -> int:
    if isinstance(value, str):
        return BANDS.get(value.strip().lower(), default)
    if isinstance(value, (int, float)):
        return max(0, min(2, int(value)))
    return default


def _clean(text: Any, minimum: int = 0) -> str:
    """Trim a model string, or return empty if it fails the numeric guard.

    Applied to every free-text field that reaches a page. Defence 3 of §4.4.4 is
    the rule most worth enforcing rigidly, and collateral goes to customers, so
    it is enforced here at the field rather than at the section: one invented
    figure in an objection response should cost that response, not the document.
    """
    value = str(text or "").strip()
    if len(value) < minimum:
        return ""
    if _fabricated_quantity(value):
        return ""
    return value


def _list_of(payload: Any, keys: tuple[str, ...], limit: int,
             minimum: int = 12) -> list[dict[str, str]]:
    """Normalise a model list-of-objects, dropping entries that lose a field.

    An objection with no response, or a phase with no deliverable, is worse than
    no entry at all: it renders as a heading over white space and reads as an
    oversight rather than as an absence.
    """
    out: list[dict[str, str]] = []
    for raw in (payload if isinstance(payload, list) else [])[: limit * 2]:
        if not isinstance(raw, dict):
            continue
        entry = {key: _clean(raw.get(key), minimum if key == keys[-1] else 0) for key in keys}
        if all(entry[key] for key in keys):
            out.append(entry)
        if len(out) == limit:
            break
    return out


class PreSalesWriter:
    """One model call per piece of collateral, validated on the way back."""

    def __init__(self, llm: Any):
        self.llm = llm

    # -- plumbing ----------------------------------------------------------

    def _ask(self, kind: str, system: str, user: str,
             temperature: float = 0.4, max_tokens: int = 2600) -> dict[str, Any]:
        """One call. Returns {} rather than raising, so a document still builds.

        The MOCK_KIND marker is what lets the whole package run with no network
        and no key: `LLMClient._mock` keys its stub off it, so the tests exercise
        the real validation and rendering path rather than a bypass of it.
        """
        try:
            payload = self.llm.complete_json(
                f"{system}\n\nMOCK_KIND=presales",
                user, strong=True, temperature=temperature, max_tokens=max_tokens,
            )
        except (LLMError, Exception) as exc:  # noqa: BLE001 — reported, not swallowed
            log.warning("Pre-sales content for %s could not be written: %s", kind, exc)
            return {}
        return payload if isinstance(payload, dict) else {}

    # -- per-collateral content -------------------------------------------

    def discovery(self, context: str) -> dict[str, Any]:
        payload = self._ask("discovery-pack", _DISCOVERY_SYSTEM, context)
        return {
            "buying_centre": [
                {
                    "role": _clean(person.get("role")),
                    "stance": _clean(person.get("stance")),
                    "cares_about": _clean(person.get("cares_about")),
                    "trigger": _clean(person.get("trigger")),
                }
                for person in (payload.get("buying_centre") or [])[:6]
                if isinstance(person, dict) and _clean(person.get("role"))
            ],
            "qualification": _list_of(payload.get("qualification"),
                                      ("criterion", "question", "what_good_looks_like"), 8),
            "disqualifiers": [q for q in (_clean(x) for x in payload.get("disqualifiers") or [])
                              if q][:5],
        }

    def solution(self, context: str) -> dict[str, Any]:
        payload = self._ask("solution-outline", _SOLUTION_SYSTEM, context)
        return {
            "components": [
                {
                    "label": _clean(component.get("label")),
                    "provider": (str(component.get("provider", "third_party")).strip().lower()
                                 if str(component.get("provider", "")).strip().lower()
                                 in ("orange", "partner", "customer", "third_party")
                                 else "third_party"),
                    "note": _clean(component.get("note")),
                }
                for component in (payload.get("components") or [])[:12]
                if isinstance(component, dict) and _clean(component.get("label"))
            ],
            "interfaces": _list_of(payload.get("interfaces"), ("between", "carries"), 6),
            "open_questions": [q for q in (_clean(x) for x in payload.get("open_questions") or [])
                               if q][:6],
        }

    def battlecards(self, context: str) -> dict[str, Any]:
        payload = self._ask("battlecards", _BATTLECARD_SYSTEM, context, max_tokens=3200)
        cards = []
        for raw in (payload.get("cards") or [])[:8]:
            if not isinstance(raw, dict) or not _clean(raw.get("competitor")):
                continue
            cards.append({
                "competitor": _clean(raw.get("competitor")),
                "their_pitch": _clean(raw.get("their_pitch")),
                "strong_where": _clean(raw.get("strong_where")),
                "thin_where": _clean(raw.get("thin_where")),
                "trap_question": _clean(raw.get("trap_question")),
                "our_proof": _clean(raw.get("our_proof")),
                # Two ordinal readings, used only to place a dot on the map.
                "reach": _band(raw.get("reach")),
                "depth": _band(raw.get("depth")),
                "dimensions": _list_of(raw.get("dimensions"), ("dimension", "verdict"), 4),
            })
        return {"cards": cards, "field": _clean(payload.get("field"), 40)}

    def value(self, context: str) -> dict[str, Any]:
        payload = self._ask("value-hypothesis", _VALUE_SYSTEM, context)
        return {
            "drivers": _list_of(payload.get("drivers"), ("driver", "mechanism"), 5),
            "cost_of_inaction": _clean(payload.get("cost_of_inaction"), 40),
            "proof_plan": [p for p in (_clean(x) for x in payload.get("proof_plan") or []) if p][:5],
        }

    def deck(self, context: str) -> dict[str, Any]:
        payload = self._ask("first-meeting-deck", _DECK_SYSTEM, context, max_tokens=3200)
        slides = []
        for raw in (payload.get("slides") or [])[:12]:
            if not isinstance(raw, dict) or not _clean(raw.get("title")):
                continue
            slides.append({
                "title": _clean(raw.get("title")),
                "bullets": [b for b in (_clean(x) for x in raw.get("bullets") or []) if b][:5],
                "notes": _clean(raw.get("notes")),
            })
        return {"slides": slides}

    def demo(self, context: str) -> dict[str, Any]:
        payload = self._ask("demo-scope", _DEMO_SYSTEM, context)
        phases = []
        for raw in (payload.get("phases") or [])[:5]:
            if not isinstance(raw, dict) or not _clean(raw.get("label")):
                continue
            phases.append({
                "label": _clean(raw.get("label")),
                # Weeks is a duration on a proposal, not a market figure, and it
                # is clamped to a sane band rather than trusted.
                "weeks": max(1, min(8, int(raw.get("weeks") or 2)
                                    if str(raw.get("weeks") or "").strip().isdigit() else 2)),
                "deliverable": _clean(raw.get("deliverable")),
            })
        return {
            "phases": phases,
            "in_scope": [s for s in (_clean(x) for x in payload.get("in_scope") or []) if s][:8],
            "out_scope": [s for s in (_clean(x) for x in payload.get("out_scope") or []) if s][:8],
            "success_criteria": _list_of(payload.get("success_criteria"),
                                         ("criterion", "measured_by"), 5),
            "customer_provides": [s for s in (_clean(x) for x in payload.get("customer_provides") or [])
                                  if s][:6],
        }

    def rfp(self, context: str) -> dict[str, Any]:
        payload = self._ask("rfp-boilerplate", _RFP_SYSTEM, context, max_tokens=3400)
        return {"blocks": _list_of(payload.get("blocks"), ("section", "answer"), 8, minimum=80)}

    def outreach(self, context: str) -> dict[str, Any]:
        payload = self._ask("outreach-sequence", _OUTREACH_SYSTEM, context)
        return {"emails": _list_of(payload.get("emails"),
                                   ("stage", "subject", "body"), 5, minimum=80)}

    def pricing(self, context: str) -> dict[str, Any]:
        payload = self._ask("pricing-options", _PRICING_SYSTEM, context)
        options = []
        for raw in (payload.get("options") or [])[:4]:
            if not isinstance(raw, dict) or not _clean(raw.get("model")):
                continue
            options.append({
                "model": _clean(raw.get("model")),
                "how_it_works": _clean(raw.get("how_it_works")),
                "orange_risk": _band(raw.get("orange_risk")),
                "customer_appeal": _band(raw.get("customer_appeal")),
                "levers": [l for l in (_clean(x) for x in raw.get("levers") or []) if l][:4],
                "use_when": _clean(raw.get("use_when")),
            })
        return {"options": options}

    def risks(self, context: str) -> dict[str, Any]:
        payload = self._ask("risk-register", _RISK_SYSTEM, context)
        risks = []
        for raw in (payload.get("risks") or [])[:9]:
            if not isinstance(raw, dict) or not _clean(raw.get("risk")):
                continue
            risks.append({
                "risk": _clean(raw.get("risk")),
                "likelihood": _band(raw.get("likelihood")),
                "impact": _band(raw.get("impact")),
                "mitigation": _clean(raw.get("mitigation")),
                "owner_role": _clean(raw.get("owner_role")) or "Bid lead",
            })
        return {"risks": risks}

    def partner(self, context: str) -> dict[str, Any]:
        payload = self._ask("partner-brief", _PARTNER_SYSTEM, context)
        return {
            "gaps": _list_of(payload.get("gaps"), ("capability", "why_needed", "candidate_type"), 5),
            "the_ask": _clean(payload.get("the_ask"), 40),
            "what_orange_brings": [b for b in (_clean(x) for x in payload.get("what_orange_brings") or [])
                                   if b][:5],
        }


# ---------------------------------------------------------------------------
# System prompts
#
# Each one names the register it is writing in and the register it may not touch.
# The recurring instruction — "only the named entities supplied to you" — is the
# same defence the description prompt uses: a model asked for a battlecard will
# invent a plausible competitor unless the list is closed.
# ---------------------------------------------------------------------------

_COMMON = (
    "You are writing internal pre-sales material for Orange Business. It will be read by "
    "people who sell for a living and will be checked against reality in front of a customer, "
    "so it has to be specific and it has to be honest about what is not known.\n"
    "RULES:\n"
    "- Name ONLY the Orange assets, partners and competitors supplied to you. Never invent one.\n"
    "- Where the evidence is thin, say so plainly. A document that admits something is trusted.\n"
    "- Write in operational terms, not marketing register. No superlatives, no 'leading', "
    "no 'best-in-class'.\n"
    "- British English. Return JSON only.\n"
    "- If RECENT PUBLIC ITEMS are supplied below, use them to make the material current — a "
    "regulator's deadline, a competitor's announcement, a closed tender. Anything you take "
    "from one MUST name its publisher inline, like \"(Handelsblatt, 2026-07-14)\". An "
    "unattributed claim from those items is worse than leaving them out."
)

_DISCOVERY_SYSTEM = _COMMON + (
    "\n\nProduce a discovery and qualification pack.\n"
    'JSON: {"buying_centre":[{"role","stance","cares_about","trigger"}],'
    '"qualification":[{"criterion","question","what_good_looks_like"}],'
    '"disqualifiers":[string]}\n'
    "`stance` is exactly one of: economic buyer, champion, technical evaluator, user, blocker. "
    "Exactly one entry must be the economic buyer. `trigger` is the event that makes that person "
    "act this year rather than next. `criterion` follows MEDDIC-style qualification (metrics, "
    "economic buyer, decision criteria, decision process, pain, champion). `disqualifiers` are "
    "the signs this is NOT a real opportunity and the team should walk away."
)

_SOLUTION_SYSTEM = _COMMON + (
    "\n\nProduce a solution outline for a pre-sales engineer.\n"
    'JSON: {"components":[{"label","provider","note"}],"interfaces":[{"between","carries"}],'
    '"open_questions":[string]}\n'
    "`provider` is exactly one of: orange, partner, customer, third_party. Use `orange` ONLY for "
    "the named Orange assets supplied. Anything the engagement needs that is not in that list is "
    "`third_party` — those gaps are the most useful thing on the page, so do not hide them by "
    "guessing. `note` is at most six words on what the component does. `interfaces` describe what "
    "flows between which two components. `open_questions` are what the architect must ask before "
    "committing to a design."
)

_BATTLECARD_SYSTEM = _COMMON + (
    "\n\nProduce one battlecard per competitor supplied, and a sentence on the shape of the field.\n"
    'JSON: {"field":string,"cards":[{"competitor","their_pitch","strong_where","thin_where",'
    '"trap_question","our_proof","reach","depth","dimensions":[{"dimension","verdict"}]}]}\n'
    "`reach` and `depth` are each exactly one of: low, medium, high — reach is how broadly they "
    "cover this market, depth is how deep their capability goes in it. These place them on a map; "
    "they are judgements, not measurements, and must not appear as numbers in your prose. "
    "`trap_question` is a question a customer can ask THEM that is awkward for them and "
    "comfortable for Orange. `our_proof` must cite a named Orange asset or reference from the "
    "list supplied — if there is none, write 'No named proof point yet — this is a gap.'"
)

_VALUE_SYSTEM = _COMMON + (
    "\n\nProduce the qualitative half of a business case. The figures come from the radar's own "
    "sizing and are supplied to you; your job is the MECHANISM behind them.\n"
    'JSON: {"drivers":[{"driver","mechanism"}],"cost_of_inaction":string,"proof_plan":[string]}\n'
    "`mechanism` explains how the driver turns into money in operational terms — what stops "
    "happening, what happens faster, what stops being paid for. `proof_plan` is how the customer "
    "could verify each driver in their own data before signing anything."
)

_DECK_SYSTEM = _COMMON + (
    "\n\nProduce a first-meeting deck: 8 to 10 slides, in the order a first conversation actually "
    "goes — what changed, why now, what we heard, what we would build, why Orange, what it is "
    "worth, what happens next.\n"
    'JSON: {"slides":[{"title","bullets":[string],"notes"}]}\n'
    "At most four bullets per slide, at most twelve words each. `notes` is what the presenter "
    "says out loud, two or three sentences, conversational. Do not write a slide about the "
    "solution architecture — a diagram slide is inserted for you."
)

_DEMO_SYSTEM = _COMMON + (
    "\n\nProduce a proof-of-concept scoping sheet.\n"
    'JSON: {"phases":[{"label","weeks","deliverable"}],"in_scope":[string],"out_scope":[string],'
    '"success_criteria":[{"criterion","measured_by"}],"customer_provides":[string]}\n'
    "Three or four phases, `weeks` an integer between 1 and 8. `out_scope` is the most important "
    "field on the sheet: name the things a customer will otherwise assume are included. "
    "`measured_by` must be something observable at the end of the PoC, not a feeling."
)

_RFP_SYSTEM = _COMMON + (
    "\n\nProduce reusable tender response blocks. These get pasted into a Word response and "
    "edited, so write finished prose in the first person plural ('we'), not notes.\n"
    'JSON: {"blocks":[{"section","answer"}]}\n'
    "Cover: our understanding of the requirement; proposed approach; architecture and "
    "integration; security and data protection; digital sovereignty and where data resides; "
    "service levels and support; relevant experience; transition and knowledge transfer. "
    "Each answer is two or three paragraphs. Leave a bracketed placeholder like "
    "[customer name] wherever the bid team must localise it."
)

_OUTREACH_SYSTEM = _COMMON + (
    "\n\nProduce an outreach email sequence built on the trigger events in the buying analysis.\n"
    'JSON: {"emails":[{"stage","subject","body"}]}\n'
    "Stages, in order: first touch, follow-up, value nudge, breakup, re-engagement. Subject lines "
    "under nine words, lower-case except proper nouns, no punctuation theatre. Bodies under 120 "
    "words, one ask each, no attachments mentioned. Address the operational pain, not the "
    "technology. Use [first name] and [company] as placeholders."
)

_PRICING_SYSTEM = _COMMON + (
    "\n\nProduce commercial model options. You are describing SHAPES, not prices — never state a "
    "price, a rate, a margin or a percentage.\n"
    'JSON: {"options":[{"model","how_it_works","orange_risk","customer_appeal","levers":[string],'
    '"use_when"}]}\n'
    "Three or four options drawn from: subscription, consumption-based, outcome-based, managed "
    "service, build-then-transfer. `orange_risk` and `customer_appeal` are each exactly one of: "
    "low, medium, high. `levers` are the commercial variables that move the deal — term, volume "
    "commitment, exclusivity, scope of managed responsibility."
)

_RISK_SYSTEM = _COMMON + (
    "\n\nProduce an internal bid risk register. This one is not shown to the customer, so it can "
    "be blunt about Orange's own weaknesses.\n"
    'JSON: {"risks":[{"risk","likelihood","impact","mitigation","owner_role"}]}\n'
    "Six to nine risks. `likelihood` and `impact` are each exactly one of: low, medium, high. "
    "Cover delivery, commercial, competitive, regulatory and internal-capability risks — a "
    "register that only lists competitor risks has not been thought about. `owner_role` is a "
    "role, never a person's name."
)

_PARTNER_SYSTEM = _COMMON + (
    "\n\nProduce a partner engagement brief. The portfolio path supplied to you shows where "
    "Orange's own capability stops.\n"
    'JSON: {"gaps":[{"capability","why_needed","candidate_type"}],"the_ask":string,'
    '"what_orange_brings":[string]}\n'
    "`candidate_type` is the KIND of partner needed (for example 'systems integrator with OT "
    "experience'), never a named company unless that company appears in the assets supplied. "
    "`the_ask` is the single specific thing this brief is requesting from the business unit or "
    "partner manager reading it."
)
