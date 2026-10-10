"""Micro-detail smoothing (Phase 2).

Reduces fine high-frequency detail *before* color simplification using a small
edge-stopping (bilateral-like) filter. Strong colour boundaries are kept
reasonably sharp, while low-amplitude grain is averaged away — this deliberately
avoids a plain Gaussian blur.

The filter is fully vectorized: a fixed, small loop over pixel shifts is used,
so there is never a per-pixel Python loop and no giant ``(shifts, H, W)``
allocation. Alpha, when present, participates in the edge-stopping weights so
smoothing does not bleed across alpha boundaries.
"""

from __future__ import annotations

import numpy as np

_DEFAULT_RADIUS = 2
_DEFAULT_SIGMA_SPATIAL = 1.3
_DEFAULT_SIGMA_COLOR = 0.15
_DEFAULT_SIGMA_ALPHA = 0.15


def _neighbour_offsets(radius: int):
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dy == 0 and dx == 0:
                continue
            yield dy, dx


def _bilateral_smooth(
    rgb: np.ndarray,
    alpha: np.ndarray | None,
    radius: int,
    sigma_spatial: float,
    sigma_color: float,
    sigma_alpha: float,
) -> np.ndarray:
    height, width = int(rgb.shape[0]), int(rgb.shape[1])
    radius = int(max(1, min(radius, max(height, width))))

    padded = np.pad(rgb, ((radius, radius), (radius, radius), (0, 0)), mode="edge")
    if alpha is not None:
        padded_alpha = np.pad(
            alpha, ((radius, radius), (radius, radius), (0, 0)), mode="edge"
        )
    else:
        padded_alpha = None

    center = padded[radius : radius + height, radius : radius + width]
    center_alpha = (
        padded_alpha[radius : radius + height, radius : radius + width]
        if padded_alpha is not None
        else None
    )

    accum = np.zeros((height, width, 3), dtype=np.float32)
    weight_sum = np.zeros((height, width), dtype=np.float32)

    color_denom = 2.0 * float(sigma_color) ** 2
    alpha_denom = 2.0 * float(sigma_alpha) ** 2
    spatial_denom = 2.0 * float(sigma_spatial) ** 2

    for dy, dx in _neighbour_offsets(radius):
        neighbour = padded[
            radius + dy : radius + dy + height,
            radius + dx : radius + dx + width,
        ]
        # Squared colour distance computed per channel to avoid a full
        # ``(H, W, 3)`` temporary for every shift.
        distance = np.zeros((height, width), dtype=np.float32)
        for channel in range(3):
            difference = neighbour[..., channel] - center[..., channel]
            distance += difference * difference
        weight = np.exp(-distance / color_denom, dtype=np.float32)

        if padded_alpha is not None:
            alpha_neighbour = padded_alpha[
                radius + dy : radius + dy + height,
                radius + dx : radius + dx + width,
            ]
            alpha_difference = alpha_neighbour[..., 0] - center_alpha[..., 0]
            weight *= np.exp(
                -(alpha_difference * alpha_difference) / alpha_denom, dtype=np.float32
            )

        weight *= float(
            np.exp(-(dy * dy + dx * dx) / spatial_denom, dtype=np.float32)
        )
        for channel in range(3):
            accum[..., channel] += neighbour[..., channel] * weight
        weight_sum += weight

    return (accum / np.maximum(weight_sum, 1e-8)[..., None]).astype(np.float32)


def apply_micro_detail(
    array: np.ndarray,
    micro_detail: float,
    *,
    alpha: np.ndarray | None = None,
    radius: int = _DEFAULT_RADIUS,
    sigma_color: float = _DEFAULT_SIGMA_COLOR,
) -> np.ndarray:
    """Blend a smoothed version with the original by ``micro_detail``.

    ``micro_detail == 1`` returns the input unchanged (Phase 1 behavior).
    ``micro_detail == 0`` returns the fully smoothed image. The blend is
    ``smoothed + (original - smoothed) * micro_detail``.

    ``array`` may be ``(H, W, 3)`` or ``(H, W, 4)``. For RGBA input the alpha
    channel is used in the edge-stopping weights and returned untouched; for RGB
    input an optional ``alpha`` ``(H, W, 1)`` array can be supplied for the same
    purpose.
    """

    data = np.asarray(array, dtype=np.float32)
    amount = float(np.clip(float(micro_detail), 0.0, 1.0))
    if amount >= 1.0:
        return data

    channels = int(data.shape[-1])
    if channels == 4:
        rgb = data[..., :3]
        internal_alpha = data[..., 3:4]
        external_alpha = internal_alpha if alpha is None else alpha
        smoothed = _bilateral_smooth(
            rgb, external_alpha, radius, _DEFAULT_SIGMA_SPATIAL, sigma_color, _DEFAULT_SIGMA_ALPHA
        )
        mixed = smoothed + (rgb - smoothed) * amount
        return np.clip(
            np.concatenate([mixed, internal_alpha], axis=-1), 0.0, 1.0
        ).astype(np.float32)

    rgb = data[..., :3]
    smoothed = _bilateral_smooth(
        rgb, alpha, radius, _DEFAULT_SIGMA_SPATIAL, sigma_color, _DEFAULT_SIGMA_ALPHA
    )
    mixed = smoothed + (rgb - smoothed) * amount
    return np.clip(mixed, 0.0, 1.0).astype(np.float32)
