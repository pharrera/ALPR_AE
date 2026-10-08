"""Draw a labelled stand-in for a photograph that has not arrived yet.

A recap e-blast is mostly pictures, and the copy has to be approved before
the pictures exist. These tiles hold the slots open so the draft can be
read at full length, and each one names the shot it is waiting for, so the
person picking photographs is answering a specific question rather than
guessing how many are needed.

Deliberately unmistakable: nothing here could be read as finished artwork
if one ever survived into a send.
"""
import sys

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 600
BG, EDGE, INK, MUTED = "#E9EDF1", "#B9C3CE", "#5A6675", "#8A95A3"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def placeholder(label, dst, w=W, h=H):
    im = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(im)

    inset, dash, gap = 24, 22, 16
    for x in range(inset, w - inset, dash + gap):
        for y in (inset, h - inset):
            d.line([(x, y), (min(x + dash, w - inset), y)], fill=EDGE, width=4)
    for y in range(inset, h - inset, dash + gap):
        for x in (inset, w - inset):
            d.line([(x, y), (x, min(y + dash, h - inset))], fill=EDGE, width=4)

    # A camera, so the tile reads as "picture missing" before anything is read.
    cx, cy = w // 2, h // 2 - 58
    d.rounded_rectangle([cx - 104, cy - 58, cx + 104, cy + 62], 14, fill=EDGE)
    d.rectangle([cx - 46, cy - 78, cx + 22, cy - 56], fill=EDGE)
    d.ellipse([cx - 44, cy - 38, cx + 44, cy + 50], fill=BG)
    d.ellipse([cx - 26, cy - 20, cx + 26, cy + 32], fill=EDGE)

    for text, font, yy, col in ((label.upper(), ImageFont.truetype(BOLD, 40), h // 2 + 64, INK),
                                ("photo to come", ImageFont.truetype(REG, 28), h // 2 + 122, MUTED)):
        tw = d.textbbox((0, 0), text, font=font)[2]
        d.text(((w - tw) // 2, yy), text, font=font, fill=col)

    im.save(dst, "JPEG", quality=88, optimize=True)
    return dst


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit('usage: photo_placeholder.py "Label" DEST')
    print(placeholder(sys.argv[1], sys.argv[2]))
