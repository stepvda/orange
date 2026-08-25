#!/usr/bin/env python3
"""Build the narrated product demo (docs/Orange_Innovation_Radar_Demo.mp4).

The third film in the set, and the one to show somebody who has to USE the
thing. Orange_Innovation_Radar.mp4 argues why the product is built the way it
is; this one opens every screen in the order a person would, in seven chapters
that match Orange_Innovation_Radar_Walkthrough.pptx one for one — the chapter
cards ARE that deck's slides, rendered, so the film and the deck cannot drift.

  1  The radar, and one opportunity space
  2  Role modes
  3  One space, full screen — all four tabs
  4  The workflow board, and what it feeds
  5  Analytics
  6  Creating a space: parameters, and the scoping conversation
  7  The Planner: both sources, and the plan document

THREE THINGS ABOUT THE RECORDING, EACH OF WHICH WAS LEARNED THE HARD WAY.

*   **The browser is headed.** Headless Chromium does not render an embedded
    PDF, and three of the seven chapters are largely a PDF on the page — the
    sales brief, a built pre-sales piece, the plan document. Headless produces a
    grey rectangle where the demo's whole point should be.

*   **It scrolls.** Every long pane is scrolled through rather than shown from
    the top: the detail pane, the score breakdown, the twelve pre-sales pieces,
    the analytics charts, the plan. A frame of the first 900 pixels of a screen
    is not a demonstration of that screen.

*   **One browser context per chapter.** Playwright finalises a recording when
    its context closes, so a context per chapter is what makes it possible to
    cut a chapter card in between. The signed-in session is carried across them
    as saved storage state rather than by signing in seven times.

Synchronisation is the same as the other two builds: every narration clip is
generated FIRST so its exact length is known, then each step holds until a
CUMULATIVE target. A step that overruns is absorbed by the next rather than
pushing the voice out of step for the rest of the film.

Prerequisites: the API on :8000, the frontend on :5173, and
docs/build_walkthrough_deck.py already run.

    python3 docs/build_demo.py
    python3 docs/build_demo.py --chapters 3,7     # re-record two chapters only
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parents[1]
WORK = Path("/tmp/demo")
SLIDES = WORK / "slides"
AUDIO = WORK / "audio"
SEG = WORK / "seg"
CLIPS = WORK / "clips"
STATE = WORK / "session.json"
OUT = ROOT / "docs" / "Orange_Innovation_Radar_Demo.mp4"
DECK = ROOT / "docs" / "Orange_Innovation_Radar_Walkthrough.pptx"

VOICE = "en-US-BrianNeural"
RATE = "-3%"
W, H = 1920, 1080

BASE = "http://localhost:5173"
USER, PASSWORD = "orange", "orange"

#: The space the tour opens. The one with the whole chain built, so no pane in
#: any chapter is an empty state.
TOPIC = "OS004"

# ---------------------------------------------------------------------------
# Narration
# ---------------------------------------------------------------------------

#: (slide number in the rendered walkthrough deck, narration). These play as
#: stills; everything else is the live application.
OPENING = [
    (1, "This is a walkthrough of the Orange Business Innovation Radar. Not the thinking "
        "behind it, which is a different film, but the tool itself: every screen, in the order "
        "somebody would actually use them, against the live corpus. Nothing here is a mock-up."),
    (2, "Seven chapters. We start at the radar and open one opportunity space. Then the three "
        "role modes, and the full-screen view of a space with its four tabs. Then the workflow "
        "board and the analytics. Then how a new space gets created, by two different routes. "
        "And finally the Planner, which turns the ranking into a portfolio."),
]

CLOSING = [
    (30, "Everything in this film is live. Every number came out of the database at the moment "
         "the frame was captured, every document was rendered by the application itself, and "
         "every claim on every screen traces back to a dated, attributable source. Start at the "
         "radar, filter to your vertical, open a space full screen, move it on the board, and "
         "plan the set."),
]

#: Each chapter is (deck slide number for its card, card narration, [steps]).
#: A step is (narration, step-name) — the name only appears in the build log.
CHAPTERS: list[tuple[int, str, list[tuple[str, str]]]] = [

    # ------------------------------------------------------------ chapter 1
    (3, "Chapter one. The radar itself, and one opportunity space opened up.", [
        ("Here is the application. Along the top: three role modes on the left, the views in the "
         "middle, and on the right the date of the last refresh and the weight set — the "
         "configuration version that produced every number on this screen. Below that, three "
         "panes: filters, the radar, and the detail of whatever you select.", "orient"),

        ("The radar uses four channels at once. Angular sector is the business domain — six "
         "sectors around the circle. Distance from the centre is the time horizon: Now in the "
         "middle, Later at the rim. Marker size is attractiveness. Marker colour is right to win, "
         "from light to dark. So the two questions the radar exists to answer are both visible "
         "without a single click.", "read_radar"),

        ("Hovering a marker gives you the summary. The statement first — specific enough to open "
         "a customer meeting with, which is the bar. Then both scores, side by side and never "
         "combined. Then the horizon, the portfolio distance, how many signals support it, the "
         "serviceable market, and the competitive band. An exclamation mark inside a marker means "
         "an evidence gap: Orange has few or no published references in that vertical.",
         "hover_marker"),

        ("The left rail is where you narrow it down. Every dimension is multi-select, and the "
         "counts beside each are computed over the whole eligible set rather than over what "
         "happens to be on screen. That distinction mattered: an early version counted only the "
         "visible page, so a filter could read zero while thirty-seven topics matched.",
         "filter_vertical"),

        ("Filters compose. Manufacturing, plus a medium competitive field, plus only spaces that "
         "already have a sales brief. The result count updates, and so does the radar. And the "
         "whole view is in the address bar — role, tab, filters, sort and selection — so a "
         "prepared view is a link you can send to a colleague.", "filter_more"),

        ("Selecting a space fills the detail pane on the right. This is one page in the order the "
         "questions actually arrive.", "select_topic"),

        ("What is it, and why is it hot now. Every claim here carries the identifiers of the "
         "signals it was written from, and you can follow each one back to a dated, attributable "
         "source. A claim that cited nothing was removed rather than rewritten — asking a model to "
         "repair a claim just teaches it to attach a citation at random.", "scroll_why"),

        ("Further down: where the value lands and for whom, then can-we-play and can-we-win "
         "itemised against named Orange offers, references, partners and certifications. Those are "
         "query results against a curated graph. A language model never asserts one.",
         "scroll_value"),

        ("And the market size, computed bottom-up rather than quoted: enterprise counts by sector "
         "and size class, times an observed adoption rate, times a plausible contract value. Every "
         "factor carries its source, its year and a confidence badge, so the estimate can be "
         "rejected on its arithmetic rather than believed on its authority.", "scroll_size"),

        ("Every number opens up. How was this calculated shows the weight table, the weighted "
         "total, and for each component the actual evidence — publisher entropy and the publishers "
         "counted, the tier distribution, the periods the momentum slope was fitted to.",
         "open_explain"),

        ("At the foot of it are the reproducibility stamps: weight set, pipeline version, prompt "
         "version and model version. A number you cannot re-derive is not explained, only "
         "displayed.", "scroll_explain"),
    ]),

    # ------------------------------------------------------------ chapter 2
    (9, "Chapter two. Role modes — the same data, three genuinely different rankings.", [
        ("Look at the line above the radar. Strategist slash Innovator. Decide where to invest "
         "study and prototyping effort next quarter. Only spaces Orange could deliver at L1 to L4 "
         "appear here, ordered for this role. The screen tells you which question it is answering "
         "before you read a single topic.", "instruction_line"),

        ("Switch to Sales and the instruction changes with it: open or re-open a conversation with "
         "a named account. And so does the set. Sales ranks on right to win and proof-point "
         "density, and only shows topics with a delivery path, a published reference in the same "
         "vertical, and no evidence gap. The count at the top drops, and that drop is the point.",
         "role_sales"),

        ("Presales is different again: differentiation first — where Orange has assets and the "
         "market has few credible providers. Sees L0 to L2. These are not three filters over one "
         "score. They are three ranking functions, and each one is configuration rather than "
         "code.", "role_presales"),

        ("The help explains why. A high-attractiveness L4 topic is exactly the strategist's "
         "innovation agenda — and exactly what a salesperson should never be shown, because there "
         "is nothing to sell. The role modes are not interface presets; they fall out of portfolio "
         "distance, which is the shortest path from a topic to something Orange could actually "
         "deliver.", "role_help"),
    ]),

    # ------------------------------------------------------------ chapter 3
    (12, "Chapter three. One space, full screen, and the four tabs it carries.", [
        ("The three-pane layout is right for working through the radar — filter, scan, open, "
         "compare, move on. It is wrong for the moment somebody actually reads a space, because "
         "there are ten sections and a four-hundred-pixel column. So the same content opens with "
         "the panes out of the way, in four tabs, in the order the questions arrive: what is this, "
         "who else is here, what do I send, and what happens after the meeting.", "enter_full"),

        ("Tab one is the space itself. Everything the radar computed about it, with room to read "
         "it: the statement and the triple it resolves to, both scores, the evidence timeline, the "
         "links onto Orange assets, the stage it sits at on the collaboration board.",
         "fs_scroll_space"),

        ("Tab two is the competitive field, and it is per competitor rather than a band. What each "
         "one says it sells here, taken from pages they published, with each claim carrying the "
         "page it came from. Then the differentiation angle against each of them — and a paragraph "
         "that named an Orange asset the graph does not hold is stripped, while the half "
         "describing the competitor survives.", "fs_competitors"),

        ("A competitor whose site refused our crawler is marked as refused rather than quietly "
         "omitted, because a gap in the register must not read as no competitor found.",
         "fs_competitors_scroll"),

        ("Tab three is the sales brief: the PDF somebody takes into a meeting, rendered here on "
         "the page rather than hidden behind a download. Six pages, and every figure on it stamped "
         "with the versions that produced it.", "fs_brief"),

        ("And notice the banner. This brief is out of date — the space has been refreshed since it "
         "was built — and it is also incomplete, because it was built before the competitor "
         "analysis section existed. Those are different problems: a stale brief was correct when "
         "it was made and has been overtaken, while an incomplete one never had the section, so "
         "waiting does not fix it. Showing the brief beside the space rather than only offering a "
         "download is what makes anyone notice either.", "fs_brief_scroll"),

        ("Tab four is the pre-sales pack. The brief is one document for one conversation; this is "
         "the twelve pieces a team needs between that conversation and a proposal. All twelve are "
         "listed whether or not anything has been built, because what could be produced is as much "
         "of the answer as what has been — and a screen that starts empty is one nobody presses a "
         "button on.", "fs_presales"),

        ("They are grouped by when they are used. Before the meeting: a discovery and "
         "qualification pack, an outreach sequence. In the meeting: a first-meeting deck, a value "
         "hypothesis with the market sized as a funnel and the value built up as a waterfall.",
         "fs_presales_scroll1"),

        ("Then the competitive and technical work: battlecards, a reference pack, a solution "
         "outline with the components coloured by who owns each one. And finally the bid: a PoC "
         "scoping sheet, a partner brief, commercial model options, tender response blocks and a "
         "risk register.", "fs_presales_scroll2"),

        ("The format is the reader's choice, per piece. Documents come as PDF, Word or "
         "OpenDocument; decks as PowerPoint, OpenDocument or PDF. The default is the format the "
         "artefact wants to be — a battlecard is a PDF because it is read on a phone and must not "
         "have been edited since it was approved; tender blocks are Word because a PDF of "
         "paste-fodder obstructs. And the formats coexist: asking for Word after you have the PDF "
         "gives you both.", "fs_presales_formats"),

        ("All twelve are built from one snapshot of the space, read once. Two documents in the "
         "same pack quoting different market sizes — because one was made before a sizing run and "
         "one after — is the failure that makes impossible rather than merely unlikely.",
         "fs_presales_open"),
    ]),

    # ------------------------------------------------------------ chapter 4
    (17, "Chapter four. The workflow board — and the thing it feeds.", [
        ("The stage gate. A space moves Shortlisted, Demand-tested, Packaged, Live, and ownership "
         "follows the stage: strategist, then sales, then presales. Every transition records who "
         "moved it and why.", "workflow_open"),

        ("The known weakness of a stage gate is latency — a topic dies waiting for its owner to "
         "look at it. So age-in-stage is computed and a stalled card is flagged rather than left "
         "for somebody to notice. Cards are also marked where the team's conviction and the "
         "evidence-derived score disagree, which is a signal to look before advancing.",
         "workflow_scroll"),

        ("Each role rates only the axis it owns, nought to five, with written anchors rather than "
         "a bare number. Those ratings aggregate into conviction, which changes what surfaces "
         "first for each role and never touches either published score.", "workflow_assess"),

        ("And here is the part worth remembering for chapter seven. This board is an input to the "
         "Planner. Everything the team has moved to Demand-tested or beyond can be planned "
         "directly, as a portfolio the business has already committed to — so nobody re-enters a "
         "decision that has already been taken.", "workflow_planner_link"),
    ]),

    # ------------------------------------------------------------ chapter 5
    (19, "Chapter five. Analytics.", [
        ("Analytics answers the questions that are about the portfolio rather than about a topic. "
         "Where is it thin, where do the team and the evidence disagree, and how much of the grid "
         "has any evidence at all.", "analytics_open"),

        ("Each chart is chosen by the job the data does rather than by taste. The vertical by "
         "domain heatmap is magnitude on a grid, so it is sequential — and blue, because orange "
         "already means right to win on this screen and reusing it would imply the same quantity.",
         "analytics_heatmap"),

        ("Conviction against evidence is polarity, so it is diverging with a neutral midpoint: "
         "agreement reads as nothing and only disagreement draws the eye. The stage funnel is an "
         "ordered sequence, so it is ordinal. Only the signal-type mix is genuinely categorical, "
         "and that one ships a legend and a table.", "analytics_scroll"),

        ("And the market-size distribution, which is the sanity check on the sizing engine: how "
         "many spaces rest on observed contract values, how many on partial evidence, and how many "
         "are modelled — the least reliable of the three, and labelled as such everywhere it "
         "appears.", "analytics_sizes"),
    ]),

    # ------------------------------------------------------------ chapter 6
    (21, "Chapter six. Creating an opportunity space, by two different routes.", [
        ("Everything so far arrived from a scheduled refresh. The Generate screen is for the case "
         "a refresh cannot serve: somebody has a specific question now, about a cell of the grid "
         "the corpus has not been asked about yet. There are two routes in, and they differ only "
         "in what you already have to know.", "generate_open"),

        ("The first route is parameters, for somebody who knows the taxonomy. Pick a vertical, a "
         "use case, a technology and a horizon, and the screen counts how much evidence sits "
         "behind that combination before anything is spent.", "generate_grid"),

        ("And before it runs, it shows you the spaces that already satisfy those criteria. The "
         "most common outcome of an on-demand run is rediscovering something the last refresh "
         "produced, and finding that out afterwards costs four model calls and several minutes.",
         "generate_matching"),

        ("The second route replaced a text box. The box asked for one thing and gave one piece of "
         "feedback — a character count, which is the only failure that did not matter. An "
         "opportunity space is a vertical times a use case times a technology, plus a buyer's "
         "problem and a place, and somebody who knows their market but not this vocabulary "
         "under-specified two of those every time.", "generate_chat"),

        ("So the assistant interviews instead, with the corpus in front of it. Every turn "
         "re-embeds the whole conversation against the same signal vectors the run itself will "
         "read, at the same floor, and shows what came back beside the answer — publisher, date "
         "and cosine similarity, per signal. An answer that sharpens the idea sharpens the "
         "evidence the next question is asked from.", "chat_evidence"),

        ("And the corpus enables the button, not the model. Asked whether it has enough, a model "
         "says yes. So a proposed brief has to clear the run's own retrieval floor, and it has to "
         "be corroborated on its use case or its technology — never on its vertical, which "
         "corroborates every brief ever written about a well-covered sector. Where it cannot be "
         "run, the refusal comes with the reason before the model calls are spent, rather than "
         "after.", "chat_ready"),
    ]),

    # ------------------------------------------------------------ chapter 7
    (24, "Chapter seven. The Planner.", [
        ("The radar answers which opportunity, one space at a time. The Planner answers a "
         "different question: which set of them, in what order, and what does that set earn. It "
         "opens full screen because it is a statement about the whole portfolio rather than a way "
         "of looking at the current filter.", "planner_open"),

        ("There are two sources for the portfolio, and they ask genuinely different questions. "
         "Under Parameters, nothing has been decided: you state the constraints and an optimiser "
         "chooses the set. Entry slots per year, the share of capability headcount free for new "
         "work, an evidence floor, a distance cap, a concentration cap.", "planner_form"),

        ("A ranked list cannot answer this, because it assumes you can take the top N and you "
         "cannot — not four hundred spaces at once, and not twelve in the same vertical. So "
         "selection is a mixed-integer program. And the objective is a decision the screen makes "
         "you take rather than defaulting silently: profit, revenue, net present value or "
         "strategic coverage give materially different portfolios.", "planner_form_scroll"),

        ("Selection and projection are arithmetic, so this is immediate — no model call. Fifty-one "
         "spaces selected from two hundred and thirty-one admissible candidates. One point four "
         "six billion euros of five-year revenue, one hundred and eighty-seven million of profit, "
         "and a net present value discounted at Orange's own filed rate.", "planner_run"),

        ("The band on the cumulative chart is the sizing engine's own low and high estimates "
         "carried through, not error bars invented for the picture. The entry schedule is "
         "staggered by horizon and by what capacity allowed — a cohort bigger than a year's slots "
         "cascades forward rather than pretending the capacity exists.", "planner_overview"),

        ("Capability pool utilisation is the constraint that binds first in most plans. And on the "
         "right, from candidates to committed: what each constraint removed, at each step. That is "
         "the thing a ranked list cannot tell you, because the answer is a constraint rather than "
         "a score.", "planner_overview_scroll"),

        ("The spaces tab lists every selection with its entry year and its economics — the margin "
         "band its portfolio distance earned it, the overlap discount applied because obtainable "
         "share is not additive, and the capability pool it draws on. Below them, the near-misses, "
         "each with the constraint that excluded it.", "planner_spaces"),

        ("The business plan is one model call over the finished projection. It may not introduce a "
         "figure: a section that states a number the plan does not hold is stripped and listed, "
         "because a sentence that disagrees with the table beside it is a defect the reader has to "
         "adjudicate.", "planner_narrative"),

        ("The assumptions are last, exactly as the sales brief does it. Every band, its owner and "
         "its version — and the two that are not assumptions at all: the margin applied to revenue "
         "and the rate used to discount it are quoted from Orange's own filed accounts.",
         "planner_assumptions"),

        ("And the whole thing exports as one document, rendered here rather than downloaded, "
         "because a plan that has to leave the tool to be read is a plan that gets read in a stale "
         "copy. Inputs first — including the effective value of anything you did not state, and "
         "where it came from — then the projection, every selected space, the business plan, and "
         "the assumptions.", "planner_document"),

        ("Now the second source. Workflow selected takes the portfolio as already decided: every "
         "space the collaboration board moved to Demand-tested or beyond is in this plan, and none "
         "of those constraints is applied to it. Each of them would overrule a decision a "
         "strategist, a salesperson or a presales engineer has already taken — dropping a space "
         "for resting on a modelled size answers a human judgement with an assumption band.",
         "planner_workflow"),

        ("So there is no objective and nothing is excluded for being outranked. What the Planner "
         "does here is the part nobody did by hand: each space enters when its horizon says the "
         "market arrives, a space already Live starts in year one whatever its horizon says, and "
         "the revenue, margin, ramp, overlap discount and capability load follow from that.",
         "planner_workflow_run"),

        ("And nothing is dropped to make the numbers work. Where the committed set needs more than "
         "the capability pools can staff, the plan says so and by how much — that gap is the "
         "finding, not a reason to edit the portfolio — and it names what closes it: hiring, "
         "partnering, raising the share available for new work, or moving a space back down the "
         "gate.", "planner_workflow_overview"),

        ("The prose knows which question it answered, too. A narrative written for a committed set "
         "may not describe alternatives being weighed, because none were. This pool runs hot, it "
         "says, peaking above the share available for new work, meaning the plan is "
         "over-committed. That is the plan telling you something true rather than something "
         "comfortable.", "planner_workflow_narrative"),
    ]),
]


# ---------------------------------------------------------------------------
# Rendering the deck
# ---------------------------------------------------------------------------

def render_slides() -> None:
    """Rasterise the walkthrough deck, so the chapter cards are the deck's own
    slides rather than something drawn twice."""
    SLIDES.mkdir(parents=True, exist_ok=True)
    if (SLIDES / "slide-01.png").exists():
        print(f"slides already rendered in {SLIDES}")
        return
    if not DECK.exists():
        raise SystemExit(f"{DECK} is missing — run docs/build_walkthrough_deck.py first.")
    subprocess.run(["soffice", "--headless", "--convert-to", "pdf",
                    "--outdir", str(WORK), str(DECK)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pdf = WORK / f"{DECK.stem}.pdf"
    subprocess.run(["pdftoppm", "-png", "-r", "150", "-f", "1",
                    str(pdf), str(SLIDES / "slide")], check=True)
    # pdftoppm zero-pads to the page count's width; normalise to two digits.
    for path in sorted(SLIDES.glob("slide-*.png")):
        num = int(path.stem.split("-")[-1])
        want = SLIDES / f"slide-{num:02d}.png"
        if path != want:
            path.rename(want)
    print(f"rendered {len(list(SLIDES.glob('slide-*.png')))} slides")


# ---------------------------------------------------------------------------
# Narration
# ---------------------------------------------------------------------------

async def synth(text: str, path: Path, attempts: int = 4) -> None:
    """Speak one line, and verify the result is actually audio.

    edge-tts occasionally returns an empty file when several requests are in
    flight — the call succeeds and writes nothing. Verifying here turns a
    ten-minute-later crash into a retry.
    """
    clean = text.replace("—", ",").replace("·", ",")
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            await edge_tts.Communicate(clean, VOICE, rate=RATE).save(str(path))
            if path.exists() and path.stat().st_size > 2048 and _probe_ok(path):
                return
            last = RuntimeError(f"unreadable audio ({path.stat().st_size if path.exists() else 0} bytes)")
        except Exception as exc:  # noqa: BLE001 — the service is the flaky part
            last = exc
        await asyncio.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"TTS failed for {path.name} after {attempts} attempts: {last}")


def _probe_ok(path: Path) -> bool:
    return subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True).returncode == 0


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def narration_jobs() -> list[tuple[str, str]]:
    jobs = [(f"open{num:02d}", line) for num, line in OPENING]
    jobs += [(f"close{num:02d}", line) for num, line in CLOSING]
    for ci, (_, card, steps) in enumerate(CHAPTERS, start=1):
        jobs.append((f"card{ci}", card))
        jobs += [(f"c{ci}s{si:02d}", line) for si, (line, _) in enumerate(steps)]
    return jobs


async def build_narration() -> dict[str, float]:
    AUDIO.mkdir(parents=True, exist_ok=True)
    jobs = narration_jobs()
    todo = [(k, l) for k, l in jobs if not (AUDIO / f"{k}.mp3").exists()]
    sem = asyncio.Semaphore(3)

    async def guarded(key: str, line: str):
        async with sem:
            await synth(line, AUDIO / f"{key}.mp3")

    if todo:
        await asyncio.gather(*(guarded(k, l) for k, l in todo))
    durations = {k: duration(AUDIO / f"{k}.mp3") for k, _ in jobs}
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "durations.json").write_text(json.dumps(durations, indent=1))
    print(f"narrated {len(durations)} clips, {sum(durations.values())/60:.1f} min of speech")
    return durations


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------

def sign_in(browser) -> None:
    """Sign in once and save the session, so seven contexts do not sign in
    seven times on camera."""
    if STATE.exists():
        return
    ctx = browser.new_context(viewport={"width": W, "height": H})
    page = ctx.new_page()
    page.goto(BASE, wait_until="networkidle")
    page.wait_for_timeout(1500)
    if page.locator("input[autocomplete='username']").count():
        page.fill("input[autocomplete='username']", USER)
        page.fill("input[autocomplete='current-password']", PASSWORD)
        page.click("button.login-submit")
        page.wait_for_timeout(3000)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    ctx.storage_state(path=str(STATE))
    ctx.close()
    print("signed in; session saved")


class Tour:
    """One chapter's worth of driving, with the clock that keeps it in step."""

    def __init__(self, page, targets: list[float], names: list[str]):
        self.page = page
        self.targets = targets
        self.names = names
        self.started = time.monotonic()

    # -- timing ------------------------------------------------------------
    def hold(self, step: int) -> None:
        left = self.targets[step] - (time.monotonic() - self.started)
        if left > 0:
            self.page.wait_for_timeout(int(left * 1000))
        else:
            print(f"    step {step:2} ({self.names[step]}) ran {abs(left):.1f}s over")

    def wait(self, ms: int) -> None:
        self.page.wait_for_timeout(ms)

    # -- actions -----------------------------------------------------------
    def safe(self, fn, what: str) -> bool:
        try:
            fn()
            return True
        except Exception as exc:  # noqa: BLE001 — one control must not end a chapter
            print(f"    ! skipped {what}: {str(exc).splitlines()[0][:100]}")
            return False

    def goto(self, url: str, settle: int = 2600) -> None:
        self.page.goto(f"{BASE}{url}", wait_until="networkidle")
        self.wait(settle)

    def scroll(self, selector: str | None, dy: int, steps: int = 14, pause: int = 90) -> None:
        """Scroll a pane the way a person does — in increments, not one jump.

        A single large wheel event teleports the content and the viewer loses
        their place; a slow ramp reads as reading. When `selector` is given the
        mouse is parked over that element first, because the wheel goes to
        whatever is under the cursor and several panes here scroll internally.
        """
        if selector:
            try:
                box = self.page.locator(selector).first.bounding_box()
                if box:
                    self.page.mouse.move(box["x"] + box["width"] / 2,
                                         box["y"] + min(box["height"] / 2, H / 2))
            except Exception:  # noqa: BLE001
                pass
        per = dy // max(steps, 1)
        for _ in range(steps):
            self.page.mouse.wheel(0, per)
            self.page.wait_for_timeout(pause)

    def tab(self, name: str) -> None:
        self.safe(lambda: self.page.get_by_label("View").get_by_role(
            "button", name=name, exact=False).first.click(), f"tab {name}")
        self.wait(700)

    def role(self, name: str) -> None:
        self.safe(lambda: self.page.get_by_label("Role mode").get_by_role(
            "button", name=name).first.click(), f"role {name}")
        self.wait(900)


