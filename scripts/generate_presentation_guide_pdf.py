"""Generate the companion presenter's guide for the CTO deck.

A readable, printable document: the narrative, the 25-minute run of show, one page
per slide (what is on it, what to say, what to point at, what you will be asked),
the objection bank, stakeholder lenses and the numbers reference.

Usage:
    python scripts/generate_presentation_guide_pdf.py
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "EXECUTIVE_PRESENTATION_GUIDE.pdf"
DECK = "presentation/EXECUTIVE_PRESENTATION.pptx"

PAGE_W, PAGE_H = A4
MARGIN_X = 16 * mm
MARGIN_TOP = 17 * mm
MARGIN_BOT = 15 * mm
WIDTH = PAGE_W - 2 * MARGIN_X

# --------------------------------------------------------------------------- palette
NAVY = colors.HexColor("#0E1B2E")
INK = colors.HexColor("#1B2432")
BLUE = colors.HexColor("#2F6FED")
BLUE_LT = colors.HexColor("#E8F0FE")
VIOLET = colors.HexColor("#6E45C8")
VIOLET_LT = colors.HexColor("#F0EBFB")
TEAL = colors.HexColor("#147D7D")
TEAL_LT = colors.HexColor("#E6F4F4")
AMBER = colors.HexColor("#946200")
AMBER_LT = colors.HexColor("#FDF3E1")
RED = colors.HexColor("#9B2C2C")
RED_LT = colors.HexColor("#FBEAEA")
GREEN = colors.HexColor("#276749")
GREEN_LT = colors.HexColor("#E9F5EE")
GREY = colors.HexColor("#4A5568")
MUTED = colors.HexColor("#718096")
LIGHT = colors.HexColor("#F4F6FA")
BORDER = colors.HexColor("#D8DFE9")
WHITE = colors.white

TITLE = "Presenting the engineering transformation"
SUBTITLE = ("A slide-by-slide guide to the 13-slide CTO deck: the story, the script, "
            "the evidence and the questions you should expect")
CLASSIFICATION = "Head of DevOps & Analytics  ·  25 October 2026  ·  Internal — for decision"


# --------------------------------------------------------------------------- fonts
def register_fonts() -> tuple[str, str, str]:
    """Use Segoe UI when available so the guide matches the deck's typography."""
    folder = Path("C:/Windows/Fonts")
    files = {
        "Segoe": "segoeui.ttf",
        "Segoe-Bold": "segoeuib.ttf",
        "Segoe-Italic": "segoeuii.ttf",
        "Segoe-Light": "segoeuil.ttf",
    }
    if all((folder / name).exists() for name in files.values()):
        for name, filename in files.items():
            pdfmetrics.registerFont(TTFont(name, str(folder / filename)))
        pdfmetrics.registerFontFamily(
            "Segoe", normal="Segoe", bold="Segoe-Bold", italic="Segoe-Italic",
            boldItalic="Segoe-Bold",
        )
        return "Segoe", "Segoe-Bold", "Segoe-Light"
    return "Helvetica", "Helvetica-Bold", "Helvetica"


FONT, FONT_B, FONT_L = register_fonts()


def styles() -> dict[str, ParagraphStyle]:
    base = dict(fontName=FONT, textColor=INK)

    def style(name: str, **overrides) -> ParagraphStyle:
        params = dict(base)
        params.update(overrides)
        return ParagraphStyle(name, **params)

    return {
        "body": style("body", fontSize=9.2, leading=13.2, spaceAfter=4.4),
        "body_snug": style("body_snug", fontSize=9.2, leading=12.8, spaceAfter=2.0),
        "lead": style("lead", fontSize=10.0, leading=14.2, spaceAfter=6.0, textColor=GREY),
        "bullet": style("bullet", fontSize=9.0, leading=12.8, leftIndent=10,
                        bulletIndent=1, spaceAfter=2.8),
        "h1": style("h1", fontSize=17.0, leading=20.0, textColor=NAVY,
                    fontName=FONT_B, spaceBefore=0, spaceAfter=1),
        "eyebrow": style("eyebrow", fontSize=7.6, leading=9.4, textColor=BLUE,
                         fontName=FONT_B, spaceAfter=2.5),
        "h2": style("h2", fontSize=9.8, leading=12.2, textColor=VIOLET,
                    fontName=FONT_B, spaceBefore=4, spaceAfter=2),
        "label": style("label", fontSize=7.2, leading=9.0, textColor=MUTED,
                       fontName=FONT_B, spaceAfter=3),
        "table": style("table", fontSize=7.8, leading=10.2),
        "table_sm": style("table_sm", fontSize=7.2, leading=9.5),
        "table_head": style("table_head", fontSize=7.6, leading=9.6,
                            textColor=WHITE, fontName=FONT_B),
        "cover_title": style("cover_title", fontSize=21, leading=25,
                             textColor=WHITE, fontName=FONT_B),
        "cover_sub": style("cover_sub", fontSize=9.6, leading=13.0,
                           textColor=colors.HexColor("#C9D6E3")),
        "cover_meta": style("cover_meta", fontSize=7.4, leading=10.0,
                            textColor=colors.HexColor("#9FB2C8")),
        "cover_eyebrow": style("cover_eyebrow", fontSize=7.6, leading=9.4,
                               textColor=colors.HexColor("#8FB6FF"), fontName=FONT_B),
        "script": style("script", fontSize=9.4, leading=13.8, spaceAfter=0),
        "slide_body": style("slide_body", fontSize=9.8, leading=13.8, spaceAfter=2.6),
        "slide_script": style("slide_script", fontSize=10.2, leading=14.8, spaceAfter=0),
        "detail": style("detail", fontSize=9.5, leading=13.4, spaceAfter=2.4),
        "qa_q": style("qa_q", fontSize=8.8, leading=11.6, textColor=NAVY,
                      fontName=FONT_B, spaceAfter=1.5),
        "qa_a": style("qa_a", fontSize=8.6, leading=12.0, spaceAfter=0),
        "transition": style("transition", fontSize=8.6, leading=11.6, textColor=GREY),
        "time": style("time", fontSize=8.2, leading=10.0, textColor=BLUE,
                      fontName=FONT_B, alignment=2),
        "kpi_value": style("kpi_value", fontSize=15.5, leading=17.5,
                           textColor=NAVY, fontName=FONT_B, alignment=TA_CENTER),
        "kpi_label": style("kpi_label", fontSize=6.9, leading=8.4, textColor=GREY,
                           alignment=TA_CENTER),
        "kpi_note": style("kpi_note", fontSize=6.2, leading=7.6, textColor=MUTED,
                          alignment=TA_CENTER),
        "callout_title": style("callout_title", fontSize=7.6, leading=9.6,
                               textColor=NAVY, fontName=FONT_B, spaceAfter=2),
    }


S = styles()


# --------------------------------------------------------------------------- helpers
def P(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, S[style])


def bullets(items: list[str], style: str = "bullet") -> list[Paragraph]:
    return [Paragraph(f"&bull;&nbsp;&nbsp;{item}", S[style]) for item in items]


def rule(color=NAVY, thickness=1.2, space_before=2, space_after=6) -> list:
    bar = Table([[""]], colWidths=[WIDTH], rowHeights=[thickness])
    bar.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return [Spacer(1, space_before), bar, Spacer(1, space_after)]


def gradient_rule(space_after=6) -> Table:
    bar = Table([["", "", ""]], colWidths=[WIDTH / 3] * 3, rowHeights=[1.6])
    bar.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), BLUE),
        ("BACKGROUND", (1, 0), (1, 0), VIOLET),
        ("BACKGROUND", (2, 0), (2, 0), colors.HexColor("#C9B6F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return bar


def section(number: str, title: str, kicker: str = "") -> list:
    parts: list = [P(f"SECTION {number}", "eyebrow"), P(title, "h1")]
    if kicker:
        parts += [Spacer(1, 3), P(kicker, "lead")]
    parts += rule()
    parts.append(Spacer(1, 3))
    return parts


def table(rows, widths, *, size: float = 7.5, header: bool = True, zebra: bool = True,
          header_bg=NAVY, bold_first: bool = False, valign_top: bool = True) -> Table:
    body = S["table"] if size >= 7.5 else S["table_sm"]
    head = S["table_head"]
    data = []
    for index, row in enumerate(rows):
        style = head if (header and index == 0) else body
        data.append([Paragraph(str(cell), style) for cell in row])

    tbl = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP" if valign_top else "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4.6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4.6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, BORDER),
    ]
    if header:
        commands += [("BACKGROUND", (0, 0), (-1, 0), header_bg),
                     ("LINEBELOW", (0, 0), (-1, 0), 0.5, header_bg)]
    if zebra:
        start = 1 if header else 0
        for row_index in range(start, len(data)):
            if (row_index - start) % 2 == 1:
                commands.append(("BACKGROUND", (0, row_index), (-1, row_index), LIGHT))
    if bold_first:
        for row_index in range(1, len(data)):
            data[row_index][0].style = ParagraphStyle(
                "bf", parent=body, fontName=FONT_B, textColor=NAVY)
    tbl.setStyle(TableStyle(commands))
    return tbl


def callout(title: str, body, *, tone=BLUE, bg=BLUE_LT, width: float = WIDTH) -> Table:
    inner = [P(title, "callout_title")]
    if isinstance(body, str):
        inner.append(P(body, "script"))
    elif isinstance(body, (list, tuple)):
        inner.extend(body)
    else:
        inner.append(body)
    cell = Table([[inner]], colWidths=[width - 9])
    cell.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    wrapper = Table([["", cell]], colWidths=[9, width - 9])
    wrapper.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), tone),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return wrapper


