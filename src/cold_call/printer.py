"""Printer controller for Cold Calls.

Renders prompt dispatches as images and prints them on MHT-80E thermal printers.
All text is rendered via Pillow for full typographic control.
"""

from __future__ import annotations

import struct
import time
from pathlib import Path
from typing import TYPE_CHECKING

from escpos.printer import File
from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from cold_call.hardware import Side

import yaml

PRINT_WIDTH = 576  # 80mm at 203dpi (~72mm printable)
TOP_MARGIN = 64    # 8mm of leader, also part of the cut clearance
FEED_LINES = 2     # ~8.5mm at 1/6" per line — the rest of the clearance

# A 2400px dispatch (172,800 raster bytes in one GS v 0) desynced both
# printers mid-image: the firmware stopped consuming pixel data, printed the
# remainder as garbage text and swallowed the cut. The largest dispatch that
# printed cleanly was 169,200 bytes, so the real ceiling sits somewhere just
# above it. Banding the raster would avoid the limit but leaves visible gaps
# between bands, so instead we keep every dispatch comfortably under it.
MAX_RASTER_BYTES = 165_000

# Pause between the two raster commands of a dispatch, so the printer has time
# to drain rather than accumulate both halves.
RASTER_PAUSE = 0.4

ASSETS = Path(__file__).resolve().parent.parent.parent / "assets"
FONT_REG = str(ASSETS / "fonts" / "CourierPrime-Regular.ttf")
FONT_BOLD = str(ASSETS / "fonts" / "CourierPrime-Bold.ttf")

# One margin for everything that is not centered — steps, notice, rules, and
# the fields all start on the same vertical, so the receipt reads as a column
# rather than a stack of independently indented blocks.
MARGIN = 40

# Four vertical intervals, in ascending order of how much they separate. Any
# gap on the receipt is one of these; the rhythm falls apart when each block
# invents its own padding.
SPACE_XS = 12
SPACE_S = 20
SPACE_M = 36
SPACE_L = 52

# Four type sizes, in ascending order of emphasis: supporting detail, the
# instructions to carry out, the banner, and the question itself.
SIZE_SUPPORT = 16
SIZE_STEP = 18
SIZE_BANNER = 28
SIZE_QUESTION = 36

# The question takes the full page column: 496px at 21.6px per character. It
# was set at 40 with a 14-character wrap, which broke short questions into
# eight-line towers.
QUESTION_CHARS = 22
QUESTION_LEADING = 2

# How much of each stroke survives the downscale. 160 matches the fields;
# lower thins the letterforms. Thermal heads spread slightly, so print a test
# receipt before going much below this — thin strokes can drop out.
QUESTION_WEIGHT = 60

# Courier is 0.6em wide, so size 18 is 10.8px per character. The margins
# leave 45 columns and the "(n) " prefix takes four of them. The notice is a
# size smaller again, so 51 of its characters fit the same column.
STEP_CHARS = 41
NOTICE_CHARS = 51

NOTICE = ("Please follow the procedure below. "
          "Failure to comply may result in {}.")
DEFAULT_CONSEQUENCE = "further review"
ASK_STEP = "Ask the following question to the respondent:"
LISTEN_STEP = "Listen to their response."
POST_STEP = "Post your form to the board with an adhesive seal."
SIGN_OFF = "Thank you for performing your civic duties."
SIGN_OFF_MARK = 48  # width of the short rule between agency and thanks

# Data-entry fields are drawn rather than pasted, so every department shares
# one stroke weight, one margin, and one label style. Curves are drawn at
# SUPERSAMPLE and scaled down, since a 1-bit canvas cannot antialias.
FIELD_STROKE = 3
FIELD_PAD = 22

# Air between the two faces, so the pair does not read as one tall shape,
# and above the first one, so it clears the caption.
FACE_GAP = 64
FACE_TOP = 30

# The quotation marks the Polite Indifference field is built from.
QUOTE_SIZE = 59  # height of each quotation mark

# Room below a write-on rule for the word that names it.
RULE_LABEL_DROP = 26

# The invite form: height of the name-writing gap, and of an RSVP box.
INVITE_NAME_H = 54
INVITE_BOX = 64
SUPERSAMPLE = 3

