"""
OCR preprocessing and utilities for license plate recognition.

Provides image preprocessing pipeline, multi-language support,
character allowlists, and confidence-based filtering to improve
EasyOCR accuracy on license plate crops.
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional, Dict
import re


# Character allowlist for license plates
# Brazilian plates (UFPR-ALPR): ABC1234 or ABC1D23 (Mercosul format)
# Chinese plates (CCPD): Mixed Chinese + alphanumeric
PLATE_CHARS_ALPHANUMERIC = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
PLATE_CHARS_BRAZILIAN = PLATE_CHARS_ALPHANUMERIC  # 3 letters + 4 digits (or 3L1D1L2D)


def preprocess_plate_for_ocr(
    plate_crop: np.ndarray,
    target_width: int = 256,
    target_height: int = 80,
    enhance_contrast: bool = True,
    binarize: bool = False,
    denoise: bool = True,
) -> np.ndarray:
    """
    Preprocess a plate crop image for optimal OCR performance.

    Pipeline:
    1. Resize to consistent dimensions
    2. Convert to grayscale
    3. Denoise
    4. Enhance contrast (CLAHE)
    5. Optional binarization (adaptive threshold)
    6. Convert back to 3-channel for EasyOCR

    Args:
        plate_crop: BGR or RGB plate crop image
        target_width: Target width for resizing
        target_height: Target height for resizing
        enhance_contrast: Apply CLAHE contrast enhancement
        binarize: Apply adaptive thresholding
        denoise: Apply denoising

    Returns:
        Preprocessed image (3-channel for EasyOCR compatibility)
    """
    if plate_crop is None or plate_crop.size == 0:
        return plate_crop

    # Resize to consistent size
    img = cv2.resize(plate_crop, (target_width, target_height),
                     interpolation=cv2.INTER_CUBIC)

    # Convert to grayscale
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY if img.shape[2] == 3 else cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()

    # Denoise
    if denoise:
        gray = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)

    # Enhance contrast with CLAHE
    if enhance_contrast:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 4))
        gray = clahe.apply(gray)

    # Sharpen
    kernel = np.array([[-1, -1, -1],
                       [-1,  9, -1],
                       [-1, -1, -1]])
    gray = cv2.filter2D(gray, -1, kernel)

    # Optional binarization
    if binarize:
        gray = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )

    # Convert back to 3-channel (EasyOCR expects this)
    result = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
    return result


def preprocess_plate_multi_variant(plate_crop: np.ndarray) -> List[np.ndarray]:
    """
    Generate multiple preprocessed variants of a plate crop for ensemble OCR.

    Returns multiple versions (original, enhanced, binarized, inverted)
    so we can run OCR on each and pick the best result.
    """
    variants = []

    # Variant 1: Standard enhancement
    variants.append(preprocess_plate_for_ocr(plate_crop, binarize=False))

    # Variant 2: With binarization
    variants.append(preprocess_plate_for_ocr(plate_crop, binarize=True))

    # Variant 3: Original (just resized to consistent size)
    resized = cv2.resize(plate_crop, (256, 80), interpolation=cv2.INTER_CUBIC)
    if len(resized.shape) == 2:
        resized = cv2.cvtColor(resized, cv2.COLOR_GRAY2RGB)
    variants.append(resized)

    # Variant 4: High contrast + inverted
    gray = cv2.cvtColor(plate_crop, cv2.COLOR_RGB2GRAY) if len(plate_crop.shape) == 3 else plate_crop
    gray = cv2.resize(gray, (256, 80))
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 4))
    enhanced = clahe.apply(gray)
    inverted = cv2.bitwise_not(enhanced)
    variants.append(cv2.cvtColor(inverted, cv2.COLOR_GRAY2RGB))

    return variants


def run_ocr_with_preprocessing(
    plate_crop: np.ndarray,
    ocr_engine,
    languages: List[str] = None,
    allowlist: str = None,
    confidence_threshold: float = 0.2,
    use_ensemble: bool = True,
) -> Tuple[str, float]:
    """
    Run OCR with full preprocessing pipeline and confidence filtering.

    If use_ensemble=True, runs OCR on multiple preprocessed variants
    and returns the result with highest total confidence.

    Args:
        plate_crop: Plate crop image (RGB)
        ocr_engine: EasyOCR reader instance
        languages: Language list (default: None uses engine's default)
        allowlist: Allowed characters string
        confidence_threshold: Minimum per-character confidence
        use_ensemble: Use multi-variant ensemble

    Returns:
        (predicted_text, average_confidence)
    """
    if plate_crop is None or plate_crop.size == 0:
        return "", 0.0

    if use_ensemble:
        variants = preprocess_plate_multi_variant(plate_crop)
    else:
        variants = [preprocess_plate_for_ocr(plate_crop)]

    best_text = ""
    best_confidence = 0.0

    for variant in variants:
        try:
            kwargs = {}
            if allowlist:
                kwargs["allowlist"] = allowlist

            results = ocr_engine.readtext(variant, **kwargs)

            if not results:
                continue

            # Filter by confidence
            filtered = [(text, conf) for _, text, conf in results
                        if conf >= confidence_threshold]

            if not filtered:
                # If all below threshold, take best single result
                best_result = max(results, key=lambda r: r[2])
                filtered = [(best_result[1], best_result[2])]

            text = "".join([t for t, c in filtered]).upper()
            avg_conf = np.mean([c for t, c in filtered])

            # Clean the text
            text = clean_plate_text(text)

            if avg_conf > best_confidence and len(text) >= 3:
                best_text = text
                best_confidence = avg_conf
        except Exception:
            continue

    return best_text, best_confidence


def clean_plate_text(text: str) -> str:
    """
    Clean and normalize OCR output for license plate text.

    - Remove spaces, dashes, dots
    - Fix common OCR confusions (O/0, I/1, S/5, B/8, Z/2)
    - Keep only alphanumeric characters
    """
    # Remove non-alphanumeric
    text = re.sub(r'[^A-Za-z0-9]', '', text.upper())

    # Common OCR corrections for plates
    # These are context-dependent — for Brazilian plates (ABC1234):
    # First 3 chars should be letters, next 4 should be digits
    # (or ABC1D23 for Mercosul format)
    if len(text) == 7:
        corrected = list(text)
        # Positions 0-2: should be letters
        letter_fixes = {'0': 'O', '1': 'I', '5': 'S', '8': 'B', '2': 'Z'}
        for i in range(min(3, len(corrected))):
            if corrected[i] in letter_fixes:
                corrected[i] = letter_fixes[corrected[i]]

        # Position 3: should be digit
        digit_fixes = {'O': '0', 'I': '1', 'S': '5', 'B': '8', 'Z': '2', 'G': '6'}
        if len(corrected) > 3 and corrected[3] in digit_fixes:
            corrected[3] = digit_fixes[corrected[3]]

        # Positions 4-6: could be digits (old) or letter+digits (Mercosul)
        for i in range(4, min(7, len(corrected))):
            if corrected[i] in digit_fixes:
                corrected[i] = digit_fixes[corrected[i]]

        text = ''.join(corrected)

    return text


def create_ocr_engine(
    languages: List[str] = None,
    gpu: bool = True,
) -> object:
    """
    Create an EasyOCR reader with optimized settings for license plates.

    Args:
        languages: Language list. Default includes English + Portuguese (for UFPR)
        gpu: Use GPU acceleration

    Returns:
        EasyOCR Reader instance
    """
    import easyocr

    if languages is None:
        # English + Portuguese for Brazilian plates (UFPR-ALPR)
        languages = ["en", "pt"]

    reader = easyocr.Reader(
        languages,
        gpu=gpu,
        verbose=False,
    )
    return reader
