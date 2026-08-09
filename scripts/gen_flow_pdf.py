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
     [("n", "hears: ringback, twice"),
      ("n", "brrr—brrr ... brrr—brrr"),
      ("d", "two cadences, 12 seconds")],
     [("acc", ">>> THE PRINTER BUZZES"),
      ("n", "one buzz every 2 seconds"),
      ("d", "The handset does not ring. The "
            "receipt printer is the bell — it "
            "is what recruits a stranger who "
            "has not opted in yet.")]),

    ("sec", "ON HOLD"),
    ("row", "0:16",
     [("qc", "ringback ends, hears:"),
      ("q", "“This call requires another "
            "participant to continue holding "
            "the line…”"),
      ("d", "over hold music, recurring "
            "every 20 seconds — one minute "
            "of it, fading out at the end")],
     [("d", "printer still buzzing, "
            "unanswered")]),
    ("row", "up to 1:16",
     [("n", "hold music stops")],
     [("b", "LIFTS THE HANDSET")]),

    ("sec", "BOTH HANDSETS UP"),
    ("row", "+0s",
     [("qc", "hears:"),
      ("q", "“Both participants are now "
            "present.”")],
     [("n", "hears: dial tone, then "
            "touch-tone dialing")]),
    ("note", "Side B hears its own dial tone and dialing on pickup, mirroring what "
             "the caller heard when they first lifted the handset — both people got "
             "to make a call. Side A's line runs at the same time and is timed to "
             "roughly the same length."),

    ("sec", "THE HEADS-UP"),
    ("row", "+4s",
     [("qc", "hears:"),
      ("q", "“Printing your questionnaire "
            "now.”")],
     [("qc", "hears, the same moment:"),
      ("q", "“Printing your questionnaire "
            "now.”")]),

    ("sec", "THE PRINT"),
    ("row", "+6s",
     [("b", "the receipt prints"),
      ("d", "a prompt from this side's "
            "department")],
     [("b", "the receipt prints"),
      ("d", "a different prompt, from the "
            "other department")]),
    ("note", "Both printers run with nothing else on the bus — the phones and the "
             "printers share one USB controller, so audio never overlaps a print. "
             "It is fast and loud on purpose: the machine chattering out a foot of "
             "paper is the event, not a wait to be filled."),

    ("sec", "THE BRIEFING"),
    ("row", "+18s",
     [("qc", "hears:"),
      ("q", "“Greetings from the Seattle "
            "Municipal Office of Social "
            "Climate. You've been contracted "
            "by one of our sub-agencies to "
            "investigate a particular aspect "
            "of the social phenomenon known "
            "as the Seattle Freeze. You will "
            "soon be connected to a fellow "
            "investigator and given a printed "
            "questionnaire. Read the question "
            "aloud to them, then document "
            "their response on your "
            "questionnaire using the writing "
            "instruments provided, before "
            "posting your form to the board "
            "with an adhesive seal.”")],
     [("qc", "hears, the same moment:"),
      ("q", "(the same line)")]),
    ("note", "The briefing runs after the print, not before it, so the paper is "
             "already in their hands while the voice explains what to do with it. "
             "About 28 seconds. This is the only thing that teaches the conceit — "
             "the receipt carries its procedure, but nobody reads a form they have "
             "not been told to care about."),

    ("sec", "THE OPERATOR"),
    ("row", "+46s",
     [("qc", "hears:"),
      ("q", "“One moment please, your call "
            "is being connected.”")],
     [("qc", "hears, the same moment:"),
      ("q", "“One moment please, your call "
            "is being connected.”")]),

    ("sec", "CONNECTED"),
    ("row", "+50s",
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
     [("n", "hears: ringback, twice (12s)")],
     [("d", "printer buzzing, unanswered")]),
    ("row", "0:16",
     [("n", "hold music, one minute, "
            "message every 20 seconds"),
      ("d", "fades out over the last 4 "
            "seconds — the wait audibly "
            "ends before the intercept says "
            "so")],
     [("d", "printer buzzing, unanswered")]),
    ("row", "1:16",
     [("qc", "hears:"),
      ("q", "“We're sorry. The number you "
            "have dialed is not in service. "
            "Please hang up and try again.”")],
     [("d", "still on hook")]),
    ("row", "1:22",
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
        self.c.setSubject("Seattle Municipal Office of Social Climate · Seattle Design Festival 2026")
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
        c.drawString(M, M - 16, "Cold Calls · Office of Social Climate "
                                "· Seattle Design Festival 2026")
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
                          "OFFICE OF SOCIAL CLIMATE")
        c.drawRightString(PAGE_W - M, self.y - 26, "SEATTLE DESIGN FESTIVAL 2026")
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
_footer = (
    "All of this is implemented in src/cold_call/session.py and has been run "
    "on the hardware. Times before the receiver answers are exact. The +Ns "
    "marks after it are clip lengths plus an assumed 12s print — the print "
    "takes as long as it takes, so everything after it shifts with it. "
    "Conversation length is unbounded."
)
for _line in wrap(_footer, "CP", 6.8, PAGE_W - 2 * M):
    d.c.drawString(M, d.y, _line)
    d.y -= 8.6
d.save()

print(f"wrote {OUT}  ({OUT.stat().st_size:,} bytes)")
