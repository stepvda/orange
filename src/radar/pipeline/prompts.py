"""Prompt construction (§4.4.2, §4.4.3).

Prompts are built from configuration rather than written as literals wherever
the content comes from a controlled vocabulary (NFR-11), so extending the
taxonomy extends the prompt automatically.

Prompt versions are constants here and are written onto every artefact the
prompt produces (DR-10, NFR-02). Changing a prompt means bumping its version —
otherwise the lineage claim in NFR-02 is false.
"""

from __future__ import annotations

import json
from typing import Any

from ..config import Config

PROMPT_VERSION_SYNTHESIS = "synth-v1"
PROMPT_VERSION_CRITIC = "critic-v1"
PROMPT_VERSION_RELEVANCE_RUBRIC = "strategic-relevance-v1"
PROMPT_VERSION_NEXT_ACTION = "next-action-v1"
PROMPT_VERSION_ENTAILMENT = "entail-v1"
PROMPT_VERSION_DESCRIPTION = "describe-v1"


# The six worked examples from the briefing. §4.4.2 calls these "unusually good
# few-shot anchors because they were written by the client and encode the
# intended granularity precisely".
POSITIVE_EXAMPLES = [
    "Private 5G plus edge vision for safety compliance in mining",
    "Agentic AI for claims deflection in insurance contact centres",
    "Digital product passports and traceability for materials producers",
    "Network-as-a-sensor security analytics for banking WANs",
    "Predictive worker-safety wearables for chemicals plants",
    "Sovereign cloud and AI enclaves for government citizen data",
]

# §4.4.2 negative examples, with the reason each fails.
NEGATIVE_EXAMPLES = [
    ("AI", "a technology, not an opportunity: no vertical, no use case, nothing to sell"),
    ("Cloud", "a delivery model, not an opportunity"),
    ("Cybersecurity", "a domain, not an opportunity"),
    ("Digital transformation in retail", "a vertical plus a slogan: no specific use case or technology"),
    ("AI in industry", "generic on both axes; a salesperson could not open a meeting with it"),
]


def orange_context_block(cfg: Config) -> str:
    """System context: who Orange Business is (§4.4.2 element 1)."""
    strategy = cfg.strategy
    ambitions = "\n".join(
        f"  - {a['label']}: {a['content'].strip()}\n    Radar implication: {a['radar_implication'].strip()}"
        for a in strategy["ambitions"]
    )
    privileged = ", ".join(strategy.get("privileged_verticals", {}))
    scale = cfg.assets.get("scale_reference", {})
    return f"""You are working for Orange Business, the enterprise division of the Orange Group.

WHO ORANGE BUSINESS IS
Orange Business positions itself simultaneously as operator, integrator and platform
player. Revenue €{scale.get('ob_revenue_2025_eur_bn')}bn (2025), {scale.get('ob_employees'):,} employees,
{scale.get('ob_b2b_customers'):,}+ B2B customers, coverage in {scale.get('countries_covered')}+ countries
with teams in {scale.get('countries_with_teams')}.

STRATEGIC FRAME — "{strategy['plan']}" ({strategy['period']})
{ambitions}

An opportunity space that connects to NONE of these three ambitions is, by the
Group's own definition, not strategically relevant. Discard it.

PRIVILEGED VERTICALS: {privileged}. Orange created dedicated divisions for these.

TRUST AND SOVEREIGNTY are a cross-cutting axis, not one topic among others. A
topic deliverable on sovereign, certified infrastructure is worth more to Orange
than the same topic delivered generically.

DIVISIONAL GUIDANCE: the division is expected to shift mix toward trusted,
higher-value services rather than to grow volume. Favour topics with a credible
margin story over topics that merely add revenue."""


def vocabulary_block(cfg: Config) -> str:
    """Controlled vocabularies (§4.4.2 element 2)."""
    return f"""CONTROLLED VOCABULARIES — you may emit ONLY these ids. Any other value fails
validation and the candidate is discarded.

VERTICALS ({len(cfg.verticals)}):
{cfg.verticals.prompt_block()}

USE CASES ({len(cfg.use_cases)}):
{cfg.use_cases.prompt_block()}

TECHNOLOGIES ({len(cfg.technologies)}):
{cfg.technologies.prompt_block()}

BUSINESS DOMAINS ({len(cfg.domains)}):
{cfg.domains.prompt_block(include_definitions=False)}

CUSTOMER PERSONAS ({len(cfg.personas)}):
{cfg.personas.prompt_block(include_definitions=False)}"""


def examples_block() -> str:
    positives = "\n".join(f"  GOOD: {e}" for e in POSITIVE_EXAMPLES)
    negatives = "\n".join(f"  BAD: \"{text}\" — {why}" for text, why in NEGATIVE_EXAMPLES)
    return f"""WHAT SPECIFICITY MEANS
These were written by the client and encode the intended granularity exactly:
{positives}

These fail and must never be emitted:
{negatives}

The test: could a salesperson open a customer meeting on Thursday with this
sentence, and would the customer know it was about them?"""


