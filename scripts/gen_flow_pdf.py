"""Render the Cold Calls interaction flow as a shareable PDF.

Two-column side-by-side timeline, typeset in Courier Prime to match the
receipt aesthetic. Source of truth is src/cold_call/session.py — update the
ROWS/BRANCH tables below when the state machine changes, then re-run.

Needs reportlab, which is deliberately NOT a project dependency (the stations
never render PDFs). Run it outside the station venv:

    uv run --with reportlab python scripts/gen_flow_pdf.py
"""

from pathlib import Path

from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

REPO = Path(__file__).resolve().parent.parent
FONTS = REPO / "assets" / "fonts"
OUT = REPO / "docs" / "cold-calls-interaction-flow.pdf"

pdfmetrics.registerFont(TTFont("CP", FONTS / "CourierPrime-Regular.ttf"))
pdfmetrics.registerFont(TTFont("CP-B", FONTS / "CourierPrime-Bold.ttf"))

INK = HexColor("#1A1A1A")
DIM = HexColor("#8A8A8A")
MID = HexColor("#5C5C5C")
ACC = HexColor("#9B2C2C")
RULE = HexColor("#C8C8C8")
WASH = Color(0.96, 0.955, 0.94)

PAGE_W, PAGE_H = letter
M = 0.55 * 72
TIME_W = 0.62 * 72
GAP = 0.18 * 72
COL_W = (PAGE_W - 2 * M - TIME_W - GAP * 2) / 2
AX = M + TIME_W + GAP
BX = AX + COL_W + GAP

BODY = 8.1
LEAD = 9.8

# style -> (font, size, color)
ST = {
    "n": ("CP", BODY, INK),
    "b": ("CP-B", BODY, INK),
    "d": ("CP", BODY - 0.4, MID),
    "acc": ("CP-B", BODY, ACC),
    "q": ("CP-B", BODY, ACC),
    "qc": ("CP", BODY, INK),
}