def label(text: str, color=MUTED) -> Paragraph:
    return Paragraph(text, ParagraphStyle("lbl", parent=S["label"], textColor=color))


def kpi_tiles(items) -> Table:
    cells = []
    for value, name, note, accent in items:
        inner = Table([[P(value, "kpi_value")], [P(name, "kpi_label")], [P(note, "kpi_note")]],
                      colWidths=[WIDTH / len(items) - 6])
        inner.setStyle(TableStyle([
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("LEFTPADDING", (0, 0), (-1, -1), 1),
            ("RIGHTPADDING", (0, 0), (-1, -1), 1),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("LINEABOVE", (0, 0), (-1, 0), 2.0, accent),
        ]))
        cells.append(inner)
    row = Table([cells], colWidths=[WIDTH / len(items)] * len(items))
    row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("BOX", (0, 0), (-1, -1), 0.4, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER),
    ]))
    return row


# --------------------------------------------------------------------------- canvas
class GuideCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved: list[dict] = []

    def showPage(self) -> None:  # noqa: N802 - reportlab API
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._saved)
        for index, state in enumerate(self._saved, start=1):
            self.__dict__.update(state)
            self._decorate(index, total)
            super().showPage()
        super().save()

    def _decorate(self, page: int, total: int) -> None:
        if page == 1:
            return
        self.saveState()
        self.setStrokeColor(BORDER)
        self.setLineWidth(0.5)
        self.line(MARGIN_X, PAGE_H - MARGIN_TOP + 7, PAGE_W - MARGIN_X, PAGE_H - MARGIN_TOP + 7)
        self.setFont(FONT, 6.8)
        self.setFillColor(MUTED)
        self.drawString(MARGIN_X, PAGE_H - MARGIN_TOP + 10, TITLE)
        self.drawRightString(PAGE_W - MARGIN_X, PAGE_H - MARGIN_TOP + 10,
                             "Companion to EXECUTIVE_PRESENTATION.pptx")
        self.line(MARGIN_X, MARGIN_BOT - 2, PAGE_W - MARGIN_X, MARGIN_BOT - 2)
        self.drawString(MARGIN_X, MARGIN_BOT - 11, "Cyncly  ·  Internal — for decision")
        self.drawRightString(PAGE_W - MARGIN_X, MARGIN_BOT - 11, f"Page {page} of {total}")
        self.restoreState()


# --------------------------------------------------------------------------- page 1
def page_cover() -> list:
    story: list = []
    band = Table(
        [[P("PRESENTER'S GUIDE", "cover_eyebrow")],
         [P(TITLE, "cover_title")],
         [P(SUBTITLE, "cover_sub")],
         [Spacer(1, 8)],
         [P(CLASSIFICATION, "cover_meta")]],
        colWidths=[WIDTH],
    )
    band.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, 0), 16),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 16),
        ("TOPPADDING", (0, 1), (-1, -1), 2),
    ]))
    story += [band, Spacer(1, 16)]

    story.append(P("How to use this guide", "h2"))
    story += bullets([
        "<b>Read the story first (section 01).</b> Everything else is detail; if you can deliver the "
        "story, the deck takes care of itself.",
        "<b>Rehearse the run of show (section 02).</b> 25 minutes, 13 slides; the timing matters more "
        "than the completeness.",
        "<b>Use one page per slide while preparing.</b> Each page gives you what is on it, what to say, "
        "what to point at, the question you are likely to get and the line that moves you on.",
        "<b>Keep sections 03–07 for the room.</b> The objection bank, stakeholder lenses, numbers "
        "reference and decision-capture template are the pages you will want open beside you.",
    ])
    story.append(Spacer(1, 6))
    story.append(callout(
        "The frame to hold in your head",
        "This deck is a <b>decision memo</b>, not a status report. The CTO should leave knowing three "
        "things: the migration is working, the method around it is not, and there are four decisions "
        "that unlock the next quarter. If the conversation never reaches those decisions, the "
        "presentation has failed regardless of how well the slides were received.",
        tone=VIOLET, bg=VIOLET_LT,
    ))
    story.append(Spacer(1, 12))

    story.append(P("Contents", "h2"))
    rows = [
        ["01&nbsp;&nbsp;The story you are telling &nbsp;·&nbsp; p2",
         "Slide 1&nbsp;&nbsp;Cover &nbsp;·&nbsp; p4"],
        ["02&nbsp;&nbsp;Run of show and room mechanics &nbsp;·&nbsp; p3",
         "Slide 2&nbsp;&nbsp;Executive summary &nbsp;·&nbsp; p5"],
        ["03&nbsp;&nbsp;The objection bank &nbsp;·&nbsp; p17",
         "Slide 3&nbsp;&nbsp;Target architecture &nbsp;·&nbsp; p6"],
        ["04&nbsp;&nbsp;Same deck, different stakeholders &nbsp;·&nbsp; p18",
         "Slide 4&nbsp;&nbsp;Golden path &nbsp;·&nbsp; p7"],
        ["05&nbsp;&nbsp;Numbers reference and glossary &nbsp;·&nbsp; p19",
         "Slide 5&nbsp;&nbsp;AI-enabled engineering &nbsp;·&nbsp; p8"],
        ["06&nbsp;&nbsp;Decision capture and follow-up &nbsp;·&nbsp; p20",
         "Slide 6&nbsp;&nbsp;Measurement spine &nbsp;·&nbsp; p9"],
        ["07&nbsp;&nbsp;Evidence map &nbsp;·&nbsp; p21",
         "Slide 7&nbsp;&nbsp;Evidence &nbsp;·&nbsp; p10"],
        ["", "Slide 8&nbsp;&nbsp;Operating model &nbsp;·&nbsp; p11"],
        ["", "Slide 9&nbsp;&nbsp;Roadmap &nbsp;·&nbsp; p12"],
        ["", "Slide 10&nbsp;&nbsp;Risks &nbsp;·&nbsp; p13"],
        ["", "Slide 11&nbsp;&nbsp;The choice &nbsp;·&nbsp; p14"],
        ["", "Slide 12&nbsp;&nbsp;Decisions &nbsp;·&nbsp; p15"],
        ["", "Slide 13&nbsp;&nbsp;Closing &nbsp;·&nbsp; p16"],
    ]
    story.append(table(rows, [WIDTH / 2] * 2, header=False, zebra=False, size=7.4))
    story.append(Spacer(1, 12))

    story.append(P("The decision at a glance", "h2"))
    decisions = [
        ("D1", "Golden path", "Inherit one governed pipeline instead of porting 1,500", BLUE),
        ("D2", "One definition", "Publish the four DORA metrics from one Gold source", VIOLET),
        ("D3", "Five controls", "Enforce them on all new pipelines from day one", AMBER),
        ("D6", "Stop-list", "Stop three activities to fund the platform team", GREEN),
    ]
    cells = []
    for code, name, desc, accent in decisions:
        code_style = ParagraphStyle("d", fontName=FONT_B, fontSize=9.2, textColor=accent)
        name_style = ParagraphStyle("dn", fontName=FONT_B, fontSize=8.4, textColor=NAVY)
        desc_style = ParagraphStyle("dd", fontName=FONT, fontSize=6.9, leading=9, textColor=GREY)
        inner = Table([
            [Paragraph(f"<b>{code}</b>", code_style)],
            [Paragraph(name, name_style)],
            [Paragraph(desc, desc_style)],
        ], colWidths=[WIDTH / 4 - 10])
        inner.setStyle(TableStyle([
            ("LINEABOVE", (0, 0), (-1, 0), 2.0, accent),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ]))
        cells.append(inner)
    strip = Table([cells], colWidths=[WIDTH / 4] * 4)
    strip.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("BOX", (0, 0), (-1, -1), 0.4, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER),
    ]))
    story.append(strip)
    return story


