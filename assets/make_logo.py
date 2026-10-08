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
PAD = 4                      # cells of padding around the glyph
COLS_EXTRA = 9               # room on the right for drifting fragments
LEFT, RIGHT = (0x3E, 0xF2, 0xFF), (0xFF, 0x2E, 0x88)   # cyan -> magenta
BG = "#0B0D12"
EYE = "#F4FBFF"


def lerp(a, b, t):
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(a, b))


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
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
           f'shape-rendering="crispEdges" role="img" aria-label="soulkiller">']
    if tile:
        out.append(f'<rect width="{W}" height="{H}" rx="{CELL * 3}" fill="{BG}"/>')
        # faint scanlines
        out += [f'<rect y="{y}" width="{W}" height="1" fill="#FFFFFF" opacity="0.035"/>' for y in range(0, H, 4)]
    gap = 1  # 1px gutter between cells reads as "pixel"
    seen = set()
    for x, y in solid:
        color = lerp(LEFT, RIGHT, x / total_w)
        out.append(f'<rect x="{(x + ox) * CELL}" y="{(y + oy) * CELL}" width="{CELL - gap}" height="{CELL - gap}" fill="{color}"/>')
        seen.add((x, y))
    for x, y in eyes:
        out.append(f'<rect x="{(x + ox) * CELL}" y="{(y + oy) * CELL}" width="{CELL - gap}" height="{CELL - gap}" fill="{EYE}"/>')
        seen.add((x, y))
    for x, y, a in fragments:
        if (x, y) in seen or y < -oy + 1:
            continue
        seen.add((x, y))
        color = lerp(LEFT, RIGHT, min(1, x / total_w))
        out.append(f'<rect x="{(x + ox) * CELL}" y="{(y + oy) * CELL}" width="{CELL - gap}" height="{CELL - gap}" '
                   f'fill="{color}" opacity="{a:.2f}"/>')
    out.append("</svg>")
    path.write_text("\n".join(out) + "\n")


if __name__ == "__main__":
    here = Path(__file__).parent
    render(here / "logo.svg", tile=True)
    render(here / "logo-mark.svg", tile=False)
