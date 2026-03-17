"""
Train the convolutional autoencoder for plate image restoration.

Usage:
    python train_autoencoder.py --plate-dir data/plates --device cuda
    python train_autoencoder.py --plate-dir data/plates --model unet --epochs 150

Dual-GPU (Kaggle T4 x2):
    Batch size is automatically doubled when 2 GPUs are detected.
    DataParallel splits each batch across both GPUs in parallel.
    Saved weights are always unwrapped so they load on any device.
"""

import argparse
import os
import json
import numpy as np
import cv2
import torch
import torch.nn as nn

from utils.data_loader import load_config, PlateImageDataset
from utils.device import resolve_device, use_pinned_memory
from utils.degradation import ImageDegrader
from utils.visualization import plot_training_history, plot_reconstruction_samples
from models.autoencoder import (
    ConvAutoencoder,
    UNetAutoencoder,
    AutoencoderTrainer,
)
from torch.utils.data import DataLoader, random_split


def main():
    parser = argparse.ArgumentParser(description="Train plate autoencoder")
    parser.add_argument("--config", default="configs/config.yaml")
    parser.add_argument(
        "--model", choices=["conv", "unet"], default="unet",
        help="Autoencoder architecture",
    )
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument(
        "--device", default=None,
        help="Device: auto, cuda, mps, or cpu",
    )
    parser.add_argument(
        "--plate-dir", default="data/plates",
        help="Directory with cropped plate images (output of extract_plates.py). "
             "Run extract_plates.py first if this directory doesn't exist.",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    ae_config = config["autoencoder"]

    device = resolve_device(args.device)
    pin_memory = use_pinned_memory(device)

    # --- Detect how many GPUs are available ---
    num_gpus = torch.cuda.device_count() if device == "cuda" else 0
    use_multi_gpu = num_gpus > 1

    # Scale batch size with GPU count so each GPU gets the configured batch
    base_batch = args.batch_size or ae_config["batch_size"]
    batch_size = base_batch * num_gpus if use_multi_gpu else base_batch
    epochs = args.epochs or ae_config["epochs"]

    print(f"Device        : {device}")
    print(f"GPUs available: {num_gpus}  {'(DataParallel enabled)' if use_multi_gpu else ''}")
    print(f"Architecture  : {args.model}")
    print(f"Batch size    : {batch_size} ({base_batch} x {num_gpus} GPUs)" if use_multi_gpu else f"Batch size    : {batch_size}")
    print(f"Epochs        : {epochs}")

    # --- Degradation function for training pairs ---
    def train_degradation(image):
        """Random mix of downsample + noise + JPEG compression."""
        h, w = image.shape[:2]
        factor = np.random.choice([2, 3, 4, 6, 8, 10, 12, 16])
        small = cv2.resize(
            image, (max(w // factor, 8), max(h // factor, 8)),
            interpolation=cv2.INTER_AREA,
        )
        degraded = cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)

        if np.random.random() > 0.5:
            noise = np.random.normal(0, np.random.uniform(5, 25), degraded.shape)
            degraded = np.clip(degraded.astype(float) + noise, 0, 255).astype(np.uint8)

        if np.random.random() > 0.5:
            quality = np.random.randint(20, 80)
            _, encoded = cv2.imencode(".jpg", degraded, [cv2.IMWRITE_JPEG_QUALITY, quality])
            degraded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)

        # Random blur
        if np.random.random() > 0.6:
            k = np.random.choice([3, 5, 7])
            degraded = cv2.GaussianBlur(degraded, (k, k), 0)

        return degraded

    # --- Dataset ---
    dataset = PlateImageDataset(
        root_dir=args.plate_dir,
        img_height=ae_config["input_size"],
        img_width=ae_config["input_width"],
        degradation_fn=train_degradation,
    )

    if len(dataset) == 0:
        raise ValueError(
            f"No plate images found in '{args.plate_dir}'.\n"
            "Run extract_plates.py first:\n"
            "  python extract_plates.py --data-dir data --output-dir data/plates"
        )

    n_val = max(1, int(len(dataset) * 0.2))
    n_train = len(dataset) - n_val
    train_ds, val_ds = random_split(
        dataset, [n_train, n_val],
        generator=torch.Generator().manual_seed(config["project"]["seed"]),
    )

    # More workers when multi-GPU to keep the pipeline fed
    num_workers = min(4 * max(num_gpus, 1), os.cpu_count() or 1)

    train_loader = DataLoader(
        train_ds, batch_size=batch_size, shuffle=True,
        num_workers=num_workers, pin_memory=pin_memory, drop_last=True,
    )
    val_loader = DataLoader(
        val_ds, batch_size=batch_size, shuffle=False,
        num_workers=num_workers, pin_memory=pin_memory,
    )

    print(f"Train samples : {n_train}  |  Val samples: {n_val}")

    # --- Build model (ONCE) ---
    if args.model == "unet":
        base_model = UNetAutoencoder(
            in_channels=3,
            base_features=ae_config["encoder_channels"][0],
            depth=len(ae_config["encoder_channels"]),
        )
    else:
        base_model = ConvAutoencoder(
            in_channels=3,
            encoder_channels=ae_config["encoder_channels"],
            latent_dim=ae_config["latent_dim"],
            input_height=ae_config["input_size"],
            input_width=ae_config["input_width"],
        )

    total_params = sum(p.numel() for p in base_model.parameters())
    print(f"Model params  : {total_params:,}")

    # --- Wrap with DataParallel for dual-GPU ---
    # base_model is kept as a reference so we can unwrap weights for saving
    if use_multi_gpu:
        print(f"Wrapping model with DataParallel across {num_gpus} GPUs")
        model = nn.DataParallel(base_model)
    else:
        model = base_model

    # --- Train ---
    trainer = AutoencoderTrainer(
        model=model,
        device=device,
        learning_rate=ae_config["learning_rate"],
        weight_decay=ae_config["weight_decay"],
        loss_type=ae_config["loss"],
        ssim_weight=ae_config["ssim_weight"],
        perceptual_weight=ae_config.get("perceptual_weight", 0.1),
        scheduler_T_max=ae_config.get("scheduler_T_max", 50),
    )

    save_dir = f"results/autoencoder/{args.model}"
    os.makedirs(save_dir, exist_ok=True)

    print("\n" + "=" * 60)
    print(f"TRAINING {args.model.upper()} AUTOENCODER")
    print("=" * 60)

    history = trainer.train(
        train_loader, val_loader, epochs=epochs, save_dir=save_dir,
    )

    # --- Save unwrapped weights so they load cleanly on any device ---
    # DataParallel stores the real model under .module; unwrap before saving
    unwrapped = model.module if use_multi_gpu else model
    torch.save(
        unwrapped.state_dict(),
        os.path.join(save_dir, "best_autoencoder_unwrapped.pth"),
    )
    print("Saved unwrapped weights -> best_autoencoder_unwrapped.pth")

    # --- Plots ---
    plot_training_history(
        history,
        save_path=os.path.join(save_dir, "training_history.png"),
        title=f"{args.model.upper()} Autoencoder Training",
    )

    # --- Sample reconstructions ---
    unwrapped.eval()
    with torch.no_grad():
        degraded_samples, reconstructed_samples, clean_samples = [], [], []

        for degraded, clean in val_loader:
            degraded = degraded.to(device)
            output = unwrapped(degraded)   # use unwrapped for inference
            if isinstance(output, tuple):
                output = output[0]

            for i in range(min(4, degraded.size(0))):
                def _to_img(t):
                    arr = t.cpu().permute(1, 2, 0).numpy()
                    return ((arr * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8)

                degraded_samples.append(_to_img(degraded[i]))
                reconstructed_samples.append(_to_img(output[i]))
                clean_samples.append(_to_img(clean[i]))
            break

        if degraded_samples:
            plot_reconstruction_samples(
                degraded_samples, reconstructed_samples, clean_samples,
                save_path=os.path.join(save_dir, "reconstruction_samples.png"),
            )

    # --- Save JSON results ---
    with open(os.path.join(save_dir, "training_results.json"), "w") as f:
        json.dump(history, f, indent=2)

    print(f"\nBest val loss : {history['best_val_loss']:.6f}")
    print(f"Results saved : {save_dir}")
    print("Training complete!")


if __name__ == "__main__":
    main()
