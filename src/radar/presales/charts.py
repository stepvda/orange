"""The drawn vocabulary the pre-sales collateral is built from.

Every picture in this package is drawn here, with exact geometry, for the reason
`brief.SolutionDiagram` and `plan_report.BarChart` are: a chart whose bars are
positioned by arithmetic is legible every time, and one handed to a layout engine
is legible until the data changes. There is no browser in the pipeline and none
is wanted (NFR-05).

WHY THE COLOUR IS NOT HAND-PICKED. Collateral goes to customers, so the palette
had to be decided once and checked rather than chosen per chart. Each colour here
does exactly one job — identity, order, magnitude, polarity or state — and the
categorical and ordinal sets were run through a contrast/colour-vision validator
rather than eyeballed:

  ORDINAL_ORANGE   funnel stages, phase timelines. One hue, monotone lightness,
                   light end still 2.4:1 on the page. Order is visible IN the
                   colour, because swapping two funnel stages would be a lie.
  CATEGORICAL      up to four series that are merely different, safe under
                   protanopia and deuteranopia at every pair, not just adjacent
                   ones — these get used in scatter forms where any two marks
                   can end up side by side. Slot 0 is Orange's own.
  DIVERGING        a warm pole and a cool pole around a neutral grey, for
                   quantities with a sign: money in, money out.
  PROVIDER_STYLE   imported from `brief`, unchanged. Who owns a component is
                   the same question on a battlecard as in the brief, and a
                   reader should not have to learn it twice.
  status           imported from `brief.COMPETITION_COLOUR`. Reserved for state,
                   never spent on a series.

THE ONE BRAND RULE, which is `brief`'s and is kept: Orange means Orange, or it
means emphasis. It is never slot four of a competitor palette. That is why the
field map paints every competitor in one neutral blue and names them instead —
identity there comes from the label, and the only orange mark on the chart is
where Orange stands.
"""

from __future__ import annotations

import math
import unicodedata
from typing import Any, Sequence

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Flowable

from ..brief import (COMPETITION_COLOUR, INK, MUTED, ORANGE, ORANGE_DARK, PROVIDER_LABEL,
                     PROVIDER_STYLE, RULE, SURFACE, _wrap)

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------

#: Ordered stages: funnels, phase timelines, tiers. One hue, light -> dark, so
#: the sequence is readable without the legend. Validated: monotone lightness,
#: every adjacent step >= 0.06 apart, light end 2.44:1 against the page.
ORDINAL_ORANGE = [
    colors.HexColor("#F08A2E"),
    colors.HexColor("#DE6A05"),
    colors.HexColor("#B85200"),
    colors.HexColor("#8A3800"),
]

#: Series that are merely different. Four slots, fixed order, never cycled — a
#: fifth series folds into "other" or the chart becomes small multiples. Slot 0
#: is Orange's own, so a chart comparing Orange against others needs no separate
#: rule. Validated all-pairs (not just adjacent) because these appear in scatter
#: forms: worst colour-vision pair dE 10.3, worst normal-vision pair dE 16.3.
#: The teal sits at 2.7:1 rather than 3:1, which is legal only because every
#: mark that uses it is directly labelled — see `_label_outside`.
CATEGORICAL = [
    colors.HexColor("#D9600A"),   # Orange
    colors.HexColor("#2a78d6"),   # blue
    colors.HexColor("#1baf7a"),   # teal
    colors.HexColor("#4a3aa7"),   # indigo
]

#: Quantities with a sign. Warm against cool, which is what makes the two poles
#: read as opposites, and a neutral grey in the middle so zero reads as nothing.
#: Never two cool hues: blue against teal looks like a gradient, not a sign.
GAIN = colors.HexColor("#D9600A")
COST = colors.HexColor("#2a78d6")
NEUTRAL = colors.HexColor("#9A9A9A")

#: State, never identity. Borrowed from the brief so "crowded field" is the same
#: red in a battlecard as in the PDF the same person read yesterday.
STATUS = {
    "low": COMPETITION_COLOUR["low"],
    "medium": COMPETITION_COLOUR["medium"],
    "high": COMPETITION_COLOUR["high"],
    "none": COMPETITION_COLOUR["none"],
}

#: 2pt at PDF scale. Touching fills are separated by a gap in the page colour
#: rather than by a stroke around each one: a border is ink that is not data.
GAP = 0.7 * mm
#: 4px at PDF scale — the rounding on the growing end of a bar.
RADIUS = 1.4 * mm

#: How far a scatter's usable range is held off its own border. Positions here
#: are judgements on a three-point band, so 0.0 and 1.0 are the common cases
#: rather than the extremes — without this the most interesting marks on the
#: chart are the ones half outside it.
INSET = 0.09


# ---------------------------------------------------------------------------
# Shared drawing helpers
# ---------------------------------------------------------------------------

def _luminance(colour: colors.Color) -> float:
    return 0.2126 * colour.red + 0.7152 * colour.green + 0.0722 * colour.blue


def ink_on(fill: colors.Color) -> colors.Color:
    """Text colour for a label sitting INSIDE a coloured fill.

    The one place a label is allowed to leave the text tokens: on top of a
    stacked segment or a matrix cell there is no page colour behind it, so the
    label has to flip with the fill or it fails contrast on one end of the ramp.
    """
    return colors.white if _luminance(fill) < 0.55 else INK


def _fits(canvas: Any, text: str, font: str, size: float, width: float) -> bool:
    """Whether `text` fits in `width` with padding on both sides.

    Called before every in-mark label. A label that does not fit is moved
    outside the mark or dropped to the table — never clipped, because clipping
    eats the first or last characters and is worse than no label at all.
    """
    return canvas.stringWidth(text, font, size) <= width - 3 * mm