def synthesis_system_prompt(cfg: Config) -> str:
    """The core synthesis prompt (§4.4.2)."""
    return f"""MOCK_KIND=synthesis
{orange_context_block(cfg)}

YOUR TASK
You are given a cluster of dated, attributable evidence. Produce candidate
OPPORTUNITY SPACES, each defined as exactly:

    Vertical  x  Use Case  x  Technology

plus a human-readable opportunity statement.

{vocabulary_block(cfg)}

{examples_block()}

ABSOLUTE RULES — violating any of these invalidates the candidate
1. EVIDENCE ONLY. The evidence block is the only factual material you may use.
   You are reorganising retrieved evidence, not recalling what you know. If the
   evidence does not support a candidate, do not produce that candidate.
2. EVERY CLAIM IS CITED. Each entry in `why_hot` must carry a non-empty
   `signals` array of signal ids drawn from the evidence block. An uncited claim
   is stripped, not rewritten.
3. CLOSED VOCABULARY. `vertical`, `use_case` and `technology` must each be
   exactly one id from the lists above. Not two. Not a new one.
4. NO NUMBERS. Never state a market size, growth rate, percentage or monetary
   value. If the evidence contains one, you may cite the signal, but express the
   magnitude qualitatively.
5. FEWER, BETTER. Produce only candidates the evidence genuinely supports. An
   empty list is a valid and often correct answer.

OUTPUT — a single JSON object:
{{
  "candidates": [
    {{
      "vertical": "<vertical id>",
      "use_case": "<use case id>",
      "technology": "<technology id>",
      "statement": "<one specific sentence, 40-180 characters>",
      "domains": ["<domain id>", ...],
      "personas": ["<persona id>", ...],
      "geographies": ["<ISO 3166-1 alpha-2 code or EU>", ...],
      "why_hot": [
        {{"claim": "<one sentence, no invented numbers>", "signals": ["SIG-...", ...]}}
      ],
      "why_specific": "<why this is not a generic theme>"
    }}
  ]
}}"""


def synthesis_user_prompt(cluster: dict[str, Any], target_cells: list[dict[str, str]] | None = None,
                          lens: str | None = None, constraints: list[str] | None = None,
                          brief: str | None = None, avoid: list[str] | None = None) -> str:
    """Evidence block (§4.4.2 element 3), optionally targeted at empty grid cells.

    `lens` steers one generation pass toward a particular kind of evidence.
    §4.4.3: an open-ended loop "elaborates around whatever it produced first",
    so several passes over the same cluster need different starting points to
    explore rather than paraphrase.

    `constraints` are the operator's bounds from the Generate screen, already
    phrased by the caller. They are stated LAST and as hard rules, because they
    narrow the answer rather than steering it — and every one of them that can
    be checked is checked again after the model replies (§4.4.4: the prompt asks,
    the validator decides).

    `brief` is a written description of the opportunity somebody is looking for.
    It appears AFTER the evidence and is explicitly demoted to a request rather
    than a fact, because the failure mode it invites is the one §4.4.4 defence 1
    exists to stop: a model handed a plausible sentence and a pile of documents
    will happily assert the sentence and cite the documents. The evidence block
    stays the only factual material, and the brief only says which part of it to
    look at.
    """
    lines = [
        f"THEME CLUSTER {cluster['cluster_id']}: {cluster.get('label') or '(unlabelled)'}",
        f"Keyphrases: {cluster.get('keyphrases')}",
        "",
        "EVIDENCE — these are the only facts you may use:",
    ]
    for signal in cluster["signals"]:
        geographies = signal.get("geographies") or "[]"
        lines.append(
            f"- [{signal['id']}] ({signal['published_at']}, {signal['publisher']}, "
            f"tier {signal['tier']}, type {signal.get('signal_type') or 'unclassified'}, geo {geographies})\n"
            f"  {signal['title']}\n"
            f"  {signal['extract'][:500]}"
        )

    if avoid:
        # §4.4.5 makes the taxonomy triple the canonical identity, so a candidate
        # landing on an occupied cell is not a new opportunity space — it is an
        # update to one that exists. That is the right behaviour on a refresh and
        # the wrong answer to "find me five more", and the model cannot avoid a
        # collision it was never told about. Stated as cells rather than
        # statements because the cell is what identity is defined on.
        lines += [
            "",
            "ALREADY IN THE RADAR — these taxonomy cells are taken.",
            "A candidate landing on one of them updates the existing space rather than",
            "creating anything, so it does not answer the request. Propose a DIFFERENT",
            "cell that this evidence also supports — a different technology against the",
            "same use case, a different vertical facing the same problem, a narrower use",
            "case within the same domain. If the evidence supports nothing outside this",
            "list, return an empty list; that is a real answer.",
        ]
        lines += [f"  - {cell}" for cell in avoid]

    if target_cells:
        # §4.4.3 coverage-driven prompting: the pipeline knows which taxonomy
        # cells have evidence and no candidate yet, and targets generation at
        # exactly those cells. This turns brainstorming from "produce more
        # ideas" into "cover the evidenced grid", which terminates.
        lines += [
            "",
            "COVERAGE TARGETS — these taxonomy cells have evidence but no candidate yet.",
            "If and only if this cluster's evidence supports them, prioritise:",
        ]
        lines += [
            f"  - {c['vertical']} x {c['use_case']} x {c['technology']}" for c in target_cells[:10]
        ]

    if brief:
        lines += [
            "",
            "WHAT THE USER IS LOOKING FOR — this is a REQUEST, not evidence.",
            "It came from a person typing a sentence. Nothing in it is a fact you may",
            "assert or cite. Use it only to decide which part of the evidence above to",
            "reason from, and to judge whether that evidence supports a space of this",
            "kind at all.",
            "",
            f"    \"{brief}\"",
            "",
            "If the evidence above does not support an opportunity space along these",
            "lines, return an empty candidate list. Do NOT restate the request as though",
            "the evidence established it — that is the single failure this pipeline is",
            "built to prevent. Produce AT MOST ONE candidate.",
        ]

    if constraints:
        lines += [
            "",
            "REQUESTED SCOPE — a candidate outside this is discarded, not corrected.",
            "Producing nothing is the right answer if this cluster's evidence does not",
            "support anything inside it. Do not stretch a candidate to fit.",
        ]
        lines += constraints

    if lens:
        lines += ["", f"THIS PASS'S LENS: {lens}",
                  "Other passes cover other angles, so do not try to be exhaustive here — "
                  "follow this lens and let it take you somewhere specific."]

    lines += [
        "",
        "Produce candidate opportunity spaces grounded strictly in the evidence above.",
        "Return JSON only.",
    ]
    return "\n".join(lines)


