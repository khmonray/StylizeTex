"""Pure, deterministic style randomization for the "Randomize Style" button.

``randomized_style(seed)`` maps a seed to a restrained, artistically sensible set
of style parameters. Only *style* fields are randomized — output resolution,
output directory and the last-output path are never touched. The same seed
always yields the same settings.
"""

from __future__ import annotations

import secrets
from dataclasses import fields

import numpy as np

from .settings import StylizationSettings

# Fields the randomizer is allowed to change. Output settings are deliberately
# excluded.
STYLE_FIELDS: tuple[str, ...] = (
    "color_steps",
    "color_simplification",
    "variation_strength",
    "variation_scale",
    "contrast",
    "saturation",
    "hue_variation",
    "brush_scale",
    "paint_variation",
    "micro_detail",
    "seed",
)

# Restrained artistic ranges. Kept explicit so both tests and the UI can reason
# about them.
RANDOM_RANGES: dict[str, tuple[float, float]] = {
    "color_steps": (5.0, 12.0),
    "color_simplification": (0.45, 0.90),
    "variation_strength": (0.08, 0.30),
    "variation_scale": (0.10, 0.35),
    "contrast": (0.95, 1.15),
    "saturation": (0.75, 1.05),
    "hue_variation": (0.02, 0.12),
    "brush_scale": (0.08, 0.30),
    "paint_variation": (0.10, 0.35),
    "micro_detail": (0.15, 0.45),
}

_SEED_MODULUS = 2**31

_NON_STYLE_FIELDS = {"output_resolution"}
_STYLE_FIELD_NAMES = tuple(
    field.name for field in fields(StylizationSettings) if field.name not in _NON_STYLE_FIELDS
)
assert set(STYLE_FIELDS) == set(_STYLE_FIELD_NAMES), (
    "STYLE_FIELDS must whitelist exactly the style fields"
)


def randomized_style(seed: int) -> StylizationSettings:
    """Return deterministic, bounded style settings derived from ``seed``."""

    normalized = int(seed) % _SEED_MODULUS
    rng = np.random.default_rng(normalized)

    low, high = RANDOM_RANGES["color_steps"]
    color_steps = int(rng.integers(int(low), int(high) + 1))

    sampled = {
        name: float(rng.uniform(*bounds))
        for name, bounds in RANDOM_RANGES.items()
        if name != "color_steps"
    }

    return StylizationSettings(
        color_steps=color_steps,
        color_simplification=sampled["color_simplification"],
        variation_strength=sampled["variation_strength"],
        variation_scale=sampled["variation_scale"],
        contrast=sampled["contrast"],
        saturation=sampled["saturation"],
        seed=normalized,
        hue_variation=sampled["hue_variation"],
        brush_scale=sampled["brush_scale"],
        paint_variation=sampled["paint_variation"],
        micro_detail=sampled["micro_detail"],
    )


def pick_new_seed(current: int) -> int:
    """Return a secure random seed that differs from ``current``.

    Uses the operating system's cryptographically secure random source and
    guarantees the result is not equal to the current seed. In the
    (astronomically unlikely) event secure randomness keeps colliding, it falls
    back to a deterministic increment.
    """

    current = int(current)
    for _ in range(64):
        candidate = secrets.randbits(31)
        if candidate != current:
            return candidate
    return (current + 1) % _SEED_MODULUS
