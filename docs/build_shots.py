#!/usr/bin/env python3
"""Capture the screenshots both decks put on their slides.

A deck that illustrates a screen with a drawing of that screen is a deck that
drifts. These are the real application, driven by Playwright against the running
instance, so a screen that changed shows as changed the next time this is run.

THE BROWSER IS HEADED, NOT HEADLESS, and that is not a preference. Several of
the screens worth showing are a PDF rendered in an `<object>` — the sales brief,
the plan document, a built battlecard — and headless Chromium renders an empty
grey box in their place. Half the point of the pre-sales and Planner shots is
that the document is actually there.

    python3 docs/build_shots.py            # everything, into /tmp/vid/shots
    python3 docs/build_shots.py radar list # only those

Prerequisites: the API on :8000 and the frontend on :5173.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path("/tmp/vid/shots")
BASE = "http://localhost:5173"

USER, PASSWORD = "orange", "orange"

#: The space every screenshot opens. It is the one with the whole chain built —
#: a description, a PDF brief, sizing by both methods, a scored competitive
#: field, a written competitor comparison and all twelve pre-sales artefacts —
#: so no panel in any shot is an empty state.
TOPIC = "OS004"

# 16:9, and the larger of the two sensible sizes. A slide is 13.33in wide, so a
# 1600px capture is being upscaled on every projector in the room; 1920 is not.
W, H = 1920, 1080


def wait(page, ms: int) -> None:
    page.wait_for_timeout(ms)


def shot(page, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path))
    print(f"  {name:22} {path.stat().st_size // 1024:5} KB")


def safe(fn, what: str) -> bool:
    """Never let one missing control end the capture run."""
    try:
        fn()
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  ! skipped {what}: {str(exc).splitlines()[0][:100]}")
        return False


def main(only: list[str]) -> int:
    from playwright.sync_api import sync_playwright

    want = set(only) if only else None
    take = lambda n: want is None or n in want

    with sync_playwright() as p:
        # headed: an embedded PDF does not render in headless Chromium.
        browser = p.chromium.launch(headless=False, args=["--force-device-scale-factor=1"])
        ctx = browser.new_context(viewport={"width": W, "height": H})
        page = ctx.new_page()

        # -- sign in ------------------------------------------------------
        page.goto(BASE, wait_until="networkidle")
        wait(page, 1200)
        if page.locator("input[autocomplete='username']").count():
            if take("login"):
                shot(page, "login")
            page.fill("input[autocomplete='username']", USER)
            page.fill("input[autocomplete='current-password']", PASSWORD)
            page.click("button.login-submit")
            page.wait_for_timeout(2500)

        def goto(url: str, settle: int = 2600) -> None:
            page.goto(f"{BASE}{url}", wait_until="networkidle")
            wait(page, settle)

        # -- the radar ----------------------------------------------------
        if take("radar"):
            goto("/?tab=radar")
            shot(page, "radar")

        # A marker hovered, so the summary card is on the shot rather than a
        # bare chart nobody can read a topic out of.
        if take("radar_hover"):
            goto("/?tab=radar")
            safe(lambda: page.locator("circle.dot").nth(6).hover(), "hover marker")
            wait(page, 900)
            shot(page, "radar_hover")

        # -- role modes ---------------------------------------------------
        if take("roles"):
            goto("/?tab=list&role=sales")
            safe(lambda: page.get_by_label("Role mode").get_by_role(
                "button", name="Sales").first.hover(), "hover role")
            wait(page, 1100)
            shot(page, "roles")

        if take("role_help"):
            goto("/?tab=radar")
            safe(lambda: page.locator('button[aria-label^="Help:"]').first.click(), "open role help")
            wait(page, 1400)
            shot(page, "role_help")
            page.keyboard.press("Escape")

        # -- list and detail ----------------------------------------------
        if take("list"):
            goto(f"/?tab=list&topic={TOPIC}")
            shot(page, "list")

        if take("detail"):
            goto(f"/?tab=detail&topic={TOPIC}")
            shot(page, "detail")

        # The score breakdown is the part worth showing and it is below the
        # fold, so it gets its own frame rather than being cropped out.
        if take("detail_scores"):
            goto(f"/?tab=detail&topic={TOPIC}")
            safe(lambda: page.locator(".detail-pane").locator(
                "text=How was this calculated?").first.scroll_into_view_if_needed(),
                "scroll to scores")
            wait(page, 1200)
            shot(page, "detail_scores")

        if take("explain"):
            goto(f"/?tab=detail&topic={TOPIC}")
            safe(lambda: page.get_by_role(
                "button", name="How was this calculated?").first.click(), "open explain")
            wait(page, 1600)
            shot(page, "explain")
            page.keyboard.press("Escape")

        # -- full screen, all four panes ----------------------------------
        pane_shots = [
            ("fs_space", "Opportunity space", 2600),
            ("fs_competitors", "Competitors", 3200),
            ("fs_brief", "Sales brief", 4200),        # a PDF: needs the headed browser
            ("fs_presales", "Pre-sales", 3000),
        ]
        if any(take(n) for n, _, _ in pane_shots):
            goto(f"/?topic={TOPIC}&view=full", settle=3200)
            for name, label, settle in pane_shots:
                if not take(name):
                    continue
                safe(lambda l=label: page.get_by_label("View").get_by_role(
                    "button", name=l, exact=False).first.click(), f"pane {label}")
                wait(page, settle)
                shot(page, name)

        # The twelve pieces do not fit on one screen; the second half is where
        # the tender blocks and the risk register live.
        if take("fs_presales_lower"):
            goto(f"/?topic={TOPIC}&view=full", settle=3200)
            safe(lambda: page.get_by_label("View").get_by_role(
                "button", name="Pre-sales", exact=False).first.click(), "pane Pre-sales")
            wait(page, 3000)
            safe(lambda: page.mouse.wheel(0, 2200), "scroll presales")
            wait(page, 1400)
            shot(page, "fs_presales_lower")

        # -- workflow and analytics ---------------------------------------
        if take("workflow"):
            goto("/?tab=workflow")
            shot(page, "workflow")

        if take("analytics"):
            goto("/?tab=analytics", settle=3600)
            shot(page, "analytics")

        if take("analytics_lower"):
            goto("/?tab=analytics", settle=3600)
            safe(lambda: page.mouse.wheel(0, 1600), "scroll analytics")
            wait(page, 1600)
            shot(page, "analytics_lower")

        if take("coverage"):
            goto("/?tab=coverage", settle=3000)
            shot(page, "coverage")

        if take("whitespace"):
            goto("/?tab=whitespace", settle=2800)
            shot(page, "whitespace")

        # -- generation, both routes --------------------------------------
        if take("generate_grid"):
            goto("/?screen=generate", settle=3200)
            safe(lambda: page.get_by_role("tab", name="Cover more of the grid").click(), "grid tab")
            wait(page, 2200)
            shot(page, "generate_grid")

        if take("generate_chat"):
            goto("/?screen=generate", settle=3200)
            safe(lambda: page.get_by_role("tab", name="Describe a space").click(), "chat tab")
            wait(page, 3000)
            shot(page, "generate_chat")

        # -- the Planner ---------------------------------------------------
        # The form's defaults reproduce plans that are already stored, and a
        # plan id is a fingerprint of its inputs — so pressing the button
        # returns the stored plan immediately rather than spending anything.
        planner_tabs = [("overview", "Overview", 2600), ("spaces", "Spaces", 2600),
                        ("narrative", "Business plan", 2600),
                        ("assumptions", "Assumptions", 2200),
                        ("document", "Document", 6000)]   # the last one is a PDF

        def planner_run(prefix: str, workflow: bool) -> None:
            goto("/?view=planner", settle=3000)
            if workflow:
                safe(lambda: page.get_by_label("Where the portfolio comes from").get_by_role(
                    "button", name="Workflow selected").click(), "workflow source")
                wait(page, 1500)
            if take(f"{prefix}_form"):
                shot(page, f"{prefix}_form")
            # The two modes label the same button differently: "Build the plan"
            # under parameters, "Generate the business plan" under workflow.
            safe(lambda: page.locator("button.pl-run").first.click(), "run plan")
            page.wait_for_timeout(9000)
            for suffix, label, settle in planner_tabs:
                name = f"{prefix}_{suffix}"
                if not take(name):
                    continue
                safe(lambda l=label: page.get_by_label("View").get_by_role(
                    "button", name=l, exact=False).first.click(), f"plan tab {label}")
                wait(page, settle)
                shot(page, name)

        if any(take(f"planner_{x}") for x in
               ("form", "overview", "spaces", "narrative", "assumptions", "document")):
            planner_run("planner", workflow=False)

        if any(take(f"plannerwf_{x}") for x in
               ("form", "overview", "spaces", "narrative", "assumptions", "document")):
            planner_run("plannerwf", workflow=True)

        # -- help ----------------------------------------------------------
        if take("help"):
            goto("/?tab=radar")
            safe(lambda: page.locator('button[aria-label^="Help:"]').nth(1).click(), "open help")
            wait(page, 1500)
            shot(page, "help")
            page.keyboard.press("Escape")

        ctx.close()
        browser.close()

    print(f"\nshots in {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
