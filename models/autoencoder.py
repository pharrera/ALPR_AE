"""
Convolutional Autoencoder for License Plate Image Restoration.

Two architectures:
1. ConvAutoencoder: Standard encoder-decoder with bottleneck
2. UNetAutoencoder: U-Net style with skip connections for better
   spatial detail preservation

The autoencoder learns to map degraded (low-res, noisy, compressed)
plate images back to clean, high-resolution versions. This is the
core contribution of the project: demonstrating that an autoencoder
preprocessing step can recover detection/OCR accuracy lost to
image degradation.

Loss: Combined MSE + SSIM for both pixel-level and structural similarity.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple
import math
import torchvision.models as models


# =========================================================================
# Loss Functions
# =========================================================================

class SSIMLoss(nn.Module):
    """
    Differentiable SSIM loss for training.
    Returns 1 - SSIM (so lower is better, consistent with other losses).
    """

    def __init__(self, window_size: int = 11, channels: int = 3):
        super().__init__()
        self.window_size = window_size
        self.channels = channels
        self.window = self._create_window(window_size, channels)

    def _create_window(self, window_size: int, channels: int) -> torch.Tensor:
        """Create Gaussian window for SSIM computation."""
        sigma = 1.5
        gauss = torch.tensor(
            [
                math.exp(-((x - window_size // 2) ** 2) / (2 * sigma**2))
                for x in range(window_size)
            ]
        )
        gauss = gauss / gauss.sum()
        window_1d = gauss.unsqueeze(1)
        window_2d = window_1d.mm(window_1d.t()).float().unsqueeze(0).unsqueeze(0)
        return window_2d.expand(channels, 1, window_size, window_size).contiguous()

    def forward(self, img1: torch.Tensor, img2: torch.Tensor) -> torch.Tensor:
        channels = img1.size(1)
        window = self.window.to(img1.device)
        if channels != self.channels:
            window = self._create_window(self.window_size, channels).to(img1.device)

        mu1 = F.conv2d(img1, window, padding=self.window_size // 2, groups=channels)
        mu2 = F.conv2d(img2, window, padding=self.window_size // 2, groups=channels)

        mu1_sq = mu1.pow(2)
        mu2_sq = mu2.pow(2)
        mu1_mu2 = mu1 * mu2

        sigma1_sq = (
            F.conv2d(img1 * img1, window, padding=self.window_size // 2, groups=channels)
            - mu1_sq
        )
        sigma2_sq = (
            F.conv2d(img2 * img2, window, padding=self.window_size // 2, groups=channels)
            - mu2_sq
        )
        sigma12 = (
            F.conv2d(img1 * img2, window, padding=self.window_size // 2, groups=channels)
            - mu1_mu2
        )

        C1 = 0.01**2
        C2 = 0.03**2

        ssim_map = ((2 * mu1_mu2 + C1) * (2 * sigma12 + C2)) / (
            (mu1_sq + mu2_sq + C1) * (sigma1_sq + sigma2_sq + C2)
        )

        return 1.0 - ssim_map.mean()


class VGGPerceptualLoss(nn.Module):
    """
    VGG-based perceptual loss (feature matching loss).

    Compares feature representations from a pre-trained VGG16 network
    rather than raw pixel values. This encourages the autoencoder to
    preserve perceptual quality (edges, textures, structure) rather
    than just minimising pixel-level error.

    Uses features from layers: relu1_2, relu2_2, relu3_3, relu4_3
    """

    def __init__(self, resize: bool = True):
        super().__init__()
        vgg = models.vgg16(weights=models.VGG16_Weights.IMAGENET1K_V1)
        blocks = []
        blocks.append(vgg.features[:4].eval())   # relu1_2
        blocks.append(vgg.features[4:9].eval())   # relu2_2
        blocks.append(vgg.features[9:16].eval())  # relu3_3
        blocks.append(vgg.features[16:23].eval()) # relu4_3

        self.blocks = nn.ModuleList(blocks)
        self.resize = resize

        # Freeze VGG weights
        for param in self.parameters():
            param.requires_grad = False

        # ImageNet normalization (VGG expects ImageNet-normalized inputs)
        self.register_buffer(
            "mean", torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
        )
        self.register_buffer(
            "std", torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
        )

        # Weights for each layer's contribution
        self.layer_weights = [1.0 / 32, 1.0 / 16, 1.0 / 8, 1.0 / 4]

    def _normalize(self, x: torch.Tensor) -> torch.Tensor:
        """Convert from [-1,1] (Tanh output) to ImageNet-normalized."""
        # [-1, 1] -> [0, 1]
        x = x * 0.5 + 0.5
        # ImageNet normalization (move buffers to input device)
        return (x - self.mean.to(x.device)) / self.std.to(x.device)

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        # Move VGG blocks to input device if needed
        if pred.device != next(self.blocks[0].parameters()).device:
            self.to(pred.device)

        # Normalize to ImageNet scale
        pred = self._normalize(pred)
        target = self._normalize(target)

        # Resize to minimum VGG input size if needed
        if self.resize and (pred.shape[2] < 32 or pred.shape[3] < 32):
            pred = F.interpolate(pred, size=(64, 128), mode="bilinear", align_corners=False)
            target = F.interpolate(target, size=(64, 128), mode="bilinear", align_corners=False)

        loss = 0.0
        x = pred
        y = target
        for block, weight in zip(self.blocks, self.layer_weights):
            x = block(x)
            y = block(y)
            loss += weight * F.l1_loss(x, y)

        return loss


class CombinedLoss(nn.Module):
    """MSE + SSIM + optional VGG perceptual loss."""

    def __init__(self, ssim_weight: float = 0.5, perceptual_weight: float = 0.0):
        super().__init__()
        self.mse = nn.MSELoss()
        self.ssim = SSIMLoss()
        self.ssim_weight = ssim_weight
        self.perceptual_weight = perceptual_weight

        self.perceptual = None
        if perceptual_weight > 0:
            self.perceptual = VGGPerceptualLoss()

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        mse_loss = self.mse(pred, target)
        ssim_loss = self.ssim(pred, target)

        total = (1 - self.ssim_weight) * mse_loss + self.ssim_weight * ssim_loss

        if self.perceptual is not None:
            total = total + self.perceptual_weight * self.perceptual(pred, target)

        return total


# =========================================================================
# Standard Convolutional Autoencoder
# =========================================================================

class ConvAutoencoder(nn.Module):
    """
    Standard convolutional autoencoder with symmetric encoder-decoder.

    Encoder: Series of Conv2d + BN + ReLU + MaxPool
    Bottleneck: Compressed latent representation
    Decoder: Series of ConvTranspose2d + BN + ReLU (mirrors encoder)
    """

    def __init__(
        self,
        in_channels: int = 3,
        encoder_channels: List[int] = None,
        latent_dim: int = 128,
        input_height: int = 128,
        input_width: int = 256,
    ):
        super().__init__()

        if encoder_channels is None:
            encoder_channels = [32, 64, 128, 256]

        self.in_channels = in_channels
        self.encoder_channels = encoder_channels
        self.latent_dim = latent_dim
        self.input_height = input_height
        self.input_width = input_width

        # --- Encoder ---
        encoder_layers = []
        ch_in = in_channels
        for ch_out in encoder_channels:
            encoder_layers.extend([
                nn.Conv2d(ch_in, ch_out, kernel_size=3, stride=2, padding=1),
                nn.BatchNorm2d(ch_out),
                nn.ReLU(inplace=True),
            ])
            ch_in = ch_out
        self.encoder = nn.Sequential(*encoder_layers)

        # Calculate encoded spatial dimensions
        num_downsamples = len(encoder_channels)
        self.enc_h = input_height // (2 ** num_downsamples)
        self.enc_w = input_width // (2 ** num_downsamples)
        self.enc_flat = encoder_channels[-1] * self.enc_h * self.enc_w

        # Bottleneck
        self.fc_encode = nn.Linear(self.enc_flat, latent_dim)
        self.fc_decode = nn.Linear(latent_dim, self.enc_flat)

        # --- Decoder ---
        decoder_channels = list(reversed(encoder_channels))
        decoder_layers = []
        for i, ch_out in enumerate(decoder_channels[1:]):
            ch_in = decoder_channels[i]
            decoder_layers.extend([
                nn.ConvTranspose2d(
                    ch_in, ch_out, kernel_size=3, stride=2, padding=1, output_padding=1
                ),
                nn.BatchNorm2d(ch_out),
                nn.ReLU(inplace=True),
            ])

        # Final layer to reconstruct original channels
        decoder_layers.extend([
            nn.ConvTranspose2d(
                decoder_channels[-1],
                in_channels,
                kernel_size=3,
                stride=2,
                padding=1,
                output_padding=1,
            ),
            nn.Tanh(),  # Output in [-1, 1] range (matching normalized input)
        ])
        self.decoder = nn.Sequential(*decoder_layers)

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        """Encode input to latent representation."""
        h = self.encoder(x)
        h = h.view(h.size(0), -1)
        z = self.fc_encode(h)
        return z

    def decode(self, z: torch.Tensor) -> torch.Tensor:
        """Decode latent representation to image."""
        h = self.fc_decode(z)
        h = h.view(h.size(0), self.encoder_channels[-1], self.enc_h, self.enc_w)
        out = self.decoder(h)
        # Ensure output matches input dimensions
        out = F.interpolate(
            out, size=(self.input_height, self.input_width), mode="bilinear", align_corners=False
        )
        return out

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass: encode then decode.
        Returns (reconstruction, latent_code).
        """
        z = self.encode(x)
        reconstruction = self.decode(z)
        return reconstruction, z


