"""Generates the soulkiller pixel glyph: a realistic face dissolving into data.

    uv run --with pillow python assets/make_logo.py   ->  assets/*.svg

The face is sampled from assets/source/face.png (an AI-generated portrait of a fictional
person), quantized into brightness levels and drawn as a red LED matrix. Pixels on the
right side break off and drift away.

Each variant is drawn for one display size so every cell lands on whole device pixels
(crisp at 1x and 2x). Show them at their native width/height, never scaled.
"""
from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageOps

HERE = Path(__file__).parent
SOURCE = HERE / "source" / "face.png"
CROP = (190, 30, 840, 930)  # left, top, right, bottom of the face in the source portrait
COLS = 20                    # face width in cells: fewer = chunkier, more = more realistic
LEVELS = 6                   # brightness steps (0 = off)
COLS_EXTRA = 7               # room on the right for drifting fragments

# Palette from jach.me/engram (engram.css)
RED = "#FF2D3F"          # --red
HIGHLIGHT = "#FF7F8A"    # brightest level: lit skin reads as a hot LED
RED_LINE = "#4A1219"     # --red-line: card borders
BG = "#010101"           # --background-color
OPACITY = {1: 0.18, 2: 0.36, 3: 0.58, 4: 0.82, 5: 1.0}


def face_levels(cols: int | None = None) -> list[list[int]]:
    """Sample the portrait into a grid of brightness levels 0..LEVELS-1."""
    cols = cols or COLS
    im = Image.open(SOURCE).convert("L").crop(CROP)
    rows = round(cols * im.height / im.width)
    im = ImageOps.autocontrast(im.resize((cols, rows), Image.Resampling.BOX), cutoff=(2, 1))
    px = im.load()
    return [[min(LEVELS - 1, int((px[x, y] / 255) ** 1.3 * LEVELS)) for x in range(cols)] for y in range(rows)]


def pixels(seed=6):
    rnd = random.Random(seed)
    grid = face_levels()
    h, w = len(grid), len(grid[0])
    solid, fragments = [], []
    for y, row in enumerate(grid):
        for x, level in enumerate(row):
            if not level:
                continue
            # dissolution starts right of centre and grows towards the edge
            d = max(0.0, (x - w * 0.55) / (w * 0.45))
            if rnd.random() < d * 0.9:
                # pixel breaks off: drifts right and slightly up, fading
                dist = 1 + int(rnd.random() * (2 + d * COLS_EXTRA))
                fx, fy = x + dist, y - int(rnd.random() * dist * 0.6)
                if rnd.random() < 0.8:
                    fragments.append((fx, fy, level, max(0.2, 1 - dist / (COLS_EXTRA + 3))))
            else:
                solid.append((x, y, level))
    return solid, fragments, w, h


def render(path: Path, tile: bool, cell: int, gap: int, pad: int = 2, glow: bool = True, seed: int = 6):
    """cell/gap are in CSS px at native size."""
    solid, fragments, w, h = pixels(seed)
    total_w = w + COLS_EXTRA
    side = max(total_w, h) + pad * 2          # square canvas: works as avatar / favicon
    W = H = side * cell
    ox, oy = (side - total_w) // 2, (side - h) // 2   # centre the glyph + its debris

    def px(x, y, level, alpha=1.0):
        fill = HIGHLIGHT if level == LEVELS - 1 else RED
        a = OPACITY[level] * alpha
        op = "" if a >= 1 else f' opacity="{a:.2f}"'
        return (f'<rect x="{(x + ox) * cell}" y="{(y + oy) * cell}" '
                f'width="{cell - gap}" height="{cell - gap}" fill="{fill}"{op}/>')

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
           f'role="img" aria-label="soulkiller">']
    if glow:
        # same soft red glow as the page's buttons (box-shadow: 0 0 24px var(--red-glow))
        out.append('<defs><filter id="glow" x="-30%" y="-30%" width="160%" height="160%">'
                   f'<feGaussianBlur stdDeviation="{cell * 0.8:g}" result="b"/>'
                   '<feColorMatrix in="b" values="0 0 0 0 1  0 0 0 0 0.176  0 0 0 0 0.247  0 0 0 0.45 0"/>'
                   '<feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>')
    if tile:
        out.append(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" fill="{BG}" stroke="{RED_LINE}"/>')
    out.append('<g filter="url(#glow)" shape-rendering="crispEdges">' if glow else '<g shape-rendering="crispEdges">')
    seen = set()
    for x, y, level in solid:
        out.append(px(x, y, level))
        seen.add((x, y))
    for x, y, level, a in fragments:
        if (x, y) in seen or y + oy < 1 or x + ox >= side:
            continue
        seen.add((x, y))
        out.append(px(x, y, level, a))
    out.append("</g>")
    out.append("</svg>")
    path.write_text("\n".join(out) + "\n")


VARIANTS = {
    # name: (tile, cell px, gap px, extra)
    "logo.svg":      (True, 6, 1, {}),                 # README, 192px
    "logo-mark.svg": (False, 10, 1, {}),               # OG image, big placements, 320px
    "favicon.svg":   (True, 1, 0, {"pad": 0, "glow": False}),  # browsers downsample it
}

if __name__ == "__main__":
    for name, (tile, cell, gap, extra) in VARIANTS.items():
        render(HERE / name, tile=tile, cell=cell, gap=gap, **extra)
        print(name, open(HERE / name).readline().split('width="')[1].split('"')[0] + "px")