def critic_system_prompt(cfg: Config) -> str:
    """Adversarial critique pass (§4.4.3).

    "In practice the critic pass improves output quality more than any amount of
    prompt refinement on the generator." A different system prompt is the point:
    the critic is not the generator being asked to check itself.
    """
    return f"""MOCK_KIND=critic
You are a hostile reviewer of proposed innovation topics for Orange Business.
Your job is to REJECT weak candidates, not to be helpful. Assume the candidate
is generic until it proves otherwise.

{examples_block()}

Score the candidate 1-5 against ALL of these tests. The score is the MINIMUM of
your per-test judgements — one failure caps the whole score.

  A. SPECIFIC ENOUGH FOR A CIO. Could a salesperson put this in front of a CIO
     and have them recognise their own situation? "AI in industry" fails.
  B. EVERY CLAIM CITED. Is every `why_hot` claim supported by a cited signal id
     that actually appears in the evidence? An uncited claim fails this test.
  C. DISTINGUISHABLE. Is this meaningfully different from its neighbouring
     candidates, or is it the same topic with a synonym swapped?
  D. ACTIONABLE. Would a salesperson know what to actually say? Would a presales
     person know what to assemble?
  E. NO INVENTED FACTS. Does any claim state a number, date or fact absent from
     the evidence?

Scoring anchors:
  5 — as good as the client's own worked examples; ship it
  4 — specific and actionable, minor wording issues
  3 — borderline: real topic, but the statement is vague or a claim is thin
  2 — generic, or a claim is uncited
  1 — a technology theme wearing an opportunity's clothes, or contains invention

Return JSON:
{{"score": 1-5, "verdict": "accept"|"revise"|"reject",
  "issues": ["<specific, actionable>", ...],
  "revised_statement": "<only if verdict is revise; else null>"}}"""


def strategic_relevance_prompt(cfg: Config) -> str:
    """Rubric-scored strategic relevance (Table 23, §4.6).

    §4.6 score-compression guard: models asked to rate on 0-100 cluster their
    answers in a narrow band, so the rubric uses a small number of discrete
    levels with anchor examples, mapped to numbers afterwards.
    """
    strategy = cfg.strategy
    ambitions = "\n".join(f"  - {a['label']}: {a['content'].strip()}" for a in strategy["ambitions"])
    privileged = ", ".join(strategy.get("privileged_verticals", {}))
    return f"""MOCK_KIND=relevance
You score how strategically relevant an opportunity space is to Orange Business.

"{strategy['plan']}" ambitions:
{ambitions}

Privileged verticals (dedicated divisions): {privileged}
Cross-cutting: trust, sovereignty and compliance raise relevance wherever the
topic can be delivered on sovereign or certified infrastructure.
Divisional guidance: prefer a credible margin story over pure revenue volume.

Score on this DISCRETE 0-5 scale. Do not use intermediate values.
  5 — Squarely inside Innovative growth: a trusted B2B service, cyberdefence,
      trusted cloud or trusted AI, ideally in a privileged vertical.
  4 — Clearly serves one ambition with a credible Orange delivery story.
  3 — Plausibly connected to an ambition, but the connection needs an argument.
  2 — Adjacent: Orange could sell it, but it advances no stated ambition.
  1 — Weakly connected; would be a distraction from the plan.
  0 — Connects to none of the three ambitions. By the Group's own definition,
      not strategically relevant.

Return JSON:
{{"level": 0-5,
  "ambitions": ["<ambition id: customer_intimacy|innovative_growth|excellence_at_scale>", ...],
  "sovereignty_relevant": true|false,
  "rationale": "<two sentences, no invented numbers>"}}"""


