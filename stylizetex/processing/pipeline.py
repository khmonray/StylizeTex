"""Stylization pipeline: pure, vectorized, Blender-independent.

Phase 1 order (see document.txt section 41):

    Input -> color simplification -> smooth low-frequency variation
          -> contrast -> saturation -> Output

Phase 2 inserts micro-detail smoothing *before* simplification and hue plus
painterly variation *after* simplification, keeping the Phase 1 low-frequency
variation untouched. All Phase 2 effects are skipped when their neutral values
are used, so the default output is byte-for-byte identical to Phase 1.

The pipeline always works on **scene-linear** float RGB/RGBA and only converts
to a perceptual (sRGB) space for the perceptual operations, then back to linear
for the output. Alpha is preserved untouched.
"""

from __future__ import annotations

import numpy as np

from .color import (
    apply_color_simplification,
    apply_contrast,
    apply_saturation,
    linear_to_srgb,
    srgb_to_linear,
)
from .hue import apply_hue_variation
from .micro_detail import apply_micro_detail
from .painterly import apply_painterly_variation
from .settings import StylizationSettings
from .validate import validate_rgb_array
from .variation import apply_low_frequency_variation


def process_texture(
    array: np.ndarray,
    settings: StylizationSettings,
    *,
    is_linear: bool = True,
) -> np.ndarray:
    """Apply the stylization pipeline.

    Parameters
    ----------
    array:
        ``(H, W, 3)`` or ``(H, W, 4)`` float array in ``[0, 1]``.
    settings:
        A :class:`StylizationSettings` instance.
    is_linear:
        When ``True`` (default) ``array`` is treated as scene-linear and the
        output is returned as scene-linear. When ``False`` the array is already
        perceptual/sRGB and is processed as-is.
    """

    if not isinstance(settings, StylizationSettings):
        raise TypeError("settings must be a StylizationSettings instance.")

    channels = validate_rgb_array(array, name="input texture")
    data = np.asarray(array, dtype=np.float32)

    rgb = data[..., :3]
    alpha = data[..., 3:4] if channels == 4 else None

    perceptual = linear_to_srgb(rgb) if is_linear else np.clip(rgb, 0.0, 1.0)

    # Phase 2: reduce fine detail before simplification. Neutral value 1.0
    # skips this entirely, preserving the exact Phase 1 result.
    if settings.micro_detail < 1.0:
        perceptual = apply_micro_detail(perceptual, settings.micro_detail, alpha=alpha)

    perceptual = apply_color_simplification(
        perceptual, settings.color_steps, settings.color_simplification
    )

    # Phase 2: hue and painterly variation. Each is skipped at its neutral 0.
    if settings.hue_variation > 0.0:
        perceptual = apply_hue_variation(
            perceptual, settings.hue_variation, settings.seed
        )
    if settings.paint_variation > 0.0:
        perceptual = apply_painterly_variation(
            perceptual,
            settings.paint_variation,
            settings.brush_scale,
            settings.seed,
        )

    # Phase 1 low-frequency variation stays untouched and in place.
    perceptual = apply_low_frequency_variation(
        perceptual,
        settings.variation_strength,
        settings.variation_scale,
        settings.seed,
    )
    perceptual = apply_contrast(perceptual, settings.contrast)
    perceptual = apply_saturation(perceptual, settings.saturation)

    linear_rgb = srgb_to_linear(perceptual) if is_linear else perceptual

    if alpha is not None:
        result = np.concatenate([linear_rgb, alpha], axis=-1)
    else:
        result = linear_rgb

    result = np.clip(result, 0.0, 1.0).astype(np.float32)
    validate_rgb_array(result, name="output texture")
    return result

