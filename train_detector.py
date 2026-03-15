"""
Train YOLOv8 plate detector on the Kaggle ALPR dataset.

Usage:
    python train_detector.py --data-dir /absolute/path/to/dataset
    python train_detector.py --data-dir ~/Downloads/alpr-dataset --epochs 50

The dataset directory must contain train/, valid/, and test/ subfolders,
each with images/ and labels/ subdirectories (standard YOLO format).

This script:
1. Builds an absolute-path data.yaml that YOLOv8 can always find
2. Fine-tunes YOLOv8n with transfer learning from COCO
3. Saves weights to results/detection/plate_detection/weights/best.pt
"""

import argparse
import os
import json
import torch

from utils.data_loader import load_config
from utils.device import resolve_device
from models.detector import PlateDetector, create_data_yaml


def main():
    parser = argparse.ArgumentParser(description="Train plate detector")
    parser.add_argument(
        "--data-dir",
        required=True,
        help="Absolute path to the dataset root (folder containing train/, valid/, test/)",
    )
    parser.add_argument(
        "--config", default="configs/config.yaml", help="Config file path"
    )
    parser.add_argument("--resume", action="store_true", help="Resume training")
    parser.add_argument("--epochs", type=int, default=None, help="Override epochs")
    parser.add_argument("--batch-size", type=int, default=None, help="Override batch size")
    parser.add_argument(
        "--device",
        default=None,
        help="Device to train on: cuda, mps, or cpu (auto-detected if not set)",
    )
    args = parser.parse_args()

    # Resolve dataset root to an absolute path immediately
    data_root = os.path.abspath(os.path.expanduser(args.data_dir))
    if not os.path.isdir(data_root):
        raise FileNotFoundError(f"Dataset directory not found: {data_root}")

    config = load_config(args.config)

    epochs = args.epochs or config["detection"]["epochs"]
    batch_size = args.batch_size or config["detection"]["batch_size"]

    # For YOLO multi-GPU, pass "0,1" instead of "cuda"
    # Ultralytics handles DDP (DistributedDataParallel) internally
    if args.device and args.device not in ("auto", "cuda"):
        device = args.device  # explicit: mps, cpu, or "0,1"
    elif torch.cuda.device_count() > 1:
        device = ",".join(str(i) for i in range(torch.cuda.device_count()))
        batch_size = batch_size * torch.cuda.device_count()
    else:
        device = resolve_device(args.device)

    num_gpus = torch.cuda.device_count() if "cuda" in str(device) or "," in str(device) else 1
    print(f"Dataset root : {data_root}")
    print(f"Device       : {device}  ({num_gpus} GPU(s))")
    print(f"Epochs       : {epochs}  |  Batch size: {batch_size}")

    # Build absolute paths for each split.
    # The Kaggle ALPR dataset uses "valid/" (not "val/")
    train_images = os.path.join(data_root, "train", "images")
    val_images   = os.path.join(data_root, "valid", "images")
    test_images  = os.path.join(data_root, "test",  "images")

    for p in [train_images, val_images]:
        if not os.path.isdir(p):
            raise FileNotFoundError(
                f"Expected images folder not found: {p}\n"
                "Make sure --data-dir points to the folder that contains train/, valid/, test/"
            )

    # Save data.yaml next to the project so the path is always absolute
    project_dir = os.path.dirname(os.path.abspath(__file__))
    yaml_output  = os.path.join(project_dir, "data", "data.yaml")

    data_yaml = create_data_yaml(
        train_dir=train_images,
        val_dir=val_images,
        test_dir=test_images if os.path.isdir(test_images) else None,
        num_classes=1,
        class_names=["license_plate"],
        output_path=yaml_output,
    )

    # Initialize detector with pretrained YOLOv8
    detector = PlateDetector(
        model_path=config["detection"]["model"],
        confidence=config["detection"]["confidence_threshold"],
        iou_threshold=config["detection"]["iou_threshold"],
        device=device,
    )

    # Use absolute path for output dir so results land in the project folder
    output_dir = os.path.join(project_dir, "results", "detection")

    # Train
    print("\n" + "=" * 60)
    print("TRAINING PLATE DETECTOR")
    print("=" * 60)

    results = detector.train(
        data_yaml=os.path.abspath(yaml_output),
        epochs=epochs,
        img_size=config["detection"]["img_size"],
        batch_size=batch_size,
        lr=config["detection"]["learning_rate"],
        output_dir=output_dir,
        resume=args.resume,
    )

    # Print results
    print("\n" + "=" * 60)
    print("TRAINING RESULTS")
    print("=" * 60)
    for k, v in results.items():
        print(f"  {k}: {v}")

    # Save results
    os.makedirs("results", exist_ok=True)
    with open("results/detection_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nBest model saved to: {results['best_model']}")
    print("Training complete!")


if __name__ == "__main__":
    main()
