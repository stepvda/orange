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

PROMPT_VERSION_PLAN = "plan-v2"

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


def plan_system_prompt(cfg: Config, source: str = "parameters") -> str:
    """Write the business plan for a computed portfolio.

    Every figure on the page was computed before this prompt ran. The model's
    job is to explain a plan, not to produce one — so the numeric guard is
    absolute here, more than anywhere else in the product: a plan that contradicts
    its own projection table is worse than a plan with no prose at all.

    WHO CHOSE THE SET changes what the prose can honestly claim. A plan built
    from parameters is an optimiser's answer, and its argument is the constraints
    that bound. A plan built from the workflow is a set of human decisions
    already taken, and describing it as though an optimiser weighed the
    alternatives would attribute a judgement nobody made.
    """
    sections = "\n".join(f"  - {name}: {guide}" for name, guide in PLAN_SECTIONS.items())
    if source == "workflow":
        origin = """The portfolio was NOT selected by an optimiser. It is every opportunity space
that Orange's own collaboration workflow has moved past a stage gate — a set of
decisions taken by strategists, sales and presales, one space at a time. The
Planner scheduled that set across the plan window and computed the projection;
it chose nothing and rejected nothing.

So: do not write as though alternatives were weighed here. The argument is what
the business has already committed to and what that commitment implies —
when each space can start, which capability pools it commits, and where the
commitment exceeds what those pools can staff. Where a computed warning says the
set is over-committed or unsized, that is the most important thing on the page
and `risks` must carry it."""
    else:
        origin = """The portfolio has ALREADY BEEN SELECTED and the projection ALREADY COMPUTED by an
optimiser. You are explaining a decision, not making one."""

    return f"""{orange_context_block(cfg)}

YOUR TASK
Write the narrative of a five-year business plan for Orange Business.

{origin}

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
   capability capacity, entry slots, concentration caps, or the stage gate that
   admitted each space. Say so. A plan that reads as though everything desirable
   was chosen is not describing what actually produced this set.
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
    inputs = plan.get("inputs") or {}
    cap = plan.get("capacity_usage") or {}
    if inputs.get("source") == "workflow":
        lines = [
            f"PLAN {plan['id']} — {plan.get('label')}",
            f"Source: the collaboration workflow. Every space at stage "
            f"'{inputs.get('from_stage')}' or beyond is in this plan; nothing was selected "
            f"or rejected here. Window: {plan.get('plan_years')} years.",
            f"{plan.get('selected_count')} committed spaces, scheduled by horizon and by how "
            f"many new spaces can be started in a year.",
        ]
        stage_mix = cap.get("stage_mix") or []
        if stage_mix:
            lines.append("Where they stand on the gate: " + ", ".join(
                f"{m['label']} {m['count']}" for m in stage_mix))
        lines += ["", "PORTFOLIO SHAPE (shares, for your qualitative description only)"]
    else:
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
        lines += ["", ("NOT IN THIS PLAN — waiting for a decision on the workflow board, stopped "
                       "there, or unsized. Nothing here was rejected by the Planner; say so in "
                       "`not_doing`:")
                  if inputs.get("source") == "workflow" else
                  "NOTABLE EXCLUSIONS — for the `not_doing` section:"]
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


# ---------------------------------------------------------------------------
# The scoping conversation (the Generate screen's assistant tab)
#
# The free-text box this replaces asked for one thing — a description — and gave
# exactly one piece of feedback: a character count. That is the wrong shape for
# the task. An opportunity space is a vertical x use case x technology plus a
# buyer's problem and a place, and somebody who knows their market but not this
# taxonomy will reliably under-specify two of the five. The run then fails on
# retrieval, minutes later, and the only report is "nothing close enough".
#
# So the assistant interviews rather than accepts. Three things make that
# interview worth having rather than a form with a chat skin:
#
# 1.  IT HAS THE CORPUS IN FRONT OF IT. Every turn is given the theme-cluster
#     map, the geography and signal-type distribution, and the signals actually
#     retrieved by what has been said so far. That is what lets it ask "the
#     evidence here is German and Dutch tenders — is the Netherlands in scope?"
#     instead of "which geography?", and what lets it say the corpus is thin
#     DURING the conversation rather than after a run creates nothing.
#
# 2.  IT ASKS FOR WHAT IS MISSING, IN THE ORDER THAT MATTERS. The slots below
#     are ranked by how much they change retrieval. Vertical first, because it
#     is the axis the radar is organised on; deployment last, because it shapes
#     the sentence rather than the search.
#
# 3.  IT DOES NOT DECIDE WHEN IT IS READY. The model proposes; `radar.scoping`
#     re-runs the same retrieval the generation job will run and refuses to
#     enable the button if the brief would retrieve nothing. A model asked
#     "do you have enough?" says yes — that is what models do.
# ---------------------------------------------------------------------------

#: Bumped from v1 when the support test and the two non-permissions were added
#: (DR-10: changing a prompt means bumping its version, or the lineage claim in
#: NFR-02 is false).
PROMPT_VERSION_SCOPING = "scoping-v2"

#: The cheap second opinion on whether retrieved evidence is ABOUT a brief. Same
#: job as the entailment check and costed the same way — short text, small model.
PROMPT_VERSION_BRIEF_SUPPORT = "brief-support-v1"

#: At most this many spaces may come out of one conversation. A conversation
#: that has genuinely found four distinct triples is rare; one that reports four
#: is usually splitting a single idea to look generous, and each brief is a
#: separate synthesis pass with its own model calls (NFR-10).
MAX_BRIEFS_PER_CHAT = 3

#: What the conversation is trying to establish, in the order it should be
#: asked for. `required` marks the three that ARE the opportunity space (§4.4.5
#: — canonical identity is the taxonomy triple); the rest change the quality of
#: the brief rather than its validity, and the assistant asks for them only
#: while it has turns to spare.
#:
#: `ask` is the question in the assistant's own voice. It is here rather than in
#: the prose of the system prompt so that the questions are reviewable as a set,
#: the way the vocabularies are — and so that adding a slot adds a question.
SCOPING_SLOTS: tuple[dict[str, Any], ...] = (
    {
        "id": "vertical",
        "label": "Vertical — whose industry",
        "required": True,
        "vocabulary": "verticals",
        "why": "The radar is organised on the taxonomy triple and the vertical is the axis a "
               "salesperson actually walks in on. Without it the brief retrieves technology news "
               "from every industry at once and the resulting space is a theme, not an opportunity.",
        "ask": "Which industry has this problem? If it is really several, say which one you would "
               "walk into first — I can build the others afterwards.",
    },
    {
        "id": "use_case",
        "label": "Use case — what the buyer is trying to do",
        "required": True,
        "vocabulary": "use_cases",
        "why": "A technology without a job to do is a capability, not an opportunity. This is the "
               "slot most often left implicit, because the person describing it already knows it.",
        "ask": "What is the customer actually trying to achieve — the operational job, not the "
               "technology? Cut unplanned downtime, meet a reporting deadline, keep a site safe?",
    },
    {
        "id": "technology",
        "label": "Technology — what would be deployed",
        "required": True,
        "vocabulary": "technologies",
        "why": "It decides whether Orange has anything to sell, and it is what the patent and "
               "standards evidence in the corpus is indexed on.",
        "ask": "What would actually be deployed to do it? If you are not sure, tell me the "
               "constraint — no site coverage, no cloud allowed, nobody to run it — and I will "
               "suggest what the evidence points at.",
    },
    {
        "id": "buyer_problem",
        "label": "The pain — why they would pay",
        "required": False,
        "vocabulary": None,
        "why": "It is what turns a statement into something a customer recognises as being about "
               "them, and it steers retrieval towards regulation and buying signals rather than "
               "vendor announcements.",
        "ask": "What goes wrong today if nobody does this — a cost, an outage, a deadline, a fine?",
    },
    {
        "id": "geographies",
        "label": "Geography — where",
        "required": False,
        "vocabulary": None,
        "why": "Geography rides on signals (§2.6), so it is a real filter on the evidence rather "
               "than a label. It is also where a brief most often outruns the corpus.",
        "ask": "Which countries or regions? I will tell you straight away whether the corpus "
               "carries evidence there.",
    },
    {
        "id": "personas",
        "label": "Buyer — who signs",
        "required": False,
        "vocabulary": "personas",
        "why": "Two people buy very different things under the same use case. It changes the "
               "statement and the next action, not the retrieval.",
        "ask": "Who owns this budget — the CIO, the plant or operations side, security, "
               "sustainability, a line-of-business head?",
    },
    {
        "id": "deployment",
        "label": "Shape — how Orange would sell it",
        "required": False,
        "vocabulary": None,
        "why": "Managed service, integration, or a product sale are different right-to-win "
               "arguments. It shapes the sentence rather than the search, so it is asked last.",
        "ask": "How would this be sold — as a managed service, an integration project, or "
               "something the customer runs themselves?",
    },
)


def scoping_slot_block() -> str:
    """The interview plan, rendered for the prompt."""
    lines = []
    for index, slot in enumerate(SCOPING_SLOTS, 1):
        kind = "REQUIRED" if slot["required"] else "optional"
        vocab = f" [must resolve to a {slot['vocabulary']} id]" if slot["vocabulary"] else ""
        lines.append(f"{index}. {slot['id']} — {slot['label']} ({kind}){vocab}")
        lines.append(f"   Why it matters: {slot['why']}")
        lines.append(f"   Ask it roughly like this: \"{slot['ask']}\"")
    return "\n".join(lines)


def scoping_system_prompt(cfg: Config, min_chars: int, max_chars: int,
                          min_signals: int) -> str:
    """The scoping assistant (§4.4.2's context, put to a conversational use).

    Everything the synthesis prompt is given — who Orange is, the closed
    vocabularies, what specificity means — the assistant needs too, because it
    is composing the input to that prompt. What it adds is an interview policy
    and the hard rule that it is talking about a corpus it can see rather than
    about the world.
    """
    return f"""MOCK_KIND=scoping
{orange_context_block(cfg)}

WHO YOU ARE
You are the Innovation Radar's scoping assistant. Someone has come to the
Generate screen with an idea in their head and wants an opportunity space out of
it. Your job is to interview them until the idea is specific enough to retrieve
real evidence with — and to tell them honestly when the corpus cannot support
what they are describing.

You are NOT a general assistant. You do not know about the world; you know about
this corpus, and the corpus is put in front of you every turn. If it is not in
the evidence you were given, you have not heard of it.

WHAT YOU ARE COMPOSING
An opportunity space is exactly:

    Vertical  x  Use Case  x  Technology

plus one specific sentence a salesperson could open a customer meeting with.
Everything you ask for is in service of writing a SEARCH BRIEF that will
retrieve the evidence such a space could rest on.

{vocabulary_block(cfg)}

{examples_block()}

WHAT YOU ARE TRYING TO ESTABLISH — ask for what is missing, in this order
{scoping_slot_block()}

HOW TO ASK
1.  ONE question per turn. Two only when the second is a trivial confirmation.
    A numbered list of five questions is a form, and a form is what this screen
    already had.
2.  ASK FOR THE HIGHEST MISSING SLOT FIRST, using the order above. Skip anything
    the person has already said, anything you can infer with confidence from
    what they said, and anything the retrieved evidence settles on its own.
3.  GROUND THE QUESTION IN THE EVIDENCE. You have the signals their words
    actually retrieved. Ask "the tenders here are German and Dutch — is the
    Netherlands in scope, or only Germany?" rather than "which geography?".
    A question that could have been asked without the corpus is a wasted turn.
4.  OFFER OPTIONS RATHER THAN A BLANK. Where the answer must come from a closed
    vocabulary, name two or three plausible ids in plain language and let them
    pick or correct you. Put the same options in `suggestions` so they can be
    clicked.
5.  NEVER MAKE THEM LEARN THE TAXONOMY. Talk in their words; map to ids
    silently. If what they said has no legal id, say what the nearest one covers
    and ask them to confirm — do not report a validation error.
6.  BE BRIEF. Two or three sentences. You are interviewing, not briefing.
7.  NEVER ask for a market size, a budget, a growth rate or any other number,
    and never state one.
8.  NEVER ASK FOR THE SAME SLOT TWICE. If you asked and they answered, that
    slot is DONE, even if their answer did not map cleanly onto an id. Re-asking
    reads as not listening, and it is: they told you, and the gap is in the
    vocabulary rather than in what they said.

9.  WHEN NOTHING IN THE VOCABULARY FITS, SAY SO AND TAKE THE NEAREST. The lists
    are closed and finite — 59 use cases, not every job a business can have — so
    an idea worth having will regularly land between two of them or outside all
    of them. That is a fact about the taxonomy, not a defect in the idea, and it
    is NEVER a reason to keep asking. Name the closest id, say plainly that it is
    an approximation and which part of their idea it does not carry, and use it.
    "The taxonomy has no id for monetising advertising inventory; the nearest is
    customer_self_service, which covers the citizen-facing screen but not the ad
    revenue — I will file it under that and say so" is a good turn. Asking a
    fourth time what the core job is, is not.

10. STOP ASKING BY YOUR SIXTH TURN. If the required slots are still not filled by
    then, fill them with your best reading of what has been said, say what you
    assumed, and propose the brief. An interview that never ends produces
    nothing, which is worse than a brief with a stated approximation in it.

WHAT COUNTS AS SUPPORT — read this before you call anything "close"
The signals you are shown were retrieved by SIMILARITY. Similarity is not
support. A brief about municipal digital signage retrieves French public-sector
IT tenders at a high score because they are the same sector in the same country,
and not one of them mentions a screen. If you propose that space, synthesis
writes claims citing those tenders and the critic correctly refuses every one —
several model calls spent to produce nothing.

So before you treat a retrieved signal as evidence, ask what it is ABOUT, from
its own title and extract:

*   Does it mention the use case, or something a reader would agree is the same
    job? Does it mention the technology?
*   Or is it merely the same industry, the same country, the same buyer?

Count the ones that pass. If fewer than {min_signals} of them do, the corpus does
NOT support the brief, however high the similarity scores are and however many
signals came back. Say that plainly and name what the corpus does carry instead.

BUT STILL PROPOSE THE BRIEF. This is the important part, and it is the opposite of
what you may be inclined to do. The corpus cannot evidence a genuinely new idea —
that is what "new" means — and stopping there makes this screen useless for
exactly the work it is most wanted for. What you must not do is pretend the
evidence exists. What you SHOULD do is put the brief forward with `ready` false,
so the person can build it on what THEY know: their own account is then recorded
as dated, attributable internal evidence and the space rests on that instead.
Say so in your reply — "the radar has nothing on this, but you clearly do; I can
build it on what you have told me" — and fill `hypothesis_rationale`. Say it in
the REPLY, which is conversation, and never inside `hypothesis_rationale`, which
becomes evidence.

WHAT TO DO WITH THE EVIDENCE
*   State what the corpus holds, referring to signals by their ids, and only
    what is in the block you were given. Never invent a publisher, a date or a
    document.
*   If the retrieval is thin ({min_signals} usable signals is the floor a run
    needs), say so NOW — while it can still be steered — rather than letting
    them press Generate and get nothing back. Suggest the adjacent thing the
    corpus does carry.
*   If the evidence points somewhere better than what they asked for, say so and
    ask. That is the most valuable thing you can do in this conversation.
*   If a taxonomy cell they are converging on is already in the radar, say which
    space it is. Under DR-03 a run landing there refreshes that space rather
    than creating a new one, and they may prefer to aim somewhere else.

WHEN YOU ARE READY
Set `ready` to true only when ALL of these hold:
*   vertical, use_case and technology are each resolved to a legal id;
*   you can write a brief that names the industry, the buyer's problem, what
    would be deployed and (if known) where;
*   at least {min_signals} of the retrieved signals are ABOUT the use case or the
    technology, by the test above — not merely about the same sector.
Otherwise set `ready` false. Do not set it true to be helpful — the server
re-runs the retrieval on every brief you propose, applies that same test, and
will overrule you. An enabled button that produces nothing is worse than another
question.

`ready` false does NOT mean propose nothing. It means "not on the strength of the
corpus". Once the required three slots are settled, propose the brief either way:
`ready` true when the evidence carries it, and `ready` false with a filled
`hypothesis_rationale` when it does not.

"Settled" means YOU have chosen an id, not that a perfect one exists. A slot you
have asked about once is settled by the nearest legal id plus an honest note
about what it approximates. The only time you propose no brief at all is when the
person has not yet told you enough to choose even approximately — and after your
third turn that is almost never true.

TWO THINGS THAT ARE NOT PERMISSION TO PROCEED
1.  YOUR OWN HEDGE. If you find yourself writing "the evidence is thin", "the
    closest match is only", "direct evidence is limited" or anything of that
    shape, you have just said the corpus does not support it. Set `ready` false —
    and offer the other route in the same breath. What you must never do is set
    `ready` TRUE after writing that: it reads as a warning and behaves as a
    recommendation, and the run it starts spends model calls to produce nothing.
2.  THE PERSON SAYING YES. They cannot see the corpus and you can. "Go ahead",
    "yes", "propose it" answers a question about what they WANT, never a
    question about what the evidence holds. Never ask "shall I proceed?" as a
    way of resolving thin evidence — if it is thin, the answer is already no,
    and asking hands them a decision they have no basis to make. Ask instead for
    the thing that would change the retrieval: a different use case, a different
    technology, an adjacent problem the corpus does cover — or offer to build it
    on what they know, which is the honest way to say yes to a new idea.

HOW MANY SPACES
Usually one. Propose up to {MAX_BRIEFS_PER_CHAT} only when the conversation has
genuinely landed on that many DISTINCT taxonomy triples — a different vertical,
a different use case or a different technology. Two briefs that differ only in
wording are one brief; splitting an idea to look generous wastes a synthesis
pass each.

WRITING A BRIEF
The brief is a SEARCH BRIEF, not evidence and not the finished statement. It is
embedded and used to retrieve the closest corroborated signals in the corpus,
and those become the only facts the resulting space may rest on. So write it to
be retrieved with: {min_chars}-{max_chars} characters, concrete nouns, the
sector, the buyer's problem, the technology, what would be deployed, and the
geography if there is one. No numbers. No adjectives that carry no meaning
("innovative", "next-generation", "cutting-edge"). Prefer the words the evidence
itself uses.

OUTPUT — a single JSON object, nothing else:
{{
  "reply": "<your next turn, 2-3 sentences, plain language, no markdown headings>",
  "understood": {{
    "vertical": "<vertical id or null>",
    "use_case": "<use case id or null>",
    "technology": "<technology id or null>",
    "buyer_problem": "<one short phrase or null>",
    "geographies": ["<ISO 3166-1 alpha-2 code or EU>", ...],
    "personas": ["<persona id>", ...],
    "deployment": "<managed service | integration | product | null>",
    "horizon": "<now | next | later | null>"
  }},
  "missing": ["<slot id you still need>", ...],
  "asking_for": "<the slot id this turn's question is about, or null>",
  "suggestions": ["<a clickable answer to YOUR question, in the user's words>", ...],
  "evidence_note": "<one sentence on what the corpus does or does not carry here, or null>",
  "ready": <true|false>,
  "briefs": [
    {{
      "title": "<5-8 words naming the space>",
      "description": "<the search brief, {min_chars}-{max_chars} characters>",
      "vertical": "<vertical id>",
      "use_case": "<use case id>",
      "technology": "<technology id>",
      "geographies": ["<ISO code>", ...],
      "rationale": "<one sentence: which retrieved signals make this worth running>",
      "hypothesis_rationale": "<REQUIRED when ready is false. THE BUSINESS FACTS
        THIS PERSON HAS GIVEN YOU, written as their own first-hand account: who
        is asking, what they want to do, what is stopping them, what they would
        buy and from whom. Their terms, a paragraph a colleague could act on.

        NEVER MENTION THE CORPUS, the radar, the evidence, coverage, or what is
        or is not in the data. Not one clause. This text is recorded as a signal
        and the space's claims will CITE it, so a sentence like 'this is not
        directly covered by the corpus' becomes a piece of evidence stating that
        there is no evidence — and the critic then rejects the very space it was
        written to support. Write only what is true about the market, as if you
        were writing up a customer meeting. Null when ready is true.>"
    }}
  ]
}}

`briefs` is an empty list until you are ready. `understood` is CUMULATIVE — it
carries everything established so far in the conversation, not just this turn."""


def brief_support_prompt(vertical: str, use_case: str, technology: str,
                         description: str) -> str:
    """Does this retrieved evidence actually support a space on this triple?

    The gate in `radar.scoping` asks a lexical question first — does the signal
    text carry a vocabulary term, does its CPV crosswalk hit — because it is free
    and, when it fires, it is right. What it is not is COMPLETE: a report on a
    utility's compromised RTUs is unambiguously about threat detection for energy
    operators and will never contain the string "SIEM and SOAR". Refusing a brief
    on that basis would trade one wrong answer for another.

    So where the lexical test comes up short, this asks. It is deliberately the
    same shape as the entailment check (§4.4.4 defence 4) — a cheap model, a
    short text, one narrow question — and it is asked ONLY about evidence that
    already cleared retrieval, which is what keeps it to a single call at the
    moment somebody is about to spend a whole synthesis run.
    """
    return f"""MOCK_KIND=brief_support
You decide which of several documents genuinely bear on a proposed business
opportunity. You are a filter, not an author.

THE PROPOSAL, IN THE WORDS THAT MATTER
  {description}

Its taxonomy labels, which are an APPROXIMATION and not the proposal itself:
  Industry:   {vertical}
  The job:    {use_case}
  Deployed:   {technology}

JUDGE AGAINST THE SENTENCE, NOT THE LABELS. This is the whole point of asking
you. The labels come from a closed list of fifteen industries, fifty-nine jobs
and thirty-odd technologies, so a proposal regularly gets filed under the
nearest one rather than an exact one — and a document that matches the LABEL
while missing the SENTENCE is precisely the trap. A tender for private-5G video
surveillance shares the technology label with a proposal about advertising
screens and is no evidence for it whatsoever. If you find yourself reasoning
"well, it is the same technology", stop: that is a no.

A document SUPPORTS the proposal when a reader would agree it is evidence for
the thing the sentence describes — the same job being done, or the same thing
being bought, or the same problem being had. It does not have to use the same
words.

A document DOES NOT SUPPORT the proposal when it is merely:
  * the same industry, country or buyer, doing something else;
  * the same TECHNOLOGY deployed for a different purpose;
  * the same taxonomy label attached to a different activity;
  * the same broad field ("digital", "cloud", "IT services") with no bearing on
    this job;
  * a general research or opinion piece with nothing specific to this.

Be strict. The cost of accepting a document that is only adjacent is a set of
claims that cite it, which a later reviewer will correctly reject. When you are
unsure, say it does not support.

Return JSON: {{"supporting": ["<id>", ...], "note": "<one short sentence on what
this evidence is actually about>"}}
Include an id only if you would defend it. An empty list is a valid and often
correct answer."""


def format_signals_for_support(signals: list[dict[str, Any]]) -> str:
    lines = ["DOCUMENTS", ""]
    for signal in signals:
        lines.append(f"[{signal['id']}] {signal.get('title', '')}")
        if signal.get("extract"):
            lines.append(f"    {str(signal['extract'])[:300]}")
    lines.append("")
    lines.append("Which of these support the proposal? Reply with the JSON object only.")
    return "\n".join(lines)


def scoping_user_prompt(transcript: list[dict[str, str]], corpus: dict[str, Any],
                        evidence: dict[str, Any], occupied: list[str],
                        turns_taken: int, established: dict[str, Any] | None = None) -> str:
    """Everything the assistant is allowed to know, this turn.

    Three blocks, in order of how much they should influence the question: what
    the corpus is about at all, what the conversation so far actually retrieved,
    and what has been said. The retrieval is recomputed from the whole
    conversation on every turn, so an answer that sharpens the idea sharpens the
    evidence the next question is asked from.
    """
    lines: list[str] = []

    lines.append("WHAT THE CORPUS CONTAINS (the whole radar, for orientation)")
    lines.append(f"  {corpus['signals']} classified signal(s) in {corpus['clusters']} theme "
                 f"cluster(s); {corpus['spaces']} opportunity space(s) already exist.")
    if corpus.get("date_range"):
        lines.append(f"  Evidence dates from {corpus['date_range'][0]} to {corpus['date_range'][1]}.")
    if corpus.get("by_signal_type"):
        lines.append("  By signal type: "
                     + ", ".join(f"{k} {v}" for k, v in corpus["by_signal_type"]))
    if corpus.get("by_geography"):
        lines.append("  Best-covered geographies: "
                     + ", ".join(f"{k} {v}" for k, v in corpus["by_geography"]))
    if corpus.get("clusters_sample"):
        lines.append("  The largest theme clusters, which is what the radar is currently about:")
        for cluster in corpus["clusters_sample"]:
            keys = f" — {cluster['keyphrases']}" if cluster.get("keyphrases") else ""
            lines.append(f"    [{cluster['size']} signals] {cluster['label']}{keys}")

    lines.append("")
    if evidence.get("signals"):
        lines.append(f"WHAT THIS CONVERSATION HAS RETRIEVED SO FAR "
                     f"({len(evidence['signals'])} signal(s) above the similarity floor "
                     f"{evidence['floor']:.2f})")
        lines.append("These are the only documents you may refer to as facts. Cite them by id.")
        for signal, similarity in zip(evidence["signals"], evidence["similarities"]):
            # `geographies` arrives decoded — the caller owns the JSON columns so
            # that prompt construction stays free of the storage layer.
            geos = ", ".join(signal.get("geographies") or []) or "no geography"
            lines.append(
                f"  [{signal['id']}] ({similarity:.2f}) {signal['title']}"
            )
            lines.append(
                f"      {signal.get('publisher')} · {signal.get('published_at')} · "
                f"{signal.get('signal_type') or 'unclassified'} · tier {signal.get('tier')} · {geos}"
            )
            if signal.get("extract"):
                lines.append(f"      {str(signal['extract'])[:260]}")
    else:
        lines.append("WHAT THIS CONVERSATION HAS RETRIEVED SO FAR")
        lines.append("  Nothing yet — either too little has been said to retrieve with, or nothing "
                     "in the corpus is close to it. If enough has been said to be specific and the "
                     "retrieval is still empty, say so: that is the answer, and the corpus map "
                     "above is where to look for the nearest thing it does carry.")

    if occupied:
        lines.append("")
        lines.append("TAXONOMY CELLS ALREADY OCCUPIED near this conversation (DR-03: a run landing "
                     "on one of these REFRESHES that space, it does not create a new one)")
        lines += [f"  {cell}" for cell in occupied]

    if established and any(established.values()):
        lines.append("")
        lines.append("ALREADY ESTABLISHED — carry every one of these into `understood`")
        lines.append("These were settled on earlier turns and are NOT open questions. Re-asking "
                     "about any of them reads as not listening, and dropping one from `understood` "
                     "un-settles it and stalls the interview.")
        for key, value in established.items():
            if value:
                shown = ", ".join(value) if isinstance(value, list) else value
                lines.append(f"  {key}: {shown}")

    lines.append("")
    lines.append(f"THE CONVERSATION SO FAR (you have taken {turns_taken} turn(s))")
    for message in transcript:
        who = "PERSON" if message["role"] == "user" else "YOU"
        lines.append(f"  {who}: {message['content']}")

    lines.append("")
    lines.append("Answer the last thing the person said, then ask for the highest-priority slot "
                 "still missing — or, if the required three are settled and the evidence supports "
                 "it, propose the brief(s) and set ready. Reply with the JSON object only.")
    return "\n".join(lines)


#: The assistant's first turn. Written rather than generated: it is the same
#: every time, it costs a model call to produce, and it is the one message that
#: has to set the expectation that this is an interview grounded in a fixed
#: corpus rather than a wish-granting box.
SCOPING_OPENING = (
    "Tell me what you are chasing and I will turn it into an opportunity space — but only if the "
    "evidence the radar has already collected supports it. I can see the whole corpus from here, "
    "so I will tell you as we go what it does and does not carry.\n\n"
    "Start anywhere: an industry, a customer problem you keep hearing, a technology you think is "
    "about to land. I will ask for whatever is missing."
)

#: Openers offered as chips beside the first turn. Deliberately shaped like the
#: positive examples above — three axes, one sentence — so the first answer
#: teaches the granularity without a paragraph explaining it.
SCOPING_OPENING_SUGGESTIONS = (
    "What is the corpus strongest on right now?",
    "Something in manufacturing that is being driven by regulation",
    "Where does Orange have a right to win that we are not already covering?",
)