# Load department metadata for seal/name lookup
_DEPTS_PATH = ASSETS / "departments.yaml"
_DEPARTMENTS: dict = {}
if _DEPTS_PATH.exists():
    with open(_DEPTS_PATH) as f:
        _DEPARTMENTS = yaml.safe_load(f).get("departments", {})


def _dept_info(theme: str) -> dict:
    """Get department metadata by theme key."""
    return _DEPARTMENTS.get(theme, {})


class PrinterConnection:
    """Persistent connection to one MHT-80E printer with auto-reconnect."""

    def __init__(self, side: Side):
        self.side = side
        self._printer: File | None = None
        self._warned = False

    @property
    def available(self) -> bool:
        """False when no printer was paired with this side at discovery."""
        return self.side.printer_dev is not None

    def _connect(self) -> File:
        """Open and initialize the printer."""
        if not self.available:
            raise OSError(f"No printer paired with side {self.side.label}")
        p = File(self.side.printer_dev)
        p._raw(b'\x1b\x40')  # ESC @ — initialize printer, clear buffer
        return p

    def _get(self) -> File:
        """Return an open printer, reconnecting if needed."""
        if self._printer is None:
            try:
                self._printer = self._connect()
            except (OSError, IOError) as e:
                # Warn once — _get is called on every print and every ring cycle
                if not self._warned:
                    print(f"  WARNING: Printer {self.side.label} "
                          f"({self.side.printer_dev or 'not connected'}): {e}")
                    self._warned = True
                raise
        self._warned = False
        return self._printer

    def _reconnect(self) -> File:
        """Force a reconnect."""
        self.close()
        return self._get()

    def buzzer_ring(self, cycles: int = 1):
        """Play a phone-ring pattern on the printer's buzzer."""
        try:
            p = self._get()
        except (OSError, IOError):
            return
        try:
            for i in range(cycles):
                p.buzzer(times=9, duration=1)
                time.sleep(1.5)
                p.buzzer(times=9, duration=1)
                if i < cycles - 1:
                    time.sleep(3.0)
        except Exception:
            self.close()

    def print_prompt(self, prompt: str, theme: str = "apathy",
                     dispatch_num: int = 0):
        """Print a prompt dispatch. Fails gracefully if printer is dead."""
        try:
            p = self._get()
        except (OSError, IOError):
            try:
                p = self._reconnect()
            except (OSError, IOError):
                return

        try:
            parts = _compose_parts(prompt, theme=theme,
                                   dispatch_num=dispatch_num)
            # The image is rotated 180°, so the last part in reading order is
            # the first one off the head — print them back to front.
            for index, part in enumerate(reversed(parts)):
                if index:
                    # Let the printer drain before the next command. If the
                    # desync was a buffer filling up rather than a per-command
                    # ceiling, sending both halves back to back would hit the
                    # same wall as one big one.
                    time.sleep(RASTER_PAUSE)
                _print_raster(p, part.rotate(180))
            # TOP_MARGIN plus this feed is the white band above the seal, and
            # also the clearance the blade needs past the print head. Trimming
            # it further starts cutting into the seal.
            p.ln(FEED_LINES)
            p.cut()
        except Exception as e:
            print(f"  WARNING: Printer {self.side.label} failed mid-print: {e}")
            self.close()

    def print_status(self, info: dict):
        """Print a startup status receipt. Fails gracefully."""
        try:
            p = self._get()
        except (OSError, IOError):
            return

        try:
            sections = []

            theme = info.get("theme", "")
            dept = _dept_info(theme) if theme else {}
            dept_name = dept.get("name", "Bureau of Ambient Belonging")

            sections.append(_render_text(
                [dept_name.upper()],
                font_path=FONT_BOLD, size=20, pad_top=16, pad_bottom=4,
            ))
            sections.append(_render_text(
                ["System Status Report"],
                size=18, pad_bottom=8,
            ))
            sections.append(_render_separator())

            kv_lines = [
                f"Host:     {info.get('host', '?')}",
                f"IP:       {info.get('ip', '?')}",
                f"Uptime:   {info.get('uptime', '?')}",
                f"Station:  {info.get('station', '?')}",
                f"Side:     {info.get('side', '?')}",
                f"Bus:      {info.get('bus', '?')}",
                f"Phone:    card {info.get('card', '?')}",
                f"Printer:  {info.get('printer_dev', '?')}",
            ]
            sections.append(_render_text(
                kv_lines, size=20, align="left", line_spacing=4,
                pad_top=8, pad_bottom=8,
            ))

            sections.append(_render_separator())
            sections.append(_render_text(
                ["Ready for calls."],
                font_path=FONT_BOLD, size=22, pad_top=8, pad_bottom=16,
            ))

            total_h = sum(s.height for s in sections)
            composite = Image.new("1", (PRINT_WIDTH, total_h), 1)
            y = 0
            for section in sections:
                composite.paste(section, (0, y))
                y += section.height

            _print_raster(p, composite.rotate(180))
            p.ln(4)
            p.cut()
        except Exception as e:
            print(f"  WARNING: Printer {self.side.label} status print failed: {e}")
            self.close()

    def close(self):
        """Close the printer connection."""
        if self._printer is not None:
            try:
                self._printer.close()
            except Exception:
                pass
            self._printer = None