# --------------------------------------------------------------------------- page 2
def page_story() -> list:
    story = section(
        "01", "The story you are telling",
        "One arc, four beats. If you only rehearse one thing, rehearse this — the slides are evidence "
        "for the story, not the story itself.",
    )

    story.append(callout(
        "The opening line — say it before anything else",
        "&ldquo;The migration is working. The method around it is not. I am asking for four decisions "
        "today so the next wave starts on a platform we can defend, rather than a faster version of "
        "the problem.&rdquo;",
        tone=BLUE, bg=BLUE_LT,
    ))
    story.append(Spacer(1, 8))

    beats = [
        ["Beat", "What you say", "The slide that proves it"],
        ["<b>Situation</b>",
         "Five Azure DevOps organizations, ~1,000 repositories and ~1,500 pipelines are consolidating "
         "onto one GitHub Enterprise platform. Repository migration is ahead of plan — the irreversible "
         "work is landing, and history and permissions are intact.",
         "Slide 2 (working card), slide 3 (end state)"],
        ["<b>Complication</b>",
         "Pipeline conversion is behind because we convert one repository at a time, which reproduces "
         "the duplication that made the estate expensive. Security enforcement is a quarterly audit "
         "rather than a control. And the numbers are disputed, so progress cannot be proven.",
         "Slide 2 (stuck / costs), slide 7 (limits)"],
        ["<b>Resolution</b>",
         "Re-scope: keep migrating, replace per-repository porting with one golden path plus a "
         "migration factory, enforce five controls on new work now, publish one DORA definition from "
         "one Gold source, and gate full funding on Day-90 evidence.",
         "Slides 3–9 (architecture, roadmap)"],
        ["<b>Ask</b>",
         "Approve D1 (golden-path-first), D2 (one metric definition), D3 (enforced controls) and D6 "
         "(the stop-list) this month. D4 follows in month 2, D5 in month 6.",
         "Slide 12 (decisions)"],
    ]
    story.append(table(beats, [24 * mm, WIDTH - 24 * mm - 42 * mm, 42 * mm], size=7.6,
                       bold_first=False))
    story.append(Spacer(1, 8))

    story.append(P("Three sentences that must land", "h2"))
    story += bullets([
        "<b>&ldquo;The hard, irreversible work is working — protect it.&rdquo;</b> This buys you "
        "credibility before you deliver the criticism.",
        "<b>&ldquo;Converting pipelines one at a time re-creates the problem.&rdquo;</b> This makes the "
        "change of method a logical consequence, not a preference.",
        "<b>&ldquo;Judge me at Day 90, on five thresholds we can all see.&rdquo;</b> This converts a "
        "year-long budget request into a bounded, falsifiable commitment.",
    ])
    story.append(Spacer(1, 6))

    story.append(P("What not to do", "h2"))
    story += bullets([
        "Do not open with the org chart, the tooling history or the migration statistics. The CTO needs "
        "the decision, then the evidence.",
        "Do not blame delivery teams for forking pipelines or disputing metrics. The method and the "
        "measurement made those behaviours rational.",
        "Do not defend every number. Volunteer the limits on slide 7 — it is what makes the other "
        "numbers believable.",
        "Do not leave without a decision, or without an explicit &ldquo;not yet, because…&rdquo;. A "
        "polite ending is a failed meeting.",
    ])

    story.append(Spacer(1, 10))
    story.append(callout(
        "If the slot collapses to ten minutes",
        "<b>Present slides 1 → 2 → 7 → 11 → 12 and stop.</b> That is stakes, argument, evidence, "
        "choice, ask. Everything else is supporting material that can travel as the pre-read.",
        tone=AMBER, bg=AMBER_LT,
    ))
    story.append(PageBreak())
    return story


# --------------------------------------------------------------------------- page 3
def page_runbook() -> list:
    story = section(
        "02", "Run of show, timing and room mechanics",
        "Twenty-five minutes: eighteen presenting, seven deciding. Protect the decision time — it is "
        "the only part the CTO cannot get back later.",
    )

    rows = [
        ["#", "Slide", "Min", "Purpose in the room"],
        ["1", "Cover", "0:30", "Set the stakes and name the ask"],
        ["2", "Executive summary", "3:00", "Land the whole argument while attention is highest"],
        ["3", "Target architecture", "2:30", "One org, one path, one measurement spine; Azure Boards stays"],
        ["4", "Golden path and controls", "2:30", "The method change: converted once, not 1,500 times"],
        ["5", "AI-enabled engineering", "1:30", "Judgement: applied where measurable and governable"],
        ["6", "Measurement spine", "2:00", "Analytics is a gated pipeline, not a dashboard"],
        ["7", "The numbers and their limits", "2:30", "Credibility: what we can defend, and what we cannot"],
        ["8", "Operating model", "1:30", "Named owners and written decision rights"],
        ["9", "Roadmap and Day-90 gate", "2:00", "A bounded commitment with falsifiable thresholds"],
        ["10", "Risks and stop-list", "2:00", "Capacity is the binding constraint; here is the trade"],
        ["11", "Recommendation", "2:30", "Re-scope beats accelerate or pause — and here is the cost"],
        ["12", "Decisions requested", "2:00", "Four decisions this month; stop talking after the ask"],
        ["13", "Closing \u2014 questions and discussion", "5:00+", "Steer the discussion to decisions, not opinions"],
    ]
    story.append(table(rows, [8 * mm, 52 * mm, 13 * mm, WIDTH - 73 * mm], size=7.6))
    story.append(Spacer(1, 10))

    story.append(P("Before the room", "h2"))
    story += bullets([
        "<b>Send the deck 48 hours ahead</b> with one sentence: &ldquo;For decision: four items on "
        "slide 12; 25 minutes on the calendar.&rdquo;",
        "<b>Prepare two evidence tabs:</b> the repository (for the DORA report and the gates) and Power "
        "BI Desktop open on page 1 of the report, ready to refresh.",
        "<b>Know the four numbers cold:</b> 38.33 deployments per project-month, 20.5 h median lead "
        "time, 0.87% change failure rate, 2.0 h median restore — and the confidence label for each.",
        "<b>Agree the decision list with the CTO's chief of staff</b> so the meeting ends in a decision "
        "rather than an action to schedule another meeting.",
        "<b>Decide your concession in advance.</b> If the CTO will only approve D1 and D6, what do you "
        "ask for instead? (Usually: D2 as a 30-day metric freeze, D3 as enforce-on-new-work.)",
    ])
    story.append(Spacer(1, 4))

    story.append(P("During the room", "h2"))
    story += bullets([
        "<b>Presenter View, not the projected slide.</b> Press Alt+F5 in PowerPoint; the speaker notes "
        "for every slide are written for this conversation.",
        "<b>Watch for the interruption at slide 2.</b> If the CTO starts probing there, you have their "
        "attention — answer in one sentence and return to the recommendation band.",
        "<b>Use the time check.</b> If you are two minutes behind by slide 7, cut slides 8 and 9 to "
        "headlines and go to the recommendation. Never cut slide 12.",
        "<b>Write down what they say.</b> Use the capture template on page 20; decisions get re-litigated "
        "when the record is vague.",
    ])
    story.append(Spacer(1, 4))

    story.append(callout(
        "The only three questions that matter in the room",
        "<b>1.</b> Do we accept that per-repository conversion is the wrong method? &nbsp; "
        "<b>2.</b> Do we accept one published definition of the four metrics, with its stated limits? "
        "&nbsp; <b>3.</b> Will you fund the platform team by stopping the three things on the stop-list? "
        "Everything else is detail.",
        tone=TEAL, bg=TEAL_LT,
    ))
    story.append(PageBreak())
    return story


# --------------------------------------------------------------------------- slide pages
def slide_header(number: str, part: str, title: str, minutes: str, why: str) -> list:
    head = Table(
        [[P(f"SLIDE {number}", "eyebrow"),
          P(f"<b>{minutes}</b>", "time")],
         [P(title, "h1"), ""]],
        colWidths=[WIDTH - 26 * mm, 26 * mm],
    )
    head.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("SPAN", (0, 1), (1, 1)),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return [head, Spacer(1, 2), P(part.upper(), "label"), Spacer(1, 1),
            gradient_rule(), P(why, "lead")]


