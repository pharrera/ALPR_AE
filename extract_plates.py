"""
Extract cropped license plate regions from the detection dataset.

Usage:
    python extract_plates.py --data-dir data --output-dir data/plates

This creates the training data needed for the autoencoder by:
1. Reading images and YOLO-format annotations
2. Cropping plate regions with padding
3. Saving crops organized by split (train/val)
"""

import argparse
import os

from utils.data_loader import extract_plate_crops


def main():
    parser = argparse.ArgumentParser(description="Extract plate crops from dataset")
    parser.add_argument(
        "--data-dir", default="data", help="Root dataset directory (contains train/, valid/, test/)"
    )
    parser.add_argument(
        "--output-dir", default="data/plates", help="Output directory for crops"
    )
    parser.add_argument(
        "--padding", type=float, default=0.1, help="Padding fraction around plates"
    )
    args = parser.parse_args()

    for split in ["train", "valid", "test"]:
        split_dir = os.path.join(args.data_dir, split)
        img_dir = os.path.join(split_dir, "images")
        label_dir = os.path.join(split_dir, "labels")

        if not os.path.exists(img_dir):
            print(f"Skipping {split}: {img_dir} not found")
            continue

        out_split = "val" if split == "valid" else split
        output = os.path.join(args.output_dir, out_split)

        print(f"\nExtracting plates from {split}...")
        count = extract_plate_crops(
            image_dir=img_dir,
            label_dir=label_dir,
            output_dir=output,
            padding=args.padding,
        )
        print(f"  -> {count} plates extracted to {output}")

    print("\nDone! Plate crops ready for autoencoder training.")


if __name__ == "__main__":
    main()
