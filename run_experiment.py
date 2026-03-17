"""
Run the full resolution degradation experiment.

Usage:
    python run_experiment.py \
        --detector-weights results/detection/plate_detection/weights/best.pt \
        --autoencoder-weights results/autoencoder/unet/best_autoencoder.pth \
        --test-dir data/test

This is the main experiment script that:
1. Loads all trained models
2. Runs detection + OCR at multiple resolutions
3. Compares baseline vs. upscale vs. autoencoder conditions
4. Generates all result plots and metrics
"""

import argparse
import os
import sys
import json
import torch
import cv2
import numpy as np
from pathlib import Path

from utils.data_loader import load_config
from utils.device import resolve_device
from utils.metrics import MetricsTracker
from utils.visualization import plot_resolution_comparison, plot_degradation_grid
from models.detector import PlateDetector
from models.autoencoder import UNetAutoencoder, ConvAutoencoder
from experiments.resolution_experiment import ResolutionExperiment


def load_test_data(test_dir: str, max_images: int = 100, ocr_engine=None,
                   plate_gt_path: str = None):
    """
    Load test images, bounding box annotations, and ground truth plate text.

    If plate_gt_path is provided (e.g. plate_gt.json from UFPR-ALPR), verified
    ground truth plate text is loaded — enabling TRUE OCR accuracy measurement.

    If no plate_gt_path is available and ocr_engine is provided, we fall back to
    recording OCR output on clean full-resolution crops as a *reference* reading
    for OCR CONSISTENCY measurement (not accuracy).
    """
    img_dir = Path(test_dir) / "images"
    label_dir = Path(test_dir) / "labels"

    if not img_dir.exists():
        img_dir = Path(test_dir)
        label_dir = Path(test_dir)

    # Load verified ground truth plate text if available (UFPR-ALPR)
    plate_gt = {}
    if plate_gt_path and os.path.exists(plate_gt_path):
        with open(plate_gt_path) as f:
            plate_gt = json.load(f)
        print(f"  Loaded {len(plate_gt)} verified plate text entries from {plate_gt_path}")

    # Determine which split this is (for plate_gt key lookup)
    # plate_gt keys are like "test/images/track0091_01.png"
    split_name = ""
    for candidate in ["test", "valid", "train"]:
        if candidate in str(test_dir):
            split_name = candidate
            break

    images = []
    gt_boxes = []
    gt_texts = []

    for img_path in sorted(img_dir.glob("*"))[:max_images]:
        if img_path.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            continue

        image = cv2.imread(str(img_path))
        if image is None:
            continue
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        images.append(image)

        # Load YOLO bounding box annotations
        h, w = image.shape[:2]
        label_path = label_dir / (img_path.stem + ".txt")
        boxes = []
        if label_path.exists():
            with open(label_path) as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        x_c, y_c, bw, bh = map(float, parts[1:5])
                        boxes.append({
                            "bbox": [
                                (x_c - bw / 2) * w,
                                (y_c - bh / 2) * h,
                                (x_c + bw / 2) * w,
                                (y_c + bh / 2) * h,
                            ],
                            "confidence": 1.0,
                        })

        gt_boxes.append(boxes)

        # Get ground truth plate text
        gt_text = ""
        # Try verified GT from plate_gt.json first
        gt_key = f"{split_name}/images/{img_path.name}"
        if gt_key in plate_gt:
            gt_text = plate_gt[gt_key]
        elif ocr_engine is not None and boxes:
            # Fallback: OCR reference reading from clean crop
            b = boxes[0]["bbox"]
            x1, y1, x2, y2 = int(b[0]), int(b[1]), int(b[2]), int(b[3])
            pad_x = int((x2 - x1) * 0.1)
            pad_y = int((y2 - y1) * 0.1)
            x1, y1 = max(0, x1 - pad_x), max(0, y1 - pad_y)
            x2, y2 = min(w, x2 + pad_x), min(h, y2 + pad_y)
            crop = image[y1:y2, x1:x2]
            if crop.size > 0:
                results = ocr_engine.readtext(crop)
                gt_text = "".join([r[1] for r in results]).upper()

        gt_texts.append(gt_text)

    n_with_gt = sum(1 for t in gt_texts if t)
    n_verified = sum(1 for t in gt_texts if t and any(
        f"{split_name}/images/" in k for k in plate_gt
    ))
    print(f"Loaded {len(images)} test images from {test_dir}")
    if plate_gt:
        print(f"  Verified ground truth text: {n_with_gt}/{len(images)} images")
    elif ocr_engine:
        print(f"  OCR reference readings: {n_with_gt}/{len(images)} (consistency only, not accuracy)")
    return images, gt_boxes, gt_texts


