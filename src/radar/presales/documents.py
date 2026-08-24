"""The seven flowing documents, described once and emitted in any text format.

Nothing here knows what a PDF is. Each function returns a `blocks.Document` —
an ordered list of headings, prose, tables and charts — and the emitters in
`emit/` put it on a page. That is what makes "the same battlecard as PDF, Word
or ODF" a real promise rather than three documents that drift apart.

The shared furniture at the top is the part worth reading: every document opens
with the space it belongs to, states what it was built WITHOUT, and closes with
the versions that produced it. A document from this system that cannot be traced
is a brochure, and six months later the only question anybody asks about a file
found in a shared drive is which versions made it.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from ..sizing import format_eur
from . import charts
from .blocks import (USABLE_WIDTH, Bullets, Callout, Chart, Document, Heading, KPIs, Kicker,
                     PageBreak, Para, Spacer, Table)
from .context import TopicContext


# ---------------------------------------------------------------------------
# Shared furniture
# ---------------------------------------------------------------------------

def _open(ctx: TopicContext, title: str, strapline: str, subject: str) -> Document:
    return Document(title=title, subject=subject).add(
        Kicker(f"{ctx.topic_id} · {ctx.triple}"),
        Heading(title, level=1),
        Para(ctx.statement),
        Para(strapline, small=True),
        Spacer(3),
    )


def _gap_note(ctx: TopicContext, needs: list[str]) -> Callout | None:
    """State what this document is missing, on the document.

    The alternative — rendering the sections that exist and staying quiet about
    the rest — produces a file that looks finished, and the person who finds out
    otherwise is standing in front of a customer.
    """
    missing = ctx.missing(needs)
    if not missing:
        return None
    return Callout(
        f"Built without {' and '.join(missing)}. The sections that depend on it are absent "
        f"rather than guessed. Generate it for this space and rebuild to fill them in.")


def _sources(content: dict[str, Any]) -> list[Any]:
    """The live items the writer was shown, listed so a citation can be followed.

    Without this the inline attributions the prompt demands — "(Handelsblatt,
    2026-07-14)" — are unfollowable, and an unfollowable citation is decoration.
    Listed even when the writer used none of them: what the research FOUND is
    itself worth knowing, and its absence is worth knowing too.
    """
    items = content.get("_research") or []
    if not items:
        return []
    return [
        Spacer(4), Heading("Researched while this was written", level=3),
        Para("Retrieved from the public record on the day this document was built, and newer "
             "than the radar's last refresh. These have not been through the radar's evidence "
             "validation — anything drawn from them is attributed inline above.", small=True),
        Table(headers=["Published", "Publisher", "Item"],
              rows=[[item.get("published_at") or "undated", item.get("publisher", ""),
                     item.get("title", "")] for item in items[:12]],
              widths=[0.7, 1.2, 4]),
    ]


def _provenance(ctx: TopicContext, written: bool) -> list[Any]:
    size = ctx.best_size
    rows = [
        ["Built", dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")],
        ["Opportunity space", f"{ctx.topic_id} v{ctx.topic.get('version')}"],
        ["Weight set", str((ctx.topic.get("provenance") or {}).get("weight_set") or "—")],
        ["Sizing", f"{size.get('sizing_version')} ({size.get('method')})" if size else "not sized"],
        ["Competitor register", str((ctx.analysis or {}).get("register_version")
                                    or (ctx.competition or {}).get("register_version") or "—")],
    ]
    if written:
        rows.append(["Written sections",
                     "generated under the §4.4.4 defences; quantities are stripped, not trusted"])
    return [Spacer(6), Heading("Where this came from", level=3),
            Table(headers=[], rows=rows, widths=[1, 3])]


def _coverage_rows(ctx: TopicContext) -> list[tuple[str, float, str]]:
    """Named evidence counts as fractions of the largest, for a nominal bar set.

    Every bar the same colour: these are categories, not a ranking, and giving
    each its own hue would spend the identity channel re-encoding what the bar
    length already says.
    """
    counts = {
        "Signals behind this space": int(ctx.topic.get("signal_count") or 0),
        "Named Orange assets": len(ctx.orange_assets),
        "Published references": len(ctx.references),
        "Competitors identified": len(ctx.competitor_names),
    }
    top = max(counts.values(), default=0)
    if not top:
        return []
    return [(label, value / top, str(value)) for label, value in counts.items()]


def _orange_position(ctx: TopicContext) -> tuple[float, float]:
    """Orange's own mark on the field map, from computed quantities only.

    Reach from right-to-win, depth from portfolio distance inverted — a space
    Orange can deliver today (L0) is one where the capability is already deep.
    Both are stored scores, so the one mark on that chart that matters is the
    one mark no model placed.
    """
    reach = charts._clamp((ctx.topic.get("right_to_win") or {}).get("score") or 0.5)
    depth = charts._clamp(1.0 - min(ctx.portfolio_distance, 3) / 3.0)
    return reach, depth


def _components(ctx: TopicContext, content: dict[str, Any]) -> list[dict[str, str]]:
    """Component boxes, preferring the writer's list and falling back to the graph."""
    components = content.get("components") or []
    if components:
        return components
    out = [{"label": str(link.get("label")), "provider": "orange",
            "note": str(link.get("node_type", "")).replace("_", " ")}
           for link in ctx.orange_assets[:8]]
    if ctx.portfolio_distance:
        out.append({"label": f"{ctx.portfolio_distance} capability gap(s)",
                    "provider": "third_party", "note": "to be sourced"})
    return out


