"""Everything one opportunity space knows, assembled once per build.

Twelve pieces of collateral off one space would otherwise mean twelve rounds of
the same five queries. More importantly they would mean twelve chances to
disagree with each other: two documents in the same pack quoting different SAM
figures because one was built before a sizing run and one after is the failure
mode this class exists to make impossible. The pack is assembled from ONE
snapshot, and the snapshot carries the versions that produced it.

`prompt_context` is the same snapshot rendered for a model. It is deliberately
the only route from the database to a prompt: a writer that could reach past it
into the database could name an entity the validators were never given a chance
to close over.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..competition import competition_for_topic
from ..competitor_analysis import analysis_for_topic
from ..config import Config
from ..db import Database
from ..pipeline.describe import description_for_topic
from ..readmodel import ReadModel
from ..sizing import format_eur, sizes_for_topic

#: Node id prefixes that count as something Orange can actually put on the table,
#: as opposed to something merely linked. Used to decide the `provider` colour on
#: the component and portfolio charts.
ORANGE_OWNED = ("offer", "asset", "capability", "product", "service")


@dataclass
class TopicContext:
    """One space, everything about it, and where each part came from."""

    topic: dict[str, Any]
    description: dict[str, Any] | None
    competition: dict[str, Any] | None
    analysis: dict[str, Any] | None
    sizes: list[dict[str, Any]]
    links: list[dict[str, Any]] = field(default_factory=list)
    cfg: Config | None = None
    #: Items retrieved live by `research.gather`, if a research pass ran. Never
    #: loaded by `load` — a snapshot of the DATABASE should not silently make
    #: network calls, so the builder fills this in explicitly.
    research: list[dict[str, Any]] = field(default_factory=list)

    # -- derived views the charts and prompts both want --------------------

    @property
    def topic_id(self) -> str:
        return str(self.topic["id"])

    @property
    def statement(self) -> str:
        return str(self.topic.get("statement") or self.topic_id)

    @property
    def triple(self) -> str:
        labels = self.topic.get("labels") or {}
        return " × ".join(str(labels.get(k, "")) for k in ("vertical", "use_case", "technology"))

    @property
    def sections(self) -> dict[str, Any]:
        return (self.description or {}).get("sections") or {}

    @property
    def diagram(self) -> dict[str, Any] | None:
        return (self.description or {}).get("diagram")

    def section_text(self, name: str) -> str:
        entry = self.sections.get(name)
        if isinstance(entry, dict):
            return str(entry.get("text") or "")
        return str(entry or "")

    @property
    def best_size(self) -> dict[str, Any] | None:
        """The sized view with the strongest evidence behind it.

        Bottom-up and observed are two different methods, never averaged (§4.3.4),
        so a document that shows one figure has to say which method it is. This
        picks the higher-confidence method and every renderer prints the label
        beside the number.
        """
        if not self.sizes:
            return None
        order = {"high": 0, "medium": 1, "low": 2}
        return sorted(self.sizes, key=lambda s: order.get(str(s.get("confidence")), 3))[0]

    @property
    def orange_assets(self) -> list[dict[str, Any]]:
        """Links that name something Orange can put on the table."""
        return [link for link in self.links
                if str(link.get("node_id", "")).split(":", 1)[0] in ORANGE_OWNED
                and link.get("owner", "orange") != "competitor"]

    @property
    def references(self) -> list[dict[str, Any]]:
        return [link for link in self.links
                if str(link.get("node_id", "")).startswith("reference")]

    @property
    def competitor_names(self) -> list[str]:
        names = [str(c.get("label")) for c in ((self.competition or {}).get("competitors") or [])]
        for entry in ((self.analysis or {}).get("entries") or []):
            label = str(entry.get("label") or "")
            if label and label not in names:
                names.append(label)
        return [n for n in names if n]

    @property
    def portfolio_distance(self) -> int:
        try:
            return int(self.topic.get("portfolio_distance") or 0)
        except (TypeError, ValueError):
            return 0

    def missing(self, needs: list[str]) -> list[str]:
        """Which declared inputs this space does not have.

        Reported on the document and in the API payload rather than silently
        producing a thinner file: a pack that is quietly short a section reads
        as complete, and the person who finds out is standing in front of a
        customer.
        """
        absent = []
        if "description" in needs and not self.sections:
            absent.append("the written description")
        if "sizing" in needs and not self.sizes:
            absent.append("the market sizing")
        if "competition" in needs and not self.competition:
            absent.append("the competitive assessment")
        if "analysis" in needs and not (self.analysis or {}).get("entries"):
            absent.append("the per-competitor analysis")
        return absent

    # -- the model's view --------------------------------------------------

    def prompt_context(self) -> str:
        """The snapshot as prompt text, with every nameable entity listed.

        The closed lists at the bottom are the point. §4.4.4's defence against a
        model naming a partner Orange does not have is not a plea in the prompt —
        it is giving the model the only names it is allowed to use and stripping
        anything else on the way back (`content._clean`, and the allow-listing
        the description generator does).
        """
        lines = [
            f"OPPORTUNITY SPACE {self.topic_id}",
            f"Statement: {self.statement}",
            f"Vertical × use case × technology: {self.triple}",
            f"State: {self.topic.get('state')} · horizon: {self.topic.get('horizon') or 'unset'}"
            f" · portfolio distance: L{self.portfolio_distance}",
        ]
        geographies = self.topic.get("geographies") or []
        if geographies:
            lines.append(f"Geographies: {', '.join(str(g) for g in geographies)}")
        personas = self.topic.get("persona_labels") or self.topic.get("personas") or []
        if personas:
            lines.append(f"Personas on this space: {', '.join(str(p) for p in personas)}")

        for name, title in (("summary", "Summary"),
                            ("what_is_changing", "What is changing"),
                            ("who_buys_and_why", "Who buys and why"),
                            ("what_orange_would_deliver", "What Orange would deliver"),
                            ("why_orange_can_win", "Why Orange can win"),
                            ("competitive_landscape", "Competitive landscape"),
                            ("risks_and_unknowns", "Risks and unknowns")):
            text = self.section_text(name)
            if text:
                lines.append(f"\n{title.upper()}\n{text}")

        size = self.best_size
        if size:
            lines.append(
                f"\nMARKET SIZE ({size.get('method_label')}, {size.get('confidence')} confidence)\n"
                f"TAM {format_eur(size.get('tam', {}).get('base'))} · "
                f"SAM {format_eur(size.get('sam', {}).get('base'))} · "
                f"SOM {format_eur(size.get('som', {}).get('base'))} per year. "
                f"These figures are COMPUTED. Do not restate them and do not derive from them."
            )

        if self.competition:
            lines.append(
                f"\nCOMPETITIVE INTENSITY: {self.competition.get('level_label')} — "
                f"{self.competition.get('meaning')}"
            )

        lines.append("\nCLOSED LIST — the ONLY Orange assets you may name:")
        assets = self.orange_assets
        lines.extend(f"  - {link.get('label')} ({link.get('node_type', '').replace('_', ' ')})"
                     for link in assets[:20])
        if not assets:
            lines.append("  (none linked — say so plainly rather than naming anything)")

        lines.append("\nCLOSED LIST — the ONLY competitors you may name:")
        names = self.competitor_names
        lines.extend(f"  - {name}" for name in names[:12])
        if not names:
            lines.append("  (none identified — say so plainly rather than naming anything)")

        for entry in ((self.analysis or {}).get("entries") or [])[:8]:
            written = entry.get("written") or {}
            if written.get("activity", {}).get("text") or written.get("differentiation"):
                lines.append(
                    f"\nON {entry.get('label')}: "
                    f"{(written.get('activity') or {}).get('text', '')} "
                    f"Differentiation already written: {written.get('differentiation', '')}"
                )

        if self.references:
            lines.append("\nPUBLISHED REFERENCES linked to this space:")
            lines.extend(f"  - {link.get('label')}" for link in self.references[:10])

        if self.research:
            from .research import as_prompt_block
            lines.append(as_prompt_block(self.research))

        return "\n".join(lines)


def load(cfg: Config, db: Database, topic_id: str) -> TopicContext:
    """One snapshot of one space. Raises if the space does not exist."""
    topic = ReadModel(cfg, db).topic(topic_id)
    if topic is None:
        raise KeyError(f"No such topic: {topic_id}")
    return TopicContext(
        topic=topic,
        description=description_for_topic(db, topic_id),
        competition=competition_for_topic(db, topic_id),
        analysis=analysis_for_topic(db, topic_id),
        sizes=sizes_for_topic(db, topic_id),
        links=topic.get("links") or [],
        cfg=cfg,
    )