def _render_text(lines, font_path=FONT_REG, size=24, align="center",
                 line_spacing=8, pad_top=0, pad_bottom=0, margin=0):
    """Render lines of text to a 1-bit image at PRINT_WIDTH."""
    font = ImageFont.truetype(font_path, size)
    ascent, descent = font.getmetrics()
    line_h = ascent + descent

    total_h = line_h * len(lines) + line_spacing * (len(lines) - 1) + pad_top + pad_bottom
    img = Image.new("1", (PRINT_WIDTH, total_h), 1)
    draw = ImageDraw.Draw(img)

    y = pad_top
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        if align == "center":
            x = (PRINT_WIDTH - tw) // 2
        elif align == "right":
            x = PRINT_WIDTH - tw - margin
        else:
            x = margin
        draw.text((x, y), line, font=font, fill=0)
        y += line_h + line_spacing

    return img


def _render_rule(dashed=True, weight=2, pad_top=SPACE_S, pad_bottom=SPACE_S,
                 length=None):
    """A rule drawn to the margins rather than typed out of hyphens.

    Typed rules ended at whatever width the character count happened to make,
    which left every rule on the receipt a different length and none of them
    aligned to the fields. Drawn ones all span the same column.
    """
    img = Image.new("1", (PRINT_WIDTH, pad_top + weight + pad_bottom), 1)
    draw = ImageDraw.Draw(img)
    y = pad_top

    # A length turns the rule into a short centred mark instead of a divider
    # spanning the column — a beat between two things, not a break.
    left = MARGIN if length is None else (PRINT_WIDTH - length) // 2
    right = (PRINT_WIDTH - MARGIN if length is None else left + length) - 1

    if dashed:
        x = left
        while x < right:
            draw.rectangle([x, y, min(x + 13, right), y + weight - 1], fill=0)
            x += 23
    else:
        draw.rectangle([left, y, right, y + weight - 1], fill=0)
    return img


def _render_separator(char="-", count=32):
    """Kept for the status receipts, which predate the drawn rules."""
    return _render_rule()


def _wrap_prompt(text: str, max_chars: int = 18,
                 balance: bool = False) -> list[str]:
    """Word-wrap a string into lines that fit the print size.

    With balance, the lines are evened out: the wrap is tightened as far as it
    can go without costing a line, which is what stops a question from ending
    on a lone orphan word.
    """
    def wrap(width: int) -> list[str] | None:
        lines: list[str] = []
        current = ""
        for word in text.split():
            if len(word) > width:
                return None
            test = f"{current} {word}".strip()
            if len(test) <= width:
                current = test
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    lines = wrap(max_chars) or [text]
    if not balance:
        return lines

    for width in range(max_chars - 1, 0, -1):
        tighter = wrap(width)
        if tighter is None or len(tighter) > len(lines):
            break
        lines = tighter
    return lines