def _label_outside(canvas: Any, x: float, y: float, text: str,
                   size: float = 6.4, colour: colors.Color = INK,
                   bold: bool = True) -> None:
    canvas.setFillColor(colour)
    canvas.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    canvas.drawString(x, y, text)


def _grid(canvas: Any, x: float, y: float, width: float) -> None:
    """One hairline, solid, one step off the page. Never dashed: a dashed rule
    reads as a threshold or a projection, and this is neither."""
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.4)
    canvas.line(x, y, x + width, y)


def _rounded_bar(canvas: Any, x: float, y: float, width: float, height: float,
                 fill: colors.Color, horizontal: bool = False) -> None:
    """A bar rounded on the growing end only, square at the baseline.

    reportlab has no per-corner radius, so the shape is a roundRect with the
    baseline end squared off by a plain rect drawn over it. Below twice the
    radius the rounding is skipped entirely — a short bar drawn as a lozenge
    misreports its own length.
    """
    canvas.setFillColor(fill)
    canvas.setStrokeColor(fill)
    canvas.setLineWidth(0)
    extent = width if horizontal else height
    if extent <= 0:
        return
    if extent < 2 * RADIUS:
        canvas.rect(x, y, width, height, stroke=0, fill=1)
        return
    canvas.roundRect(x, y, width, height, RADIUS, stroke=0, fill=1)
    if horizontal:
        canvas.rect(x, y, RADIUS, height, stroke=0, fill=1)
    else:
        canvas.rect(x, y, width, RADIUS, stroke=0, fill=1)


def _legend(canvas: Any, x: float, y: float,
            entries: Sequence[tuple[str, colors.Color]], size: float = 6.2) -> None:
    """Always drawn for two or more series, never for one.

    One series needs no legend: there is a single colour on the chart and the
    caption above it already says what is plotted. A box with one swatch in it
    restates the title and costs a line of page.
    """
    if len(entries) < 2:
        return
    cursor = x
    for label, colour in entries:
        canvas.setFillColor(colour)
        canvas.rect(cursor, y, 3 * mm, 2.4 * mm, stroke=0, fill=1)
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", size)
        canvas.drawString(cursor + 4 * mm, y + 0.3 * mm, label)
        cursor += 4 * mm + canvas.stringWidth(label, "Helvetica", size) + 7 * mm


def _centred_lines(canvas: Any, x: float, y: float, lines: Sequence[str],
                   size: float, leading: float) -> None:
    start = y + (len(lines) - 1) * leading / 2
    for index, line in enumerate(lines):
        canvas.drawCentredString(x, start - index * leading, line)


# ---------------------------------------------------------------------------
# Money and market
# ---------------------------------------------------------------------------

class FunnelChart(Flowable):
    """TAM -> SAM -> SOM as nested horizontal bars on a shared baseline.

    A funnel, not a pie and not three separate bars: the three figures are
    NESTED — SOM is inside SAM is inside TAM — and the only chart that says so
    is one where each bar's length is drawn to the same scale from the same
    left edge. Three unrelated bars would let a reader read them as additive.

    Stages are ordered, so the colour is the ordinal ramp rather than three
    identities: the reader sees the narrowing in the darkening.
    """

    def __init__(self, stages: Sequence[tuple[str, float | None, str]], width: float,
                 height: float = 34 * mm):
        super().__init__()
        # (label, value, note) — note carries the range or the confidence.
        self.stages = [s for s in stages if s[1] is not None]
        self.width, self.height = width, height

    def draw(self) -> None:
        canvas = self.canv
        if not self.stages:
            canvas.setFillColor(MUTED)
            canvas.setFont("Helvetica-Oblique", 7)
            canvas.drawString(0, self.height / 2, "Not sized — run the sizing stage for this space.")
            return

        top = max((value for _, value, _ in self.stages), default=1.0) or 1.0
        label_column = 20 * mm
        note_column = 30 * mm
        usable = self.width - label_column - note_column
        rows = len(self.stages)
        slot = self.height / rows
        bar_height = min(11 * mm, slot - GAP * 2)

        for index, (label, value, note) in enumerate(self.stages):
            y = self.height - (index + 1) * slot + (slot - bar_height) / 2
            fill = ORDINAL_ORANGE[min(index, len(ORDINAL_ORANGE) - 1)]
            bar_width = max(usable * (float(value) / top), 0.8 * mm)
            _rounded_bar(canvas, label_column, y, bar_width, bar_height, fill, horizontal=True)

            canvas.setFillColor(MUTED)
            canvas.setFont("Helvetica-Bold", 7)
            canvas.drawString(0, y + bar_height / 2 - 2.2, safe(label).upper())

            # The value rides the bar when it fits and steps outside when it
            # does not, so a small SOM is still labelled.
            money = _money(value)
            if _fits(canvas, money, "Helvetica-Bold", 7.4, bar_width):
                canvas.setFillColor(ink_on(fill))
                canvas.setFont("Helvetica-Bold", 7.4)
                canvas.drawString(label_column + 2 * mm, y + bar_height / 2 - 2.4, money)
            else:
                _label_outside(canvas, label_column + bar_width + 1.6 * mm,
                               y + bar_height / 2 - 2.4, money, 7.4)

            canvas.setFillColor(MUTED)
            canvas.setFont("Helvetica", 6.2)
            canvas.drawRightString(self.width, y + bar_height / 2 - 2, safe(note))


