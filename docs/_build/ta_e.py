"""TA figures 13–15 — the Planner solver, the collateral build path, access control.

Same 0..100 canvas convention as every other figure in the set.
"""
import sys, textwrap; sys.path.insert(0, ".")
from dg import *

import pathlib
OUT = str(pathlib.Path(__file__).resolve().parents[1] / "diagrams") + "/"


# ===========================================================================
# Figure 13 — The Planner: what actually runs
# ===========================================================================
c = Canvas(12.4, 7.0)
c.title("Figure 13 — The Planner: a mixed-integer program, a fallback, and arithmetic",
        "One model call in the whole subsystem, and it happens after every number is already fixed.")

c.zone(1.0, 62.0, 98.0, 28.0, "RESOLVE  ·  one pass over the read model, no model call",
       fc=GREY_LL, ec=GREY, ls="-", lw=1.1, fs=8.0)
res = [
    ("opportunity_spaces", "statement, triple,\nhorizon, domains", GREEN),
    ("market_sizes", "SOM base / low / high\nby bottom-up method", GREEN),
    ("scores", "attractiveness,\nright to win", GREEN),
    ("opportunity_links", "portfolio distance\n→ the margin band", BLUE),
    ("workflow_state", "stage — the gate,\nwhen source=workflow", PURPLE),
    ("graph_nodes", "capability pools\nand their headcount", BLUE),
    ("economics.yaml", "margin, ramp, capacity,\noverlap, discount rate", ORANGE_D),
]
x = 2.4
for name, sub, col in res:
    c.box(x, 65.0, 13.2, 15.0, "", None, fc="#FFFFFF", ec=col, lw=1.1)
    c.text(x + 6.6, 77.0, name, fs=6.9, color=col, weight="bold", ha="center")
    c.text(x + 6.6, 72.6, sub, fs=6.2, color=GREY_D, ha="center", va="top")
    x += 13.8

c.box(1.0, 44.0, 27.0, 13.0, "Candidate[]",
      "one dataclass per admissible space, with\nits legal entry years and the revenue\nvector each would produce",
      fc=ORANGE_L, ec=ORANGE_D, fs=8.6, subfs=6.5)
c.arrow((14.5, 62.0), (14.5, 57.4), color=GREY_D, lw=1.5)

# -- the solver ------------------------------------------------------------
c.zone(32.0, 30.0, 38.0, 27.0, "scipy.optimize.milp  ·  HiGHS", fc=BLUE_L, ec=BLUE,
       ls="-", lw=1.4, fs=8.4, tc=BLUE)
c.text(33.4, 51.6, "VARIABLES   one binary per (space, legal entry year)",
       fs=7.0, color=INK, weight="bold")
c.text(33.4, 48.8, "OBJECTIVE   maximise profit · revenue · NPV · coverage,\n"
                   "                        tilted by any stated preference",
       fs=7.0, color=INK, va="top", weight="bold")
c.text(33.4, 43.4, "CONSTRAINTS", fs=7.0, color=INK, weight="bold")
c.text(33.4, 41.2, "· each space enters at most once\n"
                   "· entry slots per year\n"
                   "· capability pool load, per pool per year — entry effort in the entry\n"
                   "   year plus sustain effort for everything already live\n"
                   "· total budget in person-years\n"
                   "· concentration caps per vertical and technology; horizon mix",
       fs=6.4, color=GREY_D, va="top")
c.arrow((28.0, 50.5), (32.0, 47.0), color=GREY_D, lw=1.5)

c.box(32.0, 18.0, 38.0, 9.0, "Greedy fallback",
      "If scipy is absent or the program is infeasible: rank by objective density and fill,\n"
      "relaxing the soft constraints in a fixed order — and NAME each one it relaxed.",
      fc=GOLD_L, ec=GOLD, fs=8.0, subfs=6.4)
c.arrow((51.0, 30.0), (51.0, 27.4), color=GOLD, lw=1.4)
c.text(52.4, 28.7, "infeasible / no scipy", fs=6.4, color=GOLD)

c.box(74.0, 44.0, 25.0, 13.0, "schedule_workflow()",
      "source = workflow. No objective, no constraint.\nHorizon fixes the earliest year, stage pulls it\nforward, over-subscribed cohorts cascade.",
      fc=GREEN_L, ec=GREEN, fs=8.4, subfs=6.4)
c.path([(24.0, 57.0), (24.0, 59.6), (86.5, 59.6), (86.5, 57.4)], color=GREEN, lw=1.4)
c.text(55.0, 60.8, "the same candidates, when the set is already decided", fs=6.6,
       color=GREEN, ha="center")

