"""Draw icons/seal.png — the wax seal of EMStudio's `sealMini`, as a Blender icon.

The same edge as `frontend/src/seal.ts::sealEdge` (14 points, each radius from
one hex digit), the same reds (#9c1f1a wax, #7d1612 inner, #e6897c ring). The
digest is fixed: an icon is a sign, not a particular stamp. Drawn at 8× and
reduced, so the edge stays soft at 32 px.

    .venv/bin/python scripts/draw_seal_icon.py
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw

HEX = "e57c0de53f44198e"  # case 19 of dtcstamp: any digest would do
SIZE, SCALE = 64, 8


def edge(hex_, n, r, c):
    pts = []
    for i in range(n):
        a = i / n * math.pi * 2
        j = int(hex_[i % len(hex_)], 16) / 15
        rr = r + (j - 0.5) * 7 * (r / 58)
        pts.append((c + math.cos(a) * rr, c + math.sin(a) * rr))
    return pts


def main():
    big = SIZE * SCALE
    k = big / 16  # the 16-unit viewBox of sealMini
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.polygon([(x * k, y * k) for x, y in edge(HEX, 14, 7.2, 8)], fill="#9c1f1a")
    r = 4.6 * k
    d.ellipse([8 * k - r, 8 * k - r, 8 * k + r, 8 * k + r], fill="#7d1612",
              outline="#e6897c", width=int(0.6 * k))
    r2 = 2.6 * k
    d.ellipse([8 * k - r2, 8 * k - r2, 8 * k + r2, 8 * k + r2], outline="#5a0d0a",
              width=int(0.35 * k))
    out = Path(__file__).resolve().parent.parent / "icons" / "seal.png"
    img.resize((SIZE, SIZE), Image.LANCZOS).save(out)
    print(out)


if __name__ == "__main__":
    main()