class WaterfallChart(Flowable):
    """How a number is built, one signed step at a time.

    The form exists for one question a business case always gets asked — "where
    does that figure come from" — and it answers it structurally: each bar
    starts where the last one ended, so the arithmetic is the picture. Gains and
    costs take the two poles of the diverging pair; subtotals sit on the
    baseline in neutral grey, because a subtotal has no sign.
    """

    def __init__(self, steps: Sequence[tuple[str, float, str]], width: float,
                 height: float = 52 * mm):
        super().__init__()
        # (label, delta, kind) where kind is gain | cost | total
        self.steps = list(steps)
        self.width, self.height = width, height

    def _running(self) -> list[tuple[float, float, colors.Color, str, float]]:
        """(bottom, top, colour, label, value) per step, in value units."""
        out: list[tuple[float, float, colors.Color, str, float]] = []
        cursor = 0.0
        for label, delta, kind in self.steps:
            if kind == "total":
                out.append((0.0, cursor, NEUTRAL, label, cursor))
                continue
            nxt = cursor + delta
            colour = GAIN if delta >= 0 else COST
            out.append((min(cursor, nxt), max(cursor, nxt), colour, label, delta))
            cursor = nxt
        return out

    def draw(self) -> None:
        canvas = self.canv
        bars = self._running()
        if not bars:
            return
        top = max((b[1] for b in bars), default=1.0) or 1.0
        pad_bottom, pad_top = 12 * mm, 7 * mm
        plot_height = self.height - pad_bottom - pad_top
        slot = self.width / len(bars)
        bar_width = min(14 * mm, slot - GAP * 2)

        for frac in (0, 0.5, 1.0):
            _grid(canvas, 0, pad_bottom + plot_height * frac, self.width)

        previous_top: float | None = None
        for index, (low, high, colour, label, value) in enumerate(bars):
            x = index * slot + (slot - bar_width) / 2
            y0 = pad_bottom + plot_height * (low / top)
            y1 = pad_bottom + plot_height * (high / top)
            # A connector from the last bar's landing point, so the eye follows
            # the running total rather than re-reading the axis each step.
            if previous_top is not None:
                canvas.setStrokeColor(RULE)
                canvas.setLineWidth(0.4)
                canvas.line(x - (slot - bar_width) / 2 + GAP, previous_top, x - GAP, previous_top)
            _rounded_bar(canvas, x, y0, bar_width, max(y1 - y0, 0.6 * mm), colour)
            previous_top = y1 if colour is not COST else y0 if low == 0 else y1

            canvas.setFillColor(INK)
            canvas.setFont("Helvetica-Bold", 6.2)
            canvas.drawCentredString(x + bar_width / 2, y1 + 1.4 * mm, _money(abs(value)))

            canvas.setFillColor(MUTED)
            canvas.setFont("Helvetica", 5.8)
            _centred_lines(canvas, x + bar_width / 2, 4.6 * mm,
                           _wrap(safe(label), max(10, int(bar_width / 1.5)))[:2], 5.8, 5.4)

        _legend(canvas, 0, self.height - 4 * mm,
                [("value created", GAIN), ("cost to serve", COST), ("net", NEUTRAL)])


class PaybackCurve(Flowable):
    """Cumulative position over time, with the crossing called out.

    One series, so no legend box — the caption names it. Everything on this
    chart exists to locate a single moment: where the line crosses zero. The
    zero rule is the only emphasised gridline, the crossing carries the only
    marker, and the only direct label is the month it happens.
    """

    def __init__(self, cumulative: Sequence[float], period_label: str, width: float,
                 height: float = 44 * mm):
        super().__init__()
        self.values = list(cumulative)
        self.period_label = period_label
        self.width, self.height = width, height

    def draw(self) -> None:
        canvas = self.canv
        values = self.values
        if len(values) < 2:
            return
        low, high = min(min(values), 0.0), max(max(values), 0.0)
        span = (high - low) or 1.0
        pad_left, pad_bottom, pad_top = 18 * mm, 9 * mm, 6 * mm
        plot_w = self.width - pad_left - 6 * mm
        plot_h = self.height - pad_bottom - pad_top

        def point(index: int) -> tuple[float, float]:
            x = pad_left + plot_w * (index / (len(values) - 1))
            y = pad_bottom + plot_h * ((values[index] - low) / span)
            return x, y

        zero_y = pad_bottom + plot_h * ((0.0 - low) / span)
        _grid(canvas, pad_left, pad_bottom + plot_h, plot_w)
        canvas.setStrokeColor(MUTED)
        canvas.setLineWidth(0.6)
        canvas.line(pad_left, zero_y, pad_left + plot_w, zero_y)
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 5.8)
        canvas.drawRightString(pad_left - 1.6 * mm, zero_y - 1.4, "break even")
        canvas.drawRightString(pad_left - 1.6 * mm, pad_bottom + plot_h - 1.4, _money(high))

        canvas.setStrokeColor(ORANGE)
        canvas.setLineWidth(2)
        canvas.setLineJoin(1)
        canvas.setLineCap(1)
        path = canvas.beginPath()
        path.moveTo(*point(0))
        for index in range(1, len(values)):
            path.lineTo(*point(index))
        canvas.drawPath(path, stroke=1, fill=0)

        crossing = next((i for i in range(1, len(values))
                         if values[i - 1] < 0 <= values[i]), None)
        if crossing is not None:
            x, y = point(crossing)
            # A ring in the page colour, not a stroke: it keeps the marker
            # legible where it sits on top of the line it belongs to.
            canvas.setFillColor(colors.white)
            canvas.circle(x, y, 2.6 * mm / 2 + 0.7 * mm, stroke=0, fill=1)
            canvas.setFillColor(ORANGE_DARK)
            canvas.circle(x, y, 1.6 * mm, stroke=0, fill=1)
            _label_outside(canvas, x + 2.6 * mm, y + 1.2 * mm,
                           f"{self.period_label} {crossing}", 6.6, ORANGE_DARK)

        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 5.8)
        for index in (0, len(values) - 1):
            x, _ = point(index)
            canvas.drawCentredString(x, 3.4 * mm, f"{self.period_label} {index}")


