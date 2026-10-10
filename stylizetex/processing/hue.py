"""Bounded, wrapped hue variation in perceptual (sRGB) space (Phase 2).

The hue offset is driven by a smooth low-frequency field (never per-pixel
noise) and is scaled by the local saturation so neutral greys are preserved
exactly. The hue channel is wrapped with a modulo, so the shift stays limited
and cannot produce out-of-gamut artefacts.
"""

from __future__ import annotations

import numpy as np

from .fields import multiscale_field
from .seeding import HUE_EFFECT_ID, effect_rng

# Relative feature size of the hue blobs (fraction of the image, resolution
# independent) and the maximum fraction of the hue circle that a fully driven
# pixel can be shifted.
_HUE_CELLS = 7
_HUE_OCTAVES = 2
_HUE_MAX_SHIFT = 0.25

_EPS = 1e-12


def rgb_to_hsv(rgb: np.ndarray) -> np.ndarray:
    """Vectorized RGB ``[0, 1]`` -> HSV with ``H``, ``S``, ``V`` in ``[0, 1]``."""

    data = np.asarray(rgb, dtype=np.float32)
    red = data[..., 0]
    green = data[..., 1]
    blue = data[..., 2]

    maximum = np.max(data, axis=-1)
    minimum = np.min(data, axis=-1)
    delta = maximum - minimum

    safe_delta = np.where(delta > _EPS, delta, 1.0)
    red_c = (maximum - red) / safe_delta
    green_c = (maximum - green) / safe_delta
    blue_c = (maximum - blue) / safe_delta

    hue = np.where(
        maximum == red,
        blue_c - green_c,
        np.where(maximum == green, 2.0 + red_c - blue_c, 4.0 + green_c - red_c),
    )
    hue = np.where(delta > _EPS, (hue / 6.0) % 1.0, 0.0)

    saturation = np.where(maximum > _EPS, delta / np.maximum(maximum, _EPS), 0.0)
    value = maximum

    return np.stack([hue, saturation, value], axis=-1).astype(np.float32)


def hsv_to_rgb(hsv: np.ndarray) -> np.ndarray:
    """Vectorized HSV ``[0, 1]`` -> RGB ``[0, 1]``."""

    data = np.asarray(hsv, dtype=np.float32)
    hue = data[..., 0]
    saturation = data[..., 1]
    value = data[..., 2]

    scaled = np.clip(hue, 0.0, 1.0) * 6.0
    floor = np.floor(scaled)
    sector = floor.astype(np.int32) % 6
    fraction = (scaled - floor).astype(np.float32)

    p = value * (1.0 - saturation)
    q = value * (1.0 - saturation * fraction)
    t = value * (1.0 - saturation * (1.0 - fraction))

    # ``np.choose`` selects per pixel without building six boolean mask arrays.
    red = np.choose(sector, [value, q, p, p, t, value])
    green = np.choose(sector, [t, value, value, q, p, p])
    blue = np.choose(sector, [p, p, t, value, value, q])

    return np.stack([red, green, blue], axis=-1).astype(np.float32)


def apply_hue_variation(rgb: np.ndarray, amount: float, seed: int) -> np.ndarray:
    """Shift hue by a smooth seeded field, wrapping and preserving greys.

    ``amount == 0`` returns the input unchanged. Offsets are multiplied by the
    local saturation, so fully neutral pixels stay neutral.
    """

    data = np.asarray(rgb, dtype=np.float32)
    strength = float(np.clip(float(amount), 0.0, 1.0))
    if strength <= 0.0:
        return data

    height, width = int(data.shape[0]), int(data.shape[1])
    rng = effect_rng(seed, HUE_EFFECT_ID)
    field = multiscale_field(
        height,
        width,
        cells_x=_HUE_CELLS,
        cells_y=_HUE_CELLS,
        rng=rng,
        octaves=_HUE_OCTAVES,
    )

    hsv = rgb_to_hsv(data)
    saturation = hsv[..., 1]
    offset = field * (_HUE_MAX_SHIFT * strength) * saturation
    hsv[..., 0] = (hsv[..., 0] + offset) % 1.0
    return np.clip(hsv_to_rgb(hsv), 0.0, 1.0).astype(np.float32)
