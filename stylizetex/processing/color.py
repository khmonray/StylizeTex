"""Color space conversion and perceptual color operations (NumPy only)."""

from __future__ import annotations

import numpy as np

_SRGB_THRESHOLD = 0.04045
_LINEAR_THRESHOLD = 0.0031308
_LUMA_WEIGHTS = (0.2126, 0.7152, 0.0722)


def srgb_to_linear(values: np.ndarray) -> np.ndarray:
    """Convert sRGB-encoded values in ``[0, 1]`` to scene-linear."""

    data = np.clip(np.asarray(values, dtype=np.float32), 0.0, 1.0)
    return np.where(
        data <= _SRGB_THRESHOLD,
        data / 12.92,
        np.power((data + 0.055) / 1.055, 2.4),
    ).astype(np.float32)


def linear_to_srgb(values: np.ndarray) -> np.ndarray:
    """Convert scene-linear values in ``[0, 1]`` to sRGB-encoded."""

    data = np.clip(np.asarray(values, dtype=np.float32), 0.0, 1.0)
    return np.where(
        data <= _LINEAR_THRESHOLD,
        data * 12.92,
        1.055 * np.power(data, 1.0 / 2.4) - 0.055,
    ).astype(np.float32)


def apply_color_simplification(rgb: np.ndarray, steps: int, strength: float) -> np.ndarray:
    """Posterize each channel and blend with the original by ``strength``."""

    levels = int(np.clip(int(steps), 2, 64))
    divisor = float(levels - 1)
    quantized = np.round(rgb * divisor) / divisor
    amount = float(np.clip(float(strength), 0.0, 1.0))
    return (rgb + (quantized - rgb) * amount).astype(np.float32)


def apply_contrast(rgb: np.ndarray, contrast: float) -> np.ndarray:
    """Scale contrast around mid grey in perceptual space."""

    factor = float(contrast)
    return np.clip((rgb - 0.5) * factor + 0.5, 0.0, 1.0).astype(np.float32)


def apply_saturation(rgb: np.ndarray, saturation: float) -> np.ndarray:
    """Adjust saturation around the perceptual luminance of each pixel."""

    factor = float(saturation)
    luma = (
        rgb[..., 0] * _LUMA_WEIGHTS[0]
        + rgb[..., 1] * _LUMA_WEIGHTS[1]
        + rgb[..., 2] * _LUMA_WEIGHTS[2]
    )[..., None]
    return np.clip(luma + (rgb - luma) * factor, 0.0, 1.0).astype(np.float32)
