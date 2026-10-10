"""Unit tests for the tolerant settings adapter (no Blender required)."""

from __future__ import annotations

import os
import sys
import unittest
from typing import Any

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from stylized_texture_addon.processing import (  # noqa: E402
    StylizationSettings,
    adapt_settings,
    normalize_resolution,
)


class OldSettings:
    """Simulates an old/partial settings object with unknown extra fields."""

    def __init__(self):
        self.color_steps = 5
        self.contrast = 1.2
        self.output_resolution = "RES_2048"
        self.legacy_option = "should be ignored"
        self.removed_field = 123


class MalformedSettings:
    def __init__(self):
        self.color_steps = "not a number"
        self.contrast = object()
        self.output_resolution = "oops"
        self.saturation = 0.5


class AdapterTests(unittest.TestCase):
    def test_none_returns_defaults(self):
        settings = adapt_settings(None)
        self.assertEqual(settings, StylizationSettings())
        self.assertIsInstance(settings, StylizationSettings)

    def test_empty_source_returns_defaults(self):
        settings = adapt_settings(object())
        self.assertEqual(settings.as_dict(), StylizationSettings().as_dict())

    def test_partial_source_defaults_missing_fields(self):
        settings = adapt_settings(OldSettings())
        self.assertEqual(settings.color_steps, 5)
        self.assertAlmostEqual(settings.contrast, 1.2)
        self.assertEqual(settings.output_resolution, 2048)
        # missing fields fall back to defaults
        self.assertAlmostEqual(settings.variation_strength, 0.25)
        self.assertEqual(settings.seed, 12345)

    def test_unknown_fields_are_ignored(self):
        settings = adapt_settings(OldSettings())
        self.assertFalse(hasattr(settings, "legacy_option"))
        self.assertFalse(hasattr(settings, "removed_field"))

    def test_dict_source_is_supported(self):
        settings = adapt_settings({"color_steps": 12, "saturation": 1.4, "unknown": 1})
        self.assertEqual(settings.color_steps, 12)
        self.assertAlmostEqual(settings.saturation, 1.4)

    def test_malformed_values_fall_back_to_defaults(self):
        settings = adapt_settings(MalformedSettings())
        self.assertEqual(settings.color_steps, StylizationSettings().color_steps)
        self.assertEqual(settings.contrast, StylizationSettings().contrast)
        self.assertEqual(settings.output_resolution, StylizationSettings().output_resolution)
        self.assertAlmostEqual(settings.saturation, 0.5)

    def test_base_is_used_for_missing_fields(self):
        base = StylizationSettings(color_steps=3, seed=999)
        settings = adapt_settings(object(), base=base)
        self.assertEqual(settings.color_steps, 3)
        self.assertEqual(settings.seed, 999)

    def test_rna_enum_resolution_normalized(self):
        self.assertEqual(normalize_resolution("2048"), 2048)
        settings = adapt_settings(OldSettings())
        self.assertEqual(settings.output_resolution, 2048)

    def test_out_of_range_values_are_clamped(self):
        settings = adapt_settings({"color_steps": 1000, "saturation": 50.0})
        self.assertEqual(settings.color_steps, 32)
        self.assertAlmostEqual(settings.saturation, 3.0)

    def test_roundtrip_as_dict(self):
        original = StylizationSettings()
        settings = adapt_settings(original.as_dict())
        self.assertEqual(settings.as_dict(), original.as_dict())


class NonFiniteAdapterTests(unittest.TestCase):
    """Non-finite (inf/nan) values must fall back per field, never clamp/crash."""

    NON_FINITE = (float("inf"), float("-inf"), float("nan"))

    def test_non_finite_resolution_falls_back_to_default(self):
        default = StylizationSettings().output_resolution
        for value in self.NON_FINITE:
            with self.subTest(value=value):
                settings = adapt_settings({"output_resolution": value})
                self.assertEqual(settings.output_resolution, default)

    def test_non_finite_integer_fields_fall_back_to_default(self):
        defaults = StylizationSettings()
        for name in ("color_steps", "seed"):
            for value in self.NON_FINITE:
                with self.subTest(field=name, value=value):
                    settings = adapt_settings({name: value})
                    self.assertEqual(getattr(settings, name), getattr(defaults, name))

    def test_non_finite_float_fields_fall_back_to_default(self):
        defaults = StylizationSettings()
        for name in (
            "color_simplification",
            "variation_strength",
            "variation_scale",
            "contrast",
            "saturation",
        ):
            for value in self.NON_FINITE:
                with self.subTest(field=name, value=value):
                    settings = adapt_settings({name: value})
                    self.assertEqual(getattr(settings, name), getattr(defaults, name))

    def test_non_finite_values_do_not_clamp_to_bounds(self):
        settings = adapt_settings({"contrast": float("nan"), "saturation": float("-inf")})
        self.assertEqual(settings.contrast, StylizationSettings().contrast)
        self.assertEqual(settings.saturation, StylizationSettings().saturation)

    def test_non_finite_values_fall_back_to_base(self):
        base = StylizationSettings(contrast=0.5, seed=999, output_resolution=512)
        settings = adapt_settings(
            {
                "contrast": float("nan"),
                "seed": float("inf"),
                "output_resolution": float("-inf"),
            },
            base=base,
        )
        self.assertEqual(settings.contrast, 0.5)
        self.assertEqual(settings.seed, 999)
        self.assertEqual(settings.output_resolution, 512)

    def test_non_finite_does_not_break_finite_fields(self):
        settings = adapt_settings({"color_steps": 5, "contrast": float("nan"), "seed": float("inf")})
        self.assertEqual(settings.color_steps, 5)

    def test_direct_construction_handles_non_finite(self):
        defaults = StylizationSettings()
        positive_inf: Any = float("inf")
        negative_inf: Any = float("-inf")
        not_a_number: Any = float("nan")
        settings = StylizationSettings(
            color_steps=positive_inf,
            contrast=not_a_number,
            seed=negative_inf,
            saturation=positive_inf,
        )
        self.assertEqual(settings.color_steps, defaults.color_steps)
        self.assertEqual(settings.contrast, defaults.contrast)
        self.assertEqual(settings.seed, defaults.seed)
        self.assertEqual(settings.saturation, defaults.saturation)


if __name__ == "__main__":
    unittest.main(verbosity=2)