# -- the seven chapters -----------------------------------------------------

def chapter_1(t: Tour) -> None:
    t.goto("/?tab=radar", settle=3000)
    t.hold(0)
    t.hold(1)
    t.safe(lambda: t.page.locator("circle.dot").nth(6).hover(), "hover marker")
    t.wait(1200)
    t.hold(2)

    t.safe(lambda: t.page.get_by_role("checkbox", name="Manufacturing").first.check(),
           "vertical filter")
    t.wait(1400)
    t.hold(3)

    t.safe(lambda: t.page.get_by_role("checkbox", name="MEDIUM").first.check(), "competition filter")
    t.wait(900)
    t.safe(lambda: t.page.get_by_role("checkbox", name="Has a sales brief").first.check(),
           "brief filter")
    t.wait(1400)
    t.hold(4)

    # A reload is the reliable reset. An earlier cut cleared the filters with the
    # button, the state did not fully reset, and the next step opened an empty set.
    t.goto(f"/?tab=radar&topic={TOPIC}", settle=3200)
    t.hold(5)

    t.scroll(".detail-pane", 900, steps=12)
    t.hold(6)
    t.scroll(".detail-pane", 1200, steps=14)
    t.hold(7)
    t.scroll(".detail-pane", 1400, steps=16)
    t.hold(8)

    t.safe(lambda: t.page.get_by_role(
        "button", name="How was this calculated?").first.click(), "open explain")
    t.wait(2000)
    t.hold(9)
    t.scroll(".help-backdrop, .explain-body, .modal, body", 1200, steps=14)
    t.hold(10)
    t.page.keyboard.press("Escape")