def _portfolio_hops(ctx: TopicContext, content: dict[str, Any]) -> list[dict[str, str]]:
    """The path drawn as boxes: what exists, what is missing, what it becomes.

    Capped at the stored distance so the picture cannot claim more hops than the
    graph computed.
    """
    assets = ctx.orange_assets
    hops = [{"label": assets[0].get("label") if assets else "Orange portfolio today",
             "provider": "orange",
             "note": f"{len(assets)} named asset(s)" if assets else "nothing linked yet"}]
    for gap in (content.get("gaps") or [])[: max(ctx.portfolio_distance, 1)]:
        hops.append({"label": gap["capability"], "provider": "third_party",
                     "note": gap["candidate_type"][:34]})
    hops.append({"label": "Deliverable configuration", "provider": "partner",
                 "note": f"L{ctx.portfolio_distance} from here"})
    return hops


# ---------------------------------------------------------------------------
# 1 — Discovery & qualification pack
# ---------------------------------------------------------------------------

def discovery_pack(ctx: TopicContext, content: dict[str, Any]) -> Document:
    doc = _open(ctx, "Discovery & qualification pack",
                "Read before the meeting. The questions are the deliverable — everything else "
                "on the page exists to make them land.",
                "Discovery & qualification pack")
    doc.add(_gap_note(ctx, ["description"]))

    people = content.get("buying_centre") or []
    if people:
        doc.add(
            Heading("The buying centre"),
            Para("Who signs, who feels it, and what makes them act this year. The highlighted "
                 "seat is the economic buyer — the one a first meeting most often does not have "
                 "in the room.", small=True),
            Chart(build=lambda w, p=people: charts.StakeholderMap(p, w)),
        )
        triggers = [f"<b>{p['role']}</b> — {p.get('trigger', '')}"
                    for p in people if p.get("trigger")]
        if triggers:
            doc.add(Heading("What makes each of them act", level=3), Bullets(triggers))

    questions = (ctx.description or {}).get("qualifying_questions") or []
    if questions:
        doc.add(Spacer(3), Heading("Ask these in the first meeting"),
                Para("Generated against this space's own evidence, so the answers are checkable "
                     "against the radar rather than against a feeling.", small=True),
                Bullets([str(q) for q in questions]))

    qualification = content.get("qualification") or []
    if qualification:
        doc.add(Spacer(4), Heading("Qualification"),
                Table(headers=["Criterion", "Ask", "A good answer sounds like"],
                      rows=[[row["criterion"], row["question"], row["what_good_looks_like"]]
                            for row in qualification],
                      widths=[1.2, 2.6, 2.4]))

    objections = (ctx.description or {}).get("objection_handling") or []
    if objections:
        doc.add(PageBreak(), Heading("Objections you will meet"))
        for entry in objections:
            doc.add(Para(f'“{entry.get("objection", "")}”', bold=True),
                    Para(entry.get("response", ""), small=True), Spacer(2))

    disqualifiers = content.get("disqualifiers") or []
    if disqualifiers:
        doc.add(Spacer(2), Heading("Walk away if"),
                Para("A qualification sheet with no disqualifiers has not been used yet.",
                     small=True),
                Bullets(disqualifiers))

    bars = _coverage_rows(ctx)
    if bars:
        doc.add(Spacer(4), Heading("How well evidenced this space is"),
                Para("Thin evidence is not a reason not to go — it is a reason to ask rather "
                     "than assert. This is what the radar actually holds.", small=True),
                Chart(build=lambda w, b=bars: charts.CoverageBars(b, w)))
        if ctx.topic.get("evidence_gap_warning"):
            doc.add(Callout("The radar flags an evidence gap on this space. Treat the narrative "
                            "as a hypothesis to test in the meeting, not as a finding to present."))

    doc.add(*_sources(content), *_provenance(ctx, written=bool(people or qualification)))
    return doc