# ---------------------------------------------------------------------------
# Competitive
# ---------------------------------------------------------------------------

class FieldMap(Flowable):
    """Where each named competitor stands, and where Orange stands.

    Deliberately NOT coloured by competitor. Identity here comes from the name
    printed beside the dot, which frees the colour channel for the thing that
    actually matters on this chart — whose dot is Orange's. One neutral blue for
    the field, brand orange for us, and the reader's eye goes to the right mark
    without a legend telling it to.

    It also sidesteps a real limit: any two dots on a scatter can end up
    adjacent, so a per-competitor palette would have to separate ALL pairs under
    colour-vision simulation, which caps out at three or four series. Names do
    not cap.
    """

    def __init__(self, entries: Sequence[dict[str, Any]], x_label: str, y_label: str,
                 width: float, height: float = 62 * mm):
        super().__init__()
        # {label, x: 0..1, y: 0..1, is_orange: bool}
        self.entries = list(entries)
        self.x_label, self.y_label = x_label, y_label
        self.width, self.height = width, height

    #: Vertical separation between two marks that landed on the same point.
    DODGE = 4.2 * mm

    def _dodged(self) -> list[tuple[dict[str, Any], float]]:
        """Each entry with a vertical offset that keeps its label readable.

        Positions here are ordinal judgements on a three-point band, so on a
        crowded space several competitors land on EXACTLY the same coordinate —
        eight competitors over nine possible cells guarantees it. Drawn as-is
        their labels print on top of each other and the chart says "TeleVodafone
        Tech", which is worse than useless: it is unreadable AND it looks like a
        rendering fault rather than a crowded market.

        So marks sharing a cell are fanned vertically around it, in a stable
        order. Symmetric rather than downward-only, because a cell at the bottom
        of the plot has no room below it.
        """
        buckets: dict[tuple[float, float], list[dict[str, Any]]] = {}
        for entry in self.entries:
            key = (round(_clamp(entry.get("x", 0.5)), 3), round(_clamp(entry.get("y", 0.5)), 3))
            buckets.setdefault(key, []).append(entry)
        out: list[tuple[dict[str, Any], float]] = []
        for entries in buckets.values():
            span = len(entries) - 1
            for index, entry in enumerate(entries):
                out.append((entry, (index - span / 2) * self.DODGE))
        return out

    def draw(self) -> None:
        canvas = self.canv
        pad_left, pad_bottom = 8 * mm, 10 * mm
        plot_w = self.width - pad_left - 4 * mm
        plot_h = self.height - pad_bottom - 5 * mm

        canvas.setFillColor(SURFACE)
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.4)
        canvas.rect(pad_left, pad_bottom, plot_w, plot_h, stroke=1, fill=1)
        for frac in (0.25, 0.5, 0.75):
            _grid(canvas, pad_left, pad_bottom + plot_h * frac, plot_w)
            canvas.line(pad_left + plot_w * frac, pad_bottom,
                        pad_left + plot_w * frac, pad_bottom + plot_h)

        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica-Bold", 6)
        canvas.drawCentredString(pad_left + plot_w / 2, 3.4 * mm, safe(self.x_label).upper())
        canvas.saveState()
        canvas.rotate(90)
        canvas.drawCentredString(pad_bottom + plot_h / 2, -3.2 * mm, safe(self.y_label).upper())
        canvas.restoreState()

        for entry, dodge in self._dodged():
            # Inset the usable range rather than plotting edge to edge. A value
            # of 1.0 is common and legitimate here — Orange sits at depth 1.0 on
            # every L0 space — and drawn at the literal top of the plot its dot
            # straddles the border and its label leaves the chart entirely.
            x = pad_left + plot_w * (INSET + (1 - 2 * INSET) * _clamp(entry.get("x", 0.5)))
            y = pad_bottom + plot_h * (INSET + (1 - 2 * INSET) * _clamp(entry.get("y", 0.5)))
            y += dodge
            orange = bool(entry.get("is_orange"))
            radius = 2.2 * mm if orange else 1.7 * mm
            canvas.setFillColor(colors.white)
            canvas.circle(x, y, radius + 0.7 * mm, stroke=0, fill=1)
            canvas.setFillColor(ORANGE if orange else CATEGORICAL[1])
            canvas.circle(x, y, radius, stroke=0, fill=1)

            label = _clip(str(entry.get("label", "")), 22)
            canvas.setFont("Helvetica-Bold" if orange else "Helvetica", 6.2)
            text_width = canvas.stringWidth(label, "Helvetica-Bold", 6.2)
            # Flip the label to the left near the right edge so it never runs
            # off the plot.
            if x + radius + 1.4 * mm + text_width > pad_left + plot_w:
                canvas.setFillColor(ORANGE_DARK if orange else INK)
                canvas.drawRightString(x - radius - 1.4 * mm, y - 1.9, label)
            else:
                canvas.setFillColor(ORANGE_DARK if orange else INK)
                canvas.drawString(x + radius + 1.4 * mm, y - 1.9, label)


