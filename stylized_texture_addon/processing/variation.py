"""Seeded smooth low-frequency color variation (NumPy only)."""

from __future__ import annotations

import numpy as np


def _value_noise(height: int, width: int, cells: int, rng: np.random.Generator) -> np.ndarray:
    """Bilinear smooth value noise sampled on a ``cells x cells`` random grid."""

    cells = int(max(1, cells))
    grid = rng.random((cells + 1, cells + 1), dtype=np.float32)

    ys = np.linspace(0.0, float(cells), height, endpoint=False, dtype=np.float32)
    xs = np.linspace(0.0, float(cells), width, endpoint=False, dtype=np.float32)

    y0 = np.floor(ys).astype(np.int32)
    x0 = np.floor(xs).astype(np.int32)
    y1 = np.minimum(y0 + 1, cells)
    x1 = np.minimum(x0 + 1, cells)

    fy = (ys - y0).astype(np.float32)[:, None]
    fx = (xs - x0).astype(np.float32)[None, :]
    fy = fy * fy * (3.0 - 2.0 * fy)
    fx = fx * fx * (3.0 - 2.0 * fx)

    top_left = grid[y0][:, x0]
    top_right = grid[y0][:, x1]
    bottom_left = grid[y1][:, x0]
    bottom_right = grid[y1][:, x1]

    top = top_left + (top_right - top_left) * fx
    bottom = bottom_left + (bottom_right - bottom_left) * fx
    return (top + (bottom - top) * fy).astype(np.float32)


def low_frequency_field(
    height: int,
    width: int,
    scale: float,
    seed: int,
    *,
    octaves: int = 3,
    persistence: float = 0.5,
) -> np.ndarray:
    """Return a deterministic smooth noise field in ``[-1, 1]``.

    ``scale`` is the relative feature size (small values produce larger blobs);
    small uniform noise is deliberately avoided by summing a few smooth
    octaves.
    """

    safe_scale = max(float(scale), 1e-3)
    base_cells = max(2, int(round(1.0 / safe_scale)))
    rng = np.random.default_rng(int(seed) % (2**31))

    field = np.zeros((height, width), dtype=np.float32)
    amplitude = 1.0
    total = 0.0
    cells = base_cells
    for _ in range(max(1, int(octaves))):
        field += amplitude * _value_noise(height, width, cells, rng)
        total += amplitude
        amplitude *= float(persistence)
        cells *= 2

    field /= max(total, 1e-6)
    return (field * 2.0 - 1.0).astype(np.float32)


def apply_low_frequency_variation(
    rgb: np.ndarray,
    strength: float,
    scale: float,
    seed: int,
    *,
    octaves: int = 3,
) -> np.ndarray:
    """Apply smooth large-scale brightness/chroma variation to perceptual RGB."""

    amount = float(np.clip(float(strength), 0.0, 1.0))
    if amount <= 0.0:
        return np.asarray(rgb, dtype=np.float32)

    height, width = int(rgb.shape[0]), int(rgb.shape[1])
    base = low_frequency_field(height, width, scale, seed, octaves=octaves)
    chroma = low_frequency_field(
        height, width, scale, int(seed) + 1, octaves=max(1, octaves - 1)
    )

    value_factor = 1.0 + (0.6 * amount) * base
    result = np.asarray(rgb, dtype=np.float32) * value_factor[..., None]
    result[..., 0] = result[..., 0] * (1.0 + (0.15 * amount) * chroma)
    result[..., 2] = result[..., 2] * (1.0 - (0.15 * amount) * chroma)
    return np.clip(result, 0.0, 1.0).astype(np.float32)
