"""
Image degradation utilities for resolution experiments.

Provides systematic degradation of license plate images to test
how detection and OCR accuracy degrade with resolution, and how
well the autoencoder can recover lost information.
"""

import cv2
import numpy as np
from typing import Tuple, Optional, Callable, List


class ImageDegrader:
    """
    Applies various degradation types to images for systematic experiments.

    Degradation types:
    - Bicubic downsampling: Clean resolution reduction
    - Gaussian blur: Simulates out-of-focus or motion blur
    - JPEG compression: Simulates lossy compression artifacts
    - Combined: Multiple degradations applied together
    - Noise: Additive Gaussian noise (simulates sensor noise)
    """

    def __init__(self, base_resolution: int = 640, seed: int = 42):
        self.base_resolution = base_resolution
        self.rng = np.random.RandomState(seed)

    def bicubic_downsample(
        self,
        image: np.ndarray,
        target_resolution: int,
        upscale_back: bool = True,
    ) -> np.ndarray:
        """
        Downsample image then optionally upscale back to original size.

        This simulates the information loss from low-resolution capture
        while keeping image dimensions consistent for the model.
        """
        h, w = image.shape[:2]

        # Calculate scale factor
        scale = target_resolution / max(h, w)
        new_h, new_w = int(h * scale), int(w * scale)

        # Downsample
        small = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)

        if upscale_back:
            # Upscale back to original resolution
            restored = cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)
            return restored
        return small

    def gaussian_blur(
        self,
        image: np.ndarray,
        kernel_size: int = 5,
        sigma: float = 0.0,
    ) -> np.ndarray:
        """Apply Gaussian blur to simulate defocus or motion blur."""
        # Ensure kernel size is odd
        if kernel_size % 2 == 0:
            kernel_size += 1
        return cv2.GaussianBlur(image, (kernel_size, kernel_size), sigma)

    def jpeg_compress(
        self,
        image: np.ndarray,
        quality: int = 50,
    ) -> np.ndarray:
        """Apply JPEG compression artifacts."""
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        _, encoded = cv2.imencode(".jpg", image, encode_param)
        decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        return decoded

    def add_noise(
        self,
        image: np.ndarray,
        noise_std: float = 25.0,
    ) -> np.ndarray:
        """Add Gaussian noise to simulate sensor noise."""
        noise = self.rng.normal(0, noise_std, image.shape).astype(np.float32)
        noisy = image.astype(np.float32) + noise
        return np.clip(noisy, 0, 255).astype(np.uint8)

    def combined_degradation(
        self,
        image: np.ndarray,
        target_resolution: int,
        blur_kernel: int = 3,
        jpeg_quality: int = 75,
        noise_std: float = 10.0,
    ) -> np.ndarray:
        """
        Apply a combination of degradations to simulate real-world conditions.

        Order: downsample -> blur -> noise -> JPEG compress -> upscale
        """
        h, w = image.shape[:2]

        # Downsample
        scale = target_resolution / max(h, w)
        new_h, new_w = int(h * scale), int(w * scale)
        degraded = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)

        # Blur
        if blur_kernel > 1:
            if blur_kernel % 2 == 0:
                blur_kernel += 1
            degraded = cv2.GaussianBlur(
                degraded, (blur_kernel, blur_kernel), 0
            )

        # Noise
        if noise_std > 0:
            noise = self.rng.normal(0, noise_std, degraded.shape).astype(np.float32)
            degraded = np.clip(
                degraded.astype(np.float32) + noise, 0, 255
            ).astype(np.uint8)

        # JPEG compression
        if jpeg_quality < 100:
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]
            _, encoded = cv2.imencode(".jpg", degraded, encode_param)
            degraded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)

        # Upscale back
        degraded = cv2.resize(degraded, (w, h), interpolation=cv2.INTER_CUBIC)

        return degraded

    def get_degradation_fn(
        self,
        degradation_type: str,
        target_resolution: int,
        **kwargs,
    ) -> Callable:
        """
        Get a degradation function for use with datasets.

        Args:
            degradation_type: One of "bicubic_downsample", "gaussian_blur",
                              "jpeg_compression", "combined"
            target_resolution: Target degraded resolution
            **kwargs: Additional parameters for the degradation type

        Returns:
            A callable that takes an image and returns the degraded version
        """
        # Scale degradation severity based on how far below base resolution
        # scale=1.0 at base_resolution, scale→large as resolution→0
        scale = self.base_resolution / max(target_resolution, 1)

        if degradation_type == "bicubic_downsample":
            return lambda img: self.bicubic_downsample(
                img, target_resolution, upscale_back=True
            )
        elif degradation_type == "gaussian_blur":
            # Kernel size increases as resolution decreases
            # scale=1→k=3, scale=2→k=7, scale=4→k=13, scale=8→k=25
            base_kernel = kwargs.get("kernel_size", 3)
            kernel = int(base_kernel * scale)
            if kernel % 2 == 0:
                kernel += 1
            kernel = max(3, min(kernel, 51))  # clamp to [3, 51]
            sigma = scale * 1.0  # sigma also scales
            return lambda img, k=kernel, s=sigma: self.gaussian_blur(
                img, kernel_size=k, sigma=s
            )
        elif degradation_type == "jpeg_compression":
            # Quality decreases as resolution decreases
            # scale=1→q=95, scale=2→q=75, scale=4→q=50, scale=8→q=15
            base_quality = kwargs.get("quality", 95)
            quality = max(5, int(base_quality / scale))
            return lambda img, q=quality: self.jpeg_compress(img, quality=q)
        elif degradation_type == "combined":
            return lambda img: self.combined_degradation(
                img,
                target_resolution,
                blur_kernel=kwargs.get("blur_kernel", 3),
                jpeg_quality=kwargs.get("jpeg_quality", 75),
                noise_std=kwargs.get("noise_std", 10.0),
            )
        else:
            raise ValueError(f"Unknown degradation type: {degradation_type}")

    def generate_degradation_grid(
        self,
        image: np.ndarray,
        resolutions: List[int],
    ) -> List[Tuple[int, np.ndarray]]:
        """
        Generate a grid of degraded versions at different resolutions.

        Useful for visualization and quick comparison.

        Returns:
            List of (resolution, degraded_image) tuples
        """
        results = [(self.base_resolution, image.copy())]  # Original
        for res in resolutions:
            if res < self.base_resolution:
                degraded = self.bicubic_downsample(image, res, upscale_back=True)
                results.append((res, degraded))
        return results


