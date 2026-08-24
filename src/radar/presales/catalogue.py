"""What pre-sales collateral exists, and what each piece is for.

One table, read by the API, the renderers and the UI alike, so the tab cannot
advertise a document the builder does not know how to make.

THE FORMAT IS PART OF THE ARTEFACT, not a preference. A battlecard is a PDF
because it is read on a phone in a car park and must not have been edited since
it was approved. A solution outline is a PPTX because the first thing a solution
architect does with it is paste two slides into their own deck, and handing them
a PDF makes them rebuild it. RFP boilerplate is a DOCX because it is paste-fodder
for a Word response and a PDF would be actively obstructive. The outreach
sequence is Markdown because nobody has ever wanted a PDF of six emails.

`needs` names the inputs a piece cannot be honest without. The builder generates
missing inputs where they are cheap and deterministic (sizing, competition) and
reports the gap where they are not, rather than rendering a document with a hole
in it and letting the reader find it in front of a customer.
"""

from __future__ import annotations

from typing import Any

MEDIA_TYPES = {
    "pdf": "application/pdf",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "odt": "application/vnd.oasis.opendocument.text",
    "odp": "application/vnd.oasis.opendocument.presentation",
    "md": "text/markdown; charset=utf-8",
}

FORMAT_LABELS = {
    "pdf": "PDF",
    "docx": "Word (.docx)",
    "odt": "OpenDocument (.odt)",
    "pptx": "PowerPoint (.pptx)",
    "odp": "OpenDocument (.odp)",
    "md": "Markdown (.md)",
}

#: The two families, and the formats each can be emitted in. The FIRST entry is
#: the default — the format the artefact wants to be — and the rest are there
#: because the choice is the reader's, not this code's: a battlecard is a PDF in
#: a car park, a Word file on a bid manager's desk and an ODF file on an estate
#: that standardised on LibreOffice, and it is the same battlecard in all three.
#:
#: A deck is never offered as .docx and a document is never offered as .pptx.
#: That is not squeamishness — a deck flowed into a Word document stops being a
#: deck, because one-idea-per-page is the only property that made it one.
DOCUMENT_FORMATS = ["pdf", "docx", "odt"]
DECK_FORMATS = ["pptx", "odp", "pdf"]

#: Bumped when a piece's sections change, so collateral built before a section
#: existed is detectable as INCOMPLETE rather than merely old — the same
#: distinction `brief.BRIEF_SCHEMA` draws, and for the same reason.
COLLATERAL_SCHEMA = "presales-1"

