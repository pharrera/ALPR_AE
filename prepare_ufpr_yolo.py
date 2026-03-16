"""
Convert UFPR-ALPR dataset to YOLO format for YOLOv8 detector training.

Input  (UFPR):
    data/UFPR-ALPR dataset/
        training/trackXXXX/trackXXXX[NN].png  + .txt
        validation/...
        testing/...

Output (YOLO):
    data/ufpr_yolo/
        train/images/  *.png
        train/labels/  *.txt   (YOLO format: class cx cy w h  normalised)
        valid/images/
        valid/labels/
        test/images/
        test/labels/
        plate_gt.json           maps image filename → plate_text (for OCR evaluation)

Usage:
    python prepare_ufpr_yolo.py
    python prepare_ufpr_yolo.py --src "data/UFPR-ALPR dataset" --dst data/ufpr_yolo
"""

import argparse
import json
import os
import shutil
from pathlib import Path

from utils.ufpr_data_loader import parse_ufpr_annotation


# Map UFPR split names → YOLO split names
SPLIT_MAP = {
    'training':   'train',
    'validation': 'valid',
    'testing':    'test',
}

IMG_W = 1920
IMG_H = 1080


def corners_to_yolo(x1: int, y1: int, x2: int, y2: int,
                    img_w: int = IMG_W, img_h: int = IMG_H):
    """
    Convert axis-aligned bbox (pixel) to YOLO format (normalised cx cy w h).
    """
    cx = (x1 + x2) / 2.0 / img_w
    cy = (y1 + y2) / 2.0 / img_h
    w  = (x2 - x1)        / img_w
    h  = (y2 - y1)        / img_h
    return cx, cy, w, h


def convert(src_root: str, dst_root: str):
    src_root = Path(src_root)
    dst_root = Path(dst_root)

    plate_gt = {}   # { "relative/image/path.png": "MLS5511" }
    total = 0

    for ufpr_split, yolo_split in SPLIT_MAP.items():
        split_dir = src_root / ufpr_split
        if not split_dir.exists():
            print(f"  [SKIP] {split_dir} not found")
            continue

        img_out = dst_root / yolo_split / 'images'
        lbl_out = dst_root / yolo_split / 'labels'
        img_out.mkdir(parents=True, exist_ok=True)
        lbl_out.mkdir(parents=True, exist_ok=True)

        txt_files = sorted(split_dir.glob('**/*.txt'))
        count = 0

        for txt_path in txt_files:
            img_path = txt_path.with_suffix('.png')
            if not img_path.exists():
                continue

            try:
                ann = parse_ufpr_annotation(str(txt_path))
            except Exception as e:
                print(f"  [WARN] Could not parse {txt_path}: {e}")
                continue

            bbox = ann.get('plate_bbox')
            if bbox is None:
                continue

            x1, y1, x2, y2 = bbox

            # Basic sanity check
            if x2 <= x1 or y2 <= y1:
                continue

            cx, cy, w, h = corners_to_yolo(x1, y1, x2, y2)

            # Clamp to [0, 1]
            cx = max(0.0, min(1.0, cx))
            cy = max(0.0, min(1.0, cy))
            w  = max(0.0, min(1.0, w))
            h  = max(0.0, min(1.0, h))

            # Unique filename: trackXXXX_frameNN
            stem = img_path.stem          # e.g. track0001[01]
            # Replace brackets so filename is shell-safe
            safe_stem = stem.replace('[', '_').replace(']', '')
            out_img = img_out / f"{safe_stem}.png"
            out_lbl = lbl_out / f"{safe_stem}.txt"

            shutil.copy2(img_path, out_img)

            with open(out_lbl, 'w') as f:
                f.write(f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")

            # Record ground truth plate text
            rel_key = f"{yolo_split}/images/{safe_stem}.png"
            plate_gt[rel_key] = ann.get('plate_text', '')
            count += 1

        print(f"  {ufpr_split:12s} → {yolo_split:5s}: {count} images")
        total += count

    # Save ground truth mapping
    gt_path = dst_root / 'plate_gt.json'
    with open(gt_path, 'w') as f:
        json.dump(plate_gt, f, indent=2)

    print(f"\nTotal: {total} images converted")
    print(f"Ground truth saved to: {gt_path}")
    print(f"\nYOLO dataset ready at: {dst_root}")
    print(f"Run detector training with:")
    print(f"  python train_detector.py --data-dir {dst_root.resolve()}")


def main():
    parser = argparse.ArgumentParser(description="Convert UFPR-ALPR to YOLO format")
    parser.add_argument(
        '--src', default='data/UFPR-ALPR dataset',
        help='Path to UFPR-ALPR dataset root'
    )
    parser.add_argument(
        '--dst', default='data/ufpr_yolo',
        help='Output path for YOLO-format dataset'
    )
    args = parser.parse_args()

    print(f"Source : {args.src}")
    print(f"Output : {args.dst}\n")
    convert(args.src, args.dst)


if __name__ == '__main__':
    main()
