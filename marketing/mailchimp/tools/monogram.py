"""Draw an initials tile for a speaker with no photograph.

The summit programme page does this for Cecilia Sanchez: a "CS" tile where
the other panelists have portraits. A monogram is the right answer where a
placeholder is not, because it is a finished design rather than a gap
waiting to be filled, and it keeps the grid even without implying the
photograph is still coming.

Sized and toned to sit beside the cropped headshots without drawing the eye.
"""
import sys

from PIL import Image, ImageDraw, ImageFont

SIZE = 500
BG = "#E4EAF6"      # the pale blue already used for reversed body copy
INK = "#204396"     # LBA blue
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def monogram(initials, dst, size=SIZE):
    im = Image.new("RGB", (size, size), BG)
    d = ImageDraw.Draw(im)
    # Bind the point size to the tile so the glyphs keep their proportion
    # whatever size the caller asks for.
    f = ImageFont.truetype(FONT, int(size * 0.34))
    box = d.textbbox((0, 0), initials, font=f)
    # textbbox carries the font's own bearing, so subtract it rather than
    # centring on the raw width and height, which leaves the text low.
    d.text(((size - (box[2] - box[0])) / 2 - box[0],
            (size - (box[3] - box[1])) / 2 - box[1]),
           initials, font=f, fill=INK)
    im.save(dst, "JPEG", quality=92, optimize=True)
    return dst


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: monogram.py INITIALS DEST")
    print(monogram(sys.argv[1], sys.argv[2]))
