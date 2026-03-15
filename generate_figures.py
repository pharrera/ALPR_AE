"""
Generate publication-quality figures for the LPR resolution degradation study.

Creates:
  1. Multi-panel resolution vs mAP comparison (all degradation types)
  2. Autoencoder reconstruction gallery (degraded → restored → original)
  3. Degradation severity heatmap (resolution × degradation type)
  4. Detection confidence vs resolution scatter
  5. PSNR/SSIM quality-accuracy correlation plot
  6. Full-image degradation progression strip

Usage:
    python generate_figures.py \
        --results results/experiment/experiment_results.json \
        --autoencoder-weights results/autoencoder/unet/best_autoencoder.pth \
        --detector-weights results/detection/plate_detection/weights/best.pt \
        --test-dir data/test \
        --plate-dir data/plates/test \
        --output-dir results/figures
"""

import argparse
import os
import json
import math
import cv2
import numpy as np
import torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.colors import LinearSegmentedColormap
from pathlib import Path

# ── Styling ────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 12,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "axes.grid": True,
    "grid.alpha": 0.3,
})

COLORS = {
    "baseline":     "#e74c3c",
    "upscale_only": "#3498db",
    "autoencoder":  "#2ecc71",
}
LABELS = {
    "baseline":     "Baseline (degraded)",
    "upscale_only": "Bicubic upscale",
    "autoencoder":  "Autoencoder restoration",
}
MARKERS = {"baseline": "o", "upscale_only": "s", "autoencoder": "D"}
DEG_LABELS = {
    "bicubic_downsample": "Bicubic Down-sample",
    "gaussian_blur":      "Gaussian Blur",
    "jpeg_compression":   "JPEG Compression",
    "combined":           "Combined",
}


# ══════════════════════════════════════════════════════════════════════
# FIGURE 1 — Multi-panel resolution vs mAP (the "main result")
# ══════════════════════════════════════════════════════════════════════
def fig1_resolution_curves(data, save_dir):
    """4-panel figure: one per degradation type, mAP vs resolution."""
    deg_types = ["bicubic_downsample", "gaussian_blur", "jpeg_compression", "combined"]
    fig, axes = plt.subplots(2, 2, figsize=(12, 9), sharey=True)
    axes = axes.ravel()

    for ax, deg in zip(axes, deg_types):
        for cond in ["baseline", "upscale_only", "autoencoder"]:
            resolutions, maps = [], []
            for key, val in sorted(data.items()):
                if key.startswith(deg + "_"):
                    res = int(key.split("_")[-1])
                    resolutions.append(res)
                    maps.append(val.get(cond, {}).get("mAP", 0))
            ax.plot(resolutions, maps,
                    color=COLORS[cond], marker=MARKERS[cond],
                    linewidth=2, markersize=7, label=LABELS[cond])

        ax.set_title(DEG_LABELS[deg], fontweight="bold")
        ax.set_xlabel("Resolution (px)")
        ax.set_ylabel("mAP")
        ax.set_ylim(-0.02, 1.0)
        ax.invert_xaxis()

    axes[0].legend(loc="lower left", framealpha=0.9)
    fig.suptitle("Detection Accuracy vs. Resolution Across Degradation Types",
                 fontsize=15, fontweight="bold", y=1.01)
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "fig1_resolution_curves.png"))
    plt.close()
    print("  ✓ fig1_resolution_curves.png")