def chapter_2(t: Tour) -> None:
    t.goto("/?tab=list", settle=3000)
    t.hold(0)
    t.role("Sales")
    t.wait(1800)
    t.hold(1)
    t.role("Presales")
    t.wait(1800)
    t.hold(2)
    t.safe(lambda: t.page.locator('button[aria-label^="Help:"]').first.click(), "role help")
    t.wait(1800)
    t.hold(3)
    t.page.keyboard.press("Escape")


def chapter_3(t: Tour) -> None:
    t.goto(f"/?topic={TOPIC}&view=full", settle=3600)
    t.hold(0)
    t.scroll(".fs-body", 900, steps=12)
    t.hold(1)

    t.tab("Competitors")
    t.wait(2600)
    t.hold(2)
    t.scroll(".fs-body", 1400, steps=16)
    t.hold(3)

    t.tab("Sales brief")
    t.wait(4500)                      # the PDF viewer needs a moment to paint
    t.hold(4)
    t.scroll(".fs-body", 700, steps=10)
    t.hold(5)

    t.tab("Pre-sales")
    t.wait(2600)
    t.hold(6)
    t.scroll(".fs-body", 1100, steps=14)
    t.hold(7)
    t.scroll(".fs-body", 1400, steps=16)
    t.hold(8)
    t.scroll(".fs-body", 1200, steps=14)
    t.hold(9)
    t.scroll(".fs-body", -2400, steps=18)
    t.hold(10)


