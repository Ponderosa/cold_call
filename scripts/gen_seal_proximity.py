#!/usr/bin/env python3
"""Generate an Office of Acceptable Proximity seal for thermal printing."""

import math

from PIL import Image, ImageDraw, ImageFont

SIZE = 360
CENTER = SIZE // 2
OUT = "assets/images/proximity_seal.png"


def draw_circle(draw, cx, cy, r, **kwargs):
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], **kwargs)


img = Image.new("1", (SIZE, SIZE), 1)
draw = ImageDraw.Draw(img)

try:
    font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
    font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    font_motto = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
except OSError:
    font_title = ImageFont.load_default()
    font_sub = font_title
    font_motto = font_title

# Outer ring — double line
draw_circle(draw, CENTER, CENTER, 174, outline=0, width=4)
draw_circle(draw, CENTER, CENTER, 164, outline=0, width=2)

# Inner ring
draw_circle(draw, CENTER, CENTER, 148, outline=0, width=2)

# Small dashes between rings (like a measuring tape / ruler marks)
for i in range(72):
    angle = 2 * math.pi * i / 72
    r_inner = 165
    r_outer = 173 if i % 6 == 0 else 169
    x1 = CENTER + r_inner * math.cos(angle)
    y1 = CENTER + r_inner * math.sin(angle)
    x2 = CENTER + r_outer * math.cos(angle)
    y2 = CENTER + r_outer * math.sin(angle)
    draw.line([(x1, y1), (x2, y2)], fill=0, width=1)

# Top text
draw.text((CENTER, 38), "OFFICE OF", anchor="mt", font=font_title, fill=0)
draw.text((CENTER, 62), "ACCEPTABLE", anchor="mt", font=font_title, fill=0)
draw.text((CENTER, 86), "PROXIMITY", anchor="mt", font=font_title, fill=0)

# Separator
draw.line([(55, 114), (SIZE - 55, 114)], fill=0, width=2)

# Center icon: two figures standing at a measured distance
# Left figure (simple)
fig_y = CENTER + 25
fig_lx = CENTER - 55
fig_rx = CENTER + 55

for fx in [fig_lx, fig_rx]:
    # Head
    draw_circle(draw, fx, fig_y - 28, 10, outline=0, width=2)
    # Body
    draw.line([(fx, fig_y - 18), (fx, fig_y + 10)], fill=0, width=2)
    # Arms
    draw.line([(fx - 12, fig_y - 8), (fx + 12, fig_y - 8)], fill=0, width=2)
    # Legs
    draw.line([(fx, fig_y + 10), (fx - 10, fig_y + 28)], fill=0, width=2)
    draw.line([(fx, fig_y + 10), (fx + 10, fig_y + 28)], fill=0, width=2)

# Distance arrow between figures
arrow_y = fig_y + 38
draw.line([(fig_lx + 14, arrow_y), (fig_rx - 14, arrow_y)], fill=0, width=2)
# Arrowheads
for dx, sign in [(fig_lx + 14, 1), (fig_rx - 14, -1)]:
    draw.line([(dx, arrow_y), (dx + sign * 6, arrow_y - 4)], fill=0, width=2)
    draw.line([(dx, arrow_y), (dx + sign * 6, arrow_y + 4)], fill=0, width=2)

# Label on arrow
draw.text((CENTER, arrow_y - 12), "OK", anchor="mm", font=font_sub, fill=0)

# Separator below
draw.line([(55, SIZE - 114), (SIZE - 55, SIZE - 114)], fill=0, width=2)

# Bottom text
draw.text((CENTER, SIZE - 104), "EST. RECENTLY", anchor="mt", font=font_motto, fill=0)
draw.text((CENTER, SIZE - 68), '"Not too close."', anchor="mt", font=font_sub, fill=0)

img.save(OUT)
print(f"Saved {OUT} ({SIZE}x{SIZE}px, 1-bit)")