def slide_page(number, part, title, minutes, why, on_page, script, point_at, qa,
               transition, watch=None, detail=None) -> list:
    story = slide_header(number, part, title, minutes, why)

    story.append(label("WHAT IS ON THE PAGE"))
    body = [Paragraph(f"&bull;&nbsp;&nbsp;{item}", S["slide_body"]) for item in on_page]
    thumb_path = ROOT / "presentation" / "assets" / "thumbs" / f"slide-{number}.jpg"
    if thumb_path.exists():
        thumb_w = 68 * mm
        caption = Paragraph(
            f"As projected  ·  slide {number}",
            ParagraphStyle("cap", fontName=FONT, fontSize=6.4, leading=8, textColor=MUTED,
                           alignment=TA_CENTER, spaceBefore=3),
        )
        pic = Table([[Image(str(thumb_path), width=thumb_w, height=thumb_w * 9 / 16)],
                     [caption]], colWidths=[thumb_w + 4 * mm])
        pic.setStyle(TableStyle([
            ("BOX", (0, 0), (0, 0), 0.5, BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        grid = Table([[body, pic]], colWidths=[WIDTH - thumb_w - 10 * mm, thumb_w + 10 * mm])
        grid.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (0, 0), 0),
            ("RIGHTPADDING", (0, 0), (0, 0), 8),
            ("LEFTPADDING", (1, 0), (1, 0), 2),
            ("RIGHTPADDING", (1, 0), (1, 0), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(grid)
    else:
        story.extend(body)
    story.append(Spacer(1, 7))

    story.append(callout("SAY THIS", Paragraph(script, S["slide_script"]),
                         tone=BLUE, bg=BLUE_LT))
    story.append(Spacer(1, 7))

    story.append(label("POINT AT"))
    story += bullets(point_at, "slide_body")
    story.append(Spacer(1, 7))

    if detail:
        story.append(label("THE DETAIL BEHIND IT"))
        story += bullets(detail, "detail")
        story.append(Spacer(1, 7))

    if watch:
        story.append(callout("WATCH OUT", watch, tone=AMBER, bg=AMBER_LT))
        story.append(Spacer(1, 7))

    q, a = qa
    story.append(KeepTogether([
        label("IF YOU GET ASKED"),
        P(q, "qa_q"),
        P(a, "qa_a"),
    ]))
    story.append(Spacer(1, 9))

    move = Table([[P("<b>→&nbsp; Move on with:</b>", "transition"), P(transition, "transition")]],
                 colWidths=[32 * mm, WIDTH - 32 * mm])
    move.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 0.6, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(move)
    story.append(PageBreak())
    return story


def slides_1_2() -> list:
    story = slide_page(
        "01", "Cover  ·  0:30", "Cover \u2014 one platform, one source of truth", "0:30",
        "This page exists to change the register of the meeting: from update to decision.",
        [
            "Three-line proposition: one platform (consolidation), one source of truth (measurement), "
            "one number we can defend (trust).",
            "Four scale numbers: 5 → 1 ADO organizations, ~1,000 repositories, ~1,500 pipelines, "
            "12 months to one platform.",
            "Three chips pre-frame the recommendation: re-scope, golden path first, Day-90 evidence gate.",
            "Cyncly lockup with the &ldquo;Make it amazing&rdquo; tagline — the deck is a company document, "
            "not a personal pitch.",
        ],
        "&ldquo;Thank you for the time. This is a decision, not a status update. Five Azure DevOps "
        "organizations become one GitHub platform, and the migration is ahead of plan. The method "
        "around it is not. I need four decisions today so the next wave starts on something we can "
        "defend.&rdquo;",
        [
            "The title first — pause after &ldquo;one number we can defend&rdquo;.",
            "The 5 → 1 stat, then ~1,500 pipelines. That contrast is the whole capacity problem in two "
            "numbers.",
            "The three chips, briefly — they preview the recommendation without spending it.",
        ],
        ("Are we asking for more money?",
         "No. The platform team is largely reallocated from the per-repository conversion effort. Two "
         "roles are new or ring-fenced — one security engineer and part of one data engineer — and both "
         "are funded by work we stop. Slide 11 has the shape."),
        "&ldquo;Let me give you the one-page version before we go anywhere near detail.&rdquo;",
        detail=[
            "The four scale numbers describe the estate, not the benefits: five organizations, ~1,000 "
            "repositories, ~1,500 pipelines, 12 months.",
            "Twelve months is the consolidation horizon; the first decision point is Day 90, and progress "
            "is reviewed monthly.",
            "The deck is designed to be read without you — every number carries a confidence label on "
            "slide 7.",
        ],
    )

    story += slide_page(
        "02", "The case for change  ·  3:00", "Executive summary — migration works; the method does not", "3:00",
        "If they remember one slide, it is this one: three facts, one recommendation, one ask.",
        [
            "<b>What is working</b> — repository migration is ahead of plan, history and permissions "
            "arrive intact, and the irreversible work is landing.",
            "<b>What is stuck</b> — pipelines converted one at a time (~1,500, mostly copy-paste), "
            "controls checked quarterly, five organizations with five definitions.",
            "<b>What it costs</b> — no deployment event in the source, disputed metrics (MTTR rests on "
            "three incidents), duplication re-created at full scale.",
            "The recommendation band: not accelerate, not pause, re-scope. Three reasons, one line each.",
            "The evidence strip: 4/4 unit tests, 3/3 quality gates, 25/25 model files, 19 visuals live.",
        ],
        "&ldquo;Three facts. Migration is working and irreversible — protect it. Pipeline conversion is "
        "behind because we convert one repository at a time, which reproduces the duplication we are "
        "paying to remove. And because the numbers are disputed, I cannot yet prove progress to you. "
        "So: not accelerate, because that scales the defect; not pause, because that stops the only "
        "workstream working; re-scope.&rdquo;",
        [
            "Card one when you say &ldquo;protect it&rdquo; — it buys you the right to criticise.",
            "Card two when you say &ldquo;the method&rdquo; — the problem is the approach, not the teams.",
            "The recommendation band when you say &ldquo;re-scope&rdquo;; do not read the full paragraph.",
        ],
        ("Why can't you prove progress today?",
         "Because the source records builds, not deployments. Frequency and failure rate are proxies, "
         "and two organizations count pipeline runs, completed builds and releases as the same thing. "
         "Slide 7 shows exactly what the numbers can and cannot support, and the rebuild converts the "
         "proxy into a real event."),
        "&ldquo;If we accept the method is the problem, the next question is what replaces it — and "
        "that is the architecture.&rdquo;",
        watch="Do not let this become a debate about migration velocity. Migration is the good news; "
              "concede it generously and move on.",
        detail=[
            "Keep &ldquo;ahead&rdquo; and &ldquo;behind&rdquo; separate: repository migration is ahead; "
            "pipeline conversion is behind. Merging them creates a false overall status.",
            "The three &ldquo;costs&rdquo; are the argument for re-scoping, not complaints about teams.",
            "Every item in the evidence strip can be inspected today: 4/4 tests, 3/3 gates, 25/25 "
            "definitions, a 19-visual report.",
        ],
    )
    return story


def slides_3_4() -> list:
    story = slide_page(
        "03", "Part A · Platform engineering  ·  2:30",
        "Target architecture \u2014 one org, one path, one metric spine", "2:30",
        "This page answers &ldquo;what does good look like?&rdquo; in six layers and one end-state diagram.",
        [
            "Six layers, each with a single accountable owner: source control, change path, execution, "
            "telemetry, measurement, consumption.",
            "The end-state diagram: five ADO organizations today → one GitHub Enterprise organization "
            "at month 12, with a deliberate decision that <b>Azure Boards remains</b> the Agile system "
            "of record in one ADO organization.",
            "Distributed coexistence during migration, consolidated end state: hosted runners by "
            "default, self-hosted only by dated exception.",
            "Four boundaries that cannot be bought around locally: OIDC only, policy as code in the "
            "pull request, every deployment emits an event, measurement reads one Gold source.",
        ],
        "&ldquo;Six layers, one owner each. The important line is on the right: five ADO organizations "
        "consolidate onto one GitHub Enterprise org, but Azure Boards stays. That is deliberate — "
        "work-item governance does not need to move for us to get the platform benefit, and moving it "
        "mid-migration would reopen traceability design for no delivery upside. We run both states in "
        "parallel, wave by wave.&rdquo;",
        [
            "Layer 2 (change path) — this is where the method changes; everything else supports it.",
            "The TODAY → TARGET boxes, then the Azure Boards box. Say &ldquo;retained&rdquo; clearly; it "
            "is the question they are most likely to ask.",
            "The boundaries list last — these are the rules that stop exceptions becoming a second "
            "platform.",
        ],
        ("Why keep Azure Boards rather than consolidate work management too?",
         "Because the benefit of consolidation comes from source control, change path and telemetry. "
         "Azure Boards carries programme planning and work-item history; moving it adds risk and "
         "reopens a design decision without improving delivery. One ADO organization remains as the "
         "system of record, and that is the target end state, not a compromise."),
        "&ldquo;The change path is the layer that matters most, so let me show you what inheritance "
        "actually means.&rdquo;",
        detail=[
            "Layer ownership is deliberate: Platform owns 1–3, Platform and SRE share 4, Data owns 5–6.",
            "One policy set is why per-team policy forks are rejected — five policy sets is how the estate "
            "became inconsistent.",
            "Hosted runners by default removes patching and network surface from the platform team; "
            "self-hosted is the only exception.",
        ],
    )

    story += slide_page(
        "04", "Part A · Platform engineering  ·  2:30", "Golden path \u2014 1,500 pipelines converted once", "2:30",
        "The core of the re-scope: one inherited path instead of 1,500 ports.",
        [
            "The delivery flow as a contract: commit → pull request → automated gates → golden path → "
            "deployment event → metric grain. Each arrow has an owner; a missing arrow is a finding.",
            "Five controls, non-waivable on new work from day one: reviewed ruleset and required "
            "checks, SHA-pinned actions, workload identity federation, attributable human approval on "
            "production, secret scanning with push protection.",
            "Runner strategy: standard hosted by default, larger hosted for heavy builds, self-hosted "
            "only for legacy products with a dated exception.",
            "The exception path: request, risk assessment in two days, CISO approval in one, monthly "
            "review, 90-day maximum — so security does not become the bottleneck.",
        ],
        "&ldquo;This is the heart of the re-scope. Today we convert pipeline by pipeline — 1,500 times. "
        "Instead a service inherits one golden path, and the flow on the top is the contract: every "
        "arrow has an owner, and a missing arrow is a finding rather than something a team works "
        "around locally. Five controls are enforced in the pull request, not in a quarterly audit. "
        "And legacy products are not exempt — they get a named, dated exception with a 3-day "
        "turnaround.&rdquo;",
        [
            "The flow, left to right, in one sweep — do not explain each box.",
            "Node 04 (golden path) when you say &ldquo;inherits&rdquo;.",
            "The five controls as a block: &ldquo;all five, on new work, from day one&rdquo;.",
            "The exception path when someone raises a legacy product — it shows you have already "
            "thought about their constraint.",
        ],
        ("What about teams whose pipelines genuinely cannot fit the pattern?",
         "They request a pattern rather than fork a pipeline. If the constraint is real, the platform "
         "team builds it into the catalogue; if it is a runner constraint, they get a governed "
         "exception with an owner and a 12-month maximum. What they do not get is a permanent fork."),
        "&ldquo;One more platform question — where AI fits, because it is the fastest way to waste "
        "money if we are not disciplined about it.&rdquo;",
        watch="Do not read the five controls aloud one by one. Say the count, name two, and offer the "
              "list. Detail here invites a tooling debate you do not need.",
        detail=[
            "1,500 pipelines means roughly 1,500 chances to diverge; inheritance collapses that to one "
            "maintained workflow.",
            "Controls are evaluated in the pull request and the verdict is attached to the commit, so the "
            "evidence exists on demand.",
            "The exception path is deliberately faster (three days) than the work it replaces, so teams "
            "have no incentive to route around it.",
        ],
    )
    return story


def slides_5_6() -> list:
    story = slide_page(
        "05", "Part A · Platform engineering  ·  1:30",
        "AI-enabled engineering — four uses, four enforced guardrails", "1:30",
        "This page is about judgement: the CTO should see that AI is applied deliberately, not sprayed.",
        [
            "Four use cases: pipeline migration copilot, code review and test generation, incident "
            "triage and postmortems, analytics co-pilot over the semantic model.",
            "Every use case carries a guardrail enforced by the platform: human review, no direct "
            "push, read-only access, no personal data, semantic layer only.",
            "A measurement panel: adoption, time to first green, DORA delta, review load — with a "
            "negative result stopping the rollout.",
            "A sequence, not a spray: assistant first, then reviewer, then bounded agent tasks with a "
            "named owner.",
        ],
        "&ldquo;AI is applied where the work is repetitive and the output is reviewable. Four use cases, "
        "each with a guardrail the platform enforces rather than a policy we hope people read. We "
        "sequence it — assistant, then reviewer, then bounded agent tasks — and we measure it against "
        "DORA. If it does not improve lead time or review load, it stops.&rdquo;",
        [
            "The 1,500-pipeline use case first: migration is where AI has the clearest economic case.",
            "The guardrail line under each card — one phrase each, not the full sentence.",
            "The measurement panel: &ldquo;capability is not a strategy; adoption is measured next to "
            "DORA&rdquo;.",
        ],
        ("Are we behind on AI compared with peers?",
         "Possibly on breadth, not on value. The constraint is not access to models — it is governance "
         "and measurement. We would rather have four use cases with evidence than twenty pilots nobody "
         "can attribute. The sequence and the DORA pairing are what make this defensible to the board."),
        "&ldquo;None of that matters if the numbers are not trusted, so let me show you the measurement "
        "spine.&rdquo;",
        detail=[
            "The migration copilot has the clearest leverage: the same conversion problem repeated 1,500 "
            "times.",
            "Analytics Q&A runs over the semantic model, never raw tables — that is what keeps answers "
            "reproducible.",
            "The sequence matters: assistant, then reviewer, then bounded agent tasks with a named owner.",
        ],
    )

    story += slide_page(
        "06", "Part B · Data engineering  ·  2:00", "Measurement spine \u2014 a gated pipeline, not a dashboard", "2:00",
        "This page turns analytics from a reporting argument into an engineering control.",
        [
            "Five stages: Bronze (raw workbook preserved, SHA-256 and row counts), Silver (typed, "
            "validated, deduplicated, rejects kept), Gold (project × calendar month, four metrics), "
            "semantic model (8 tables, 8 relationships, 17 measures), report (Power BI, 2 pages, "
            "19 visuals).",
            "Three executable gates: DQ-01 referential integrity and grain, DQ-02 temporal validity, "
            "DQ-03 metric reconciliation. All pass.",
            "Proof, not assertion: a negative test corrupts Gold and requires all three gates to fail — "
            "they do. 25/25 definition files validate against Microsoft schemas.",
            "Four rules that keep numbers honest: one owner and one definition, pairs not singles, "
            "sample sizes published, blank is not zero.",
        ],
        "&ldquo;Trusted analytics is a pipeline, not a dashboard. Raw data is preserved, validated with "
        "rejects kept rather than silently dropped, and published at one grain. Three gates run in "
        "CI — and a negative test corrupts the data and requires all three to fail. They do. That is "
        "why the gates mean something. And a metric cannot be redefined inside a dashboard; any change "
        "is a version bump with a release note.&rdquo;",
        [
            "The five stages as a single left-to-right sentence; do not explain Bronze, Silver and Gold "
            "separately unless asked.",
            "The three PASS cards — &ldquo;all three green, and proven able to fail&rdquo;.",
            "The rules panel when you say &ldquo;blank is not zero&rdquo;: it is the rule that stops a "
            "reliability metric becoming fiction.",
        ],
        ("Is this just a one-off dashboard for the case study?",
         "No. The report is the visible layer; the asset is the pipeline and the definition. The semantic "
         "model is plain text and reviewable, the gates run in CI, and the whole thing regenerates from "
         "source. That is what makes it survivable after the person who built it moves on."),
        "&ldquo;So what do those numbers actually support? This is the slide I would want you to "
        "challenge.&rdquo;",
        detail=[
            "Gold is published at project × calendar month; two projects across six months yields nine "
            "rows because one month is absent from the source.",
            "345 builds, 149 linkable commits and 3 incidents reconcile row by row — that is the evidence "
            "behind &ldquo;trusted&rdquo;.",
            "Blank is preserved by design: four rows are partial and five minimal, each with a recorded "
            "reason.",
        ],
    )
    return story


def slide_7() -> list:
    story = slide_page(
        "07", "Part B · Data engineering  ·  2:30", "Evidence — four DORA metrics and their honest limits", "2:30",
        "Your credibility slide. Volunteer the limits before you are asked; it makes every other number "
        "believable.",
        [
            "Four figures, each with a confidence label: 38.33 deployments per project-month "
            "(<b>proxy</b>), 20.5 h median lead time (<b>high</b>, n = 149, 98.0% link coverage), "
            "0.87% change failure rate (<b>directional</b>, 3 of 345), 2.0 h median restore "
            "(<b>indicative</b>, n = 3).",
            "What the source cannot support: no deployment event (no environment or release marker), no "
            "commit-to-build link for one project, and no project-month where all four metrics are "
            "observed — 4 of 9 rows are partial, 5 minimal.",
            "The live Power BI report: two pages, 19 visuals, verified in Desktop.",
            "What becomes answerable after the rebuild: discrete deployments, exact failure attribution, "
            "credible restore time, and team improvement with paired metrics and published sample sizes.",
        ],
        "&ldquo;These are the four figures we can defend today: 38.33 deployments per project-month, "
        "20.5 hours median lead time, 0.87% change failure rate, 2.0 hours median restore. Recomputable, "
        "reconciled row by row. And here is what they are not: there is no deployment event in the "
        "source, so frequency and failure rate are proxies; MTTR rests on three incidents, which is "
        "indicative and not a trend. I would rather show you the limit than have you discover it in a "
        "board pack.&rdquo;",
        [
            "The PROXY and INDICATIVE chips while saying &ldquo;what they are not&rdquo;.",
            "The bottom-left limits list — do not skip it.",
            "The live report: &ldquo;this is the working report, not a mock-up&rdquo;.",
            "The right-hand panel when you say what the rebuild buys.",
        ],
        ("So what is our real deployment frequency?",
         "As a release event, we do not know yet — and I will not invent it. What we know is completed "
         "builds per project-month, which is a defensible proxy if it is labelled. The rebuild adds a "
         "deployment event with service, environment and commit, and then the answer becomes exact."),
        "&ldquo;If the numbers are the constraint, the operating model is how we fix it.&rdquo;",
        watch="This is the slide where a CTO tests whether you will oversell. Do not round up, do not "
              "say &ldquo;roughly&rdquo; when you mean a proxy, and never quote MTTR without n = 3.",
        detail=[
            "38.33 is 345 completed builds divided by 9 project-months — a build proxy, not a release "
            "count.",
            "98.0% link coverage means 149 of 152 commit links resolve; 12 impossible links were rejected "
            "and counted, not repaired.",
            "Change failure rate matches deployment-caused incidents to the project-month because no "
            "event-level deployment link exists.",
            "The rebuild adds a deployment event with service, environment and commit; that is when the "
            "answer becomes exact.",
        ],
    )
    return story


def slides_8_9() -> list:
    story = slide_page(
        "08", "Part C · Strategy and leadership  ·  1:30",
        "Operating model \u2014 named owners, written decision rights", "1:30",
        "This page answers the governance question: who decides, and why escalation should stop.",
        [
            "Four owners: platform product owner (catalogue, golden path, runner strategy — with "
            "authority to say no), security engineering (policy-as-code and the exception register), "
            "data and measurement (definitions, reconciliation gate, one Gold source), application "
            "teams (service quality on the golden path).",
            "Decision rights in writing: new pattern — Head of DevOps; security exception — CISO; metric "
            "definition — Head of DevOps with Data; re-platform or retire — CTO.",
            "Service tiers T0, T1, T2 and Exception, each with a platform commitment and a support "
            "model; the exception tier is the only one with an expiry date.",
            "Capability gaps close by month 3: product owner month 1, policy-as-code month 2, "
            "deployment events month 3, metric stewardship month 2.",
        ],
        "&ldquo;The platform is run as a product with a named owner who can say no to off-catalogue work. "
        "Decision rights are written down, so the programme stops escalating: I approve patterns, the "
        "CISO grants security exceptions, metric definitions are mine with Data, and re-platform or "
        "retire is yours. Service tiers turn platform commitments into something product teams can "
        "plan against — and notice the exception tier is the only one with an expiry date.&rdquo;",
        [
            "The four owner rows, one phrase each — the authority to say no is the point.",
            "The decision-rights column: &ldquo;one named role, not a committee&rdquo;.",
            "The Exception tier last — it shows the model is honest about reality.",
        ],
        ("Who decides if one of my teams needs an exception?",
         "The CISO, on a written request with a reason and an end date. Risk assessment takes two "
         "working days, approval one, and the exception is registered and visible. It is renewable once "
         "with justification, then closed. If it would exceed 90 days it escalates to you and the CISO "
         "jointly."),
        "&ldquo;That model only works if the sequence is credible, so here is the year and the gate.&rdquo;",
        detail=[
            "The product owner sits in the platform team; the role is accountability, not a steering "
            "committee.",
            "Tier commitments map to change-path availability: 99.9% for T0, 99.5% for T1, business hours "
            "for T2.",
            "Capability gaps have dates: product owner month 1, policy-as-code month 2, deployment events "
            "month 3.",
        ],
    )

    story += slide_page(
        "09", "Part C · Strategy and leadership  ·  2:00", "Roadmap — five waves, twelve months, one hard gate", "2:00",
        "This page replaces a year-long budget request with a bounded, falsifiable commitment.",
        [
            "Five waves with windows and exit criteria: Wave 0 baseline (days 1–30), Wave 1 golden path "
            "v1 (months 2–3), Wave 2 first consolidation (months 4–6), Wave 3 scale and settle "
            "(months 7–9), Wave 4 one organization (months 10–12).",
            "The Day-90 gate, five thresholds: at least 10 services on the golden path, 100% of new "
            "pipelines controlled, every figure recomputes, at least one organization "
            "decommission-ready, no regression in median lead time for onboarded teams.",
            "Staffing behind the plan: 4 platform, 1 security, 1 data, 2 migration, plus product owners "
            "per wave.",
            "One milestone is already achieved: the measurement baseline is published from one Gold "
            "source (M3).",
        ],
        "&ldquo;Five waves, each with an exit criterion that can fail. But the important date is Day 90, "
        "not month 12. If the golden path is not adopted, the controls are not measured, the numbers do "
        "not recompute, or developer friction rises — we change the approach while it is still cheap. "
        "A year-long plan with no intermediate gate is a budget request, not a plan.&rdquo;",
        [
            "The timeline nodes — wave number and window only, not the scope text.",
            "The Day-90 panel: read the five threshold values, not the descriptions.",
            "The bottom line: &ldquo;M3 is already achieved&rdquo; — evidence that the plan has started.",
        ],
        ("Why twelve months and not six?",
         "Five organizations and roughly a thousand repositories, sequenced by dependency: you cannot "
         "decommission an organization until it is empty, and you cannot empty it until the products "
         "have a funded route off legacy runners. The waves are sized to the dependency chain, not to "
         "enthusiasm. The 90-day gate is what protects us if the chain moves."),
        "&ldquo;The plan is credible; the risk is capacity, and that is the next page.&rdquo;",
        detail=[
            "Waves follow dependencies: an organization cannot be decommissioned until it is empty, and "
            "it cannot empty until its products have a funded route off legacy runners.",
            "M3 is already achieved — the baseline is published from one Gold source — and repository "
            "migration is ahead of plan.",
            "The Day-90 gate is a continue-or-change decision, not a funding cliff.",
        ],
    )
    return story


def slides_10_11() -> list:
    story = slide_page(
        "10", "Part C · Strategy and leadership  ·  2:00", "Risks — capacity is the constraint; here is the stop-list", "2:00",
        "This page makes the stop-list inevitable rather than political.",
        [
            "Five live risks, each with an early warning and a named holder. R5 is highlighted: one team "
            "is asked to migrate, build and measure — warning is golden-path backlog age above two "
            "weeks, held by the CTO.",
            "The stop-list to create capacity: per-repository pipeline porting outside pilots, team DORA "
            "dashboards that cannot reconcile to Gold, and quarterly audits as the primary control.",
            "Risk appetite in plain words: security very low; delivery pace moderate (waves slip before "
            "controls slip); exceptions low and time-bound; metric precision high (publish blank rather "
            "than wrong).",
            "What would change the recommendation: pilot rejection above a third, exception volume "
            "growing weekly, or migration stalling for two waves.",
        ],
        "&ldquo;The risk that decides the year is capacity. The same small team is being asked to migrate "
        "an estate, build a platform and fix the measurement. That is why the stop-list on the right "
        "matters: stop per-repository porting outside pilots, stop unreconciled team dashboards, and "
        "stop treating quarterly audits as the control. That is what funds the platform team — it is "
        "not a request for more people, it is a request to stop doing three things.&rdquo;",
        [
            "R5 first, then the stop-list — the two are one argument.",
            "One early warning to show the mechanism is real (fork count, exception volume, backlog age).",
            "The appetite row for metric precision: &ldquo;we would rather publish blank than "
            "wrong&rdquo;.",
        ],
        ("What happens if a wave slips?",
         "A wave date slipping is a scheduling change; a control slipping is an incident. We protect the "
         "controls and re-plan the wave with you. If migration stalls for two waves, the response is to "
         "consolidate to three organizations first rather than to keep pushing a plan that is not "
         "moving."),
        "&ldquo;Which brings me to the recommendation itself — including what it costs us.&rdquo;",
        watch="Do not present the risk list as bad news. Present it as the reason the stop-list is "
              "disciplined rather than arbitrary.",
        detail=[
            "R5 is the only risk that can invalidate the whole plan, because it attacks the team doing all "
            "three workstreams.",
            "Each stop-list item frees specific capacity: porting effort, dashboard maintenance, audit "
            "preparation.",
            "The appetite statements are pre-agreed answers, so future escalations have a reference instead "
            "of a debate.",
        ],
    )

    story += slide_page(
        "11", "Part D · Executive recommendation  ·  2:30",
        "The choice \u2014 re-scope, do not accelerate or pause", "2:30",
        "The decision page: three options, the cost of each, and the investment shape.",
        [
            "Three options with verdicts: accelerate (reject — scales the defect), pause (reject — stops "
            "the only workstream working), re-scope (recommended).",
            "Each option carries its cost, including the recommended one: teams give up bespoke pipelines "
            "and views.",
            "Invest / stop / defer: fund the golden path and factory, policy-as-code, the measurement "
            "spine, and time-boxed legacy isolation; stop porting, unreconciled dashboards and audits as "
            "control; defer Azure Boards retirement, full decommission before wave exit, autonomous "
            "production change and historical backfill.",
            "Investment shape: 4 platform FTE reallocated from conversion, 1 security FTE ring-fenced, "
            "1 data FTE part-funded by retiring dashboards, legacy isolation charged to the owning "
            "product, tooling neutral to down.",
        ],
        "&ldquo;Three options. Acceleration keeps the one-at-a-time conversion and carries duplication "
        "forward at 1,500-times cost. A pause stops the only workstream that is working. Re-scoping "
        "continues the migration, turns conversion into a golden path and a factory, applies controls "
        "to new work now, and gates full funding at Day 90. And it has a cost: teams with unusual needs "
        "lose the right to fork a pipeline, and bespoke dashboards are retired. That is the trade I am "
        "recommending.&rdquo;",
        [
            "The two REJECT verdicts first — one line each, no elaboration.",
            "The recommended card when you say &ldquo;and it has a cost&rdquo; — this is the moment "
            "that earns trust.",
            "The investment strip: &ldquo;mostly reallocated, not new&rdquo;.",
        ],
        ("What do we give up if we re-scope?",
         "Three things: per-repository freedom to fork a pipeline, team dashboards that cannot reconcile "
         "to Gold, and the option to keep every legacy product exactly as it is. In exchange: one path "
         "to production, one number, and a platform team that is not permanently firefighting."),
        "&ldquo;Six decisions follow. Four are needed this month.&rdquo;",
        detail=[
            "Re-scope is the only option that preserves the migration lead without scaling the defect.",
            "Investment is mostly reallocation: four platform FTE, one security FTE, one part-funded data "
            "FTE.",
            "The defer list is deliberate: Azure Boards retirement, full decommission before wave exit, "
            "autonomous change and historical backfill.",
        ],
    )
    return story


def slides_12_13() -> list:
    story = slide_page(
        "12", "Part D · Executive recommendation  ·  2:00", "Decisions — six requested, four needed this month", "2:00",
        "The close. Everything before this page exists to make these six rows easy to approve.",
        [
            "Six decisions with owners and dates. D1 golden-path-first, D2 one DORA definition, D3 five "
            "enforced controls, D6 the stop-list — all needed in month 1. D4 legacy runner funding in "
            "month 2, D5 re-platform or retire in month 6.",
            "What the CTO will see after approval: policy published in week 1, controls in enforce mode "
            "and the exception register live in weeks 2–4, the baseline from one Gold source in month 2, "
            "and the Day-90 gate review in month 3.",
            "The closing band restates the ask in one sentence.",
        ],
        "&ldquo;Six decisions. Four this month: golden-path-first, one metric definition, enforced "
        "controls, and the stop-list. Approve those and Wave 1 starts on a golden path with enforceable "
        "controls and one agreed number. Everything else in this brief follows from those four. What "
        "would you like to challenge?&rdquo;",
        [
            "The four Month 1 rows, in order — D1, D2, D3, D6.",
            "The right-hand timeline: what they get for saying yes, and when.",
            "The closing band, then stop talking.",
        ],
        ("What if we approve D1 and D3 but defer D2?",
         "Then we can start Wave 1, but leadership reporting stays disputed and the Day-90 gate cannot "
         "be judged on reproducibility. If D2 needs more time, the fallback is a 30-day metric freeze "
         "with one owner named, so we stop publishing numbers we cannot reconcile in the interim."),
        "That is the ask — I would rather spend the remaining time on your questions than on more "
        "slides.",
        detail=[
            "D1–D3 and D6 are needed in month 1; D4 in month 2; D5 in month 6.",
            "The right-hand timeline is what the CTO receives for saying yes, with dates.",
            "This is four decisions, not a budget approval; the funding gate is separate and later.",
        ],
    )

    story += slide_page(
        "13", "Closing  ·  5:00+", "Questions and discussion", "5:00+",
        "A closing page that steers the conversation back to decisions instead of opinions.",
        [
            "Three discussion prompts, each framed as a decision: scope of Wave 1 and its owner, the "
            "legacy products that need a dated exception, and the evidence required at Day 90.",
            "The decision recap: D1 golden path, D2 one definition, D3 controls, D6 stop-list.",
            "Presenter and date, so the closing page can be left on screen during discussion.",
        ],
        "&ldquo;Three things I would value your view on. Which services do you want in the first wave — "
        "and who owns the outcome? Which legacy products genuinely need a dated exception, and until "
        "when? And what would you need to see at Day 90 to release full-estate funding? If we answer "
        "those, the rest of the plan writes itself.&rdquo;",
        [
            "The three prompts in order — each one converts an opinion into a decision you can record.",
            "The recap pills when the discussion drifts: bring it back to the four decisions.",
        ],
        ("Can we revisit the scope of the programme after Day 90?",
         "Yes — that is the point of the gate. If the evidence holds, we release full-estate funding. "
         "If it does not, we re-scope to one pattern or re-plan the waves with you. The gate is a "
         "commitment device in both directions."),
        "Close the meeting by reading back the decisions, the owners and the dates — then send them in "
        "writing within 24 hours.",
        watch="Do not end on &ldquo;thank you&rdquo;. End on the decision recap; the Q&A page is for "
              "their questions, not for a graceful exit.",
        detail=[
            "The three prompts map to the three things that can still change the plan: scope, constraints "
            "and evidence.",
            "Record the answers using the template on page 20; decisions get re-litigated when the record "
            "is vague.",
            "Leave this page on screen — it holds the four decisions while people talk.",
        ],
    )
    return story


# --------------------------------------------------------------------------- objection bank
def page_objections() -> list:
    story = section("03", "The objection bank",
        "Twelve questions you should expect, with answers short enough to deliver without notes. "
        "Answer in one sentence, then stop — the silence is what invites the decision.",
    )

    rows = [
        ["Question", "Answer"],
        ["Why not just convert pipelines faster?",
         "Acceleration scales the defect: per-repository conversion carries duplication forward at "
         "1,500-times cost. The golden path converts once and is inherited."],
        ["What does this actually cost?",
         "Mostly reallocated: four platform FTE from the conversion effort, one security FTE "
         "ring-fenced, one data FTE part-funded by retiring dashboards. Tooling is neutral to down as "
         "five organizations consolidate."],
        ["Why keep Azure Boards?",
         "Work-item governance does not need to move for the platform benefit. Retiring it mid-migration "
         "reopens traceability design without improving delivery."],
        ["Can I trust these numbers?",
         "They recompute from source and reconcile row by row; three gates must pass and a negative test "
         "proves they can fail. Where a figure is a proxy, it is labelled one."],
        ["Why is MTTR only 2.0 hours?",
         "Because it rests on three incidents at 2.03 hours. It is labelled indicative, not a trend, and "
         "I would not put it in a board pack as a performance claim."],
        ["What if teams do not adopt the golden path?",
         "That is the Day-90 gate: ten services or we re-scope to one pattern. The product owner has "
         "authority to say no to off-catalogue work, and fork count is the early warning."],
        ["Will security enforcement slow delivery down?",
         "Controls are enforced in the pull request, not in a quarterly audit. Exceptions have a 3-day "
         "turnaround, a named owner and a 90-day maximum."],
        ["Why invest in AI now?",
         "Only where work is repetitive and reviewable, with platform-enforced guardrails. It is measured "
         "alongside DORA, and a negative result stops the rollout."],
        ["Who is accountable for the measurement?",
         "The Head of DevOps and Analytics owns the definition; data engineering owns the pipeline and "
         "the reconciliation gate. A metric cannot be redefined inside a dashboard."],
        ["What happens to the team that does the work?",
         "Four platform engineers are reallocated, not added, plus one security and part of one data "
         "engineer. The stop-list is what creates the capacity — that is why it is a decision, not a "
         "preference."],
        ["If we pause instead, what is the cost?",
         "Proven migration stops, teams keep shipping on inconsistent pipelines, and restart cost plus "
         "credibility loss are both high. It also re-opens the estate to drift."],
        ["What do you need from me today?",
         "D1, D2, D3 and D6 this month. D4 in month 2, D5 in month 6. Nothing else."],
    ]
    story.append(table(rows, [62 * mm, WIDTH - 62 * mm], size=7.4))
    story.append(Spacer(1, 10))

    story.append(callout(
        "If you do not know the answer",
        "Say so, and say when you will. &ldquo;I do not have that in front of me — I will send it by "
        "Thursday.&rdquo; A CTO will forgive a missing detail far faster than an invented one, and the "
        "whole deck rests on the claim that the numbers are honest.",
        tone=AMBER, bg=AMBER_LT,
    ))
    story.append(Spacer(1, 10))

    story.append(P("Three rules for the Q&amp;A", "h2"))
    story += bullets([
        "<b>Answer in one sentence, then stop.</b> The silence is what invites the next question — or "
        "the decision.",
        "<b>Concede what is true before you correct anything.</b> &ldquo;You are right that MTTR is thin "
        "— here is why we still publish it with n = 3&rdquo; beats defending the number.",
        "<b>Separate the decision from the detail.</b> If a question needs more than a minute, offer to "
        "take it offline and return to the four decisions.",
    ])
    story.append(PageBreak())
    return story


# --------------------------------------------------------------------------- lenses
def page_lenses() -> list:
    story = section(
        "04", "Same deck, different stakeholders",
        "You will present this more than once. Keep the argument identical and change the emphasis: "
        "each audience is buying a different part of the same decision.",
    )

    rows = [
        ["Audience", "What they care about", "Slides to lead with", "What to emphasise"],
        ["CTO",
         "Decisions, cost, risk, and whether the plan can be trusted",
         "2, 7, 11, 12",
         "Four decisions this month; Day-90 gate; mostly reallocated investment."],
        ["CFO / Finance",
         "Cash, headcount and avoidable spend",
         "2, 9, 11",
         "Four FTE reallocated, not added; tooling neutral to down; legacy isolation charged to the "
         "owning product; duplication avoided at 1,500-times cost."],
        ["CISO / Security",
         "Provable controls, exception discipline, audit evidence",
         "3, 4, 8, 10",
         "Five non-waivable controls enforced in the PR; 3-day exception turnaround; register with owner "
         "and expiry; evidence per control, not a quarterly scramble."],
        ["Product and engineering leaders",
         "Speed to a compliant pipeline, and what changes for their teams",
         "3, 4, 8",
         "Time to first green under a day; service tiers; they gain a path and lose the right to fork."],
        ["Data and analytics",
         "Definitions, lineage, quality, ownership of the number",
         "6, 7",
         "One Gold source, three gates that can fail, versioned definitions, no metric redefined in a "
         "dashboard."],
        ["Board / exec committee",
         "Can progress be proven, and what is the exposure",
         "2, 7, 11",
         "Four metrics with confidence labels; one organization at month 12; funding gated at Day 90."],
        ["Delivery teams",
         "What it means for my week",
         "4, 8, 9",
         "Inherit, do not fork; exception path exists and is fast; friction is measured and the gate "
         "protects them."],
    ]
    story.append(table(rows, [30 * mm, 48 * mm, 26 * mm, WIDTH - 104 * mm], size=7.4))
    story.append(Spacer(1, 10))

    story.append(P("Two adjustments that matter", "h2"))
    story += bullets([
        "<b>With finance, lead with the stop-list, not the architecture.</b> The question is what "
        "displaces what; the platform detail is supporting evidence.",
        "<b>With security, lead with the exception path, not the controls.</b> They will assume controls "
        "exist; what they want to know is whether the process around them is usable and auditable.",
    ])
    story.append(Spacer(1, 6))
    story.append(callout(
        "The one line that works for every audience",
        "&ldquo;We are replacing 1,500 one-off conversions with one path, one number and a dated "
        "exception route — and we will prove it at Day 90 before asking for the rest.&rdquo;",
        tone=TEAL, bg=TEAL_LT,
    ))
    story.append(Spacer(1, 10))

    story.append(P("What to bring to each conversation", "h2"))
    story += bullets([
        "<b>Finance:</b> the stop-list and the reallocation table from slide 11. Do not open with the "
        "architecture; open with what is displaced.",
        "<b>Security:</b> the five controls on slide 4 and the evidence each produces. The question is "
        "not whether controls exist, but whether they are provable and usable.",
        "<b>Product and engineering leaders:</b> the service tiers on slide 8 and the time-to-first-green "
        "target. They are buying speed and predictability, not a tool.",
        "<b>Board or executive committee:</b> slides 2, 7 and 11 only — the four metrics with their "
        "confidence labels, and the Day-90 gate.",
    ])
    story.append(PageBreak())
    return story


# --------------------------------------------------------------------------- reference
def page_reference() -> list:
    story = section(
        "05", "Numbers reference and glossary",
        "Everything you might be asked to define, in the order you are likely to be asked it. "
        "If a number is not here, do not improvise it.",
    )

    story.append(kpi_tiles([
        ("38.33", "Deployments per project-month", "345 builds · 9 grain rows · proxy", BLUE),
        ("20.5 h", "Lead time for changes (median)", "n = 149 · 98.0% link coverage", TEAL),
        ("0.87 %", "Change failure rate", "3 of 345 deployments · directional", AMBER),
        ("2.0 h", "Mean time to restore (median)", "n = 3 · indicative only", RED),
    ]))
    story.append(Spacer(1, 8))

    rows = [
        ["Term", "What it means", "Why it matters in the room"],
        ["Completed build (deployment proxy)",
         "The source records a build completion, not a release event. A completed build stands in for a "
         "deployment.",
         "It is the reason frequency and failure rate are labelled proxies."],
        ["Lead time for changes",
         "Median hours from commit authoring to build completion, at the linked-commit grain.",
         "Median, not mean: the data is heavy-tailed and 12 impossible links were rejected."],
        ["Change failure rate",
         "Deployment-caused incidents divided by deployments, matched to the project-month.",
         "Directional only, because there is no event-level deployment link."],
        ["MTTR",
         "Median incident start to resolution, in hours.",
         "n = 3. Indicative; never present it as a trend."],
        ["Golden path",
         "One reusable, governed pipeline workflow that services inherit rather than copy.",
         "Converts once instead of 1,500 times; the core of the re-scope."],
        ["Policy as code",
         "Controls evaluated in the pull request, with the verdict attached to the commit.",
         "Turns compliance into a by-product of delivery rather than an audit."],
        ["OIDC federation",
         "Short-lived identity exchange between the pipeline and the cloud, with no stored secrets.",
         "Removes long-lived credentials from every pipeline."],
        ["Bronze / Silver / Gold",
         "Raw preservation; typed, validated and deduplicated; published metric grain.",
         "Explains why the numbers can be traced and recomputed."],
        ["Semantic model",
         "The Power BI layer (8 tables, 8 relationships, 17 measures) over Gold.",
         "One definition consumed by the report; no metric logic in a visual."],
        ["Day-90 gate",
         "Five thresholds that must hold to continue at the current investment.",
         "The commitment device that makes the plan falsifiable."],
        ["Exception (runner/policy)",
         "A named, dated permission for a real constraint, with an owner and expiry.",
         "How legacy products are handled without creating a second platform."],
    ]
    story.append(table(rows, [38 * mm, 66 * mm, WIDTH - 104 * mm], size=7.3))
    story.append(Spacer(1, 10))
    story.append(callout(
        "Three numbers never to round",
        "<b>0.87% is 3 of 345</b> — do not say &ldquo;under one percent&rdquo; as if it were a sample "
        "of thousands. &nbsp; <b>20.5 h has n = 149</b> — do not present it as every project; one project "
        "has no linkable commits. &nbsp; <b>2.0 h has n = 3</b> — never a trend, always indicative.",
        tone=AMBER, bg=AMBER_LT,
    ))
    story.append(PageBreak())
    return story


# --------------------------------------------------------------------------- capture
def page_capture() -> list:
    story = section(
        "06", "Decision capture and follow-up",
        "The meeting is not over when the deck ends; it is over when the decisions are written down. "
        "Fill this in during the conversation, and send it within 24 hours.",
    )

    rows = [
        ["Decision", "Owner", "Agreed / deferred", "Condition or caveat", "Evidence due"],
        ["D1 · Golden-path-first conversion", "CTO", "", "", "Policy note + amended wave list (week 1)"],
        ["D2 · One DORA definition", "CTO + Data", "", "", "Baseline published from one Gold source (month 2)"],
        ["D3 · Five controls on new pipelines", "CISO + CTO", "", "", "Coverage report + exception register (weeks 2–4)"],
        ["D4 · Legacy runner exception funding", "CTO + Product", "", "", "Named products, owners, expiry (month 2)"],
        ["D5 · Re-platform or retire legacy", "CTO", "", "", "Per-product decision with commercial owner (month 6)"],
        ["D6 · Stop-list approved", "CTO", "", "", "Stop-list published; capacity reallocated (month 1)"],
    ]
    story.append(table(rows, [48 * mm, 22 * mm, 22 * mm, 40 * mm, WIDTH - 132 * mm], size=7.2))
    story.append(Spacer(1, 12))

    story.append(P("Within 24 hours", "h2"))
    story += bullets([
        "<b>Decision note</b> — one page: what was approved, what was deferred, who owns each, and what "
        "evidence is due when.",
        "<b>Amended wave list</b> — Wave 1 scope and the named service owners, if the CTO changed the "
        "scope in the room.",
        "<b>Exception register</b> — the named legacy products, their owner, the constraint and the "
        "expiry date, even if the register is only three rows long on day one.",
        "<b>Metric freeze notice</b> — if D2 is deferred, state which figures are withdrawn from "
        "leadership reporting until they reconcile.",
    ])
    story.append(Spacer(1, 8))

    story.append(P("Signals to watch between now and Day 90", "h2"))
    signals = [
        ["Signal", "What it tells you", "Threshold for action"],
        ["Fork count of the golden-path workflow", "Adoption is failing quietly", "Rising week on week"],
        ["Exception volume", "The control design is too rigid", "Growing week on week"],
        ["Golden-path backlog age", "Capacity is being consumed by migration", "Above two weeks"],
        ["Dashboard divergence reports", "Definitions are still disputed", "Any unresolved report"],
        ["Median lead time for onboarded teams", "Developer friction is real", "Any regression"],
    ]
    story.append(table(signals, [58 * mm, 70 * mm, WIDTH - 128 * mm], size=7.4))
    story.append(Spacer(1, 12))

    story.append(callout(
        "The sentence to leave in the room",
        "&ldquo;I am not asking you to believe the plan. I am asking you to hold me to five thresholds at "
        "Day 90 — and to give me the four decisions that let me reach them.&rdquo;",
        tone=VIOLET, bg=VIOLET_LT,
    ))
    story.append(PageBreak())
    return story


# --------------------------------------------------------------------------- evidence
def page_evidence_map() -> list:
    story = section(
        "07", "Evidence map",
        "Every claim in the deck has an artefact behind it. Know where they are, in case the CTO asks "
        "for the working, and send the links with the follow-up note.",
    )

    rows = [
        ["Claim in the deck", "Artefact", "What it proves"],
        ["The DORA baseline (38.33 / 20.5 h / 0.87% / 2.0 h)",
         "analytics/gold/dora_period_summary.csv, dora_service_month.csv",
         "The published numbers, reconciled at project-month grain"],
        ["Three quality gates pass, and can fail",
         "analytics/quality-checks/dq_results.json, run_quality_checks.py --fixtures",
         "Gates are executable and the negative test forces all three to fail"],
        ["The report is real, not a mock-up",
         "analytics/dashboard/DORA_DASHBOARD.pbix, dora_powerbi_desktop.png",
         "The live report, 2 pages and 19 visuals, saved from Power BI Desktop"],
        ["The semantic model is reviewable",
         "analytics/powerbi/DORA_Project, DORA_MEASURES.dax",
         "8 tables, 8 relationships, 17 measures in plain text"],
        ["Definition files validate",
         "analytics/powerbi/validate_pbip.py, check_references.py",
         "25/25 definitions schema-valid; every visual field resolves"],
        ["Platform pattern and gates",
         ".github/workflows, src/CynclyDoraMetrics, tests/CynclyDoraMetrics.Tests",
         "PR validation, 4/4 tests, coverage artefact"],
        ["Metric definitions and limits",
         "docs/METRIC_SPEC.md, docs/METRIC_DICTIONARY.md, docs/DATA_QUALITY.md",
         "Grain, exclusions, ownership and known source defects"],
        ["Strategy, roadmap and decisions",
         "docs/DEVOPS_STRATEGY_FOR_LEADERSHIP.pdf, docs/EXECUTIVE_RECOMMENDATION.pdf",
         "The CTO briefing and the one-page decision paper"],
        ["Migration and governance",
         "docs/MIGRATION_AND_GOVERNANCE.md, docs/ARCHITECTURE.md",
         "Conversion decisions, ownership model, residual risk"],
        ["What was verified, and how",
         "docs/VALIDATION_EVIDENCE.md",
         "Commands run, results, and the defects found and fixed"],
    ]
    story.append(table(rows, [55 * mm, 66 * mm, WIDTH - 121 * mm], size=7.3))
    story.append(Spacer(1, 10))

    story.append(callout(
        "If the CTO asks for proof",
        "Do not narrate the repository. Open <b>dora_period_summary.csv</b> for the four numbers, then "
        "<b>VALIDATION_EVIDENCE.md</b> for how they were verified. Those two files answer almost every "
        "&ldquo;how do you know?&rdquo; question.",
        tone=BLUE, bg=BLUE_LT,
    ))
    story.append(Spacer(1, 10))

    story.append(P("What to send after the meeting", "h2"))
    story += bullets([
        "This guide, the deck and the one-page executive recommendation — in that order, so the CTO can "
        "delegate the detail without losing the decision.",
        "The four artefacts that back the numbers: the Gold summary, the quality-gate results, the Power "
        "BI report and the validation evidence.",
        "The decision note from page 20, within 24 hours, with owners and dates.",
    ])
    story.append(Spacer(1, 8))

    story.append(callout(
        "You are ready when you can do these three things without notes",
        "<b>1.</b> State the four decisions and who owns each. &nbsp; <b>2.</b> Explain why MTTR is "
        "labelled indicative and why that makes the other three numbers stronger, not weaker. &nbsp; "
        "<b>3.</b> Name the first three services you would put on the golden path — and why those three.",
        tone=GREEN, bg=GREEN_LT,
    ))
    return story


# --------------------------------------------------------------------------- build
def build() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)

    doc = BaseDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=MARGIN_X,
        rightMargin=MARGIN_X,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOT,
        title="Presenting the engineering transformation — presenter's guide",
        author="Head of DevOps & Analytics",
        subject=f"Companion guide to {DECK}",
        creator="scripts/generate_presentation_guide_pdf.py",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main",
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="guide", frames=[frame])])

    story: list = []
    story += page_cover()
    story.append(PageBreak())
    story += page_story()
    story += page_runbook()
    story += slides_1_2()
    story += slides_3_4()
    story += slides_5_6()
    story += slide_7()
    story += slides_8_9()
    story += slides_10_11()
    story += slides_12_13()
    story += page_objections()
    story += page_lenses()
    story += page_reference()
    story += page_capture()
    story += page_evidence_map()

    doc.build(story, canvasmaker=GuideCanvas)

    from pypdf import PdfReader

    pages = len(PdfReader(str(OUT)).pages)
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"  pages: {pages}")


if __name__ == "__main__":
    build()

