"""
Metrics tracking and evaluation utilities.

Tracks detection mAP, OCR accuracy, character error rate, PSNR, and SSIM
across different resolution levels and experimental conditions.
"""

import numpy as np
import json
import os
from typing import Dict, List, Optional
from collections import defaultdict


class MetricsTracker:
    """
    Tracks and stores metrics across resolution degradation experiments.

    Organizes results by:
    - Resolution level
    - Degradation type
    - Condition (baseline / upscale_only / autoencoder)
    """

    def __init__(self, output_dir: str = "results"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.results = defaultdict(lambda: defaultdict(dict))
        # Structure: results[resolution][condition][metric_name] = value

    def log(
        self,
        resolution: int,
        condition: str,
        metrics: Dict[str, float],
        degradation_type: str = "bicubic_downsample",
    ):
        """
        Log metrics for a specific experimental configuration.

        Args:
            resolution: Image resolution (e.g., 640, 320, 160)
            condition: "baseline", "upscale_only", or "autoencoder"
            metrics: Dict of metric_name -> value
            degradation_type: Type of degradation applied
        """
        key = f"{degradation_type}_{resolution}"
        self.results[key][condition] = metrics.copy()

    def get_resolution_curve(
        self,
        metric_name: str,
        condition: str,
        degradation_type: str = "bicubic_downsample",
    ) -> tuple:
        """
        Get metric values across all tested resolutions for a given condition.

        Returns:
            (resolutions, values) tuple for plotting
        """
        resolutions = []
        values = []

        for key in sorted(self.results.keys()):
            if key.startswith(degradation_type):
                res = int(key.split("_")[-1])
                if condition in self.results[key]:
                    if metric_name in self.results[key][condition]:
                        resolutions.append(res)
                        values.append(self.results[key][condition][metric_name])

        return resolutions, values

    def get_improvement(
        self,
        resolution: int,
        metric_name: str,
        degradation_type: str = "bicubic_downsample",
    ) -> Optional[Dict[str, float]]:
        """
        Calculate autoencoder improvement over baseline at a given resolution.

        Returns dict with absolute and relative improvement.
        """
        key = f"{degradation_type}_{resolution}"
        if key not in self.results:
            return None

        baseline = self.results[key].get("baseline", {}).get(metric_name)
        ae = self.results[key].get("autoencoder", {}).get(metric_name)

        if baseline is None or ae is None:
            return None

        return {
            "baseline": baseline,
            "autoencoder": ae,
            "absolute_improvement": ae - baseline,
            "relative_improvement": (ae - baseline) / (baseline + 1e-8) * 100,
        }

    def summary(self) -> str:
        """Generate a text summary of all results."""
        lines = ["=" * 70, "RESOLUTION DEGRADATION EXPERIMENT RESULTS", "=" * 70, ""]

        for key in sorted(self.results.keys()):
            lines.append(f"\n--- {key} ---")
            for condition in sorted(self.results[key].keys()):
                lines.append(f"  {condition}:")
                for metric, value in sorted(self.results[key][condition].items()):
                    lines.append(f"    {metric}: {value:.4f}")

        return "\n".join(lines)

    def save(self, filename: str = "experiment_results.json"):
        """Save results to JSON."""
        path = os.path.join(self.output_dir, filename)
        # Convert defaultdict to regular dict for JSON serialization
        serializable = {k: dict(v) for k, v in self.results.items()}
        with open(path, "w") as f:
            json.dump(serializable, f, indent=2)
        print(f"Results saved to {path}")

    def load(self, filename: str = "experiment_results.json"):
        """Load results from JSON."""
        path = os.path.join(self.output_dir, filename)
        with open(path, "r") as f:
            data = json.load(f)
        self.results = defaultdict(lambda: defaultdict(dict), data)
        print(f"Results loaded from {path}")


def compute_detection_metrics(
    predictions: List[Dict],
    ground_truth: List[Dict],
    iou_threshold: float = 0.5,
) -> Dict[str, float]:
    """
    Compute detection metrics (precision, recall, mAP) given predictions
    and ground truth bounding boxes.

    Args:
        predictions: List of dicts with 'bbox' and 'confidence'
        ground_truth: List of dicts with 'bbox'
        iou_threshold: IoU threshold for matching

    Returns:
        Dict with precision, recall, mAP
    """
    if not ground_truth:
        return {"precision": 1.0 if not predictions else 0.0, "recall": 1.0, "mAP": 1.0}
    if not predictions:
        return {"precision": 0.0, "recall": 0.0, "mAP": 0.0}

    # Sort predictions by confidence (descending)
    preds = sorted(predictions, key=lambda x: x["confidence"], reverse=True)
    gt_matched = [False] * len(ground_truth)

    tp = 0
    fp = 0

    for pred in preds:
        best_iou = 0
        best_gt_idx = -1

        for gt_idx, gt in enumerate(ground_truth):
            if gt_matched[gt_idx]:
                continue
            iou = _compute_iou(pred["bbox"], gt["bbox"])
            if iou > best_iou:
                best_iou = iou
                best_gt_idx = gt_idx

        if best_iou >= iou_threshold and best_gt_idx >= 0:
            tp += 1
            gt_matched[best_gt_idx] = True
        else:
            fp += 1

    fn = sum(1 for m in gt_matched if not m)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "mAP": precision * recall,  # Simplified; use YOLO's built-in for full mAP
    }