def chapter_4(t: Tour) -> None:
    t.goto("/?tab=workflow", settle=3200)
    t.hold(0)
    t.scroll(None, 700, steps=10)
    t.hold(1)
    t.scroll(None, 700, steps=10)
    t.hold(2)
    t.scroll(None, -1400, steps=12)
    t.hold(3)


def chapter_5(t: Tour) -> None:
    t.goto("/?tab=analytics", settle=4200)
    t.hold(0)
    t.hold(1)
    t.scroll(None, 1300, steps=16)
    t.hold(2)
    t.scroll(None, 1500, steps=18)
    t.hold(3)


def chapter_6(t: Tour) -> None:
    t.goto("/?screen=generate", settle=3600)
    t.hold(0)
    t.safe(lambda: t.page.get_by_role("tab", name="Cover more of the grid").click(), "grid tab")
    t.wait(2200)
    t.hold(1)
    t.scroll(None, 1100, steps=14)
    t.hold(2)
    t.scroll(None, -1100, steps=10)
    t.safe(lambda: t.page.get_by_role("tab", name="Describe a space").click(), "chat tab")
    t.wait(3200)
    t.hold(3)
    # Short scrolls here on purpose. The conversation and the retrieved-evidence
    # column are the subject of these two lines, and a full-height scroll puts
    # the "already in the radar" list on screen while the voice is describing
    # the interview.
    t.scroll(None, 380, steps=8)
    t.hold(4)
    t.scroll(None, 420, steps=8)
    t.hold(5)