def main():
    parser = argparse.ArgumentParser(description="Run resolution experiment")
    parser.add_argument("--config", default="configs/config.yaml")
    parser.add_argument("--detector-weights", required=True)
    parser.add_argument("--autoencoder-weights", required=True)
    parser.add_argument("--autoencoder-type", choices=["conv", "unet"], default="unet")
    parser.add_argument("--test-dir", required=True)
    parser.add_argument("--max-images", type=int, default=100)
    parser.add_argument("--output-dir", default="results/experiment")
    parser.add_argument(
        "--device",
        default=None,
        help="Device to run on: auto, cuda, mps, or cpu",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    device = resolve_device(args.device)
    print(f"Device: {device}")

    # Load detector
    print("Loading detector...")
    detector = PlateDetector(
        model_path=args.detector_weights,
        confidence=config["detection"]["confidence_threshold"],
        iou_threshold=config["detection"]["iou_threshold"],
        device=device,
    )

    # Load autoencoder
    print("Loading autoencoder...")
    ae_config = config["autoencoder"]
    if args.autoencoder_type == "unet":
        autoencoder = UNetAutoencoder(
            in_channels=3,
            base_features=ae_config["encoder_channels"][0],
            depth=len(ae_config["encoder_channels"]),
        )
    else:
        autoencoder = ConvAutoencoder(
            in_channels=3,
            encoder_channels=ae_config["encoder_channels"],
            latent_dim=ae_config["latent_dim"],
            input_height=ae_config["input_size"],
            input_width=ae_config["input_width"],
        )

    state_dict = torch.load(args.autoencoder_weights, map_location=device)
    # Strip DataParallel "module." prefix if weights were saved on multi-GPU
    if any(k.startswith("module.") for k in state_dict):
        state_dict = {k[len("module."):]: v for k, v in state_dict.items()}
    autoencoder.load_state_dict(state_dict)
    autoencoder = autoencoder.to(device)
    autoencoder.eval()

    # Optional: load EasyOCR
    ocr_engine = None
    try:
        import easyocr
        ocr_engine = easyocr.Reader(["en"], gpu=(device == "cuda"))
        print("EasyOCR loaded for character recognition")
    except ImportError:
        print("EasyOCR not available; OCR metrics will be skipped")

    # Load test data — use verified GT from plate_gt.json if available (UFPR-ALPR)
    print("Loading test data...")
    plate_gt_path = config.get("data", {}).get("plate_gt_path", None)
    test_images, gt_boxes, gt_texts = load_test_data(
        args.test_dir, max_images=args.max_images, ocr_engine=ocr_engine,
        plate_gt_path=plate_gt_path,
    )

    # Run experiment
    experiment = ResolutionExperiment(
        detector=detector,
        classifier=None,
        autoencoder=autoencoder,
        ocr_engine=ocr_engine,
        config=config,
        device=device,
    )

    print("\n" + "=" * 60)
    print("RUNNING RESOLUTION DEGRADATION EXPERIMENT")
    print("=" * 60)

    results = experiment.run_full_experiment(
        test_images, gt_boxes, gt_texts, save_dir=args.output_dir
    )

    # Print final summary
    print("\n" + results.summary())

    # Generate degradation visualization for one sample
    if test_images:
        from utils.degradation import ImageDegrader
        degrader = ImageDegrader()
        resolutions = [int(640 * s) for s in config["experiment"]["resolution_scales"]]
        grid = degrader.generate_degradation_grid(test_images[0], resolutions)
        plot_degradation_grid(
            test_images[0],
            grid,
            save_path=os.path.join(args.output_dir, "plots", "degradation_grid.png"),
        )

    print(f"\nAll results saved to: {args.output_dir}")
    print("Experiment complete!")


if __name__ == "__main__":
    main()
