"""Take the gold topper off the Tech Week banner and leave nothing behind.

retitle_banner.py replaces that line with another; this removes it. The
difference matters for how the gap is filled. Painting the whole band flat
leaves a rectangle you can see: the patch carries different grain from the
navy around it, and the seam reads as a bar even when the colour matches.

So nothing is painted except the letters themselves. The mask is the gold,
dilated well past its antialiased edge, and every masked pixel is copied
from the clean navy above it in the same column, tiled downwards. The
background either side of the glyphs is never touched, so there is no
patch to notice.

Copied rather than synthesised because the navy is dark enough that
gaussian grain added to it clips at zero, and clipping only ever raises
the mean: a synthesised patch comes out measurably lighter than the navy
around it, which is exactly the ghost this is meant to avoid.

The white wordmark underneath is dilated and subtracted from the mask,
because the descender of "Today!" overlaps its first row -- but only just:
widen that guard and it starts shielding the gold sitting right above the
wordmark, which then survives as a fleck.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(HERE, "_assets")

CLEAN = slice(30, 60)     # rows of flat navy above the topper
SEARCH = 210              # the topper never reaches below this row


def dilate(mask, px):
    im = Image.fromarray((mask * 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.MaxFilter(px))) > 127


def clear(src, dst):
    a = np.asarray(Image.open(src).convert("RGB")).astype(np.float64)
    top = a[:SEARCH]

    # Gold is warm as well as bright, so the test needs both; bright alone
    # also selects the white wordmark.
    gold = (top[:, :, 0] > 85) & (top[:, :, 0] - top[:, :, 2] > 22)
    white = (top.min(2) > 140) & (np.abs(top[:, :, 0] - top[:, :, 2]) < 45)
    mask = dilate(gold, 11) & ~dilate(white, 3)

    ys, xs = np.nonzero(mask)
    span = CLEAN.stop - CLEAN.start
    a[ys, xs] = a[CLEAN.start + (ys - CLEAN.start) % span, xs]

    out = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    out.save(dst, "JPEG", quality=94, optimize=True)

    chk = np.asarray(Image.open(dst).convert("RGB")).astype(int)[:SEARCH]
    left = int(((chk[:, :, 0] > 110) & (chk[:, :, 0] - chk[:, :, 2] > 40)).sum())
    return out.size, mask.sum(), left


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    size, painted, left = clear(os.path.join(ASSETS, sys.argv[1]),
                                os.path.join(ASSETS, sys.argv[2]))
    print(f"wrote _assets/{sys.argv[2]} {size}  {painted} px painted, "
          f"{left} gold px remaining")
