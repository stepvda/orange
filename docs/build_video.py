"""Build the narrated video walkthrough (docs/Orange_Innovation_Radar.mp4).

Three parts, assembled with ffmpeg:

  1. Concept slides   — rendered from the same .pptx, so the deck and the video
                        can never drift apart.
  2. Live demo        — a real browser driven by Playwright against the running
                        app, recorded as video. Nothing is faked or mocked up.
  3. Architecture     — the closing slides.

Narration is Microsoft's `en-US-BrianNeural` via edge-tts.

Synchronisation approach: every narration clip is generated FIRST, so its exact
duration is known. Slide segments are then held for precisely that long, and the
demo script dwells on each step for its own line's duration. That keeps voice
and picture together without hand-tuned sleeps.

Prerequisites: the API on :8000 and the frontend on :5173 must be running, and
docs/build_deck.py must have been run.

    python3 docs/build_video.py
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
WORK = Path("/tmp/vid")
SLIDES = WORK / "slides"
AUDIO = WORK / "audio"
SEG = WORK / "seg"
DEMO = WORK / "demo"
OUT = ROOT / "docs" / "Orange_Innovation_Radar.mp4"

VOICE = "en-US-BrianNeural"
RATE = "-4%"      # a touch slower than default; this is dense material
W, H = 1920, 1080

BASE = "http://localhost:5173"
USER, PASSWORD = "orange", "orange"

DECK = ROOT / "docs" / "Orange_Innovation_Radar.pptx"

#: The space the demo opens. The one with the whole chain built — description,
#: brief, sizing, competition, competitor comparison and all twelve pre-sales
#: artefacts — so no panel in the demo is an empty state.
TOPIC = "OS004"

# ---------------------------------------------------------------------------
# Narration
# ---------------------------------------------------------------------------

# (slide number in the rendered PDF, narration)
SLIDE_SCRIPT = [
    (1, "This is the Orange Business Innovation Radar — a working prototype built against the "
        "requirements baseline. It maintains a regularly refreshed view of specific innovation "
        "opportunities, each scored on how attractive it is, how urgent the window is, and how "
        "strong Orange's right to win is."),
    (2, "The problem it solves is not a shortage of information about technology. The information "
        "that exists is generic, undated, unsourced, and disconnected from what Orange can "
        "actually sell. Ay Eye, Cloud and Cybersecurity are rejected as topics — they fail "
        "validation. A real topic reads like this: private five G plus edge vision for safety "
        "compliance in mining. Specific enough to open a customer meeting with."),
    (3, "So an opportunity space is a triple: a vertical, times a use case, times a technology. "
        "The triple is the identity — it gives deduplication and filtering, and it is what makes a "
        "topic recur across refreshes rather than being recreated each time. The human readable "
        "statement is a rendering of that triple. A candidate that does not resolve to exactly one "
        "of each fails validation automatically."),
    (4, "Every topic carries two scores that are never combined. Attractiveness asks whether the "
        "world is moving, and is computed from external evidence alone. Right to win asks whether "
        "we can play and whether we can win, and is computed from a curated graph of Orange's "
        "offers, references, partners and certifications — as named query results, never asserted "
        "by a language model. Collapsing them would destroy the information the strategist needs. "
        "A third quantity, conviction, captures what our own people believe, and adjusts ranking "
        "without ever touching the other two."),
    (5, "The model never invents a topic out of its own knowledge. Four defences enforce that. "
        "Every claim must cite signal identifiers that exist in the cluster that produced it, and "
        "uncited claims are stripped rather than rewritten. Taxonomy values are validated against "
        "closed vocabularies. No number is ever generated — market sizes are looked up and "
        "attributed, or they are absent. And a second pass checks each claim is genuinely entailed "
        "by the span it cites. On top of that, an adversarial critic rejected three hundred and "
        "forty five of six hundred and forty four candidates in the live run, with written "
        "reasons."),
    (6, "Portfolio distance is the most decision relevant number in the product. It is the "
        "shortest path from a topic to something Orange could actually deliver. L zero means an "
        "existing offer already addresses it — that is a sales conversation. L two needs a "
        "partner. L four is white space, with no plausible path from the current portfolio. This "
        "is what drives the role modes: a high attractiveness L four topic is exactly the "
        "strategist's innovation agenda, and exactly what a salesperson should never be shown."),
    (7, "Here is what the prototype has actually produced, read live from its database. Four "
        "hundred and eighteen opportunity spaces, from eleven thousand signals gathered across "
        "thirty four live sources, joined to four thousand eight hundred named asset links. All "
        "fifteen verticals are covered. Three hundred and fourteen spaces carry a bottom up market "
        "size, a hundred and eighty one a competitive assessment, and a hundred and seventy four a "
        "sales brief. And the corpus carries over a thousand French language signals, so the "
        "anglophone bias named as a principal risk is measured rather than assumed."),
    (8, "Two further questions a topic cannot be acted on without: how big is it, and who else is "
        "already there. Headline market figures in the press come from paid research, are quoted "
        "without methodology, and often conflict by an order of magnitude. So the radar builds its "
        "own estimate bottom up — enterprise counts, times an observed adoption rate, times a "
        "plausible contract value — and shows its working, with a method and a confidence label "
        "attached. Competitive intensity is scored against a versioned competitor register. A "
        "crowded field is not a reason to walk away; it is a reason to win on a specific "
        "differentiator."),
    (9, "There are also two routes into a new opportunity space, for the case a scheduled refresh "
        "cannot serve. Parameters, for somebody who knows the taxonomy. And a scoping "
        "conversation, for somebody who knows their market but not this vocabulary — an assistant "
        "that interviews with the corpus in front of it, re-retrieving on every turn. Both are "
        "refused by the same gate, and the corpus holds it rather than the model: asked whether it "
        "has enough, a model says yes, so the button is enabled by what actually came back."),
]

CLOSING_SCRIPT = [
    (22, "Architecturally this is seven pipeline stages, each with a defined input and output "
         "contract so they can be developed and replaced independently. Collect, normalise, "
         "classify, cluster into themes, synthesise candidates, enrich them with further evidence, "
         "score, and serve. A parallel slower path maintains the Orange Business Graph and joins "
         "at the scoring stage, so right to win can be improved without re-running discovery. And "
         "two subsystems sit beside the pipeline rather than in it — the Planner, which reads the "
         "read model and an assumptions file, and the pre-sales renderer, which reads one snapshot "
         "of a space and emits twelve artefacts in five formats."),
    (23, "The stack is deliberately unremarkable, because the value is in the schema and the "
         "curation rather than the infrastructure. Thirty three sources across seventeen connector "
         "types feed a signal store. "
         "DeepSeek sits behind a provider agnostic client, so switching to a sovereign local model "
         "is an environment variable rather than a rewrite. Embeddings run locally. The graph is "
         "thousands of nodes, not millions, so SQLite is entirely adequate. Portfolio selection is "
         "a mixed integer program solved by scipy. And every path now sits behind a session guard "
         "applied to the whole application rather than route by route, because the failure mode of "
         "a per-route guard is the route somebody forgot."),
    (24, "That gives six guarantees about the numbers. Every displayed score decomposes into named "
         "components. Every component stores the inputs used to compute it, so any number can be "
         "re-derived. Lineage runs from a displayed claim back to the raw ingested item. Every "
         "score records its weight set, so trajectories are never plotted across an incomparable "
         "boundary. And counting, diversity and momentum are arithmetic, never a model — because a "
         "model asked to count is occasionally wrong and always unverifiable."),
    (25, "Finally, what is deliberately not built, and what needs a decision from Orange. There is "
         "no CRM integration and no learned scoring model, because no labels exist on day one. "
         "There is no return on investment figure on a plan, because there is no cost data at the "
         "granularity a space would need — revenue and profit are defensible from what exists, an "
         "ROI would require inventing the denominator. And sign in answers who, not may they: per "
         "role authorisation on the write endpoints is still absent. On the other side, four "
         "things need a human. Four thousand eight hundred links are machine proposed and "
         "unconfirmed. One table from Orange finance — margin by portfolio distance — moves five "
         "year profit by a factor of one point six six. The share of headcount free for new work "
         "is the constraint that binds first in most plans, and it is currently a guess. And terms "
         "of use are unconfirmed for several enabled sources."),
    (26, "The join between an external signal and an internal asset is the product. Without it "
         "this is a competent trend feed, and trend feeds already exist. With it, the radar "
         "answers a question nobody else can answer for Orange."),
]

# Live demo steps, standing in for slides 10 to 21. Each is (narration, action-name).
DEMO_SCRIPT = [
    ("Here is the running application. The radar is the signature view. Angular sectors are the "
     "six business domains; distance from the centre is the time horizon, with Now at the middle "
     "and Later at the rim.", "radar_intro"),
    ("Marker size is attractiveness and marker colour is right to win, so the two questions the "
     "radar exists to answer are visible at the same time. A marker with an exclamation mark "
     "carries an evidence gap — Orange has few published references in that vertical.",
     "radar_dwell"),
    ("Above the chart, the screen states which question it is answering. Strategist: decide where "
     "to invest study and prototyping effort next quarter. Switch to Sales and both the "
     "instruction and the set change, because Sales ranks on right to win and proof point density "
     "and only shows topics with a delivery path, a published reference in the vertical, and no "
     "evidence gap. The count drops, and that drop is the point.", "role_sales"),
    ("The list view shows the same topics ranked for the selected role, with attractiveness, right "
     "to win, horizon, portfolio distance and the number of supporting signals on every row.",
     "list_view"),
    ("Opening a topic gives the detail pane. Every claim under why it is hot now is bound to the "
     "signal identifiers that support it, and each chip links out to the original dated source.",
     "open_topic"),
    ("Further down, can we play and can we win is itemised against named Orange assets — a "
     "specific offer, a specific certification, a specific partner tier — never an aggregate "
     "assertion that Orange has relevant capabilities.", "scroll_links"),
    ("Now the part that makes the scoring defensible. Every topic has a how was this calculated "
     "surface. It shows the weight table and the weighted total, and then, per component, the "
     "actual stored inputs: the publishers counted and their entropy, the tier distribution, the "
     "per period buckets the momentum slope was fitted to. This is how a reviewer outside the "
     "project can reconstruct why a topic holds its rank.", "open_explain"),
    ("A space also opens full screen, with the three panes out of the way, in four tabs: the "
     "space, the competitors, the sales brief, and the pre-sales pack. That is the order the "
     "questions arrive in — what is this, who else is here, what do I send, and what happens after "
     "the meeting.", "fullscreen"),
    ("The brief is the PDF a salesperson takes into a meeting, rendered here on the page rather "
     "than hidden behind a download. And it knows when it is out of date: the space has been "
     "refreshed since this was built, and the banner says so. Showing it beside the space is what "
     "makes anyone notice.", "brief"),
    ("The fourth tab is the pre-sales pack — twelve pieces for the work between that first meeting "
     "and a proposal, each in the format its reader actually works in, and all built from one "
     "snapshot of the space so nothing in the pack can disagree with anything else in it.",
     "presales"),
    ("The workflow board implements the stage gate. A topic moves from shortlisted, through demand "
     "tested and packaged, to live, and ownership follows the stage. Each role assesses only the "
     "axis it owns, on a zero to five scale with written anchors, because people are unreliable at "
     "rating something seventy three out of a hundred.", "workflow"),
    ("The analytics view visualises the whole corpus. The heatmap is vertical by domain, and the "
     "empty cells are the white space. The diverging chart shows where the team and the evidence "
     "disagree — that is a review queue, because disagreement is information rather than "
     "friction.", "analytics"),
    ("The Generate screen opens with a conversation rather than a text box. The assistant "
     "interviews with the corpus in front of it and shows what each turn retrieved — publisher, "
     "date and cosine — beside the answer. The Generate button is enabled by that evidence rather "
     "than by the assistant's opinion of itself.", "generate"),
    ("And the Planner turns the ranking into a portfolio. State a budget and a capacity and a "
     "mixed integer program chooses the set, in an order, with a five year projection — and "
     "reports which constraint bound it, which is the thing a ranked list cannot tell you. Or take "
     "the set as already decided: everything the board moved to demand tested or beyond, "
     "scheduled and costed with nothing dropped to make it fit.", "planner"),
    ("And throughout, every dense concept explains itself, with a pointer back to the requirement "
     "it comes from.", "help"),
]


async def synth(text: str, path: Path, attempts: int = 4) -> None:
    """Speak one line, verifying the result is actually audio.

    edge-tts occasionally returns an empty file when several requests are in
    flight — the call succeeds and writes nothing. A zero-byte clip then fails
    much later, at the probe step, after the whole narration set has been
    generated. Verifying here turns a ten-minute-later crash into a retry.
    """
    clean = text.replace("—", ",").replace("·", ",")
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            await edge_tts.Communicate(clean, VOICE, rate=RATE).save(str(path))
            # Size alone is not enough: a truncated clip can be 100 KB and still
            # be unreadable. Probing is the only check that means anything.
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


async def build_narration() -> dict[str, float]:
    AUDIO.mkdir(parents=True, exist_ok=True)
    jobs = []
    for num, line in SLIDE_SCRIPT + CLOSING_SCRIPT:
        jobs.append((f"slide{num:02d}", line))
    for i, (line, _) in enumerate(DEMO_SCRIPT):
        jobs.append((f"demo{i:02d}", line))

    # edge-tts is a network round trip per clip; run them concurrently.
    async def one(key: str, line: str):
        await synth(line, AUDIO / f"{key}.mp3")
        return key

    sem = asyncio.Semaphore(3)

    async def guarded(key, line):
        async with sem:
            return await one(key, line)

    await asyncio.gather(*(guarded(k, l) for k, l in jobs))
    durations = {k: duration(AUDIO / f"{k}.mp3") for k, _ in jobs}
    (WORK / "durations.json").write_text(json.dumps(durations, indent=1))
    print(f"narrated {len(durations)} clips, "
          f"{sum(durations.values()):.0f}s total")
    return durations


def slide_segment(slide_num: int, audio: Path, out: Path) -> None:
    """One still slide held for exactly the length of its narration."""
    img = SLIDES / f"slide-{slide_num:02d}.png"
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-loop", "1", "-i", str(img),
        "-i", str(audio),
        "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
               f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=white,fps=30",
        "-c:a", "aac", "-b:a", "160k", "-shortest",
        str(out),
    ], check=True)


def record_demo(durations: dict[str, float]) -> Path:
    """Drive the real app with Playwright and record it.

    Each step dwells until a CUMULATIVE target rather than for its own narration
    length, so a step that overruns is absorbed by the next one instead of
    pushing the voice out of step for the rest of the film. The first version
    held per-step and recorded 198 seconds of video against 146 of speech.

    THE BROWSER IS HEADED. Two of these steps are a PDF rendered on the page —
    the sales brief and a built pre-sales piece — and headless Chromium draws a
    grey rectangle in place of both. It also SIGNS IN first, because every /api
    path now requires a session.
    """
    from playwright.sync_api import sync_playwright

    DEMO.mkdir(parents=True, exist_ok=True)
    for stale in DEMO.glob("*.webm"):
        stale.unlink()

    pause = [durations[f"demo{i:02d}"] for i in range(len(DEMO_SCRIPT))]
    targets, running = [], 0.0
    for d in pause:
        running += d
        targets.append(running)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False,
                                    args=["--force-device-scale-factor=1",
                                          f"--window-size={W},{H + 120}"])

        # Sign in on a throwaway context, so the recording does not open on a
        # login form.
        auth = browser.new_context(viewport={"width": W, "height": H})
        auth_page = auth.new_page()
        auth_page.goto(BASE, wait_until="networkidle")
        auth_page.wait_for_timeout(1500)
        if auth_page.locator("input[autocomplete='username']").count():
            auth_page.fill("input[autocomplete='username']", USER)
            auth_page.fill("input[autocomplete='current-password']", PASSWORD)
            auth_page.click("button.login-submit")
            auth_page.wait_for_timeout(3000)
        state = WORK / "session.json"
        auth.storage_state(path=str(state))
        auth.close()

        ctx = browser.new_context(
            viewport={"width": W, "height": H},
            storage_state=str(state),
            record_video_dir=str(DEMO),
            record_video_size={"width": W, "height": H},
        )
        page = ctx.new_page()
        started = time.monotonic()

        def hold(step: int):
            """Wait until this step's narration would have finished."""
            remaining = targets[step] - (time.monotonic() - started)
            if remaining > 0:
                page.wait_for_timeout(int(remaining * 1000))
            else:
                print(f"  demo: step {step} ({DEMO_SCRIPT[step][1]}) ran "
                      f"{abs(remaining):.1f}s over its narration")

        def safe(fn, what: str):
            try:
                fn()
            except Exception as exc:  # noqa: BLE001 — one control must not end the demo
                print(f"  demo: skipped {what}: {str(exc).splitlines()[0][:90]}")

        def goto(url: str, settle: int = 2600):
            page.goto(f"{BASE}{url}", wait_until="networkidle")
            page.wait_for_timeout(settle)

        # The header has both a view switcher and a skip-navigation landmark
        # that repeat the same words, so every control is scoped to its group.
        def tab(name: str):
            safe(lambda: page.get_by_label("View").get_by_role(
                "button", name=name, exact=False).first.click(), f"tab {name}")
            page.wait_for_timeout(600)

        def role_mode(name: str):
            safe(lambda: page.get_by_label("Role mode").get_by_role(
                "button", name=name).first.click(), f"role {name}")
            page.wait_for_timeout(600)

        def scroll(selector: str | None, dy: int, steps: int = 12, pause_ms: int = 90):
            """Scroll the way a person does — in increments, over the right pane.

            One large wheel event teleports the content and the viewer loses
            their place. And the wheel goes to whatever is under the cursor, so
            a pane that scrolls internally needs the mouse parked over it first.
            """
            if selector:
                try:
                    box = page.locator(selector).first.bounding_box()
                    if box:
                        page.mouse.move(box["x"] + box["width"] / 2,
                                        box["y"] + min(box["height"] / 2, H / 2))
                except Exception:  # noqa: BLE001
                    pass
            per = dy // max(steps, 1)
            for _ in range(steps):
                page.mouse.wheel(0, per)
                page.wait_for_timeout(pause_ms)

        # 0-1  the radar
        goto("/?tab=radar", settle=3000)
        hold(0)
        safe(lambda: page.locator("circle.dot").nth(6).hover(), "hover marker")
        page.wait_for_timeout(1200)
        hold(1)

        # 2  role modes, and the instruction line above the chart
        role_mode("Sales")
        page.wait_for_timeout(1800)
        hold(2)

        # 3  the list
        role_mode("Strategist")
        tab("List")
        page.wait_for_timeout(1600)
        hold(3)

        # 4-5  one topic, scrolled
        goto(f"/?tab=list&topic={TOPIC}", settle=3000)
        hold(4)
        scroll(".detail-pane", 1500, steps=16)
        hold(5)

        # 6  the score explanation
        safe(lambda: page.get_by_role(
            "button", name="How was this calculated?").first.click(), "open explain")
        page.wait_for_timeout(2000)
        scroll(None, 900, steps=12)
        hold(6)
        page.keyboard.press("Escape")
        page.wait_for_timeout(600)

        # 7-9  full screen: the space, the brief, the pre-sales pack
        goto(f"/?topic={TOPIC}&view=full", settle=3400)
        scroll(".fs-body", 800, steps=10)
        hold(7)
        tab("Sales brief")
        page.wait_for_timeout(4500)          # the PDF viewer needs a moment
        scroll(".fs-body", 600, steps=8)
        hold(8)
        tab("Pre-sales")
        page.wait_for_timeout(2600)
        scroll(".fs-body", 1600, steps=18)
        hold(9)

        # 10  the workflow board
        goto("/?tab=workflow", settle=3000)
        scroll(None, 700, steps=10)
        hold(10)

        # 11  analytics
        goto("/?tab=analytics", settle=4000)
        scroll(None, 1400, steps=16)
        hold(11)

        # 12  the scoping conversation
        goto("/?screen=generate", settle=3400)
        safe(lambda: page.get_by_role("tab", name="Describe a space").click(), "chat tab")
        page.wait_for_timeout(3000)
        scroll(None, 900, steps=12)
        hold(12)

        # 13  the Planner, both sources
        goto("/?view=planner", settle=3200)
        safe(lambda: page.locator("button.pl-run").first.click(), "build plan")
        page.wait_for_timeout(6000)
        scroll(".pl-main", 1200, steps=14)
        safe(lambda: page.get_by_label("Where the portfolio comes from").get_by_role(
            "button", name="Workflow selected").click(), "workflow source")
        page.wait_for_timeout(1800)
        hold(13)

        # 14  contextual help
        goto("/?tab=radar", settle=2200)
        safe(lambda: page.locator('button[aria-label^="Help:"]').nth(1).click(), "open help")
        page.wait_for_timeout(1500)
        hold(14)

        ctx.close()
        browser.close()

    videos = list(DEMO.glob("*.webm"))
    if not videos:
        raise RuntimeError("Playwright produced no recording")
    print(f"recorded demo: {videos[0].name} ({duration(videos[0]):.1f}s)")
    return videos[0]


