"""FDD figures 12–14 — the Planner, pre-sales collateral, and the scoping route in.

Three figures added with the planning, collateral and scoping work. They are
drawn to the same 0..100 canvas convention as every other figure so a reader
moving between them is not re-learning the geometry each time.
"""
import sys, textwrap; sys.path.insert(0, ".")
from dg import *

import pathlib
OUT = str(pathlib.Path(__file__).resolve().parents[1] / "diagrams") + "/"


# ===========================================================================
# Figure 12 — The Planner: two questions, one arithmetic
# ===========================================================================
c = Canvas(12.4, 6.9)
c.title("Figure 12 — The Planner: ranking answers which topic, a plan answers which SET",
        "Two sources ask two different questions. Everything downstream of the set is the same arithmetic, and none of it is a model.")

# -- the two sources -------------------------------------------------------
c.zone(1.0, 55.0, 45.0, 33.0, "SOURCE A — PARAMETERS  ·  the optimiser chooses",
       fc=BLUE_L, ec=BLUE, ls="-", lw=1.3, fs=8.0, tc=BLUE)
c.text(2.4, 78.5, "“What SHOULD we do, given a budget and a capacity?”",
       fs=8.2, color=INK, weight="bold")
c.text(2.4, 74.0, "Nothing is decided yet. The caller states constraints —\n"
                  "budget, entry slots, confidence floor, distance cap,\n"
                  "concentration caps, horizon mix — and a mixed-integer\n"
                  "program picks the set that maximises the objective.",
       fs=7.1, color=GREY_D, va="top")
c.chip(2.4, 57.0, 12.0, 4.0, "418 candidates", fc="#FFFFFF", ec=BLUE, tc=BLUE)
c.chip(15.2, 57.0, 14.0, 4.0, "constraints bind", fc="#FFFFFF", ec=BLUE, tc=BLUE)
c.chip(30.4, 57.0, 14.0, 4.0, "objective maximised", fc="#FFFFFF", ec=BLUE, tc=BLUE)

c.zone(53.0, 55.0, 45.0, 33.0, "SOURCE B — WORKFLOW  ·  the business already chose",
       fc=GREEN_L, ec=GREEN, ls="-", lw=1.3, fs=8.0, tc=GREEN)
c.text(54.4, 78.5, "“What does what we have committed to actually earn, and when?”",
       fs=8.2, color=INK, weight="bold")
c.text(54.4, 74.0, "Every space the stage gate moved to Demand-tested or\n"
                   "beyond is IN. No evidence floor, no distance cap, no\n"
                   "concentration limit and no objective — because there is\n"
                   "nothing left to optimise. What remains is scheduling.",
       fs=7.1, color=GREY_D, va="top")
c.chip(54.4, 57.0, 15.0, 4.0, "selected = considered", fc="#FFFFFF", ec=GREEN, tc=GREEN)
c.chip(70.2, 57.0, 12.0, 4.0, "horizon spreads", fc="#FFFFFF", ec=GREEN, tc=GREEN)
c.chip(83.0, 57.0, 13.4, 4.0, "overload reported", fc="#FFFFFF", ec=GREEN, tc=GREEN)

# -- the shared spine ------------------------------------------------------
spine = [
    (2.0,  "SET + ENTRY YEAR", "which spaces, starting when", ORANGE, ORANGE_L),
    (21.0, "PROJECTION", "revenue · profit · NPV, per year", GREEN, GREEN_L),
    (40.0, "FLAGS", "plausibility · concentration · confidence", RED, RED_L),
    (59.0, "EXCLUSIONS", "what is out, and what put it out", GOLD, GOLD_L),
    (78.0, "NARRATIVE + PDF", "prose about the numbers", PURPLE, PURPLE_L),
]
for x, title, sub, ec, fc in spine:
    c.box(x, 30.0, 18.0, 10.0, title, sub, fc=fc, ec=ec, tc=INK, fs=8.4, subfs=6.9)
for x in (20.0, 39.0, 58.0, 77.0):
    c.arrow((x, 35.0), (x + 1.0, 35.0), color=GREY_D, lw=1.4)

c.path([(23.5, 55.0), (23.5, 47.0), (11.0, 47.0), (11.0, 40.0)], color=BLUE, lw=1.5)
c.path([(75.5, 55.0), (75.5, 47.0), (11.0, 47.0), (11.0, 40.0)], color=GREEN, lw=1.5)
c.text(11.0, 48.4, "either source produces the same object", fs=7.0, color=GREY_D, ha="center")

# -- the three registers ---------------------------------------------------
c.rule(26.0)
c.text(1.0, 22.4, "THREE REGISTERS, KEPT APART — as everywhere else in this system",
       fs=8.0, color=INK, weight="bold")
