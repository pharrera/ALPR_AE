"""
UFPR-ALPR Dataset Loader

Parses UFPR-ALPR annotation files (.txt) to extract:
  - Ground truth license plate text  (plate: MLS5511)
  - License plate bounding box       (from corners)
  - Vehicle bounding box             (position_vehicle)
  - Individual character positions   (char 1..7)

Dataset structure (each split: training / validation / testing):
    <split>/
        trackXXXX/
            trackXXXX[01].png
            trackXXXX[01].txt   ← annotation file
            trackXXXX[02].png
            ...
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


# ── Annotation Parser ────────────────────────────────────────────────────────

def parse_ufpr_annotation(txt_path: str) -> Dict:
    """
    Parse a single UFPR-ALPR annotation file.

    Returns a dict with:
        camera          str
        vehicle_bbox    (x, y, w, h)  – pixel coords, top-left origin
        vehicle_type    str  ('car' | 'motorcycle')
        make / model / year  str
        plate_text      str  e.g. 'MLS5511'
        plate_corners   [(x,y), (x,y), (x,y), (x,y)]  – TL TR BR BL
        plate_bbox      (x1, y1, x2, y2)  – axis-aligned bbox derived from corners
        characters      list of {'char': str, 'bbox': (x,y,w,h)}
    """
    ann = {}
    characters = []

    with open(txt_path, 'r', encoding='utf-8') as f:
        lines = [l.strip() for l in f.readlines()]

    for line in lines:
        if line.startswith('camera:'):
            ann['camera'] = line.split(':', 1)[1].strip()

        elif line.startswith('position_vehicle:'):
            vals = list(map(int, line.split(':', 1)[1].strip().split()))
            ann['vehicle_bbox'] = tuple(vals)          # x y w h

        elif line.startswith('type:'):
            ann['vehicle_type'] = line.split(':', 1)[1].strip()

        elif line.startswith('make:'):
            ann['make'] = line.split(':', 1)[1].strip()

        elif line.startswith('model:'):
            ann['model'] = line.split(':', 1)[1].strip()

        elif line.startswith('year:'):
            ann['year'] = line.split(':', 1)[1].strip()

        elif line.startswith('plate:'):
            ann['plate_text'] = line.split(':', 1)[1].strip()

        elif line.startswith('corners:'):
            # Format: x1,y1 x2,y2 x3,y3 x4,y4
            corner_strs = line.split(':', 1)[1].strip().split()
            corners = [tuple(map(int, c.split(','))) for c in corner_strs]
            ann['plate_corners'] = corners
            # Derive axis-aligned bbox
            xs = [c[0] for c in corners]
            ys = [c[1] for c in corners]
            ann['plate_bbox'] = (min(xs), min(ys), max(xs), max(ys))  # x1,y1,x2,y2

        elif re.match(r'char \d+:', line):
            # Format: char N: x y w h
            vals = list(map(int, line.split(':', 1)[1].strip().split()))
            characters.append({'bbox': tuple(vals)})   # x y w h

    ann['characters'] = characters
    return ann


# ── Dataset Class ─────────────────────────────────────────────────────────────

class UFPRDataset:
    """
    UFPR-ALPR dataset iterator.

    Usage:
        ds = UFPRDataset('/path/to/UFPR-ALPR dataset', split='training')
        sample = ds[0]
        print(sample['plate_text'])   # 'MLS5511'
    """

    SPLITS = ('training', 'validation', 'testing')

    def __init__(self, dataset_root: str, split: str = 'training'):
        self.root = Path(dataset_root)
        assert split in self.SPLITS, f"split must be one of {self.SPLITS}"
        self.split = split

        split_dir = self.root / split
        if not split_dir.exists():
            raise FileNotFoundError(f"Split directory not found: {split_dir}")

        # Collect all annotation files
        self.samples = sorted(split_dir.glob('**/*.txt'))
        print(f"[UFPRDataset] {split}: {len(self.samples)} annotated frames found")

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Dict:
        """
        Returns:
            image       np.ndarray  BGR, 1920×1080
            plate_text  str         Ground truth plate text (e.g. 'MLS5511')
            plate_bbox  tuple       (x1, y1, x2, y2) pixel coordinates
            vehicle_bbox tuple      (x, y, w, h) pixel coordinates
            characters  list        List of char bboxes
            image_path  str
            txt_path    str
        """
        txt_path = self.samples[idx]
        img_path = txt_path.with_suffix('.png')

        if not img_path.exists():
            raise FileNotFoundError(f"Image not found: {img_path}")

        image = cv2.imread(str(img_path))
        ann   = parse_ufpr_annotation(str(txt_path))

        return {
            'image':        image,
            'plate_text':   ann.get('plate_text', ''),
            'plate_bbox':   ann.get('plate_bbox', None),
            'plate_corners': ann.get('plate_corners', []),
            'vehicle_bbox': ann.get('vehicle_bbox', None),
            'characters':   ann.get('characters', []),
            'camera':       ann.get('camera', ''),
            'vehicle_type': ann.get('vehicle_type', ''),
            'image_path':   str(img_path),
            'txt_path':     str(txt_path),
        }

    def get_plate_crop(self, idx: int) -> Tuple[np.ndarray, str]:
        """
        Returns (plate_crop_image, plate_text) for the given index.
        Useful for training the autoencoder on plate crops.
        """
        sample = self[idx]
        image  = sample['image']
        bbox   = sample['plate_bbox']
        text   = sample['plate_text']

        if bbox is None or image is None:
            return None, text

        x1, y1, x2, y2 = bbox
        # Clamp to image bounds
        h, w = image.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        crop = image[y1:y2, x1:x2]
        return crop, text


# ── OCR Accuracy (True Ground Truth) ─────────────────────────────────────────

def compute_plate_accuracy(predicted: str, ground_truth: str) -> float:
    """
    Compute character-level accuracy between OCR prediction and ground truth.

    Args:
        predicted:     OCR output string (may have spaces/special chars)
        ground_truth:  True plate text from UFPR annotation (e.g. 'MLS5511')

    Returns:
        Float in [0, 1] — fraction of correct characters
    """
    # Normalise: uppercase, strip spaces
    pred = predicted.upper().replace(' ', '').replace('-', '')
    gt   = ground_truth.upper().replace(' ', '').replace('-', '')

    if not gt:
        return 0.0

    if len(pred) == 0:
        return 0.0

    # Character-level accuracy (align by length)
    max_len = max(len(pred), len(gt))
    matches = sum(1 for a, b in zip(pred, gt) if a == b)
    return matches / max_len


# ── Quick Test ────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python ufpr_data_loader.py /path/to/UFPR-ALPR\\ dataset")
        sys.exit(1)

    root = sys.argv[1]
    ds   = UFPRDataset(root, split='training')

    sample = ds[0]
    print(f"\nFirst sample:")
    print(f"  Image shape  : {sample['image'].shape}")
    print(f"  Plate text   : {sample['plate_text']}")
    print(f"  Plate bbox   : {sample['plate_bbox']}")
    print(f"  Vehicle bbox : {sample['vehicle_bbox']}")
    print(f"  Num chars    : {len(sample['characters'])}")
    print(f"  Camera       : {sample['camera']}")

    crop, text = ds.get_plate_crop(0)
    print(f"\nPlate crop shape: {crop.shape if crop is not None else 'N/A'}")
    print(f"Plate text (GT) : {text}")

    # Test accuracy function
    print(f"\nAccuracy test (MLS5511 vs MLS5511): {compute_plate_accuracy('MLS5511','MLS5511'):.2f}")
    print(f"Accuracy test (MLS551  vs MLS5511): {compute_plate_accuracy('MLS551','MLS5511'):.2f}")
    print(f"Accuracy test (ABC1234 vs MLS5511): {compute_plate_accuracy('ABC1234','MLS5511'):.2f}")