def _draw_field(label: str, height: int, painter) -> Image.Image:
    """Draw one bounded entry field: a frame, a caption, and its contents.

    Everything the participant writes on sits inside a frame, so an open panel
    and three ruled lines read as the same kind of object. The caption lives
    inside the frame at the top left, the way a form names its own boxes, and
    the painter is handed the box that is left over.

    The canvas underneath is SUPERSAMPLE times larger and scaled at the end,
    which is what keeps drawn circles and arcs from going to staircases on a
    1-bit canvas. The painter works in final pixels.
    """
    s = SUPERSAMPLE
    canvas = Image.new("L", (PRINT_WIDTH * s, height * s), 255)
    d = _ScaledDraw(ImageDraw.Draw(canvas), s)

    x0, x1 = MARGIN, PRINT_WIDTH - MARGIN
    d.rect([x0, 0, x1 - 1, height - 1])
    d.text((x0 + FIELD_PAD, FIELD_PAD + 8), label.upper(), size=SIZE_SUPPORT,
           anchor="lm")

    painter(d, x0 + FIELD_PAD, x1 - FIELD_PAD, FIELD_PAD + 30,
            height - FIELD_PAD)

    canvas = canvas.resize((PRINT_WIDTH, height), Image.LANCZOS)
    return canvas.point(lambda v: 0 if v < 160 else 255).convert("1")


class _ScaledDraw:
    """An ImageDraw whose coordinates and widths are in final pixels."""

    def __init__(self, draw: ImageDraw.ImageDraw, scale: int):
        self._d = draw
        self._s = scale

    def _xy(self, coords):
        return [c * self._s for c in coords]

    def line(self, coords, width=FIELD_STROKE):
        self._d.line(self._xy(coords), fill=0, width=width * self._s)

    def rect(self, coords, width=FIELD_STROKE):
        self._d.rectangle(self._xy(coords), outline=0, width=width * self._s)

    def ellipse(self, coords, width=FIELD_STROKE, fill=None):
        self._d.ellipse(self._xy(coords), outline=0, width=width * self._s,
                        fill=fill)

    def text(self, xy, message, size=18, anchor="mm", bold=False):
        font = ImageFont.truetype(FONT_BOLD if bold else FONT_REG,
                                  size * self._s)
        self._d.text(self._xy(xy), message, font=font, fill=0, anchor=anchor)

    def polygon(self, points, fill=0):
        self._d.polygon([(x * self._s, y * self._s) for x, y in points],
                        fill=fill)


def _ruled(labels: list[str] | None = None, count: int = 3):
    """A painter for write-on rules, each named underneath as the artwork had.

    The label sits below its own line rather than in a gutter beside it, so
    the full width of the box is available to write on.
    """
    def paint(d, x0, x1, y0, y1):
        rows = len(labels) if labels else count
        row = (y1 - y0) / rows
        for i in range(rows):
            y = y0 + row * (i + 1) - RULE_LABEL_DROP
            d.line([x0, y, x1, y], width=2)
            if labels:
                d.text(((x0 + x1) / 2, y + RULE_LABEL_DROP - 6), labels[i],
                       size=SIZE_SUPPORT, anchor="mm", bold=True)
    return paint


def _field_belonging(d, x0, x1, y0, y1):
    """Room to draw a journey line, with its terminals on the frame itself.

    The marks sit on the left and right edges rather than inset, so the line
    has the full width to travel and reads as running off the receipt — which
    is what step 3 asks for when it says to connect it to another line. START
    high and END low, the diagonal the original artwork used: a journey that
    goes somewhere rather than a level line.
    """
    for x, y, label, anchor in (
        (MARGIN, y0 + 20, "START", "lm"),
        (PRINT_WIDTH - MARGIN, y1 - 44, "END", "rm"),
    ):
        d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=0)
        d.text((x0 if anchor == "lm" else x1, y + 34), label,
               size=SIZE_SUPPORT, anchor=anchor)


def _bezier(p0, control, p1, steps=28):
    """Points along a quadratic curve, for the tails of the quote marks."""
    out = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        out.append((u * u * p0[0] + 2 * u * t * control[0] + t * t * p1[0],
                    u * u * p0[1] + 2 * u * t * control[1] + t * t * p1[1]))
    return out