def build_demo_segment(video: Path, durations: dict[str, float], out: Path) -> None:
    """Mux the recording with its concatenated narration."""
    listing = WORK / "demo_audio.txt"
    listing.write_text("\n".join(
        f"file '{AUDIO / f'demo{i:02d}.mp3'}'" for i in range(len(DEMO_SCRIPT))))
    demo_audio = WORK / "demo_audio.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(listing), "-c", "copy", str(demo_audio)], check=True)

    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(video), "-i", str(demo_audio),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
               f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=white,fps=30",
        "-c:a", "aac", "-b:a", "160k", "-shortest",
        str(out),
    ], check=True)


def render_slides() -> None:
    """Rasterise the deck. The film's stills ARE the deck's slides, so the two
    cannot drift apart — which is the whole reason the deck is a script."""
    SLIDES.mkdir(parents=True, exist_ok=True)
    if (SLIDES / "slide-01.png").exists():
        print(f"slides already rendered in {SLIDES}")
        return
    if not DECK.exists():
        raise SystemExit(f"{DECK} is missing — run docs/build_deck.py first.")
    subprocess.run(["soffice", "--headless", "--convert-to", "pdf",
                    "--outdir", str(WORK), str(DECK)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["pdftoppm", "-png", "-r", "150",
                    str(WORK / f"{DECK.stem}.pdf"), str(SLIDES / "slide")], check=True)
    for path in sorted(SLIDES.glob("slide-*.png")):
        num = int(path.stem.split("-")[-1])
        want = SLIDES / f"slide-{num:02d}.png"
        if path != want:
            path.rename(want)
    print(f"rendered {len(list(SLIDES.glob('slide-*.png')))} slides")


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    render_slides()

    SEG.mkdir(parents=True, exist_ok=True)
    for stale in SEG.glob("*.mp4"):
        stale.unlink()

    durations = asyncio.run(build_narration())

    segments: list[Path] = []
    for num, _ in SLIDE_SCRIPT:
        out = SEG / f"a{num:02d}.mp4"
        slide_segment(num, AUDIO / f"slide{num:02d}.mp3", out)
        segments.append(out)
        print("slide segment", num)

    demo_video = record_demo(durations)
    demo_seg = SEG / "demo.mp4"
    build_demo_segment(demo_video, durations, demo_seg)
    segments.append(demo_seg)
    print("demo segment built")

    for num, _ in CLOSING_SCRIPT:
        out = SEG / f"z{num:02d}.mp4"
        slide_segment(num, AUDIO / f"slide{num:02d}.mp3", out)
        segments.append(out)
        print("slide segment", num)

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