# -- downstream ------------------------------------------------------------
c.rule(15.0)
down = [
    ("project()", "overlap discount, margin by distance,\nramp by horizon, NPV at the filed WACC", GREEN),
    ("_flags()", "plausibility against filed segment revenue,\nconcentration, modelled-size confidence", RED),
    ("narrate()", "ONE model call. Prose about the projection,\nunder the numeric guard — no new figures.", PURPLE),
    ("plan_report.py", "six-part PDF via reportlab. No browser,\nso the sovereign option stays open.", ORANGE_D),
]
x = 1.0
for name, sub, col in down:
    c.box(x, 2.0, 23.6, 10.0, "", None, fc="#FFFFFF", ec=col, lw=1.2)
    c.text(x + 1.4, 9.6, name, fs=8.0, color=col, weight="bold")
    c.text(x + 1.4, 7.0, sub, fs=6.4, color=GREY_D, va="top")
    x += 24.6
c.text(1.0, 13.4, "DOWNSTREAM OF THE SET — identical whichever source produced it. "
                  "The plan id is a SHA-256 of the inputs, the config versions and the plan schema, so the same "
                  "request returns the same plan rather than a second copy of it.",
       fs=7.0, color=GREY_D)
c.save(OUT + "ta-13-planner.png")


# ===========================================================================
# Figure 14 — The collateral build path
# ===========================================================================
c = Canvas(12.4, 6.4)
c.title("Figure 14 — Building one piece of pre-sales collateral, in one format",
        "The brief's lifecycle, twelve times: build to a file, record it with the versions that produced it, and age each input separately.")

steps = [
    ("catalogue.py", "resolve kind + format.\nAn unsupported format is a\n400 naming the alternatives,\nnever a silent fallback.", GREY_D, GREY_L),
    ("context.load()", "ONE read of the space:\nsizing, competition,\ndescription, links, scores,\nevidence, graph assets.", GREEN, GREEN_L),
    ("builder.prepare()", "generate the declared inputs\nthat are cheap and\ndeterministic; report the\nrest as a gap.", BLUE, BLUE_L),
    ("research.py", "targeted live queries through\nthe pipeline's own\nconnectors — same session,\nthrottling and robots rules.", TEAL, TEAL_L),
    ("content.py", "ONE model call, given the\nsnapshot and the retrieved\nitems. Numbers may only be\nquoted, never invented.", PURPLE, PURPLE_L),
    ("documents / decks", "describe the piece as BLOCKS —\nheadings, prose, tables,\nchart specs, citations,\nthe missing-input banner.", ORANGE_D, ORANGE_L),
    ("emitters.py", "walk the blocks into the\nchosen format. Charts are\nvector in PDF and native\nshapes in PPTX.", RED, RED_L),
]
W, GAP = 13.0, 0.85
x = 1.0
for name, sub, ec, fc in steps:
    c.box(x, 60.0, W, 22.0, "", None, fc="#FFFFFF", ec=ec, lw=1.3)
    c.ax.add_patch(Rectangle((x, 76.0), W, 6.0, fc=fc, ec="none", zorder=4))
    c.text(x + W / 2, 79.0, name, fs=7.2, color=ec, weight="bold", ha="center", z=6)
    c.text(x + 0.8, 73.8, sub, fs=6.0, color=GREY_D, va="top")
    if x > 1.0:
        c.arrow((x - GAP, 70.0), (x - 0.1, 70.0), color=GREY_D, lw=1.3)
    x += W + GAP
LAST = 1.0 + 6 * (W + GAP) + W / 2          # centre of the emitters box

c.cylinder(38.0, 38.0, 26.0, 14.0, "topic_collateral",
           "key is (space, kind, FORMAT) — asking for Word after the\nPDF gives both, rather than overwriting the first",
           fc=GREEN_L, ec=GREEN, fs=8.4, subfs=6.3)
c.path([(LAST, 60.0), (LAST, 45.0), (64.0, 45.0)], color=GREY_D, lw=1.4)
c.box(1.0, 38.0, 26.0, 14.0, "data/collateral/<space>/",
      "the file on disk, named for the space,\nthe kind and the format", fc=GREY_L, ec=GREY_D,
      fs=8.0, subfs=6.4)
c.arrow((38.0, 45.0), (27.4, 45.0), color=GREY_D, lw=1.4)

