"""Pure NumPy unit tests for the processing pipeline.

Run with any Python + NumPy installation::

    python -m unittest tests.test_processing -v
"""

from __future__ import annotations

import os
import sys
import unittest

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from stylizetex.processing import (  # noqa: E402
    StylizationSettings,
    fit_resolution,
    linear_to_srgb,
    low_frequency_field,
    normalize_resolution,
    process_texture,
    resize_bilinear,
    srgb_to_linear,
    validate_rgb_array,
)


class ColorSpaceTests(unittest.TestCase):
    def test_srgb_linear_roundtrip(self):
        values = np.linspace(0.0, 1.0, 256, dtype=np.float32)
        roundtrip = linear_to_srgb(srgb_to_linear(values))
        np.testing.assert_allclose(roundtrip, values, atol=1e-4)

    def test_srgb_conversion_is_monotonic(self):
        values = np.linspace(0.0, 1.0, 64, dtype=np.float32)
        linear = srgb_to_linear(values)
        self.assertTrue(np.all(np.diff(linear) >= 0.0))


class ValidationTests(unittest.TestCase):
    def test_rgb_is_accepted(self):
        array = np.zeros((4, 4, 3), dtype=np.float32)
        self.assertEqual(validate_rgb_array(array), 3)

    def test_rgba_is_accepted(self):
        array = np.zeros((4, 4, 4), dtype=np.float32)
        self.assertEqual(validate_rgb_array(array), 4)

    def test_non_array_raises_type_error(self):
        with self.assertRaises(TypeError):
            validate_rgb_array([[0.0]])

    def test_wrong_dimensions_raise(self):
        with self.assertRaises(ValueError):
            validate_rgb_array(np.zeros((4, 4), dtype=np.float32))

    def test_wrong_channel_count_raises(self):
        with self.assertRaises(ValueError):
            validate_rgb_array(np.zeros((4, 4, 5), dtype=np.float32))

    def test_integer_dtype_raises_type_error(self):
        with self.assertRaises(TypeError):
            validate_rgb_array(np.zeros((4, 4, 3), dtype=np.uint8))

    def test_nan_raises_value_error(self):
        array = np.zeros((4, 4, 3), dtype=np.float32)
        array[0, 0, 0] = np.nan
        with self.assertRaises(ValueError):
            validate_rgb_array(array)

    def test_out_of_range_raises_value_error(self):
        array = np.zeros((4, 4, 3), dtype=np.float32)
        array[0, 0, 0] = 1.5
        with self.assertRaises(ValueError):
            validate_rgb_array(array)

    def test_empty_raises_value_error(self):
        with self.assertRaises(ValueError):
            validate_rgb_array(np.zeros((0, 4, 3), dtype=np.float32))


class PipelineTests(unittest.TestCase):
    def _sample(self, seed=0):
        rng = np.random.default_rng(seed)
        return rng.random((24, 32, 4), dtype=np.float32)

    def test_output_shape_and_dtype(self):
        result = process_texture(self._sample(), StylizationSettings())
        self.assertEqual(result.shape, (24, 32, 4))
        self.assertEqual(result.dtype, np.float32)

    def test_output_within_range(self):
        result = process_texture(self._sample(), StylizationSettings(contrast=2.0))
        self.assertGreaterEqual(float(result.min()), 0.0)
        self.assertLessEqual(float(result.max()), 1.0)

    def test_alpha_is_preserved_exactly(self):
        source = self._sample()
        result = process_texture(source, StylizationSettings(seed=7))
        np.testing.assert_array_equal(source[..., 3], result[..., 3])

    def test_rgb_input_stays_rgb(self):
        source = self._sample()[..., :3]
        result = process_texture(source, StylizationSettings())
        self.assertEqual(result.shape, (24, 32, 3))

    def test_reproducible_for_same_seed(self):
        source = self._sample()
        first = process_texture(source, StylizationSettings(seed=42))
        second = process_texture(source, StylizationSettings(seed=42))
        np.testing.assert_array_equal(first, second)

    def test_different_seed_changes_result(self):
        source = self._sample()
        first = process_texture(source, StylizationSettings(seed=1))
        second = process_texture(source, StylizationSettings(seed=2))
        self.assertFalse(np.array_equal(first, second))

    def test_color_simplification_reduces_unique_colors(self):
        source = self._sample()[..., :3]
        perceptual = linear_to_srgb(source)
        settings = StylizationSettings(
            color_steps=4,
            color_simplification=1.0,
            variation_strength=0.0,
            contrast=1.0,
            saturation=1.0,
            seed=0,
        )
        result = process_texture(source, settings, is_linear=True)

        def unique_colors(rgb):
            quantized = np.round(rgb * 255).astype(np.int32).reshape(-1, 3)
            return len(np.unique(quantized, axis=0))

        original_unique = unique_colors(perceptual)
        result_unique = unique_colors(linear_to_srgb(result[..., :3]))
        self.assertLess(result_unique, original_unique)

    def test_contrast_one_is_close_to_identity(self):
        source = self._sample()[..., :3]
        settings = StylizationSettings(
            color_simplification=0.0,
            variation_strength=0.0,
            contrast=1.0,
            saturation=1.0,
        )
        result = process_texture(source, settings, is_linear=True)
        np.testing.assert_allclose(result, source, atol=2e-2)

    def test_desaturation_moves_towards_grey(self):
        source = np.zeros((2, 2, 3), dtype=np.float32)
        source[..., 0] = 1.0
        settings = StylizationSettings(
            color_simplification=0.0,
            variation_strength=0.0,
            contrast=1.0,
            saturation=0.0,
        )
        result = process_texture(source, settings, is_linear=True)
        self.assertAlmostEqual(float(result[..., 0].mean()), float(result[..., 1].mean()), places=2)

    def test_accepts_perceptual_input(self):
        source = self._sample()[..., :3]
        result = process_texture(source, StylizationSettings(), is_linear=False)
        self.assertEqual(result.shape, source.shape)

    def test_requires_settings_instance(self):
        with self.assertRaises(TypeError):
            process_texture(self._sample(), {"seed": 1})


