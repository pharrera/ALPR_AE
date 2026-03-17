"""
Convert CCPD dataset to YOLO format for combined training with UFPR-ALPR.

CCPD (Chinese City Parking Dataset) encodes all annotations in filenames,
making it self-contained. This script:
1. Parses bounding box + plate text from filenames
2. Writes YOLO-format label files
3. Extracts plate crops for autoencoder training
4. Creates a plate_gt.json mapping for OCR evaluation

Usage:
    python prepare_ccpd.py \
        --ccpd-dir data/ccpd/CCPD2019 \
        --output-dir data/ccpd_yolo \
        --plate-output-dir data/plates/ccpd \
        --max-images 50000
"""

import argparse
import os
import json
import random
import shutil
import cv2
from pathlib import Path
from tqdm import tqdm


# CCPD character mapping
PROVINCES = [
    "皖", "沪", "津", "渝", "冀", "晋", "蒙", "辽", "吉", "黑",
    "苏", "浙", "京", "闽", "赣", "鲁", "豫", "鄂", "湘", "粤",
    "桂", "琼", "川", "贵", "云", "藏", "陕", "甘", "青", "宁", "新",
]
ADS = [
    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K', 'L', 'M',
    'N', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
    '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
]


def parse_ccpd_filename(filename: str):
    """
    Parse CCPD filename to extract bounding box and plate text.

    Returns:
        (bbox_x1, bbox_y1, bbox_x2, bbox_y2), plate_text
        or None, None on parse failure
    """
    try:
        stem = Path(filename).stem
        parts = stem.split('-')
        if len(parts) < 7:
            return None, None

        # Bounding box: field[2] = "x1&y1_x2&y2"
        bbox_str = parts[2]
        coords = bbox_str.split('_')
        x1, y1 = [int(c) for c in coords[0].split('&')]
        x2, y2 = [int(c) for c in coords[1].split('&')]

        # Plate number: field[4] = indices separated by '_'
        plate_indices = [int(idx) for idx in parts[4].split('_')]

        # First character is province
        plate_text = PROVINCES[plate_indices[0]]
        # Rest are alphanumeric
        for idx in plate_indices[1:]:
            if idx < len(ADS):
                plate_text += ADS[idx]

        return (x1, y1, x2, y2), plate_text
    except (IndexError, ValueError):
        return None, None


def convert_to_yolo_format(bbox, img_w, img_h):
    """Convert (x1, y1, x2, y2) to YOLO format (cx, cy, w, h) normalized."""
    x1, y1, x2, y2 = bbox
    cx = (x1 + x2) / 2.0 / img_w
    cy = (y1 + y2) / 2.0 / img_h
    w = (x2 - x1) / img_w
    h = (y2 - y1) / img_h
    return cx, cy, w, h