def wrap(text, font, size, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if pdfmetrics.stringWidth(trial, font, size) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def cell_lines(cell, width):
    """Expand a list of (style, text) into rendered lines."""
    out = []
    for style, text in cell:
        if text == "":
            out.append((style, ""))
            continue
        font, size, _ = ST[style]
        for ln in wrap(text, font, size, width):
            out.append((style, ln))
    return out


# ---------------------------------------------------------------- content

ROWS = [
    ("sec", "BEFORE THE CALL"),
    ("row", "idle", [("d", "on hook, silent")], [("d", "on hook, silent")]),

    ("sec", "SOMEONE PICKS UP"),
    ("row", "0:00",
     [("b", "LIFTS THE HANDSET"), ("n", "hears: dial tone")],
     [("d", "on hook"), ("d", "hears: nothing")]),
    ("row", "0:02",
     [("n", "dial tone cuts off"),
      ("n", "hears: touch-tone dialing"),
      ("d", "dials a random famous number "
            "— Jenny's 867-5309, and friends")],
     [("d", "hears: nothing")]),

    ("sec", "RINGING"),
    ("row", "0:04",
     [("n", "hears: ringback, looping"),
      ("n", "brrr—brrr ... brrr—brrr"),
      ("d", "waits up to 30 seconds")],
     [("acc", ">>> THE PRINTER BUZZES"),
      ("n", "one buzz every 2 seconds"),
      ("d", "The handset does not ring. The "
            "receipt printer is the bell — it "
            "is what recruits a stranger who "
            "has not opted in yet.")]),
    ("row", "0:10",
     [("n", "ringback stops")],
     [("b", "LIFTS THE HANDSET")]),

    ("sec", "BOTH HANDSETS UP — THE QUIET MOMENT"),
    ("row", "0:10",
     [("n", "hears: nothing"),
      ("b", "the receipt prints"),
      ("d", "a prompt from this side's "
            "department")],
     [("n", "hears: nothing"),
      ("b", "the receipt prints"),
      ("d", "a different prompt, from the "
            "other department")]),
    ("note", "Both printers run before any audio starts. Takes 5–15 seconds, "
             "and it is silent on both ends. This gap either reads as anticipation "
             "or as “this thing is broken” — which one depends on whether "
             "the paper is visibly moving where they can see it."),

    ("sec", "THE OPERATOR"),
    ("row", "0:18",
     [("qc", "hears:"),
      ("q", "“One moment please, your call "
            "is being connected.”")],
     [("qc", "hears, the same moment:"),
      ("q", "“One moment please, your call "
            "is being connected.”")]),

    ("sec", "CONNECTED"),
    ("row", "0:22",
     [("n", "voice  ----------->"),
      ("n", "<-----------  earpiece"),
      ("d", "rain / city ambience mixed "
            "softly underneath")],
     [("n", "<-----------  earpiece"),
      ("n", "voice  ----------->"),
      ("d", "rain / city ambience mixed "
            "softly underneath")]),
    ("note", "They talk. They read each other their prompts. They answer with "
             "stamps, stickers, and tape on the easel between them — no pens. "
             "It runs as long as they both stay on the handset. There is no time limit."),

    ("sec", "EITHER SIDE HANGS UP"),
    ("row", "—",
     [("b", "HANGS UP"),
      ("d", "or the other side does "
            "— it works the same either way")],
     [("n", "still holding the handset"),
      ("n", "hears: a click, then a busy "
            "tone, looping until they hang "
            "up too")]),
    ("row", "+1s",
     [("d", "both on hook — ready for the "
            "next pair")],
     [("d", "both on hook — ready for the "
            "next pair")]),
]

BRANCH = [
    ("sec", "IF NOBODY ANSWERS"),
    ("row", "0:04",
     [("n", "hears: ringback, 30 seconds")],
     [("d", "printer buzzing, unanswered")]),
    ("row", "0:34",
     [("qc", "hears:"),
      ("q", "“We're sorry. The number you "
            "have dialed is not in service. "
            "Please hang up and try again.”")],
     [("d", "still on hook")]),
    ("row", "0:40",
     [("n", "click, then busy tone until "
            "they hang up")],
     [("d", "—")]),
]


# ---------------------------------------------------------------- drawing

class Doc:
    def __init__(self, path):
        self.c = canvas.Canvas(str(path), pagesize=letter)
        self.c.setTitle("Cold Calls — Interaction Flow")
        self.c.setAuthor("Seattle Design Nerds")
        self.c.setSubject("Bureau of Ambient Belonging · SAM Remix 2026")
        self.y = 0
        self.page = 0
        self.new_page(first=True)

    def new_page(self, first=False):
        if not first:
            self.footer()
            self.c.showPage()
        self.page += 1
        self.y = PAGE_H - M
        if first:
            self.title()
        self.col_heads()

    def footer(self):
        c = self.c
        c.setFillColor(DIM)
        c.setFont("CP", 6.6)
        c.drawString(M, M - 16, "Cold Calls · Bureau of Ambient Belonging "
                                "· SAM Remix 2026")
        c.drawRightString(PAGE_W - M, M - 16, f"{self.page}")

    def title(self):
        c = self.c
        c.setFillColor(INK)
        c.setFont("CP-B", 21)
        c.drawString(M, self.y - 16, "COLD CALLS")
        c.setFont("CP", 9)
        c.setFillColor(MID)
        c.drawString(M, self.y - 30, "What one call looks like, side to side")
        c.setFont("CP", 7.6)
        c.setFillColor(DIM)
        c.drawRightString(PAGE_W - M, self.y - 16,
                          "BUREAU OF AMBIENT BELONGING")
        c.drawRightString(PAGE_W - M, self.y - 26, "SAM REMIX 2026")
        self.y -= 44
        c.setStrokeColor(INK)
        c.setLineWidth(1.1)
        c.line(M, self.y, PAGE_W - M, self.y)
        self.y -= 15
        c.setFont("CP", 7.8)
        c.setFillColor(MID)
        for ln in wrap("Two strangers pick up handsets on opposite sides of an "
                       "easel. Either side can be the caller — whoever lifts "
                       "first becomes Side A for that call. The roles are not "
                       "fixed to a physical side.",
                       "CP", 7.8, PAGE_W - 2 * M):
            c.drawString(M, self.y, ln)
            self.y -= 9.6
        self.y -= 8

    def col_heads(self):
        c = self.c
        c.setFillColor(INK)
        c.setFont("CP-B", 8.4)
        c.drawString(AX, self.y - 8, "SIDE A")
        c.drawString(BX, self.y - 8, "SIDE B")
        c.setFont("CP", 7.2)
        c.setFillColor(DIM)
        c.drawString(AX + pdfmetrics.stringWidth("SIDE A ", "CP-B", 8.4),
                     self.y - 8, "the caller")
        c.drawString(BX + pdfmetrics.stringWidth("SIDE B ", "CP-B", 8.4),
                     self.y - 8, "the receiver")
        self.y -= 13
        c.setStrokeColor(RULE)
        c.setLineWidth(0.6)
        c.line(M, self.y, PAGE_W - M, self.y)
        self.y -= 12

    def room(self, h):
        if self.y - h < M + 6:
            self.new_page()

    def section(self, label):
        self.room(30)
        c = self.c
        self.y -= 4
        c.setFillColor(ACC)
        c.setFont("CP-B", 7.4)
        c.drawString(M, self.y, label.upper())
        w = pdfmetrics.stringWidth(label.upper(), "CP-B", 7.4)
        c.setStrokeColor(RULE)
        c.setLineWidth(0.6)
        c.line(M + w + 8, self.y + 2.4, PAGE_W - M, self.y + 2.4)
        self.y -= 10

    def row(self, time, a, b):
        la = cell_lines(a, COL_W)
        lb = cell_lines(b, COL_W)
        h = max(len(la), len(lb)) * LEAD
        self.room(h + 8)
        c = self.c
        top = self.y

        c.setFillColor(DIM)
        c.setFont("CP", 7.4)
        c.drawString(M, top - BODY, time)

        for x, lines in ((AX, la), (BX, lb)):
            yy = top - BODY
            for style, text in lines:
                font, size, col = ST[style]
                c.setFont(font, size)
                c.setFillColor(col)
                c.drawString(x, yy, text)
                yy -= LEAD

        self.y = top - h - 5.5

    def note(self, text):
        lines = wrap(text, "CP", 7.6, PAGE_W - 2 * M - 22)
        h = len(lines) * 9.4 + 10
        self.room(h + 6)
        c = self.c
        top = self.y + 2
        c.setFillColor(WASH)
        c.rect(M, top - h, PAGE_W - 2 * M, h, stroke=0, fill=1)
        c.setFillColor(ACC)
        c.rect(M, top - h, 2.2, h, stroke=0, fill=1)
        c.setFillColor(MID)
        c.setFont("CP", 7.6)
        yy = top - 12
        for ln in lines:
            c.drawString(M + 12, yy, ln)
            yy -= 9.4
        self.y = top - h - 8

    def render(self, rows):
        for item in rows:
            if item[0] == "sec":
                self.section(item[1])
            elif item[0] == "note":
                self.note(item[1])
            else:
                _, t, a, b = item
                self.row(t, a, b)

    def save(self):
        self.footer()
        self.c.save()


d = Doc(OUT)
d.render(ROWS)
d.y -= 6
d.render(BRANCH)

d.room(14)
d.y -= 1
d.c.setStrokeColor(INK)
d.c.setLineWidth(1.1)
d.c.line(M, d.y, PAGE_W - M, d.y)
d.y -= 11
d.c.setFillColor(DIM)
d.c.setFont("CP", 6.8)
d.c.drawString(M, d.y, "Timings from src/cold_call/session.py. Conversation "
                       "length is unbounded; all other durations are fixed.")
d.save()

print(f"wrote {OUT}  ({OUT.stat().st_size:,} bytes)")
