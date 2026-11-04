"""Clear the LBA lockup off a session banner, leaving white space.

The e-blasts carry the Insights masthead above the session banner, so the
banner's own logo is the second LBA mark in the first 350px. Removing it
leaves the masthead to do the branding.

The left panel of these banners is flat #FDFDFD, so a rectangle fill is
enough -- no texture to match, unlike the navy Tech Week topper that
clear_banner_topper.py had to copy real pixels into.

The box is measured rather than hard-coded: everything meaningfully darker
than the panel, above the series pill and left of the artwork, is the logo.

    python3 tools/clear_banner_logo.py _assets/ai-session3.jpg \
                                       _assets/ai-session3-nologo.jpg
"""
import sys

import numpy as np
from PIL import Image

BG = (253, 253, 253)      # the panel's own white
PILL_TOP = 106            # first row of the "BUILDING AN..." pill
PAD = 12                  # breathing room around the measured box


def main(src, dst):
    im = Image.open(src).convert("RGB")
    a = np.asarray(im).astype(int)

    # The artwork on the right starts somewhere past the middle; find where,
    # so the search for the logo stops short of it.
    top = a[:PILL_TOP]
    ink = np.abs(top - np.array(BG)).max(axis=2) > 18
    cols = np.nonzero(ink.any(axis=0))[0]
    if not len(cols):
        sys.exit("nothing to clear above row %d" % PILL_TOP)
    gaps = np.nonzero(np.diff(cols) > 40)[0]
    right = cols[gaps[0]] if len(gaps) else cols[-1]

    box = ink[:, :right + 1]
    ys, xs = np.nonzero(box)
    x0, x1 = max(xs.min() - PAD, 0), min(xs.max() + PAD, im.width - 1)
    y0, y1 = max(ys.min() - PAD, 0), min(ys.max() + PAD, PILL_TOP - 1)
    print("clearing x %d-%d, y %d-%d" % (x0, x1, y0, y1))

    a[y0:y1 + 1, x0:x1 + 1] = BG
    Image.fromarray(a.astype("uint8")).save(dst, quality=95, subsampling=0)

    left = np.abs(np.asarray(Image.open(dst).convert("RGB")).astype(int)[y0:y1 + 1, x0:x1 + 1]
                  - np.array(BG)).max()
    print("%s written; max deviation in the cleared box: %d" % (dst, left))


if __name__ == "__main__":
    main(*sys.argv[1:3])