def next_action_prompt(cfg: Config) -> str:
    """Role-specific next action (FR-17, AC-03, Table 23)."""
    modes = "\n".join(
        f"  - {m['id']} ({m['label']}): {m['description']} Primary action: {m['primary_action']}."
        for m in cfg.role_modes_raw["modes"]
    )
    return f"""You write the single next action a named role should take on an opportunity space.

ROLES
{modes}

Rules:
  - One sentence per role. Imperative. Concrete.
  - Ground it in the named Orange assets supplied to you. If none are supplied
    for a role, say what to find out, not what to claim.
  - Never invent a number, an offer name or a partner tier.
  - NEVER NAME A CUSTOMER OR PROSPECT ORGANISATION that is not in the supplied
    asset list. Naming a plausible-sounding account is the most damaging failure
    here, because a salesperson may repeat it as though it were a known Orange
    relationship.
      BAD:  "In a meeting with the head of security at Heathrow, say…"
            (Heathrow was never supplied — invented account)
      GOOD: "In a meeting with a major airport operator's head of security, say…"
      GOOD: "Reach out to Saint-Gobain Glass…"  (only if supplied as a reference)
  - Refer to unnamed prospects by ROLE AND SEGMENT instead: "a European airport
    operator", "a tier-1 automotive supplier".
  - The sales action must be something a person could actually say out loud in a
    customer meeting.

Return JSON:
{{"strategist": "...", "sales": "...", "presales": "...",
  "assets_named": ["<each Orange asset or customer organisation you named, verbatim>"]}}

`assets_named` is validated against the supplied list. Listing something that
was not supplied causes the action to be rejected, so name nothing you were not
given."""


def entailment_prompt() -> str:
    """Entailment check on key claims (§4.4.4 defence 4).

    "For the 'why hot' sentence, a cheap second-model pass verifies that the
    claim is entailed by the cited span. Cost is low because the text is short."
    """
    return """You verify whether a claim is supported by an evidence span.

Answer strictly on what the span says. Do not use outside knowledge. If the span
is merely ABOUT the same topic but does not state the claim, that is "unsupported".

Return JSON: {"supported": true|false, "reason": "<short>"}"""


def format_candidate_for_critic(candidate: dict[str, Any], evidence: list[dict[str, Any]],
                               neighbours: list[str]) -> str:
    lines = [
        "CANDIDATE",
        json.dumps(
            {k: candidate.get(k) for k in
             ("vertical", "use_case", "technology", "statement", "why_hot", "why_specific")},
            ensure_ascii=False, indent=2,
        ),
        "",
        "EVIDENCE AVAILABLE (cited ids must appear here):",
    ]
    for signal in evidence:
        lines.append(f"- [{signal['id']}] {signal['title']} ({signal['publisher']}, {signal['published_at']})")
        lines.append(f"  {signal['extract'][:300]}")
    if neighbours:
        lines += ["", "NEIGHBOURING CANDIDATES (test C — is this distinguishable?):"]
        lines += [f"  - {n}" for n in neighbours[:5]]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Long-form description and sales brief (FR-14, FR-17, FR-18)
# ---------------------------------------------------------------------------

#: Sections that assert something about the world, and therefore must cite the
#: evidence they were written from. The others describe what Orange would do or
#: ask — a proposal and a question cannot be "supported by a source", and
#: demanding a citation for them would only teach the model to attach one at
#: random (§4.4.4's binding rule works precisely because it is not decorative).
CITED_SECTIONS = ("what_is_changing", "competitive_landscape")

DESCRIPTION_SECTIONS = {
    "summary": "Two or three sentences a salesperson could read out. What the opportunity is, "
               "for whom, and why it exists now.",
    "what_is_changing": "What has changed in the market to open this. Regulation, technology "
                        "maturity, buying behaviour. EVERY claim cited.",
    "who_buys_and_why": "Which role signs, which role feels the pain, and what event triggers "
                        "them to act. Be concrete about the pain in operational terms.",
    "what_orange_would_deliver": "The shape of the engagement, built ONLY from the named Orange "
                                 "assets supplied. What is assembled, in what order.",
    "why_orange_can_win": "The specific reason Orange rather than the alternatives — named assets "
                          "only. If the assets are thin, say so plainly instead of inflating them.",
    "competitive_landscape": "Who else sells into this and how the customer will frame the "
                             "comparison. ONLY the competitors supplied, and say what each is "
                             "strong at. Cite the evidence where a competitor was named in it.",
    "risks_and_unknowns": "What would make this fail or stall, and what is genuinely not known "
                          "yet. A brief a salesperson trusts is one that admits something.",
}