def chapter_7(t: Tour) -> None:
    t.goto("/?view=planner", settle=3600)
    t.hold(0)
    t.hold(1)
    t.scroll(".pl-side", 900, steps=12)
    t.hold(2)

    # Same inputs, same plan: the id is a fingerprint, so this returns the
    # stored plan rather than recomputing it.
    t.safe(lambda: t.page.locator("button.pl-run").first.click(), "build plan")
    t.wait(6000)
    t.hold(3)
    t.hold(4)
    t.scroll(".pl-main", 1400, steps=16)
    t.hold(5)

    t.tab("Spaces")
    t.wait(2200)
    t.scroll(".pl-main", 1300, steps=16)
    t.hold(6)

    t.tab("Business plan")
    t.wait(2200)
    t.scroll(".pl-main", 1200, steps=16)
    t.hold(7)

    t.tab("Assumptions")
    t.wait(2000)
    t.scroll(".pl-main", 900, steps=12)
    t.hold(8)

    t.tab("Document")
    t.wait(6500)                      # a rendered PDF, so give it room
    t.hold(9)

    t.safe(lambda: t.page.get_by_label("Where the portfolio comes from").get_by_role(
        "button", name="Workflow selected").click(), "workflow source")
    t.wait(2200)
    t.hold(10)
    t.safe(lambda: t.page.locator("button.pl-run").first.click(), "build workflow plan")
    t.wait(6000)
    t.hold(11)
    t.scroll(".pl-main", 1300, steps=16)
    t.hold(12)

    t.tab("Business plan")
    t.wait(2200)
    t.scroll(".pl-main", 1000, steps=14)
    t.hold(13)


