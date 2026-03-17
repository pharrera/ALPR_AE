"""
Train the DQN restoration agent.

The agent learns to choose the best restoration strategy (pass-through,
bicubic upscale, or autoencoder restoration) for each plate crop based
on its degradation level.  Training simulates degraded plate images at
random resolutions, applies the agent's action, and rewards higher
detection confidence and OCR accuracy.

Usage:
    python train_dqn.py \
        --autoencoder-weights results/autoencoder/unet/best_autoencoder.pth \
        --detector-weights results/detection/plate_detection/weights/best.pt \
        --plate-dir data/plates/train \
        --episodes 500 \
        --output-dir results/dqn
"""

import argparse
import os
import json
import random
import cv2
import numpy as np
import torch
from tqdm import tqdm
from pathlib import Path

from utils.data_loader import load_config
from utils.device import resolve_device
from utils.degradation import ImageDegrader, compute_image_quality_metrics
from utils.ufpr_data_loader import compute_plate_accuracy
from models.autoencoder import UNetAutoencoder
from models.dqn_agent import DQNRestorationAgent


def compute_reward(
    original: np.ndarray,
    restored: np.ndarray,
    action: int,
    ocr_engine=None,
    gt_text: str = "",
) -> float:
    """
    Compute reward for a restoration action.

    If ocr_engine and gt_text are provided, reward is based on TRUE OCR
    accuracy against verified ground truth (UFPR-ALPR). Otherwise falls
    back to PSNR-based image quality reward.

    Args:
        original: Clean plate crop (ground truth image)
        restored: Plate crop after applying the agent's action
        action: The action taken (0=pass, 1=upscale, 2=autoencoder)
        ocr_engine: Optional EasyOCR reader for OCR-based reward
        gt_text: Verified ground truth plate text (e.g. 'MLS5511')

    Returns:
        Scalar reward value
    """
    reward = 0.0

    # OCR-based reward (preferred — uses true ground truth)
    if ocr_engine is not None and gt_text:
        results = ocr_engine.readtext(restored)
        predicted = "".join([r[1] for r in results]).upper()
        ocr_accuracy = compute_plate_accuracy(predicted, gt_text)
        reward = ocr_accuracy  # [0, 1] range
    else:
        # Fallback: PSNR-based reward
        if restored.shape[:2] != original.shape[:2]:
            restored = cv2.resize(restored, (original.shape[1], original.shape[0]))

        mse = np.mean((original.astype(float) - restored.astype(float)) ** 2)
        if mse == 0:
            psnr = 50.0
        else:
            psnr = min(50.0, 10 * np.log10(255.0 ** 2 / mse))
        reward = psnr / 50.0

    # Small cost for more expensive actions (encourages efficiency)
    action_cost = {0: 0.0, 1: 0.01, 2: 0.03}
    reward -= action_cost.get(action, 0)

    return reward


def load_plate_images(plate_dir: str, max_images: int = 2000,
                      plate_gt: dict = None) -> list:
    """
    Load plate crop images for training.

    Returns list of (image, gt_text) tuples. gt_text is '' if no GT available.
    """
    paths = sorted(
        p for p in Path(plate_dir).glob("*")
        if p.suffix.lower() in (".jpg", ".jpeg", ".png")
    )[:max_images]
    samples = []
    for p in paths:
        img = cv2.imread(str(p))
        if img is not None:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            # Try to find GT text: plate crops are named like track0091_01_plate0.jpg
            # The original image was track0091_01.png → key "train/images/track0091_01.png"
            gt_text = ""
            if plate_gt:
                # Strip _plateN suffix to recover original image stem
                stem = p.stem
                if "_plate" in stem:
                    stem = stem[:stem.rindex("_plate")]
                # Try all splits
                for split in ["train", "valid", "test"]:
                    key = f"{split}/images/{stem}.png"
                    if key in plate_gt:
                        gt_text = plate_gt[key]
                        break
            samples.append((img, gt_text))
    n_with_gt = sum(1 for _, t in samples if t)
    print(f"Loaded {len(samples)} plate crops from {plate_dir} "
          f"({n_with_gt} with verified GT text)")
    return samples