c.rule(32.0)
c.text(1.0, 28.6, "WHAT IS RECORDED, AND WHY EACH FIELD EARNS ITS PLACE", fs=8.0, color=INK, weight="bold")
rows = [
    ("collateral_schema", "Which renderer version built it. A piece built before a section existed reads as INCOMPLETE, not merely old — the same distinction the brief draws."),
    ("space / description / sizing / competition stamps", "Staleness is reported PER INPUT. A pack whose battlecard predates this month's competitor register and whose value case was built this morning is the failure this makes visible."),
    ("format + media type", "The row key includes the format, so the tab can show which formats exist and which of them are stale, independently."),
    ("bytes + content hash", "The tab can size a download without opening the file, and the embedded viewer cache-busts when a piece is rebuilt."),
]
y = 24.0
for name, why in rows:
    c.chip(1.0, y - 1.4, 33.0, 4.0, name, fc=ORANGE_L, ec="none", tc=ORANGE_D, fs=6.6)
    c.text(36.0, y + 0.6, "\n".join(textwrap.wrap(why, 140)), fs=6.5, color=GREY_D, va="top")
    y -= 5.6

c.text(1.0, 1.6, "A PIECE WHOSE DECLARED INPUTS ARE MISSING STILL BUILDS, with a banner naming the gap. "
                 "An engineer who asked for a solution outline and got an error has nothing; one who got the outline with "
                 "“built without the written description” across the top has the component map, the portfolio path and a clear instruction.",
       fs=6.9, color=GREY_D)
c.save(OUT + "ta-14-collateral.png")


# ===========================================================================
# Figure 15 — Access control and the deletion cascade
# ===========================================================================
c = Canvas(12.4, 6.6)
c.title("Figure 15 — Who may read it, and what a delete takes with it",
        "Two features that were the same gap: the deployed app answered every request it received, and a wrong result could only be retracted by editing the database by hand.")

# -- left: the session -----------------------------------------------------
c.zone(1.0, 40.0, 47.0, 50.0, "SIGN-IN  ·  src/radar/auth.py", fc=GREY_LL, ec=BLUE,
       ls="-", lw=1.3, fs=8.4, tc=BLUE)
c.box(2.4, 76.0, 20.0, 9.0, "POST /api/auth/login",
      "unknown account and wrong password\nanswer identically, and cost the same time",
      fc="#FFFFFF", ec=BLUE, fs=7.6, subfs=6.0)
c.box(25.4, 76.0, 21.2, 9.0, "users",
      "PBKDF2-HMAC-SHA256 verifier at\nOWASP's iteration count — never a password",
      fc=GREEN_L, ec=GREEN, fs=7.6, subfs=6.0)
c.arrow((22.4, 80.5), (25.4, 80.5), color=GREY_D, lw=1.2)

c.box(2.4, 62.0, 20.0, 11.0, "Set-Cookie",
      "HttpOnly — a script cannot read it\nSameSite=Lax — stands in for a CSRF token\nSecure — follows x-forwarded-proto",
      fc=ORANGE_L, ec=ORANGE_D, fs=7.6, subfs=6.0)
c.box(25.4, 62.0, 21.2, 11.0, "sessions",
      "keyed by the SHA-256 of the cookie value.\nA copy of the database file is neither a set\nof passwords nor a set of live logins.",
      fc=GREEN_L, ec=GREEN, fs=7.6, subfs=6.0)
c.arrow((22.4, 67.5), (25.4, 67.5), color=GREY_D, lw=1.2)
c.arrow((12.4, 76.0), (12.4, 73.4), color=GREY_D, lw=1.2)

c.box(2.4, 48.0, 44.2, 11.0, "The guard is an application-level dependency, not a decorator per route",
      "Every /api path needs a session except the three under /api/auth. The failure mode of a per-route guard is the\n"
      "route somebody forgot — so tests/test_api_auth.py WALKS THE ROUTER rather than naming endpoints, for the same reason.\n"
      "The built bundle and /healthz stay open: the login screen has to load, and a probe that answers 401 looks unhealthy.",
      fc=RED_L, ec=RED, fs=7.6, subfs=6.0)

c.text(2.4, 44.6, "Idle window refreshes on use; a ceiling it cannot outlive. An empty user table seeds orange/orange,\n"
                  "flagged must_change_password — and the interface says so on every screen until it is cleared.",
       fs=6.3, color=GREY_D, va="top")

