"""Validation helpers for float RGB/RGBA image arrays.

Blender-independent (NumPy only).
"""

from __future__ import annotations

import numpy as np

_ALLOWED_CHANNELS = (3, 4)
_TOLERANCE = 1e-4


def validate_rgb_array(array: np.ndarray, *, name: str = "array") -> int:
    """Validate a float RGB/RGBA array and return its channel count.

    The array must be a floating point ``(H, W, 3)`` or ``(H, W, 4)`` NumPy
    array with finite values inside ``[0, 1]``.
    """

    if not isinstance(array, np.ndarray):
        raise TypeError(f"{name} must be a numpy.ndarray, got {type(array).__name__}.")

    if array.ndim != 3:
        raise ValueError(f"{name} must be a 3D (H, W, C) array, got {array.ndim} dimensions.")

    channels = int(array.shape[2])
    if channels not in _ALLOWED_CHANNELS:
        raise ValueError(f"{name} must have 3 (RGB) or 4 (RGBA) channels, got {channels}.")

    if array.shape[0] == 0 or array.shape[1] == 0:
        raise ValueError(f"{name} must not be empty.")

    if not np.issubdtype(array.dtype, np.floating):
        raise TypeError(f"{name} must use a floating point dtype, got {array.dtype}.")

    if not np.isfinite(array).all():
        raise ValueError(f"{name} contains NaN or infinite values.")

    minimum = float(array.min())
    maximum = float(array.max())
    if minimum < -_TOLERANCE or maximum > 1.0 + _TOLERANCE:
        raise ValueError(f"{name} values must be within [0, 1], got range [{minimum}, {maximum}].")

    return channels
