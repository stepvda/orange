"""The four decks, described once and emitted as PowerPoint, ODF or PDF.

Same separation as `documents`: nothing here knows what a .pptx is. A deck is a
list of slides, each with a title, up to a few bullets, speaker notes and at
most one chart, and the emitters put them on slides.

THE SPEAKER NOTES ARE HALF THE DELIVERABLE. A deck of bullets with no notes is a
document somebody has to invent a script for on the way to the meeting, and what
they invent will not be what the radar's evidence supports. Every content slide
here carries what the presenter actually says out loud, including — on the
slides where it matters — an instruction about what NOT to say.

CHARTS CARRY TWO RENDERINGS. `build` is the reportlab geometry, used by the PDF
emitter and rasterised for ODF. `pptx` is the native-shape version, so a
PowerPoint deck arrives with real rectangles and connectors that an architect
can move rather than a flat picture they have to redraw.
"""

from __future__ import annotations

from typing import Any

from ..sizing import format_eur
from . import charts, office
from .blocks import Chart, Deck, Slide
from .context import TopicContext


# ---------------------------------------------------------------------------
# Charts, in both renderings
# ---------------------------------------------------------------------------

def _funnel(ctx: TopicContext) -> Chart | None:
    size = ctx.best_size
    if not size:
        return None
    stages = [(label, (size.get(key) or {}).get("base"), note)
              for label, key, note in (("TAM", "tam", "total addressable"),
                                       ("SAM", "sam", "serviceable"),
                                       ("SOM", "som", "realistically obtainable"))]
    stages = [s for s in stages if s[1]]
    if not stages:
        return None
    return Chart(
        build=lambda w, s=stages: charts.FunnelChart(s, w),
        pptx=lambda deck, slide, top, c=ctx: office.funnel(deck, slide, c, top),
        caption=f"{size.get('method_label')} · {size.get('confidence')} confidence · per year.")


def _diagram(ctx: TopicContext) -> Chart | None:
    from ..brief import SolutionDiagram
    diagram = ctx.diagram
    if not diagram:
        return None
    return Chart(
        build=lambda w, d=diagram: SolutionDiagram(d, w),
        pptx=lambda deck, slide, top, d=diagram: office.layered_diagram(deck, slide, d, top),
        caption=str(diagram.get("caption") or ""))


def _components_chart(components: list[dict[str, str]]) -> Chart:
    return Chart(
        build=lambda w, c=components: charts.ComponentMap(c, w),
        pptx=lambda deck, slide, top, c=components: office.component_map(deck, slide, c, top))


def _field(ctx: TopicContext, entries: list[dict[str, Any]]) -> Chart:
    return Chart(
        build=lambda w, e=entries: charts.FieldMap(
            e, "reach across this market", "depth of capability", w),
        pptx=lambda deck, slide, top, e=entries: office.field_map(deck, slide, e, top))


def _waterfall(steps: list[tuple[str, float, str]]) -> Chart:
    return Chart(
        build=lambda w, s=steps: charts.WaterfallChart(s, w),
        pptx=lambda deck, slide, top, s=steps: office.waterfall(deck, slide, s, top))


def _payback(values: list[float]) -> Chart:
    return Chart(
        build=lambda w, v=values: charts.PaybackCurve(v, "period", w),
        pptx=lambda deck, slide, top, v=values: office.payback(deck, slide, v, top))


def _options(options: list[dict[str, Any]], measure: str, key: str) -> Chart:
    return Chart(
        build=lambda w, o=options, k=key: charts.OptionColumns(
            [(opt["model"], (int(opt.get(k, 1)) + 1) / 3.0,
              {0: "low", 1: "medium", 2: "high"}[int(opt.get(k, 1))]) for opt in o], w),
        pptx=lambda deck, slide, top, o=options, m=measure, k=key:
            office.option_columns(deck, slide, o, top, m, k))