# -- right: the delete -----------------------------------------------------
c.zone(52.0, 40.0, 47.0, 50.0, "DELETING A SPACE  ·  src/radar/deletion.py", fc=GREY_LL,
       ec=PURPLE, ls="-", lw=1.3, fs=8.4, tc=PURPLE)
c.box(53.4, 76.0, 20.0, 9.0, "GET …/deletion-impact",
      "asked BEFORE the button is shown.\nThe dialog reads the impact out first.",
      fc="#FFFFFF", ec=PURPLE, fs=7.6, subfs=6.0)
c.box(76.4, 76.0, 21.2, 9.0, "DELETE /api/topics/{id}",
      "thirteen tables cascade;\nthe result names what went",
      fc="#FFFFFF", ec=PURPLE, fs=7.6, subfs=6.0)
c.arrow((73.4, 80.5), (76.4, 80.5), color=GREY_D, lw=1.2)

goes = [("Evidence attachments", RED), ("Both score trajectories", RED),
        ("Confirmed asset links", RED), ("Stage history + assessments", RED),
        ("Market size + competition", RED), ("Description, brief PDF, collateral", RED),
        ("Duplicates folded in here", RED)]
stays = [("Signals themselves", GREEN), ("Plans that selected it", GOLD)]
c.text(53.4, 71.8, "GOES WITH IT", fs=7.2, color=RED, weight="bold")
y = 68.8
for name, col in goes:
    c.chip(53.4, y - 1.3, 21.0, 3.4, name, fc=RED_L, ec="none", tc=RED, fs=6.1)
    y -= 4.0
c.text(76.4, 71.8, "DOES NOT", fs=7.2, color=GREEN, weight="bold")
y = 68.8
for name, col in stays:
    c.chip(76.4, y - 1.3, 21.2, 3.4, name, fc=GREEN_L if col is GREEN else GOLD_L,
           ec="none", tc=col, fs=6.1)
    y -= 4.0
c.text(76.4, 60.0, "A signal is evidence about the world that\n"
                   "several spaces may cite, collected under\n"
                   "DR-01 and kept for replay under DR-14.\n\n"
                   "A plan's stored projection was computed\n"
                   "once and is immutable by design, so the\n"
                   "plans are NAMED rather than blocked —\n"
                   "refusing would make any space that ever\n"
                   "appeared in a plan permanent.",
       fs=6.2, color=GREY_D, va="top")

c.rule(36.0)
c.text(1.0, 32.6, "THE CAVEAT THIS MODULE CANNOT FIX, AND THEREFORE STATES LOUDLY", fs=8.0, color=INK, weight="bold")
c.text(1.0, 29.4, "DELETION IS NOT SUPPRESSION. Identity is the vertical × use case × technology triple (DR-03), so a later refresh that meets the same triple in the evidence will\n"
                  "synthesise the space again — with a new id and none of the history removed here. Removing a space is a statement about the corpus as it stands, not a permanent veto.",
       fs=7.0, color=GREY_D, va="top")

c.rule(23.0)
c.text(1.0, 20.4, "THREE DECISIONS THAT COULD REASONABLY HAVE GONE THE OTHER WAY", fs=8.0, color=INK, weight="bold")
dec = [
    ("Sessions in the database, not signed and stateless",
     "A JWT cannot be revoked without server state, which puts the state back anyway — and the thing an operator "
     "actually wants (“sign that account out everywhere, now”) is one DELETE here and impossible there."),
    ("PBKDF2 from the standard library, not argon2",
     "Not the best KDF. The best one available with NO NEW DEPENDENCY — which is what keeps NFR-05's sovereign "
     "deployment option cheap. The iteration count is stamped into every hash, so raising it re-hashes on next sign-in."),
    ("A duplicate folded into this space leaves with it",
     "A merged_into row is a tombstone saying “this triple is that topic”. Clearing the pointer instead would "
     "resurrect duplicates against the identity rule — and the unique index would refuse the second one anyway."),
]
x = 1.0
for name, why, in dec:
    c.box(x, 1.0, 31.6, 17.6, "", None, fc="#FFFFFF", ec=GREY, lw=1.1)
    c.text(x + 1.4, 16.8, "\n".join(textwrap.wrap(name, 42)), fs=7.0, color=INK, weight="bold", va="top")
    c.text(x + 1.4, 12.2, "\n".join(textwrap.wrap(why, 52)), fs=6.3, color=GREY_D, va="top")
    x += 32.6
c.save(OUT + "ta-15-access-deletion.png")

print("  ta-13-planner, ta-14-collateral, ta-15-access-deletion")
