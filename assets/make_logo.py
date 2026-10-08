"""Generates the soulkiller pixel glyph: a face dissolving into data.

    python assets/make_logo.py   ->  assets/logo.svg, assets/logo-mark.svg
"""
from __future__ import annotations

import random
from pathlib import Path

# '#' = face, 'o' = lit eyes (never dissolve), '.' = empty.
FACE = """
.......######.......
.....##########.....
....############....
...##############...
..################..
..################..
.##################.
.##################.
.###ooo######ooo###.
.###ooo######ooo###.
.##################.
.##################.
.#########.########.
..########.#######..
..#######...######..
...##############...
...###..........##..
....###.......###...
.....###########....
......#########.....
.......#######......
""".strip().splitlines()

CELL = 10
GAP = 2                      # gutter between pixels; ~1px when shown at 180px
PAD = 4                      # cells of padding around the glyph
COLS_EXTRA = 9               # room on the right for drifting fragments
# Palette from jach.me/engram (engram.css)
RED = "#FF2D3F"          # --red
RED_LINE = "#4A1219"     # --red-line: card borders
BG = "#010101"           # --background-color
EYE = "#FFFFFF"          # --text-color


def pixels(seed=7):
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
            d = max(0.0, (x - w * 0.6) / (w * 0.4))
            if rnd.random() < d * 0.85:
                # pixel breaks off: drifts right and slightly up, fading
                dist = 1 + int(rnd.random() * (2 + d * COLS_EXTRA))
                fx, fy = x + dist, y - int(rnd.random() * dist * 0.6)
                if rnd.random() < 0.75:
                    fragments.append((fx, fy, max(0.15, 1 - dist / (COLS_EXTRA + 3))))
            else:
                solid.append((x, y))
    return solid, eyes, fragments, w, h


def render(path: Path, tile: bool, seed=7):
    solid, eyes, fragments, w, h = pixels(seed)
    total_w = w + COLS_EXTRA
    side = max(total_w, h) + PAD * 2          # square canvas: works as avatar / favicon
    W = H = side * CELL
    ox, oy = (side - total_w) // 2, (side - h) // 2   # centre the glyph + its debris
    px = lambda x, y, fill, extra="": (f'<rect x="{(x + ox) * CELL}" y="{(y + oy) * CELL}" '
                                        f'width="{CELL - GAP}" height="{CELL - GAP}" fill="{fill}"{extra}/>')
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
           f'role="img" aria-label="soulkiller">',
           # same soft red glow as the page's buttons (box-shadow: 0 0 24px var(--red-glow))
           '<defs><filter id="glow" x="-30%" y="-30%" width="160%" height="160%">'
           f'<feGaussianBlur stdDeviation="{CELL * 1.2}" result="b"/>'
           '<feColorMatrix in="b" values="0 0 0 0 1  0 0 0 0 0.176  0 0 0 0 0.247  0 0 0 0.55 0"/>'
           '<feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>']
    if tile:
        out.append(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" fill="{BG}" stroke="{RED_LINE}"/>')
    out.append('<g filter="url(#glow)" shape-rendering="crispEdges">')
    seen = set()
    for x, y in solid:
        out.append(px(x, y, RED))
        seen.add((x, y))
    for x, y in eyes:
        out.append(px(x, y, EYE))
        seen.add((x, y))
    for x, y, a in fragments:
        if (x, y) in seen or y < -oy + 1:
            continue
        seen.add((x, y))
        out.append(px(x, y, RED, f' opacity="{a:.2f}"'))
    out.append("</g>")
    out.append("</svg>")
    path.write_text("\n".join(out) + "\n")


if __name__ == "__main__":
    here = Path(__file__).parent
    render(here / "logo.svg", tile=True)
    render(here / "logo-mark.svg", tile=False)
