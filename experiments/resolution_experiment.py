"""
Resolution Degradation Experiment

Core experiment: systematically degrade image resolution and measure
the impact on plate detection (mAP) and character recognition (OCR accuracy),
then test whether the autoencoder can recover lost performance.

Experimental conditions at each resolution:
1. baseline:      Feed degraded image directly to detector/OCR
2. upscale_only:  Bicubic upscale to original resolution, then detect/OCR
3. autoencoder:   Restore with autoencoder, then detect/OCR

This produces the key result figure: accuracy vs resolution curves
for each condition, showing the autoencoder's value proposition.
"""

import os
import cv2
import json
import numpy as np
import torch
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from tqdm import tqdm

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.degradation import ImageDegrader, compute_image_quality_metrics
from utils.device import resolve_device
from utils.metrics import MetricsTracker, compute_detection_metrics, compute_ocr_accuracy
from utils.visualization import (
    plot_resolution_comparison,
    plot_reconstruction_samples,
    plot_degradation_grid,
)


class ResolutionExperiment:
    """
    Runs the full resolution degradation ablation study.

    Flow for each (resolution, degradation_type) pair:
    1. Degrade test images to target resolution
    2. Run detection + OCR under each condition
    3. Compute and log metrics
    4. Generate comparison plots
    """

    def __init__(
        self,
        detector,
        classifier,
        autoencoder,
        ocr_engine=None,
        config: dict = None,
        device: str = "cuda",
    ):
        """
        Args:
            detector: PlateDetector instance
            classifier: CharacterClassifier instance (or None to use OCR engine)
            autoencoder: Trained autoencoder model (ConvAutoencoder or UNetAutoencoder)
            ocr_engine: Optional EasyOCR/Tesseract reader
            config: Experiment configuration
            device: Compute device
        """
        self.detector = detector
        self.classifier = classifier
        self.autoencoder = autoencoder
        self.ocr_engine = ocr_engine
        self.config = config or {}
        self.device = device

        self.degrader = ImageDegrader(
            base_resolution=config.get("detection", {}).get("img_size", 640)
        )
        self.metrics = MetricsTracker(
            output_dir=config.get("project", {}).get("output_dir", "results")
        )

        # Default experiment parameters
        exp_config = config.get("experiment", {})
        self.base_resolution = config.get("detection", {}).get("img_size", 640)
        self.resolution_scales = exp_config.get(
            "resolution_scales", [1.0, 0.75, 0.5, 0.375, 0.25, 0.125]
        )
        self.degradation_types = exp_config.get(
            "degradation_types", ["bicubic_downsample"]
        )

    def _get_resolutions(self) -> List[int]:
        """Convert scale factors to pixel resolutions."""
        return [int(self.base_resolution * s) for s in self.resolution_scales]

    def _apply_autoencoder(self, image: np.ndarray) -> np.ndarray:
        """
        Pass image through autoencoder for restoration.

        Handles the tensor conversion, inference, and back-conversion.
        """
        if self.autoencoder is None:
            return image

        self.autoencoder.eval()
        with torch.no_grad():
            # Preprocess: normalize to [-1, 1]
            img = image.astype(np.float32) / 255.0
            img = (img - 0.5) / 0.5
            tensor = torch.from_numpy(img).permute(2, 0, 1).unsqueeze(0)
            tensor = tensor.to(self.device)

            # Inference
            output = self.autoencoder(tensor)
            if isinstance(output, tuple):
                output = output[0]

            # Post-process: denormalize
            result = output.squeeze(0).permute(1, 2, 0).cpu().numpy()
            result = (result * 0.5 + 0.5) * 255.0
            result = np.clip(result, 0, 255).astype(np.uint8)

        return result

    def _apply_autoencoder_to_full_image(self, image: np.ndarray) -> np.ndarray:
        """
        Apply autoencoder restoration to the full image by processing it
        in overlapping tiles at the autoencoder's native resolution.

        This allows the autoencoder to improve the full image before detection,
        not just plate crops before OCR.
        """
        if self.autoencoder is None:
            return image

        ae_h = self.config.get("autoencoder", {}).get("input_size", 128)
        ae_w = self.config.get("autoencoder", {}).get("input_width", 256)
        h, w = image.shape[:2]

        # If image is small enough, process directly
        if h <= ae_h * 2 and w <= ae_w * 2:
            resized = cv2.resize(image, (ae_w, ae_h))
            restored = self._apply_autoencoder(resized)
            return cv2.resize(restored, (w, h))

        # For larger images, process in overlapping tiles
        # Use stride of 75% of tile size for overlap
        stride_h = max(ae_h // 2, 1)
        stride_w = max(ae_w // 2, 1)

        output = np.zeros_like(image, dtype=np.float32)
        weight_map = np.zeros((h, w, 1), dtype=np.float32)

        for y in range(0, h - ae_h + 1, stride_h):
            for x in range(0, w - ae_w + 1, stride_w):
                tile = image[y:y+ae_h, x:x+ae_w]
                restored_tile = self._apply_autoencoder(tile)
                output[y:y+ae_h, x:x+ae_w] += restored_tile.astype(np.float32)
                weight_map[y:y+ae_h, x:x+ae_w] += 1.0

        # Handle right and bottom edges
        if (h - ae_h) % stride_h != 0:
            y = h - ae_h
            for x in range(0, w - ae_w + 1, stride_w):
                tile = image[y:y+ae_h, x:x+ae_w]
                restored_tile = self._apply_autoencoder(tile)
                output[y:y+ae_h, x:x+ae_w] += restored_tile.astype(np.float32)
                weight_map[y:y+ae_h, x:x+ae_w] += 1.0

        if (w - ae_w) % stride_w != 0:
            x = w - ae_w
            for y in range(0, h - ae_h + 1, stride_h):
                tile = image[y:y+ae_h, x:x+ae_w]
                restored_tile = self._apply_autoencoder(tile)
                output[y:y+ae_h, x:x+ae_w] += restored_tile.astype(np.float32)
                weight_map[y:y+ae_h, x:x+ae_w] += 1.0

        # Bottom-right corner
        if (h - ae_h) % stride_h != 0 and (w - ae_w) % stride_w != 0:
            y, x = h - ae_h, w - ae_w
            tile = image[y:y+ae_h, x:x+ae_w]
            restored_tile = self._apply_autoencoder(tile)
            output[y:y+ae_h, x:x+ae_w] += restored_tile.astype(np.float32)
            weight_map[y:y+ae_h, x:x+ae_w] += 1.0

        # Average overlapping regions
        weight_map = np.maximum(weight_map, 1.0)
        output = (output / weight_map).clip(0, 255).astype(np.uint8)

        # Fill any unprocessed borders with original
        mask = (weight_map.squeeze() == 0)
        if mask.any():
            output[mask] = image[mask]

        return output

    def _run_ocr(self, plate_crop: np.ndarray) -> str:
        """Run OCR on a plate crop image with preprocessing pipeline."""
        if self.ocr_engine is not None:
            try:
                from utils.ocr_utils import run_ocr_with_preprocessing, PLATE_CHARS_ALPHANUMERIC
                text, confidence = run_ocr_with_preprocessing(
                    plate_crop,
                    self.ocr_engine,
                    allowlist=PLATE_CHARS_ALPHANUMERIC,
                    confidence_threshold=0.2,
                    use_ensemble=True,
                )
                return text
            except ImportError:
                # Fallback to basic OCR
                results = self.ocr_engine.readtext(plate_crop)
                text = "".join([r[1] for r in results]).upper()
                return text
        else:
            return ""

    def run_single_condition(
        self,
        images: List[np.ndarray],
        gt_boxes: List[List[Dict]],
        gt_texts: List[str],
        resolution: int,
        condition: str,
        degradation_type: str = "bicubic_downsample",
    ) -> Dict[str, float]:
        """
        Run experiment for a single condition at a given resolution.

        Args:
            images: List of test images (full resolution)
            gt_boxes: Ground truth bounding boxes for each image
            gt_texts: Ground truth plate texts
            resolution: Target degraded resolution
            condition: "baseline", "upscale_only", or "autoencoder"
            degradation_type: Type of degradation to apply

        Conditions explained:
            baseline:    Degrade image (keep at low resolution), run detector
            upscale_only: Degrade then bicubic-upscale back to original size, run detector
            autoencoder:  Degrade, bicubic-upscale, then restore plate crops
                          with autoencoder before OCR. Detection runs on the
                          upscaled image (same as upscale_only) but OCR benefits
                          from autoencoder restoration of each plate crop.
        """
        all_det_metrics = []
        all_ocr_results = {"degraded": [], "reference": []}
        all_quality = {"psnr": [], "ssim": []}

        ae_h = self.config.get("autoencoder", {}).get("input_size", 128)
        ae_w = self.config.get("autoencoder", {}).get("input_width", 256)

        for i, (image, gt_box, gt_text) in enumerate(
            zip(images, gt_boxes, gt_texts)
        ):
            h, w = image.shape[:2]

            # Step 1: Degrade the image
            if resolution < self.base_resolution:
                degradation_fn = self.degrader.get_degradation_fn(
                    degradation_type, resolution
                )

                if condition == "baseline":
                    # Downsample WITHOUT upscaling back — detector sees
                    # the small image (or the blurred/compressed version
                    # at original size for non-resolution degradations)
                    if degradation_type == "bicubic_downsample":
                        processed = self.degrader.bicubic_downsample(
                            image.copy(), resolution, upscale_back=False
                        )
                    else:
                        # For blur/jpeg/combined, apply the degradation
                        processed = degradation_fn(image.copy())
                elif condition == "upscale_only":
                    # Degrade then upscale back to original size with bicubic
                    if degradation_type == "bicubic_downsample":
                        processed = self.degrader.bicubic_downsample(
                            image.copy(), resolution, upscale_back=True
                        )
                    else:
                        processed = degradation_fn(image.copy())
                elif condition == "autoencoder":
                    # Degrade, upscale, then apply autoencoder to full image
                    # before detection — this is the key difference from upscale_only
                    if degradation_type == "bicubic_downsample":
                        processed = self.degrader.bicubic_downsample(
                            image.copy(), resolution, upscale_back=True
                        )
                    else:
                        processed = degradation_fn(image.copy())
                    # Apply autoencoder restoration to the full image
                    processed = self._apply_autoencoder_to_full_image(processed)
                else:
                    raise ValueError(f"Unknown condition: {condition}")

                # Compute quality vs. original (resize processed to match if needed)
                compare_img = processed
                if compare_img.shape[:2] != image.shape[:2]:
                    compare_img = cv2.resize(compare_img, (w, h))
                quality = compute_image_quality_metrics(image, compare_img)
            else:
                processed = image.copy()
                quality = {"psnr": float("inf"), "ssim": 1.0}

            all_quality["psnr"].append(quality["psnr"])
            all_quality["ssim"].append(quality["ssim"])

            # Step 2: Detect plates
            detections = self.detector.detect(processed)

            # Step 3: Compute detection metrics
            # Scale GT boxes if image was not upscaled back
            if processed.shape[:2] != image.shape[:2]:
                scale_x = processed.shape[1] / w
                scale_y = processed.shape[0] / h
                scaled_gt = []
                for box in gt_box:
                    scaled_gt.append({
                        "bbox": [
                            box["bbox"][0] * scale_x,
                            box["bbox"][1] * scale_y,
                            box["bbox"][2] * scale_x,
                            box["bbox"][3] * scale_y,
                        ]
                    })
            else:
                scaled_gt = gt_box

            det_metric = compute_detection_metrics(detections, scaled_gt)
            all_det_metrics.append(det_metric)

            # Step 4: OCR on detected plate crops
            if detections and gt_text:
                crops = self.detector.crop_plates(processed)

                if condition == "autoencoder" and crops:
                    # Restore each crop with autoencoder before OCR
                    restored_crops = []
                    for crop in crops:
                        resized = cv2.resize(crop, (ae_w, ae_h))
                        restored = self._apply_autoencoder(resized)
                        restored_crops.append(restored)
                    crops = restored_crops

                for crop in crops:
                    ocr_text = self._run_ocr(crop)
                    all_ocr_results["degraded"].append(ocr_text)
                    all_ocr_results["reference"].append(gt_text)

        # Aggregate metrics
        avg_metrics = {
            "detection_accuracy": np.mean(
                [m.get("precision", 0) for m in all_det_metrics]
            ),
            "mAP": np.mean([m.get("mAP", 0) for m in all_det_metrics]),
            "precision": np.mean([m.get("precision", 0) for m in all_det_metrics]),
            "recall": np.mean([m.get("recall", 0) for m in all_det_metrics]),
            "psnr": np.mean(all_quality["psnr"]),
            "ssim": np.mean(all_quality["ssim"]),
        }

        # OCR consistency metrics (not accuracy — no verified GT text in this dataset)
        if all_ocr_results["degraded"]:
            consistency = compute_ocr_accuracy(
                all_ocr_results["degraded"],
                all_ocr_results["reference"],
            )
            avg_metrics.update({
                "ocr_consistency": consistency["exact_match"],    # vs. clean reference
                "char_consistency": consistency["char_accuracy"], # vs. clean reference
                "char_change_rate": consistency["cer"],           # chars that changed
            })

        return avg_metrics

    def run_full_experiment(
        self,
        test_images: List[np.ndarray],
        gt_boxes: List[List[Dict]],
        gt_texts: List[str],
        save_dir: str = "results/experiment",
    ) -> MetricsTracker:
        """
        Run the complete resolution degradation experiment.

        Tests all combinations of:
        - Resolution levels
        - Degradation types
        - Conditions (baseline / upscale / autoencoder)

        Returns populated MetricsTracker with all results.
        """
        os.makedirs(save_dir, exist_ok=True)
        resolutions = self._get_resolutions()
        conditions = ["baseline", "upscale_only", "autoencoder"]

        total = len(self.degradation_types) * len(resolutions) * len(conditions)
        pbar = tqdm(total=total, desc="Running experiments")

        for deg_type in self.degradation_types:
            for resolution in resolutions:
                for condition in conditions:
                    print(
                        f"\n--- {deg_type} | {resolution}px | {condition} ---"
                    )

                    metrics = self.run_single_condition(
                        test_images,
                        gt_boxes,
                        gt_texts,
                        resolution,
                        condition,
                        deg_type,
                    )

                    self.metrics.log(
                        resolution=resolution,
                        condition=condition,
                        metrics=metrics,
                        degradation_type=deg_type,
                    )

                    pbar.update(1)

        pbar.close()

        # Save results — set output_dir to save_dir so save() doesn't double-prefix
        self.metrics.output_dir = save_dir
        self.metrics.save("experiment_results.json")

        # Generate plots
        for metric in ["mAP", "detection_accuracy", "ocr_accuracy"]:
            for deg_type in self.degradation_types:
                plot_resolution_comparison(
                    self.metrics,
                    metric_name=metric,
                    degradation_type=deg_type,
                    save_path=os.path.join(
                        save_dir, "plots", f"{metric}_{deg_type}.png"
                    ),
                )

        # Print summary
        print(self.metrics.summary())

        return self.metrics


def run_quick_experiment(
    test_dir: str,
    detector_weights: str,
    autoencoder_weights: str,
    config_path: str = "configs/config.yaml",
):
    """
    Quick experiment runner for testing the pipeline.

    Loads models, selects a subset of test images, and runs the experiment.
    """
    from utils.data_loader import load_config
    from models.detector import PlateDetector
    from models.autoencoder import UNetAutoencoder

    config = load_config(config_path)
    device = resolve_device()

    # Load models
    detector = PlateDetector(
        model_path=detector_weights,
        confidence=config["detection"]["confidence_threshold"],
        device=device,
    )

    autoencoder = UNetAutoencoder(in_channels=3, base_features=32, depth=4)
    autoencoder.load_state_dict(torch.load(autoencoder_weights, map_location=device))
    autoencoder = autoencoder.to(device)

    # Load test images
    test_images = []
    gt_boxes = []
    gt_texts = []

    img_dir = Path(test_dir) / "images"
    label_dir = Path(test_dir) / "labels"

    for img_path in sorted(
        p for p in img_dir.glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png")
    )[:50]:  # First 50 for quick test
        image = cv2.imread(str(img_path))
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        test_images.append(image)

        # Load GT boxes
        label_path = label_dir / (img_path.stem + ".txt")
        boxes = []
        if label_path.exists():
            with open(label_path) as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        h, w = image.shape[:2]
                        x_c, y_c, bw, bh = map(float, parts[1:5])
                        boxes.append({
                            "bbox": [
                                (x_c - bw / 2) * w,
                                (y_c - bh / 2) * h,
                                (x_c + bw / 2) * w,
                                (y_c + bh / 2) * h,
                            ]
                        })
        gt_boxes.append(boxes)
        gt_texts.append("")  # No text GT in basic YOLO format

    # Run experiment
    experiment = ResolutionExperiment(
        detector=detector,
        classifier=None,
        autoencoder=autoencoder,
        config=config,
        device=device,
    )

    results = experiment.run_full_experiment(
        test_images, gt_boxes, gt_texts, save_dir="results/experiment"
    )

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run resolution degradation experiment")
    parser.add_argument("--test-dir", required=True, help="Test data directory")
    parser.add_argument("--detector-weights", required=True, help="Detector weights path")
    parser.add_argument("--autoencoder-weights", required=True, help="Autoencoder weights path")
    parser.add_argument("--config", default="configs/config.yaml", help="Config file")
    args = parser.parse_args()

    run_quick_experiment(
        args.test_dir,
        args.detector_weights,
        args.autoencoder_weights,
        args.config,
    )