# One quotation mark, in units of the ball radius, ball centred on the origin,
# y downward: a round ball with a tail that leaves it upper right, sweeps down
# and left, and tapers to a tip. That is the closing mark; the opening one is
# the same shape turned through 180 degrees.
_BALL_R = 0.82
_BALL_TO_TAIL = (0.76, -0.30)
_TAIL_OUTER = (1.06, 1.08)
_TAIL_BACK = (-0.50, 0.60)
_TAIL_INNER = (0.32, 1.06)

# The tail stops on a flat edge rather than converging to a point: the two
# curves end at these, square across the tail rather than meeting.
_TAIL_END_OUTER = (0.04, 2.00)
_TAIL_END_INNER = (-0.28, 1.90)

# How the mark sits in its own box, same units: ball plus tail tall, and a
# pair of them steps this far across.
_MARK_HEIGHT = _TAIL_END_OUTER[1] + _BALL_R
_MARK_STEP = 2.2
_MARK_LEFT = 1.0


def _quote_mark(d, cx, cy, r, closing=True):
    """One ball-and-tail mark, centred on its ball."""
    turn = 1 if closing else -1

    def at(point):
        return (cx + point[0] * r * turn, cy + point[1] * r * turn)

    ball = _BALL_R * r
    d.ellipse([cx - ball, cy - ball, cx + ball, cy + ball], fill=0)
    # The straight edge between the two curves is the squared-off end — the
    # polygon closes across it on its own.
    d.polygon([at(_BALL_TO_TAIL)]
              + [at(pt) for pt in _bezier(_BALL_TO_TAIL, _TAIL_OUTER,
                                          _TAIL_END_OUTER)]
              + [at(pt) for pt in _bezier(_TAIL_END_INNER, _TAIL_INNER,
                                          _TAIL_BACK)])


def _field_quote(d, x0, x1, y0, y1):
    """Open space between two big quotation marks.

    Ruled lines said "write here" but not what kind of thing to write. The
    quotes say it is someone else's words being recorded, which is the whole
    point of the department's activity.

    Drawn rather than set: Courier's own quotes are angular slashes that read
    as tick marks at this size, and the artwork's are wedges with no ball.
    """
    r = QUOTE_SIZE / _MARK_HEIGHT

    # Opening pair hangs from the top left, closing pair from the bottom right.
    cx, cy = x0 + _MARK_LEFT * r, y0 + 10 + (_MARK_HEIGHT - _BALL_R) * r
    _quote_mark(d, cx, cy, r, closing=False)
    _quote_mark(d, cx + _MARK_STEP * r, cy, r, closing=False)

    cx, cy = x1 - _MARK_LEFT * r, y1 - (_MARK_HEIGHT - _BALL_R) * r
    _quote_mark(d, cx, cy, r, closing=True)
    _quote_mark(d, cx - _MARK_STEP * r, cy, r, closing=True)


def _field_invitation(d, x0, x1, y0, y1):
    """The invite form the original artwork laid out: a name, a picture, RSVP.

    Built from the bottom up — the RSVP row and its labels are fixed heights,
    the name rules are fixed at the top, and the drawing box takes whatever is
    left between them.
    """
    # Name: one rule to write on, named underneath. The artwork had a second
    # rule above it, but under the field's caption it read as a stray divider.
    d.line([x0, y0 + INVITE_NAME_H, x1, y0 + INVITE_NAME_H], width=2)
    name_bottom = y0 + INVITE_NAME_H + RULE_LABEL_DROP
    d.text(((x0 + x1) / 2, name_bottom - 6), "EVENT NAME",
           size=SIZE_SUPPORT, bold=True)

    # RSVP: three boxes to tick, named underneath, sitting on the floor.
    choices = ("YES", "MAYBE", "NO")
    box_bottom = y1 - RULE_LABEL_DROP
    box_top = box_bottom - INVITE_BOX
    for i, choice in enumerate(choices):
        centre = x0 + (x1 - x0) * (2 * i + 1) / (2 * len(choices))
        d.rect([centre - INVITE_BOX / 2, box_top,
                centre + INVITE_BOX / 2, box_bottom], width=2)
        d.text((centre, y1 - 4), choice, size=SIZE_SUPPORT, anchor="mm",
               bold=True)

    rsvp_top = box_top - RULE_LABEL_DROP
    d.text(((x0 + x1) / 2, rsvp_top - 4), "RSVP (CHECK ONE)",
           size=SIZE_SUPPORT, anchor="mm", bold=True)

    # Whatever is left in the middle is the drawing box, lighter than the
    # field's own frame so the two borders do not read as equals.
    draw_top = name_bottom + SPACE_S
    draw_bottom = rsvp_top - SPACE_M
    d.rect([x0, draw_top, x1, draw_bottom], width=2)
    d.text(((x0 + x1) / 2, draw_bottom - 22), "THUMBNAIL",
           size=SIZE_SUPPORT, anchor="mm", bold=True)


