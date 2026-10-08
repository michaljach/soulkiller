"""Generates the soulkiller pixel glyph: a face dissolving into data.

    python assets/make_logo.py   ->  assets/*.svg

Each variant is drawn for one display size so every cell lands on whole device pixels
(crisp at 1x and 2x). Show them at their native width/height, never scaled.
"""
from __future__ import annotations

import random
from pathlib import Path

# '#' = face, 'o' = lit eyes (never dissolve), '.' = empty.
FACE = """
....####....
..########..
.##########.
.##########.
############
##oo####oo##
##oo####oo##
############
############
#####..#####
.##########.
.##......##.
..########..
....####....
""".strip().splitlines()

COLS_EXTRA = 5               # room on the right for drifting fragments
# Palette from jach.me/engram (engram.css)
RED = "#FF2D3F"          # --red
RED_LINE = "#4A1219"     # --red-line: card borders
BG = "#010101"           # --background-color
EYE = "#FFFFFF"          # --text-color


def pixels(seed=6):
    rnd = random.Random(seed)
    h, w = len(FACE), len(FACE[0])
    solid, eyes, fragments = [], [], []
    for y, row in enumerate(FACE):
        for x, ch in enumerate(row):
            if ch == "o":
                eyes.append((x, y))
            if ch != "#":
                continue
            # dissolution starts right of centre and grows towards the edge
            d = max(0.0, (x - w * 0.5) / (w * 0.5))
            if rnd.random() < d * 0.95:
                # pixel breaks off: drifts right and slightly up, fading
                dist = 1 + int(rnd.random() * (2 + d * COLS_EXTRA))
                fx, fy = x + dist, y - int(rnd.random() * dist * 0.6)
                if rnd.random() < 0.9:
                    fragments.append((fx, fy, max(0.15, 1 - dist / (COLS_EXTRA + 3))))
            else:
                solid.append((x, y))
    return solid, eyes, fragments, w, h


def render(path: Path, tile: bool, cell: int, gap: int, pad: int = 2, side: int | None = None,
           glow: bool = True, seed: int = 6):
    """cell/gap are in CSS px at native size. `side` (cells) forces a smaller canvas, cropping debris."""
    solid, eyes, fragments, w, h = pixels(seed)
    total_w = w + COLS_EXTRA
    side = side or max(total_w, h) + pad * 2  # square canvas: works as avatar / favicon
    W = H = side * cell
    ox, oy = max(0, (side - total_w) // 2), (side - h) // 2   # centre the glyph + its debris
    px = lambda x, y, fill, extra="": (f'<rect x="{(x + ox) * cell}" y="{(y + oy) * cell}" '
                                        f'width="{cell - gap}" height="{cell - gap}" fill="{fill}"{extra}/>')
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
           f'role="img" aria-label="soulkiller">']
    if glow:
        # same soft red glow as the page's buttons (box-shadow: 0 0 24px var(--red-glow))
        out.append('<defs><filter id="glow" x="-30%" y="-30%" width="160%" height="160%">'
                   f'<feGaussianBlur stdDeviation="{cell * 0.8:g}" result="b"/>'
                   '<feColorMatrix in="b" values="0 0 0 0 1  0 0 0 0 0.176  0 0 0 0 0.247  0 0 0 0.55 0"/>'
                   '<feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>')
    if tile:
        out.append(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" fill="{BG}" stroke="{RED_LINE}"/>')
    out.append('<g filter="url(#glow)" shape-rendering="crispEdges">' if glow else '<g shape-rendering="crispEdges">')
    seen = set()
    for x, y in solid:
        out.append(px(x, y, RED))
        seen.add((x, y))
    for x, y in eyes:
        out.append(px(x, y, EYE))
        seen.add((x, y))
    for x, y, a in fragments:
        if (x, y) in seen or y + oy < 1 or x + ox >= side:
            continue
        seen.add((x, y))
        out.append(px(x, y, RED, f' opacity="{a:.2f}"'))
    out.append("</g>")
    out.append("</svg>")
    path.write_text("\n".join(out) + "\n")


VARIANTS = {
    # name: (tile, cell px, gap px, extra)          native size
    "logo.svg":        (True, 8, 1, {}),           # 168px  README
    "logo-mark.svg":   (False, 16, 2, {}),         # 336px  OG image, big placements
    "logo-header.svg": (False, 4, 1, {}),          # 84px   inline next to a heading
    "favicon.svg":     (True, 2, 0, {"pad": 0, "side": 16, "glow": False}),  # 32px, 1 cell = 2px
}

if __name__ == "__main__":
    here = Path(__file__).parent
    for name, (tile, cell, gap, extra) in VARIANTS.items():
        render(here / name, tile=tile, cell=cell, gap=gap, **extra)
        print(name)
