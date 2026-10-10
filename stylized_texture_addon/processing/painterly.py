"""Painterly variation: smooth anisotropic multiscale brush strokes (Phase 2).

The effect perturbs brightness, saturation and hue with correlated *smooth*
fields whose feature size is controlled by ``brush_scale``. A larger
``brush_scale`` produces larger strokes (lower spatial frequency). All variation
is low-amplitude and bounded; no per-pixel grain is introduced.
"""

from __future__ import annotations

import numpy as np

from .fields import multiscale_field
from .hue import hsv_to_rgb, rgb_to_hsv
from .seeding import (
    PAINTERLY_BRIGHTNESS_EFFECT_ID,
    PAINTERLY_CHROMA_EFFECT_ID,
    PAINTERLY_HUE_EFFECT_ID,
    effect_rng,
)

_BRUSH_OCTAVES = 3
_PERSISTENCE = 0.5
# Strokes are stretched along one axis; fewer cells vertically than
# horizontally yields anisotropic (brush-like) shapes.
_ANISOTROPY = 0.45

_BRIGHTNESS_GAIN = 0.28
_SATURATION_GAIN = 0.22
_HUE_GAIN = 0.05


def stroke_cells(brush_scale: float) -> tuple[float, float]:
    """Return continuous ``(cells_x, cells_y)`` for a brush size.

    Larger ``brush_scale`` -> larger strokes -> fewer cells on both axes. The
    counts are intentionally *fractional*: the feature span is ``1 / brush_scale``
    cells across the image, so the whole ``0.01..1`` range maps monotonically to
    a continuously changing stroke size (in particular ``0.6`` and ``1.0`` are
    distinct and ``0.5..1.0`` is no longer a plateau). Each axis is floored at a
    single cell so the coarsest strokes stay a single smooth gradient rather than
    collapsing, and the smallest brush never requires more than ~100 cells.
    """

    safe = float(np.clip(float(brush_scale), 0.01, 1.0))
    base = 1.0 / safe
    cells_x = float(max(1.0, base))
    cells_y = float(max(1.0, base * _ANISOTROPY))
    return cells_x, cells_y


def painterly_field(
    height: int,
    width: int,
    brush_scale: float,
    seed: int,
    *,
    effect_id: int = PAINTERLY_BRIGHTNESS_EFFECT_ID,
) -> np.ndarray:
    """Return the primary smooth painterly stroke field in ``[-1, 1]``."""

    cells_x, cells_y = stroke_cells(brush_scale)
    rng = effect_rng(seed, effect_id)
    return multiscale_field(
        height,
        width,
        cells_x=cells_x,
        cells_y=cells_y,
        rng=rng,
        octaves=_BRUSH_OCTAVES,
        persistence=_PERSISTENCE,
    )


def apply_painterly_variation(
    rgb: np.ndarray,
    paint_variation: float,
    brush_scale: float,
    seed: int,
) -> np.ndarray:
    """Apply bounded, smooth painterly brightness/saturation/hue variation."""

    data = np.asarray(rgb, dtype=np.float32)
    amount = float(np.clip(float(paint_variation), 0.0, 1.0))
    if amount <= 0.0:
        return data

    height, width = int(data.shape[0]), int(data.shape[1])
    cells_x, cells_y = stroke_cells(brush_scale)

    brightness_rng = effect_rng(seed, PAINTERLY_BRIGHTNESS_EFFECT_ID)
    chroma_rng = effect_rng(seed, PAINTERLY_CHROMA_EFFECT_ID)
    hue_rng = effect_rng(seed, PAINTERLY_HUE_EFFECT_ID)

    brightness_field = multiscale_field(
        height, width, cells_x=cells_x, cells_y=cells_y, rng=brightness_rng,
        octaves=_BRUSH_OCTAVES, persistence=_PERSISTENCE,
    )
    chroma_field = multiscale_field(
        height, width, cells_x=cells_x, cells_y=cells_y, rng=chroma_rng,
        octaves=_BRUSH_OCTAVES, persistence=_PERSISTENCE,
    )
    hue_field = multiscale_field(
        height, width, cells_x=cells_x, cells_y=cells_y, rng=hue_rng,
        octaves=_BRUSH_OCTAVES, persistence=_PERSISTENCE,
    )

    result = data * (1.0 + (_BRIGHTNESS_GAIN * amount) * brightness_field)[..., None]

    luma = (
        result[..., 0] * 0.2126 + result[..., 1] * 0.7152 + result[..., 2] * 0.0722
    )
    saturation_factor = 1.0 + (_SATURATION_GAIN * amount) * chroma_field
    # In-place saturation around luma to limit temporary buffers.
    result -= luma[..., None]
    result *= saturation_factor[..., None]
    result += luma[..., None]
    np.clip(result, 0.0, 1.0, out=result)

    hsv = rgb_to_hsv(result)
    offset = (_HUE_GAIN * amount) * hue_field * hsv[..., 1]
    hsv[..., 0] = (hsv[..., 0] + offset) % 1.0
    return np.clip(hsv_to_rgb(hsv), 0.0, 1.0).astype(np.float32)