def main():
    parser = argparse.ArgumentParser(description="Train DQN restoration agent")
    parser.add_argument("--autoencoder-weights", required=True)
    parser.add_argument("--detector-weights", default=None,
                        help="Optional detector weights for confidence-based reward")
    parser.add_argument("--plate-dir", default="data/plates/train")
    parser.add_argument("--config", default="configs/config.yaml")
    parser.add_argument("--episodes", type=int, default=500)
    parser.add_argument("--steps-per-episode", type=int, default=50)
    parser.add_argument("--output-dir", default="results/dqn")
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    config = load_config(args.config)
    device = resolve_device(args.device)
    print(f"Device: {device}")

    # Load autoencoder
    print("Loading autoencoder...")
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
    autoencoder.eval()

    # Create DQN agent
    print("Creating DQN agent...")
    agent = DQNRestorationAgent(
        autoencoder=autoencoder,
        device=device,
        lr=1e-3,
        gamma=0.95,
        epsilon_start=1.0,
        epsilon_end=0.05,
        epsilon_decay=args.episodes * args.steps_per_episode // 4,
        buffer_size=20_000,
        batch_size=64,
        target_update=50,
    )

    # Load ground truth plate text (UFPR-ALPR)
    plate_gt = {}
    plate_gt_path = config.get("data", {}).get("plate_gt_path", None)
    if plate_gt_path and os.path.exists(plate_gt_path):
        with open(plate_gt_path) as f:
            plate_gt = json.load(f)
        print(f"Loaded {len(plate_gt)} verified plate text entries")

    # Optional: load EasyOCR for OCR-based reward
    ocr_engine = None
    if plate_gt:
        try:
            import easyocr
            ocr_engine = easyocr.Reader(["en"], gpu=(device == "cuda"))
            print("EasyOCR loaded — using true OCR accuracy for reward")
        except ImportError:
            print("EasyOCR not available — falling back to PSNR-based reward")

    # Load training plates
    plates = load_plate_images(args.plate_dir, plate_gt=plate_gt)
    if not plates:
        print("ERROR: No plate images found. Run extract_plates.py first.")
        return

    # Degradation engine
    degrader = ImageDegrader(base_resolution=256, seed=42)
    resolution_scales = [1.0, 0.75, 0.5, 0.375, 0.25, 0.125]

    # Training loop
    print(f"\nTraining DQN for {args.episodes} episodes "
          f"× {args.steps_per_episode} steps...")
    print("=" * 60)

    episode_rewards = []
    action_counts = [0, 0, 0]

    for episode in tqdm(range(args.episodes), desc="Training DQN"):
        episode_reward = 0.0
        episode_loss = 0.0
        n_losses = 0

        for step in range(args.steps_per_episode):
            # Sample a random plate and degradation level
            original, gt_text = random.choice(plates)
            original_resized = cv2.resize(original, (256, 128))
            scale = random.choice(resolution_scales)
            target_res = int(256 * scale)

            # Degrade the plate
            if scale < 1.0:
                # Random degradation type
                deg_type = random.choice(["bicubic", "blur", "combined"])
                if deg_type == "bicubic":
                    degraded = degrader.bicubic_downsample(
                        original_resized, target_res, upscale_back=True
                    )
                elif deg_type == "blur":
                    k = max(3, int(3 / scale))
                    if k % 2 == 0:
                        k += 1
                    degraded = degrader.gaussian_blur(original_resized, kernel_size=k)
                else:
                    degraded = degrader.combined_degradation(
                        original_resized, target_res
                    )
            else:
                degraded = original_resized.copy()

            # Get state
            features, quality = agent.get_state(degraded, scale)

            # Select action
            action = agent.select_action(features, quality)
            action_counts[action] += 1

            # Apply action
            restored = agent.apply_action(degraded, action)

            # Compute reward (OCR-based if GT available, else PSNR-based)
            reward = compute_reward(
                original_resized, restored, action,
                ocr_engine=ocr_engine, gt_text=gt_text,
            )
            episode_reward += reward

            # Next state (after action)
            next_features, next_quality = agent.get_state(restored, scale)

            # Store combined state in replay buffer
            feat_dim = agent.feature_extractor.feature_dim
            state_combined = torch.cat([features, quality])
            next_combined = torch.cat([next_features, next_quality])

            agent.replay_buffer.push(
                state_combined, action, reward, next_combined, done=True
            )

            # Train
            loss = agent.train_step()
            if loss is not None:
                episode_loss += loss
                n_losses += 1

            agent.steps_done += 1

        # Update target network periodically
        if (episode + 1) % agent.target_update == 0:
            agent.update_target_network()

        avg_reward = episode_reward / args.steps_per_episode
        avg_loss = episode_loss / max(n_losses, 1)
        episode_rewards.append(avg_reward)

        agent.training_history["reward"].append(avg_reward)
        agent.training_history["loss"].append(avg_loss)
        agent.training_history["epsilon"].append(agent.epsilon)

        if (episode + 1) % 50 == 0:
            total_actions = sum(action_counts)
            pcts = [c / total_actions * 100 for c in action_counts]
            tqdm.write(
                f"  Ep {episode+1:4d} | reward={avg_reward:.4f} | "
                f"loss={avg_loss:.4f} | ε={agent.epsilon:.3f} | "
                f"actions: pass={pcts[0]:.0f}% up={pcts[1]:.0f}% ae={pcts[2]:.0f}%"
            )

    # Save agent
    agent.save(os.path.join(args.output_dir, "dqn_agent.pth"))

    # Save training history
    history_path = os.path.join(args.output_dir, "dqn_training_history.json")
    with open(history_path, "w") as f:
        json.dump(agent.training_history, f, indent=2)
    print(f"Training history saved to {history_path}")

    # Generate training plot
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 4))

    ax1.plot(agent.training_history["reward"], color="#2ecc71", alpha=0.3)
    # Smoothed
    window = min(20, len(agent.training_history["reward"]))
    if window > 1:
        smoothed = np.convolve(
            agent.training_history["reward"],
            np.ones(window) / window, mode="valid"
        )
        ax1.plot(range(window - 1, len(agent.training_history["reward"])),
                 smoothed, color="#2ecc71", linewidth=2)
    ax1.set_xlabel("Episode")
    ax1.set_ylabel("Avg Reward")
    ax1.set_title("Episode Reward")
    ax1.grid(True, alpha=0.3)

    ax2.plot(agent.training_history["loss"], color="#e74c3c", alpha=0.3)
    if window > 1:
        smoothed_loss = np.convolve(
            agent.training_history["loss"],
            np.ones(window) / window, mode="valid"
        )
        ax2.plot(range(window - 1, len(agent.training_history["loss"])),
                 smoothed_loss, color="#e74c3c", linewidth=2)
    ax2.set_xlabel("Episode")
    ax2.set_ylabel("Loss")
    ax2.set_title("Training Loss")
    ax2.grid(True, alpha=0.3)

    ax3.plot(agent.training_history["epsilon"], color="#3498db", linewidth=2)
    ax3.set_xlabel("Episode")
    ax3.set_ylabel("Epsilon")
    ax3.set_title("Exploration Rate")
    ax3.grid(True, alpha=0.3)

    plt.suptitle("DQN Restoration Agent Training", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(os.path.join(args.output_dir, "dqn_training.png"), dpi=150)
    plt.close()

    # Print final action distribution
    total_actions = sum(action_counts)
    print(f"\nFinal action distribution:")
    for i, name in enumerate(DQNRestorationAgent.ACTION_NAMES):
        print(f"  {name}: {action_counts[i]} ({action_counts[i]/total_actions*100:.1f}%)")
    print("\nDQN training complete!")


if __name__ == "__main__":
    main()