# ---------------------------------------------------------------------------
# 2 — Competitor battlecards
# ---------------------------------------------------------------------------

def battlecards(ctx: TopicContext, content: dict[str, Any]) -> Document:
    doc = _open(ctx, "Competitor battlecards",
                "One card per competitor. The trap question is the part to memorise.",
                "Competitor battlecards")
    doc.add(_gap_note(ctx, ["competition", "analysis"]))

    competition = ctx.competition or {}
    if competition:
        doc.add(KPIs(cells=[(str(competition.get("level_label", "—")), "competitive intensity"),
                            (str(len(ctx.competitor_names)), "competitors named on this space"),
                            (f"L{ctx.portfolio_distance}", "portfolio distance")],
                     tones=[str(competition.get("level", "none")), "", ""]),
                Para(str(competition.get("meaning", "")), small=True))

    cards = content.get("cards") or []
    if cards:
        doc.add(Spacer(3), Heading("The field"))
        if content.get("field"):
            doc.add(Para(content["field"]))
        reach, depth = _orange_position(ctx)
        entries = [{"label": card["competitor"], "x": card["reach"] / 2, "y": card["depth"] / 2}
                   for card in cards]
        entries.append({"label": "Orange", "x": reach, "y": depth, "is_orange": True})
        doc.add(
            Para("Reach is how broadly they cover this market; depth is how far their capability "
                 "actually goes in it. Both are judgements from their own published positions, "
                 "not measurements. Orange is the orange mark.", small=True),
            Chart(build=lambda w, e=entries: charts.FieldMap(
                e, "reach across this market", "depth of capability", w)),
        )

    for card in cards:
        doc.add(PageBreak(), Heading(card["competitor"]))
        if card.get("their_pitch"):
            doc.add(Para(f'<b>Their pitch:</b> “{card["their_pitch"]}”', markup=True))
        rows = [[label, value] for label, value in
                (("Strong where", card.get("strong_where")),
                 ("Thin where", card.get("thin_where"))) if value]
        if rows:
            doc.add(Table(headers=[], rows=rows, widths=[1, 4]))
        if card.get("trap_question"):
            doc.add(Spacer(1.5),
                    Para(f'<b>Ask them:</b> “{card["trap_question"]}”', markup=True))
        if card.get("our_proof"):
            doc.add(Para(f'Our proof: {card["our_proof"]}', small=True))

        dimensions = card.get("dimensions") or []
        if dimensions:
            rows = [(d["dimension"], 0.75, 0.45) if "orange" in d["verdict"].lower()
                    else (d["dimension"], 0.45, 0.75) if "ahead" in d["verdict"].lower()
                    else (d["dimension"], 0.6, 0.6) for d in dimensions]
            doc.add(Spacer(2), Chart(
                build=lambda w, r=rows, c=card["competitor"]: charts.StrengthBars(r, c, w)))

    entries = (ctx.analysis or {}).get("entries") or []
    if entries:
        doc.add(PageBreak(), Heading("What each of them publishes about this"),
                Para("Read from their own pages by the competitor intelligence stage. Where a "
                     "site refused to be read, that is said rather than inferred.", small=True))
        for entry in entries[:10]:
            written = entry.get("written") or {}
            doc.add(Spacer(2.5),
                    Para(f'<b>{entry.get("label", "")}</b> — {entry.get("type_label", "")}',
                         markup=True))
            if entry.get("profile_status") != "profiled":
                doc.add(Para(f'Their published position is unread — '
                             f'{entry.get("profile_reason") or entry.get("profile_status")}.',
                             small=True))
            elif (written.get("activity") or {}).get("text"):
                doc.add(Para(written["activity"]["text"], small=True))
            if written.get("differentiation"):
                doc.add(Para(f'<b>How Orange differentiates:</b> {written["differentiation"]}',
                             small=True, markup=True))

    doc.add(*_sources(content), *_provenance(ctx, written=bool(cards)))
    return doc