def _sources_slide(content: dict[str, Any]) -> Slide | None:
    """The live items the writer saw, so an attribution on a slide can be followed.

    The documents list these at the back and the decks did not, which made the
    inline attribution the prompt demands — "(Handelsblatt, 2026-07-14)" — a
    dead end in exactly the artefact most likely to be read out loud. Same rule,
    same place in the pack.
    """
    items = content.get("_research") or []
    if not items:
        return None
    return Slide(
        title="Researched while this was written",
        subtitle="Retrieved from the public record on the day this deck was built, and newer "
                 "than the radar's last refresh",
        rows=[(f"{item.get('published_at') or 'undated'} · {item.get('publisher', '')}",
               str(item.get("title", ""))[:110]) for item in items[:8]],
        notes="These have not been through the radar's evidence validation. Anything drawn "
              "from them is attributed inline on the slide it appears on.")


def _provenance_slide(ctx: TopicContext, written: bool) -> Slide:
    size = ctx.best_size
    rows = [
        ("Opportunity space", f"{ctx.topic_id} v{ctx.topic.get('version')}"),
        ("Weight set", str((ctx.topic.get("provenance") or {}).get("weight_set") or "—")),
        ("Sizing", f"{size.get('sizing_version')} ({size.get('method')})" if size else "not sized"),
        ("Competitor register", str((ctx.analysis or {}).get("register_version")
                                    or (ctx.competition or {}).get("register_version") or "—")),
    ]
    if written:
        rows.append(("Written sections",
                     "generated under the §4.4.4 defences — quantities stripped, not trusted"))
    return Slide(title="Where this came from",
                 subtitle="Every figure in this deck decomposes into stored components. Nothing "
                          "on the money slides was written by a model.",
                 rows=rows)


# ---------------------------------------------------------------------------
# 1 — Solution outline
# ---------------------------------------------------------------------------

def solution_outline(ctx: TopicContext, content: dict[str, Any]) -> Deck:
    deck = Deck(title="Solution outline", subject="Solution outline")
    deck.add(Slide(kind="cover", title="Solution outline",
                   strapline="For the solution architect. In PowerPoint every shape is "
                             "editable — drag a box, rename a component, delete the row that "
                             "does not apply."))

    diagram = _diagram(ctx)
    if diagram:
        deck.add(Slide(title=str((ctx.diagram or {}).get("title") or "How it fits together"),
                       subtitle="Layers and flows as the radar validated them. Colour says who "
                                "owns each component.",
                       chart=diagram, notes=diagram.caption))
    else:
        deck.add(Slide(kind="section",
                       title="No solution diagram has been generated for this space",
                       subtitle="Generate the description for this space and rebuild — the "
                                "diagram is written and validated there, not here."))

    components = content.get("components") or []
    if components:
        gaps = sum(1 for c in components if c.get("provider") == "third_party")
        deck.add(Slide(
            title="What it is made of",
            subtitle=(f"{len(components)} components · {gaps} still to be sourced" if gaps
                      else f"{len(components)} components, all covered by named assets"),
            chart=_components_chart(components),
            notes="The grey boxes are the honest part of this slide. Each one is a capability "
                  "somebody has to supply before this is sellable."))

    interfaces = content.get("interfaces") or []
    if interfaces:
        deck.add(Slide(title="What flows between them",
                       bullets=[f'{i["between"]} — {i["carries"]}' for i in interfaces],
                       notes="Integration surface. Each line here is a conversation with "
                             "somebody who owns a system on the customer side."))

    questions = content.get("open_questions") or []
    if questions:
        deck.add(Slide(title="What we still need to ask", bullets=questions,
                       subtitle="Before committing to a design",
                       notes="A solution outline with no open questions has not been thought "
                             "about hard enough. Take these into the technical session."))

    delivered = ctx.section_text("what_orange_would_deliver")
    if delivered:
        deck.add(Slide(title="The shape of the engagement", bullets=[delivered[:300]],
                       notes=delivered))

    deck.add(_sources_slide(content), _provenance_slide(ctx, written=bool(components)))
    return deck


# ---------------------------------------------------------------------------
# 2 — Value hypothesis
# ---------------------------------------------------------------------------

