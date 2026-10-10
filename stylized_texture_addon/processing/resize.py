"""Vectorized bilinear image resampling (NumPy only)."""

from __future__ import annotations

import numpy as np


def resize_bilinear(array: np.ndarray, out_height: int, out_width: int) -> np.ndarray:
    """Resize an ``(H, W, C)`` float array using bilinear interpolation."""

    if not isinstance(array, np.ndarray) or array.ndim != 3:
        raise ValueError("resize_bilinear expects a 3D (H, W, C) array.")

    out_height = int(out_height)
    out_width = int(out_width)
    if out_height <= 0 or out_width <= 0:
        raise ValueError("Output dimensions must be positive.")

    in_height, in_width = int(array.shape[0]), int(array.shape[1])
    if in_height == out_height and in_width == out_width:
        return array.astype(np.float32, copy=False)

    source = array.astype(np.float32, copy=False)

    ys = (np.arange(out_height, dtype=np.float32) + 0.5) * (in_height / out_height) - 0.5
    xs = (np.arange(out_width, dtype=np.float32) + 0.5) * (in_width / out_width) - 0.5
    ys = np.clip(ys, 0.0, float(in_height - 1))
    xs = np.clip(xs, 0.0, float(in_width - 1))

    y0 = np.floor(ys).astype(np.int32)
    x0 = np.floor(xs).astype(np.int32)
    y1 = np.minimum(y0 + 1, in_height - 1)
    x1 = np.minimum(x0 + 1, in_width - 1)

    wy = (ys - y0)[:, None, None]
    wx = (xs - x0)[None, :, None]

    top_left = source[y0][:, x0]
    top_right = source[y0][:, x1]
    bottom_left = source[y1][:, x0]
    bottom_right = source[y1][:, x1]

    top = top_left + (top_right - top_left) * wx
    bottom = bottom_left + (bottom_right - bottom_left) * wx
    return (top + (bottom - top) * wy).astype(np.float32)


def fit_resolution(in_width: int, in_height: int, target: int) -> tuple[int, int]:
    """Return ``(out_width, out_height)`` scaled so the longest side is ``target``."""

    in_width = int(in_width)
    in_height = int(in_height)
    target = int(target)
    if in_width <= 0 or in_height <= 0:
        raise ValueError("Input dimensions must be positive.")
    if target <= 0:
        raise ValueError("Target resolution must be positive.")

    longest = max(in_width, in_height)
    scale = target / float(longest)
    out_width = max(1, int(round(in_width * scale)))
    out_height = max(1, int(round(in_height * scale)))
    return out_width, out_height
