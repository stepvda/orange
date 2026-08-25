#!/usr/bin/env python3
"""Regenerate every diagram embedded in the design documents.

Matplotlib only — no graphviz, no browser, no manual editing. Each figure is
laid out on a 0..100 canvas so positions are declarative and comparable across
figures, and connectors route through explicit waypoints because auto-routing
overlaps labels.

    python3 docs/build_diagrams.py
"""
from __future__ import annotations

import pathlib
import runpy
import sys

HERE = pathlib.Path(__file__).resolve().parent
BUILD = HERE / "_build"

#: Run order matters only in that later scripts may overwrite earlier drafts of
#: the same figure. Each module writes directly into docs/diagrams/.
SCRIPTS = [
    # Functional Design Document
    "fdd_a1",      # 1  system context
    "fdd_a2",      # 2  capability map
    "fdd_b",       # 3  four quantities
    "fdd_b2",      # 4  portfolio distance and role modes
    "fdd_c",       # 5  lifecycle
    "fdd_c2",      # 6  collaboration
    "fdd_d3",      # 7  evidence funnel and the four defences
    "fdd_d2",      # 8  market sizing
    "fdd_e2",      # 9  screens and role journeys
    "fdd_f2",      # 10 conceptual data model
    # Technical Architecture
    "ta_a1",       # 1  layered architecture
    "ta_a",        # 2  the pipeline
    "ta_b",        # 3  refresh sequence, 4 read sequence
    "ta_c",        # 5  deployment, 6 scoring
    "ta_d",        # 11 model guardrails
    "ta_erd1",     # 7  physical data model, part 1
    "ta_erd2",     # 8, 9, 10 parts 2-4
    # Added with competitor intelligence: FDD 11 and TA 12
    "new_diags",
    # Added with the Planner, pre-sales collateral, scoping and access control:
    "fdd_g",       # FDD 12 planner, 13 pre-sales collateral, 14 generation routes
    "ta_e",        # TA 13 planner internals, 14 collateral build, 15 access + deletion
]


def main() -> int:
    sys.path.insert(0, str(BUILD))
    out = HERE / "diagrams"
    out.mkdir(parents=True, exist_ok=True)
    for name in SCRIPTS:
        path = BUILD / f"{name}.py"
        if not path.exists():
            print(f"  skip {name} (missing)")
            continue
        print(f"  {name}")
        runpy.run_path(str(path), run_name="__main__")
    print(f"\n{len(list(out.glob('*.png')))} diagrams in {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