class StrengthBars(Flowable):
    """Orange against one competitor, dimension by dimension.

    Two series, so a legend is present. Paired rather than stacked, because
    these are two independent readings of the same dimension and stacking would
    imply they sum to something.
    """

    #: Vertical space one dimension occupies: a wrapped label plus a bar pair.
    ROW = 13 * mm
    #: Reserved at the bottom for the legend, which sits BELOW the plot and must
    #: not be written over — the previous constant left the last row's second
    #: bar at a negative y, printing it through the legend swatches.
    LEGEND_BAND = 7 * mm

    def __init__(self, rows: Sequence[tuple[str, float, float]], competitor: str,
                 width: float, height: float | None = None):
        super().__init__()
        # (dimension, orange 0..1, competitor 0..1)
        self.rows = list(rows)
        self.competitor = competitor
        self.width = width
        self.height = (height if height is not None
                       else max(len(self.rows), 1) * self.ROW + self.LEGEND_BAND)

    def draw(self) -> None:
        canvas = self.canv
        if not self.rows:
            return
        label_column = 34 * mm
        usable = self.width - label_column - 4 * mm
        bar_height = 3.4 * mm

        for index, (dimension, ours, theirs) in enumerate(self.rows):
            # Measured DOWN from the top of the flowable in fixed row units, so
            # the last row lands exactly one ROW above the legend band whatever
            # the row count. Dividing the available height by the row count
            # instead is what let a two-row chart overrun its own legend.
            top = self.height - index * self.ROW
            canvas.setFillColor(INK)
            canvas.setFont("Helvetica", 6.6)
            for line_no, line in enumerate(_wrap(safe(dimension), 30)[:2]):
                canvas.drawString(0, top - 4 * mm - line_no * 6.4, line)
            for offset, (value, colour) in enumerate(
                    ((ours, ORANGE), (theirs, CATEGORICAL[1]))):
                y = top - 4.4 * mm - offset * (bar_height + GAP * 2) - bar_height
                _rounded_bar(canvas, label_column, y,
                             max(usable * _clamp(value), 0.6 * mm), bar_height,
                             colour, horizontal=True)

        _legend(canvas, label_column, 1.2 * mm,
                [("Orange", ORANGE), (_clip(self.competitor, 26), CATEGORICAL[1])])


# ---------------------------------------------------------------------------
# Structure and process
# ---------------------------------------------------------------------------

class ComponentMap(Flowable):
    """What the engagement is made of, coloured by who owns each piece.

    The same four-way provider encoding the brief's solution diagram uses, in a
    flat grid rather than in layers, because the question this answers is not
    "how does it fit together" but "how much of it do we actually have". The
    gaps are the point: a `third_party` box is a thing somebody has to source
    before this is sellable, and it is drawn in the same grey every time so the
    reader can count them at a glance.
    """

    def __init__(self, components: Sequence[dict[str, str]], width: float,
                 columns: int = 4):
        super().__init__()
        # {label, provider, note}
        self.components = list(components)
        self.columns = columns
        self.width = width
        self.box_height = 17 * mm
        rows = max(1, math.ceil(len(self.components) / columns))
        self.height = rows * self.box_height + (rows - 1) * GAP * 2 + 8 * mm

    def draw(self) -> None:
        canvas = self.canv
        if not self.components:
            return
        box_width = (self.width - (self.columns - 1) * GAP * 2) / self.columns
        for index, component in enumerate(self.components):
            row, column = divmod(index, self.columns)
            x = column * (box_width + GAP * 2)
            y = self.height - 8 * mm - (row + 1) * self.box_height - row * GAP * 2
            provider = component.get("provider", "third_party")
            fill, text_colour, border = PROVIDER_STYLE.get(provider,
                                                           PROVIDER_STYLE["third_party"])
            canvas.setFillColor(fill)
            canvas.setStrokeColor(border)
            canvas.setLineWidth(0.9)
            canvas.roundRect(x, y, box_width, self.box_height, 2.5, stroke=1, fill=1)

            canvas.setFillColor(text_colour)
            canvas.setFont("Helvetica-Bold", 7)
            per_line = max(8, int((box_width - 4 * mm) / 3.6))
            lines = _wrap(safe(component.get("label", "")), per_line)[:3]
            _centred_lines(canvas, x + box_width / 2, y + self.box_height / 2 + 1.6 * mm,
                           lines, 7, 8.4)
            note = component.get("note")
            if note:
                canvas.setFont("Helvetica", 5.6)
                canvas.drawCentredString(x + box_width / 2, y + 2.4 * mm,
                                         _clip(str(note), per_line + 4))

        _legend(canvas, 0, self.height - 5 * mm,
                [(PROVIDER_LABEL[key], PROVIDER_STYLE[key][0])
                 for key in ("orange", "partner", "customer", "third_party")], 5.8)