def value_hypothesis(ctx: TopicContext, content: dict[str, Any]) -> Deck:
    deck = Deck(title="Value hypothesis", subject="Value hypothesis")
    deck.add(Slide(kind="cover", title="Value hypothesis",
                   strapline="The market sized bottom-up, the value built step by step, and "
                             "when it pays back. Every figure decomposes into stored "
                             "components."))

    funnel = _funnel(ctx)
    if funnel:
        deck.add(Slide(title="What this market is worth",
                       subtitle="Nested, not additive — SOM sits inside SAM sits inside TAM",
                       chart=funnel,
                       notes="Lead with SOM, not TAM. TAM is context; SOM is the number the "
                             "customer's own budget has to live inside."))
    else:
        deck.add(Slide(kind="section", title="This space has not been sized",
                       subtitle="Run the sizing stage for it and rebuild."))

    drivers = content.get("drivers") or []
    if drivers:
        deck.add(Slide(title="Where the value comes from",
                       bullets=[f'{d["driver"]} — {d["mechanism"]}' for d in drivers],
                       subtitle="Mechanisms, not promises",
                       notes="Each of these has to survive the customer asking 'how, exactly'. "
                             "The mechanism is the answer."))

        som = (ctx.best_size or {}).get("som", {}).get("base")
        if som:
            # Built from ONE computed figure split across the drivers the writer
            # named, never from figures a model produced. The even split is
            # stated on the slide: an unequal one would be a claim about
            # relative value that nothing in the evidence supports.
            share = float(som) / len(drivers)
            steps = [(d["driver"], share, "gain") for d in drivers]
            steps += [("Cost to serve", -float(som) * 0.35, "cost"), ("Net", 0.0, "total")]
            deck.add(Slide(
                title="How the number is built",
                subtitle="Obtainable market apportioned equally across the named drivers — a "
                         "shape to test with the customer, not a forecast",
                chart=_waterfall(steps),
                notes="Say out loud that the split is even because nothing in the evidence "
                      "justifies weighting one driver over another yet. That is what the proof "
                      "plan is for."))

            monthly = float(som) / 12.0 * 0.65
            setup = float(som) * 0.4
            cumulative = [-setup + monthly * (m / 2.0) for m in range(12)]
            deck.add(Slide(
                title="When it pays back",
                subtitle="Indicative shape from the obtainable figure and a nominal ramp",
                chart=_payback(cumulative),
                notes="This curve is a shape, not a commitment. Its job is to make the "
                      "conversation about WHEN rather than whether."))

    if content.get("cost_of_inaction"):
        deck.add(Slide(title="The cost of doing nothing",
                       bullets=[content["cost_of_inaction"]],
                       notes="The strongest slide in most business cases, and the one most "
                             "often left out."))

    proof = content.get("proof_plan") or []
    if proof:
        deck.add(Slide(title="How you could check this in your own data", bullets=proof,
                       subtitle="Before signing anything",
                       notes="Offering to be checked is what separates a business case from a "
                             "brochure. Mean it."))

    deck.add(_sources_slide(content), _provenance_slide(ctx, written=bool(drivers)))
    return deck


# ---------------------------------------------------------------------------
# 3 — First-meeting deck
# ---------------------------------------------------------------------------