def main():
    parser = argparse.ArgumentParser(description="Convert CCPD to YOLO format")
    parser.add_argument("--ccpd-dir", required=True,
                        help="Path to CCPD dataset root (e.g. data/ccpd/CCPD2019)")
    parser.add_argument("--output-dir", default="data/ccpd_yolo",
                        help="Output YOLO-format dataset directory")
    parser.add_argument("--plate-output-dir", default="data/plates/ccpd",
                        help="Output directory for plate crops")
    parser.add_argument("--max-images", type=int, default=50000,
                        help="Maximum images to process")
    parser.add_argument("--val-split", type=float, default=0.1,
                        help="Validation split ratio")
    parser.add_argument("--test-split", type=float, default=0.1,
                        help="Test split ratio")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    ccpd_dir = Path(args.ccpd_dir)

    # Find all CCPD subdirectories with images
    # Common CCPD splits: ccpd_base, ccpd_blur, ccpd_challenge, ccpd_db,
    # ccpd_fn, ccpd_rotate, ccpd_tilt, ccpd_weather
    image_paths = []
    for subdir in sorted(ccpd_dir.iterdir()):
        if subdir.is_dir() and subdir.name.startswith("ccpd_"):
            for img_path in subdir.glob("*.jpg"):
                image_paths.append(img_path)

    # Also check root dir for images
    for img_path in ccpd_dir.glob("*.jpg"):
        image_paths.append(img_path)

    if not image_paths:
        # Try finding images in any subdirectory
        for img_path in ccpd_dir.rglob("*.jpg"):
            image_paths.append(img_path)

    print(f"Found {len(image_paths)} CCPD images")

    if not image_paths:
        print("ERROR: No images found. Check --ccpd-dir path.")
        print(f"  Searched: {ccpd_dir}")
        return

    # Shuffle and limit
    random.shuffle(image_paths)
    image_paths = image_paths[:args.max_images]

    # Split into train/val/test
    n_total = len(image_paths)
    n_test = int(n_total * args.test_split)
    n_val = int(n_total * args.val_split)
    n_train = n_total - n_val - n_test

    splits = {
        "train": image_paths[:n_train],
        "valid": image_paths[n_train:n_train + n_val],
        "test": image_paths[n_train + n_val:],
    }

    # Create output directories
    output_dir = Path(args.output_dir)
    plate_dir = Path(args.plate_output_dir)

    for split in ["train", "valid", "test"]:
        (output_dir / split / "images").mkdir(parents=True, exist_ok=True)
        (output_dir / split / "labels").mkdir(parents=True, exist_ok=True)
    plate_dir.mkdir(parents=True, exist_ok=True)

    plate_gt = {}
    stats = {"total": 0, "success": 0, "failed": 0}

    for split, paths in splits.items():
        print(f"\nProcessing {split}: {len(paths)} images")

        for img_path in tqdm(paths, desc=split):
            stats["total"] += 1

            # Parse filename
            bbox, plate_text = parse_ccpd_filename(img_path.name)
            if bbox is None:
                stats["failed"] += 1
                continue

            # Read image to get dimensions
            img = cv2.imread(str(img_path))
            if img is None:
                stats["failed"] += 1
                continue

            h, w = img.shape[:2]
            x1, y1, x2, y2 = bbox

            # Validate bbox
            if x1 >= x2 or y1 >= y2 or x1 < 0 or y1 < 0 or x2 > w or y2 > h:
                stats["failed"] += 1
                continue

            stats["success"] += 1

            # Generate a clean filename
            out_name = f"ccpd_{stats['success']:06d}"

            # Copy image
            dst_img = output_dir / split / "images" / f"{out_name}.jpg"
            shutil.copy2(str(img_path), str(dst_img))

            # Write YOLO label
            cx, cy, bw, bh = convert_to_yolo_format(bbox, w, h)
            dst_label = output_dir / split / "labels" / f"{out_name}.txt"
            with open(dst_label, "w") as f:
                f.write(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")

            # Store plate GT text (alphanumeric only for OCR comparison)
            # Skip Chinese province character for OCR training
            alnum_text = ''.join(c for c in plate_text if c.isalnum() and c.isascii())
            gt_key = f"{split}/images/{out_name}.jpg"
            plate_gt[gt_key] = alnum_text

            # Extract plate crop for autoencoder training
            pad_x = int((x2 - x1) * 0.1)
            pad_y = int((y2 - y1) * 0.1)
            crop_x1 = max(0, x1 - pad_x)
            crop_y1 = max(0, y1 - pad_y)
            crop_x2 = min(w, x2 + pad_x)
            crop_y2 = min(h, y2 + pad_y)

            crop = img[crop_y1:crop_y2, crop_x1:crop_x2]
            if crop.size > 0:
                crop_path = plate_dir / f"{out_name}_plate0.jpg"
                cv2.imwrite(str(crop_path), crop)

    # Save plate GT
    gt_path = output_dir / "plate_gt.json"
    with open(gt_path, "w") as f:
        json.dump(plate_gt, f, indent=2, ensure_ascii=False)

    # Write data.yaml for YOLO training
    yaml_path = output_dir / "data.yaml"
    with open(yaml_path, "w") as f:
        f.write(f"path: {output_dir.resolve()}\n")
        f.write("train: train/images\n")
        f.write("val: valid/images\n")
        f.write("test: test/images\n\n")
        f.write("nc: 1\n")
        f.write("names: ['plate']\n")

    print(f"\n{'='*60}")
    print(f"CCPD Conversion Complete")
    print(f"{'='*60}")
    print(f"Total images:   {stats['total']}")
    print(f"Successful:     {stats['success']}")
    print(f"Failed/skipped: {stats['failed']}")
    print(f"Train/Val/Test: {len(splits['train'])}/{len(splits['valid'])}/{len(splits['test'])}")
    print(f"Plate GT entries: {len(plate_gt)}")
    print(f"\nOutputs:")
    print(f"  YOLO dataset:  {output_dir}")
    print(f"  Plate crops:   {plate_dir}")
    print(f"  Plate GT JSON: {gt_path}")
    print(f"  data.yaml:     {yaml_path}")


if __name__ == "__main__":
    main()