def description_system_prompt(cfg: Config) -> str:
    """Long-form topic description (§4.9, FR-18).

    §4.9 says the topic page should answer the user's questions "in the order
    they arrive", and §4.13 asks the brief to be something a salesperson can act
    on. That needs prose — but prose is exactly where a model starts inventing,
    so the same four defences as synthesis apply (§4.4.4), plus the named-entity
    rule from the next-action prompt: naming a customer or a competitor that was
    not supplied is the failure most likely to be repeated in a meeting as if it
    were fact.
    """
    sections = "\n".join(f"  - {name}: {guidance}" for name, guidance in DESCRIPTION_SECTIONS.items())
    return f"""{orange_context_block(cfg)}

YOUR TASK
Write the detailed description of ONE opportunity space, for an Orange Business
sales and presales audience preparing a real customer conversation.

SECTIONS
{sections}

Plus a SOLUTION DIAGRAM and two practical blocks:
  - qualifying_questions: 4 to 6 questions to ask in a first meeting that would
    establish whether this customer actually has this problem. Specific enough
    that the answer changes what you do next. No generic discovery questions.
  - objection_handling: 2 to 4 objections this specific proposition will meet,
    each with a response that concedes what is true before answering.
  - diagram: the solution, drawn as layers. You are NOT drawing it — you are
    describing its structure, and the brief renders it. Three to five layers,
    ordered from the customer's business outcome at the top down to the field,
    site or device at the bottom. One to four boxes per layer. `provider` says
    who supplies each box: "orange" ONLY for a supplied Orange asset, named
    exactly as supplied; "partner" for a supplied partner; "customer" for
    something the customer already owns; "third_party" otherwise. Flows connect
    two boxes by their exact labels and say what moves between them.

ABSOLUTE RULES — a violation invalidates the section
1. EVIDENCE ONLY. The supplied evidence, Orange assets and competitor list are
   the only factual material you may use. You are organising what you were
   given, not recalling what you know.
2. CITE THE FACTUAL SECTIONS. {', '.join(CITED_SECTIONS)} must each carry a
   non-empty `signals` array of signal ids taken from the evidence block. An
   uncited factual section is discarded, not rewritten.
3. NO NUMBERS. Never state a market size, growth rate, percentage, monetary
   value or headcount. The brief carries computed figures from the sizing
   engine; anything you write would contradict them and be wrong.
4. NAME NOTHING YOU WERE NOT GIVEN. No customer, prospect, partner or competitor
   beyond the supplied lists. Refer to unnamed prospects by role and segment —
   "a European airport operator", "a tier-1 automotive supplier".
5. NO FILLER. If a section has nothing substantive behind it, write one honest
   sentence saying what is missing rather than three vague ones.

OUTPUT — a single JSON object:
{{
  "sections": {{
    "<section name>": {{"text": "<prose, 2-5 sentences>", "signals": ["SIG-...", ...]}}
  }},
  "qualifying_questions": ["<question>", ...],
  "objection_handling": [{{"objection": "<what they will say>", "response": "<answer>"}}],
  "diagram": {{
    "title": "<4-8 words>",
    "layers": [
      {{"label": "<layer name, 2-4 words>",
        "nodes": [{{"label": "<2-5 words>", "provider": "orange|partner|customer|third_party"}}]}}
    ],
    "flows": [{{"from": "<exact node label>", "to": "<exact node label>", "label": "<1-4 words>"}}],
    "caption": "<one sentence: what this picture tells a customer>"
  }},
  "entities_named": ["<every organisation you named, verbatim>"]
}}

`entities_named` is validated against the supplied lists. Naming something that
was not supplied causes that section to be dropped, so name nothing you were not
given."""


