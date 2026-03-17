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

Usage:
    python generate_figures.py \
        --results results/experiment/experiment_results.json \
        --dqn-history results/dqn/dqn_training_history.json \
        --autoencoder-weights results/autoencoder/unet/best_autoencoder.pth \
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
        import easyocr
        reader = easyocr.Reader(['en'], gpu=(device != "cpu"))
    except ImportError:
        print("  ✗ Skipping fig10: EasyOCR not installed")
        return

    degrader = ImageDegrader(base_resolution=256)
    plates = list(Path(plate_dir).rglob("*.jpg")) + list(Path(plate_dir).rglob("*.png"))
    plates = sorted(plates)[:4]
    
    if not plates:
        print("  ✗ Skipping fig10: no plate crops found")
        return

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
        bl_result = reader.readtext(degraded_up, detail=0)
        bl_text = bl_result[0] if bl_result else "[FAILED]"

        # Autoencoder Restore
        inp = torch.from_numpy(degraded_up).permute(2, 0, 1).float() / 255.0
        inp = (inp - 0.5) / 0.5  # Normalize to [-1, 1]
        inp = inp.unsqueeze(0).to(device)
        with torch.no_grad():
            out = autoencoder(inp)
        restored = out.squeeze(0).permute(1, 2, 0).cpu().numpy()
        restored = ((restored * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8)

        # AE OCR (After)
        ae_result = reader.readtext(restored, detail=0)
        ae_text = ae_result[0] if ae_result else "[FAILED]"

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
# MAIN
# ══════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="Generate paper figures")
    parser.add_argument("--results", default="results/experiment/experiment_results.json")
    parser.add_argument("--dqn-history", default="results/dqn/dqn_training_history.json")
    parser.add_argument("--autoencoder-weights", default=None)
    parser.add_argument("--detector-weights", default=None)
    parser.add_argument("--test-dir", default="data/ufpr_yolo/test")
    parser.add_argument("--plate-dir", default="data/plates/test")
    parser.add_argument("--output-dir", default="results/figures")
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # 1. Load experiment results
    if os.path.exists(args.results):
        with open(args.results) as f:
            data = json.load(f)
        print(f"Loaded results: {len(data)} conditions")
        
        # Stat Plots
        fig1_resolution_curves(data, args.output_dir)
        fig3_heatmap(data, args.output_dir)
        fig4_quality_accuracy(data, args.output_dir)
        fig5_improvement_bars(data, args.output_dir)
    else:
        print(f"  ✗ Skipping results plots: {args.results} not found")

    # 2. DQN Plots
    fig8_dqn_training_curves(args.dqn_history, args.output_dir)
    fig9_dqn_action_dist(args.dqn_history, args.output_dir)

    # 3. Simple Image visualizers
    fig6_degradation_strip(args.test_dir, args.output_dir)

    # 4. Neural Network Image Visualizers (Require loading models)
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
        fig10_before_after_ocr(args.plate_dir, autoencoder, device, args.output_dir)
    else:
        print("  ✗ Skipping fig2 and fig10: no autoencoder weights provided")

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

    print(f"\nAll figures saved to {args.output_dir}/")


if __name__ == "__main__":
    main()