class StakeholderMap(Flowable):
    """The buying centre: who signs, who feels it, who can stop it.

    Three columns in the order the deal moves through them, with the economic
    buyer emphasised because that is the one seat a first meeting is usually
    missing. Arrows run left to right along the influence path rather than
    between every pair — a fully connected graph of five roles is a hairball and
    says nothing.
    """

    def __init__(self, people: Sequence[dict[str, str]], width: float):
        super().__init__()
        # {role, name_hint, cares_about, stance}
        self.people = list(people)[:6]
        self.width = width
        self.box_height = 20 * mm
        rows = max(1, math.ceil(len(self.people) / 3))
        self.height = rows * self.box_height + (rows - 1) * 6 * mm + 6 * mm

    def draw(self) -> None:
        canvas = self.canv
        if not self.people:
            return
        columns = 3
        box_width = (self.width - (columns - 1) * 6 * mm) / columns
        for index, person in enumerate(self.people):
            row, column = divmod(index, columns)
            x = column * (box_width + 6 * mm)
            y = self.height - 6 * mm - (row + 1) * self.box_height - row * 6 * mm
            economic = str(person.get("stance", "")).lower() == "economic buyer"
            canvas.setFillColor(colors.HexColor("#FDF1E4") if economic else SURFACE)
            canvas.setStrokeColor(ORANGE if economic else RULE)
            canvas.setLineWidth(1.1 if economic else 0.5)
            canvas.roundRect(x, y, box_width, self.box_height, 3, stroke=1, fill=1)

            canvas.setFillColor(ORANGE_DARK if economic else MUTED)
            canvas.setFont("Helvetica-Bold", 5.8)
            canvas.drawString(x + 2.6 * mm, y + self.box_height - 5 * mm,
                              _clip(str(person.get("stance", "")).upper(), 24))
            canvas.setFillColor(INK)
            canvas.setFont("Helvetica-Bold", 7.6)
            per_line = max(10, int((box_width - 5 * mm) / 3.9))
            for line_no, line in enumerate(_wrap(safe(person.get("role", "")), per_line)[:2]):
                canvas.drawString(x + 2.6 * mm, y + self.box_height - 9.4 * mm - line_no * 8.4, line)
            canvas.setFillColor(MUTED)
            canvas.setFont("Helvetica", 5.8)
            for line_no, line in enumerate(_wrap(safe(person.get("cares_about", "")),
                                                 per_line + 6)[:3]):
                canvas.drawString(x + 2.6 * mm, y + 5.6 * mm - line_no * 6.2, line)

            if column < columns - 1 and index + 1 < len(self.people):
                canvas.setStrokeColor(RULE)
                canvas.setFillColor(RULE)
                canvas.setLineWidth(0.8)
                mid = y + self.box_height / 2
                canvas.line(x + box_width + 1.2 * mm, mid, x + box_width + 4.4 * mm, mid)
                canvas.setStrokeColor(MUTED)
                canvas.setFillColor(MUTED)
                path = canvas.beginPath()
                path.moveTo(x + box_width + 5.2 * mm, mid)
                path.lineTo(x + box_width + 3.4 * mm, mid + 1.1 * mm)
                path.lineTo(x + box_width + 3.4 * mm, mid - 1.1 * mm)
                path.close()
                canvas.drawPath(path, stroke=0, fill=1)


class PhaseTimeline(Flowable):
    """Phases end to end, scaled by duration.

    A Gantt would be the reflex, but a proof of concept has no parallel tracks
    worth drawing — it is a sequence, and a sequence drawn as one bar per row
    wastes the horizontal axis that carries the only quantity here. So: one
    band, segments proportional to duration, separated by a gap in the page
    colour rather than by borders, coloured on the ordinal ramp because the
    order is real.
    """

    def __init__(self, phases: Sequence[tuple[str, int, str]], width: float,
                 height: float = 30 * mm):
        super().__init__()
        # (label, weeks, deliverable)
        self.phases = list(phases)
        self.width, self.height = width, height

    def draw(self) -> None:
        canvas = self.canv
        if not self.phases:
            return
        total = sum(max(weeks, 1) for _, weeks, _ in self.phases)
        band_y = self.height - 14 * mm
        band_height = 9 * mm
        cursor = 0.0
        for index, (label, weeks, deliverable) in enumerate(self.phases):
            span = self.width * (max(weeks, 1) / total)
            fill = ORDINAL_ORANGE[min(index, len(ORDINAL_ORANGE) - 1)]
            canvas.setFillColor(fill)
            canvas.rect(cursor, band_y, max(span - GAP, 1 * mm), band_height, stroke=0, fill=1)

            weeks_text = f"{weeks}w"
            if _fits(canvas, weeks_text, "Helvetica-Bold", 7, span):
                canvas.setFillColor(ink_on(fill))
                canvas.setFont("Helvetica-Bold", 7)
                canvas.drawCentredString(cursor + span / 2, band_y + band_height / 2 - 2.4,
                                         weeks_text)

            canvas.setFillColor(INK)
            canvas.setFont("Helvetica-Bold", 6.4)
            per_line = max(8, int(span / 3.4))
            for line_no, line in enumerate(_wrap(safe(label), per_line)[:2]):
                canvas.drawString(cursor, band_y + band_height + 2.2 * mm + (1 - line_no) * 6.2, line)
            canvas.setFillColor(MUTED)
            canvas.setFont("Helvetica", 5.6)
            for line_no, line in enumerate(_wrap(safe(deliverable), per_line + 6)[:2]):
                canvas.drawString(cursor, band_y - 3.4 * mm - line_no * 6, line)
            cursor += span


class PortfolioPath(Flowable):
    """The hops between what Orange has today and a deliverable configuration.

    This is `portfolio_distance` drawn out. The number on the badge says "L2"
    and nobody can act on that; the picture says which two things are missing
    and who would have to supply them, which is a partner conversation with an
    agenda.
    """

    def __init__(self, hops: Sequence[dict[str, str]], width: float, height: float = 34 * mm):
        super().__init__()
        # {label, provider, note}
        self.hops = list(hops)
        self.width, self.height = width, height

    def draw(self) -> None:
        canvas = self.canv
        if not self.hops:
            return
        count = len(self.hops)
        gap = 9 * mm
        box_width = (self.width - (count - 1) * gap) / count
        box_height = 18 * mm
        y = self.height - box_height - 8 * mm

        for index, hop in enumerate(self.hops):
            x = index * (box_width + gap)
            provider = hop.get("provider", "third_party")
            fill, text_colour, border = PROVIDER_STYLE.get(provider,
                                                           PROVIDER_STYLE["third_party"])
            canvas.setFillColor(fill)
            canvas.setStrokeColor(border)
            canvas.setLineWidth(1.0)
            canvas.roundRect(x, y, box_width, box_height, 3, stroke=1, fill=1)
            canvas.setFillColor(text_colour)
            canvas.setFont("Helvetica-Bold", 7)
            per_line = max(8, int((box_width - 4 * mm) / 3.6))
            _centred_lines(canvas, x + box_width / 2, y + box_height / 2 + 1.4 * mm,
                           _wrap(safe(hop.get("label", "")), per_line)[:3], 7, 8.2)

            canvas.setFillColor(MUTED)
            canvas.setFont("Helvetica", 5.6)
            canvas.drawCentredString(x + box_width / 2, y - 4.4 * mm,
                                     _clip(str(hop.get("note", "")), per_line + 8))

            if index < count - 1:
                mid = y + box_height / 2
                canvas.setStrokeColor(ORANGE)
                canvas.setLineWidth(1.1)
                canvas.line(x + box_width + 1.6 * mm, mid, x + box_width + gap - 3.4 * mm, mid)
                canvas.setFillColor(ORANGE)
                path = canvas.beginPath()
                path.moveTo(x + box_width + gap - 1.6 * mm, mid)
                path.lineTo(x + box_width + gap - 3.8 * mm, mid + 1.3 * mm)
                path.lineTo(x + box_width + gap - 3.8 * mm, mid - 1.3 * mm)
                path.close()
                canvas.drawPath(path, stroke=0, fill=1)

        _legend(canvas, 0, self.height - 4.4 * mm,
                [(PROVIDER_LABEL[key], PROVIDER_STYLE[key][0])
                 for key in ("orange", "partner", "third_party")], 5.8)


