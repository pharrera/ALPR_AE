"""
GAN-based training for license plate image restoration.

Upgrades the U-Net autoencoder (generator) with adversarial training
using a PatchGAN discriminator. The generator learns to produce
perceptually realistic plate restorations rather than just minimising
pixel-level reconstruction error.

Architecture:
  Generator:   UNetAutoencoder (existing, unchanged)
               MSE + SSIM + VGG perceptual loss  (pixel-level quality)
               + Adversarial loss                (perceptual realism)
  Discriminator: MultiScaleDiscriminator         (PatchGAN × 2 scales)
               LSGAN objective for stability

Loss breakdown for generator:
  L_G = λ_pixel * (MSE + SSIM) + λ_vgg * L_perceptual + λ_adv * L_adv

Recommended: Start with a pre-trained autoencoder (--pretrained-weights)
and fine-tune with GAN loss. This avoids early training instability
where the discriminator collapses before the generator learns anything.

Usage:
    # Fine-tune from existing autoencoder weights:
    python train_gan.py \\
        --plate-dir data/plates/train \\
        --pretrained-weights results/autoencoder/unet/best_autoencoder.pth \\
        --epochs 100 --batch-size 16 --device cuda

    # Train from scratch:
    python train_gan.py \\
        --plate-dir data/plates/train \\
        --epochs 150 --batch-size 16 --device cuda
"""

import argparse
import os
import json
import numpy as np
import cv2
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, random_split
from tqdm import tqdm
from pathlib import Path

from utils.data_loader import load_config, PlateImageDataset
from utils.device import resolve_device, use_pinned_memory
from utils.visualization import plot_training_history, plot_reconstruction_samples
from models.autoencoder import UNetAutoencoder, VGGPerceptualLoss, SSIMLoss
from models.discriminator import MultiScaleDiscriminator, GANLoss


# =========================================================================
# Degradation (same as train_autoencoder.py)
# =========================================================================

def train_degradation(image: np.ndarray) -> np.ndarray:
    """Random degradation: downsample + noise + JPEG + blur."""
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

    if np.random.random() > 0.6:
        k = np.random.choice([3, 5, 7])
        degraded = cv2.GaussianBlur(degraded, (k, k), 0)

    return degraded


# =========================================================================
# GAN Trainer
# =========================================================================

