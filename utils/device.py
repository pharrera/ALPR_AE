"""
Device resolution utility.

Centralizes device selection logic so all training scripts
consistently handle cuda / mps / cpu with a single function.
"""

import torch


def resolve_device(device: str = None) -> str:
    """
    Resolve the best available device.

    Priority: explicit arg > CUDA > MPS > CPU

    Args:
        device: "cuda", "mps", "cpu", "auto", or None (auto-detect)

    Returns:
        Device string ready to pass to PyTorch / Ultralytics
    """
    if device and device != "auto":
        return device

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def use_pinned_memory(device: str) -> bool:
    """
    Return whether pin_memory should be enabled for DataLoaders.

    pin_memory only helps when copying to CUDA. It can cause
    errors on MPS and has no benefit on CPU.
    """
    return device == "cuda"
