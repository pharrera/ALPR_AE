"""
PatchGAN Discriminator for License Plate GAN-based Restoration.

PatchGAN classifies whether overlapping image patches are real or fake,
rather than classifying the whole image. This forces the generator to
produce locally realistic textures and sharp character edges — exactly
what matters for license plate OCR.

Architecture overview:
  Input: real or generated plate crop (3×H×W, normalized to [-1,1])
  Output: patch grid of real/fake scores (1×Ph×Pw)
           each score covers a receptive field of the input image

  Discriminator is NOT conditioned on the degraded input (unconditional).
  The generator is given the degraded plate; the discriminator just judges
  whether the output looks like a real clean plate.

Two variants:
  - PatchGANDiscriminator: Standard 70×70 PatchGAN (4-layer, from pix2pix)
  - MultiScaleDiscriminator: Two PatchGANs at different scales (from pix2pixHD)
    for better high-frequency and low-frequency discrimination.

Reference: Isola et al. "Image-to-Image Translation with Conditional Adversarial
Networks" (pix2pix, CVPR 2017); Wang et al. "High-Resolution Image Synthesis
and Semantic Manipulation with Conditional GANs" (pix2pixHD, CVPR 2018).
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import List


# =========================================================================
# Building Blocks
# =========================================================================

class ConvNormLReLU(nn.Module):
    """Conv2d → InstanceNorm2d → LeakyReLU block."""

    def __init__(
        self,
        in_ch: int,
        out_ch: int,
        kernel_size: int = 4,
        stride: int = 2,
        padding: int = 1,
        normalize: bool = True,
    ):
        super().__init__()
        layers = [
            nn.Conv2d(in_ch, out_ch, kernel_size, stride, padding, bias=not normalize),
        ]
        if normalize:
            layers.append(nn.InstanceNorm2d(out_ch, affine=True))
        layers.append(nn.LeakyReLU(0.2, inplace=True))
        self.block = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x)


# =========================================================================
# 70×70 PatchGAN Discriminator
# =========================================================================

class PatchGANDiscriminator(nn.Module):
    """
    Standard PatchGAN discriminator (70×70 receptive field).

    Produces a grid of real/fake scores rather than a single scalar.
    Each score covers a 70×70 pixel receptive field of the input.
    Loss is averaged over all patch scores.

    For license plates (128×256 input), this gives a ~2×4 score grid —
    each patch covers roughly one character cluster, which is ideal for
    detecting blurry or artifacted characters.

    Architecture (from pix2pix):
      C64 → C128 → C256 → C512 → Conv(1)
      (no norm on first layer; stride 2 except last two)
    """

    def __init__(self, in_channels: int = 3, base_features: int = 64, n_layers: int = 3):
        super().__init__()

        layers = [
            # First layer: no normalization
            ConvNormLReLU(in_channels, base_features, normalize=False),
        ]

        nf = base_features
        for i in range(1, n_layers):
            nf_prev = nf
            nf = min(nf * 2, 512)
            layers.append(ConvNormLReLU(nf_prev, nf, stride=2))

        # Last strided conv before output (stride=1)
        nf_prev = nf
        nf = min(nf * 2, 512)
        layers.append(ConvNormLReLU(nf_prev, nf, stride=1))

        # Output: 1-channel patch grid (no activation — use BCEWithLogitsLoss)
        layers.append(
            nn.Conv2d(nf, 1, kernel_size=4, stride=1, padding=1)
        )

        self.model = nn.Sequential(*layers)

        # Weight initialization
        self.apply(self._init_weights)

    @staticmethod
    def _init_weights(m: nn.Module):
        if isinstance(m, nn.Conv2d):
            nn.init.normal_(m.weight, 0.0, 0.02)
            if m.bias is not None:
                nn.init.constant_(m.bias, 0.0)
        elif isinstance(m, nn.InstanceNorm2d) and m.affine:
            nn.init.normal_(m.weight, 1.0, 0.02)
            nn.init.constant_(m.bias, 0.0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Image tensor (B, C, H, W), normalized to [-1, 1]
        Returns:
            Patch score map (B, 1, Ph, Pw) — raw logits (no sigmoid)
        """
        return self.model(x)


