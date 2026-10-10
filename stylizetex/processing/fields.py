"""Smooth, seeded procedural fields for the Phase 2 effects (NumPy only).

These helpers are intentionally separate from :mod:`variation` so the Phase 1
low-frequency variation stream and its output remain byte-for-byte untouched.
All randomness comes from an injected :class:`numpy.random.Generator`, which the
Phase 2 effects derive from independent streams (see :mod:`seeding`).
"""

from __future__ import annotations

import numpy as np


def _smoothstep(values: np.ndarray) -> np.ndarray:
    return (values * values * (3.0 - 2.0 * values)).astype(np.float32)


def bilinear_value_noise(
    height: int,
    width: int,
    cells_x: float,
    cells_y: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Return a smooth value-noise field in ``[0, 1]``.

    The random lattice is ``(ceil(cells_y) + 1) x (ceil(cells_x) + 1)``; separate
    cell counts on each axis allow anisotropic (stretched) features. The field is
    sampled with smoothstep-interpolated bilinear weights, so it never contains
    per-pixel white noise.

    Cell counts may be fractional: the sampling span is exactly ``cells_x`` /
    ``cells_y`` across the image, so a continuous brush size maps to a
    continuously changing feature size instead of snapping to integers. Integer
    cell counts behave exactly as before.
    """

    span_x = float(max(1.0, float(cells_x)))
    span_y = float(max(1.0, float(cells_y)))
    cells_x = int(np.ceil(span_x))
    cells_y = int(np.ceil(span_y))
    grid = rng.random((cells_y + 1, cells_x + 1), dtype=np.float32)

    ys = np.linspace(0.0, span_y, int(height), endpoint=False, dtype=np.float32)
    xs = np.linspace(0.0, span_x, int(width), endpoint=False, dtype=np.float32)

    y0 = np.floor(ys).astype(np.int32)
    x0 = np.floor(xs).astype(np.int32)
    y1 = np.minimum(y0 + 1, cells_y)
    x1 = np.minimum(x0 + 1, cells_x)

    fy = _smoothstep((ys - y0).astype(np.float32))[:, None]
    fx = _smoothstep((xs - x0).astype(np.float32))[None, :]

    top_left = grid[y0][:, x0]
    top_right = grid[y0][:, x1]
    bottom_left = grid[y1][:, x0]
    bottom_right = grid[y1][:, x1]

    top = top_left + (top_right - top_left) * fx
    bottom = bottom_left + (bottom_right - bottom_left) * fx
    return (top + (bottom - top) * fy).astype(np.float32)


def multiscale_field(
    height: int,
    width: int,
    *,
    cells_x: float,
    cells_y: float,
    rng: np.random.Generator,
    octaves: int = 3,
    persistence: float = 0.5,
) -> np.ndarray:
    """Sum a few anisotropic value-noise octaves into a field in ``[-1, 1]``.

    ``cells_x``/``cells_y`` control the coarsest (largest) feature size on each
    axis; larger cell counts mean smaller features. They may be fractional so a
    continuous scale parameter keeps varying the feature size smoothly. Summing
    octaves keeps the variation large-scale and correlated instead of grainy.
    """

    octaves = max(1, int(octaves))
    field = np.zeros((int(height), int(width)), dtype=np.float32)
    amplitude = 1.0
    total = 0.0
    cx = float(max(1.0, float(cells_x)))
    cy = float(max(1.0, float(cells_y)))
    for _ in range(octaves):
        field += amplitude * bilinear_value_noise(height, width, cx, cy, rng)
        total += amplitude
        amplitude *= float(persistence)
        cx *= 2.0
        cy *= 2.0

    field /= max(total, 1e-6)
    return (field * 2.0 - 1.0).astype(np.float32)