class GANTrainer:
    """
    Trains generator (U-Net) + discriminator (MultiScalePatchGAN) jointly.

    Training alternates:
      1. Update discriminator: maximise D(real) - D(G(degraded))
      2. Update generator:     minimise pixel loss + perceptual loss + adversarial loss

    Discriminator is updated more frequently early in training to give
    the generator a useful learning signal from the start.
    """

    def __init__(
        self,
        generator: nn.Module,
        discriminator: nn.Module,
        device: str = "cuda",
        lr_g: float = 0.0002,
        lr_d: float = 0.0001,
        lambda_pixel: float = 10.0,
        lambda_vgg: float = 1.0,
        lambda_adv: float = 1.0,
        lambda_ssim: float = 4.0,
        d_steps_per_g: int = 1,
    ):
        self.generator = generator.to(device)
        self.discriminator = discriminator.to(device)
        self.device = device
        self.lambda_pixel = lambda_pixel
        self.lambda_vgg = lambda_vgg
        self.lambda_adv = lambda_adv
        self.lambda_ssim = lambda_ssim
        self.d_steps_per_g = d_steps_per_g

        # Losses
        self.gan_loss = GANLoss(mode="lsgan")
        self.l1_loss = nn.L1Loss()
        self.ssim_loss = SSIMLoss()
        self.perceptual_loss = VGGPerceptualLoss()

        # Optimisers — Adam with β1=0.5 is standard for GANs
        self.opt_g = torch.optim.Adam(
            generator.parameters(), lr=lr_g, betas=(0.5, 0.999)
        )
        self.opt_d = torch.optim.Adam(
            discriminator.parameters(), lr=lr_d, betas=(0.5, 0.999)
        )

        # LR schedulers: linear decay from epoch 50% to 100%
        self.sched_g = None  # set in train()
        self.sched_d = None

        self.history = {
            "g_loss": [], "d_loss": [],
            "g_pixel": [], "g_vgg": [], "g_adv": [],
            "val_psnr": [], "val_loss": [],
        }
        self._snapshot_samples = None  # Fixed samples for reconstruction snapshots

    def _move_perceptual_to_device(self):
        """Ensure VGG perceptual loss is on the right device."""
        if next(self.perceptual_loss.parameters()).device != torch.device(self.device):
            self.perceptual_loss = self.perceptual_loss.to(self.device)

    def train_epoch(self, dataloader) -> dict:
        self.generator.train()
        self.discriminator.train()
        self._move_perceptual_to_device()

        totals = {"g_loss": 0, "d_loss": 0, "g_pixel": 0, "g_vgg": 0, "g_adv": 0}
        n = 0

        for degraded, clean in dataloader:
            degraded = degraded.to(self.device)
            clean = clean.to(self.device)
            batch = degraded.size(0)

            # ── Discriminator update ──────────────────────────────────────
            for _ in range(self.d_steps_per_g):
                self.opt_d.zero_grad()

                # Generate fake plates (no grad for D update)
                with torch.no_grad():
                    fake = self.generator(degraded)
                    if isinstance(fake, tuple):
                        fake = fake[0]

                # D loss: real=1, fake=0
                pred_real = self.discriminator(clean)
                pred_fake = self.discriminator(fake.detach())

                loss_d_real = self.gan_loss(pred_real, is_real=True)
                loss_d_fake = self.gan_loss(pred_fake, is_real=False)
                loss_d = (loss_d_real + loss_d_fake) * 0.5

                loss_d.backward()
                # Gradient clip for D stability
                nn.utils.clip_grad_norm_(self.discriminator.parameters(), 1.0)
                self.opt_d.step()

            # ── Generator update ──────────────────────────────────────────
            self.opt_g.zero_grad()

            fake = self.generator(degraded)
            if isinstance(fake, tuple):
                fake = fake[0]

            # Pixel loss (L1 — sharper than MSE for textures)
            loss_pixel = self.l1_loss(fake, clean)

            # SSIM structural loss
            loss_ssim = self.ssim_loss(fake, clean)

            # VGG perceptual loss
            loss_vgg = self.perceptual_loss(fake, clean)

            # Adversarial loss (generator wants D to output 1 for fakes)
            pred_fake_for_g = self.discriminator(fake)
            loss_adv = self.gan_loss(pred_fake_for_g, is_real=True)

            # Total generator loss
            loss_g = (
                self.lambda_pixel * loss_pixel
                + self.lambda_ssim * loss_ssim
                + self.lambda_vgg * loss_vgg
                + self.lambda_adv * loss_adv
            )

            loss_g.backward()
            nn.utils.clip_grad_norm_(self.generator.parameters(), 1.0)
            self.opt_g.step()

            totals["g_loss"] += loss_g.item() * batch
            totals["d_loss"] += loss_d.item() * batch
            totals["g_pixel"] += loss_pixel.item() * batch
            totals["g_vgg"] += loss_vgg.item() * batch
            totals["g_adv"] += loss_adv.item() * batch
            n += batch

        return {k: v / n for k, v in totals.items()}

    @torch.no_grad()
    def evaluate(self, dataloader) -> dict:
        self.generator.eval()
        total_psnr = 0.0
        total_pixel = 0.0
        n = 0

        for degraded, clean in dataloader:
            degraded = degraded.to(self.device)
            clean = clean.to(self.device)

            fake = self.generator(degraded)
            if isinstance(fake, tuple):
                fake = fake[0]

            loss_pixel = self.l1_loss(fake, clean)
            total_pixel += loss_pixel.item() * degraded.size(0)

            # PSNR (images are in [-1,1], convert to [0,1] for MSE)
            fake_01 = fake * 0.5 + 0.5
            clean_01 = clean * 0.5 + 0.5
            mse = F.mse_loss(fake_01, clean_01, reduction="none")
            mse = mse.view(mse.size(0), -1).mean(dim=1)
            psnr = 10 * torch.log10(1.0 / (mse + 1e-8))
            total_psnr += psnr.sum().item()
            n += degraded.size(0)

        return {"val_psnr": total_psnr / n, "val_loss": total_pixel / n}

    @torch.no_grad()
    def save_reconstruction_snapshot(self, val_loader, save_dir, epoch, n_samples=6):
        """Save a grid of reconstruction examples at this epoch."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        self.generator.eval()
        snap_dir = os.path.join(save_dir, "snapshots")
        os.makedirs(snap_dir, exist_ok=True)

        # Collect fixed samples on first call
        if self._snapshot_samples is None:
            for degraded, clean in val_loader:
                self._snapshot_samples = (
                    degraded[:n_samples].to(self.device),
                    clean[:n_samples].to(self.device),
                )
                break

        degraded, clean = self._snapshot_samples
        fake = self.generator(degraded)
        if isinstance(fake, tuple):
            fake = fake[0]

        n = degraded.size(0)
        fig, axes = plt.subplots(n, 3, figsize=(10, 2.5 * n))
        if n == 1:
            axes = axes[np.newaxis, :]

        col_titles = ["Degraded", "GAN Restored", "Ground Truth"]
        for i in range(n):
            for j, tensor in enumerate([degraded[i], fake[i], clean[i]]):
                img = tensor.cpu().permute(1, 2, 0).numpy()
                img = ((img * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8)
                axes[i, j].imshow(img)
                axes[i, j].axis("off")
                if i == 0:
                    axes[i, j].set_title(col_titles[j], fontweight="bold")

        fig.suptitle(f"GAN Reconstruction — Epoch {epoch + 1}",
                     fontsize=13, fontweight="bold")
        plt.tight_layout()
        plt.savefig(os.path.join(snap_dir, f"snapshot_epoch_{epoch+1:03d}.png"),
                    dpi=120)
        plt.close()

    def train(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader,
        epochs: int = 100,
        save_dir: str = "results/autoencoder/gan",
        early_stop_patience: int = 20,
        snapshot_interval: int = 10,
    ) -> dict:
        os.makedirs(save_dir, exist_ok=True)

        # Linear LR decay starting at epoch epochs//2
        decay_start = epochs // 2
        def lr_lambda(epoch):
            if epoch < decay_start:
                return 1.0
            return max(0.0, 1.0 - (epoch - decay_start) / max(decay_start, 1))

        self.sched_g = torch.optim.lr_scheduler.LambdaLR(self.opt_g, lr_lambda)
        self.sched_d = torch.optim.lr_scheduler.LambdaLR(self.opt_d, lr_lambda)

        best_psnr = 0.0
        patience_counter = 0

        for epoch in range(epochs):
            train_metrics = self.train_epoch(train_loader)
            val_metrics = self.evaluate(val_loader)

            self.sched_g.step()
            self.sched_d.step()

            for k, v in train_metrics.items():
                self.history[k].append(v)
            for k, v in val_metrics.items():
                self.history[k].append(v)

            print(
                f"Epoch [{epoch+1:3d}/{epochs}] "
                f"G={train_metrics['g_loss']:.4f} "
                f"(px={train_metrics['g_pixel']:.4f} "
                f"vgg={train_metrics['g_vgg']:.4f} "
                f"adv={train_metrics['g_adv']:.4f}) "
                f"D={train_metrics['d_loss']:.4f} | "
                f"Val PSNR={val_metrics['val_psnr']:.2f} dB"
            )

            # Save best generator by validation PSNR
            if val_metrics["val_psnr"] > best_psnr:
                best_psnr = val_metrics["val_psnr"]
                torch.save(
                    self.generator.state_dict(),
                    os.path.join(save_dir, "best_generator.pth"),
                )
                torch.save(
                    self.discriminator.state_dict(),
                    os.path.join(save_dir, "best_discriminator.pth"),
                )
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= early_stop_patience:
                    print(f"Early stopping at epoch {epoch+1}")
                    break

            # Save periodic reconstruction snapshots
            if (epoch + 1) % snapshot_interval == 0 or epoch == 0:
                self.save_reconstruction_snapshot(
                    val_loader, save_dir, epoch
                )

        # Save final checkpoints
        torch.save(
            self.generator.state_dict(),
            os.path.join(save_dir, "final_generator.pth"),
        )
        torch.save(
            self.discriminator.state_dict(),
            os.path.join(save_dir, "final_discriminator.pth"),
        )

        self.history["best_val_psnr"] = best_psnr
        return self.history


# =========================================================================
# Main
# =========================================================================

def main():
    parser = argparse.ArgumentParser(description="GAN training for plate restoration")
    parser.add_argument("--config", default="configs/config.yaml")
    parser.add_argument("--plate-dir", default="data/plates/train")
    parser.add_argument("--pretrained-weights", default=None,
                        help="Path to pre-trained autoencoder weights (.pth). "
                             "Strongly recommended for stable GAN training.")
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--device", default=None)
    parser.add_argument("--output-dir", default="results/autoencoder/gan")
    parser.add_argument("--lambda-pixel", type=float, default=10.0,
                        help="Weight for L1 pixel loss")
    parser.add_argument("--lambda-vgg", type=float, default=1.0,
                        help="Weight for VGG perceptual loss")
    parser.add_argument("--lambda-adv", type=float, default=1.0,
                        help="Weight for adversarial loss")
    parser.add_argument("--lr-g", type=float, default=0.0002,
                        help="Generator learning rate")
    parser.add_argument("--lr-d", type=float, default=0.0001,
                        help="Discriminator learning rate (typically 0.5x generator LR)")
    args = parser.parse_args()

    config = load_config(args.config)
    ae_cfg = config["autoencoder"]
    gan_cfg = config.get("gan", {})

    device = resolve_device(args.device)
    pin_memory = use_pinned_memory(device)
    num_gpus = torch.cuda.device_count() if device == "cuda" else 0

    epochs = args.epochs or gan_cfg.get("epochs", 100)
    base_batch = args.batch_size or gan_cfg.get("batch_size", 16)
    batch_size = base_batch * max(num_gpus, 1) if num_gpus > 1 else base_batch

    print(f"Device        : {device}")
    print(f"GPUs available: {num_gpus}")
    print(f"Batch size    : {batch_size}")
    print(f"Epochs        : {epochs}")
    print(f"Pretrained    : {args.pretrained_weights or 'None (training from scratch)'}")

    # ── Dataset ──────────────────────────────────────────────────────────
    dataset = PlateImageDataset(
        root_dir=args.plate_dir,
        img_height=ae_cfg["input_size"],
        img_width=ae_cfg["input_width"],
        degradation_fn=train_degradation,
    )

    if len(dataset) == 0:
        raise ValueError(f"No plate images found in '{args.plate_dir}'. Run extract_plates.py first.")

    n_val = max(1, int(len(dataset) * 0.2))
    n_train = len(dataset) - n_val
    train_ds, val_ds = random_split(
        dataset, [n_train, n_val],
        generator=torch.Generator().manual_seed(config["project"]["seed"]),
    )

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

    # ── Models ───────────────────────────────────────────────────────────
    generator = UNetAutoencoder(
        in_channels=3,
        base_features=ae_cfg["encoder_channels"][0],
        depth=len(ae_cfg["encoder_channels"]),
    )

    # Load pre-trained weights if provided
    if args.pretrained_weights and os.path.exists(args.pretrained_weights):
        state_dict = torch.load(args.pretrained_weights, map_location="cpu")
        # Strip DataParallel wrapper if present
        if any(k.startswith("module.") for k in state_dict):
            state_dict = {k[len("module."):]: v for k, v in state_dict.items()}
        generator.load_state_dict(state_dict)
        print(f"Loaded pre-trained generator weights from: {args.pretrained_weights}")
    else:
        print("Training generator from scratch (no pre-trained weights)")

    discriminator = MultiScaleDiscriminator(
        in_channels=3,
        base_features=gan_cfg.get("disc_base_features", 64),
        n_layers=gan_cfg.get("disc_n_layers", 3),
    )

    g_params = sum(p.numel() for p in generator.parameters())
    d_params = sum(p.numel() for p in discriminator.parameters())
    print(f"Generator params    : {g_params:,}")
    print(f"Discriminator params: {d_params:,}")

    # ── Train ────────────────────────────────────────────────────────────
    trainer = GANTrainer(
        generator=generator,
        discriminator=discriminator,
        device=device,
        lr_g=args.lr_g,
        lr_d=args.lr_d,
        lambda_pixel=args.lambda_pixel,
        lambda_vgg=args.lambda_vgg,
        lambda_adv=args.lambda_adv,
    )

    os.makedirs(args.output_dir, exist_ok=True)
    print(f"\n{'='*60}")
    print("TRAINING PLATE RESTORATION GAN")
    print(f"{'='*60}")

    history = trainer.train(
        train_loader, val_loader, epochs=epochs, save_dir=args.output_dir
    )

    # ── Save results ─────────────────────────────────────────────────────
    with open(os.path.join(args.output_dir, "gan_training_results.json"), "w") as f:
        json.dump(history, f, indent=2)

    # ── Plot training curves ─────────────────────────────────────────────
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 3, figsize=(18, 8))

    plots = [
        ("g_loss",   "Generator Loss",        "#2ecc71", axes[0, 0]),
        ("d_loss",   "Discriminator Loss",     "#e74c3c", axes[0, 1]),
        ("val_psnr", "Val PSNR (dB)",          "#3498db", axes[0, 2]),
        ("g_pixel",  "G Pixel Loss (L1)",      "#f39c12", axes[1, 0]),
        ("g_vgg",    "G VGG Perceptual Loss",  "#9b59b6", axes[1, 1]),
        ("g_adv",    "G Adversarial Loss",     "#1abc9c", axes[1, 2]),
    ]

    for key, title, color, ax in plots:
        if key in history and history[key]:
            data = history[key]
            ax.plot(data, color=color, alpha=0.3, linewidth=0.8)
            window = min(10, len(data))
            if window > 1:
                smoothed = np.convolve(data, np.ones(window)/window, mode="valid")
                ax.plot(range(window-1, len(data)), smoothed, color=color, linewidth=2)
            ax.set_title(title, fontweight="bold")
            ax.set_xlabel("Epoch")
            ax.grid(True, alpha=0.3)

    plt.suptitle("Plate Restoration GAN Training", fontsize=16, fontweight="bold")
    plt.tight_layout()
    plt.savefig(os.path.join(args.output_dir, "gan_training_curves.png"), dpi=150)
    plt.close()
    print(f"Training curves saved to {args.output_dir}/gan_training_curves.png")

    # ── Sample reconstructions ───────────────────────────────────────────
    generator.eval()
    with torch.no_grad():
        degraded_samples, restored_samples, clean_samples = [], [], []
        for degraded, clean in val_loader:
            degraded = degraded.to(device)
            fake = generator(degraded)
            if isinstance(fake, tuple):
                fake = fake[0]
            for i in range(min(4, degraded.size(0))):
                def _to_img(t):
                    arr = t.cpu().permute(1, 2, 0).numpy()
                    return ((arr * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8)
                degraded_samples.append(_to_img(degraded[i]))
                restored_samples.append(_to_img(fake[i]))
                clean_samples.append(_to_img(clean[i]))
            break

        if degraded_samples:
            plot_reconstruction_samples(
                degraded_samples, restored_samples, clean_samples,
                save_path=os.path.join(args.output_dir, "gan_reconstruction_samples.png"),
            )

    print(f"\nBest val PSNR : {history['best_val_psnr']:.2f} dB")
    print(f"Results saved : {args.output_dir}")
    print("GAN training complete!")
    print(f"\nTo use GAN generator in experiments, point --autoencoder-weights to:")
    print(f"  {args.output_dir}/best_generator.pth")


if __name__ == "__main__":
    main()
