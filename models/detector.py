"""
YOLOv8-based license plate detection module.

Wraps Ultralytics YOLOv8 for plate detection with support for:
- Transfer learning from COCO pretrained weights
- Fine-tuning on OpenALPR/CCPD datasets
- Inference at multiple resolutions for degradation experiments
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
import cv2

from utils.device import resolve_device


class PlateDetector:
    """
    License plate detector using YOLOv8.

    This wraps the Ultralytics YOLO API for clean integration with
    the rest of the pipeline.
    """

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        confidence: float = 0.5,
        iou_threshold: float = 0.45,
        device: str = "auto",
    ):
        """
        Args:
            model_path: Path to YOLOv8 weights (or model name for auto-download)
            confidence: Minimum confidence threshold for detections
            iou_threshold: IoU threshold for NMS
            device: "auto", "cuda", "mps", or "cpu"
        """
        try:
            from ultralytics import YOLO
        except ImportError:
            raise ImportError("Install ultralytics: pip install ultralytics")

        self.device = resolve_device(device)
        self.confidence = confidence
        self.iou_threshold = iou_threshold

        # Load model
        self.model = YOLO(model_path)
        print(f"Loaded YOLOv8 model from {model_path} on {self.device}")

    def train(
        self,
        data_yaml: str,
        epochs: int = 50,
        img_size: int = 640,
        batch_size: int = 16,
        lr: float = 0.001,
        output_dir: str = "results/detection",
        resume: bool = False,
    ) -> Dict:
        """
        Fine-tune YOLOv8 on license plate dataset.

        Args:
            data_yaml: Path to YOLO-format data.yaml
            epochs: Number of training epochs
            img_size: Training image size
            batch_size: Training batch size
            lr: Initial learning rate
            output_dir: Directory for training outputs
            resume: Whether to resume from last checkpoint

        Returns:
            Dict with training results and metrics
        """
        results = self.model.train(
            data=data_yaml,
            epochs=epochs,
            imgsz=img_size,
            batch=batch_size,
            lr0=lr,
            device=self.device,
            project=output_dir,
            name="plate_detection",
            exist_ok=True,
            resume=resume,
            # Optimization
            optimizer="Adam",
            cos_lr=True,
            # Augmentation (moderate - plates have fixed orientation)
            hsv_h=0.015,
            hsv_s=0.5,
            hsv_v=0.3,
            degrees=5.0,       # Slight rotation only
            translate=0.1,
            scale=0.3,
            flipud=0.0,        # No vertical flip
            fliplr=0.0,        # No horizontal flip (text would be mirrored)
            mosaic=0.5,
            mixup=0.0,
        )

        return {
            "mAP50": float(results.results_dict.get("metrics/mAP50(B)", 0)),
            "mAP50_95": float(results.results_dict.get("metrics/mAP50-95(B)", 0)),
            "precision": float(results.results_dict.get("metrics/precision(B)", 0)),
            "recall": float(results.results_dict.get("metrics/recall(B)", 0)),
            "best_model": str(results.save_dir / "weights" / "best.pt"),
        }

    def detect(
        self,
        image: np.ndarray,
        img_size: int = 640,
    ) -> List[Dict]:
        """
        Detect license plates in a single image.

        Args:
            image: Input image (BGR or RGB numpy array)
            img_size: Inference image size

        Returns:
            List of detection dicts with keys:
                bbox: [x1, y1, x2, y2] in pixel coordinates
                confidence: Detection confidence
                class_id: Class index
        """
        results = self.model.predict(
            image,
            imgsz=img_size,
            conf=self.confidence,
            iou=self.iou_threshold,
            device=self.device,
            verbose=False,
        )

        detections = []
        for result in results:
            boxes = result.boxes
            if boxes is not None:
                for i in range(len(boxes)):
                    det = {
                        "bbox": boxes.xyxy[i].cpu().numpy().tolist(),
                        "confidence": float(boxes.conf[i].cpu()),
                        "class_id": int(boxes.cls[i].cpu()),
                    }
                    detections.append(det)

        return detections

    def detect_batch(
        self,
        images: List[np.ndarray],
        img_size: int = 640,
    ) -> List[List[Dict]]:
        """Detect plates in a batch of images."""
        results = self.model.predict(
            images,
            imgsz=img_size,
            conf=self.confidence,
            iou=self.iou_threshold,
            device=self.device,
            verbose=False,
        )

        all_detections = []
        for result in results:
            detections = []
            boxes = result.boxes
            if boxes is not None:
                for i in range(len(boxes)):
                    det = {
                        "bbox": boxes.xyxy[i].cpu().numpy().tolist(),
                        "confidence": float(boxes.conf[i].cpu()),
                        "class_id": int(boxes.cls[i].cpu()),
                    }
                    detections.append(det)
            all_detections.append(detections)

        return all_detections

    def evaluate(
        self,
        data_yaml: str,
        img_size: int = 640,
        split: str = "val",
    ) -> Dict:
        """
        Evaluate detector on validation/test set.

        Returns dict with mAP, precision, recall metrics.
        """
        metrics = self.model.val(
            data=data_yaml,
            imgsz=img_size,
            split=split,
            device=self.device,
            verbose=False,
        )

        return {
            "mAP50": float(metrics.results_dict.get("metrics/mAP50(B)", 0)),
            "mAP50_95": float(metrics.results_dict.get("metrics/mAP50-95(B)", 0)),
            "precision": float(metrics.results_dict.get("metrics/precision(B)", 0)),
            "recall": float(metrics.results_dict.get("metrics/recall(B)", 0)),
        }

    def crop_plates(
        self,
        image: np.ndarray,
        padding: float = 0.1,
    ) -> List[np.ndarray]:
        """
        Detect plates and return cropped plate regions.

        Useful as preprocessing for the OCR / character classification step.
        """
        detections = self.detect(image)
        h, w = image.shape[:2]
        crops = []

        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            # Add padding
            pad_x = int((x2 - x1) * padding)
            pad_y = int((y2 - y1) * padding)
            x1 = max(0, int(x1) - pad_x)
            y1 = max(0, int(y1) - pad_y)
            x2 = min(w, int(x2) + pad_x)
            y2 = min(h, int(y2) + pad_y)

            crop = image[y1:y2, x1:x2]
            if crop.size > 0:
                crops.append(crop)

        return crops

    def load_weights(self, weights_path: str):
        """Load fine-tuned weights."""
        from ultralytics import YOLO
        self.model = YOLO(weights_path)
        print(f"Loaded weights from {weights_path}")


def create_data_yaml(
    train_dir: str,
    val_dir: str,
    test_dir: Optional[str] = None,
    num_classes: int = 1,
    class_names: List[str] = None,
    output_path: str = "data/data.yaml",
) -> str:
    """
    Create a YOLO-format data.yaml configuration file.

    Args:
        train_dir: Path to training images
        val_dir: Path to validation images
        test_dir: Optional path to test images
        num_classes: Number of object classes
        class_names: List of class names
        output_path: Where to save the YAML file

    Returns:
        Path to created data.yaml
    """
    import yaml

    if class_names is None:
        class_names = ["license_plate"]

    data = {
        "train": os.path.abspath(train_dir),
        "val": os.path.abspath(val_dir),
        "nc": num_classes,
        "names": class_names,
    }
    if test_dir:
        data["test"] = os.path.abspath(test_dir)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False)

    print(f"Created data.yaml at {output_path}")
    return output_path
