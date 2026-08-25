#!/usr/bin/env python3
"""Rebuild the Functional Design Document and the Technical Architecture.

Both embed the diagrams from docs/diagrams/, so run build_diagrams.py first if
they have changed. The narrative is hand-written in docs/_build/*_content.py —
this only assembles it.

    python3 docs/generators/build_diagrams.py     # first, if figures changed
    python3 docs/generators/build_docs.py
"""
from __future__ import annotations

import pathlib
import runpy
import sys

DOCS = pathlib.Path(__file__).resolve().parent.parent
BUILD = DOCS / "_build"

DOCUMENTS = [
    ("Functional Design Document", "fdd_content.py"),
    ("Technical Architecture", "ta_content.py"),
    ("Speaker Notes", "notes_content.py"),
]


def main() -> int:
    sys.path.insert(0, str(BUILD))
    missing = [n for n, f in DOCUMENTS if not (BUILD / f).exists()]
    if missing:
        print(f"missing content modules: {', '.join(missing)}", file=sys.stderr)
    for name, filename in DOCUMENTS:
        path = BUILD / filename
        if not path.exists():
            continue
        print(f"  {name}")
        runpy.run_path(str(path), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