def compute_image_quality_metrics(
    original: np.ndarray,
    degraded: np.ndarray,
) -> dict:
    """
    Compute image quality metrics between original and degraded images.

    Returns dict with PSNR and SSIM values.
    """
    # Ensure same size
    if original.shape != degraded.shape:
        degraded = cv2.resize(
            degraded, (original.shape[1], original.shape[0])
        )

    # PSNR
    mse = np.mean((original.astype(float) - degraded.astype(float)) ** 2)
    if mse == 0:
        psnr = float("inf")
    else:
        psnr = 10 * np.log10(255.0**2 / mse)

    # SSIM (simplified single-channel version)
    # For full SSIM, use skimage.metrics.structural_similarity
    gray_orig = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY) if len(original.shape) == 3 else original
    gray_deg = cv2.cvtColor(degraded, cv2.COLOR_BGR2GRAY) if len(degraded.shape) == 3 else degraded

    C1 = (0.01 * 255) ** 2
    C2 = (0.03 * 255) ** 2

    mu1 = cv2.GaussianBlur(gray_orig.astype(np.float64), (11, 11), 1.5)
    mu2 = cv2.GaussianBlur(gray_deg.astype(np.float64), (11, 11), 1.5)

    mu1_sq = mu1**2
    mu2_sq = mu2**2
    mu1_mu2 = mu1 * mu2

    sigma1_sq = cv2.GaussianBlur(gray_orig.astype(np.float64) ** 2, (11, 11), 1.5) - mu1_sq
    sigma2_sq = cv2.GaussianBlur(gray_deg.astype(np.float64) ** 2, (11, 11), 1.5) - mu2_sq
    sigma12 = (
        cv2.GaussianBlur(
            gray_orig.astype(np.float64) * gray_deg.astype(np.float64),
            (11, 11),
            1.5,
        )
        - mu1_mu2
    )

    ssim_map = ((2 * mu1_mu2 + C1) * (2 * sigma12 + C2)) / (
        (mu1_sq + mu2_sq + C1) * (sigma1_sq + sigma2_sq + C2)
    )
    ssim = float(np.mean(ssim_map))

    return {"psnr": psnr, "ssim": ssim}
