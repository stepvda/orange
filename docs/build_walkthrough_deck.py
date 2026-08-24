#!/usr/bin/env python3
"""Build the walkthrough deck (docs/Orange_Innovation_Radar_Walkthrough.pptx).

A different deck from Orange_Innovation_Radar.pptx, for a different job. That one
argues WHY the product is built the way it is; this one shows HOW TO USE IT, in
the order somebody actually would — and it is the same order the narrated demo
film takes, because the film's chapter cards are rendered from these slides.

Seven chapters:

  1  The radar, and one opportunity space
  2  Role modes — the same data, three rankings
  3  One space, full screen: the four tabs
  4  The workflow board — and what it feeds
  5  Analytics
  6  Creating a space: the two routes in
  7  The Planner

Every screenshot is the real application, captured by docs/build_shots.py
against the running instance. Layout helpers are imported from build_deck.py so
the two decks cannot drift apart typographically.

    python3 docs/build_shots.py            # first — needs the app running
    python3 docs/build_walkthrough_deck.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from build_deck import (BLUE, GREEN, INK, LIGHT, MONO, MUTED, ORANGE, RED, RULE, SANS, W, H,
                        WHITE, F, blank, bullets, caption, header, picture, rect, stat, text)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "Orange_Innovation_Radar_Walkthrough.pptx"

PALE = RGBColor(0xC3, 0xC2, 0xB7)

CHAPTERS = [
    ("1", "The radar, and one opportunity space",
     "Four channels on one chart, the filter rail, and every number opened up"),
    ("2", "Role modes",
     "The same data, three genuinely different rankings — and the screen says which one you are in"),
    ("3", "One space, full screen",
     "Four tabs, in the order the questions arrive"),
    ("4", "The workflow board",
     "Who owns this now — and the input to a plan nobody has to re-enter"),
    ("5", "Analytics",
     "Where the portfolio is thin, and where the team and the evidence disagree"),
    ("6", "Creating a space",
     "Two routes in, and one gate the corpus holds"),
    ("7", "The Planner",
     "Which set, in what order, and what it earns"),
]


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def chapter(prs, number: str, title: str, sub: str, n: int) -> int:
    """A full-bleed divider. The demo film cuts to these between sections, so
    they carry the number as well as the title — a viewer who looked away needs
    to know where they are, not just what they are looking at."""
    s = blank(prs)
    rect(s, 0, 0, W, H, fill=INK)
    rect(s, 0, 0, Inches(0.22), H, fill=ORANGE)
    text(s, Inches(1.1), Inches(2.35), Inches(11), Inches(0.5),
         f"CHAPTER {number}", size=13, color=ORANGE, bold=True, font=MONO)
    text(s, Inches(1.1), Inches(2.95), Inches(11), Inches(1.2), title,
         size=44, bold=True, color=WHITE, spacing=1.05)
    text(s, Inches(1.1), Inches(4.45), Inches(10.4), Inches(0.9), sub,
         size=17, color=PALE, spacing=1.3)
    return n + 1


def screen(prs, shot_name: str, title: str, sub: str, points: list, n: int,
           note: str | None = None) -> int:
    """A screenshot with what to look at beside it. The points are what the
    narration says, so the slide and the film cannot disagree."""
    s = blank(prs)
    rect(s, 0, 0, W, Inches(0.06), fill=ORANGE)
    text(s, Inches(0.7), Inches(0.4), Inches(7.4), Inches(0.3),
         "WALKTHROUGH", size=10.5, color=ORANGE, bold=True)
    text(s, Inches(0.7), Inches(0.72), Inches(4.1), Inches(1.1), title, size=25, bold=True)
    text(s, Inches(0.7), Inches(1.86), Inches(4.0), Inches(0.6), sub, size=12.5, color=ORANGE,
         spacing=1.22)
    # A heading is allowed to run to two lines, so the body starts below where
    # a second line would land rather than on top of it.
    y = Inches(2.44)
    for head, body in points:
        rect(s, Inches(0.7), y + Inches(0.05), Inches(0.05), Inches(0.5), fill=ORANGE)
        text(s, Inches(0.9), y, Inches(3.7), Inches(0.45), head, size=12, bold=True)
        text(s, Inches(0.9), y + Inches(0.42), Inches(3.7), Inches(0.8), body,
             size=9.5, color=MUTED, spacing=1.2)
        # 1.15in per point is what a two-line heading over a three-line body
        # needs. Four of those still clear the footer; five would not, which is
        # why no slide here carries five.
        y += Inches(1.13)
    picture(s, shot_name, Inches(4.95), Inches(0.95), Inches(7.9))
    if note:
        assert len(points) <= 3, "a fourth point leaves no room for a note"
        text(s, Inches(0.7), Inches(6.4), Inches(3.7), Inches(0.5), note,
             size=9.5, color=MUTED, spacing=1.25)
    footer_(s, n + 1)
    return n + 1


def footer_(slide, n: int) -> None:
    text(slide, Inches(0.7), Inches(7.0), Inches(8), Inches(0.3),
         "Orange Business · Innovation Radar · walkthrough", size=9, color=MUTED)
    from pptx.enum.text import PP_ALIGN
    text(slide, Inches(11.6), Inches(7.0), Inches(1.0), Inches(0.3),
         str(n), size=9, color=MUTED, align=PP_ALIGN.RIGHT, font=MONO)


# ---------------------------------------------------------------------------
# Slides
# ---------------------------------------------------------------------------

def build():
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H
    n = 0

    # ---- 1. Title --------------------------------------------------------
    s = blank(prs)
    rect(s, 0, 0, W, H, fill=INK)
    rect(s, 0, 0, Inches(0.22), H, fill=ORANGE)
    text(s, Inches(1.1), Inches(2.05), Inches(11), Inches(0.4),
         "ORANGE BUSINESS", size=13, color=ORANGE, bold=True)
    text(s, Inches(1.1), Inches(2.5), Inches(11), Inches(1.4),
         "Innovation Radar\nWalkthrough", size=48, bold=True, color=WHITE, spacing=1.05)
    text(s, Inches(1.1), Inches(4.3), Inches(10.2), Inches(0.9),
         "A guided tour of the working application — every screen, in the order somebody would "
         "actually use them, against the live corpus.", size=15, color=PALE, spacing=1.3)
    text(s, Inches(1.1), Inches(5.55), Inches(11), Inches(0.4),
         f"{F.get('topics')} opportunity spaces  ·  {F.get('signals', 0):,} signals  ·  "
         f"weight set {F.get('weight_set', 'w-2026-08-a')}",
         size=12, color=ORANGE, font=MONO)
    n += 1

    # ---- 2. Contents -----------------------------------------------------
    s = blank(prs); y = header(s, "Walkthrough", "Seven chapters, in this order",
                               "The order is not arbitrary — each chapter uses something the one before it produced.")
    for i, (num, title_, sub) in enumerate(CHAPTERS):
        col, row = i % 2, i // 2
        x = Inches(0.75) + Inches(6.15) * col
        yy = y + Inches(1.12) * row
        rect(s, x, yy, Inches(5.85), Inches(0.98), fill=LIGHT)
        text(s, x + Inches(0.24), yy + Inches(0.14), Inches(0.5), Inches(0.3), num,
             size=17, bold=True, color=ORANGE, font=MONO)
        text(s, x + Inches(0.72), yy + Inches(0.13), Inches(5.0), Inches(0.3), title_,
             size=14.5, bold=True)
        text(s, x + Inches(0.72), yy + Inches(0.46), Inches(5.0), Inches(0.45), sub,
             size=10, color=MUTED, spacing=1.25)
    footer_(s, n := n + 1)

    # ================================================== CHAPTER 1 — the radar
    n = chapter(prs, *CHAPTERS[0], n)

    n = screen(prs, "radar", "The radar",
               "Four channels at once, no legend to study",
               [("Angular sector is the domain",
                 "Six sectors around the circle. Position carries identity, which frees colour to "
                 "carry a quantity instead."),
                ("Distance from the centre is time",
                 "Now in the middle, Later at the rim. A topic drifts inward as its evidence matures."),
                ("Size is attractiveness; colour is right to win",
                 "The two questions the radar exists to answer, visible in one glance and never "
                 "combined into a single number."),
                ("A ! inside a marker is an evidence gap",
                 "Orange has few or no published references in that vertical. A glyph as well as a "
                 "colour, so the warning never depends on colour alone.")], n)

    n = screen(prs, "radar_hover", "One space, at a glance",
               "Four questions answered without a click",
               [("The statement, not a keyword",
                 "Specific enough to open a customer meeting with. “AI” and “cloud” "
                 "fail validation as topics; this is the bar."),
                ("Both scores, side by side",
                 "Attractiveness and right to win are shown as two numbers because they answer two "
                 "questions owned by two different people."),
                ("Horizon, portfolio distance, signal count",
                 "L0 means an existing offer already covers it. L4 is white space. That one number "
                 "decides whose conversation this is."),
                ("Serviceable market and competition",
                 "Both computed, both filterable — a number the radar computes but cannot be sorted "
                 "on is a number nobody uses.")], n)

    n = screen(prs, "list", "The filter rail and the list",
               "Multi-select, and the counts are real",
               [("Counts cover the whole set, not the page",
                 "Not over the page. “CISO: 0” once meant “none on this screen” while "
                 "37 matched — the facets are now server-computed."),
                ("Filters that answer a question",
                 "Horizon, competition band, has-a-sales-brief, vertical, use case, technology, "
                 "portfolio distance, evidence gap."),
                ("The list is the same data, ranked",
                 "Same corpus, same scores. What changes between the radar and the list is only "
                 "what you can scan quickly."),
                ("Any view is a link",
                 "Role, tab, filters, sort and selection are all in the address bar, so a prepared "
                 "view can be sent to a colleague.")], n)

    n = screen(prs, "detail", "The detail pane",
               "In the order the questions arrive",
               [("What is it, and why now",
                 "Each claim carries the signal identifiers it was written from. An uncited claim is "
                 "removed rather than rewritten."),
                ("Where the value lands, and for whom",
                 "The buyer, the trigger, and the job the technology does — not a description of the "
                 "technology."),
                ("Can we play, can we win",
                 "Itemised against named Orange offers, references, partners and certifications. "
                 "Query results, never a model's assertion."),
                ("The next action, for this role",
                 "Different per role, because a strategist and a salesperson do not do the same "
                 "thing with the same topic.")], n)

    n = screen(prs, "explain", "How this score was calculated",
               "Checkable, rather than asserted",
               [("The weight table and the total",
                 "Every component with the arithmetic that produced it, not a tooltip saying the "
                 "score is “based on” something."),
                ("The evidence behind each component",
                 "Publisher entropy and the publishers counted, the tier distribution, the periods "
                 "the momentum slope was fitted to."),
                ("The reproducibility stamps",
                 "Weight set, pipeline, prompt and model version. A number you cannot re-derive is "
                 "not explained — only displayed."),
                ("Reachable wherever a number appears",
                 "The detail pane, every list row and the workflow board, and it deep-links.")], n)

    # ============================================== CHAPTER 2 — role modes
    n = chapter(prs, *CHAPTERS[1], n)

    n = screen(prs, "roles", "Three role modes",
               "They fall out of portfolio distance",
               [("The instruction line, on every screen",
                 "“Strategist / Innovator. Decide where to invest study and prototyping effort "
                 "next quarter.” The screen says which question it is answering."),
                ("Strategist sees L1–L4",
                 "Ranks on attractiveness and novelty. Low right-to-win is a flag, not a penalty — "
                 "white space is the point."),
                ("Sales sees L0–L1 only",
                 "Ranks on right to win and proof-point density, and only shows topics with a "
                 "delivery path, a published reference in the vertical, and no evidence gap."),
                ("Presales sees L0–L2",
                 "Ranks on differentiation: where Orange has assets and the market has few credible "
                 "providers.")], n)

    n = screen(prs, "role_help", "Why the roles differ",
               "Every dense concept explains itself",
               [("The same data, three ranking functions",
                 "Not one score shown through three filters. Each role has its own weighted blend, "
                 "and the blend is configuration, not code."),
                ("A high-attractiveness L4 topic",
                 "Is exactly the strategist's innovation agenda — and exactly what a salesperson "
                 "should never be shown, because there is nothing to sell."),
                ("Help says what, why, and which requirement",
                 "So the answer is checkable rather than merely confident. One registry, so the "
                 "explanation and the behaviour cannot drift apart.")], n)

    # =========================================== CHAPTER 3 — full screen
    n = chapter(prs, *CHAPTERS[2], n)

    n = screen(prs, "fs_space", "Tab 1 — the opportunity space",
               "The same content with the panes out of the way",
               [("Why full screen exists",
                 "The three-pane layout is right for working THROUGH the radar. It is wrong for the "
                 "moment somebody reads a space: ten sections in a 420px column."),
                ("Everything the space knows",
                 "Statement, triple, both scores, sizing with its working, competition, evidence "
                 "timeline, links, stage, and the delete."),
                ("Escape returns you to the radar",
                 "With the selection, filters and role intact, because the address bar carried "
                 "them the whole time.")], n)

    n = screen(prs, "fs_competitors", "Tab 2 — competitors",
               "Who else is here, and what we say",
               [("A named field, not just a band",
                 "The band is on the space; this is per competitor: what they say they sell here, "
                 "from pages they published, each claim carrying the page."),
                ("A differentiation angle per competitor",
                 "And a paragraph naming an Orange asset the graph does not hold is stripped, while "
                 "the half describing the competitor survives."),
                ("A refusal is marked, not omitted",
                 "Not omitted. A gap in the register is reported as a gap rather than read as "
                 "“no competitor found”.")], n)

    n = screen(prs, "fs_brief", "Tab 3 — the sales brief",
               "The meeting PDF, rendered in place",
               [("Six pages, every figure stamped",
                 "Weight set, sizing version, prompt and model version on the last page, so a brief "
                 "can be checked against the run that produced it."),
                ("It knows when it is out of date",
                 "The topic has been refreshed since this was built, and the banner says so. That "
                 "is why the brief sits beside the space rather than behind a download."),
                ("Incomplete is not the same as stale",
                 "A stale brief was correct when built. An incomplete one never had a section that "
                 "current briefs carry — and waiting does not fix it.")], n)

    n = screen(prs, "fs_presales", "Tab 4 — pre-sales collateral",
               "For the work between meeting and proposal",
               [("All twelve are listed, built or not",
                 "What COULD be produced is as much of the answer as what has been, and a screen "
                 "that starts empty is one nobody presses a button on."),
                ("Grouped by when they are used",
                 "Before the meeting, in the meeting, after it, and in the bid — qualification, "
                 "battlecards, a solution outline, tender blocks, a risk register."),
                ("The format is your choice, per piece",
                 "PDF, Word or OpenDocument for documents; PowerPoint, OpenDocument or PDF for "
                 "decks. Asking for Word after the PDF gives you both."),
                ("Built from ONE snapshot of the space",
                 "So nothing in a pack can quote a different market size from anything else in "
                 "it.")], n)

    # ============================================== CHAPTER 4 — workflow
    n = chapter(prs, *CHAPTERS[3], n)

    n = screen(prs, "workflow", "The stage gate",
               "Shortlisted → Demand-tested → Packaged → Live",
               [("Ownership follows the stage",
                 "Strategist, then sales, then presales. Every transition records who moved it and "
                 "why."),
                ("Stalled cards are flagged",
                 "Latency is the known weakness of a stage gate — a topic dies waiting for its "
                 "owner — so age-in-stage is computed rather than left to be noticed."),
                ("Each role rates only its own axis",
                 "0–5 with written anchors. Those ratings become conviction, which changes what "
                 "surfaces first and never touches either score."),
                ("This board is an input to the Planner",
                 "Everything past Demand-tested can be planned directly — chapter 7 uses exactly "
                 "this, as a portfolio the business already committed to.")], n)

    # ============================================= CHAPTER 5 — analytics
    n = chapter(prs, *CHAPTERS[4], n)

    n = screen(prs, "analytics", "Analytics",
               "Charts chosen by the job the data does",
               [("Vertical × domain is magnitude",
                 "So it is sequential, and blue — orange already means right to win, and reusing it "
                 "would imply the same quantity."),
                ("Conviction vs evidence is polarity",
                 "So it is diverging with a neutral midpoint: agreement reads as nothing, and only "
                 "disagreement draws the eye."),
                ("The stage funnel is ordered",
                 "So it is ordinal. Only the signal-type mix is genuinely categorical, and it ships "
                 "a legend and a table."),
                ("What it is for",
                 "Where the portfolio is thin, where the team and the evidence disagree, and how "
                 "much of the grid has evidence at all.")], n)

    # ============================================ CHAPTER 6 — generation
    n = chapter(prs, *CHAPTERS[5], n)

    n = screen(prs, "generate_grid", "Route 1 — parameters",
               "For somebody who knows the taxonomy",
               [("Pick the cell you want covered",
                 "A vertical, a use case, a technology, a horizon — and the screen counts how much "
                 "evidence is behind that combination before you spend anything."),
                ("It shows what ALREADY matches",
                 "The most common outcome of an on-demand run is rediscovering what the last "
                 "refresh produced, and finding that out afterwards costs four model calls."),
                ("The same pipeline, the same guards",
                 "A space created here goes through the identical evidence binding, closed "
                 "vocabulary, no-generated-numbers and entailment checks.")], n)

    n = screen(prs, "generate_chat", "Route 2 — a scoping conversation",
               "For somebody who knows their market",
               [("The assistant interviews, corpus in hand",
                 "Every turn re-embeds the whole transcript against the same signal vectors the run "
                 "will read, and shows what came back beside the answer."),
                ("Publisher, date and cosine, per signal",
                 "So the conversation is about evidence rather than about phrasing, and an answer "
                 "that sharpens the idea sharpens the next question."),
                ("The corpus enables the button",
                 "Asked “do you have enough?” a model says yes. A brief must clear the run's "
                 "own retrieval floor AND be corroborated on its use case or technology."),
                ("A refusal comes before the spend",
                 "Not after. And where a brief cannot be run, the contributed-evidence route opens "
                 "instead — the path that can actually build it.")], n)

    # ============================================== CHAPTER 7 — the Planner
    n = chapter(prs, *CHAPTERS[6], n)

    n = screen(prs, "planner_form", "Source 1 — parameters",
               "State the constraints; it chooses the set",
               [("A ranked list cannot answer this",
                 "It assumes you can take the top N, and you cannot — not 400 spaces at once, and "
                 "not twelve in one vertical."),
                ("The constraints you would state aloud",
                 "Entry slots per year, capability headcount available for new work, an evidence "
                 "floor, a distance cap, a concentration cap, a horizon mix."),
                ("Selection and projection are arithmetic",
                 "No model call, so it is immediate. The written business plan is a separate step, "
                 "and it may not introduce a figure."),
                ("A different objective, a different set",
                 "Profit, revenue, NPV or strategic coverage. That is a decision, and the screen "
                 "says so rather than defaulting silently.")], n)

    n = screen(prs, "planner_overview", "What the plan reports",
               "Including which constraint bound it",
               [("Revenue and profit, with the band",
                 "The interval is the sizing engine's own low and high estimates, not error bars "
                 "invented for the chart."),
                ("The entry schedule",
                 "Staggered by horizon and by what capacity allowed. A cohort bigger than a year's "
                 "slots cascades forward rather than pretending the capacity exists."),
                ("Capability pool utilisation",
                 "Peak load against the share of headcount available for new work — the constraint "
                 "that binds first in most plans."),
                ("From candidates to committed",
                 "What each constraint removed, at each step. That is the thing a ranked list "
                 "cannot tell you, because the answer is a constraint rather than a score.")], n)

    n = screen(prs, "plannerwf_form", "Source 2 — workflow selected",
               "Already decided — this only schedules it",
               [("Everything past Demand-tested is in",
                 "No evidence floor, no distance cap, no concentration limit and no objective — "
                 "each would overrule a decision somebody already took."),
                ("Horizon spreads it across time",
                 "Each space enters when its market arrives; a space already Live starts in year "
                 "one whatever its horizon says."),
                ("Nothing is dropped to make it fit",
                 "Where the committed set needs more than the pools can staff, the plan says so and "
                 "by how much. That gap is the finding, not a reason to edit the portfolio."),
                ("A committed space with no size",
                 "Listed by id and flagged, and the totals are described as a floor — rather than "
                 "silently missing from a number the reader believes is complete.")], n)

    n = screen(prs, "plannerwf_narrative", "The business plan",
               "Written about the projection, under guard",
               [("Thesis, set, sequence, execution, risks",
                 "Written after every figure is fixed, so the prose cannot disagree with the table "
                 "beside it."),
                ("It may not state a new figure",
                 "A section that introduces a number the plan does not hold is stripped and "
                 "listed — the same discipline the topic description works under."),
                ("The prose knows its own question",
                 "A narrative for a committed set may not describe alternatives being weighed, "
                 "because none were. The prompt splits on the source."),
                ("Over-commitment is stated plainly",
                 "“This pool runs hot, peaking above the share available for new work, meaning "
                 "the plan is over-committed.” And what closes the gap.")], n)

    n = screen(prs, "planner_document", "The plan as a document",
               "In the order a committee reads it",
               [("Rendered in place, not downloaded",
                 "A plan that has to leave the tool to be read is a plan that gets read in a stale "
                 "copy."),
                ("Inputs first",
                 "Including the effective value of anything you did not state, and where it came "
                 "from. A plan without its inputs is not reproducible."),
                ("Every selected space, with its economics",
                 "Entry year, margin band, overlap discount, capability pool — and the near-misses "
                 "with the constraint that excluded each."),
                ("The assumptions, last",
                 "Every band, its owner and its version, exactly as the sales brief does it. The "
                 "margin and the discount rate are quoted from Orange's own filed accounts.")], n)

    # ---- Close -----------------------------------------------------------
    s = blank(prs)
    rect(s, 0, 0, W, H, fill=INK)
    rect(s, 0, 0, Inches(0.22), H, fill=ORANGE)
    text(s, Inches(1.1), Inches(2.2), Inches(11), Inches(0.9),
         "Everything you just saw is live", size=40, bold=True, color=WHITE)
    text(s, Inches(1.1), Inches(3.3), Inches(10.4), Inches(1.6),
         "No screen in this walkthrough is a mock-up. Every number came out of the database at the "
         "moment the frame was captured, every document was rendered by the application, and every "
         "claim on every screen traces back to a dated, attributable source.",
         size=17, color=PALE, spacing=1.35)
    text(s, Inches(1.1), Inches(5.35), Inches(11), Inches(0.4),
         "radar  ·  filter  ·  open full screen  ·  move it on the board  ·  plan the set",
         size=13, color=ORANGE, font=MONO)
    n += 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT)
    print(f"wrote {OUT}  ({n} slides)")
    return OUT


if __name__ == "__main__":
    sys.exit(0 if build() else 1)
