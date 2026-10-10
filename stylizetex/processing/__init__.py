"""Pure, Blender-independent image processing for the stylized texture add-on."""

from .color import (
    apply_color_simplification,
    apply_contrast,
    apply_saturation,
    linear_to_srgb,
    srgb_to_linear,
)
from .fields import bilinear_value_noise, multiscale_field
from .hue import apply_hue_variation, hsv_to_rgb, rgb_to_hsv
from .micro_detail import apply_micro_detail
from .painterly import apply_painterly_variation, painterly_field, stroke_cells
from .pipeline import process_texture
from .randomize import RANDOM_RANGES, STYLE_FIELDS, pick_new_seed, randomized_style
from .resize import fit_resolution, resize_bilinear
from .seeding import effect_rng
from .settings import (
    DEFAULT_RESOLUTION,
    SUPPORTED_RESOLUTIONS,
    StylizationSettings,
    adapt_settings,
    normalize_resolution,
)
from .validate import validate_rgb_array
from .variation import apply_low_frequency_variation, low_frequency_field

__all__ = [
    "DEFAULT_RESOLUTION",
    "RANDOM_RANGES",
    "STYLE_FIELDS",
    "SUPPORTED_RESOLUTIONS",
    "StylizationSettings",
    "adapt_settings",
    "apply_color_simplification",
    "apply_contrast",
    "apply_hue_variation",
    "apply_low_frequency_variation",
    "apply_micro_detail",
    "apply_painterly_variation",
    "apply_saturation",
    "bilinear_value_noise",
    "effect_rng",
    "fit_resolution",
    "hsv_to_rgb",
    "linear_to_srgb",
    "low_frequency_field",
    "multiscale_field",
    "normalize_resolution",
    "painterly_field",
    "process_texture",
    "randomized_style",
    "pick_new_seed",
    "resize_bilinear",
    "rgb_to_hsv",
    "srgb_to_linear",
    "stroke_cells",
    "validate_rgb_array",
]
