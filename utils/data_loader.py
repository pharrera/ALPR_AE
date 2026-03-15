"""
Data loading utilities for OpenALPR license plate recognition project.

Supports:
- OpenALPR dataset download via Roboflow
- YOLO-format detection datasets
- Character-level classification datasets
- Resolution degradation pipelines
"""

import os
import cv2
import yaml
import numpy as np
from pathlib import Path
from typing import Tuple, List, Optional, Dict

import torch
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from PIL import Image

from utils.device import resolve_device, use_pinned_memory

# Character mapping: 0-9 + A-Z = 36 classes
CHAR_CLASSES = list("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")
CHAR_TO_IDX = {c: i for i, c in enumerate(CHAR_CLASSES)}
IDX_TO_CHAR = {i: c for i, c in enumerate(CHAR_CLASSES)}


def load_config(config_path: str = "configs/config.yaml") -> dict:
    """Load project configuration from YAML file."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def download_dataset(config: dict) -> str:
    """
    Download OpenALPR dataset from Roboflow.

    Returns the path to the downloaded dataset directory.
    """
    try:
        from roboflow import Roboflow
    except ImportError:
        raise ImportError("Install roboflow: pip install roboflow")

    api_key = os.environ.get("ROBOFLOW_API_KEY", config["data"]["roboflow_api_key"])
    if api_key == "YOUR_API_KEY":
        print(
            "WARNING: Set ROBOFLOW_API_KEY environment variable or update config.yaml"
        )
        print("You can also manually download datasets and place them in data/openalpr/")
        return config["data"]["root_dir"]

    rf = Roboflow(api_key=api_key)
    project = rf.workspace(config["data"]["roboflow_workspace"]).project(
        config["data"]["roboflow_project"]
    )
    dataset = project.version(config["data"]["roboflow_version"]).download("yolov8")

    print(f"Dataset downloaded to: {dataset.location}")
    return dataset.location


class OpenALPRDataset(Dataset):
    """
    Dataset for license plate images with YOLO-format annotations.

    Loads images and their bounding box annotations for plate detection.
    Supports on-the-fly resolution degradation for experiments.
    """

    def __init__(
        self,
        root_dir: str,
        img_size: int = 640,
        transform=None,
        target_resolution: Optional[int] = None,
        degradation_fn=None,
    ):
        """
        Args:
            root_dir: Directory containing 'images/' and 'labels/' subdirs
            img_size: Target image size for the model
            transform: Optional torchvision transforms
            target_resolution: If set, degrade images to this resolution
            degradation_fn: Custom degradation function (from ImageDegrader)
        """
        self.root_dir = Path(root_dir)
        self.img_size = img_size
        self.transform = transform
        self.target_resolution = target_resolution
        self.degradation_fn = degradation_fn

        # Find all images
        self.img_dir = self.root_dir / "images"
        self.label_dir = self.root_dir / "labels"

        if not self.img_dir.exists():
            # Some datasets put images directly in the split folder
            self.img_dir = self.root_dir
            self.label_dir = self.root_dir

        self.image_paths = sorted(
            [
                p
                for p in self.img_dir.glob("*")
                if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp")
            ]
        )

        print(f"Found {len(self.image_paths)} images in {root_dir}")

    def __len__(self) -> int:
        return len(self.image_paths)

    def __getitem__(self, idx: int) -> Dict:
        # Load image
        img_path = self.image_paths[idx]
        image = cv2.imread(str(img_path))
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        original_h, original_w = image.shape[:2]

        # Load YOLO-format labels: class x_center y_center width height (normalized)
        label_path = self.label_dir / (img_path.stem + ".txt")
        boxes = []
        if label_path.exists():
            with open(label_path, "r") as f:
                for line in f.readlines():
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        cls_id = int(parts[0])
                        x_c, y_c, w, h = map(float, parts[1:5])
                        boxes.append([cls_id, x_c, y_c, w, h])

        boxes = np.array(boxes) if boxes else np.zeros((0, 5))

        # Apply resolution degradation if specified
        if self.target_resolution and self.target_resolution < self.img_size:
            if self.degradation_fn:
                image = self.degradation_fn(image, self.target_resolution)
            else:
                # Default: bicubic downsample then upsample
                image = cv2.resize(
                    image,
                    (self.target_resolution, self.target_resolution),
                    interpolation=cv2.INTER_AREA,
                )
                image = cv2.resize(
                    image,
                    (self.img_size, self.img_size),
                    interpolation=cv2.INTER_CUBIC,
                )
        else:
            image = cv2.resize(
                image, (self.img_size, self.img_size), interpolation=cv2.INTER_LINEAR
            )

        # Apply transforms
        if self.transform:
            image = self.transform(image)
        else:
            image = transforms.ToTensor()(image)

        return {
            "image": image,
            "boxes": torch.tensor(boxes, dtype=torch.float32),
            "img_path": str(img_path),
            "original_size": (original_h, original_w),
        }


class CharacterDataset(Dataset):
    """
    Dataset for individual character classification.

    Expects directory structure:
        root/
            0/
                img001.png
                img002.png
            1/
            ...
            A/
            B/
            ...
            Z/
    """

    def __init__(
        self,
        root_dir: str,
        img_size: int = 64,
        transform=None,
        grayscale: bool = True,
    ):
        self.root_dir = Path(root_dir)
        self.img_size = img_size
        self.grayscale = grayscale

        self.transform = transform or self._default_transform()

        # Collect all samples
        self.samples = []  # List of (path, label_idx)
        for char_dir in sorted(self.root_dir.iterdir()):
            if char_dir.is_dir() and char_dir.name.upper() in CHAR_TO_IDX:
                label = CHAR_TO_IDX[char_dir.name.upper()]
                for img_file in char_dir.glob("*"):
                    if img_file.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp"):
                        self.samples.append((img_file, label))

        print(f"Found {len(self.samples)} character samples in {root_dir}")

    def _default_transform(self):
        t = [transforms.Resize((self.img_size, self.img_size))]
        if self.grayscale:
            t.append(transforms.Grayscale(num_output_channels=1))
        t.extend([transforms.ToTensor(), transforms.Normalize([0.5], [0.5])])
        return transforms.Compose(t)

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, int]:
        img_path, label = self.samples[idx]
        image = Image.open(img_path)
        if self.transform:
            image = self.transform(image)
        return image, label


class PlateImageDataset(Dataset):
    """
    Dataset for autoencoder training on cropped license plate images.

    Uses high-quality plate crops as targets and generates degraded versions
    as inputs, training the autoencoder to restore quality.
    """

    def __init__(
        self,
        root_dir: str,
        img_height: int = 128,
        img_width: int = 256,
        degradation_fn=None,
        transform=None,
    ):
        self.root_dir = Path(root_dir)
        self.img_height = img_height
        self.img_width = img_width
        self.degradation_fn = degradation_fn

        self.transform = transform or transforms.Compose(
            [
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]),
            ]
        )

        # Find all plate crop images
        self.image_paths = sorted(
            [
                p
                for p in self.root_dir.rglob("*")
                if p.suffix.lower() in (".jpg", ".jpeg", ".png")
            ]
        )

        print(f"Found {len(self.image_paths)} plate images for autoencoder training")

    def __len__(self) -> int:
        return len(self.image_paths)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        """Returns (degraded_image, clean_image) pair."""
        img_path = self.image_paths[idx]
        image = cv2.imread(str(img_path))
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Resize to target dimensions
        clean = cv2.resize(
            image, (self.img_width, self.img_height), interpolation=cv2.INTER_LINEAR
        )

        # Generate degraded version
        if self.degradation_fn:
            degraded = self.degradation_fn(clean.copy())
        else:
            # Default: downsample by 4x then upsample
            small = cv2.resize(
                clean,
                (self.img_width // 4, self.img_height // 4),
                interpolation=cv2.INTER_AREA,
            )
            degraded = cv2.resize(
                small,
                (self.img_width, self.img_height),
                interpolation=cv2.INTER_CUBIC,
            )

        clean_tensor = self.transform(clean)
        degraded_tensor = self.transform(degraded)

        return degraded_tensor, clean_tensor


def get_data_loaders(
    config: dict,
    dataset_type: str = "detection",
    target_resolution: Optional[int] = None,
    device: Optional[str] = None,
) -> Tuple[DataLoader, DataLoader, Optional[DataLoader]]:
    """
    Create train/val/test data loaders based on configuration.

    Args:
        config: Project configuration dict
        dataset_type: "detection", "classification", or "autoencoder"
        target_resolution: Optional resolution override for experiments
        device: Requested device for DataLoader memory settings
    """
    batch_size_key = {
        "detection": "detection",
        "classification": "classification",
        "autoencoder": "autoencoder",
    }
    batch_size = config[batch_size_key[dataset_type]]["batch_size"]

    if dataset_type == "detection":
        train_ds = OpenALPRDataset(
            config["data"]["train_dir"],
            img_size=config["detection"]["img_size"],
            target_resolution=target_resolution,
        )
        val_ds = OpenALPRDataset(
            config["data"]["val_dir"],
            img_size=config["detection"]["img_size"],
            target_resolution=target_resolution,
        )
        test_ds = None
        test_path = config["data"].get("test_dir")
        if test_path and os.path.exists(test_path):
            test_ds = OpenALPRDataset(
                test_path,
                img_size=config["detection"]["img_size"],
                target_resolution=target_resolution,
            )

    elif dataset_type == "classification":
        train_ds = CharacterDataset(
            os.path.join(config["data"]["root_dir"], "characters", "train"),
            img_size=config["classification"]["input_size"],
        )
        val_ds = CharacterDataset(
            os.path.join(config["data"]["root_dir"], "characters", "val"),
            img_size=config["classification"]["input_size"],
        )
        test_ds = None

    elif dataset_type == "autoencoder":
        train_ds = PlateImageDataset(
            os.path.join(config["data"]["root_dir"], "plates", "train"),
            img_height=config["autoencoder"]["input_size"],
            img_width=config["autoencoder"]["input_width"],
        )
        val_ds = PlateImageDataset(
            os.path.join(config["data"]["root_dir"], "plates", "val"),
            img_height=config["autoencoder"]["input_size"],
            img_width=config["autoencoder"]["input_width"],
        )
        test_ds = None
    else:
        raise ValueError(f"Unknown dataset_type: {dataset_type}")

    num_workers = min(4, os.cpu_count() or 1)
    pin_memory = use_pinned_memory(resolve_device(device))

    train_loader = DataLoader(
        train_ds,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=pin_memory,
        drop_last=True,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=pin_memory,
    )
    test_loader = None
    if test_ds:
        test_loader = DataLoader(
            test_ds,
            batch_size=batch_size,
            shuffle=False,
            num_workers=num_workers,
            pin_memory=pin_memory,
        )

    return train_loader, val_loader, test_loader


def extract_plate_crops(
    image_dir: str,
    label_dir: str,
    output_dir: str,
    img_size: int = 640,
    padding: float = 0.1,
):
    """
    Extract cropped license plate regions from detection dataset.

    Used to create training data for the autoencoder and character classifier.

    Args:
        image_dir: Directory with full images
        label_dir: Directory with YOLO-format label files
        output_dir: Where to save cropped plates
        img_size: Image size (for denormalizing YOLO coords)
        padding: Extra padding around plate bounding box (fraction)
    """
    os.makedirs(output_dir, exist_ok=True)
    img_dir = Path(image_dir)
    lbl_dir = Path(label_dir)

    count = 0
    for img_path in sorted(img_dir.glob("*")):
        if img_path.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            continue

        image = cv2.imread(str(img_path))
        if image is None:
            continue
        h, w = image.shape[:2]

        label_path = lbl_dir / (img_path.stem + ".txt")
        if not label_path.exists():
            continue

        with open(label_path, "r") as f:
            for i, line in enumerate(f.readlines()):
                parts = line.strip().split()
                if len(parts) < 5:
                    continue

                # YOLO format: class x_center y_center width height (normalized)
                x_c, y_c, bw, bh = map(float, parts[1:5])

                # Convert to pixel coordinates
                x1 = int((x_c - bw / 2) * w)
                y1 = int((y_c - bh / 2) * h)
                x2 = int((x_c + bw / 2) * w)
                y2 = int((y_c + bh / 2) * h)

                # Add padding
                pad_x = int((x2 - x1) * padding)
                pad_y = int((y2 - y1) * padding)
                x1 = max(0, x1 - pad_x)
                y1 = max(0, y1 - pad_y)
                x2 = min(w, x2 + pad_x)
                y2 = min(h, y2 + pad_y)

                # Crop and save
                crop = image[y1:y2, x1:x2]
                if crop.size > 0:
                    out_path = os.path.join(
                        output_dir, f"{img_path.stem}_plate{i}.jpg"
                    )
                    cv2.imwrite(out_path, crop)
                    count += 1

    print(f"Extracted {count} plate crops to {output_dir}")
    return count
