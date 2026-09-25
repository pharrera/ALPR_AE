"""Crop the honoree headshots to a common framing.

The four photographs arrive from four different photographers, and in the
2x2 grid that shows: measured on the versions published to the Tech Week
site, the face filled 62% of the frame for one honoree and 28% for
another, and two of the four sat noticeably off-centre. Side by side that
reads as a mistake rather than as four portraits.

This re-crops each source so every face is the same size and sits in the
same place, which is the only thing a grid needs to look deliberate.

The one constraint worth knowing: a crop can only ever tighten. The
tightest source (Hacegaba at 62%) therefore sets the floor for the whole
set, so TARGET_FACE sits just under it and that image passes through close
to untouched while the others come in to meet it. Raising TARGET_FACE
above the tightest source would need canvas invented around it, which is
not worth doing to someone's portrait. FACE_CY is likewise set by that
image: pulled any higher, a tight crop takes the top off the head on the
faces that sit highest in their originals.
"""
import os
import sys

import cv2
from PIL import Image

TARGET_FACE = 0.56   # face width as a fraction of the finished frame
FACE_CX = 0.50       # where the face centre sits, left to right
FACE_CY = 0.52       # and top to bottom: low enough to keep the crown in
OUT_PX = 500         # 2x the 250px the email renders them at

CASCADE = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"


def find_face(path):
    """Return the largest detected face as (x, y, w, h)."""
    img = cv2.imread(path)
    if img is None:
        raise SystemExit(f"cannot read {path}")
    grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = cv2.CascadeClassifier(CASCADE).detectMultiScale(
        grey, scaleFactor=1.05, minNeighbors=6, minSize=(60, 60))
    if len(faces) == 0:
        raise SystemExit(f"no face found in {path}")
    return max(faces, key=lambda r: r[2] * r[3])


def normalize(src, dst):
    x, y, w, h = find_face(src)
    im = Image.open(src).convert("RGB")
    W, H = im.size

    # The crop is square, so it can be no larger than the shorter side.
    side = min(w / TARGET_FACE, W, H)
    left = (x + w / 2) - FACE_CX * side
    top = (y + h / 2) - FACE_CY * side

    # Slide the window back inside the frame rather than shrinking it, so a
    # face near an edge keeps its scale and only loses its exact centring.
    left = max(0, min(left, W - side))
    top = max(0, min(top, H - side))

    out = im.crop((round(left), round(top),
                   round(left + side), round(top + side)))
    out = out.resize((OUT_PX, OUT_PX), Image.LANCZOS)
    out.save(dst, "JPEG", quality=88, optimize=True)
    return w / side, (x + w / 2 - left) / side, (y + h / 2 - top) / side


if __name__ == "__main__":
    pairs = sys.argv[1:]
    if not pairs or len(pairs) % 2:
        raise SystemExit("usage: normalize_headshots.py SRC DST [SRC DST ...]")
    for src, dst in zip(pairs[::2], pairs[1::2]):
        frac, cx, cy = normalize(src, dst)
        print(f"{os.path.basename(dst):24s} face {frac:.0%} of frame  "
              f"centre ({cx:.2f}, {cy:.2f})")