DRIVERS = [chapter_1, chapter_2, chapter_3, chapter_4, chapter_5, chapter_6, chapter_7]


def record_chapter(browser, index: int, durations: dict[str, float]) -> Path:
    """Record one chapter and return its raw .webm."""
    from playwright.sync_api import Error as PwError  # noqa: F401  (documented dependency)

    ci = index + 1
    _, _, steps = CHAPTERS[index]
    out_dir = CLIPS / f"c{ci}"
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("*.webm"):
        stale.unlink()

    per = [durations[f"c{ci}s{si:02d}"] for si in range(len(steps))]
    targets, running = [], 0.0
    for d in per:
        running += d
        targets.append(running)

    ctx = browser.new_context(
        viewport={"width": W, "height": H},
        storage_state=str(STATE),
        record_video_dir=str(out_dir),
        record_video_size={"width": W, "height": H},
    )
    page = ctx.new_page()
    tour = Tour(page, targets, [name for _, name in steps])
    print(f"  chapter {ci}: {len(steps)} steps, {targets[-1]:.0f}s of narration")
    DRIVERS[index](tour)
    ctx.close()

    video = next(iter(out_dir.glob("*.webm")), None)
    if video is None:
        raise RuntimeError(f"Playwright produced no recording for chapter {ci}")
    print(f"  chapter {ci}: recorded {duration(video):.0f}s")
    return video


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def slide_segment(slide_num: int, audio: Path, out: Path) -> None:
    """One still slide, held for exactly the length of its narration."""
    img = SLIDES / f"slide-{slide_num:02d}.png"
    if not img.exists():
        raise SystemExit(f"missing rendered slide {img}")
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-loop", "1", "-i", str(img), "-i", str(audio),
        "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
               f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=white,fps=30",
        "-c:a", "aac", "-b:a", "160k", "-shortest", str(out),
    ], check=True)