# ══════════════════════════════════════════════════════════════════════
# FIGURE 2 — Autoencoder reconstruction gallery
# ══════════════════════════════════════════════════════════════════════
def fig2_reconstruction_gallery(plate_dir, autoencoder, device, save_dir):
    """Show degraded → reconstructed → original for 4 plates × 3 degradation levels."""
    from utils.degradation import ImageDegrader
    degrader = ImageDegrader(base_resolution=256)

    plates = sorted(Path(plate_dir).glob("*.jpg"))[:6]
    if not plates:
        print("  ✗ Skipping fig2: no plate crops found")
        return

    resolutions = [256, 128, 64]  # simulate 1×, 0.5×, 0.25× for plate crops
    n_plates = min(4, len(plates))

    fig, axes = plt.subplots(n_plates, 3 * len(resolutions),
                             figsize=(3 * len(resolutions) * 2.2, n_plates * 2.2))
    if n_plates == 1:
        axes = axes[np.newaxis, :]

    for row, plate_path in enumerate(plates[:n_plates]):
        plate = cv2.imread(str(plate_path))
        plate = cv2.cvtColor(plate, cv2.COLOR_BGR2RGB)
        plate_resized = cv2.resize(plate, (256, 128))

        for ri, res in enumerate(resolutions):
            # Degrade
            if res < 256:
                degraded = degrader.bicubic_downsample(plate_resized, res, upscale_back=True)
            else:
                degraded = plate_resized.copy()

            # Restore with autoencoder
            inp = torch.from_numpy(degraded).permute(2, 0, 1).float() / 255.0
            inp = inp.unsqueeze(0).to(device)
            with torch.no_grad():
                out = autoencoder(inp)
            restored = out.squeeze(0).permute(1, 2, 0).cpu().numpy()
            restored = np.clip(restored * 255, 0, 255).astype(np.uint8)

            col_base = ri * 3
            for ci, (img, title) in enumerate([
                (degraded,      f"Degraded ({res}px)"),
                (restored,      "AE Restored"),
                (plate_resized, "Original"),
            ]):
                ax = axes[row, col_base + ci]
                ax.imshow(img)
                ax.axis("off")
                if row == 0:
                    ax.set_title(title, fontsize=9, fontweight="bold" if ci == 1 else "normal")

    fig.suptitle("Autoencoder Plate Restoration: Degraded → Restored → Ground Truth",
                 fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "fig2_reconstruction_gallery.png"))
    plt.close()
    print("  ✓ fig2_reconstruction_gallery.png")


# ══════════════════════════════════════════════════════════════════════
# FIGURE 3 — Heatmap: mAP across resolution × degradation type
# ══════════════════════════════════════════════════════════════════════
def fig3_heatmap(data, save_dir):
    """Heatmap showing mAP for each (degradation, resolution) cell — baseline condition."""
    deg_types = ["bicubic_downsample", "gaussian_blur", "jpeg_compression", "combined"]
    resolutions = [640, 480, 320, 240, 160, 80, 40]

    matrix = np.zeros((len(deg_types), len(resolutions)))
    for di, deg in enumerate(deg_types):
        for ri, res in enumerate(resolutions):
            key = f"{deg}_{res}"
            matrix[di, ri] = data.get(key, {}).get("baseline", {}).get("mAP", 0)

    fig, ax = plt.subplots(figsize=(10, 4))
    cmap = LinearSegmentedColormap.from_list("rg", ["#e74c3c", "#f39c12", "#2ecc71"])
    im = ax.imshow(matrix, cmap=cmap, aspect="auto", vmin=0, vmax=1)

    ax.set_xticks(range(len(resolutions)))
    ax.set_xticklabels([str(r) for r in resolutions])
    ax.set_yticks(range(len(deg_types)))
    ax.set_yticklabels([DEG_LABELS[d] for d in deg_types])
    ax.set_xlabel("Resolution (px)")
    ax.set_title("Detection mAP Across Degradation Types and Resolutions",
                 fontweight="bold")

    # Annotate cells
    for di in range(len(deg_types)):
        for ri in range(len(resolutions)):
            val = matrix[di, ri]
            color = "white" if val < 0.5 else "black"
            ax.text(ri, di, f"{val:.2f}", ha="center", va="center",
                    color=color, fontsize=10, fontweight="bold")

    plt.colorbar(im, ax=ax, label="mAP", shrink=0.8)
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "fig3_degradation_heatmap.png"))
    plt.close()
    print("  ✓ fig3_degradation_heatmap.png")