def format_topic_for_description(topic: dict[str, Any], signals: list[dict[str, Any]],
                                 assets: dict[str, list[str]], competition: dict[str, Any] | None,
                                 labels: dict[str, str]) -> str:
    """The evidence block for one topic (§4.4.2 element 3)."""
    lines = [
        f"OPPORTUNITY SPACE {topic['id']}",
        f"Statement: {topic['statement']}",
        f"Vertical: {labels['vertical']}",
        f"Use case: {labels['use_case']}",
        f"Technology: {labels['technology']}",
        f"Time horizon: {topic.get('horizon')} (basis: {topic.get('horizon_basis')})",
        f"Lifecycle state: {topic.get('state')}",
        "",
        "EVIDENCE — the only facts you may use. Cite by id:",
    ]
    for signal in signals[:20]:
        lines.append(
            f"- [{signal['id']}] ({signal['published_at']}, {signal['publisher']}, tier {signal['tier']})\n"
            f"  {signal['title']}\n  {signal['extract'][:420]}"
        )

    lines += ["", "EVIDENCE-BOUND CLAIMS ALREADY ESTABLISHED FOR THIS TOPIC:"]
    for claim in topic.get("why_hot") or []:
        lines.append(f"  - {claim.get('claim')}  [{', '.join(claim.get('signals', []))}]")

    lines += ["", "NAMED ORANGE ASSETS LINKED TO THIS TOPIC — the only assets you may name:"]
    if assets:
        for kind, values in sorted(assets.items()):
            lines.append(f"  {kind}: {', '.join(values[:6])}")
    else:
        lines.append("  (none linked — say plainly that there is no proof point yet)")

    if competition and competition.get("competitors"):
        lines += ["", f"COMPETITORS — the only competitors you may name. "
                      f"Assessed intensity: {competition['level_label'].upper()}."]
        for entry in competition["competitors"]:
            relationship = {"both": " (also an Orange partner)", "partner": " (Orange partner)"}.get(
                entry.get("relationship"), ""
            )
            mentioned = (" — named in evidence " + ", ".join(m["signal_id"] for m in entry.get("mentions", [])[:3])
                         if entry.get("basis") == "evidenced" else "")
            lines.append(f"  - {entry['label']} [{entry.get('type_label')}]{relationship}: "
                         f"{entry.get('why', '')}{mentioned}")
    else:
        lines += ["", "COMPETITORS: none identified. Say that the field looks open and that this "
                      "is worth verifying, rather than asserting there is no competition."]

    lines += [
        "",
        "For the diagram: the boxes marked `orange` must be assets from the list above, named "
        "exactly as they appear there. If no Orange asset is listed, mark every box `third_party` "
        "or `customer` and let the picture show honestly what would have to be assembled.",
        "",
        "Write the description. Return JSON only.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Competitor profiling (§4.3.3 extension)
# ---------------------------------------------------------------------------

PROMPT_VERSION_COMPETITOR_PROFILE = "cprofile-v1"
PROMPT_VERSION_COMPETITOR_ANALYSIS = "canalysis-v1"


def competitor_profile_system_prompt(cfg: Config) -> str:
    """Turn one competitor's own pages into a structured profile.

    The input is marketing copy: the most self-serving text a company produces.
    That is fine, because the question being asked of it is not "is this true"
    but "what does this company say it sells, and to whom" — and for that
    question the vendor is the primary source.

    What it must not become is a set of assertions the radar then repeats as
    fact. So the same defences as synthesis apply: every claim carries the page
    that made it, taxonomy values come from the closed vocabulary, and a number
    on a marketing page is still a number a model may not restate.
    """
    return f"""{vocabulary_block(cfg)}

YOUR TASK
You are reading pages published by ONE company, taken from its own website.
Produce a structured profile of what that company says it sells, to whom, and
with what.

This is competitive intelligence for Orange Business. It will be shown next to
an Orange opportunity space, so it has to be accurate about the competitor and
useless as marketing. Describe their position; do not adopt their language.

ABSOLUTE RULES — a violation drops the claim or the whole field
1. THEIR PAGES ONLY. The supplied page extracts are the only material you may
   use. You may not add anything you happen to know about this company —
   including facts that are true. An unsupported claim is worse than a thin
   profile, because a thin profile is honest about what was read.
2. CITE EVERY CLAIM. Each entry in `claims` carries a `pages` array of page ids
   from the supplied block. An uncited claim is discarded, not rewritten.
3. CLOSED VOCABULARY. `verticals`, `use_cases` and `technologies` must be ids
   from the vocabulary above. If their page describes something with no id in
   the vocabulary, leave it out rather than inventing an id or stretching one.
4. NO NUMBERS. No market share, growth rate, customer count, revenue or
   percentage — not even one they printed themselves. Marketing figures are
   unmethodical by construction and the radar publishes only computed ones.
5. NAME ONLY THEIR OWN THINGS. `named_offers` are product or service names this
   company uses for its own offerings, spelled as they spell them. Do not name
   their customers, and do not name Orange.
6. SAY WHAT IS ABSENT. If the pages do not establish which verticals they serve,
   return an empty array. Silence is a finding; a guess is a defect.

OUTPUT — a single JSON object:
{{
  "positioning": "<2-4 sentences: what this company presents itself as, and to whom. Neutral register.>",
  "claims": [
    {{"claim": "<one specific thing they say they do>", "pages": ["<page id>", ...]}}
  ],
  "verticals": ["<vocabulary id>", ...],
  "use_cases": ["<vocabulary id>", ...],
  "technologies": ["<vocabulary id>", ...],
  "named_offers": [{{"name": "<their own product name>", "pages": ["<page id>", ...]}}],
  "go_to_market": "<1-2 sentences: direct, channel, partner-led, platform — only if the pages say>"
}}

Six to twelve claims. Prefer the specific over the sweeping: "runs a managed SOC
with regional analysts" beats "is a leader in cybersecurity"."""


def format_competitor_for_profile(entry: dict[str, Any], pages: list[dict[str, Any]]) -> str:
    """The page block for one competitor."""
    lines = [
        f"COMPANY: {entry['label']}",
        f"Register type: {entry.get('type')}",
        f"Website: {entry.get('website')}",
        "",
        "PAGES (id | kind | title | extract)",
    ]
    for page in pages:
        title = (page.get("title") or "").strip()
        lines.append(
            f"[{page['id']}] ({page.get('kind')}) {title}\n    {page.get('extract', '')[:1800]}"
        )
    lines += [
        "",
        "Cite page ids exactly as they appear in square brackets above.",
    ]
    return "\n".join(lines)


def competitor_analysis_system_prompt(cfg: Config) -> str:
    """Compare the competitors matched to one opportunity space, and say how
    Orange differentiates against each of them individually.

    The differentiation paragraph is the part a salesperson actually uses, and
    it is also the part most likely to become a slogan. Two constraints keep it
    honest: it may only cite Orange assets that are LINKED to this topic in the
    business graph, and it must name a real asymmetry rather than assert
    superiority. Where Orange has nothing to differentiate with, it has to say
    so — a fabricated advantage is discovered in the meeting.
    """
    return f"""{orange_context_block(cfg)}

YOUR TASK
One Orange Business opportunity space, and the competitors the register has
matched to it. For each competitor, write two things:

  activity        What this competitor is doing in THIS space — grounded in
                  their own published pages, cited by page id. If their pages
                  say nothing about this space, say that instead of inferring.

  differentiation One paragraph on how Orange differentiates against THIS
                  competitor specifically, for THIS opportunity. Not a general
                  Orange pitch — the asymmetry between these two companies here.

Then one short `field` paragraph on the shape of the field as a whole.

WHAT MAKES A DIFFERENTIATION PARAGRAPH USABLE
  * It names the asymmetry. Sovereignty and EU data residency against a
    hyperscaler; an owned network and field operations against a systems
    integrator; integration breadth against a point specialist; regulatory
    footing against a vendor with no European compliance story.
  * It is anchored in a SUPPLIED Orange asset — a named offer, a named
    certification, a named partner at its tier, or a published reference in this
    vertical. If none was supplied, the honest paragraph says Orange would be
    competing on price and delivery rather than on a structural advantage.
  * It concedes what is true. A paragraph that gives the competitor nothing
    reads as marketing and gets discounted whole.
  * It is actionable: what to lead with, and what to avoid arguing about.

ABSOLUTE RULES — a violation drops that competitor's entry
1. SUPPLIED MATERIAL ONLY. Competitor page extracts, Orange linked assets, and
   the topic's own evidence. Nothing else, including things you know.
2. CITE ACTIVITY. `activity` carries `pages` — page ids from that competitor's
   block. No pages means the activity text must say the pages are silent on this
   space, and `pages` is empty.
3. NAME ONLY SUPPLIED ORANGE ASSETS in `differentiation`, spelled exactly as
   supplied. `orange_assets` lists the ones you used and is validated.
4. NO NUMBERS anywhere. No market share, no growth rate, no percentage, no
   monetary value — the brief carries computed figures and yours would contradict
   them.
5. NO CUSTOMER NAMES beyond the published references supplied to you.
6. NO SUPERLATIVES ABOUT ORANGE. "Better", "leading" and "best-in-class" are not
   differentiators; a named capability the competitor demonstrably lacks is.

OUTPUT — a single JSON object:
{{
  "competitors": [
    {{
      "id": "<competitor id, exactly as supplied>",
      "activity": {{"text": "<2-4 sentences>", "pages": ["<page id>", ...]}},
      "differentiation": "<one paragraph, 3-5 sentences>",
      "orange_assets": ["<supplied asset name used>", ...],
      "concession": "<one sentence: what this competitor genuinely does better here>"
    }}
  ],
  "field": "<3-5 sentences on the shape of the field and where the gap is>"
}}

Return an entry for every competitor supplied, in the order supplied."""


def format_topic_for_competitor_analysis(topic: dict[str, Any], labels: dict[str, str],
                                         entries: list[dict[str, Any]],
                                         assets: dict[str, list[str]],
                                         signals: list[dict[str, Any]]) -> str:
    """The evidence block for one topic's competitive analysis."""
    lines = [
        f"OPPORTUNITY SPACE {topic['id']}",
        f"Statement: {topic['statement']}",
        f"Vertical: {labels.get('vertical')}  |  Use case: {labels.get('use_case')}  "
        f"|  Technology: {labels.get('technology')}",
        "",
        "ORANGE ASSETS LINKED TO THIS SPACE — the only Orange things you may name",
    ]
    if any(assets.values()):
        for kind, names in assets.items():
            if names:
                lines.append(f"  {kind}: {', '.join(names)}")
    else:
        lines.append("  (none linked — say so rather than inventing an advantage)")

    lines += ["", "WHY THIS SPACE IS LIVE (topic evidence, for context only)"]
    for sig in signals[:8]:
        lines.append(f"  - {sig.get('title', '')[:160]} ({sig.get('publisher')})")

    lines += ["", "COMPETITORS MATCHED TO THIS SPACE"]
    for entry in entries:
        lines.append("")
        lines.append(f"COMPETITOR id={entry['id']}  {entry['label']}  "
                     f"[type: {entry.get('type_label', entry.get('type'))}]")
        lines.append(f"  Presence: {entry.get('basis')}  |  Orange relationship: "
                     f"{entry.get('relationship', 'competitor')}")
        if entry.get("profile_status") != "profiled":
            lines.append(f"  NO PROFILE — {entry.get('profile_status')}: "
                         f"{entry.get('profile_reason') or 'their site was not read'}. "
                         f"Say that their published position is unread rather than inferring one.")
            continue
        if entry.get("positioning"):
            lines.append(f"  Positioning: {entry['positioning']}")
        for claim in entry.get("relevant_claims", [])[:8]:
            pages = ", ".join(claim.get("pages", []))
            lines.append(f"  [{pages}] {claim.get('claim')}")
        if entry.get("named_offers"):
            lines.append(f"  Their named offers: {', '.join(entry['named_offers'][:8])}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# The Planner narrative
# ---------------------------------------------------------------------------

PROMPT_VERSION_PLAN = "plan-v1"

PLAN_SECTIONS = {
    "thesis": "The investment thesis in three or four sentences. What is the coherent bet "
              "this portfolio makes, and why now? Not a list of the spaces — the argument that "
              "connects them.",
    "why_these": "Why this set rather than the obvious alternatives. Refer to the selection "
                 "criteria that actually bound: capability capacity, entry slots, concentration "
                 "limits, evidence confidence.",
    "sequence": "The entry sequence and what it buys. Which spaces start first, what they "
                "establish for the ones that follow, and why the later cohorts wait.",
    "capacity": "The execution story. Which capability pools this plan commits, where it runs "
                "hot, and what that means for hiring or partnering.",
    "risks": "The three or four things most likely to make this plan wrong, stated plainly. "
             "Include the ones the computed flags raise.",
    "not_doing": "What was deliberately left out and why. Name the constraint, not a preference.",
}


def plan_system_prompt(cfg: Config) -> str:
    """Write the business plan for a computed portfolio.

    Every figure on the page was computed before this prompt ran. The model's
    job is to explain a plan, not to produce one — so the numeric guard is
    absolute here, more than anywhere else in the product: a plan that contradicts
    its own projection table is worse than a plan with no prose at all.
    """
    sections = "\n".join(f"  - {name}: {guide}" for name, guide in PLAN_SECTIONS.items())
    return f"""{orange_context_block(cfg)}

YOUR TASK
Write the narrative of a five-year business plan for Orange Business. The
portfolio has ALREADY BEEN SELECTED and the projection ALREADY COMPUTED by an
optimiser. You are explaining a decision, not making one.

The audience is an Orange Business executive committee. They will ask where every
number came from, and the answer has to be "the model computed it", never "the
plan asserts it".

SECTIONS
{sections}

ABSOLUTE RULES — a violation drops the section
1. NO NUMBERS. Not one. No euro figure, no percentage, no headcount, no year-on-year
   change — not even one that appears in the supplied data. Every figure is already
   in the projection table beside your prose, and a sentence of yours that disagrees
   with it is a defect the reader has to adjudicate. Refer to magnitudes in words:
   "the largest single contributor", "roughly a third of the portfolio", "the pool
   that runs hottest".
2. ONLY THE SUPPLIED SPACES. Name opportunity spaces only from the selected list,
   by their statement or their id. Do not invent a space, and do not name one that
   was excluded as though it were in.
3. ONLY SUPPLIED ORANGE ASSETS. Offers, certifications, partners and capability
   pools only as supplied. Never a customer name.
4. THE CONSTRAINTS ARE THE ARGUMENT. This plan is shaped by what bound it —
   capability capacity, entry slots, concentration caps. Say so. A plan that reads
   as though everything desirable was chosen is not describing an optimiser's output.
5. CONCEDE THE UNCERTAINTY. The projection rests on declared assumption bands and
   on obtainable-share figures that are planning assumptions rather than forecasts.
   The `risks` section must say this in plain words.
6. NO SUPERLATIVES about Orange. A named capability is an argument; "world-leading"
   is not.

OUTPUT — a single JSON object:
{{
  "sections": {{ "<section name>": "<prose, 3-6 sentences>" }},
  "headline": "<one sentence a CEO could repeat, no numbers>",
  "spaces_named": ["<every opportunity space id you referred to>"]
}}

`spaces_named` is validated against the selected list."""


def format_plan_for_narrative(plan: dict[str, Any]) -> str:
    """The computed plan, as the evidence block for its own narrative."""
    proj = plan.get("projection") or {}
    mix = proj.get("mix") or {}
    lines = [
        f"PLAN {plan['id']} — {plan.get('label')}",
        f"Objective: {plan.get('objective')} over {plan.get('plan_years')} years",
        f"Selected {plan.get('selected_count')} spaces from {plan.get('considered_count')} admissible candidates.",
        "",
        "PORTFOLIO SHAPE (shares, for your qualitative description only)",
    ]
    for key in ("vertical", "horizon", "distance"):
        entries = mix.get(key) or []
        if entries:
            lines.append(f"  by {key}: " + ", ".join(
                f"{e['key']} {e['share']:.0%}" for e in entries[:6]))

    lines += ["", "ENTRY SEQUENCE"]
    by_year: dict[int, list[dict]] = {}
    for s in plan.get("selections", []):
        by_year.setdefault(s["entry_year"], []).append(s)
    for year in sorted(by_year):
        lines.append(f"  YEAR {year} — {len(by_year[year])} space(s) enter:")
        for s in by_year[year][:8]:
            lines.append(f"    [{s['opportunity_id']}] {s['statement'][:110]}")
            lines.append(f"       {s['vertical']} · L{s['portfolio_distance']} · "
                         f"{s['horizon']} · pool: {s.get('pool') or 'unassigned'}")

    cap = plan.get("capacity_usage") or {}
    lines += ["", "CAPABILITY POOLS COMMITTED (utilisation as a share, for description)"]
    for pool, data in (cap.get("pools") or {}).items():
        util = data.get("peak_utilisation")
        if util:
            lines.append(f"  {pool}: peaks at {util:.0%} of the share available for new work")
    if cap.get("binding"):
        lines += ["", "WHAT BOUND THIS PLAN — the constraints that were hit:"]
        lines += [f"  - {b}" for b in cap["binding"]]

    if plan.get("flags"):
        lines += ["", "COMPUTED WARNINGS — these must be reflected in `risks`:"]
        for f in plan["flags"]:
            lines.append(f"  - [{f['severity']}] {f['message']}")

    exc = plan.get("exclusions") or []
    if exc:
        lines += ["", "NOTABLE EXCLUSIONS — for the `not_doing` section:"]
        for e in exc[:8]:
            lines.append(f"  [{e['opportunity_id']}] {e['statement'][:90]} — {e['reason']}")

    a = plan.get("assumptions") or {}
    lines += ["", "ASSUMPTIONS THIS PLAN RESTS ON (describe qualitatively, quote no figures):",
              "  Margin varies by portfolio distance, anchored on Orange's filed segment margin.",
              "  Revenue ramps from each space's own entry year, by time horizon.",
              "  Obtainable share is a planning assumption, discounted where selected spaces",
              "  compete for the same buying centre.",
              f"  Economics version: {a.get('economics_version')} · owner: {a.get('owner')}"]
    return "\n".join(lines)
