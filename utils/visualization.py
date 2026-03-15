"""
Visualization utilities for experiment results and model outputs.

Generates publication-quality plots for:
- Resolution vs. accuracy curves (main result figure)
- Autoencoder reconstruction comparisons
- Training history plots
- Detection visualization
"""

import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from typing import Dict, List, Optional, Tuple

# Use a clean style
plt.style.use("seaborn-v0_8-whitegrid")


def plot_resolution_comparison(
    metrics_tracker,
    metric_name: str = "mAP",
    degradation_type: str = "bicubic_downsample",
    save_path: Optional[str] = None,
    title: Optional[str] = None,
):
    """
    Plot the main result: metric vs resolution for all conditions.

    This is the key figure showing how accuracy degrades with resolution
    and how the autoencoder helps recover it.
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    conditions = ["baseline", "upscale_only", "autoencoder"]
    colors = ["#e74c3c", "#3498db", "#2ecc71"]
    markers = ["o", "s", "D"]
    labels = [
        "Baseline (degraded input)",
        "Bicubic upscale only",
        "Autoencoder restoration",
    ]

    for condition, color, marker, label in zip(conditions, colors, markers, labels):
        resolutions, values = metrics_tracker.get_resolution_curve(
            metric_name, condition, degradation_type
        )
        if resolutions:
            ax.plot(
                resolutions,
                values,
                color=color,
                marker=marker,
                linewidth=2,
                markersize=8,
                label=label,
            )

    ax.set_xlabel("Resolution (pixels)", fontsize=12)
    ax.set_ylabel(metric_name, fontsize=12)
    ax.set_title(
        title or f"{metric_name} vs Resolution ({degradation_type})",
        fontsize=14,
    )
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)

    # Invert x-axis so high resolution is on left (natural reading order)
    ax.invert_xaxis()

    plt.tight_layout()
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved plot to {save_path}")
    plt.close()


def plot_training_history(
    history: Dict[str, List[float]],
    save_path: Optional[str] = None,
    title: str = "Training History",
):
    """Plot training and validation loss/accuracy curves."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Loss
    if "train_loss" in history:
        axes[0].plot(history["train_loss"], label="Train", color="#e74c3c")
    if "val_loss" in history:
        axes[0].plot(history["val_loss"], label="Validation", color="#3498db")
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Loss")
    axes[0].set_title("Loss")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # Accuracy or PSNR
    if "train_acc" in history:
        axes[1].plot(history["train_acc"], label="Train", color="#e74c3c")
        axes[1].plot(history["val_acc"], label="Validation", color="#3498db")
        axes[1].set_ylabel("Accuracy")
        axes[1].set_title("Accuracy")
    elif "val_psnr" in history:
        axes[1].plot(history["val_psnr"], label="Validation PSNR", color="#2ecc71")
        axes[1].set_ylabel("PSNR (dB)")
        axes[1].set_title("Reconstruction Quality")

    axes[1].set_xlabel("Epoch")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    fig.suptitle(title, fontsize=14, y=1.02)
    plt.tight_layout()

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_reconstruction_samples(
    degraded_images: List[np.ndarray],
    reconstructed_images: List[np.ndarray],
    clean_images: List[np.ndarray],
    num_samples: int = 4,
    save_path: Optional[str] = None,
):
    """
    Show side-by-side comparison: degraded | reconstructed | original.

    Useful for qualitative evaluation of the autoencoder.
    """
    n = min(num_samples, len(degraded_images))
    fig, axes = plt.subplots(n, 3, figsize=(12, 3 * n))

    if n == 1:
        axes = axes[np.newaxis, :]

    col_titles = ["Degraded Input", "Autoencoder Output", "Ground Truth"]

    for i in range(n):
        for j, (img, title) in enumerate(
            zip(
                [degraded_images[i], reconstructed_images[i], clean_images[i]],
                col_titles,
            )
        ):
            if img.ndim == 2:
                axes[i, j].imshow(img, cmap="gray")
            else:
                axes[i, j].imshow(img)
            axes[i, j].set_title(title if i == 0 else "", fontsize=11)
            axes[i, j].axis("off")

    plt.suptitle("Autoencoder Reconstruction Samples", fontsize=14)
    plt.tight_layout()

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_degradation_grid(
    original: np.ndarray,
    degraded_samples: List[Tuple[int, np.ndarray]],
    save_path: Optional[str] = None,
):
    """
    Show an image at multiple degradation levels in a grid.

    Args:
        original: Original high-res image
        degraded_samples: List of (resolution, degraded_image) tuples
    """
    n = len(degraded_samples)
    fig, axes = plt.subplots(1, n, figsize=(4 * n, 4))

    if n == 1:
        axes = [axes]

    for ax, (res, img) in zip(axes, degraded_samples):
        if img.ndim == 2:
            ax.imshow(img, cmap="gray")
        else:
            ax.imshow(img)
        ax.set_title(f"{res}px", fontsize=12)
        ax.axis("off")

    plt.suptitle("Resolution Degradation Progression", fontsize=14)
    plt.tight_layout()

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_results(
    metrics_tracker,
    save_dir: str = "results/plots",
):
    """Generate all standard result plots."""
    os.makedirs(save_dir, exist_ok=True)

    # Main result: mAP vs resolution
    for metric in ["mAP", "ocr_accuracy", "detection_accuracy"]:
        for deg_type in ["bicubic_downsample", "combined"]:
            plot_resolution_comparison(
                metrics_tracker,
                metric_name=metric,
                degradation_type=deg_type,
                save_path=os.path.join(save_dir, f"{metric}_{deg_type}.png"),
            )

    print(f"All plots saved to {save_dir}")


def plot_detection_on_image(
    image: np.ndarray,
    detections: List[Dict],
    save_path: Optional[str] = None,
):
    """Draw detection bounding boxes on an image."""
    import cv2

    vis = image.copy()
    for det in detections:
        x1, y1, x2, y2 = [int(c) for c in det["bbox"]]
        conf = det["confidence"]
        cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = f"{conf:.2f}"
        cv2.putText(
            vis, label, (x1, y1 - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2,
        )

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.imshow(vis if vis.ndim == 3 else cv2.cvtColor(vis, cv2.COLOR_BGR2RGB))
    ax.axis("off")
    ax.set_title("Plate Detections")

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()