def _field_faces(d, x0, x1, y0, y1):
    """Two blank faces stacked, named underneath — expected, then actual.

    Side by side, the pair read as one comparison to fill in at once. Stacked
    they read as two entries on a form, which is what they are, and each gets
    the full width of the box to draw a face into.
    """
    label_h = 34
    # The caption sits tight against the frame, so hold the first circle off
    # it — otherwise the pair starts flush under the words.
    y0 += FACE_TOP
    row = ((y1 - y0) - FACE_GAP) / 2
    size = min(x1 - x0, row - label_h)
    centre_x = (x0 + x1) / 2

    for i, label in enumerate(("EXPECTED", "ACTUAL")):
        top = y0 + (row + FACE_GAP) * i + (row - label_h - size) / 2
        d.ellipse([centre_x - size / 2, top, centre_x + size / 2, top + size])
        d.text((centre_x, top + size + 20), label, size=SIZE_SUPPORT)


# caption, height, painter
_FIELDS = {
    "ambient_belonging": ("Journey of belonging", 420, _field_belonging),
    "polite_indifference": ("Highlight of the conversation", 400, _field_quote),
    "acceptable_proximity": ("Haiku", 350, _ruled(["FIVE", "SEVEN", "FIVE"])),
    "minimal_engagement": ("Reason for minimal engagement", 200,
                       _ruled(["ONE WORD"])),
    "conditional_invitations": ("Event invitation", 700, _field_invitation),
    "deferred_enthusiasm": ("Expected and actual emotions", 840, _field_faces),
}


def _render_field(theme: str) -> list[Image.Image]:
    """The department's data-entry field, or nothing if it has no activity."""
    entry = _FIELDS.get(theme)
    if entry is None:
        return []
    caption, height, painter = entry
    return [_draw_field(caption, height, painter),
            Image.new("1", (PRINT_WIDTH, SPACE_S), 1)]


def _render_question(prompt: str) -> Image.Image:
    """The question, centred in its own column.

    Step 1 ends on a colon pointing straight at it, and the widest interval on
    the receipt sits above and below, which is what sets it apart — no frame.

    Courier Prime ships regular and bold and nothing lighter, so the weight is
    taken off the strokes at render time instead: drawn at SUPERSAMPLE and
    downscaled, then thresholded dark enough that only the core of each stroke
    survives. QUESTION_WEIGHT is the dial — lower is thinner.
    """
    lines = _wrap_prompt(prompt.upper(), max_chars=QUESTION_CHARS, balance=True)

    s = SUPERSAMPLE
    font = ImageFont.truetype(FONT_REG, SIZE_QUESTION * s)
    ascent, descent = font.getmetrics()
    line_h = ascent + descent + QUESTION_LEADING * s
    text_h = (line_h * len(lines)) // s

    big = Image.new("L", (PRINT_WIDTH * s, text_h * s), 255)
    draw = ImageDraw.Draw(big)
    y = 0
    for line in lines:
        width = draw.textlength(line, font=font)
        draw.text(((PRINT_WIDTH * s - width) / 2, y), line, font=font, fill=0)
        y += line_h
    text = big.resize((PRINT_WIDTH, text_h), Image.LANCZOS)
    text = text.point(lambda v: 0 if v < QUESTION_WEIGHT else 255).convert("1")

    return text