# ---------------------------------------------------------------------------
# 3 — Reference & proof pack
# ---------------------------------------------------------------------------

def reference_pack(ctx: TopicContext, content: dict[str, Any]) -> Document:
    doc = _open(ctx, "Reference & proof pack",
                "Everything Orange can actually point at on this space, and — stated plainly — "
                "where it cannot.", "Reference & proof pack")

    assets, references = ctx.orange_assets, ctx.references
    doc.add(KPIs(cells=[(str(len(assets)), "named Orange assets"),
                        (str(len(references)), "published references"),
                        (f"L{ctx.portfolio_distance}", "hops to a deliverable configuration")],
                 tones=["accent", "", ""]))

    bars = _coverage_rows(ctx)
    if bars:
        doc.add(Heading("What backs this space"),
                Chart(build=lambda w, b=bars: charts.CoverageBars(b, w)), Spacer(3))

    if assets:
        doc.add(Heading("Named Orange assets"),
                Para("Each one individually inspectable in the radar (LK-08). 'Unconfirmed' means "
                     "the link was inferred and no curator has signed it off yet — worth checking "
                     "before you say it out loud.", small=True),
                Table(headers=["Asset", "Type", "How it is linked", "Confirmed by"],
                      rows=[[str(link.get("label")),
                             str(link.get("node_type", "")).replace("_", " "),
                             str(link.get("link_meaning") or link.get("link_type")),
                             str(link.get("confirmed_by") or "unconfirmed")]
                            for link in assets[:24]],
                      widths=[2.2, 1, 2.4, 1.1]))
    else:
        doc.add(Heading("Named Orange assets"),
                Callout("No Orange asset is linked to this space. That is the honest position "
                        "and it is worth knowing before a meeting: anything claimed here would "
                        "be a claim about capability Orange has not yet connected to this "
                        "opportunity."))

    if references:
        doc.add(Spacer(4), Heading("Published references"),
                Table(headers=["Reference", "Link"],
                      rows=[[str(link.get("label")),
                             str(link.get("link_meaning") or link.get("link_type"))]
                            for link in references[:20]],
                      widths=[1.2, 1]))

    geographies = ctx.topic.get("geographies") or []
    if geographies:
        doc.add(Spacer(4), Heading("Where the evidence is from"),
                Para(", ".join(str(g) for g in geographies)))

    doc.add(*_sources(content), *_provenance(ctx, written=False))
    return doc


# ---------------------------------------------------------------------------
# 4 — Demo / PoC scoping sheet
# ---------------------------------------------------------------------------

