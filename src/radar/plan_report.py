"""The plan as a PDF — everything on the Planner screen, in one document.

Six parts, in the order an executive committee reads them:

  1  cover          what this is, what it earns, and what it rests on
  2  inputs         the constraints that produced it. A plan without its inputs
                    is not reproducible, and reproducibility is the difference
                    between a proposal and an assertion
  3  overview       the projection, its interval, the entry schedule, the
                    capability load, the mix, and anything flagged
  4  spaces         every selected space with its entry year and economics,
                    then the near-misses and the constraint that excluded each
  5  business plan  the written narrative, if it has been generated
  6  assumptions    every band, its owner, its version — the last page, exactly
                    as the sales brief does it

Charts are drawn here rather than imported, for the reason the brief draws its
own solution diagram: a chart with exact geometry is legible every time, and one
handed to a layout engine is legible until the data changes.

reportlab rather than HTML-to-PDF, so there is no browser dependency — which is
what keeps the sovereign deployment option open (NFR-05).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Flowable, Frame, KeepTogether, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)

from .brief import INK, MUTED, ORANGE, ORANGE_DARK, RULE, SURFACE, WARN, WARN_BG, _styles, _text
from .config import Config
from .db import Database

log = logging.getLogger(__name__)

PLAN_REPORT_SCHEMA = "planreport-1"

COHORT_COLOUR = {
    "now": ORANGE,
    "next": colors.HexColor("#E8A33D"),
    "later": colors.HexColor("#F0CFA0"),
}


def _eur(value: float | None) -> str:
    if value is None:
        return "—"
    m = value / 1e6
    if abs(m) >= 1000:
        return f"EUR {m/1000:,.2f}bn"
    if abs(m) >= 10:
        return f"EUR {m:,.0f}m"
    # Rounding a real but small figure to "EUR 0.0m" reads as nothing at all,
    # which is a different claim from "small".
    if 0 < abs(m) < 0.1:
        return "< EUR 0.1m"
    return f"EUR {m:,.1f}m"


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

class BarChart(Flowable):
    """Revenue and profit per year, as paired bars with a value on each.

    Paired rather than stacked: profit is a PART of revenue, and stacking them
    would imply they add. The reader has to be able to see the margin as a
    proportion, which is the whole point of putting them side by side.
    """

    def __init__(self, revenue: list[float], profit: list[float], width: float,
                 height: float = 46 * mm):
        super().__init__()
        self.revenue, self.profit = revenue, profit
        self.width, self.height = width, height

    def draw(self) -> None:
        c = self.canv
        n = max(len(self.revenue), 1)
        top = max(max(self.revenue, default=0), 1.0)
        pad_l, pad_b = 20 * mm, 8 * mm
        plot_w = self.width - pad_l - 4 * mm
        plot_h = self.height - pad_b - 5 * mm
        slot = plot_w / n

        c.setStrokeColor(RULE)
        c.setLineWidth(0.4)
        c.setFont("Helvetica", 5.8)
        for frac in (0, 0.5, 1.0):
            y = pad_b + plot_h * frac
            c.line(pad_l, y, pad_l + plot_w, y)
            c.setFillColor(MUTED)
            c.drawRightString(pad_l - 2 * mm, y - 1.4, _eur(top * frac))

        for i in range(n):
            x0 = pad_l + i * slot
            bw = slot * 0.3
            rev, prof = self.revenue[i], self.profit[i]
            c.setFillColor(colors.HexColor("#F5D7B4"))
            c.rect(x0 + slot * 0.14, pad_b, bw, plot_h * (rev / top), stroke=0, fill=1)
            c.setFillColor(ORANGE)
            c.rect(x0 + slot * 0.52, pad_b, bw, plot_h * (prof / top), stroke=0, fill=1)
            c.setFillColor(MUTED)
            c.setFont("Helvetica", 5.8)
            c.drawCentredString(x0 + slot / 2, 2 * mm, f"Y{i+1}")
            c.setFillColor(INK)
            c.setFont("Helvetica-Bold", 5.8)
            c.drawCentredString(x0 + slot * 0.14 + bw / 2,
                                pad_b + plot_h * (rev / top) + 1.4 * mm, _eur(rev))
            c.setFillColor(ORANGE_DARK)
            c.drawCentredString(x0 + slot * 0.52 + bw / 2,
                                pad_b + plot_h * (prof / top) + 1.4 * mm, _eur(prof))

        c.setFont("Helvetica", 6)
        c.setFillColor(colors.HexColor("#F5D7B4"))
        c.rect(pad_l, self.height - 3.6 * mm, 3 * mm, 2.4 * mm, stroke=0, fill=1)
        c.setFillColor(MUTED)
        c.drawString(pad_l + 4 * mm, self.height - 3.4 * mm, "revenue")
        c.setFillColor(ORANGE)
        c.rect(pad_l + 18 * mm, self.height - 3.6 * mm, 3 * mm, 2.4 * mm, stroke=0, fill=1)
        c.setFillColor(MUTED)
        c.drawString(pad_l + 22 * mm, self.height - 3.4 * mm, "profit")


class EntryChart(Flowable):
    """Spaces entering each year, stacked by the horizon cohort they came from."""

    def __init__(self, by_year: dict[int, dict[str, int]], years: int, width: float,
                 height: float = 38 * mm):
        super().__init__()
        self.by_year, self.years = by_year, years
        self.width, self.height = width, height

    def draw(self) -> None:
        c = self.canv
        totals = [sum(self.by_year.get(y, {}).values()) for y in range(1, self.years + 1)]
        top = max(totals + [1])
        pad_l, pad_b = 10 * mm, 7 * mm
        plot_w = self.width - pad_l - 4 * mm
        # The top strip is the legend's; the tallest bar's count label has to
        # land below it rather than through it.
        plot_h = self.height - pad_b - 9 * mm
        slot = plot_w / max(self.years, 1)

        for i in range(self.years):
            year = i + 1
            counts = self.by_year.get(year, {})
            acc = 0
            x0 = pad_l + i * slot + slot * 0.22
            bw = slot * 0.56
            for cohort in ("now", "next", "later"):
                n = counts.get(cohort, 0)
                if not n:
                    continue
                h = plot_h * (n / top)
                c.setFillColor(COHORT_COLOUR[cohort])
                c.rect(x0, pad_b + plot_h * (acc / top), bw, h, stroke=0, fill=1)
                acc += n
            c.setFillColor(MUTED)
            c.setFont("Helvetica", 5.8)
            c.drawCentredString(x0 + bw / 2, 2 * mm, f"Y{year}")
            if acc:
                c.setFillColor(INK)
                c.setFont("Helvetica-Bold", 6.4)
                c.drawCentredString(x0 + bw / 2, pad_b + plot_h * (acc / top) + 1.2 * mm, str(acc))

        c.setFont("Helvetica", 6)
        x = pad_l
        for cohort in ("now", "next", "later"):
            c.setFillColor(COHORT_COLOUR[cohort])
            c.rect(x, self.height - 3.6 * mm, 3 * mm, 2.4 * mm, stroke=0, fill=1)
            c.setFillColor(MUTED)
            c.drawString(x + 4 * mm, self.height - 3.4 * mm, cohort)
            x += 17 * mm


class CapacityChart(Flowable):
    """Peak load per capability pool against the ceiling.

    The ceiling is the point, so it is a line the bar can visibly reach — a
    pool at 100% is the reason the plan is the size it is, and that has to be
    readable at a glance rather than inferred from a number.
    """

    def __init__(self, pools: dict[str, Any], width: float):
        super().__init__()
        self.pools = pools
        self.width = width
        self.height = max(len(pools), 1) * 7 * mm + 4 * mm

    def draw(self) -> None:
        c = self.canv
        pad_l = 42 * mm
        bar_w = self.width - pad_l - 16 * mm
        for i, (name, data) in enumerate(self.pools.items()):
            y = self.height - (i + 1) * 7 * mm
            util = min(data.get("peak_utilisation") or 0.0, 1.0)
            over = (data.get("peak_utilisation") or 0.0) >= 0.98
            c.setFont("Helvetica", 6.4)
            c.setFillColor(INK)
            c.drawRightString(pad_l - 2 * mm, y + 1.2 * mm, _text(name.replace(" experts", ""))[:34])
            c.setFillColor(SURFACE)
            c.setStrokeColor(RULE)
            c.setLineWidth(0.4)
            c.rect(pad_l, y, bar_w, 3.6 * mm, stroke=1, fill=1)
            c.setFillColor(colors.HexColor("#B3261E") if over else ORANGE)
            c.rect(pad_l, y, bar_w * util, 3.6 * mm, stroke=0, fill=1)
            c.setFillColor(colors.HexColor("#B3261E") if over else MUTED)
            c.setFont("Helvetica-Bold" if over else "Helvetica", 6.4)
            c.drawString(pad_l + bar_w + 2 * mm, y + 1.2 * mm,
                         f"{(data.get('peak_utilisation') or 0)*100:.0f}%")


# ---------------------------------------------------------------------------
# The document
# ---------------------------------------------------------------------------

class PlanReportBuilder:
    def __init__(self, cfg: Config, db: Database, output_dir: Path | None = None):
        self.cfg = cfg
        self.db = db
        self.styles = _styles()
        self.output_dir = Path(output_dir or Path(cfg.db_path).parent / "plans")

    def build(self, plan: dict[str, Any]) -> dict[str, Any]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{plan['id']}-business-plan.pdf"
        path = self.output_dir / filename
        story = self._story(plan)
        self._render(path, story, plan)
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        with self.db.cursor() as cur:
            cur.execute("UPDATE plans SET pdf_path=?, pdf_bytes=?, pdf_hash=?, "
                        "pdf_generated_at=?, pdf_schema=? WHERE id=?",
                        (str(path), len(payload), digest,
                         dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                         PLAN_REPORT_SCHEMA, plan["id"]))
        log.info("Plan report %s: %s (%d bytes)", plan["id"], path, len(payload))
        return {"path": str(path), "filename": filename, "bytes": len(payload),
                "content_hash": digest, "schema": PLAN_REPORT_SCHEMA}

    # -------------------------------------------------------------- render
    def _render(self, path: Path, story: list[Any], plan: dict[str, Any]) -> None:
        doc = BaseDocTemplate(
            str(path), pagesize=A4,
            leftMargin=17 * mm, rightMargin=17 * mm, topMargin=17 * mm, bottomMargin=16 * mm,
            title=f"{plan['id']} — {plan.get('label')}",
            author="Orange Business Innovation Radar",
            subject="Five-year portfolio plan",
        )
        frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body")
        econ = plan.get("economics_version")

        def decorate(canvas, document):
            canvas.saveState()
            canvas.setFillColor(ORANGE)
            canvas.rect(0, A4[1] - 6, A4[0], 6, stroke=0, fill=1)
            canvas.setFont("Helvetica", 6.6)
            canvas.setFillColor(MUTED)
            canvas.drawString(17 * mm, 10 * mm,
                              f"Orange Business Innovation Radar · {plan['id']} · "
                              f"{_text(plan.get('label'))[:60]}")
            canvas.drawRightString(A4[0] - 17 * mm, 10 * mm, f"page {document.page}")
            canvas.setStrokeColor(RULE)
            canvas.setLineWidth(0.4)
            canvas.line(17 * mm, 13 * mm, A4[0] - 17 * mm, 13 * mm)
            if document.page > 1:
                canvas.drawString(17 * mm, A4[1] - 12 * mm,
                                  f"Internal — scenario under stated assumptions · "
                                  f"economics {econ}")
            canvas.restoreState()

        doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=decorate)])
        doc.build(story)

    # --------------------------------------------------------------- story
    def _story(self, plan: dict[str, Any]) -> list[Any]:
        story: list[Any] = []
        story += self._cover(plan)
        story += self._inputs(plan)
        story += self._overview(plan)
        story += self._spaces(plan)
        story += self._narrative(plan)
        story += self._assumptions(plan)
        return story

    # 1 -------------------------------------------------------------- cover
    def _cover(self, plan: dict[str, Any]) -> list[Any]:
        s = self.styles
        p = plan["projection"]
        story: list[Any] = [
            Paragraph("ORANGE BUSINESS · INNOVATION RADAR · PORTFOLIO PLAN", s["kicker"]),
            Paragraph(_text(plan.get("label") or "Five-year portfolio plan"), s["title"]),
            Paragraph(
                f"{plan['selected_count']} opportunity spaces selected from "
                f"{plan['considered_count']} admissible candidates, entered over "
                f"{plan['plan_years']} years.", s["body"]),
        ]
        narrative = plan.get("narrative") or {}
        if narrative.get("headline"):
            story.append(Paragraph(
                f'<i>"{_text(narrative["headline"])}"</i>', s["body"]))

        rows = [
            [Paragraph(h, s["cellhead"]) for h in
             ("", f"{plan['plan_years']}-year total", "Range", "Basis")],
            [Paragraph("Revenue", s["cell"]), Paragraph(_eur(p["revenue_total"]), s["cell"]),
             Paragraph("—", s["cell"]),
             Paragraph("obtainable share, overlap-adjusted", s["cell"])],
            [Paragraph("Profit", s["cell"]), Paragraph(_eur(p["profit_total"]), s["cell"]),
             Paragraph(f"{_eur(p['profit_total_low'])} – {_eur(p['profit_total_high'])}", s["cell"]),
             Paragraph("margin band by portfolio distance", s["cell"])],
            [Paragraph("NPV of profit", s["cell"]), Paragraph(_eur(p["npv_profit"]), s["cell"]),
             Paragraph("—", s["cell"]),
             Paragraph(f"discounted at {p['discount_rate']:.1%}, Orange's filed rate", s["cell"])],
        ]
        table = Table(rows, colWidths=[26 * mm, 32 * mm, 46 * mm, 72 * mm], hAlign="LEFT")
        table.setStyle(_plan_table_style())
        story += [Spacer(1, 3 * mm), table, Spacer(1, 3 * mm)]

        # The provenance line, on the cover rather than the last page: a reader
        # deciding how much to trust this document needs to know which figures
        # are Orange's own before reading any of them.
        a = plan.get("assumptions") or {}
        filed = a.get("filed") or {}
        story.append(Paragraph(
            f"<b>Grounded in Orange's own published accounts.</b> The margin applied to revenue "
            f"({filed.get('segment_ebitdaal_margin', 0):.1%} segment EBITDAaL) and the rate used to "
            f"discount it ({filed.get('discount_rate_post_tax', 0):.1%} post-tax) are quoted from "
            f"{_text(a.get('source_filing'))}. Everything else is a planning band with a named "
            f"owner, listed in full on the last page.", s["small"]))
        story.append(Paragraph(
            "<b>This is a scenario, not a forecast.</b> Obtainable share is a planning assumption "
            "computed per space; the range above is the sizing engine's own low and high estimate, "
            "not a confidence interval. Every figure is reproducible from the inputs on the next "
            "page and the assumptions on the last.", s["warn"]))

        for flag in plan.get("flags") or []:
            story.append(Paragraph(
                f"<b>{_text(flag['kind']).upper()} — {_text(flag['severity'])}.</b> "
                f"{_text(flag['message'])}", s["warn"]))
        return story

    # 2 ------------------------------------------------------------- inputs
    def _inputs(self, plan: dict[str, Any]) -> list[Any]:
        s = self.styles
        inputs = plan.get("inputs") or {}
        from_workflow = inputs.get("source") == "workflow"
        story = [Paragraph("The inputs that produced this plan", s["h2"])]
        if from_workflow:
            # The reader has to know, before the first figure, that nobody chose
            # this set here. Everything downstream — why nothing was optimised,
            # why a pool can be over-committed — follows from that one fact.
            from .planner import WORKFLOW_STAGE_LABELS
            stage = inputs.get("from_stage") or "demand_tested"
            story.append(Paragraph(
                f"This plan did not select anything. The portfolio is every opportunity space "
                f"the collaboration workflow has moved to "
                f"<b>{_text(WORKFLOW_STAGE_LABELS.get(stage, stage))} or beyond</b> — a set of "
                f"human decisions taken on the workflow board, not an optimiser's output. No "
                f"confidence floor, distance cap or concentration limit was applied to it, "
                f"because each would have overruled one of those decisions with an assumption "
                f"band. What the Planner did is schedule the set across the window and do the "
                f"arithmetic.", s["small"]))
        else:
            story.append(Paragraph(
                "A plan without its inputs is not reproducible. These are the stated "
                "constraints; the same values against the same assumption versions "
                "produce this plan again, and a test asserts it.", s["small"]))
        a = plan.get("assumptions") or {}
        cap, defaults = a.get("capacity") or {}, a.get("defaults") or {}
        # An unset parameter is not an absent one — the planner falls back to
        # the economics default and plans against that. Showing the stated
        # values alone would misrepresent what the optimiser actually ran with,
        # so every row carries its effective value and where it came from.
        fallback = {
            "plan_years": defaults.get("plan_years"),
            "objective": defaults.get("objective"),
            "min_confidence": defaults.get("min_confidence"),
            "max_portfolio_distance": defaults.get("max_portfolio_distance"),
            "entry_slots_per_year": cap.get("entry_slots_per_year"),
            "pool_availability": cap.get("pool_availability"),
            "max_share_per_vertical": defaults.get("max_share_per_vertical"),
            "max_share_per_technology": defaults.get("max_share_per_technology"),
            "horizon_mix": defaults.get("horizon_mix"),
            "horizon_tolerance": defaults.get("horizon_tolerance"),
        }
        labels = [
            ("source", "Where the portfolio came from"),
            ("objective", "Objective"),
            ("plan_years", "Plan horizon (years)"),
            ("entry_slots_per_year", "New spaces started per year"),
            ("pool_availability", "Capability headcount available for new work"),
            ("budget_person_years", "Entry-effort budget (person-years)"),
            ("min_confidence", "Minimum size confidence"),
            ("max_portfolio_distance", "Furthest portfolio distance"),
            ("max_share_per_vertical", "Maximum share in one vertical"),
            ("max_share_per_technology", "Maximum share in one technology"),
            ("horizon_mix", "Target now / next / later mix"),
            ("horizon_tolerance", "Tolerance on that mix"),
            ("max_competition", "Maximum competitive intensity"),
            ("require_sovereign", "Sovereign delivery required"),
            ("geographies", "Geographies"),
            ("prefer_verticals", "Preferred verticals"),
            ("prefer_domains", "Preferred domains"),
            ("preference_weight", "Weight on those preferences"),
            ("exclude_verticals", "Excluded verticals"),
            ("exclude_technologies", "Excluded technologies"),
            ("exclude_geographies", "Excluded geographies"),
        ]

        def show(value: Any) -> str:
            if isinstance(value, dict):
                return " / ".join(f"{k} {v:.0%}" for k, v in value.items())
            if isinstance(value, list):
                return ", ".join(str(v).replace("_", " ") for v in value)
            if isinstance(value, bool):
                return "yes" if value else "no"
            if isinstance(value, float) and 0 < value <= 1:
                return f"{value:.0%}"
            return str(value).replace("_", " ")

        if from_workflow:
            labels = [
                ("source", "Where the portfolio came from"),
                ("from_stage", "Included from this stage onward"),
                ("plan_years", "Plan horizon (years)"),
                ("entry_slots_per_year", "New spaces started per year"),
                ("pool_availability", "Capability headcount available for new work"),
            ]
            fallback = {k: v for k, v in fallback.items() if k in dict(labels)}

        rows = [[Paragraph(h, s["cellhead"]) for h in ("Parameter", "Value", "Source")]]
        for key, label in labels:
            stated = inputs.get(key)
            if stated in (None, "", [], ()):
                value, source = fallback.get(key), "default"
                if value in (None, "", [], ()):
                    continue
            else:
                value, source = stated, "stated"
            rows.append([Paragraph(_text(label), s["cell"]), Paragraph(_text(show(value)), s["cell"]),
                         Paragraph(source, s["cell"])])
        table = Table(rows, colWidths=[74 * mm, 76 * mm, 26 * mm], hAlign="LEFT")
        table.setStyle(_plan_table_style())
        story.append(table)
        story.append(Paragraph(
            f"Rows marked <i>default</i> were not stated and fall back to the economics assumption "
            f"set {_text(plan.get('economics_version'))}, listed in full on the last page. The "
            f"plan id is a fingerprint of the stated values, so the same request against the same "
            f"assumption versions returns this plan rather than recomputing it.", s["small"]))

        if from_workflow:
            mix = (plan.get("capacity_usage") or {}).get("stage_mix") or []
            if mix:
                story.append(Paragraph(
                    "Where the committed set stands on the gate: "
                    + " · ".join(f"{_text(m['label'])} {m['count']}" for m in mix), s["body"]))

        binding = (plan.get("capacity_usage") or {}).get("binding") or []
        if binding:
            story.append(Paragraph("What bound this plan", s["h3"]))
            story.append(Paragraph(
                "The committed set was scheduled, not selected, so these are the limits the "
                "schedule ran into rather than constraints that removed anything. Nothing was "
                "dropped to satisfy them." if from_workflow else
                "These are the constraints the optimiser actually hit. Relaxing one of them is "
                "what would change the answer; relaxing anything else would not.", s["small"]))
            story.append(Paragraph(
                " · ".join(_text(item) for item in binding), s["body"]))
        return story

    # 3 ----------------------------------------------------------- overview
    def _overview(self, plan: dict[str, Any]) -> list[Any]:
        s = self.styles
        p = plan["projection"]
        width = A4[0] - 34 * mm
        story: list[Any] = [PageBreak(), Paragraph("The projection", s["h2"])]

        head = [Paragraph(h, s["cellhead"]) for h in
                ["", *[f"Year {i+1}" for i in range(p["years"])], "Total"]]
        rows = [head,
                [Paragraph("Revenue", s["cell"])] +
                [Paragraph(_eur(v), s["cell"]) for v in p["revenue_by_year"]] +
                [Paragraph(_eur(p["revenue_total"]), s["cell"])],
                [Paragraph("Profit", s["cell"])] +
                [Paragraph(_eur(v), s["cell"]) for v in p["profit_by_year"]] +
                [Paragraph(_eur(p["profit_total"]), s["cell"])]]
        col = (width - 24 * mm) / (p["years"] + 1)
        table = Table(rows, colWidths=[24 * mm] + [col] * (p["years"] + 1), hAlign="LEFT")
        table.setStyle(_plan_table_style())
        story += [table, Spacer(1, 4 * mm),
                  BarChart(p["revenue_by_year"], p["profit_by_year"], width)]

        seg = p.get("year5_share_of_segment")
        if seg is not None:
            story.append(Paragraph(
                f"Year-{p['years']} incremental revenue is <b>{seg:.1%}</b> of Orange Business's "
                f"filed segment revenue of {_eur(p.get('segment_revenue'))}. That segment is "
                f"declining, so this share is the plausibility test this plan has to pass — it is "
                f"checked automatically and flagged on the cover when it does not.", s["small"]))

        by_year: dict[int, dict[str, int]] = {}
        for sel in plan.get("selections", []):
            cohort = (sel.get("horizon") or "next")
            by_year.setdefault(sel["entry_year"], {})
            by_year[sel["entry_year"]][cohort] = by_year[sel["entry_year"]].get(cohort, 0) + 1
        story += [Paragraph("Entry schedule", s["h3"]),
                  Paragraph("Staggered by time horizon and then by what capacity allowed. A space "
                            "ramps from its own entry year, so a deferred entry earns less inside "
                            "the window — waiting is a real cost, not free scheduling.", s["small"]),
                  EntryChart(by_year, p["years"], width)]

        pools = (plan.get("capacity_usage") or {}).get("pools") or {}
        if pools:
            story += [Paragraph("Capability pool utilisation", s["h3"]),
                      Paragraph("Peak load against the share of each pool's headcount available "
                                "for new work. A pool at its ceiling is the reason this plan is "
                                "the size it is.", s["small"]),
                      CapacityChart(pools, width)]

        mix = p.get("mix") or {}
        panels = []
        for key in ("vertical", "horizon", "distance"):
            entries = (mix.get(key) or [])[:8]
            if not entries:
                continue
            rows = [[Paragraph(key.title(), s["cellhead"]), Paragraph("n", s["cellhead"]),
                     Paragraph("Share", s["cellhead"])]]
            for e in entries:
                rows.append([Paragraph(_text(str(e["key"]).replace("_", " ")), s["cell"]),
                             Paragraph(str(e["count"]), s["cell"]),
                             Paragraph(f"{e['share']:.0%}", s["cell"])])
            inner = Table(rows, colWidths=[30 * mm, 8 * mm, 14 * mm])
            inner.setStyle(_plan_table_style())
            panels.append(inner)
        if panels:
            # Three short tables side by side rather than stacked: stacked, they
            # spill past the page break and strand one of them on a page alone.
            outer = Table([panels], colWidths=[(A4[0] - 34 * mm) / len(panels)] * len(panels),
                          hAlign="LEFT")
            outer.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                       ("LEFTPADDING", (0, 0), (0, -1), 0),
                                       ("TOPPADDING", (0, 0), (-1, -1), 0)]))
            story += [Paragraph("Portfolio mix", s["h3"]), outer]
        return story

    def _summaries(self, plan: dict[str, Any]) -> dict[str, str]:
        """The one-paragraph summary from each space's own long-form description.

        A table of ids and euro figures tells a reader which spaces were chosen
        and nothing about what any of them IS. The summary is the sentence a
        salesperson could read out, it is already written and already bound to
        that space's own evidence, so the plan quotes it rather than asking a
        model to paraphrase what has been written once already.
        """
        ids = [s["opportunity_id"] for s in plan.get("selections", [])]
        if not ids:
            return {}
        placeholders = ",".join("?" for _ in ids)
        rows = self.db.query(
            f"SELECT opportunity_id, sections FROM topic_descriptions "
            f"WHERE opportunity_id IN ({placeholders})", tuple(ids))
        from .db import unjs
        out: dict[str, str] = {}
        for row in rows:
            sections = unjs(row["sections"], {}) or {}
            entry = sections.get("summary") or {}
            text = (entry.get("text") if isinstance(entry, dict) else entry) or ""
            if text.strip():
                out[row["opportunity_id"]] = text.strip()
        return out

    # 4 ------------------------------------------------------------- spaces
    def _spaces(self, plan: dict[str, Any]) -> list[Any]:
        s = self.styles
        story: list[Any] = [PageBreak(), Paragraph("The selected opportunity spaces", s["h2"]),
                            Paragraph("In entry order, each with the one-paragraph summary from "
                                      "its own long-form description — written against that "
                                      "space's own evidence, and quoted here rather than "
                                      "paraphrased.", s["small"])]
        summaries = self._summaries(plan)
        selections = plan.get("selections", [])
        if selections and len(summaries) < len(selections):
            # Said once, with a number, rather than left as a gap the reader
            # discovers repeatedly and has to count for themselves.
            story.append(Paragraph(
                f"<b>{len(summaries)} of {len(selections)} selected spaces have a long-form "
                f"description.</b> The rest are marked below. Generating the missing ones and "
                f"rebuilding this document completes it — nothing about the plan changes.",
                s["warn"]))
        by_year: dict[int, list[dict]] = {}
        for sel in plan.get("selections", []):
            by_year.setdefault(sel["entry_year"], []).append(sel)

        for year in sorted(by_year):
            story.append(Paragraph(f"Year {year} — {len(by_year[year])} space(s) enter", s["h3"]))
            for sel in by_year[year]:
                tid = sel["opportunity_id"]
                block: list[Any] = [Paragraph(
                    f'<b>{_text(tid)}</b> &nbsp;<font color="{_grey()}" size=7.4>'
                    f'{_text(str(sel["vertical"]).replace("_", " "))} · '
                    f'L{sel["portfolio_distance"]} · {_text(sel.get("horizon") or "")} · '
                    f'{_text(sel.get("pool") or "unassigned")}</font><br/>'
                    f'{_text(sel["statement"])}', s["body"])]
                summary = summaries.get(tid)
                if summary:
                    block.append(Paragraph(_text(summary), s["small"]))
                else:
                    block.append(Paragraph(
                        "<i>No long-form description has been generated for this space yet, so "
                        "there is nothing to quote. Generate it from the topic detail and rebuild "
                        "this document.</i>", s["small"]))
                figures = Table(
                    [[Paragraph(f"5-year revenue &nbsp;<b>{_eur(sum(sel.get('revenue_by_year') or []))}</b>",
                                s["cell"]),
                      Paragraph(f"5-year profit &nbsp;<b>{_eur(sum(sel.get('profit_by_year') or []))}</b>",
                                s["cell"]),
                      Paragraph(f"margin applied &nbsp;<b>{(sel.get('margin_applied') or 0):.1%}</b>",
                                s["cell"]),
                      Paragraph(f"entry effort &nbsp;<b>{sel.get('entry_effort', 0):.0f} py</b>",
                                s["cell"])]],
                    colWidths=[44 * mm, 44 * mm, 44 * mm, 44 * mm], hAlign="LEFT")
                figures.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                    ("BOX", (0, 0), (-1, -1), 0.3, colors.HexColor("#DDDDDD")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#DDDDDD")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]))
                block += [figures, Spacer(1, 3 * mm)]
                story.append(KeepTogether(block))

        exclusions = plan.get("exclusions") or []
        if exclusions:
            from_workflow = (plan.get("inputs") or {}).get("source") == "workflow"
            story += [
                Paragraph("What is not in this plan, and why" if from_workflow else
                          "Near misses, and the constraint that excluded each", s["h2"]),
                Paragraph("Nothing here was excluded by the Planner — it excluded nothing. These "
                          "spaces are waiting for a decision on the workflow board, were stopped "
                          "there, or carry no market size to project." if from_workflow else
                          "As useful as the inclusions, and the thing an optimiser can say "
                          "that a ranked list cannot: the reason is a constraint, and the "
                          "constraint is named.", s["small"])]
            rows = [[Paragraph(h, s["cellhead"]) for h in ("Space", "Opportunity", "Why not")]]
            for e in exclusions[:14]:
                rows.append([Paragraph(_text(e["opportunity_id"]), s["cell"]),
                             Paragraph(_text(e["statement"]), s["cell"]),
                             Paragraph(_text(e["reason"]), s["cell"])])
            table = Table(rows, colWidths=[15 * mm, 78 * mm, 82 * mm], hAlign="LEFT")
            table.setStyle(_plan_table_style())
            story.append(table)
        return story

    # 5 ---------------------------------------------------------- narrative
    def _narrative(self, plan: dict[str, Any]) -> list[Any]:
        from .pipeline.prompts import PLAN_SECTIONS

        s = self.styles
        narrative = plan.get("narrative") or {}
        sections = narrative.get("sections") or {}
        story: list[Any] = [PageBreak(), Paragraph("The business plan", s["h2"])]
        if not sections:
            story.append(Paragraph(
                "<b>The written plan has not been generated for this portfolio.</b> Everything "
                "above was computed by the optimiser; this section is where a model explains it. "
                "Generate it from the Planner and rebuild this document to include it.", s["warn"]))
            return story

        titles = {
            "thesis": "The thesis", "why_these": "Why this set", "sequence": "The sequence",
            "capacity": "Execution", "risks": "Risks", "not_doing": "What we are not doing",
        }
        story.append(Paragraph(
            "Written by a model from the computed plan, under one absolute rule: it may not "
            "state a figure. Every number in this document was produced by the optimiser, and a "
            "sentence that disagreed with the table beside it would be a defect the reader has to "
            "adjudicate. Sections that broke the rule were removed and are listed at the end.",
            s["small"]))
        for key in PLAN_SECTIONS:
            if key not in sections:
                continue
            story.append(KeepTogether([
                Paragraph(titles.get(key, key.replace("_", " ").title()), s["h3"]),
                Paragraph(_text(sections[key]), s["body"]),
            ]))

        stripped = plan.get("stripped") or []
        if stripped:
            story.append(Paragraph("Removed by the guardrails", s["h3"]))
            for item in stripped:
                story.append(Paragraph(
                    f"— <b>{_text(item.get('section'))}</b>: {_text(item.get('reason'))}",
                    s["small"]))
        return story

    # 6 -------------------------------------------------------- assumptions
    def _assumptions(self, plan: dict[str, Any]) -> list[Any]:
        s = self.styles
        a = plan.get("assumptions") or {}
        filed = a.get("filed") or {}
        story: list[Any] = [PageBreak(), Paragraph("What this plan rests on", s["h2"]),
                            Paragraph("Two figures are quoted from Orange's own filed accounts. "
                                      "Everything else is a planning band with a named owner. A "
                                      "plan built under one version of these assumptions is not "
                                      "comparable with a plan built under another, which is why "
                                      "the version travels on every plan.", s["small"])]

        story.append(Paragraph(f"Filed — {_text(a.get('source_filing'))}", s["h3"]))
        rows = [[Paragraph(h, s["cellhead"]) for h in ("Figure", "Value", "Where it is used")]]
        for label, key, use in (
            ("Post-tax discount rate", "discount_rate_post_tax", "Discounting the profit stream"),
            ("Pre-tax discount rate", "discount_rate_pre_tax", "Reference only"),
            ("Segment EBITDAaL margin", "segment_ebitdaal_margin",
             "Anchor for the margin bands below"),
            ("Segment revenue", "segment_revenue_eur_m", "The plausibility check"),
        ):
            value = filed.get(key)
            if value is None:
                continue
            shown = f"EUR {value:,.0f}m" if key.endswith("_eur_m") else f"{value:.1%}"
            rows.append([Paragraph(label, s["cell"]), Paragraph(shown, s["cell"]),
                         Paragraph(use, s["cell"])])
        table = Table(rows, colWidths=[52 * mm, 34 * mm, 90 * mm], hAlign="LEFT")
        table.setStyle(_plan_table_style())
        story.append(table)

        story.append(Paragraph(f"Planning bands — owner: {_text(a.get('owner'))}", s["h3"]))
        rows = [[Paragraph(h, s["cellhead"]) for h in ("Assumption", "Value", "Note")]]
        for level, margin in (a.get("margin_by_distance") or {}).items():
            note = {"L0": "existing offer on existing overhead — above the segment average",
                    "L1": "packaging two existing offers",
                    "L2": "partner-dependent; the filed segment figure itself",
                    "L3": "a capability build, carried in opex during the window",
                    "L4": "no delivery path; earns nothing inside the window"}.get(level, "")
            rows.append([Paragraph(f"Margin at {level}", s["cell"]),
                         Paragraph(f"{margin:.1%}", s["cell"]), Paragraph(note, s["cell"])])
        for horizon, ramp in (a.get("ramp_by_horizon") or {}).items():
            rows.append([Paragraph(f"Ramp — {horizon}", s["cell"]),
                         Paragraph(" · ".join(f"{v:.0%}" for v in ramp), s["cell"]),
                         Paragraph("share of obtainable market reached in each year after "
                                   "that space's own entry", s["cell"])])
        cap = a.get("capacity") or {}
        for label, key, note in (
            ("Entry slots per year", "entry_slots_per_year",
             "new spaces the organisation can start at all"),
            ("Pool availability", "pool_availability",
             "share of headcount free for new opportunity work"),
            ("Shared build discount", "shared_build_discount",
             "saved on the second space needing the same capability"),
        ):
            if key in cap:
                value = cap[key]
                shown = f"{value:.0%}" if isinstance(value, float) and value <= 1 else str(value)
                rows.append([Paragraph(label, s["cell"]), Paragraph(shown, s["cell"]),
                             Paragraph(note, s["cell"])])
        agg = a.get("aggregation") or {}
        for label, key, note in (
            ("Overlap — same vertical", "overlap_discount_same_vertical",
             "obtainable share is not additive; spaces compete for one buying centre"),
            ("Overlap — same use case", "overlap_discount_same_use_case",
             "applied again, more weakly"),
            ("Plausibility flag", "plausibility_flag_share_of_segment",
             "year-5 revenue above this share of segment revenue is flagged"),
        ):
            if key in agg:
                rows.append([Paragraph(label, s["cell"]),
                             Paragraph(f"{agg[key]:.0%}", s["cell"]), Paragraph(note, s["cell"])])
        table = Table(rows, colWidths=[46 * mm, 40 * mm, 90 * mm], hAlign="LEFT")
        table.setStyle(_plan_table_style())
        story.append(table)

        story.append(Paragraph("Provenance", s["h3"]))
        story.append(Paragraph(
            f"plan {_text(plan['id'])} · created {_text(plan.get('created_at'))} · "
            f"economics {_text(plan.get('economics_version'))} · "
            f"sizing {_text(plan.get('sizing_version'))} · "
            f"weight set {_text(plan.get('weight_set'))}"
            + (f" · prompt {_text(plan.get('prompt_version'))}" if plan.get("prompt_version") else "")
            + (f" · model {_text(plan.get('model_version'))}" if plan.get("model_version") else ""),
            s["cite"]))
        story.append(Paragraph(
            "A plan that cannot be traced is a pitch. Every figure above is reproducible from the "
            "inputs on page 2 and the bands on this page.", s["small"]))
        return story


def _grey() -> str:
    return "#666666"


def _plan_table_style() -> TableStyle:
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3C3C3C")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#C8C8C8")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F6F6")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ])


def plan_report_meta(db: Database, plan_id: str) -> dict[str, Any] | None:
    """Stored PDF metadata, with staleness against the plan it was built from."""
    row = db.query_one(
        "SELECT id, pdf_path, pdf_bytes, pdf_hash, pdf_generated_at, pdf_schema, "
        "status, narrative FROM plans WHERE id = ?", (plan_id,))
    if row is None or not row["pdf_path"]:
        return None
    path = Path(row["pdf_path"])
    # A plan is immutable once computed — its id is a fingerprint of its inputs —
    # so the only way the PDF goes stale is the narrative being written or
    # rewritten underneath it.
    narrated_after = bool(row["narrative"]) and row["pdf_schema"] == PLAN_REPORT_SCHEMA
    return {
        "plan_id": plan_id, "filename": path.name, "path": str(path), "bytes": row["pdf_bytes"],
        "content_hash": row["pdf_hash"], "generated_at": row["pdf_generated_at"],
        "schema": row["pdf_schema"], "exists": path.exists(),
        "stale": row["pdf_schema"] != PLAN_REPORT_SCHEMA or not path.exists(),
        "has_narrative": narrated_after,
        "url": f"/api/planner/plans/{plan_id}/report.pdf",
    }
