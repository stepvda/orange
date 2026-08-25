"""Build the hands-on walkthrough video (docs/Orange_Innovation_Radar_Walkthrough.mp4).

SUPERSEDED BY docs/build_demo.py. That build covers everything this one does and
four subsystems this one predates — the Planner, the pre-sales pack, the scoping
conversation and sign-in — and it records HEADED, so the embedded PDFs actually
render. This script is kept because the film it produced is still in docs/ and a
build that cannot be re-run is a film nobody can correct. Do not extend it;
extend build_demo.py.


A different film from Orange_Innovation_Radar.mp4. That one explains the
thinking; this one shows a person how to actually use the tool. So the deck is
cut to three slides — just enough vocabulary to follow along — and the rest is a
single continuous live demo of every screen and control.

Same synchronisation approach as the other build: narration is generated first
so its exact length is known, and the browser holds each step until a CUMULATIVE
target, so a step that overruns is absorbed by the next rather than pushing the
voice out of step with the picture for the rest of the film.

Prerequisites: API on :8000, frontend on :5173, and docs/build_deck.py already
run (this reuses its rendered slides).

    python3 docs/build_walkthrough.py
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parents[1]
WORK = Path("/tmp/walk")
SLIDES = Path("/tmp/vid/slides")          # rendered by the deck build
AUDIO = WORK / "audio"
SEG = WORK / "seg"
DEMO = WORK / "demo"
OUT = ROOT / "docs" / "Orange_Innovation_Radar_Walkthrough.mp4"

VOICE = "en-US-BrianNeural"
RATE = "-3%"
W, H = 1920, 1080

# The topic the tour opens: it already has a description, a PDF brief,
# observed-confidence sizing and a scored competitive field, so every panel has
# something real in it rather than an empty state.
TOPIC = "OS021"

# Short intro — three slides from the main deck, then straight into the app.
INTRO = [
    (1, "This is a walkthrough of the Orange Business Innovation Radar. The last "
        "film explained the thinking behind it; this one shows you how to use it. Three "
        "slides of vocabulary, then we go straight into the running application."),
    (3, "First, what a topic is. An opportunity space is a triple — a vertical, a use "
        "case, and a technology — plus a sentence a salesperson could actually open a "
        "meeting with. The triple is the identity, so the same topic keeps its identity "
        "across refreshes rather than being recreated each time."),
    (4, "Second, the scores. Attractiveness asks whether the world is moving. Right to "
        "win asks whether Orange can play and can win. They are never combined. A third "
        "quantity, conviction, records what your own colleagues think, and changes the "
        "order things appear in without touching either score. Keep those three apart in "
        "your head and everything else follows."),
]

# The tour. Each entry is (narration, step-name). Step names are for the log only.
TOUR = [
    ("Here is the application. Along the top there are three role modes on the left, the "
     "views in the middle, and on the right the date of the last refresh and the weight "
     "set — the configuration version that produced every number on screen.", "orient"),

    ("The radar is the default view. Angular sectors are the six business domains. "
     "Distance from the centre is the time horizon: Now in the middle, Later at the rim. "
     "Marker size is attractiveness, and marker colour is right to win, from light to "
     "dark. So the two questions the radar exists to answer are visible at once.",
     "radar_read"),

    ("Hovering a marker gives you the summary — the statement, both scores, the horizon, "
     "the portfolio distance and how many signals support it. A marker with an "
     "exclamation mark carries an evidence gap, meaning Orange has few or no published "
     "references in that vertical.", "radar_hover"),

    ("The left rail is where you narrow things down. Every dimension is multi select, and "
     "the counts beside each value come from the server across everything your role can "
     "see — not just the rows currently on screen. Picking Manufacturing filters "
     "everything: the radar, the list, and the analytics.", "filter_vertical"),

    ("You can also filter by how crowded the field is, and by whether a topic already has "
     "a sales brief built. That second one is the fastest way for a salesperson to find "
     "something they can take into a meeting today.", "filter_more"),

    ("There is free text search across statements and claims, and a single button to "
     "clear everything and start again.", "search_clear"),

    ("By default a view shows twenty four topics, to protect signal to noise. It tells you "
     "how many more match, and you can ask for more, or for all of them. The cap is a "
     "default, not a dead end.", "show_more"),

    ("The order control re-ranks what you are looking at. Ranked for this role is the "
     "default; you can also sort by the largest serviceable market, by attractiveness, or "
     "by right to win. It changes the order, never which topics you can see.", "sort"),

    ("Switching role changes the ranking function, not just a filter. Sales ranks on right "
     "to win and proof points, and only shows topics Orange could deliver at L zero or L "
     "one that have a published reference in that vertical and no evidence gap — which is "
     "why the count drops. Presales ranks on differentiation instead.", "roles"),

    ("The list view is the same topics as rows. Each row carries attractiveness, right to "
     "win, the horizon, the portfolio distance, the competitive intensity, the serviceable "
     "market per year, and the number of supporting signals.", "list"),

    ("Clicking a row opens the detail pane on the right. This is one page in the order your "
     "questions actually arrive. It starts with why the topic is hot now — and every claim "
     "is bound to the signals that support it. Those chips link out to the original dated "
     "source, so nothing here has to be taken on trust.", "detail_why"),

    ("Next, market opportunity. This is built bottom up — enterprise counts, an adoption "
     "rate, and a contract value — rather than quoted from a report. It shows the method "
     "and a confidence label, so you can argue with the arithmetic instead of the "
     "conclusion.", "detail_market"),

    ("Then competition: who is visibly playing in this space, scored from a versioned "
     "register against the evidence actually collected. A crowded field is not a reason to "
     "walk away — it is a reason to lead with a specific differentiator.", "detail_comp"),

    ("Below that, questions to ask and objections to expect, and a detailed description of "
     "the solution shape. Both are generated on demand and grounded in the same cited "
     "evidence.", "detail_desc"),

    ("Then the part that answers can we play, can we win. These are named, individually "
     "inspectable assets — a specific offer, a specific certification, a specific partner "
     "tier — never a vague claim that Orange has relevant capabilities. Anything marked "
     "awaiting curator has been proposed by the machine and not yet confirmed by a human.",
     "detail_links"),

    ("Further down there is the score breakdown, the derived time horizon with the test "
     "that produced it, and a recommended next action written for whichever role you are "
     "currently in.", "detail_rest"),

    ("Any score can be interrogated. The how was this calculated button opens the full "
     "working.", "explain_open"),

    ("It shows each component, its weight, and its contribution to the total — and then, "
     "component by component, the actual stored inputs. Here are the publishers counted "
     "and their entropy, the tier distribution of the evidence, and the per period buckets "
     "the momentum slope was fitted to. This is what makes the number arguable rather than "
     "merely displayed.", "explain_expand"),

    ("The brief view turns a topic into a PDF you can take into a customer meeting. Briefs "
     "already built are listed, and you can download or open one directly.", "brief"),

    ("The workflow view is the stage gate. A topic moves from shortlisted, through demand "
     "tested and packaged, to live, and ownership moves with it — strategist, then sales, "
     "then presales. Cards flag when they have been sitting too long, and when the team "
     "and the evidence disagree.", "workflow_board"),

    ("You advance a topic from its detail pane. And this is where each role gives its "
     "assessment — you rate only the axis your role owns. Sales rates customer demand; "
     "hovering a level tells you exactly what that level means, which is what makes a zero "
     "to five scale mean the same thing to two different people.", "assess"),

    ("Submitting records it, with a confidence weighting and an optional reason. Those "
     "assessments become team conviction, and where conviction and the evidence disagree "
     "sharply, the topic is flagged for review — because disagreement is information, not "
     "friction.", "assess_submit"),

    ("The analytics view steps back to the whole corpus, and deliberately ignores your "
     "filters — it answers where is the radar as a whole. The heatmap is vertical by "
     "domain, and the empty cells are the white space. Beside it, where sized opportunity "
     "concentrates, in euros per year.", "analytics"),

    ("Scrolling on, the diverging chart shows where the team and the evidence disagree, the "
     "stage funnel shows the pipeline, and the evidence mix, portfolio distance, source "
     "tiers and language coverage describe the corpus the whole thing rests on.",
     "analytics_scroll"),

    ("White space is high attractiveness with no path from the current portfolio — the "
     "strategist's innovation agenda, and precisely what a salesperson should never be "
     "shown.", "whitespace"),

    ("Coverage reports the corpus honestly: languages, source tiers, signal types and "
     "geographies. Anglophone bias is a named risk, so it is measured rather than assumed.",
     "coverage"),

    ("Finally, everything dense explains itself. The question mark buttons open a "
     "definition of what the thing is, why it works that way, and which requirement it "
     "came from. There is a light and dark theme, and every view is deep linkable, so you "
     "can send a colleague a topic, a role and a score explanation in a single URL.",
     "help"),
]


# ---------------------------------------------------------------------------
# Narration
# ---------------------------------------------------------------------------

def _probe_ok(path: Path) -> bool:
    return subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True).returncode == 0


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


async def synth(text: str, path: Path, attempts: int = 4) -> None:
    clean = text.replace("—", ",").replace("·", ",")
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            await edge_tts.Communicate(clean, VOICE, rate=RATE).save(str(path))
            if path.exists() and path.stat().st_size > 2048 and _probe_ok(path):
                return
            last = RuntimeError("unreadable audio")
        except Exception as exc:  # noqa: BLE001 — the service is the flaky part
            last = exc
        await asyncio.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"TTS failed for {path.name}: {last}")


async def build_narration() -> dict[str, float]:
    AUDIO.mkdir(parents=True, exist_ok=True)
    jobs = [(f"intro{num:02d}", line) for num, line in INTRO]
    jobs += [(f"tour{i:02d}", line) for i, (line, _) in enumerate(TOUR)]

    sem = asyncio.Semaphore(3)

    async def one(key: str, line: str):
        async with sem:
            await synth(line, AUDIO / f"{key}.mp3")

    await asyncio.gather(*(one(k, l) for k, l in jobs))
    durations = {k: duration(AUDIO / f"{k}.mp3") for k, _ in jobs}
    (WORK / "durations.json").write_text(json.dumps(durations, indent=1))
    print(f"narrated {len(durations)} clips, {sum(durations.values())/60:.1f} min")
    return durations


def slide_segment(slide_num: int, audio: Path, out: Path) -> None:
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-loop", "1", "-i", str(SLIDES / f"slide-{slide_num:02d}.png"),
        "-i", str(audio),
        "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
               f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=white,fps=30",
        "-c:a", "aac", "-b:a", "160k", "-shortest", str(out),
    ], check=True)


# ---------------------------------------------------------------------------
# The tour
# ---------------------------------------------------------------------------

def record_tour(durations: dict[str, float]) -> Path:
    from playwright.sync_api import sync_playwright

    DEMO.mkdir(parents=True, exist_ok=True)
    for stale in DEMO.glob("*.webm"):
        stale.unlink()

    pause = [durations[f"tour{i:02d}"] for i in range(len(TOUR))]
    targets, running = [], 0.0
    for d in pause:
        running += d
        targets.append(running)

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--force-device-scale-factor=1"])
        ctx = browser.new_context(
            viewport={"width": 1600, "height": 900},
            record_video_dir=str(DEMO), record_video_size={"width": 1600, "height": 900},
        )
        page = ctx.new_page()
        started = time.monotonic()

        def hold(step: int):
            left = targets[step] - (time.monotonic() - started)
            if left > 0:
                page.wait_for_timeout(int(left * 1000))
            else:
                print(f"  step {step:2} ({TOUR[step][1]}) ran {abs(left):.1f}s over")

        def safe(fn, what: str):
            try:
                fn()
            except Exception as exc:  # noqa: BLE001 — never let one control end the tour
                print(f"  skipped {what}: {str(exc).splitlines()[0][:90]}")

        # The header repeats view names in a skip-nav landmark, so scope by group.
        # Two groups, because the top bar has two: the view tabs, and the tray
        # holding Generate / Workflow / Planner. Workflow is a tab that lives in
        # the second one — it renders in the reading layout like every other tab,
        # but it is read beside the two controls that also change the portfolio.
        def tab(name: str):
            def click() -> None:
                for group in ("View", "Portfolio"):
                    button = page.get_by_role("group", name=group).get_by_role(
                        "button", name=name, exact=True)
                    if button.count():
                        button.first.click()
                        return
                raise LookupError(f"no {name!r} button in the View or Portfolio groups")
            safe(click, f"tab {name}")
            page.wait_for_timeout(500)

        def role(name: str):
            safe(lambda: page.get_by_label("Role mode").get_by_role(
                "button", name=name).first.click(), f"role {name}")
            page.wait_for_timeout(500)

        def scroll_to(text_: str, where: str):
            # Scoped to the detail pane on purpose: several of these words also
            # appear as filter labels in the left rail, and an unscoped match
            # scrolls the wrong column.
            safe(lambda: page.locator(".detail-pane").locator(f"text={text_}")
                 .first.scroll_into_view_if_needed(), f"scroll to {where}")
            page.wait_for_timeout(500)

        # -- orientation ---------------------------------------------------
        page.goto("http://localhost:5173/?tab=radar", wait_until="networkidle")
        page.wait_for_timeout(2600)
        hold(0)
        hold(1)

        safe(lambda: page.locator("circle.dot").nth(5).hover(), "hover marker")
        hold(2)

        # -- filters -------------------------------------------------------
        safe(lambda: page.get_by_role("checkbox", name="Manufacturing").first.check(), "vertical filter")
        page.wait_for_timeout(900)
        hold(3)

        safe(lambda: page.get_by_role("checkbox", name="MEDIUM").first.check(), "competition filter")
        page.wait_for_timeout(700)
        safe(lambda: page.get_by_role("checkbox", name="Has a sales brief").first.check(), "brief filter")
        page.wait_for_timeout(900)
        hold(4)

        safe(lambda: page.locator("input.search-input").fill("security"), "search")
        page.wait_for_timeout(1200)
        hold(5)

        # Clear, then VERIFY. The first cut left three filters applied — the
        # click resolved but the state did not fully reset — and the next role
        # switch landed on an empty result set, so the viewer watched "0 match"
        # while the narration explained role ranking. A reload is the reliable
        # reset, and cheap.
        safe(lambda: page.get_by_role("button", name="Clear").first.click(), "clear filters")
        page.wait_for_timeout(900)
        if page.locator("input.search-input").input_value() or "0 match" in page.content():
            page.goto("http://localhost:5173/?tab=radar", wait_until="networkidle")
            page.wait_for_timeout(1500)

        # -- cap and sort ---------------------------------------------------
        safe(lambda: page.get_by_role("button", name="Show 24 more").first.click(), "show more")
        page.wait_for_timeout(1200)
        hold(6)

        safe(lambda: page.locator(".sort-control select").select_option(label="Largest serviceable market"),
             "sort by market size")
        page.wait_for_timeout(1200)
        hold(7)
        safe(lambda: page.locator(".sort-control select").select_option(index=0), "sort back to rank")
        page.wait_for_timeout(600)

        # -- roles ----------------------------------------------------------
        # Guarantee a populated view before talking about role ranking: an empty
        # screen here would illustrate the opposite of the point being made.
        if "No topics match" in page.content():
            page.goto("http://localhost:5173/?tab=radar", wait_until="networkidle")
            page.wait_for_timeout(1500)
        role("Sales")
        page.wait_for_timeout(1300)
        role("Presales / Proposal")
        page.wait_for_timeout(1300)
        role("Sales")
        hold(8)

        # -- list -----------------------------------------------------------
        tab("List")
        page.wait_for_timeout(1400)
        hold(9)

        # -- detail pane tour -------------------------------------------------
        page.goto(f"http://localhost:5173/?tab=list&role=sales&topic={TOPIC}",
                  wait_until="networkidle")
        page.wait_for_timeout(2200)
        scroll_to("Why it is hot now", "why hot")
        hold(10)
        scroll_to("Market opportunity", "market size")
        hold(11)
        scroll_to("Competition", "competition")
        hold(12)
        scroll_to("Detailed description", "description")
        hold(13)
        scroll_to("Can we play, can we win", "links")
        hold(14)
        scroll_to("Next action, by role", "next action")
        hold(15)

        # -- score explanation -------------------------------------------------
        safe(lambda: page.get_by_role("button", name="How was this calculated?").first.click(),
             "open explain")
        page.wait_for_timeout(1600)
        hold(16)
        safe(lambda: page.locator(".se-detail summary").first.click(), "expand component")
        page.wait_for_timeout(900)
        safe(lambda: page.locator(".se-detail").nth(1).scroll_into_view_if_needed(), "scroll explain")
        page.wait_for_timeout(700)
        safe(lambda: page.locator(".se-detail summary").nth(3).click(), "expand momentum")
        page.wait_for_timeout(900)
        hold(17)
        page.keyboard.press("Escape")
        page.wait_for_timeout(600)

        # -- brief -------------------------------------------------------------
        tab("Brief")
        page.wait_for_timeout(1800)
        hold(18)

        # -- workflow -----------------------------------------------------------
        tab("Workflow")
        page.wait_for_timeout(1800)
        hold(19)

        safe(lambda: page.locator(".board-card").first.click(), "open board card")
        page.wait_for_timeout(1400)
        scroll_to("Your assessment", "assessment widget")
        safe(lambda: page.locator(".rating button").nth(4).hover(), "hover rating")
        page.wait_for_timeout(900)
        hold(20)
        safe(lambda: page.locator(".rating button").nth(4).click(), "pick rating")
        page.wait_for_timeout(700)
        safe(lambda: page.get_by_role("button", name="Submit assessment").first.click(), "submit")
        page.wait_for_timeout(1600)
        hold(21)

        # -- analytics ----------------------------------------------------------
        tab("Analytics")
        page.wait_for_timeout(2400)
        hold(22)
        safe(lambda: page.locator("text=Stage gate").first.scroll_into_view_if_needed(), "scroll analytics")
        page.wait_for_timeout(1400)
        hold(23)

        # -- white space / coverage ---------------------------------------------
        tab("White space")
        page.wait_for_timeout(1600)
        hold(24)
        tab("Coverage")
        page.wait_for_timeout(1800)
        hold(25)

        # -- help + theme ---------------------------------------------------------
        tab("Radar")
        page.wait_for_timeout(1200)
        safe(lambda: page.locator('button[aria-label^="Help:"]').first.click(), "open help")
        page.wait_for_timeout(1800)
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
        safe(lambda: page.get_by_title("Theme").first.click(), "theme toggle")
        page.wait_for_timeout(1500)
        hold(26)

        ctx.close()
        browser.close()

    video = next(iter(DEMO.glob("*.webm")), None)
    if video is None:
        raise RuntimeError("Playwright produced no recording")
    print(f"recorded tour: {duration(video):.0f}s")
    return video


def build_tour_segment(video: Path, out: Path) -> None:
    listing = WORK / "tour_audio.txt"
    listing.write_text("\n".join(
        f"file '{AUDIO / f'tour{i:02d}.mp3'}'" for i in range(len(TOUR))))
    track = WORK / "tour_audio.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(listing), "-c", "copy", str(track)], check=True)
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(video), "-i", str(track),
        "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
               f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=white,fps=30",
        "-c:a", "aac", "-b:a", "160k", "-shortest", str(out),
    ], check=True)


def main() -> int:
    if not (SLIDES / "slide-01.png").exists():
        print("Rendered slides missing — run docs/build_deck.py and render to /tmp/vid/slides.",
              file=sys.stderr)
        return 1
    WORK.mkdir(parents=True, exist_ok=True)
    SEG.mkdir(parents=True, exist_ok=True)
    for stale in SEG.glob("*.mp4"):
        stale.unlink()

    durations = asyncio.run(build_narration())

    segments = []
    for num, _ in INTRO:
        out = SEG / f"i{num:02d}.mp4"
        slide_segment(num, AUDIO / f"intro{num:02d}.mp3", out)
        segments.append(out)
        print("intro slide", num)

    video = record_tour(durations)
    tour_seg = SEG / "tour.mp4"
    build_tour_segment(video, tour_seg)
    segments.append(tour_seg)

    listing = WORK / "segments.txt"
    listing.write_text("\n".join(f"file '{s}'" for s in segments))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
        "-i", str(listing), "-c:v", "libx264", "-crf", "21", "-preset", "medium",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
        str(OUT),
    ], check=True)
    (WORK / "DONE").write_text(str(OUT))
    print(f"\nwrote {OUT}  ({duration(OUT)/60:.1f} min)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
