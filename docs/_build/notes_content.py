# -*- coding: utf-8 -*-
import sys; sys.path.insert(0, ".")
from notes_kit import *
from notes_kit import _shade, _nobord
from slides_data import SLIDES

import pathlib
OUT = str(pathlib.Path(__file__).resolve().parent.parent / "Orange_Innovation_Radar_Speaker_Notes.docx")
TOTAL = len(SLIDES)


def mmss(s):
    return f"{int(s)//60}:{int(s) % 60:02d}"


d = Notes("Orange Innovation Radar — Speaker Notes")

# ------------------------------------------------------------------ cover
d.spacer(52)
p = d.d.add_paragraph(); p.paragraph_format.space_after = Pt(2)
r = p.add_run("ORANGE BUSINESS  ·  INNOVATION RADAR")
r.font.size = Pt(11); r.font.bold = True; r.font.color.rgb = ORANGE; r.font.name = FONT
d.h("Speaker Notes", size=34, color=INK, after=2)
p = d.d.add_paragraph(); p.paragraph_format.space_after = Pt(20)
r = p.add_run("Opportunity Spaces / Innovation Radar  —  MVP walkthrough")
r.font.size = Pt(15); r.font.color.rgb = GREY; r.font.name = FONT

t = d.d.add_table(rows=1, cols=1); c = t.cell(0, 0)
_shade(c._tc.get_or_add_tcPr(), "FFF1E3"); _nobord(c)
c.paragraphs[0]._p.getparent().remove(c.paragraphs[0]._p)
for txt, sz, bold, col in [
        ("26 slides   ·   target running time 12 minutes 15 seconds", 12.5, True, ORANGE_D),
        ("One page per slide. Read the SAY block; the green bar at the foot of each page is your cue to advance.", 11, False, INK)]:
    pp = c.add_paragraph(); pp.paragraph_format.space_after = Pt(3)
    rr = pp.add_run(txt); rr.font.size = Pt(sz); rr.font.bold = bold; rr.font.color.rgb = col; rr.font.name = FONT
d.spacer(14)

d.kv([
    ("Deck", "docs/Orange_Innovation_Radar.pptx"),
    ("Reference recording", "docs/Orange_Innovation_Radar.mp4"),
    ("Companion walkthrough", "docs/Orange_Innovation_Radar_Walkthrough.pptx  ·  docs/Orange_Innovation_Radar_Demo.mp4"),
    ("Notes transcribed from", "the recorded walkthrough, corrected and extended for the six slides added since"),
    ("Version", "1.1  ·  24 August 2026"),
])
d.pagebreak()

# ------------------------------------------------------------------ how to use
d.h("How to use these notes", size=22)
d.p("Every slide gets its own page, in deck order. Each page carries four things:", after=9)
d.box("PAGE STRUCTURE", [
    "**The orange banner** — slide number, which part of the talk you are in, the running clock when the slide starts, and how long to spend on it.",
    "**ON SCREEN** — one line on what the audience is looking at, so you can find your place if you lose it.",
    "**SAY** — the script. It is what was actually said in the recording, corrected and tightened for reading aloud. Bold marks the words to land on; blue square brackets are stage directions, not words to read.",
    "**The green bar** — your cue to advance. It names the next slide, so you know what is coming before you press the key.",
], accent=ORANGE_D, fill="FFF1E3")
d.p("**Timings are a guide, not a script.** The clock column shows where you should be if you are keeping to the "
    "recorded pace. If you run long on the concept slides, the demo section (10–21) is where the time is easiest to "
    "make back — and the two Planner pages are the ones to cut first if the room is a sales audience rather than a "
    "strategy one.", after=12)

d.h("One thing to decide before you start", size=15, color=INK, before=4)
d.p("Slides 10 to 21 are the **live application**, not slides. The deck carries a screenshot of each of the twelve "
    "views so the pack reads on its own and so a presenter who cannot reach the running instance can still give the "
    "talk — but the material is written to be demonstrated.", after=6)
