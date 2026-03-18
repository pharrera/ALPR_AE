"""
Generate publication-quality figures for the LPR resolution degradation study.

Creates:
  1. Multi-panel resolution vs mAP comparison (all degradation types)
  2. Autoencoder reconstruction gallery (degraded → restored → original)
  3. Degradation severity heatmap (resolution × degradation type)
  4. Detection confidence vs resolution scatter
  5. PSNR/SSIM quality-accuracy correlation plot
  6. Full-image degradation progression strip
  7. Detection bounding boxes at varying resolutions
  8. DQN Training Curves (Reward, Loss, Epsilon)
  9. DQN Learned Policy Action Distribution
 10. OCR Before & After Restoration Examples
 11. GAN vs Autoencoder Reconstruction Comparison
 12. GAN Training Curves (G/D losses, PSNR, component losses)
 13. Experiment Version Comparison (v2 vs v3 results)

Usage:
    python generate_figures.py \
        --results results/experiment_v3/experiment_results.json \
        --results-v2 results/experiment_v2/experiment_results.json \
        --dqn-history results/dqn/dqn_training_history.json \
        --autoencoder-weights results/autoencoder/unet/best_autoencoder.pth \
        --gan-weights results/autoencoder/gan/best_generator.pth \
        --gan-history results/autoencoder/gan/gan_training_results.json \
        --detector-weights results/detection/plate_detection/weights/best.pt \
        --test-dir data/ufpr_yolo/test \
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
    "gan":          "#9b59b6",
}
LABELS = {
    "baseline":     "Baseline (degraded)",
    "upscale_only": "Bicubic upscale",
    "autoencoder":  "Autoencoder restoration",
    "gan":          "GAN restoration",
}
MARKERS = {"baseline": "o", "upscale_only": "s", "autoencoder": "D", "gan": "^"}
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
    from utils.degradation import ImageDegrader
    degrader = ImageDegrader(base_resolution=256)

    # Glob both jpg and png
    plates = list(Path(plate_dir).rglob("*.jpg")) + list(Path(plate_dir).rglob("*.png"))
    plates = sorted(plates)[:6]
    
    if not plates:
        print("  ✗ Skipping fig2: no plate crops found")
        return

    resolutions = [256, 128, 64]
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
            if res < 256:
                degraded = degrader.bicubic_downsample(plate_resized, res, upscale_back=True)
            else:
                degraded = plate_resized.copy()

            # Restore with autoencoder (Applying proper Tanh normalization)
            inp = torch.from_numpy(degraded).permute(2, 0, 1).float() / 255.0
            inp = (inp - 0.5) / 0.5  # Map [0,1] to [-1,1]
            inp = inp.unsqueeze(0).to(device)
            with torch.no_grad():
                out = autoencoder(inp)
            restored = out.squeeze(0).permute(1, 2, 0).cpu().numpy()
            restored = ((restored * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8)

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
# FIGURES 3 to 7 — (Kept exactly identical to existing implementation)
# ══════════════════════════════════════════════════════════════════════
def fig3_heatmap(data, save_dir):
    deg_types = ["bicubic_downsample", "gaussian_blur", "jpeg_compression", "combined"]
    resolutions = [640, 480, 320, 240, 160, 80, 40]
    matrix = np.zeros((len(deg_types), len(resolutions)))
    for di, deg in enumerate(deg_types):
        for ri, res in enumerate(resolutions):
            matrix[di, ri] = data.get(f"{deg}_{res}", {}).get("baseline", {}).get("mAP", 0)

    fig, ax = plt.subplots(figsize=(10, 4))
    cmap = LinearSegmentedColormap.from_list("rg", ["#e74c3c", "#f39c12", "#2ecc71"])
    im = ax.imshow(matrix, cmap=cmap, aspect="auto", vmin=0, vmax=1)
    ax.set_xticks(range(len(resolutions)))
    ax.set_xticklabels([str(r) for r in resolutions])
    ax.set_yticks(range(len(deg_types)))
    ax.set_yticklabels([DEG_LABELS[d] for d in deg_types])
    ax.set_xlabel("Resolution (px)")
    ax.set_title("Detection mAP Across Degradation Types and Resolutions", fontweight="bold")

    for di in range(len(deg_types)):
        for ri in range(len(resolutions)):
            val = matrix[di, ri]
            color = "white" if val < 0.5 else "black"
            ax.text(ri, di, f"{val:.2f}", ha="center", va="center", color=color, fontsize=10, fontweight="bold")
    plt.colorbar(im, ax=ax, label="mAP", shrink=0.8)
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "fig3_degradation_heatmap.png"))
    plt.close()
    print("  ✓ fig3_degradation_heatmap.png")

def fig4_quality_accuracy(data, save_dir):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    deg_colors = {"bicubic_downsample": "#e74c3c", "gaussian_blur": "#9b59b6", "jpeg_compression": "#f39c12", "combined": "#1abc9c"}
    for deg_type, color in deg_colors.items():
        psnrs, ssims, maps = [], [], []
        for key, val in data.items():
            if key.startswith(deg_type + "_"):
                bl = val.get("baseline", {})
                p = bl.get("psnr", 0)
                if p == float("inf") or p > 100: continue
                psnrs.append(p)
                ssims.append(bl.get("ssim", 0))
                maps.append(bl.get("mAP", 0))
        ax1.scatter(psnrs, maps, color=color, s=80, alpha=0.8, edgecolors="white", linewidth=0.5, label=DEG_LABELS[deg_type])
        ax2.scatter(ssims, maps, color=color, s=80, alpha=0.8, edgecolors="white", linewidth=0.5, label=DEG_LABELS[deg_type])
    ax1.set_xlabel("PSNR (dB)"); ax1.set_ylabel("Detection mAP"); ax1.set_title("PSNR vs Detection Accuracy", fontweight="bold"); ax1.legend()
    ax2.set_xlabel("SSIM"); ax2.set_ylabel("Detection mAP"); ax2.set_title("SSIM vs Detection Accuracy", fontweight="bold"); ax2.legend()
    fig.suptitle("Image Quality Metrics vs. Detection Performance", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "fig4_quality_vs_accuracy.png"))
    plt.close()
    print("  ✓ fig4_quality_vs_accuracy.png")

def fig5_improvement_bars(data, save_dir):
    resolutions = [480, 320, 240, 160, 80, 40]
    deg_types = ["bicubic_downsample", "combined"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    for ax, deg in zip(axes, deg_types):
        baseline_vals, upscale_gains, ae_gains = [], [], []
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
        ax.bar(x - width/2, upscale_gains, width, color=COLORS["upscale_only"], label="Bicubic upscale gain", edgecolor="white")
        ax.bar(x + width/2, ae_gains, width, color=COLORS["autoencoder"], label="Autoencoder gain", edgecolor="white")
        ax.axhline(y=0, color="gray", linewidth=0.8)
        ax.set_xticks(x); ax.set_xticklabels([str(r) for r in resolutions])
        ax.set_xlabel("Resolution (px)"); ax.set_ylabel("mAP Improvement over Baseline"); ax.set_title(DEG_LABELS[deg], fontweight="bold")
        ax.legend(loc="upper right")
    fig.suptitle("Restoration Method Improvement over Degraded Baseline", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "fig5_improvement_bars.png"))
    plt.close()
    print("  ✓ fig5_improvement_bars.png")

def fig6_degradation_strip(test_dir, save_dir):
    from utils.degradation import ImageDegrader
    degrader = ImageDegrader(base_resolution=640)
    imgs = list(Path(test_dir).rglob("*.jpg")) + list(Path(test_dir).rglob("*.png"))
    if not imgs:
        print("  ✗ Skipping fig6: no test images found")
        return
    img_path = sorted(imgs)[min(4, len(imgs) - 1)]
    image = cv2.imread(str(img_path))
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    resolutions = [640, 480, 320, 240, 160, 80, 40]
    fig, axes = plt.subplots(1, len(resolutions), figsize=(3.5 * len(resolutions), 3.5))
    for ax, res in zip(axes, resolutions):
        degraded = degrader.bicubic_downsample(image, res, upscale_back=True) if res < 640 else image.copy()
        ax.imshow(degraded); ax.set_title(f"{res}px", fontsize=12, fontweight="bold"); ax.axis("off")
    fig.suptitle("Progressive Resolution Degradation (Bicubic Downsampling)", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "fig6_degradation_strip.png"))
    plt.close()
    print("  ✓ fig6_degradation_strip.png")

def fig7_detection_comparison(test_dir, detector, save_dir):
    from utils.degradation import ImageDegrader
    degrader = ImageDegrader(base_resolution=640)
    imgs = list(Path(test_dir).rglob("*.jpg")) + list(Path(test_dir).rglob("*.png"))
    if not imgs or detector is None:
        print("  ✗ Skipping fig7: no test images or detector not loaded")
        return
    img_path = sorted(imgs)[min(4, len(imgs) - 1)]
    image = cv2.imread(str(img_path))
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    resolutions = [640, 320, 160, 80]
    fig, axes = plt.subplots(1, len(resolutions), figsize=(5 * len(resolutions), 5))
    for ax, res in zip(axes, resolutions):
        degraded = degrader.bicubic_downsample(image, res, upscale_back=True) if res < 640 else image.copy()
        img_bgr = cv2.cvtColor(degraded, cv2.COLOR_RGB2BGR)
        detections = detector.detect(img_bgr)
        vis = degraded.copy()
        for det in detections:
            x1, y1, x2, y2 = [int(c) for c in det["bbox"]]
            cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 3)
            cv2.putText(vis, f"{det['confidence']:.2f}", (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        ax.imshow(vis)
        n_det = len(detections)
        ax.set_title(f"{res}px — {n_det} det.", fontsize=12, fontweight="bold"); ax.axis("off")
    fig.suptitle("License Plate Detection at Varying Resolutions", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "fig7_detection_comparison.png"))
    plt.close()
    print("  ✓ fig7_detection_comparison.png")


# ══════════════════════════════════════════════════════════════════════
# FIGURE 8 — DQN Training Curves (Loss, Reward, Epsilon)
# ══════════════════════════════════════════════════════════════════════
def fig8_dqn_training_curves(dqn_history_path, save_dir):
    if not dqn_history_path or not os.path.exists(dqn_history_path):
        print("  ✗ Skipping fig8: DQN history file not found")
        return
        
    with open(dqn_history_path, "r") as f:
        data = json.load(f)

    rewards = data.get("reward", [])
    losses = data.get("loss", [])
    epsilons = data.get("epsilon", [])

    if not rewards:
        print("  ✗ Skipping fig8: Empty DQN history")
        return

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # Average Reward Curve
    axes[0].plot(rewards, color="#2ecc71", alpha=0.3)
    if len(rewards) > 10:
        smoothed = np.convolve(rewards, np.ones(10)/10, mode='valid')
        axes[0].plot(range(9, len(rewards)), smoothed, color="#27ae60", linewidth=2)
    axes[0].set_title("Episode Reward (OCR Accuracy)", fontweight="bold")
    axes[0].set_xlabel("Episode")
    axes[0].set_ylabel("Avg Reward")

    # Loss Curve
    axes[1].plot(losses, color="#e74c3c", alpha=0.3)
    if len(losses) > 10:
        smoothed_loss = np.convolve(losses, np.ones(10)/10, mode='valid')
        axes[1].plot(range(9, len(losses)), smoothed_loss, color="#c0392b", linewidth=2)
    axes[1].set_title("Q-Network Training Loss", fontweight="bold")
    axes[1].set_xlabel("Episode")
    axes[1].set_ylabel("Loss")
    axes[1].set_yscale("log")

    # Epsilon Decay Curve
    axes[2].plot(epsilons, color="#3498db", linewidth=2)
    axes[2].set_title("Exploration Rate (\u03B5)", fontweight="bold")
    axes[2].set_xlabel("Episode")
    axes[2].set_ylabel("Epsilon")

    fig.suptitle("DQN Restoration Agent Training History", fontsize=16, fontweight="bold", y=1.05)
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "fig8_dqn_training_curves.png"))
    plt.close()
    print("  ✓ fig8_dqn_training_curves.png")


# ══════════════════════════════════════════════════════════════════════
# FIGURE 9 — DQN Learned Action Policy Distribution
# ══════════════════════════════════════════════════════════════════════
def fig9_dqn_action_dist(dqn_history_path, save_dir):
    if not dqn_history_path or not os.path.exists(dqn_history_path):
        print("  ✗ Skipping fig9: DQN history file not found")
        return
        
    with open(dqn_history_path, "r") as f:
        data = json.load(f)

    dist = data.get("final_action_distribution", {})
    if not dist:
        print("  ✗ Skipping fig9: No action distribution in DQN history")
        return

    actions = ["pass_through", "bicubic_upscale", "autoencoder_restore"]
    counts = [dist.get(a, 0) for a in actions]
    friendly_labels = ["Pass-Through\n(High Quality)", "Bicubic Upscale\n(Mild Degraded)", "Autoencoder\n(Heavy Degraded)"]

    fig, ax = plt.subplots(figsize=(7, 5))
    colors = [COLORS["baseline"], COLORS["upscale_only"], COLORS["autoencoder"]]
    
    bars = ax.bar(friendly_labels, counts, color=colors, edgecolor="white", linewidth=1.5)
    ax.set_title("DQN Learned Policy: Action Distribution", fontweight="bold")
    ax.set_ylabel("Times Selected During Eval")
    
    # Add counts above bars
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, yval + (max(counts)*0.02), 
                f"{yval:,}", ha='center', va='bottom', fontweight="bold")

    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "fig9_dqn_action_dist.png"))
    plt.close()
    print("  ✓ fig9_dqn_action_dist.png")


# ══════════════════════════════════════════════════════════════════════
# FIGURE 10 — OCR Before & After Restoration 
# ══════════════════════════════════════════════════════════════════════
def fig10_before_after_ocr(plate_dir, autoencoder, device, save_dir):
    """Show heavily degraded plates alongside AE restored versions + OCR outputs."""
    from utils.degradation import ImageDegrader
    try:
        from utils.ocr_utils import create_ocr_engine, run_ocr_with_preprocessing
        ocr_engine = create_ocr_engine(
            languages=["en", "pt"], gpu=(device != "cpu")
        )
    except (ImportError, Exception):
        print("  ✗ Skipping fig10: OCR engine not available")
        return

    degrader = ImageDegrader(base_resolution=256)
    plates = list(Path(plate_dir).rglob("*.jpg")) + list(Path(plate_dir).rglob("*.png"))
    plates = sorted(plates)[:4]

    if not plates:
        print("  ✗ Skipping fig10: no plate crops found")
        return

    def _ocr(img):
        text, conf = run_ocr_with_preprocessing(
            ocr_engine, img, allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        )
        return text if text else "[FAILED]"

    fig, axes = plt.subplots(len(plates), 2, figsize=(9, 2.5 * len(plates)))
    if len(plates) == 1: axes = axes[np.newaxis, :]

    for row, plate_path in enumerate(plates):
        plate = cv2.imread(str(plate_path))
        plate = cv2.cvtColor(plate, cv2.COLOR_BGR2RGB)
        plate_resized = cv2.resize(plate, (256, 128))

        # Apply Heavy Combined Degradation (simulate a bad security cam)
        degraded = degrader.combined_degradation(plate_resized, target_resolution=80)
        degraded_up = cv2.resize(degraded, (256, 128), interpolation=cv2.INTER_CUBIC)

        # Baseline OCR (Before)
        bl_text = _ocr(degraded_up)

        # Autoencoder Restore
        inp = torch.from_numpy(degraded_up).permute(2, 0, 1).float() / 255.0
        inp = (inp - 0.5) / 0.5  # Normalize to [-1, 1]
        inp = inp.unsqueeze(0).to(device)
        with torch.no_grad():
            out = autoencoder(inp)
        restored = out.squeeze(0).permute(1, 2, 0).cpu().numpy()
        restored = ((restored * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8)

        # AE OCR (After)
        ae_text = _ocr(restored)

        # Plot Before
        ax1 = axes[row, 0]
        ax1.imshow(degraded_up)
        ax1.axis("off")
        ax1.set_title(f"Baseline\nOCR: '{bl_text}'", color="#c0392b", fontweight="bold")

        # Plot After
        ax2 = axes[row, 1]
        ax2.imshow(restored)
        ax2.axis("off")
        ax2.set_title(f"Autoencoder Restored\nOCR: '{ae_text}'", color="#27ae60", fontweight="bold")

    fig.suptitle("End-to-End Impact: Autoencoder Restoration Rescues OCR",
                 fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "fig10_before_after_ocr.png"))
    plt.close()
    print("  ✓ fig10_before_after_ocr.png")


# ══════════════════════════════════════════════════════════════════════
# FIGURE 11 — GAN vs Autoencoder Reconstruction Comparison
# ══════════════════════════════════════════════════════════════════════
def fig11_gan_vs_ae_gallery(plate_dir, autoencoder, gan_generator, device, save_dir):
    """Side-by-side: Degraded → AE Restored → GAN Restored → Original."""
    from utils.degradation import ImageDegrader
    degrader = ImageDegrader(base_resolution=256)

    plates = list(Path(plate_dir).rglob("*.jpg")) + list(Path(plate_dir).rglob("*.png"))
    plates = sorted(plates)[:6]

    if not plates:
        print("  ✗ Skipping fig11: no plate crops found")
        return

    n_plates = min(5, len(plates))
    resolutions = [128, 64, 32]  # Focus on challenging resolutions

    fig, axes = plt.subplots(n_plates, 4 * len(resolutions),
                             figsize=(4 * len(resolutions) * 2.0, n_plates * 2.2))
    if n_plates == 1:
        axes = axes[np.newaxis, :]

    def _restore(model, img, dev):
        """Run a model on a single plate image."""
        inp = torch.from_numpy(img).permute(2, 0, 1).float() / 255.0
        inp = (inp - 0.5) / 0.5
        inp = inp.unsqueeze(0).to(dev)
        with torch.no_grad():
            out = model(inp)
            if isinstance(out, tuple):
                out = out[0]
        result = out.squeeze(0).permute(1, 2, 0).cpu().numpy()
        return ((result * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8)

    for row, plate_path in enumerate(plates[:n_plates]):
        plate = cv2.imread(str(plate_path))
        plate = cv2.cvtColor(plate, cv2.COLOR_BGR2RGB)
        plate_resized = cv2.resize(plate, (256, 128))

        for ri, res in enumerate(resolutions):
            degraded = degrader.bicubic_downsample(plate_resized, res, upscale_back=True)
            ae_restored = _restore(autoencoder, degraded, device)
            gan_restored = _restore(gan_generator, degraded, device)

            col_base = ri * 4
            panels = [
                (degraded,      f"Degraded ({res}px)"),
                (ae_restored,   "AE Restored"),
                (gan_restored,  "GAN Restored"),
                (plate_resized, "Original"),
            ]
            for ci, (img, title) in enumerate(panels):
                ax = axes[row, col_base + ci]
                ax.imshow(img)
                ax.axis("off")
                if row == 0:
                    fw = "bold" if ci in (1, 2) else "normal"
                    color = COLORS["autoencoder"] if ci == 1 else \
                            COLORS["gan"] if ci == 2 else "black"
                    ax.set_title(title, fontsize=9, fontweight=fw, color=color)

    fig.suptitle("GAN vs Autoencoder Plate Restoration Comparison",
                 fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "fig11_gan_vs_ae_gallery.png"))
    plt.close()
    print("  ✓ fig11_gan_vs_ae_gallery.png")


# ══════════════════════════════════════════════════════════════════════
# FIGURE 12 — GAN Training Curves
# ══════════════════════════════════════════════════════════════════════
def fig12_gan_training_curves(gan_history_path, save_dir):
    """6-panel GAN training history: G/D losses, Val PSNR, component losses."""
    if not gan_history_path or not os.path.exists(gan_history_path):
        print("  ✗ Skipping fig12: GAN history file not found")
        return

    with open(gan_history_path, "r") as f:
        history = json.load(f)

    fig, axes = plt.subplots(2, 3, figsize=(18, 9))

    plot_configs = [
        ("g_loss",   "Generator Total Loss",   "#2ecc71", axes[0, 0]),
        ("d_loss",   "Discriminator Loss",      "#e74c3c", axes[0, 1]),
        ("val_psnr", "Validation PSNR (dB)",    "#3498db", axes[0, 2]),
        ("g_pixel",  "G Pixel Loss (L1)",       "#f39c12", axes[1, 0]),
        ("g_vgg",    "G VGG Perceptual Loss",   "#9b59b6", axes[1, 1]),
        ("g_adv",    "G Adversarial Loss",      "#1abc9c", axes[1, 2]),
    ]

    for key, title, color, ax in plot_configs:
        data = history.get(key, [])
        if not data:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    transform=ax.transAxes, fontsize=12, color="gray")
            ax.set_title(title, fontweight="bold")
            continue

        ax.plot(data, color=color, alpha=0.3, linewidth=0.8)
        window = min(10, len(data))
        if window > 1:
            smoothed = np.convolve(data, np.ones(window) / window, mode="valid")
            ax.plot(range(window - 1, len(data)), smoothed,
                    color=color, linewidth=2)
        ax.set_title(title, fontweight="bold")
        ax.set_xlabel("Epoch")
        ax.grid(True, alpha=0.3)

    # Add best PSNR annotation
    best_psnr = history.get("best_val_psnr", None)
    if best_psnr:
        axes[0, 2].axhline(y=best_psnr, color="#3498db", linestyle="--",
                            alpha=0.5, linewidth=1)
        axes[0, 2].text(0.02, 0.95, f"Best: {best_psnr:.2f} dB",
                        transform=axes[0, 2].transAxes, fontsize=10,
                        verticalalignment="top", color="#3498db",
                        fontweight="bold")

    fig.suptitle("Plate Restoration GAN — Training History",
                 fontsize=16, fontweight="bold")
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "fig12_gan_training_curves.png"))
    plt.close()
    print("  ✓ fig12_gan_training_curves.png")


# ══════════════════════════════════════════════════════════════════════
# FIGURE 13 — Experiment Version Comparison (v2 vs v3)
# ══════════════════════════════════════════════════════════════════════
def fig13_version_comparison(data_v2, data_v3, save_dir):
    """Compare v2 (AE only) vs v3 (GAN) experiment results side by side."""
    if not data_v2 or not data_v3:
        print("  ✗ Skipping fig13: Need both v2 and v3 results")
        return

    deg_types = ["bicubic_downsample", "gaussian_blur", "jpeg_compression", "combined"]
    fig, axes = plt.subplots(2, 2, figsize=(14, 10), sharey=True)
    axes = axes.ravel()

    for ax, deg in zip(axes, deg_types):
        # Extract resolution→mAP for autoencoder condition from both versions
        for version_data, version_label, color, marker, ls in [
            (data_v2, "v2 (AE)", "#2ecc71", "D", "--"),
            (data_v3, "v3 (GAN)", "#9b59b6", "^", "-"),
        ]:
            resolutions, maps = [], []
            for key, val in sorted(version_data.items()):
                if key.startswith(deg + "_"):
                    res = int(key.split("_")[-1])
                    resolutions.append(res)
                    maps.append(val.get("autoencoder", {}).get("mAP", 0))
            if resolutions:
                ax.plot(resolutions, maps, color=color, marker=marker,
                        linewidth=2, markersize=7, linestyle=ls,
                        label=f"{version_label}")

        # Also plot shared baseline for reference
        resolutions, maps = [], []
        for key, val in sorted(data_v3.items()):
            if key.startswith(deg + "_"):
                res = int(key.split("_")[-1])
                resolutions.append(res)
                maps.append(val.get("baseline", {}).get("mAP", 0))
        if resolutions:
            ax.plot(resolutions, maps, color=COLORS["baseline"], marker="o",
                    linewidth=1.5, markersize=5, alpha=0.5, linestyle=":",
                    label="Baseline (shared)")

        ax.set_title(DEG_LABELS[deg], fontweight="bold")
        ax.set_xlabel("Resolution (px)")
        ax.set_ylabel("mAP")
        ax.set_ylim(-0.02, 1.0)
        ax.invert_xaxis()

    axes[0].legend(loc="lower left", framealpha=0.9)
    fig.suptitle("Experiment Comparison: Autoencoder (v2) vs GAN (v3)",
                 fontsize=15, fontweight="bold", y=1.01)
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "fig13_version_comparison.png"))
    plt.close()
    print("  ✓ fig13_version_comparison.png")


# ══════════════════════════════════════════════════════════════════════
# FIGURE 14 — OCR Accuracy: AE vs GAN Before & After
# ══════════════════════════════════════════════════════════════════════
def fig14_gan_ocr_comparison(plate_dir, autoencoder, gan_generator, device, save_dir):
    """Show OCR output for heavily degraded plates: AE vs GAN restored."""
    from utils.degradation import ImageDegrader
    try:
        from utils.ocr_utils import create_ocr_engine, run_ocr_with_preprocessing
    except ImportError:
        print("  ✗ Skipping fig14: ocr_utils not available")
        return

    degrader = ImageDegrader(base_resolution=256)
    plates = list(Path(plate_dir).rglob("*.jpg")) + list(Path(plate_dir).rglob("*.png"))
    plates = sorted(plates)[:4]
    if not plates:
        print("  ✗ Skipping fig14: no plate crops found")
        return

    try:
        ocr_engine = create_ocr_engine(
            languages=["en", "pt"], gpu=(device != "cpu")
        )
    except Exception:
        print("  ✗ Skipping fig14: Could not load OCR engine")
        return

    def _restore(model, img, dev):
        inp = torch.from_numpy(img).permute(2, 0, 1).float() / 255.0
        inp = (inp - 0.5) / 0.5
        inp = inp.unsqueeze(0).to(dev)
        with torch.no_grad():
            out = model(inp)
            if isinstance(out, tuple):
                out = out[0]
        result = out.squeeze(0).permute(1, 2, 0).cpu().numpy()
        return ((result * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8)

    def _ocr(img):
        text, conf = run_ocr_with_preprocessing(
            ocr_engine, img, allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        )
        return text if text else "[FAILED]"

    n = len(plates)
    fig, axes = plt.subplots(n, 3, figsize=(13, 2.8 * n))
    if n == 1:
        axes = axes[np.newaxis, :]

    for row, plate_path in enumerate(plates):
        plate = cv2.imread(str(plate_path))
        plate = cv2.cvtColor(plate, cv2.COLOR_BGR2RGB)
        plate_resized = cv2.resize(plate, (256, 128))

        degraded = degrader.combined_degradation(plate_resized, target_resolution=64)
        degraded_up = cv2.resize(degraded, (256, 128), interpolation=cv2.INTER_CUBIC)

        ae_restored = _restore(autoencoder, degraded_up, device)
        gan_restored = _restore(gan_generator, degraded_up, device)

        bl_text = _ocr(degraded_up)
        ae_text = _ocr(ae_restored)
        gan_text = _ocr(gan_restored)

        panels = [
            (degraded_up, f"Degraded\nOCR: '{bl_text}'", "#c0392b"),
            (ae_restored, f"AE Restored\nOCR: '{ae_text}'", "#27ae60"),
            (gan_restored, f"GAN Restored\nOCR: '{gan_text}'", "#8e44ad"),
        ]
        for ci, (img, title, color) in enumerate(panels):
            ax = axes[row, ci]
            ax.imshow(img)
            ax.axis("off")
            ax.set_title(title, color=color, fontweight="bold", fontsize=10)

    fig.suptitle("OCR Recovery: Degraded → AE → GAN Restoration",
                 fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "fig14_gan_ocr_comparison.png"))
    plt.close()
    print("  ✓ fig14_gan_ocr_comparison.png")


# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════
def _load_model(weights_path, config, device):
    """Load a UNetAutoencoder from weights file."""
    from models.autoencoder import UNetAutoencoder
    ae_cfg = config["autoencoder"]
    model = UNetAutoencoder(
        in_channels=3,
        base_features=ae_cfg["encoder_channels"][0],
        depth=len(ae_cfg["encoder_channels"]),
    )
    state_dict = torch.load(weights_path, map_location=device)
    if any(k.startswith("module.") for k in state_dict):
        state_dict = {k[len("module."):]: v for k, v in state_dict.items()}
    model.load_state_dict(state_dict)
    return model.to(device).eval()


def main():
    parser = argparse.ArgumentParser(description="Generate paper figures")
    parser.add_argument("--results", default="results/experiment/experiment_results.json",
                        help="Primary experiment results JSON (latest version)")
    parser.add_argument("--results-v2", default=None,
                        help="Previous experiment results for v2-vs-v3 comparison")
    parser.add_argument("--dqn-history", default="results/dqn/dqn_training_history.json")
    parser.add_argument("--autoencoder-weights", default=None)
    parser.add_argument("--gan-weights", default=None,
                        help="GAN generator weights for comparison figures")
    parser.add_argument("--gan-history", default=None,
                        help="GAN training history JSON for training curves")
    parser.add_argument("--detector-weights", default=None)
    parser.add_argument("--test-dir", default="data/ufpr_yolo/test")
    parser.add_argument("--plate-dir", default="data/plates/test")
    parser.add_argument("--output-dir", default="results/figures")
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    print("=" * 60)
    print("Generating Publication Figures")
    print("=" * 60)

    # ── 1. Experiment result stat plots ───────────────────────────────
    data = None
    if os.path.exists(args.results):
        with open(args.results) as f:
            data = json.load(f)
        print(f"\nLoaded results: {len(data)} conditions from {args.results}")

        fig1_resolution_curves(data, args.output_dir)
        fig3_heatmap(data, args.output_dir)
        fig4_quality_accuracy(data, args.output_dir)
        fig5_improvement_bars(data, args.output_dir)
    else:
        print(f"\n  ✗ Skipping results plots: {args.results} not found")

    # ── 2. DQN plots ─────────────────────────────────────────────────
    fig8_dqn_training_curves(args.dqn_history, args.output_dir)
    fig9_dqn_action_dist(args.dqn_history, args.output_dir)

    # ── 3. Simple image visualizers ──────────────────────────────────
    fig6_degradation_strip(args.test_dir, args.output_dir)

    # ── 4. Load models for neural network figures ────────────────────
    from utils.device import resolve_device
    from utils.data_loader import load_config
    device = resolve_device(args.device)
    config = load_config("configs/config.yaml")

    autoencoder = None
    if args.autoencoder_weights and os.path.exists(args.autoencoder_weights):
        autoencoder = _load_model(args.autoencoder_weights, config, device)
        print(f"\n  Loaded autoencoder from {args.autoencoder_weights}")

        fig2_reconstruction_gallery(args.plate_dir, autoencoder, device, args.output_dir)
        fig10_before_after_ocr(args.plate_dir, autoencoder, device, args.output_dir)
    else:
        print("\n  ✗ Skipping fig2/fig10: no autoencoder weights provided")

    # ── 5. GAN-specific figures ──────────────────────────────────────
    gan_generator = None
    if args.gan_weights and os.path.exists(args.gan_weights):
        gan_generator = _load_model(args.gan_weights, config, device)
        print(f"  Loaded GAN generator from {args.gan_weights}")

    # Fig 11: GAN vs AE reconstruction gallery
    if autoencoder is not None and gan_generator is not None:
        fig11_gan_vs_ae_gallery(
            args.plate_dir, autoencoder, gan_generator, device, args.output_dir
        )
        fig14_gan_ocr_comparison(
            args.plate_dir, autoencoder, gan_generator, device, args.output_dir
        )
    else:
        print("  ✗ Skipping fig11/fig14: need both AE and GAN weights")

    # Fig 12: GAN training curves
    gan_hist = args.gan_history
    if not gan_hist:
        # Auto-detect common paths
        for candidate in [
            "results/autoencoder/gan/gan_training_results.json",
            "results/gan/gan_training_results.json",
        ]:
            if os.path.exists(candidate):
                gan_hist = candidate
                break
    fig12_gan_training_curves(gan_hist, args.output_dir)

    # ── 6. Version comparison (v2 vs v3) ─────────────────────────────
    data_v2 = None
    v2_path = args.results_v2
    if not v2_path:
        # Auto-detect v2 results
        for candidate in [
            "results/experiment_v2/experiment_results.json",
            "results/experiment/experiment_results.json",
        ]:
            if os.path.exists(candidate) and candidate != args.results:
                v2_path = candidate
                break
    if v2_path and os.path.exists(v2_path):
        with open(v2_path) as f:
            data_v2 = json.load(f)
        print(f"  Loaded v2 results from {v2_path}")

    if data_v2 and data:
        fig13_version_comparison(data_v2, data, args.output_dir)
    else:
        print("  ✗ Skipping fig13: need both v2 and v3 results for comparison")

    # ── 7. Detection comparison ──────────────────────────────────────
    if args.detector_weights and os.path.exists(args.detector_weights):
        from models.detector import PlateDetector
        detector = PlateDetector(
            model_path=args.detector_weights,
            confidence=0.3,
            device="cpu",
        )
        fig7_detection_comparison(args.test_dir, detector, args.output_dir)
    else:
        print("  ✗ Skipping fig7: no detector weights provided")

    print(f"\n{'=' * 60}")
    print(f"All figures saved to {args.output_dir}/")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()