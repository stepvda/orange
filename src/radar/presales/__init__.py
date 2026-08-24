"""Pre-sales collateral for one opportunity space (FR-18, extending the brief).

The brief is a leave-behind for a first meeting. This package is what the team
needs BETWEEN that meeting and a proposal: qualification, a solution outline,
battlecards, a business case, a PoC scope, tender blocks, a risk register and a
partner ask — each in the format the person receiving it actually works in.

Twelve pieces, one snapshot. `context.load` reads the space once and every
renderer works from that, so two documents in the same pack cannot quote
different figures for the same quantity.
"""

from .builder import (PreSalesBuilder, collateral_dir, collateral_for_topic, collateral_path,
                      item_for, resolve)
from .catalogue import (CATALOGUE, COLLATERAL_SCHEMA, FORMAT_LABELS, entry,
                        formats_for, media_type_for, resolve_format)

__all__ = [
    "CATALOGUE",
    "COLLATERAL_SCHEMA",
    "FORMAT_LABELS",
    "PreSalesBuilder",
    "collateral_dir",
    "collateral_for_topic",
    "collateral_path",
    "entry",
    "formats_for",
    "item_for",
    "media_type_for",
    "resolve",
    "resolve_format",
]