class ScopeBoundary(Flowable):
    """The same component set as `ComponentMap`, split by what the PoC covers.

    In-scope keeps the provider colours; out-of-scope drops to an outline on the
    page colour. A scope argument three weeks into a proof of concept is always
    about a box somebody thought was inside the line, so the line is drawn.
    """

    #: Vertical space one entry occupies, including the second wrapped line it
    #: is allowed. Both boxes are drawn to the taller column's height so the
    #: line between them stays a line rather than a step.
    ROW = 9.6 * mm

    def __init__(self, in_scope: Sequence[str], out_scope: Sequence[str], width: float):
        super().__init__()
        self.in_scope = list(in_scope)[:8]
        self.out_scope = list(out_scope)[:8]
        self.width = width
        # Sized to content rather than to a constant. A fixed height means a
        # three-item scope draws two mostly-empty boxes, and empty space inside
        # a drawn boundary reads as "nothing decided yet" rather than as "short
        # list" — the opposite of what this chart is for.
        rows = max(len(self.in_scope), len(self.out_scope), 1)
        self.height = 14 * mm + rows * self.ROW

    def draw(self) -> None:
        canvas = self.canv
        column_width = (self.width - 8 * mm) / 2
        for index, (title, items, inside) in enumerate(
                (("In scope", self.in_scope, True), ("Out of scope", self.out_scope, False))):
            x = index * (column_width + 8 * mm)
            canvas.setStrokeColor(ORANGE if inside else RULE)
            canvas.setLineWidth(1.2 if inside else 0.6)
            canvas.setFillColor(colors.HexColor("#FDF6EF") if inside else colors.white)
            canvas.roundRect(x, 0, column_width, self.height, 3, stroke=1, fill=1)

            canvas.setFillColor(ORANGE_DARK if inside else MUTED)
            canvas.setFont("Helvetica-Bold", 7)
            canvas.drawString(x + 3 * mm, self.height - 6 * mm, title.upper())

            canvas.setFont("Helvetica", 6.8)
            per_line = max(14, int((column_width - 12 * mm) / 3.3))
            # One slot per entry, whether it wrapped or not, so the two columns
            # stay aligned row for row — a reader compares them across the gap.
            for row, item in enumerate(items):
                cursor = self.height - 12 * mm - row * self.ROW
                canvas.setFillColor(ORANGE if inside else RULE)
                canvas.circle(x + 4.4 * mm, cursor + 1.4, 1.1 * mm, stroke=0, fill=1)
                canvas.setFillColor(INK if inside else MUTED)
                for line_no, line in enumerate(_wrap(safe(item), per_line)[:2]):
                    canvas.drawString(x + 7.4 * mm, cursor - line_no * 6.4, line)


class RiskMatrix(Flowable):
    """Likelihood against impact, with the register's entries placed on it.

    Status colour, not a series palette: the cells mean good-to-critical and
    that meaning is reserved everywhere else in this codebase too. Every cell
    also carries its band as a word, because colour alone is not an encoding
    anyone should have to rely on.
    """

    BANDS = ("low", "medium", "high")

    def __init__(self, risks: Sequence[dict[str, Any]], width: float, height: float = 60 * mm):
        super().__init__()
        # {label, likelihood: 0..2, impact: 0..2}
        self.risks = list(risks)
        self.width, self.height = width, height

    def draw(self) -> None:
        canvas = self.canv
        pad_left, pad_bottom = 20 * mm, 12 * mm
        grid_w = self.width - pad_left - 3 * mm
        grid_h = self.height - pad_bottom - 4 * mm
        cell_w, cell_h = grid_w / 3, grid_h / 3

        for row in range(3):
            for column in range(3):
                severity = row + column
                band = "low" if severity <= 1 else "medium" if severity <= 2 else "high"
                tint = {"low": colors.HexColor("#EAF3EA"),
                        "medium": colors.HexColor("#FBF0DC"),
                        "high": colors.HexColor("#F9E4E2")}[band]
                x = pad_left + column * cell_w
                y = pad_bottom + row * cell_h
                canvas.setFillColor(tint)
                canvas.setStrokeColor(colors.white)
                canvas.setLineWidth(GAP * 2)
                canvas.rect(x, y, cell_w, cell_h, stroke=1, fill=1)
                canvas.setFillColor(STATUS[band])
                canvas.setFont("Helvetica-Bold", 5.4)
                canvas.drawString(x + 1.8 * mm, y + 1.6 * mm, band.upper())

        for index, risk in enumerate(self.risks[:9]):
            column = min(max(int(risk.get("likelihood", 1)), 0), 2)
            row = min(max(int(risk.get("impact", 1)), 0), 2)
            x = pad_left + column * cell_w + cell_w / 2
            y = pad_bottom + row * cell_h + cell_h / 2
            canvas.setFillColor(colors.white)
            canvas.circle(x, y, 2.9 * mm, stroke=0, fill=1)
            canvas.setFillColor(ORANGE)
            canvas.circle(x, y, 2.2 * mm, stroke=0, fill=1)
            canvas.setFillColor(colors.white)
            canvas.setFont("Helvetica-Bold", 6.4)
            canvas.drawCentredString(x, y - 2.2, str(index + 1))

        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica-Bold", 6)
        canvas.drawCentredString(pad_left + grid_w / 2, 4.6 * mm, "LIKELIHOOD →")
        canvas.saveState()
        canvas.rotate(90)
        canvas.drawCentredString(pad_bottom + grid_h / 2, -3.4 * mm, "IMPACT →")
        canvas.restoreState()
        canvas.setFont("Helvetica", 5.8)
        for index, label in enumerate(self.BANDS):
            canvas.drawCentredString(pad_left + index * cell_w + cell_w / 2, 8.6 * mm, label)
            canvas.drawRightString(pad_left - 2 * mm, pad_bottom + index * cell_h + cell_h / 2,
                                   label)