regs = [
    ("INPUTS", "What the caller asked for. Same inputs plus the same config versions give the "
               "same plan — the id is a fingerprint of them, so a plan is immutable once computed.", BLUE),
    ("PROJECTION", "Arithmetic over stored market sizes and configured bands. No model call. "
                   "Margin varies by portfolio distance; SOM is discounted for overlap, because obtainable "
                   "share is not additive.", GREEN),
    ("NARRATIVE", "A model writing prose ABOUT the projection, under the numeric guard. It may not "
                  "introduce a figure that is not already in the plan.", PURPLE),
]
x = 1.0
for name, body, col in regs:
    c.box(x, 6.0, 31.6, 13.0, "", None, fc="#FFFFFF", ec=col, lw=1.2)
    c.text(x + 1.4, 16.6, name, fs=8.0, color=col, weight="bold")
    c.text(x + 1.4, 14.0, "\n".join(textwrap.wrap(body, 60)), fs=6.8, color=GREY_D, va="top")
    x += 32.6

c.text(1.0, 2.4, "WHY AN OPTIMISER AND NOT A LEARNED MODEL:  selection under constraints is a multi-dimensional knapsack — it solves exactly in under a second at this size and "
                 "explains which constraint bound. There are also no labels: 418 spaces and zero historical outcomes is a spreadsheet, not a training set.",
       fs=6.9, color=GREY_D)
c.save(OUT + "fdd-12-planner.png")


# ===========================================================================
# Figure 13 — Pre-sales collateral: twelve pieces, one snapshot
# ===========================================================================
c = Canvas(12.4, 6.9)
c.title("Figure 13 — Pre-sales collateral: twelve pieces from one snapshot, in the format the reader works in",
        "The brief is one document for one conversation. This is what the team needs between that conversation and a proposal.")

# The title and subtitle are placed by hand rather than through `cylinder`'s
# own slots: the helper centres a subtitle on 0.34 of the height, which puts a
# third line through the bottom ellipse.
c.cylinder(1.0, 61.0, 17.0, 21.0, "", None, fc=GREEN_L, ec=GREEN)
c.text(9.5, 74.6, "ONE SNAPSHOT", fs=9.0, color=INK, weight="bold", ha="center")
c.text(9.5, 70.2, "context.load reads the space\nonce — sizing, competition,\ndescription, links, evidence",
       fs=6.6, color=GREY_D, ha="center")
c.text(1.0, 57.0, "Two documents in the same pack quoting different\n"
                  "SAM figures is the failure this makes impossible\n"
                  "rather than merely unlikely.", fs=6.9, color=GREY_D, va="top")

pieces = [
    ("Discovery & qualification", "PDF"), ("Outreach sequence", "MD"),
    ("First-meeting deck", "PPTX"), ("Value hypothesis", "PPTX"),
    ("Reference & proof pack", "PDF"), ("Competitor battlecards", "PDF"),
    ("Solution outline (HLD)", "PPTX"), ("PoC / demo scoping", "PDF"),
    ("Partner brief", "PDF"), ("Commercial model options", "PPTX"),
    ("Tender response blocks", "DOCX"), ("Bid risk register", "PDF"),
]
COLW, ROWH = 19.4, 8.2
x0, y0 = 22.0, 82.0
for i, (name, fmt) in enumerate(pieces):
    col, row = i % 4, i // 4
    x = x0 + col * COLW
    y = y0 - row * ROWH - 6.4
    c.box(x, y, COLW - 1.4, 6.4, "", None, fc=GREY_LL, ec=GREY_L, lw=0.9, radius=0.5)
    c.text(x + 1.2, y + 4.4, "\n".join(textwrap.wrap(name, 24)), fs=6.7, color=INK,
           va="top", weight="bold")
    c.chip(x + COLW - 7.4, y + 0.9, 5.6, 2.6, fmt, fc=ORANGE_L, ec="none", tc=ORANGE_D, fs=6.0)
c.text(22.0, 84.6, "TWELVE PIECES  ·  the default format is the one the artefact wants to be",
       fs=7.6, color=INK, weight="bold")

c.rule(52.0)

# -- the emitter fan -------------------------------------------------------
c.text(1.0, 48.4, "A DOCUMENT IS DESCRIBED ONCE AND EMITTED MANY TIMES",
       fs=8.0, color=INK, weight="bold")
c.text(1.0, 45.0, "Seven documents × three formats plus four decks × three is thirty-three places for the same battlecard to say something slightly\n"
                  "different, and within a month two of them disagree. So documents.py and decks.py describe BLOCKS; emitters.py puts a block on a page.",
       fs=7.0, color=GREY_D, va="top")

