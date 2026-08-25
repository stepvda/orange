"""A document described once, emitted in any of five formats.

WHY THIS EXISTS. Pre-sales asked for the format to be their choice: a battlecard
as PDF for the car park, as Word because the bid manager edits everything, as
ODF because some of the estate is LibreOffice. The obvious implementation —
a renderer per (document x format) — is 7 documents by 3 formats plus 4 decks by
3, which is thirty-three places for the same battlecard to say something
slightly different. Within a month two of them disagree and nobody knows which
is right.

So a document is DESCRIBED here, as an ordered list of blocks, and the emitters
in `emit/` each know how to put one block on a page. Adding a format is one
emitter. Changing what the battlecard says is one edit, in one file, and every
format follows.

CHARTS ARE THE INTERESTING CASE. A chart cannot be a block of text, and the
formats do not have a common drawing model. `Chart` therefore carries up to
three renderings of the same picture, and each emitter takes the best one it
can use:

  `flowable`   reportlab geometry — vector, exact, used by the PDF emitter.
                 Always present: it is the definition of the picture.
  `pptx`       native PowerPoint shapes, so a deck arrives EDITABLE. The
                 architect who needs to move one box can, instead of redrawing
                 the slide. Optional; only the deck charts have it.
  raster       neither of the above. `png()` renders the flowable through a
                 one-page PDF and rasterises it, which is how a chart reaches
                 Word and ODF without a third and fourth implementation of the
                 same geometry.

The raster path is a deliberate trade, and it is the right way round: the two
formats people EDIT (PPTX) and the one they SEND (PDF) get true vector output,
and the fallback only applies where a chart is being read rather than worked on.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas

#: Text width of the A4 documents, and the width every chart is built against.
USABLE_WIDTH = A4[0] - 34 * mm


# ---------------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------------

@dataclass
class Kicker:
    """The small coloured line above a title — the space's own id and triple."""
    text: str


@dataclass
class Heading:
    text: str
    level: int = 2          # 1 title · 2 section · 3 sub-section


@dataclass
class Para:
    text: str
    small: bool = False     # the muted supporting register
    bold: bool = False
    #: Inline `<b>` is honoured by the PDF emitter's markup parser and stripped
    #: by the others, so a caller may always write it and never has to know
    #: which emitter will read it.
    markup: bool = False


@dataclass
class Bullets:
    items: list[str]


@dataclass
class Callout:
    """A banner that has to be noticed — a missing input, an honest gap."""
    text: str
    tone: str = "warn"      # warn | note


@dataclass
class KPIs:
    """Three or four figures across the page. Values are strings: every one of
    them is computed elsewhere and formatted once, and re-deriving here is how
    two documents start disagreeing about the same quantity."""
    cells: list[tuple[str, str]]                 # (value, caption)
    tones: list[str] = field(default_factory=list)   # '' | 'accent' | a status band


@dataclass
class Table:
    headers: list[str]
    rows: list[list[str]]
    #: Relative column widths, summing to anything — normalised per emitter.
    widths: list[float] = field(default_factory=list)


@dataclass
class Chart:
    """One picture, in as many renderings as the emitters can use."""
    build: Callable[[float], Any]                        # width -> reportlab Flowable
    caption: str = ""
    #: (deck, slide, top) -> None. Native PowerPoint shapes where they exist.
    pptx: Callable[..., None] | None = None
    #: Height in millimetres for the rasterised path, when the flowable's own
    #: height would be wrong for a page it is not being laid out on.
    raster_scale: float = 1.0

    def png(self, width: float = USABLE_WIDTH, dpi: int = 220) -> bytes:
        """The picture as PNG bytes, for the emitters with no drawing model.

        Rendered through a one-page PDF sized exactly to the flowable rather
        than to A4, so there is no margin to crop off afterwards and the image
        lands in Word at the aspect ratio it was designed at.
        """
        import fitz  # PyMuPDF — imported here so the PDF path never needs it

        flowable = self.build(width)
        _, height = flowable.wrapOn(None, width, A4[1])
        buffer = io.BytesIO()
        surface = pdfcanvas.Canvas(buffer, pagesize=(width, height))
        flowable.drawOn(surface, 0, 0)
        surface.showPage()
        surface.save()
        buffer.seek(0)
        with fitz.open(stream=buffer.read(), filetype="pdf") as document:
            pixmap = document[0].get_pixmap(dpi=dpi, alpha=False)
            return pixmap.tobytes("png")

    def size_mm(self, width: float = USABLE_WIDTH) -> tuple[float, float]:
        flowable = self.build(width)
        _, height = flowable.wrapOn(None, width, A4[1])
        return width / mm, height / mm


@dataclass
class PageBreak:
    pass


@dataclass
class Spacer:
    mm: float = 4.0


Block = (Kicker | Heading | Para | Bullets | Callout | KPIs | Table | Chart
         | PageBreak | Spacer)


# ---------------------------------------------------------------------------
# Documents and decks
# ---------------------------------------------------------------------------

@dataclass
class Document:
    """A flowing document: the PDF, Word and ODF text formats."""
    title: str
    subject: str
    blocks: list[Any] = field(default_factory=list)

    def add(self, *blocks: Any) -> "Document":
        self.blocks.extend(b for b in blocks if b is not None)
        return self


@dataclass
class Slide:
    """One slide. `chart` draws under the bullets when both are present."""
    title: str = ""
    subtitle: str = ""
    bullets: list[str] = field(default_factory=list)
    notes: str = ""
    chart: Chart | None = None
    kind: str = "content"          # cover | section | content
    strapline: str = ""
    rows: list[tuple[str, str]] = field(default_factory=list)   # provenance slide


@dataclass
class Deck:
    """A presentation: the PowerPoint, ODF presentation and PDF formats."""
    title: str
    subject: str
    slides: list[Slide] = field(default_factory=list)

    def add(self, *slides: Slide) -> "Deck":
        self.slides.extend(s for s in slides if s is not None)
        return self


# ---------------------------------------------------------------------------

def plain(text: str) -> str:
    """Strip the inline markup the PDF emitter understands.

    Word, ODF and Markdown each have their own emphasis mechanism and none of
    them is `<b>`. Rather than making every caller ask which emitter it is
    writing for, the markup is written once in reportlab's dialect and removed
    where it would show up as literal angle brackets.
    """
    out, depth = [], 0
    for char in str(text or ""):
        if char == "<":
            depth += 1
        elif char == ">":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(char)
    return "".join(out)
