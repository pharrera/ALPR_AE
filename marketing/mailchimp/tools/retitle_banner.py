#!/usr/bin/env python3
"""Swap the gold topper on the Tech Week banner, keeping the rest of the artwork.

The banner carries a gold line above the wordmark. Each send wants its own text
there, so this erases that line and sets a new one on the same baseline.

Everything is measured from the source rather than hardcoded, so it works on
both the 781px original and the 1200px clean export, whose toppers differ in
size and position.

Erasing is the hard part. Three faults caused visible damage on earlier passes:

  * The gold's bright core passes a naive "is this white?" test, which then
    protects the very pixels being erased and leaves the old line showing
    through. Gold is warm, so the test also requires neutrality.
  * A mask that only just covers the glyphs leaves their antialiased halo,
    which reads as a pale smudge. The mask is dilated well past the edges and
    held clear of the wordmark below.
  * Filling from one flat colour leaves a patch wherever the background is not
    flat, and the palm frond crosses the line. The fill comes from a
    normalised-convolution estimate of the background with every glyph excluded
    from the model, and is feathered at the edges.

Usage:  python3 tools/retitle_banner.py "New Line" out.jpg [source.jpg]
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(HERE, "_assets")
FONT = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"
MAX_WIDTH = 0.90          # of the image, so a long line still has a margin


def odd(n):
    n = max(3, int(round(n)))
    return n if n % 2 else n + 1


def dilate(mask, k):
    return np.array(Image.fromarray((mask * 255).astype(np.uint8))
                    .filter(ImageFilter.MaxFilter(odd(k)))) > 0


def boxblur(x, r, passes=3):
    r = max(1, int(r))
    for _ in range(passes):
        p = np.pad(x, ((r + 1, r), (0, 0)), mode="edge")
        c = np.cumsum(p, 0)
        x = (c[2 * r + 1:] - c[:-(2 * r + 1)]) / (2 * r + 1)
        p = np.pad(x, ((0, 0), (r + 1, r)), mode="edge")
        c = np.cumsum(p, 1)
        x = (c[:, 2 * r + 1:] - c[:, :-(2 * r + 1)]) / (2 * r + 1)
    return x


def measure_topper(gold):
    """Rows, baseline and cap height of the topmost gold line."""
    rows = gold.sum(1)
    bands, run = [], None
    for y in range(len(rows)):
        if rows[y] > 2 and run is None:
            run = y
        elif rows[y] <= 2 and run is not None:
            if y - run > 5:
                bands.append((run, y - 1))
            run = None
    top, nxt = bands[0], (bands[1][0] if len(bands) > 1 else len(rows))
    sub = rows[top[0]:top[1] + 1]
    baseline = top[0] + int(np.nonzero(sub > sub.max() * 0.4)[0].max())
    return top, baseline, baseline - top[0], nxt


def fit_size(text, cap, width_limit):
    """Point size matching the old cap height, reduced if the line runs wide."""
    draw = ImageDraw.Draw(Image.new("L", (1, 1)))
    pt = max(8, int(round(cap * 44 / 32)))          # 44pt gives a 32px cap
    while pt > 8 and draw.textlength(text, font=ImageFont.truetype(FONT, pt)) > width_limit:
        pt -= 1
    return pt


def retitle(text, out_path, source):
    a = np.array(Image.open(source).convert("RGB")).astype(np.float64)
    h, w, _ = a.shape
    k = w / 781.0                                    # kernels scale with the art

    gold = (a[:, :, 0] > 140) & (a[:, :, 1] > 100) & (a[:, :, 2] < 120) \
        & (a[:, :, 0] - a[:, :, 2] > 50)
    white = (a.sum(2) > 430) & (np.abs(a[:, :, 0] - a[:, :, 2]) < 40)

    (y0, y1), baseline, cap, next_band = measure_topper(gold)
    line = gold.copy()
    line[next_band - 2:, :] = False
    line[:max(0, y0 - int(30 * k)), :] = False

    core = np.array(Image.fromarray((line * 255).astype(np.uint8))
                    .filter(ImageFilter.MinFilter(odd(5 * k)))) > 0
    ink = tuple(int(v) for v in np.median(a[core], 0))

    # The white guard keeps the wide dilation off the wordmark's edge, but the
    # old line's descenders reach into that halo, so the glyphs themselves are
    # always covered - otherwise fragments of the old text survive.
    mask = (dilate(line, 17 * k) & ~dilate(white, 5 * k)) | line
    mask[next_band - 2:, :] = False
    missed = (line & ~mask).sum()
    assert missed == 0, f"{missed} pixels of the old line are not covered"

    keep = (~(mask | dilate(gold, 7 * k) | dilate(white, 7 * k))).astype(np.float64)
    weight = boxblur(keep, 14 * k)
    bg = np.stack([boxblur(a[:, :, c] * keep, 14 * k) / np.maximum(weight, 1e-6)
                   for c in range(3)], -1)

    clean = a[int(14 * k):int(46 * k), int(130 * k):int(560 * k)].reshape(-1, 3)
    rng = np.random.default_rng(11)
    fill = bg + rng.normal(0, clean.std(0), a.shape)

    hard = dilate(line, 9 * k).astype(np.float64)
    alpha = np.maximum(np.clip(boxblur(hard, max(1, 3 * k)), 0, 1), hard) * mask
    out = a * (1 - alpha[..., None]) + fill * alpha[..., None]

    plate = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
    pt = fit_size(text, cap, w * MAX_WIDTH)
    s = 4
    layer = Image.new("L", (w * s, h * s), 0)
    ImageDraw.Draw(layer).text((w * s / 2, baseline * s), text, 255,
                               font=ImageFont.truetype(FONT, pt * s), anchor="ms")
    plate.paste(Image.new("RGB", (w, h), ink), (0, 0),
                layer.resize((w, h), Image.LANCZOS))
    plate.save(out_path, quality=94, subsampling=0, optimize=True)
    return missed, pt, cap, baseline


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    src = os.path.join(ASSETS, sys.argv[3]) if len(sys.argv) == 4 \
        else os.path.join(ASSETS, "techweek-2026.jpg")
    missed, pt, cap, base = retitle(sys.argv[1], os.path.join(ASSETS, sys.argv[2]), src)
    print(f"wrote _assets/{sys.argv[2]}  set at {pt}pt on baseline {base} "
          f"(old cap {cap}px), {missed} stray pixels of the old line")