# ══════════════════════════════════════════════════════════════════════
# FIGURE 4 — PSNR/SSIM vs detection accuracy scatter
# ══════════════════════════════════════════════════════════════════════
def fig4_quality_accuracy(data, save_dir):
    """Scatter plot: image quality (PSNR, SSIM) vs detection mAP."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    deg_colors = {
        "bicubic_downsample": "#e74c3c",
        "gaussian_blur": "#9b59b6",
        "jpeg_compression": "#f39c12",
        "combined": "#1abc9c",
    }

    for deg_type, color in deg_colors.items():
        psnrs, ssims, maps = [], [], []
        for key, val in data.items():
            if key.startswith(deg_type + "_"):
                bl = val.get("baseline", {})
                p = bl.get("psnr", 0)
                if p == float("inf") or p > 100:
                    continue
                psnrs.append(p)
                ssims.append(bl.get("ssim", 0))
                maps.append(bl.get("mAP", 0))

        ax1.scatter(psnrs, maps, color=color, s=80, alpha=0.8,
                    edgecolors="white", linewidth=0.5,
                    label=DEG_LABELS[deg_type])
        ax2.scatter(ssims, maps, color=color, s=80, alpha=0.8,
                    edgecolors="white", linewidth=0.5,
                    label=DEG_LABELS[deg_type])

    ax1.set_xlabel("PSNR (dB)")
    ax1.set_ylabel("Detection mAP")
    ax1.set_title("PSNR vs Detection Accuracy", fontweight="bold")
    ax1.legend()

    ax2.set_xlabel("SSIM")
    ax2.set_ylabel("Detection mAP")
    ax2.set_title("SSIM vs Detection Accuracy", fontweight="bold")
    ax2.legend()

    fig.suptitle("Image Quality Metrics vs. Detection Performance",
                 fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "fig4_quality_vs_accuracy.png"))
    plt.close()
    print("  ✓ fig4_quality_vs_accuracy.png")


# ══════════════════════════════════════════════════════════════════════
# FIGURE 5 — Autoencoder improvement bar chart (combined degradation)
# ══════════════════════════════════════════════════════════════════════
def fig5_improvement_bars(data, save_dir):
    """Bar chart showing mAP improvement from autoencoder over baseline."""
    resolutions = [480, 320, 240, 160, 80, 40]
    deg_types = ["bicubic_downsample", "combined"]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)

    for ax, deg in zip(axes, deg_types):
        baseline_vals = []
        upscale_gains = []
        ae_gains = []

        for res in resolutions:
            key = f"{deg}_{res}"
            bl = data.get(key, {}).get("baseline", {}).get("mAP", 0)
            up = data.get(key, {}).get("upscale_only", {}).get("mAP", 0)
            ae = data.get(key, {}).get("autoencoder", {}).get("mAP", 0)
            baseline_vals.append(bl)
            upscale_gains.append(up - bl)
            ae_gains.append(ae - bl)

        x = np.arange(len(resolutions))
        width = 0.35

        ax.bar(x - width/2, upscale_gains, width, color=COLORS["upscale_only"],
               label="Bicubic upscale gain", edgecolor="white")
        ax.bar(x + width/2, ae_gains, width, color=COLORS["autoencoder"],
               label="Autoencoder gain", edgecolor="white")
        ax.axhline(y=0, color="gray", linewidth=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels([str(r) for r in resolutions])
        ax.set_xlabel("Resolution (px)")
        ax.set_ylabel("mAP Improvement over Baseline")
        ax.set_title(DEG_LABELS[deg], fontweight="bold")
        ax.legend(loc="upper right")

    fig.suptitle("Restoration Method Improvement over Degraded Baseline",
                 fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "fig5_improvement_bars.png"))
    plt.close()
    print("  ✓ fig5_improvement_bars.png")


# ══════════════════════════════════════════════════════════════════════
# FIGURE 6 — Full-image degradation progression strip
# ══════════════════════════════════════════════════════════════════════
def fig6_degradation_strip(test_dir, save_dir):
    """Show a single test image at progressively decreasing resolutions."""
    from utils.degradation import ImageDegrader
    degrader = ImageDegrader(base_resolution=640)

    imgs = sorted(Path(test_dir).glob("images/*.jpg"))
    if not imgs:
        print("  ✗ Skipping fig6: no test images found")
        return

    # Pick a good example (the 5th image — skip the first few)
    img_path = imgs[min(4, len(imgs) - 1)]
    image = cv2.imread(str(img_path))
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    resolutions = [640, 480, 320, 240, 160, 80, 40]
    fig, axes = plt.subplots(1, len(resolutions), figsize=(3.5 * len(resolutions), 3.5))

    for ax, res in zip(axes, resolutions):
        if res < 640:
            degraded = degrader.bicubic_downsample(image, res, upscale_back=True)
        else:
            degraded = image.copy()
        ax.imshow(degraded)
        ax.set_title(f"{res}px", fontsize=12, fontweight="bold")
        ax.axis("off")

    fig.suptitle("Progressive Resolution Degradation (Bicubic Downsampling)",
                 fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "fig6_degradation_strip.png"))
    plt.close()
    print("  ✓ fig6_degradation_strip.png")


# ══════════════════════════════════════════════════════════════════════
# FIGURE 7 — Detection on degraded images (visual comparison)
# ══════════════════════════════════════════════════════════════════════
def fig7_detection_comparison(test_dir, detector, save_dir):
    """Show detector bounding boxes on same image at 3 resolution levels."""
    from utils.degradation import ImageDegrader
    degrader = ImageDegrader(base_resolution=640)

    imgs = sorted(Path(test_dir).glob("images/*.jpg"))
    if not imgs or detector is None:
        print("  ✗ Skipping fig7: no test images or detector not loaded")
        return

    img_path = imgs[min(4, len(imgs) - 1)]
    image = cv2.imread(str(img_path))
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    resolutions = [640, 320, 160, 80]
    fig, axes = plt.subplots(1, len(resolutions), figsize=(5 * len(resolutions), 5))

    for ax, res in zip(axes, resolutions):
        if res < 640:
            degraded = degrader.bicubic_downsample(image, res, upscale_back=True)
        else:
            degraded = image.copy()

        # Run detector
        img_bgr = cv2.cvtColor(degraded, cv2.COLOR_RGB2BGR)
        detections = detector.detect(img_bgr)

        # Draw boxes
        vis = degraded.copy()
        for det in detections:
            x1, y1, x2, y2 = [int(c) for c in det["bbox"]]
            conf = det["confidence"]
            cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 3)
            cv2.putText(vis, f"{conf:.2f}", (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        ax.imshow(vis)
        n_det = len(detections)
        ax.set_title(f"{res}px — {n_det} detection{'s' if n_det != 1 else ''}",
                     fontsize=12, fontweight="bold")
        ax.axis("off")

    fig.suptitle("License Plate Detection at Varying Resolutions",
                 fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "fig7_detection_comparison.png"))
    plt.close()
    print("  ✓ fig7_detection_comparison.png")


# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="Generate paper figures")
    parser.add_argument("--results", default="results/experiment/experiment_results.json")
    parser.add_argument("--autoencoder-weights", default=None)
    parser.add_argument("--detector-weights", default=None)
    parser.add_argument("--test-dir", default="data/test")
    parser.add_argument("--plate-dir", default="data/plates/test")
    parser.add_argument("--output-dir", default="results/figures")
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # Load experiment results
    with open(args.results) as f:
        data = json.load(f)
    print(f"Loaded results: {len(data)} conditions")

    print("\nGenerating figures...")

    # Fig 1 — main result curves (no models needed)
    fig1_resolution_curves(data, args.output_dir)

    # Fig 3 — heatmap (no models needed)
    fig3_heatmap(data, args.output_dir)

    # Fig 4 — quality vs accuracy scatter (no models needed)
    fig4_quality_accuracy(data, args.output_dir)

    # Fig 5 — improvement bars (no models needed)
    fig5_improvement_bars(data, args.output_dir)

    # Fig 6 — degradation strip (no models needed, just test images)
    fig6_degradation_strip(args.test_dir, args.output_dir)

    # Fig 2 — reconstruction gallery (needs autoencoder)
    if args.autoencoder_weights and os.path.exists(args.autoencoder_weights):
        from utils.device import resolve_device
        from models.autoencoder import UNetAutoencoder
        from utils.data_loader import load_config

        device = resolve_device(args.device)
        config = load_config("configs/config.yaml")
        ae_cfg = config["autoencoder"]

        autoencoder = UNetAutoencoder(
            in_channels=3,
            base_features=ae_cfg["encoder_channels"][0],
            depth=len(ae_cfg["encoder_channels"]),
        )
        state_dict = torch.load(args.autoencoder_weights, map_location=device)
        if any(k.startswith("module.") for k in state_dict):
            state_dict = {k[len("module."):]: v for k, v in state_dict.items()}
        autoencoder.load_state_dict(state_dict)
        autoencoder = autoencoder.to(device).eval()

        fig2_reconstruction_gallery(args.plate_dir, autoencoder, device, args.output_dir)
    else:
        print("  ✗ Skipping fig2: no autoencoder weights provided")

    # Fig 7 — detection comparison (needs detector)
    if args.detector_weights and os.path.exists(args.detector_weights):
        from models.detector import PlateDetector
        detector = PlateDetector(
            model_path=args.detector_weights,
            confidence=0.3,  # lower threshold to show more detections
            device="cpu",    # CPU is fine for a few images
        )
        fig7_detection_comparison(args.test_dir, detector, args.output_dir)
    else:
        print("  ✗ Skipping fig7: no detector weights provided")

    print(f"\nAll figures saved to {args.output_dir}/")


if __name__ == "__main__":
    main()