class VariationTests(unittest.TestCase):
    def test_field_is_deterministic(self):
        first = low_frequency_field(16, 16, 0.25, seed=3)
        second = low_frequency_field(16, 16, 0.25, seed=3)
        np.testing.assert_array_equal(first, second)

    def test_field_changes_with_seed(self):
        first = low_frequency_field(16, 16, 0.25, seed=3)
        second = low_frequency_field(16, 16, 0.25, seed=4)
        self.assertFalse(np.array_equal(first, second))

    def test_field_is_normalized(self):
        field = low_frequency_field(32, 32, 0.2, seed=1)
        # A smooth field sampled on a small grid is approximately centered.
        self.assertLess(abs(float(field.mean())), 0.25)
        self.assertGreaterEqual(float(field.min()), -1.0)
        self.assertLessEqual(float(field.max()), 1.0)


class ResizeTests(unittest.TestCase):
    def test_identity_when_dimensions_match(self):
        source = np.arange(4 * 5 * 3, dtype=np.float32).reshape(4, 5, 3) / 100.0
        result = resize_bilinear(source, 4, 5)
        np.testing.assert_allclose(result, source)

    def test_output_shape(self):
        source = np.zeros((10, 20, 4), dtype=np.float32)
        result = resize_bilinear(source, 5, 40)
        self.assertEqual(result.shape, (5, 40, 4))

    def test_uniform_image_stays_uniform(self):
        source = np.full((8, 8, 3), 0.5, dtype=np.float32)
        result = resize_bilinear(source, 16, 16)
        np.testing.assert_allclose(result, 0.5, atol=1e-6)

    def test_fit_resolution_preserves_aspect(self):
        self.assertEqual(fit_resolution(1024, 512, 2048), (2048, 1024))
        self.assertEqual(fit_resolution(512, 512, 1024), (1024, 1024))

    def test_invalid_dimensions_raise(self):
        with self.assertRaises(ValueError):
            resize_bilinear(np.zeros((4, 4, 3), dtype=np.float32), 0, 4)


class ResolutionNormalizationTests(unittest.TestCase):
    def test_supported_values_are_kept(self):
        self.assertEqual(normalize_resolution(2048), 2048)
        self.assertEqual(normalize_resolution("1024"), 1024)
        self.assertEqual(normalize_resolution("RES_512"), 512)

    def test_unsupported_values_snap(self):
        self.assertEqual(normalize_resolution(9999), 4096)
        self.assertEqual(normalize_resolution(600), 512)
        self.assertEqual(normalize_resolution(1500), 1024)

    def test_unparseable_value_raises(self):
        with self.assertRaises(ValueError):
            normalize_resolution("none")

    def test_boolean_raises(self):
        with self.assertRaises(ValueError):
            normalize_resolution(True)

    def test_non_finite_values_raise_value_error(self):
        for value in (float("inf"), float("-inf"), float("nan")):
            with self.subTest(value=value):
                # ValueError (not OverflowError) keeps malformed input consistent
                # with the adapter's per-field fallback handling.
                with self.assertRaises(ValueError):
                    normalize_resolution(value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