# =========================================================================
# Multi-Scale Discriminator (pix2pixHD style)
# =========================================================================

class MultiScaleDiscriminator(nn.Module):
    """
    Multi-scale discriminator using two PatchGANs at different resolutions.

    Discriminator D1 sees the image at full resolution → captures fine detail.
    Discriminator D2 sees the image downsampled 2× → captures global structure.

    Generator loss = average of both discriminator losses.
    This prevents mode collapse and improves stability compared to a single disc.

    Recommended for license plates since both fine character strokes (D1)
    and overall plate layout (D2) matter for perceptual quality.
    """

    def __init__(self, in_channels: int = 3, base_features: int = 64, n_layers: int = 3):
        super().__init__()
        self.D1 = PatchGANDiscriminator(in_channels, base_features, n_layers)
        self.D2 = PatchGANDiscriminator(in_channels, base_features, n_layers)
        self.downsample = nn.AvgPool2d(3, stride=2, padding=1, count_include_pad=False)

    def forward(self, x: torch.Tensor) -> List[torch.Tensor]:
        """
        Returns list of [D1_output, D2_output] — raw logits.
        """
        d1_out = self.D1(x)
        x_down = self.downsample(x)
        d2_out = self.D2(x_down)
        return [d1_out, d2_out]


# =========================================================================
# GAN Loss Functions
# =========================================================================

class GANLoss(nn.Module):
    """
    Flexible GAN loss supporting LSGAN (default) and vanilla GAN.

    LSGAN (least squares) is strongly preferred for image restoration:
    - More stable training gradients
    - Penalises outputs far from the decision boundary
    - Less prone to vanishing gradients than BCE

    For multi-scale discriminator, pass a list of tensors and this
    class averages the loss over all scales automatically.
    """

    def __init__(self, mode: str = "lsgan"):
        super().__init__()
        if mode == "lsgan":
            self.loss_fn = nn.MSELoss()
            self.real_label = 1.0
            self.fake_label = 0.0
        elif mode == "vanilla":
            self.loss_fn = nn.BCEWithLogitsLoss()
            self.real_label = 1.0
            self.fake_label = 0.0
        else:
            raise ValueError(f"Unknown GAN mode: {mode}")

    def _get_target(self, preds: torch.Tensor, is_real: bool) -> torch.Tensor:
        val = self.real_label if is_real else self.fake_label
        return torch.full_like(preds, val)

    def forward(
        self,
        preds,
        is_real: bool,
    ) -> torch.Tensor:
        """
        Args:
            preds: Single tensor OR list of tensors (multi-scale discriminator)
            is_real: True for real images, False for generated
        Returns:
            Scalar loss
        """
        if isinstance(preds, (list, tuple)):
            loss = sum(
                self.loss_fn(p, self._get_target(p, is_real)) for p in preds
            ) / len(preds)
            return loss
        return self.loss_fn(preds, self._get_target(preds, is_real))


# =========================================================================
# Feature Matching Loss (pix2pixHD)
# =========================================================================

class FeatureMatchingLoss(nn.Module):
    """
    Feature matching loss: matches intermediate discriminator features
    between real and generated images.

    Forces the generator to produce outputs whose internal feature
    statistics match real images at multiple scales, improving stability
    and preventing the generator from fooling the discriminator via
    high-frequency artifacts.

    Only usable with discriminators that expose intermediate features.
    """

    def __init__(self, weight: float = 10.0):
        super().__init__()
        self.weight = weight
        self.criterion = nn.L1Loss()

    def forward(
        self,
        real_features: List[torch.Tensor],
        fake_features: List[torch.Tensor],
    ) -> torch.Tensor:
        loss = 0.0
        for real_feat, fake_feat in zip(real_features, fake_features):
            loss += self.criterion(fake_feat, real_feat.detach())
        return self.weight * loss / len(real_features)