def demo_scope(ctx: TopicContext, content: dict[str, Any]) -> Document:
    doc = _open(ctx, "Proof of concept — scoping sheet",
                "Agreed before the work starts. The out-of-scope column is the one that "
                "prevents the argument in week three.", "PoC scoping sheet")
    doc.add(_gap_note(ctx, ["description"]))

    phases = content.get("phases") or []
    if phases:
        total = sum(int(p.get("weeks", 0)) for p in phases)
        rows = [(p["label"], int(p["weeks"]), p["deliverable"]) for p in phases]
        doc.add(
            KPIs(cells=[(f"{total} weeks", "end to end"), (str(len(phases)), "phases"),
                        (str(len(content.get("success_criteria") or [])), "success criteria")],
                 tones=["accent", "", ""]),
            Heading("Shape of the engagement"),
            Para("Durations are proposal shapes, not commitments — they exist so the customer "
                 "can see the sequence and the deliverable at each step.", small=True),
            Chart(build=lambda w, r=rows: charts.PhaseTimeline(r, w)),
            Spacer(4),
        )

    in_scope = content.get("in_scope") or []
    out_scope = content.get("out_scope") or []
    if in_scope or out_scope:
        doc.add(Heading("Where the line is"),
                Chart(build=lambda w, i=in_scope, o=out_scope: charts.ScopeBoundary(i, o, w)),
                Spacer(4))

    criteria = content.get("success_criteria") or []
    if criteria:
        doc.add(Heading("Success criteria"),
                Para("Written before the work starts, and observable at the end of it. A "
                     "criterion nobody can measure is a criterion nobody can fail.", small=True),
                Table(headers=["This is a success if", "Measured by"],
                      rows=[[row["criterion"], row["measured_by"]] for row in criteria],
                      widths=[1.1, 1]))

    provides = content.get("customer_provides") or []
    if provides:
        doc.add(Spacer(4), Heading("What the customer has to provide"),
                Para("Every one of these is a dependency that can stall the PoC. Confirm each "
                     "has a name against it before the kick-off.", small=True),
                Bullets(provides))

    doc.add(*_sources(content), *_provenance(ctx, written=bool(phases)))
    return doc


# ---------------------------------------------------------------------------
# 5 — Bid risk & objection register
# ---------------------------------------------------------------------------

def risk_register(ctx: TopicContext, content: dict[str, Any]) -> Document:
    doc = _open(ctx, "Bid risk & objection register",
                "Internal. Not for the customer — which is what lets it be blunt about "
                "Orange's own gaps.", "Bid risk register")
    doc.add(_gap_note(ctx, ["description"]))

    risks = content.get("risks") or []
    if risks:
        severe = sum(1 for r in risks if r["likelihood"] + r["impact"] >= 3)
        doc.add(
            KPIs(cells=[(str(len(risks)), "risks on the register"),
                        (str(severe), "in the high band"),
                        (str(len({r["owner_role"] for r in risks})), "owning roles")],
                 tones=["", "high" if severe else "", ""]),
            Heading("Likelihood against impact"),
            Para("Numbered to the table below. Bands are judgements from the bid team's own "
                 "reading, and each cell says its band in words as well as colour.", small=True),
            Chart(build=lambda w, r=risks: charts.RiskMatrix(r, w)),
            Spacer(4),
            Heading("The register"),
            Table(headers=["#", "Risk", "Band", "Mitigation", "Owner"],
                  rows=[[str(index),
                         risk["risk"],
                         ("low" if risk["likelihood"] + risk["impact"] <= 1
                          else "medium" if risk["likelihood"] + risk["impact"] <= 2
                          else "high").upper(),
                         risk["mitigation"], risk["owner_role"]]
                        for index, risk in enumerate(risks, start=1)],
                  widths=[0.3, 2.2, 0.7, 2.4, 1.2]),
        )

    unknowns = ctx.section_text("risks_and_unknowns")
    if unknowns:
        doc.add(Spacer(4), Heading("What the radar itself says is unknown"), Para(unknowns))

    doc.add(*_sources(content), *_provenance(ctx, written=bool(risks)))
    return doc


# ---------------------------------------------------------------------------
# 6 — Partner engagement brief
# ---------------------------------------------------------------------------