# =========================================================================
# U-Net Style Autoencoder (with Skip Connections)
# =========================================================================

class DoubleConv(nn.Module):
    """Two consecutive Conv-BN-ReLU blocks."""

    def __init__(self, in_ch: int, out_ch: int):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, padding=1),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, 3, padding=1),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.block(x)


class UNetAutoencoder(nn.Module):
    """
    U-Net style autoencoder with skip connections.

    Skip connections help preserve spatial detail during reconstruction,
    which is critical for license plate characters where fine details
    (like the difference between 'O' and '0', or '1' and 'I') matter.

    This is the recommended architecture for the resolution restoration task.
    """

    def __init__(
        self,
        in_channels: int = 3,
        base_features: int = 32,
        depth: int = 4,
    ):
        super().__init__()

        self.depth = depth
        features = [base_features * (2**i) for i in range(depth)]
        # e.g., [32, 64, 128, 256] for depth=4

        # Encoder path
        self.encoders = nn.ModuleList()
        self.pools = nn.ModuleList()
        ch_in = in_channels
        for f in features:
            self.encoders.append(DoubleConv(ch_in, f))
            self.pools.append(nn.MaxPool2d(2, 2))
            ch_in = f

        # Bottleneck
        self.bottleneck = DoubleConv(features[-1], features[-1] * 2)

        # Decoder path
        self.upconvs = nn.ModuleList()
        self.decoders = nn.ModuleList()
        ch_in = features[-1] * 2
        for f in reversed(features):
            self.upconvs.append(
                nn.ConvTranspose2d(ch_in, f, kernel_size=2, stride=2)
            )
            self.decoders.append(DoubleConv(f * 2, f))  # *2 for skip connection concat
            ch_in = f

        # Output
        self.output_conv = nn.Sequential(
            nn.Conv2d(features[0], in_channels, kernel_size=1),
            nn.Tanh(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        input_size = (x.shape[2], x.shape[3])

        # Encoder
        skip_connections = []
        h = x
        for encoder, pool in zip(self.encoders, self.pools):
            h = encoder(h)
            skip_connections.append(h)
            h = pool(h)

        # Bottleneck
        h = self.bottleneck(h)

        # Decoder with skip connections
        skip_connections = skip_connections[::-1]  # Reverse for decoder order
        for upconv, decoder, skip in zip(
            self.upconvs, self.decoders, skip_connections
        ):
            h = upconv(h)
            # Handle size mismatch from pooling
            if h.shape != skip.shape:
                h = F.interpolate(h, size=skip.shape[2:], mode="bilinear", align_corners=False)
            h = torch.cat([h, skip], dim=1)  # Skip connection
            h = decoder(h)

        out = self.output_conv(h)

        # Ensure output matches input size exactly
        if out.shape[2:] != input_size:
            out = F.interpolate(out, size=input_size, mode="bilinear", align_corners=False)

        return out


# =========================================================================
# Autoencoder Trainer
# =========================================================================

class AutoencoderTrainer:
    """Training wrapper for autoencoder models."""

    def __init__(
        self,
        model: nn.Module,
        device: str = "cuda",
        learning_rate: float = 0.0001,
        weight_decay: float = 1e-5,
        loss_type: str = "mse+ssim",
        ssim_weight: float = 0.5,
        perceptual_weight: float = 0.0,
        scheduler_T_max: int = 100,
    ):
        self.model = model.to(device)
        self.device = device

        if loss_type == "mse+ssim":
            self.criterion = CombinedLoss(ssim_weight=ssim_weight, perceptual_weight=perceptual_weight)
        elif loss_type == "mse":
            self.criterion = nn.MSELoss()
        elif loss_type == "l1":
            self.criterion = nn.L1Loss()
        else:
            raise ValueError(f"Unknown loss type: {loss_type}")

        self.optimizer = torch.optim.AdamW(
            model.parameters(), lr=learning_rate, weight_decay=weight_decay
        )
        self.scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
            self.optimizer, T_0=scheduler_T_max, T_mult=2, eta_min=1e-6
        )

    def train_epoch(self, dataloader) -> Dict[str, float]:
        """Train for one epoch on (degraded, clean) image pairs."""
        self.model.train()
        total_loss = 0.0
        total = 0

        for degraded, clean in dataloader:
            degraded = degraded.to(self.device)
            clean = clean.to(self.device)

            self.optimizer.zero_grad()

            # Handle both architectures (ConvAutoencoder returns tuple, UNet returns tensor)
            output = self.model(degraded)
            if isinstance(output, tuple):
                reconstruction, _ = output
            else:
                reconstruction = output

            loss = self.criterion(reconstruction, clean)
            loss.backward()
            self.optimizer.step()

            total_loss += loss.item() * degraded.size(0)
            total += degraded.size(0)

        self.scheduler.step()

        return {"loss": total_loss / total}

    @torch.no_grad()
    def evaluate(self, dataloader) -> Dict[str, float]:
        """Evaluate reconstruction quality."""
        self.model.eval()
        total_loss = 0.0
        total_psnr = 0.0
        total = 0

        for degraded, clean in dataloader:
            degraded = degraded.to(self.device)
            clean = clean.to(self.device)

            output = self.model(degraded)
            if isinstance(output, tuple):
                reconstruction, _ = output
            else:
                reconstruction = output

            loss = self.criterion(reconstruction, clean)
            total_loss += loss.item() * degraded.size(0)

            # Compute PSNR
            mse = F.mse_loss(reconstruction, clean, reduction="none")
            mse = mse.view(mse.size(0), -1).mean(dim=1)
            psnr = 10 * torch.log10(1.0 / (mse + 1e-8))
            total_psnr += psnr.sum().item()

            total += degraded.size(0)

        return {
            "loss": total_loss / total,
            "psnr": total_psnr / total,
        }

    def train(
        self,
        train_loader,
        val_loader,
        epochs: int = 100,
        save_dir: str = "results/autoencoder",
        early_stop_patience: int = 15,
    ) -> Dict:
        """Full training loop."""
        import os
        os.makedirs(save_dir, exist_ok=True)

        history = {"train_loss": [], "val_loss": [], "val_psnr": []}
        best_loss = float("inf")
        patience_counter = 0

        for epoch in range(epochs):
            train_metrics = self.train_epoch(train_loader)
            val_metrics = self.evaluate(val_loader)

            history["train_loss"].append(train_metrics["loss"])
            history["val_loss"].append(val_metrics["loss"])
            history["val_psnr"].append(val_metrics["psnr"])

            print(
                f"Epoch [{epoch+1}/{epochs}] "
                f"Train Loss: {train_metrics['loss']:.6f} "
                f"Val Loss: {val_metrics['loss']:.6f} "
                f"Val PSNR: {val_metrics['psnr']:.2f} dB"
            )

            if val_metrics["loss"] < best_loss:
                best_loss = val_metrics["loss"]
                torch.save(
                    self.model.state_dict(),
                    os.path.join(save_dir, "best_autoencoder.pth"),
                )
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= early_stop_patience:
                    print(f"Early stopping at epoch {epoch+1}")
                    break

        torch.save(
            self.model.state_dict(),
            os.path.join(save_dir, "final_autoencoder.pth"),
        )

        history["best_val_loss"] = best_loss
        return history