def compute_ocr_consistency(
    degraded_texts: List[str],
    reference_texts: List[str],
) -> Dict[str, float]:
    """
    Compute OCR consistency between degraded-image readings and clean-image
    reference readings.

    IMPORTANT: This is NOT accuracy. The reference readings are produced by
    running OCR on clean full-resolution crops; they may themselves contain
    OCR errors. These metrics measure how much the OCR output *changes* as
    image quality degrades — a consistency of 1.0 means degradation did not
    alter the OCR output at all, not that the output is correct.

    Use this only with datasets that lack verified text annotations.
    For true accuracy evaluation, verified ground-truth plate text is required.

    Returns:
        Dict with:
          exact_consistency  — fraction of plates where degraded OCR exactly
                               matches the clean reference reading
          char_consistency   — character-level match rate vs. clean reference
          char_change_rate   — fraction of characters that changed (≈ CER vs ref)
    """
    if not reference_texts:
        return {"exact_consistency": 1.0, "char_consistency": 1.0, "char_change_rate": 0.0}

    exact_matches = 0
    total_chars = 0
    matching_chars = 0

    for deg, ref in zip(degraded_texts, reference_texts):
        if deg == ref:
            exact_matches += 1
        for d_char, r_char in zip(deg, ref):
            total_chars += 1
            if d_char == r_char:
                matching_chars += 1
        total_chars += abs(len(deg) - len(ref))

    n = len(reference_texts)
    char_consistency = matching_chars / total_chars if total_chars > 0 else 0.0

    return {
        "exact_consistency": exact_matches / n,
        "char_consistency": char_consistency,
        "char_change_rate": 1.0 - char_consistency,
    }


# Keep old name as alias so existing calls don't break
def compute_ocr_accuracy(
    predicted_texts: List[str],
    reference_texts: List[str],
) -> Dict[str, float]:
    """Deprecated alias for compute_ocr_consistency. Use that instead."""
    result = compute_ocr_consistency(predicted_texts, reference_texts)
    return {
        "exact_match": result["exact_consistency"],
        "char_accuracy": result["char_consistency"],
        "cer": result["char_change_rate"],
    }


def _compute_iou(box1: List[float], box2: List[float]) -> float:
    """Compute IoU between two bounding boxes [x1, y1, x2, y2]."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    inter_area = max(0, x2 - x1) * max(0, y2 - y1)

    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])

    union_area = area1 + area2 - inter_area

    return inter_area / union_area if union_area > 0 else 0.0