def chapter_segment(index: int, video: Path, out: Path) -> None:
    """Mux one chapter's recording against its own narration track."""
    ci = index + 1
    _, _, steps = CHAPTERS[index]
    listing = WORK / f"c{ci}_audio.txt"
    listing.write_text("\n".join(
        f"file '{AUDIO / f'c{ci}s{si:02d}.mp3'}'" for si in range(len(steps))))
    track = WORK / f"c{ci}_audio.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(listing), "-c", "copy", str(track)], check=True)
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(video), "-i", str(track),
        "-c:v", "libx264", "-crf", "21", "-preset", "medium", "-pix_fmt", "yuv420p",
        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
               f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=white,fps=30",
        "-c:a", "aac", "-b:a", "160k", "-shortest", str(out),
    ], check=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chapters", help="comma-separated chapter numbers to re-record")
    args = ap.parse_args()
    only = {int(x) for x in args.chapters.split(",")} if args.chapters else None

    WORK.mkdir(parents=True, exist_ok=True)
    SEG.mkdir(parents=True, exist_ok=True)
    render_slides()
    durations = asyncio.run(build_narration())

    from playwright.sync_api import sync_playwright

    videos: dict[int, Path] = {}
    with sync_playwright() as p:
        # Headed. A headless Chromium shows a grey box where an embedded PDF
        # should be, and three chapters here are largely a PDF on the page.
        browser = p.chromium.launch(headless=False,
                                    args=["--force-device-scale-factor=1",
                                          f"--window-size={W},{H + 120}"])
        sign_in(browser)
        for i in range(len(CHAPTERS)):
            if only and (i + 1) not in only:
                existing = next(iter((CLIPS / f"c{i+1}").glob("*.webm")), None)
                if existing:
                    videos[i] = existing
                    continue
            videos[i] = record_chapter(browser, i, durations)
        browser.close()

    segments: list[Path] = []
    for num, _ in OPENING:
        out = SEG / f"open{num:02d}.mp4"
        slide_segment(num, AUDIO / f"open{num:02d}.mp3", out)
        segments.append(out)

    for i, (card_slide, _, _) in enumerate(CHAPTERS):
        card = SEG / f"card{i+1}.mp4"
        slide_segment(card_slide, AUDIO / f"card{i+1}.mp3", card)
        segments.append(card)
        body = SEG / f"c{i+1}.mp4"
        chapter_segment(i, videos[i], body)
        segments.append(body)
        print(f"  chapter {i+1} segment built")

    for num, _ in CLOSING:
        out = SEG / f"close{num:02d}.mp4"
        slide_segment(num, AUDIO / f"close{num:02d}.mp3", out)
        segments.append(out)

    listing = WORK / "segments.txt"
    listing.write_text("\n".join(f"file '{s}'" for s in segments))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
        "-i", str(listing), "-c:v", "libx264", "-crf", "21", "-preset", "medium",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
        str(OUT),
    ], check=True)
    print(f"\nwrote {OUT}  ({duration(OUT)/60:.1f} min)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
