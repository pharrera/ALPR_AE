#!/usr/bin/env python3
"""Swap the gold topper on the Tech Week banner, keeping the rest of the artwork.

The source artwork carries "Sponsorship Opportunities" in gold above the
wordmark. Each send wants its own line there, so this erases that one line and
sets a new one in its place, at the same face, size and baseline.

Erasing is the hard part. Three things caused visible damage on earlier passes,
and each is handled below:

  * The gold's bright core is bright enough to pass a naive "is this white?"
    test, which then protects the very pixels being erased and leaves the old
    line showing through. Gold is warm, so the test also requires neutrality.
  * A mask that only just covers the glyphs leaves their antialiased halo
    behind, which reads as a pale smudge. The mask is dilated well past the
    glyph edges and held clear of the white wordmark below.
  * Filling from one flat colour leaves a patch wherever the background is not
    flat - the palm frond crosses the line on the right. The fill comes from a
    normalised-convolution estimate of the background with every glyph excluded,
    so it follows the local tone, and is feathered at the edges.

Usage:  python3 tools/retitle_banner.py "Register Today!" out-name.jpg
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(HERE, "_assets")
SOURCE = os.path.join(ASSETS, "techweek-2026.jpg")
FONT = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"

PT, BASELINE = 44, 89      # matched to the line being replaced
CLEAN = (slice(14, 46), slice(130, 560))   # flat navy, for the grain estimate


def dilate(mask, k):
    return np.array(Image.fromarray((mask * 255).astype(np.uint8))
                    .filter(ImageFilter.MaxFilter(k))) > 0


def boxblur(x, r, passes=3):
    """Three box passes approximate a Gaussian, via integral images."""
    for _ in range(passes):
        p = np.pad(x, ((r + 1, r), (0, 0)), mode="edge")
        c = np.cumsum(p, 0)
        x = (c[2 * r + 1:] - c[:-(2 * r + 1)]) / (2 * r + 1)
        p = np.pad(x, ((0, 0), (r + 1, r)), mode="edge")
        c = np.cumsum(p, 1)
        x = (c[:, 2 * r + 1:] - c[:, :-(2 * r + 1)]) / (2 * r + 1)
    return x


def retitle(text, out_path, source=SOURCE):
    a = np.array(Image.open(source).convert("RGB")).astype(np.float64)
    h, w, _ = a.shape

    gold = (a[:, :, 0] > 140) & (a[:, :, 1] > 100) & (a[:, :, 2] < 120) \
        & (a[:, :, 0] - a[:, :, 2] > 50)
    white = (a.sum(2) > 430) & (np.abs(a[:, :, 0] - a[:, :, 2]) < 40)

    line = gold.copy()
    line[110:, :] = False                      # the topper only
    core = np.array(Image.fromarray((line * 255).astype(np.uint8))
                    .filter(ImageFilter.MinFilter(5))) > 0
    ink = tuple(int(v) for v in np.median(a[core], 0))

    mask = dilate(line, 17) & ~dilate(white, 5)
    mask[100:, :] = False
    missed = (line & ~mask).sum()
    assert missed < 50, f"{missed} pixels of the old line are not covered"

    keep = (~(mask | dilate(gold, 7) | dilate(white, 7))).astype(np.float64)
    weight = boxblur(keep, 14)
    bg = np.stack([boxblur(a[:, :, c] * keep, 14) / np.maximum(weight, 1e-6)
                   for c in range(3)], -1)

    sd = a[CLEAN].reshape(-1, 3).std(0)
    rng = np.random.default_rng(11)
    fill = bg + rng.normal(0, sd, a.shape)

    # hard inside the glyphs, feathered across the ring beyond them, so the
    # repair has no rectangular edge
    alpha = np.clip(boxblur(dilate(line, 9).astype(np.float64), 3), 0, 1)
    alpha = np.maximum(alpha, dilate(line, 9).astype(np.float64)) * mask
    out = a * (1 - alpha[..., None]) + fill * alpha[..., None]

    plate = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
    s = 4
    layer = Image.new("L", (w * s, h * s), 0)
    ImageDraw.Draw(layer).text((w * s / 2, BASELINE * s), text, 255,
                               font=ImageFont.truetype(FONT, PT * s), anchor="ms")
    plate.paste(Image.new("RGB", (w, h), ink), (0, 0),
                layer.resize((w, h), Image.LANCZOS))
    plate.save(out_path, quality=96, subsampling=0)
    return out_path, missed


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    path, missed = retitle(sys.argv[1], os.path.join(ASSETS, sys.argv[2]))
    print(f"wrote {os.path.relpath(path, HERE)}  ({missed} stray pixels of the old line)")