def _render_step(number: int, text: str) -> Image.Image:
    """One numbered instruction, runover indented under the first word."""
    prefix = f"({number}) "
    # Greedy, not balanced: these are left-aligned paragraphs, and evening the
    # lines only narrows them all, which reads as heavier wrapping.
    lines = _wrap_prompt(text, max_chars=STEP_CHARS)
    body = [prefix + lines[0]] + [" " * len(prefix) + line for line in lines[1:]]
    return _render_text(body, size=SIZE_STEP, align="left", margin=MARGIN,
                        line_spacing=4, pad_top=SPACE_XS, pad_bottom=SPACE_XS)


def _render_notice(text: str) -> Image.Image:
    """The standing warning above the procedure — same block as the steps."""
    return _render_text(_wrap_prompt(text, max_chars=NOTICE_CHARS),
                        size=SIZE_SUPPORT, align="left", margin=MARGIN,
                        line_spacing=4, pad_top=SPACE_S, pad_bottom=SPACE_S)


def _compose_parts(prompt: str, theme: str = "apathy",
                   dispatch_num: int = 0) -> list[Image.Image]:
    """Render a dispatch as the images that will be printed, in reading order.

    Returns [body] or [body, worksheet]. The split is deliberate: each part
    is sent as its own GS v 0, which keeps both well under the raster limit
    that desynced the printers, and the small feed the printer inserts
    between raster commands lands on the rule above the worksheet where it
    reads as intentional spacing rather than a seam.

    Uses department metadata from the theme for the seal, name, and tagline.
    """
    dept = _dept_info(theme)
    dept_name = dept.get("name", "Bureau of Apathy")
    tagline = dept.get("tagline", "")

    # Find seal image: prefer pre-baked small variant, fall back to full size
    seal_path = ASSETS / "images" / f"{theme}_seal_sm.png"
    if not seal_path.exists():
        seal_path = ASSETS / "images" / f"{theme}_seal.png"
    if not seal_path.exists():
        seal_path = ASSETS / "images" / "ambient_belonging_seal_sm.png"

    # Build sections top-to-bottom as they appear on the receipt
    sections = []

    # Top margin (8mm). This prints last — the image is rotated 180° — so it
    # doubles as clearance before the cut, on top of the ln(4) feed. It was
    # 30mm back when receipts came off as a continuous ribbon and the
    # whitespace was the only separation between them.
    sections.append(Image.new("1", (PRINT_WIDTH, TOP_MARGIN), 1))

    # Seal
    seal = Image.open(seal_path).convert("1")
    if seal.width < PRINT_WIDTH:
        centered = Image.new("1", (PRINT_WIDTH, seal.height), 1)
        centered.paste(seal, ((PRINT_WIDTH - seal.width) // 2, 0))
        seal = centered
    sections.append(seal)

    # Header. The form number is the department's prefix plus the dispatch
    # counter, so both sides of one call carry the same number.
    form_id = dept.get("form", None)
    form_line = (f"{form_id}-{dispatch_num:04d}" if form_id
                 else f"Form {dispatch_num:04d}")
    sections.append(_render_text(["DATA COLLECTION QUESTIONNAIRE"],
                                  font_path=FONT_BOLD, size=SIZE_BANNER,
                                  pad_top=SPACE_S, pad_bottom=SPACE_XS))
    sections.append(_render_text([form_line], size=SIZE_SUPPORT))

    sections.append(_render_rule())

    # The steps run in the order they are carried out, so the question sits
    # inside them rather than above: ask, then listen, then record. Step 4 is
    # below the field, in the tail, because that is when it happens.
    consequence = dept.get("consequence") or DEFAULT_CONSEQUENCE
    sections.append(_render_notice(NOTICE.format(consequence)))
    sections.append(_render_step(1, ASK_STEP))

    # Question. The widest interval on the receipt sits around it, which is
    # most of what makes it read as the one thing on the page.
    sections.append(Image.new("1", (PRINT_WIDTH, SPACE_L), 1))
    sections.append(_render_question(prompt))
    sections.append(Image.new("1", (PRINT_WIDTH, SPACE_L), 1))

    sections.append(_render_step(2, LISTEN_STEP))

    # Step 3 is the department's own activity, and lands directly above the
    # field it asks them to fill in.
    activity = dept.get("activity") or "Record their response below."
    sections.append(_render_step(3, activity))

    # The field, then the step that follows filling it in. No rule above the
    # field — its own frame is the boundary, and a rule on top of a box just
    # reads as a second, lighter box. The second raster opens on the gap, so
    # the feed the printer inserts between commands still lands on whitespace.
    tail = [Image.new("1", (PRINT_WIDTH, SPACE_M), 1)]
    tail.extend(_render_field(theme))
    tail.append(_render_step(4, POST_STEP))

    # Department identity signs the receipt off rather than heading it: the top
    # belongs to the questionnaire, and the seal already names the agency up
    # there. Bold at the step size, not the banner size — it identifies the
    # sender, it is not a headline. No rule between it and the thanks; they are
    # one block, the agency and the words it is saying.
    tail.append(_render_rule(pad_top=SPACE_M, pad_bottom=SPACE_L))
    tail.append(_render_text([dept_name.upper()], font_path=FONT_BOLD,
                             size=SIZE_STEP, pad_bottom=SPACE_XS))
    if tagline:
        tail.append(_render_text([f'"{tagline}"'], size=SIZE_SUPPORT))
    tail.append(_render_rule(dashed=False, length=SIGN_OFF_MARK,
                             pad_top=SPACE_M, pad_bottom=SPACE_M))
    tail.append(_render_text([SIGN_OFF], size=SIZE_SUPPORT,
                             pad_bottom=SPACE_L))

    return [_stack(sections), _stack(tail)]


def _stack(sections) -> Image.Image:
    """Paste sections into one tall image, top to bottom."""
    composite = Image.new("1", (PRINT_WIDTH, sum(s.height for s in sections)), 1)
    y = 0
    for section in sections:
        composite.paste(section, (0, y))
        y += section.height
    return composite


def _compose_dispatch(prompt: str, theme: str = "apathy",
                      dispatch_num: int = 0) -> Image.Image:
    """The whole dispatch as one image — previews, tests, and measurement."""
    return _stack(_compose_parts(prompt, theme=theme, dispatch_num=dispatch_num))


# Bytes the MHT-80E firmware treats as the start of a command. Taken from the
# firmware image itself (XOR 0xa3, ARM Thumb): the parser at 0x9810 rebases the
# byte by 0x14 and runs a `tbb` jump table over 0x14-0x1a, then compares ESC,
# FS, GS, RS and US explicitly. DLE is handled by the separate real-time
# command path. Anything in this range can put the printer into IAP
# firmware-update mode — we have already lost one printer that way.
COMMAND_BYTES = (0x10,) + tuple(range(0x14, 0x20))

# Escape targets must not themselves be dispatched. Flipping bit 5 lands every
# command byte in 0x30-0x3f, which the parser rejects outright, and still costs
# a single pixel. The earlier substitutions flipped bit 0 or 1 instead, which
# mapped ESC->SUB, FS->RS and GS->US — all three of them live commands — so the
# sanitizer was manufacturing the very bytes it existed to remove.
_ESCAPE_BIT = 0x20


def _sanitize_raster(data: bytes) -> bytes:
    """Remove ESC/POS command-initiator bytes from raster data.

    The MHT-80E firmware erroneously scans raster pixel data for command
    sequences. Each dangerous byte is replaced by a single bit flip, which
    moves one pixel and is visually imperceptible.
    """
    table = bytearray(range(256))
    for b in COMMAND_BYTES:
        table[b] = b ^ _ESCAPE_BIT
    return data.translate(bytes(table))


def _print_raster(p: File, img: Image.Image):
    """Send a raster image as a single GS v 0 command.

    Builds raster data directly from the 1-bit PIL image, bypassing
    EscposImage (which needlessly round-trips through RGBA/L/invert).
    PIL mode "1": 0=black, 1=white. ESC/POS raster: 1=black, 0=white.
    So we invert the packed bytes, then sanitize to remove any byte values
    the printer firmware might misinterpret as commands.
    """
    if img.mode != "1":
        img = img.convert("1")
    raw = img.tobytes()
    raster_data = bytes(b ^ 0xFF for b in raw)
    raster_data = _sanitize_raster(raster_data)
    width_bytes = img.width // 8
    height = img.height

    header = b'\x1d\x76\x30\x00'
    header += struct.pack('<HH', width_bytes, height)
    p._raw(header + raster_data)