#: Ordered as the work arrives: qualify, design, compete, justify, prove,
#: present, pilot, respond, reach out, price, de-risk, partner.
CATALOGUE: list[dict[str, Any]] = [
    {
        "kind": "discovery-pack",
        "title": "Discovery & qualification pack",
        "format": "pdf",
        "formats": DOCUMENT_FORMATS,
        "audience": "Account manager, before and during the first meeting",
        "summary": "The qualifying questions and objection handling as a working checklist, "
                   "with the buying centre drawn out: who signs, who feels the pain, and "
                   "what event makes them act.",
        "charts": ["Buying-centre map", "Evidence coverage"],
        "needs": ["description"],
        "model_calls": 1,
    },
    {
        "kind": "solution-outline",
        "title": "Solution outline (HLD)",
        "format": "pptx",
        "formats": DECK_FORMATS,
        "audience": "Solution architect / pre-sales engineer",
        "summary": "The solution drawn as layers and flows, plus a component map coloured by "
                   "who owns each piece — so the gaps that still have to be sourced are "
                   "countable at a glance.",
        "charts": ["Layered solution diagram", "Component ownership map", "Portfolio path"],
        "needs": ["description"],
        "model_calls": 1,
    },
    {
        "kind": "battlecards",
        "title": "Competitor battlecards",
        "format": "pdf",
        "formats": DOCUMENT_FORMATS,
        "audience": "Anyone walking into a competitive deal",
        "summary": "One card per named competitor: their pitch, where they are strong, where "
                   "they are thin, the question that exposes it, and the Orange proof point — "
                   "with the whole field mapped on one page first.",
        "charts": ["Competitive field map", "Strength comparison per competitor"],
        "needs": ["competition", "analysis"],
        "model_calls": 1,
    },
    {
        "kind": "value-hypothesis",
        "title": "Value hypothesis & business case",
        "format": "pptx",
        "formats": DECK_FORMATS,
        "audience": "Economic buyer, via the account team",
        "summary": "The market sized bottom-up as a funnel, the value built up step by step as "
                   "a waterfall, and the payback curve with the crossing called out. Every "
                   "figure decomposes into stored components.",
        "charts": ["TAM/SAM/SOM funnel", "Value waterfall", "Payback curve"],
        "needs": ["sizing"],
        "model_calls": 1,
    },
    {
        "kind": "reference-pack",
        "title": "Reference & proof pack",
        "format": "pdf",
        "formats": DOCUMENT_FORMATS,
        "audience": "Sent ahead of a bid, or left behind after one",
        "summary": "The named Orange assets, references and certifications behind this space, "
                   "with the evidence coverage stated plainly — including where it is thin.",
        "charts": ["Asset coverage by type", "Geographic coverage"],
        "needs": [],
        "model_calls": 0,
    },
    {
        "kind": "first-meeting-deck",
        "title": "First-meeting deck",
        "format": "pptx",
        "formats": DECK_FORMATS,
        "audience": "The first customer conversation",
        "summary": "Ten slides with speaker notes: what changed, why now, what we would build, "
                   "why Orange, what it is worth, what happens next. Carries the solution "
                   "diagram and the sizing funnel.",
        "charts": ["Layered solution diagram", "TAM/SAM/SOM funnel", "Competitive field map"],
        "needs": ["description"],
        "model_calls": 1,
    },
    {
        "kind": "demo-scope",
        "title": "Demo / PoC scoping sheet",
        "format": "pdf",
        "formats": DOCUMENT_FORMATS,
        "audience": "Agreed between the account team and the customer",
        "summary": "What gets proved, in how long, by whom, with success criteria written "
                   "before the work starts — and an explicit out-of-scope column, because "
                   "every PoC argument is about a box somebody assumed was inside the line.",
        "charts": ["Phase timeline", "Scope boundary"],
        "needs": ["description"],
        "model_calls": 1,
    },
    {
        "kind": "rfp-boilerplate",
        "title": "RFP / tender response blocks",
        "format": "docx",
        "formats": ["docx", "odt", "pdf"],
        "audience": "Bid manager, pasting into a response",
        "summary": "Reusable answer blocks for the sections every tender asks for — approach, "
                   "architecture, security and sovereignty, SLA, references — as editable "
                   "Word text rather than a PDF nobody can use.",
        "charts": [],
        "needs": ["description"],
        "model_calls": 1,
    },
    {
        "kind": "outreach-sequence",
        "title": "Outreach email sequence",
        "format": "md",
        "formats": ["md", "docx", "odt", "pdf"],
        "audience": "Account manager, copy and paste",
        "summary": "First touch, follow-up, breakup and re-engagement, written from the trigger "
                   "events in the buying analysis. Markdown, because these get pasted into a "
                   "mail client, not printed.",
        "charts": [],
        "needs": ["description"],
        "model_calls": 1,
    },
    {
        "kind": "pricing-options",
        "title": "Commercial model options",
        "format": "pptx",
        "formats": DECK_FORMATS,
        "audience": "Deal desk and the account team",
        "summary": "Subscription, outcome-based and managed-service framings side by side, with "
                   "the levers named and the risk each one moves. Indicative shapes, not a "
                   "price list.",
        "charts": ["Option comparison"],
        "needs": ["sizing"],
        "model_calls": 1,
    },
    {
        "kind": "risk-register",
        "title": "Bid risk & objection register",
        "format": "pdf",
        "formats": DOCUMENT_FORMATS,
        "audience": "Internal — the bid team",
        "summary": "The internal sibling of objection handling: what could stall or kill this, "
                   "plotted on likelihood against impact, each with an owner and a mitigation.",
        "charts": ["Risk matrix"],
        "needs": ["description"],
        "model_calls": 1,
    },
    {
        "kind": "partner-brief",
        "title": "Partner engagement brief",
        "format": "pdf",
        "formats": DOCUMENT_FORMATS,
        "audience": "Business unit or partner manager",
        "summary": "Where the portfolio stops and somebody else has to start: the shortest path "
                   "to a deliverable configuration, what is missing at each hop, and the ask.",
        "charts": ["Portfolio path", "Component ownership map"],
        "needs": [],
        "model_calls": 1,
    },
]

BY_KIND = {entry["kind"]: entry for entry in CATALOGUE}


def entry(kind: str) -> dict[str, Any]:
    if kind not in BY_KIND:
        raise KeyError(f"No such pre-sales collateral: {kind}")
    return BY_KIND[kind]


def formats_for(kind: str) -> list[str]:
    """Which output formats this piece can be emitted in, default first."""
    return list(entry(kind)["formats"])


def resolve_format(kind: str, fmt: str | None) -> str:
    """The requested format, or the piece's default. Raises on an unsupported one.

    Checked rather than coerced: silently falling back to the default would hand
    somebody who asked for ODF a .pptx with an .odp name, which fails at the
    point they try to open it in front of somebody.
    """
    allowed = formats_for(kind)
    if fmt is None:
        return allowed[0]
    fmt = str(fmt).strip().lower().lstrip(".")
    if fmt not in allowed:
        raise ValueError(
            f"{entry(kind)['title']} cannot be produced as .{fmt} — "
            f"available: {', '.join(allowed)}")
    return fmt


def filename_for(topic_id: str, kind: str, fmt: str | None = None) -> str:
    return f"{topic_id}-{kind}.{resolve_format(kind, fmt)}"


def media_type_for(kind: str, fmt: str | None = None) -> str:
    return MEDIA_TYPES[resolve_format(kind, fmt)]
