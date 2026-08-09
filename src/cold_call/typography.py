"""Typographic primitives for the printed dispatch.

The drawing vocabulary and nothing above it: page geometry, the face, and the
handful of operations every element on a receipt is built from. Knows nothing
about receipts or printers.

Rules for what goes where are in docs/DESIGN.md.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PRINT_WIDTH = 576  # 80mm at 203dpi (~72mm printable)
TOP_MARGIN = 64    # 8mm of leader, also part of the cut clearance
SIDE_MARGIN = 25   # 4.3% of width, matching the designers' worksheets
RULE_WEIGHT = 3    # 0.53% of width, the single rule weight

# The column every element is set within.
COLUMN = PRINT_WIDTH - 2 * SIDE_MARGIN

ASSETS = Path(__file__).resolve().parent.parent.parent / "assets"
# One face for the whole receipt. The dispatch has to be read aloud by a
# stranger holding a handset in a dim, crowded room — a signage problem, not a
# document one. See docs/DESIGN.md.
FONT_REG = str(ASSETS / "fonts" / "IBMPlexMono-Regular.ttf")
FONT_BOLD = str(ASSETS / "fonts" / "IBMPlexMono-Bold.ttf")


def render_text(lines, font_path=FONT_REG, size=24, align="center",
                 line_spacing=8, pad_top=0, pad_bottom=0, tracking=0):
    """Render lines of text to a 1-bit image at PRINT_WIDTH.

    `tracking` adds space between letters, in pixels. Tracked caps read as
    stamped rather than typed, so it is used on the header and identity lines
    and left at zero for running text.
    """
    font = ImageFont.truetype(font_path, size)
    ascent, descent = font.getmetrics()
    line_h = ascent + descent

    total_h = line_h * len(lines) + line_spacing * (len(lines) - 1) + pad_top + pad_bottom
    img = Image.new("1", (PRINT_WIDTH, total_h), 1)
    draw = ImageDraw.Draw(img)

    y = pad_top
    for line in lines:
        if tracking:
            widths = [draw.textlength(ch, font=font) for ch in line]
            tw = sum(widths) + tracking * (len(line) - 1)
        else:
            bbox = draw.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]

        if align == "center":
            x = (PRINT_WIDTH - tw) // 2
        elif align == "right":
            x = PRINT_WIDTH - tw
        else:
            x = 0

        if tracking:
            # Letters are placed one at a time, so the trailing space after the
            # last character is not counted into the centring above.
            for ch, w in zip(line, widths):
                draw.text((x, y), ch, font=font, fill=0)
                x += w + tracking
        else:
            draw.text((x, y), line, font=font, fill=0)
        y += line_h + line_spacing

    return img


def wrap_to_width(text: str, font_path: str, size: int, tracking: int,
                   max_width: int) -> list[str]:
    """Break a line onto as few lines as fit the column, balanced.

    Measured against the font rather than counted in characters, so the
    measure stays correct if the face changes and so tracking is accounted
    for. Long agency names wrap the way they do on the seals themselves — the
    department is named on two lines rather than set smaller than its
    neighbours.
    """
    font = ImageFont.truetype(font_path, size)
    draw = ImageDraw.Draw(Image.new("1", (1, 1)))
    # Collapse runs of whitespace up front. Text that fits is returned
    # untouched and text that wraps is rejoined on single spaces, so without
    # this the two paths disagree about spacing.
    text = " ".join(text.split())

    def width(s: str) -> float:
        return sum(draw.textlength(c, font=font) for c in s) + tracking * (len(s) - 1)

    if width(text) <= max_width:
        return [text]

    words = text.split()

    # Greedy fill settles how few lines the text can occupy.
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and width(candidate) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)

    if len(lines) < 2:
        return lines

    # Greedy packs early lines full and leaves a stub, which on centred display
    # type reads as an accident. Redistribute over the same number of lines,
    # minimising the squared slack so the rag is even. Breaks are chosen by
    # dynamic programming over word positions.
    target = len(lines)
    n = len(words)
    widths = [[None] * (n + 1) for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n + 1):
            w = width(" ".join(words[i:j]))
            widths[i][j] = w if w <= max_width else None

    INF = float("inf")
    # best[i][k] — least cost to set words[i:] on exactly k lines.
    best = [[INF] * (target + 1) for _ in range(n + 1)]
    choice = [[None] * (target + 1) for _ in range(n + 1)]
    best[n][0] = 0.0
    for i in range(n - 1, -1, -1):
        for k in range(1, target + 1):
            for j in range(i + 1, n + 1):
                w = widths[i][j]
                if w is None:
                    break
                rest = best[j][k - 1]
                if rest == INF:
                    continue
                # The last line is allowed to be short without penalty.
                slack = 0.0 if k == 1 else (max_width - w) ** 2
                cost = slack + rest
                if cost < best[i][k]:
                    best[i][k] = cost
                    choice[i][k] = j

    if best[0][target] == INF:
        return lines

    balanced, i, k = [], 0, target
    while k:
        j = choice[i][k]
        balanced.append(" ".join(words[i:j]))
        i, k = j, k - 1
    return balanced


def render_rule(width: int = COLUMN, pad_top: int = 11, pad_bottom: int = 11):
    """A drawn rule of a given width, centred."""
    img = Image.new("1", (PRINT_WIDTH, pad_top + RULE_WEIGHT + pad_bottom), 1)
    x0 = (PRINT_WIDTH - width) // 2
    ImageDraw.Draw(img).rectangle(
        [x0, pad_top, x0 + width - 1, pad_top + RULE_WEIGHT - 1], fill=0)
    return img


def render_separator(pad_top=11, pad_bottom=11):
    """A double rule — the divider between zones of the receipt.

    Doubled to tell it apart from the rules inside the designers' worksheets,
    which are lines to write on. Single rules at the same weight read as the
    same kind of object, so nothing distinguished "this divides a section"
    from "write here". Thick over thin is the ledger and form convention.

    The thin rule is 2px, which is the floor the medium allows; it survives
    because it is a long continuous horizontal, the most forgiving shape for
    a thin stroke under dot spread.
    """
    thin = 2
    gap = 6
    height = pad_top + RULE_WEIGHT + gap + thin + pad_bottom
    img = Image.new("1", (PRINT_WIDTH, height), 1)
    draw = ImageDraw.Draw(img)
    right = PRINT_WIDTH - SIDE_MARGIN - 1
    draw.rectangle([SIDE_MARGIN, pad_top,
                    right, pad_top + RULE_WEIGHT - 1], fill=0)
    y = pad_top + RULE_WEIGHT + gap
    draw.rectangle([SIDE_MARGIN, y, right, y + thin - 1], fill=0)
    return img


def stack(sections) -> Image.Image:
    """Paste sections into one tall image, top to bottom."""
    composite = Image.new("1", (PRINT_WIDTH, sum(s.height for s in sections)), 1)
    y = 0
    for section in sections:
        composite.paste(section, (0, y))
        y += section.height
    return composite


def render_body(text: str, size: int = 18, indent: int = 0, hang: int = 0,
                line_spacing: int = 4, pad_top: int = 0, pad_bottom: int = 0,
                font_path: str = FONT_REG) -> Image.Image:
    """Wrapped text set flush left in the column.

    Everything else on the receipt is centred; running instructions are not,
    because a numbered list needs a straight left edge or the numbers do not
    line up. `hang` indents every line after the first, so a step's text sits
    under itself rather than under its number.
    """
    left = SIDE_MARGIN + indent
    lines = wrap_to_width(text, font_path, size, 0, COLUMN - indent - hang)

    rendered = []
    for i, line in enumerate(lines):
        x = left + (hang if i else 0)
        img = Image.new("1", (PRINT_WIDTH, 1), 1)
        font = ImageFont.truetype(font_path, size)
        ascent, descent = font.getmetrics()
        img = Image.new("1", (PRINT_WIDTH, ascent + descent), 1)
        ImageDraw.Draw(img).text((x, 0), line, font=font, fill=0)
        rendered.append(img)

    height = sum(r.height for r in rendered) + line_spacing * (len(rendered) - 1)
    out = Image.new("1", (PRINT_WIDTH, pad_top + height + pad_bottom), 1)
    y = pad_top
    for r in rendered:
        out.paste(r, (0, y))
        y += r.height + line_spacing
    return out