def partner_brief(ctx: TopicContext, content: dict[str, Any]) -> Document:
    doc = _open(ctx, "Partner engagement brief",
                "Where the portfolio stops and somebody else has to start.",
                "Partner engagement brief")

    distance = ctx.portfolio_distance
    doc.add(KPIs(cells=[(f"L{distance}", "portfolio distance"),
                        (str(len(ctx.orange_assets)), "assets Orange already has"),
                        (str(len(content.get("gaps") or [])), "capability gaps named")],
                 tones=["accent" if distance else "", "", ""]))

    if distance == 0:
        doc.add(Callout("This space is at L0 — Orange can already deliver it from named assets. "
                        "This brief exists to record that, not to request anything. The partner "
                        "conversation this document normally starts is not needed here."))

    hops = _portfolio_hops(ctx, content)
    if hops:
        doc.add(Heading("The shortest path to something deliverable"),
                Para("This is what the L badge on the radar actually means. Each grey box is a "
                     "capability somebody has to supply before this is sellable.", small=True),
                Chart(build=lambda w, h=hops: charts.PortfolioPath(h, w)),
                Spacer(4))

    gaps = content.get("gaps") or []
    if gaps:
        doc.add(Heading("What is missing"),
                Para("Kinds of partner, not named companies — naming one here would be a "
                     "commitment the radar has no basis to make.", small=True),
                Table(headers=["Capability", "Why this deal needs it", "Kind of partner"],
                      rows=[[gap["capability"], gap["why_needed"], gap["candidate_type"]]
                            for gap in gaps],
                      widths=[1.6, 2.4, 2.2]))

    brings = content.get("what_orange_brings") or []
    if brings:
        doc.add(Spacer(4), Heading("What Orange brings to the table"), Bullets(brings))

    if content.get("the_ask"):
        doc.add(Spacer(4), Heading("The ask"), Para(content["the_ask"], bold=True))

    components = _components(ctx, {})
    if components:
        doc.add(Spacer(4), Heading("Who owns what, today"),
                Chart(build=lambda w, c=components: charts.ComponentMap(c, w)))

    doc.add(*_sources(content), *_provenance(ctx, written=bool(gaps)))
    return doc


# ---------------------------------------------------------------------------
# 7 — RFP / tender response blocks
# ---------------------------------------------------------------------------

def rfp_boilerplate(ctx: TopicContext, content: dict[str, Any]) -> Document:
    """Answer blocks, in whichever editable format the bid team works in.

    The bracketed placeholders are left in deliberately and named at the top:
    a block that reads as finished is a block that goes into a tender with
    [customer name] still in it.
    """
    doc = _open(ctx, "Tender response blocks",
                "Starting blocks, not a submission.", "Tender response blocks")
    doc.add(Callout("Every bracketed placeholder must be replaced before this goes anywhere "
                    "near a tender, and every claim about Orange capability should be checked "
                    "against the reference pack for this space."))

    blocks = content.get("blocks") or []
    if not blocks:
        doc.add(Para("The narrative for this space has not been generated, so no answer blocks "
                     "could be written. Generate the description for this space and rebuild "
                     "this document."))
    for block in blocks:
        doc.add(Heading(block["section"]))
        for paragraph in str(block["answer"]).split("\n"):
            if paragraph.strip():
                doc.add(Para(paragraph.strip()))

    doc.add(PageBreak(), *_sources(content), *_provenance(ctx, written=bool(blocks)))
    return doc


# ---------------------------------------------------------------------------
# 8 — Outreach sequence
# ---------------------------------------------------------------------------

def outreach_sequence(ctx: TopicContext, content: dict[str, Any]) -> Document:
    doc = _open(ctx, "Outreach sequence",
                "Copy one at a time. Replace [first name] and [company] before sending. Each "
                "email makes exactly one ask; sending two of these in a week undoes both.",
                "Outreach sequence")

    emails = content.get("emails") or []
    if not emails:
        doc.add(Callout("The narrative for this space has not been generated, so no sequence "
                        "could be written. Generate the description and rebuild."))
    for index, email in enumerate(emails, start=1):
        doc.add(Heading(f'{index}. {email["stage"].title()}'),
                Para(f'<b>Subject:</b> {email["subject"]}', markup=True),
                Para(email["body"]),
                Spacer(3))

    who = ctx.section_text("who_buys_and_why")
    if who:
        doc.add(Heading("Why these land"), Para(who))

    doc.add(*_sources(content), *_provenance(ctx, written=bool(emails)))
    return doc


DOCUMENTS = {
    "discovery-pack": discovery_pack,
    "battlecards": battlecards,
    "reference-pack": reference_pack,
    "demo-scope": demo_scope,
    "risk-register": risk_register,
    "partner-brief": partner_brief,
    "rfp-boilerplate": rfp_boilerplate,
    "outreach-sequence": outreach_sequence,
}