c.box(1.0, 23.0, 20.0, 12.0, "documents.py / decks.py",
      "blocks: heading, prose, table,\nchart spec, citation, banner", fc=BLUE_L, ec=BLUE, fs=8.0, subfs=6.7)
c.box(26.0, 23.0, 16.0, 12.0, "emitters.py", "one emitter per format,\nwalking the same blocks",
      fc=ORANGE_L, ec=ORANGE_D, fs=8.0, subfs=6.7)
c.arrow((21.0, 29.0), (25.6, 29.0), color=GREY_D, lw=1.4)

fmts = [
    ("PDF", "reportlab · vector charts, exact geometry.\nThe format to send.", GREEN, GREEN_L),
    ("PPTX", "python-pptx · charts are NATIVE SHAPES, so an\narchitect moves a box. The format to edit.", ORANGE_D, ORANGE_L),
    ("DOCX", "python-docx · native styles and tables;\ncharts rasterised at high DPI.", BLUE, BLUE_L),
    ("ODT / ODP", "odfpy · the same, for a LibreOffice estate.", PURPLE, PURPLE_L),
    ("MD", "plain text · nobody has ever wanted\na PDF of six emails.", GREY_D, GREY_L),
]
# A bus above the boxes rather than five arrows into their left edges: an
# arrow drawn into a box crosses its own label and strikes it out.
c.path([(34.0, 35.0), (34.0, 38.4), (91.9, 38.4)], color=GREY_D, lw=1.2, head=False)
x = 47.0
for name, body, ec, fc in fmts:
    c.box(x, 23.0, 9.8, 10.0, name, None, fc=fc, ec=ec, fs=8.0)
    c.arrow((x + 4.9, 38.4), (x + 4.9, 33.3), color=GREY_D, lw=1.0)
    c.text(x + 0.2, 21.6, "\n".join(textwrap.wrap(body.replace("\n", " "), 24)),
           fs=6.0, color=GREY_D, va="top")
    x += 10.4

c.rule(12.0)
c.text(1.0, 9.0, "THE FORMAT IS THE READER'S CHOICE, PER PIECE.", fs=7.6, color=INK, weight="bold")
c.text(1.0, 6.2, "A battlecard is a PDF because it is read on a phone in a car park and must not have been edited since it was approved. Tender blocks are Word because paste-fodder\n"
                 "as a PDF actively obstructs. Formats coexist — asking for Word after the PDF gives both. A deck is never offered as Word: one idea per page is the only property\n"
                 "that made it a deck. A piece whose declared inputs are missing STILL builds, with a banner naming the gap, because an error leaves the engineer with nothing.",
       fs=6.9, color=GREY_D, va="top")
c.save(OUT + "fdd-13-presales.png")


# ===========================================================================
# Figure 14 — Two routes into a new opportunity space
# ===========================================================================
c = Canvas(12.4, 7.2)
c.title("Figure 14 — Two routes into a new opportunity space, and the gate they share",
        "Parameters for somebody who knows the taxonomy; a scoping conversation for somebody who knows their market. Both are refused by the same corpus.")

c.actor(6.5, 84.0, "Strategist", "knows the taxonomy", color=BLUE)
c.actor(6.5, 63.0, "Account team", "knows the market,\nnot the vocabulary", color=PURPLE)

c.box(15.0, 80.0, 25.0, 12.0, "PARAMETERS ROUTE",
      "Pick a vertical, a use case, a technology, a\nhorizon. /generate/matching shows what\nALREADY satisfies them, before a run is spent.",
      fc=BLUE_L, ec=BLUE, fs=8.4, subfs=6.6)
c.box(15.0, 56.0, 25.0, 15.0, "SCOPING CONVERSATION",
      "The assistant interviews, with the corpus in front\nof it. Every turn re-embeds the WHOLE transcript\nagainst the same signal vectors the run will read,\nand shows what came back — publisher, date and\ncosine — beside the answer.",
      fc=PURPLE_L, ec=PURPLE, fs=8.4, subfs=6.6)

c.arrow((10.0, 84.0), (15.0, 86.0), color=BLUE, lw=1.4)
c.arrow((10.0, 63.0), (15.0, 63.5), color=PURPLE, lw=1.4)

# The gate is a ZONE, not a box: a box centres its title over its own body.
c.zone(46.0, 56.0, 26.0, 36.0, "THE GATE", fc="#FFFFFF", ec=RED, ls="-", lw=1.6, fs=9.4, tc=RED,
       align="center")