d.box("IF YOU DEMO LIVE", [
    "Have the app open on a second window before you start, on the radar view, with the role set to Strategist, and **already signed in** — the sign-in screen is not part of the story you are telling.",
    "The twelve pages of notes for slides 10–21 work as a demo script: follow them in order and you will have walked the same path as the recorded demo.",
    "Budget about **five minutes**. A live demo always runs longer than you expect — if you are behind the clock at slide 10, show the radar, the topic detail and the Planner only, then jump to slide 22.",
    "The two document-heavy views (the sales brief on slide 13's tab, and the Planner's document tab on slide 19) take a second to render. Open them a beat before you talk about them.",
], accent=BLUE, fill="EAF1F9")
d.box("IF YOU PRESENT FROM THE SCREENSHOTS", [
    "Just advance normally. Slides 11, 17 and 21 are short — do not pad them; the pace is deliberate.",
    "There is a second film for the demo half alone: **Orange_Innovation_Radar_Demo.mp4**, seven chapters against the running application. If the room wants to see the tool rather than the argument, show that instead of this deck.",
], accent=GREEN, fill="E4F1EA")
d.h("The three-part shape, if you need to cut", size=15, color=INK, before=8)
d.box("WHAT IS LOAD-BEARING AND WHAT IS NOT", [
    "**Part 1 — why and the concepts (slides 1–9, 0:00–4:51).** Load-bearing. Slide 4 (two scores) and slide 6 (portfolio distance) are the two you cannot drop; everything later refers back to them. Slide 9 can go if the room is not going to create spaces themselves.",
    "**Part 2 — the product (slides 10–21, 4:51–9:38).** Compressible, and this is where the time is. The radar view, the score-explanation panel and the Planner carry the argument; the rest is supporting.",
    "**Part 3 — architecture and status (slides 22–26, 9:38–12:12).** Slide 25 is the one the room will want to talk about — leave time for it.",
], accent=PURPLE, fill="EFE9F6")
d.pagebreak()

# ------------------------------------------------------------------ running order
d.h("Running order and timings", size=22)
d.p("The clock column is the elapsed time at which each slide **ends**, matching the recorded walkthrough.", after=10)
rows = []
for s in SLIDES:
    label = f"{s['n']}"
    demo = "  ●" if s.get("demo") else ""
    rows.append([label, s["section"] + demo, s["title"], f"{s['dur']}s", mmss(s["end"])])
d.table(["#", "Part", "Slide", "Spend", "Clock at end"], rows,
        widths=[1.0, 3.1, 8.4, 1.6, 3.1], size=9.5,
        highlight=lambda j: SLIDES[j].get("demo", False))
d.p("●  the seven slides delivered as a live application demo in the recording.", size=9, color=GREY, after=10)

d.pagebreak()

# ------------------------------------------------------------------ per slide
for i, s in enumerate(SLIDES):
    start = s["end"] - s["dur"]
    d.banner(s["n"], TOTAL, s["section"], s["title"], mmss(start), f"{s['dur']}s")
    d.onscreen(s["onscreen"])
    d.say(s["say"])
    if s.get("numbers"):
        d.box("THE FIGURES ON THE SLIDE, IF YOU ARE ASKED FOR THEM", s["numbers"], accent=GREEN, fill="E4F1EA", size=10)
    if s.get("ifasked"):
        d.box("IF ASKED", [f"**{q}**  {a}" for q, a in s["ifasked"]], accent=BLUE, fill="EAF1F9", size=10)
    if s.get("demo"):
        d.box("DEMO SECTION", ["In the recording this was live in the application. Presenting from the screenshot works too — "
                               "the script above reads the same either way."], accent=PURPLE, fill="EFE9F6", size=9.5)
    d.spacer(4)
    d.advance(("▶   " if not s.get("terminal") else "■   ") + s["advance"], terminal=s.get("terminal", False))
    if i < TOTAL - 1:
        d.pagebreak()

d.save(OUT)