class CoverageBars(Flowable):
    """One measure across a handful of named things, as plain horizontal bars.

    A nominal set — geographies, evidence tiers, offer families — so every bar
    is the SAME colour. Colouring them by their own value would spend the
    identity channel re-encoding the length, which the bar already says.
    """

    def __init__(self, rows: Sequence[tuple[str, float, str]], width: float,
                 colour: colors.Color = ORANGE, height: float | None = None):
        super().__init__()
        # (label, 0..1, value text)
        self.rows = list(rows)
        self.colour = colour
        self.width = width
        self.height = height if height is not None else max(len(self.rows), 1) * 7.6 * mm

    def draw(self) -> None:
        canvas = self.canv
        if not self.rows:
            return
        label_column = 34 * mm
        value_column = 18 * mm
        usable = self.width - label_column - value_column
        slot = self.height / len(self.rows)
        bar_height = min(4.6 * mm, slot - GAP * 2)
        for index, (label, fraction, value_text) in enumerate(self.rows):
            y = self.height - (index + 1) * slot + (slot - bar_height) / 2
            canvas.setFillColor(SURFACE)
            canvas.rect(label_column, y, usable, bar_height, stroke=0, fill=1)
            _rounded_bar(canvas, label_column, y, max(usable * _clamp(fraction), 0.6 * mm),
                         bar_height, self.colour, horizontal=True)
            canvas.setFillColor(INK)
            canvas.setFont("Helvetica", 6.6)
            canvas.drawString(0, y + bar_height / 2 - 2.1, _clip(label, 34))
            canvas.setFillColor(MUTED)
            canvas.setFont("Helvetica-Bold", 6.4)
            canvas.drawRightString(self.width, y + bar_height / 2 - 2, safe(value_text))


class OptionColumns(Flowable):
    """A handful of commercial models side by side on one measure.

    Up to four, which is where the categorical palette stops. A fifth option is
    not a fifth colour — it is a sign the sheet should be a table.
    """

    def __init__(self, options: Sequence[tuple[str, float, str]], width: float,
                 height: float = 46 * mm):
        super().__init__()
        # (label, 0..1, value text)
        self.options = list(options)[:4]
        self.width, self.height = width, height

    def draw(self) -> None:
        canvas = self.canv
        if not self.options:
            return
        pad_bottom, pad_top = 14 * mm, 6 * mm
        plot_h = self.height - pad_bottom - pad_top
        slot = self.width / len(self.options)
        bar_width = min(16 * mm, slot - GAP * 3)
        for frac in (0, 0.5, 1.0):
            _grid(canvas, 0, pad_bottom + plot_h * frac, self.width)
        for index, (label, fraction, value_text) in enumerate(self.options):
            x = index * slot + (slot - bar_width) / 2
            height = max(plot_h * _clamp(fraction), 0.8 * mm)
            _rounded_bar(canvas, x, pad_bottom, bar_width, height, CATEGORICAL[index])
            canvas.setFillColor(INK)
            canvas.setFont("Helvetica-Bold", 6.6)
            canvas.drawCentredString(x + bar_width / 2, pad_bottom + height + 1.6 * mm, safe(value_text))
            canvas.setFillColor(MUTED)
            canvas.setFont("Helvetica", 6)
            _centred_lines(canvas, x + slot / 2 - (slot - bar_width) / 2 + 0,
                           6.6 * mm, _wrap(safe(label), max(10, int(slot / 3.2)))[:2], 6, 6)


# ---------------------------------------------------------------------------

def _clamp(value: Any, low: float = 0.0, high: float = 1.0) -> float:
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return low


def safe(value: Any) -> str:
    """A string fit to be drawn straight onto a canvas.

    `brief._text` does this AND escapes for reportlab's markup parser, which is
    right for a Paragraph and wrong here: canvas.drawString has no parser, so an
    ampersand escaped for one arrives on the page as "&amp;". Same WinAnsi
    decomposition — Helvetica is a core font and a character outside it renders
    as a black box — without the escaping.
    """
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.encode("cp1252", "ignore").decode("cp1252")


def _clip(text: str, length: int) -> str:
    text = safe(text)
    return text if len(text) <= length else text[: length - 1].rstrip() + "…"


def _money(value: float | None) -> str:
    """Local rather than imported so a chart axis never disagrees with the body
    text: `sizing.format_eur` is the one formatter, and this defers to it."""
    from ..sizing import format_eur
    return format_eur(value)