def first_meeting_deck(ctx: TopicContext, content: dict[str, Any]) -> Deck:
    deck = Deck(title="First meeting", subject="First meeting")
    deck.add(Slide(kind="cover", title=ctx.statement[:90],
                   strapline="A first conversation, in the order first conversations "
                             "actually go."))

    slides = content.get("slides") or []
    diagram, funnel = _diagram(ctx), _funnel(ctx)
    for index, written in enumerate(slides):
        deck.add(Slide(title=written["title"], bullets=written.get("bullets") or [],
                       notes=written.get("notes", "")))
        # The two computed slides are inserted rather than written, and they go
        # where the conversation reaches them: the picture once the problem is
        # established, the money once the solution is on the table.
        if index == 2 and diagram:
            deck.add(Slide(title="What we would build",
                           subtitle="Colour says who owns each part", chart=diagram,
                           notes="Do not walk through every box. Point at the orange ones and "
                                 "at the gaps, then stop talking."))
        if index == 4 and funnel:
            deck.add(Slide(title="What this market is worth",
                           subtitle="Computed bottom-up from published statistics", chart=funnel,
                           notes="If they challenge the number, offer the working — it "
                                 "decomposes all the way down and that is the point."))

    if not slides:
        deck.add(Slide(kind="section",
                       title="The narrative for this space has not been written",
                       subtitle="Generate the description and rebuild. The computed slides — "
                                "the diagram and the sizing — follow."))
        if diagram:
            deck.add(Slide(title="What we would build", chart=diagram))
        if funnel:
            deck.add(Slide(title="What this market is worth", chart=funnel))

    competitors = ctx.competitor_names
    if competitors:
        reach = charts._clamp((ctx.topic.get("right_to_win") or {}).get("score") or 0.5)
        depth = charts._clamp(1.0 - min(ctx.portfolio_distance, 3) / 3.0)
        entries = [{"label": name, "x": 0.35 + 0.12 * (i % 4), "y": 0.4 + 0.1 * (i % 3)}
                   for i, name in enumerate(competitors[:6])]
        entries.append({"label": "Orange", "x": reach, "y": depth, "is_orange": True})
        deck.add(Slide(title="Who else is in this space", subtitle="Orange is the orange mark",
                       chart=_field(ctx, entries),
                       notes="Only open this slide if they ask. Volunteering the competitive "
                             "field in a first meeting invites a comparison you have not "
                             "framed yet."))

    actions = ctx.topic.get("next_actions") or {}
    if actions:
        deck.add(Slide(title="What happens next",
                       bullets=[f'{role.replace("_", " ").title()}: {action}'
                                for role, action in list(actions.items())[:5]],
                       notes="Leave with a named owner and a date against at least one of "
                             "these."))

    deck.add(_sources_slide(content), _provenance_slide(ctx, written=bool(slides)))
    return deck


# ---------------------------------------------------------------------------
# 4 — Commercial model options
# ---------------------------------------------------------------------------

def pricing_options(ctx: TopicContext, content: dict[str, Any]) -> Deck:
    deck = Deck(title="Commercial models", subject="Commercial models")
    deck.add(Slide(kind="cover", title="Commercial model options",
                   strapline="Shapes, not prices. Every option here changes who carries which "
                             "risk — that is the decision, and it is made before any number is "
                             "discussed."))

    options = content.get("options") or []
    if not options:
        deck.add(Slide(kind="section",
                       title="No commercial options have been written for this space",
                       subtitle="This piece needs one model call. Rebuild it once the space "
                                "has a description to work from."))
        deck.add(_sources_slide(content), _provenance_slide(ctx, written=False))
        return deck

    deck.add(Slide(title="How much risk Orange carries",
                   subtitle="Ordinal judgements, not measurements",
                   chart=_options(options, "Risk carried by Orange under each model",
                                  "orange_risk"),
                   notes="Start here rather than with appeal. The option that appeals most to "
                         "the customer is usually the one that moves the most risk onto "
                         "Orange, and that trade is the conversation."))
    deck.add(Slide(title="How much each appeals to the customer",
                   subtitle="Ordinal judgements, not measurements",
                   chart=_options(options, "Expected customer appeal under each model",
                                  "customer_appeal"),
                   notes="Read against the previous slide. Where appeal is high and risk is "
                         "high, the levers on the next slides are what make it workable."))

    for option in options:
        deck.add(Slide(
            title=option["model"],
            bullets=([option.get("how_it_works", "")]
                     + [f"Lever: {lever}" for lever in option.get("levers") or []]
                     + ([f'Use when: {option["use_when"]}'] if option.get("use_when") else [])),
            subtitle="Indicative shape — no price, rate or margin is stated anywhere in this "
                     "deck",
            notes=option.get("use_when", "")))

    deck.add(_sources_slide(content), _provenance_slide(ctx, written=True))
    return deck


DECKS = {
    "solution-outline": solution_outline,
    "value-hypothesis": value_hypothesis,
    "first-meeting-deck": first_meeting_deck,
    "pricing-options": pricing_options,
}
