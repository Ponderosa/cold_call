#!/usr/bin/env python3
"""Generate a Bureau of Apathy seal for thermal printing.

Outputs a 1-bit PNG sized for 80mm thermal printers.
"""

import math

from PIL import Image, ImageDraw, ImageFont

SIZE = 360
CENTER = SIZE // 2
OUT = "assets/images/bureau_seal.png"


def draw_circle(draw, cx, cy, r, **kwargs):
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], **kwargs)


# Create image
img = Image.new("1", (SIZE, SIZE), 1)  # 1-bit, white background
draw = ImageDraw.Draw(img)

# Load fonts
try:
    font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
    font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    font_motto = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
except OSError:
    font_title = ImageFont.load_default()
    font_sub = font_title
    font_motto = font_title

# Outer ring (thick)
draw_circle(draw, CENTER, CENTER, 174, outline=0, width=6)
# Decorative dots around outer ring
for i in range(36):
    angle = 2 * math.pi * i / 36
    x = CENTER + 160 * math.cos(angle)
    y = CENTER + 160 * math.sin(angle)
    draw_circle(draw, x, y, 2, fill=0)
# Inner ring
draw_circle(draw, CENTER, CENTER, 148, outline=0, width=2)

# Top text
draw.text((CENTER, 42), "BUREAU", anchor="mt", font=font_title, fill=0)
draw.text((CENTER, 68), "OF", anchor="mt", font=font_sub, fill=0)
draw.text((CENTER, 84), "APATHY", anchor="mt", font=font_title, fill=0)

# Separator lines
draw.line([(60, 118), (SIZE - 60, 118)], fill=0, width=2)

# Center: starburst
for i in range(12):
    angle = 2 * math.pi * i / 12
    x1 = CENTER + 12 * math.cos(angle)
    y1 = (CENTER + 30) + 12 * math.sin(angle)
    x2 = CENTER + 48 * math.cos(angle)
    y2 = (CENTER + 30) + 48 * math.sin(angle)
    draw.line([(x1, y1), (x2, y2)], fill=0, width=2)

# Center circles
cy_star = CENTER + 30
draw_circle(draw, CENTER, cy_star, 50, outline=0, width=2)
draw_circle(draw, CENTER, cy_star, 16, fill=0)
draw_circle(draw, CENTER, cy_star, 10, fill=1)
draw_circle(draw, CENTER, cy_star, 4, fill=0)

# Separator line below star
draw.line([(60, SIZE - 118), (SIZE - 60, SIZE - 118)], fill=0, width=2)

# Bottom text
draw.text((CENTER, SIZE - 108), "EST. WHENEVER", anchor="mt", font=font_motto, fill=0)
draw.text((CENTER, SIZE - 70), '"We\'ll get to it."', anchor="mt", font=font_sub, fill=0)

img.save(OUT)
print(f"Saved {OUT} ({SIZE}x{SIZE}px, 1-bit)")