c.text(47.4, 85.0, "1 · RETRIEVAL FLOOR", fs=7.4, color=RED, weight="bold")
c.text(47.4, 82.4, "The brief must retrieve at least the run's own\nfloor of signals, using the run's own retrieval.",
       fs=6.6, color=GREY_D, va="top")
c.rule(76.5, x0=47.4, x1=70.6)
c.text(47.4, 74.0, "2 · CORROBORATION", fs=7.4, color=RED, weight="bold")
c.text(47.4, 71.4, "Similarity is not support. A second, independent\nreason is required, on the use case or the\ntechnology — never the vertical, which\ncorroborates every brief ever written about a\nwell-covered sector.", fs=6.6, color=GREY_D, va="top")

c.arrow((40.0, 86.0), (46.0, 82.0), color=GREY_D, lw=1.3)
c.arrow((40.0, 63.5), (46.0, 68.0), color=GREY_D, lw=1.3)

c.box(78.0, 79.0, 20.0, 12.0, "", None, fc=GREEN_L, ec=GREEN)
c.text(88.0, 88.6, "RUNNABLE", fs=9.0, color=INK, weight="bold", ha="center")
c.text(78.7, 85.8, "\n".join(textwrap.wrap(
    "The Generate button is enabled by the corpus, not by the model's opinion of itself.", 33)),
    fs=6.6, color=GREY_D, va="top")
# Title placed by hand: `box` centres its title vertically, which puts it
# through the middle of any body text set underneath.
c.box(78.0, 56.0, 20.0, 16.0, "", None, fc=RED_L, ec=RED)
c.text(88.0, 69.6, "NOT RUNNABLE", fs=9.0, color=INK, weight="bold", ha="center")
c.text(78.7, 66.6, "\n".join(textwrap.wrap(
    "Refused with the reason, BEFORE the model calls are spent rather than after — "
    "and the contributed-evidence route opens instead, which is the path that can "
    "actually build it.", 33)), fs=6.6, color=GREY_D, va="top")
c.arrow((72.0, 82.0), (78.0, 85.0), color=GREEN, lw=1.4)
c.arrow((72.0, 66.0), (78.0, 61.0), color=RED, lw=1.4)

c.rule(52.0)
c.text(1.0, 48.6, "WHY THE MODEL DOES NOT DECIDE WHEN IT IS DONE", fs=8.0, color=INK, weight="bold")
c.text(1.0, 45.4, "Asked “do you have enough?” a model says yes. So `ready` is the corpus's verdict and travels beside `model_ready`, which is the model's — and the screen explains\n"
                  "either disagreement rather than silently obeying one of them. The assistant is told to put a brief forward even while hedging about the evidence, because otherwise a\n"
                  "genuinely new idea has nothing to press Generate on; its hedge is a fair remark about the corpus and a poor reason to disable a button whose brief already passed the gate.",
       fs=7.0, color=GREY_D, va="top")

c.rule(35.0)
c.text(1.0, 31.6, "THE FAILURE THIS WAS BUILT FROM — worth reading before changing the gate", fs=8.0, color=INK, weight="bold")
box_w = 31.6
cases = [
    ("The taxonomy is an approximation",
     "A brief for advertising-funded municipal screens files under citizen_service_automation × "
     "private_5g, because in closed lists of 15 verticals, 59 use cases and 32 technologies "
     "nothing closer exists.", GOLD, GOLD_L),
    ("A label match then validates it",
     "Tenders for private-5G video surveillance corroborate the LABEL private_5g perfectly and are "
     "no evidence whatsoever for advertising screens. Four supporting signals; button enabled; four "
     "model calls spent; every candidate thrown out by the critic.", RED, RED_L),
    ("So the sentence is judged, not the label",
     "The cheap model is asked about the brief's own sentence, with the labels shown as the "
     "approximation they are, and its answer overrules a label match. The vocabulary test stays — "
     "for display, where the two agree.", GREEN, GREEN_L),
]
x = 1.0
for name, body, ec, fc in cases:
    c.box(x, 7.0, box_w, 19.0, "", None, fc="#FFFFFF", ec=ec, lw=1.2)
    c.ax.add_patch(Rectangle((x, 24.4), box_w, 1.6, fc=ec, ec="none", zorder=4))
    c.text(x + 1.4, 21.6, name, fs=7.4, color=ec, weight="bold")
    c.text(x + 1.4, 18.4, "\n".join(textwrap.wrap(body, 50)), fs=6.6, color=GREY_D, va="top")
    x += box_w + 2.5
c.save(OUT + "fdd-14-generation-routes.png")

print("  fdd-12-planner, fdd-13-presales, fdd-14-generation-routes")
